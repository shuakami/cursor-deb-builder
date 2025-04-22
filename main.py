# -*- coding: utf-8 -*-
import json
import re
import time
import asyncio
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
import sys
import io
from urllib.parse import urlparse
import os

# --- Configuration ---
TARGET_URL = "https://www.cursor.com/cn/downloads"
BROWSER_LAUNCH_TIMEOUT = 20000
PAGE_LOAD_TIMEOUT = 35000
# PAGE_RELOAD_TIMEOUT = 30000 # Reload timeout can use PAGE_LOAD_TIMEOUT
ELEMENT_WAIT_TIMEOUT = 15000
REQUEST_WAIT_TIMEOUT = 12000
CLICK_TIMEOUT = 8000
TEXT_FETCH_TIMEOUT = 5000
ELEMENT_VISIBLE_TIMEOUT = 7000
RETRY_COUNT = 1 # Retries for individual link operations

# --- Optional: Configure UTF-8 output ---
# sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
# sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def extract_filename_from_url(url):
    if not isinstance(url, str): return "Invalid URL input"
    try:
        path = urlparse(url).path
        filename = path.split('/')[-1]
        return filename if filename else "Unknown filename"
    except Exception: return "Failed to parse URL"

async def get_cursor_downloads_final_reload(url=TARGET_URL):
    """
    V6: Uses serial processing with page reload before each section
    for maximum isolation, plus retries for link operations.
    Outputs JSON files.
    """
    start_time = time.time()
    downloads_data = {}
    success_count = 0
    fail_count = 0
    browser = None
    context = None

    print("Starting Playwright (async)...")
    try:
        async with async_playwright() as p:
            print("Launching browser (Chromium)...")
            browser = await p.chromium.launch(headless=True, timeout=BROWSER_LAUNCH_TIMEOUT)
            context = await browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36')
            page = await context.new_page()

            async def load_or_reload_and_wait():
                # Helper to load/reload and wait for elements
                action = "Loading" if page.url == "about:blank" else "Reloading"
                print(f"{action} page {url}...")
                try:
                    # Use 'domcontentloaded' for reload as network might not be idle quickly
                    wait_state = 'domcontentloaded' # Use faster state for reload
                    if action == "Loading":
                        await page.goto(url, wait_until=wait_state, timeout=PAGE_LOAD_TIMEOUT)
                    else:
                         # Reload waits for 'load' by default, maybe too long, use 'domcontentloaded'
                        await page.reload(wait_until=wait_state, timeout=PAGE_LOAD_TIMEOUT)

                    print("Page loaded/reloaded (DOM ready).")
                except PlaywrightTimeoutError as e:
                    print(f"Error: {action} page timed out: {e}")
                    return False

                print("Waiting for download section presence...")
                try:
                    # Just wait for the container, not specific elements yet
                    await page.locator('main > div > div > section').first.wait_for(state='attached', timeout=ELEMENT_WAIT_TIMEOUT)
                    print("Download section container present.")
                    # Add a small fixed delay after reload/load, sometimes helps rendering
                    await page.wait_for_timeout(500)
                    return True
                except PlaywrightTimeoutError as e:
                    print(f"Error: Waiting for download section container timed out: {e}")
                    return False

            # --- Initial Page Load ---
            if not await load_or_reload_and_wait():
                if browser and browser.is_connected(): await browser.close()
                return None, f"Initial page load failed: {TARGET_URL}"

            # --- Get Section Count ---
            version_section_locator = page.locator('main > div > div > section')
            try:
                section_count = await version_section_locator.count()
            except Exception as e:
                 print(f"Error counting sections: {e}")
                 if browser and browser.is_connected(): await browser.close()
                 return None, "Failed to count version sections."

            print(f"Found {section_count} version sections.")
            if section_count == 0:
                 print("Error: No version sections found on the page.")
                 if browser and browser.is_connected(): await browser.close()
                 return None, "No download version sections found."

            # --- Process Sections Serially ---
            for section_index in range(section_count):
                print("-" * 40)
                print(f"Starting processing section {section_index + 1}/{section_count}")

                # --- Re-locate elements for the current section after potential reload ---
                current_section_locator = page.locator('main > div > div > section').nth(section_index)

                current_version = f"Unknown_Version_{section_index + 1}"
                version_raw_text = "Not fetched"

                try:
                    # Get version title
                    version_text_locator = current_section_locator.locator('p[class*="text-2xl"], p[class*="text-4xl"]').first
                    try:
                        await version_text_locator.wait_for(state='visible', timeout=ELEMENT_VISIBLE_TIMEOUT)
                        version_raw_text = await version_text_locator.inner_text(timeout=TEXT_FETCH_TIMEOUT)
                    except Exception as title_err:
                        print(f"Failed to get version title for section {section_index+1}: {title_err}")
                        version_raw_text = f"Failed_Title_Fetch_{section_index+1}"

                    print(f"Processing section: {version_raw_text}")
                    # Extract version number
                    match = re.search(r'(\d+\.\d+(\.\d+)*)', version_raw_text)
                    if match: current_version = match.group(1)
                    else:
                         match_latest = re.search(r'\(([\d.]+)\)', version_raw_text)
                         if match_latest: current_version = match_latest.group(1)
                         else: print(f"Warning: Could not extract standard version number from '{version_raw_text}'.")

                    print(f"Extracted version: {current_version}")

                    # Get links for the current section
                    link_locator_list = current_section_locator.locator('div.grid a')
                    try:
                        link_count = await link_locator_list.count()
                    except Exception as e:
                        print(f"Error counting links in section {section_index+1}: {e}")
                        continue # Skip processing links if count fails

                    print(f"Found {link_count} download links in version {current_version}.")

                    # --- Process Links Serially within the section ---
                    for link_index in range(link_count):
                        current_link_locator = link_locator_list.nth(link_index)
                        link_start_time = time.time()
                        platform_text = f"Unknown_Platform_{link_index+1}"
                        description_text = f"Unknown_Description_{link_index+1}"
                        download_url = "Fetch failed"
                        filename = "Unknown"
                        error_occurred_final = True
                        attempt = 0

                        while attempt <= RETRY_COUNT:
                            if attempt > 0:
                                print(f"    Retrying ({attempt}/{RETRY_COUNT})...")
                                await page.wait_for_timeout(500 * attempt)

                            link_error_this_attempt = False
                            try:
                                # Get link text
                                try:
                                    platform_locator = current_link_locator.locator('p').nth(0)
                                    description_locator = current_link_locator.locator('p').nth(1)
                                    # Ensure element is actionable before getting text
                                    await current_link_locator.wait_for(state='visible', timeout=ELEMENT_VISIBLE_TIMEOUT)
                                    platform_text = await platform_locator.inner_text(timeout=TEXT_FETCH_TIMEOUT)
                                    description_text = await description_locator.inner_text(timeout=TEXT_FETCH_TIMEOUT)
                                    if attempt == 0: print(f"  [{current_version} - {link_index+1}/{link_count}] Processing: {platform_text} - {description_text}")
                                except Exception as text_err:
                                    print(f"  [{current_version} - {link_index+1}] (Attempt {attempt}) Error getting link text: {text_err}")
                                    link_error_this_attempt = True
                                    if attempt >= RETRY_COUNT:
                                        download_url = f"Error getting text (Retried {RETRY_COUNT} times)"
                                        filename = "Unknown (Text Error)"
                                    else: attempt += 1; continue
                                    break

                                # Capture network request
                                try:
                                    def is_download_request(request):
                                        req_url = request.url
                                        return ('downloads.cursor.com/production/' in req_url and
                                                any(req_url.endswith(ext) for ext in ['.dmg', '.exe', '.AppImage']))

                                    if attempt == 0: print(f"    Waiting for request...")
                                    else: print(f"    (Attempt {attempt}) Waiting for request...")

                                    async with page.expect_request(is_download_request, timeout=REQUEST_WAIT_TIMEOUT) as request_info:
                                        if attempt == 0: print(f"    Clicking (no_wait_after=True)...")
                                        else: print(f"    (Attempt {attempt}) Clicking (no_wait_after=True)...")
                                        # Click might need to be retried if element detached after reload etc.
                                        await current_link_locator.click(timeout=CLICK_TIMEOUT, no_wait_after=True)
                                        print("    Click sent, waiting for capture...")
                                        request_object = await request_info.value
                                    download_url = request_object.url
                                    filename = extract_filename_from_url(download_url)
                                    print(f"    Success! URL: ...{download_url[-60:]}")
                                    error_occurred_final = False
                                    success_count += 1
                                    break

                                except PlaywrightTimeoutError as request_timeout_err:
                                    error_type = "Request timeout" if "expect_request" in str(request_timeout_err) else "Click/Element timeout"
                                    print(f"    Error: (Attempt {attempt}) {platform_text} - {description_text} -> {error_type}")
                                    link_error_this_attempt = True
                                    if attempt >= RETRY_COUNT:
                                        download_url = f"{error_type} (Retried {RETRY_COUNT} times)"
                                        filename = f"Unknown ({error_type})"
                                    else: attempt += 1; continue
                                    break
                                except Exception as click_err:
                                    print(f"    Error: (Attempt {attempt}) Exception during click/capture: {click_err}")
                                    link_error_this_attempt = True
                                    if attempt >= RETRY_COUNT:
                                         download_url = f"Click/Capture Error (Retried {RETRY_COUNT} times)"
                                         filename = "Unknown (Capture Error)"
                                    else: attempt += 1; continue
                                    break

                            except Exception as outer_link_err:
                                print(f"  Outer error processing link {link_index+1} (Attempt {attempt}): {outer_link_err}")
                                link_error_this_attempt = True
                                if attempt >= RETRY_COUNT:
                                    download_url = f"Outer processing error (Retried {RETRY_COUNT} times)"
                                    filename = "Unknown (Outer Error)"
                                else: attempt += 1; continue
                                break

                        # --- End of Retry Loop ---

                        if not error_occurred_final:
                             if current_version not in downloads_data:
                                 downloads_data[current_version] = []
                             downloads_data[current_version].append({
                                 "platform": platform_text,
                                 "description": description_text,
                                 "url": download_url,
                                 "filename": filename
                             })
                        else:
                             # Only increment final fail count after all retries
                             if attempt >= RETRY_COUNT:
                                 fail_count += 1

                        link_duration = time.time() - link_start_time
                        print(f"    Time taken: {link_duration:.2f} sec {'(Failed after retries)' if error_occurred_final else ''}")
                        await page.wait_for_timeout(150) # Slightly longer pause

                except Exception as section_process_err:
                    print(f"Error processing links within section {section_index+1}: {section_process_err}")
                    # Mark failures for links in this section if we couldn't even start processing them
                    fail_count += await current_section_locator.locator('div.grid a').count()


            # --- End of Section Loop ---

            print("\nAll sections processed. Closing browser...")
            await browser.close()
            print("Browser closed.")

            # --- Prepare Final Results ---
            end_time = time.time()
            print(f"\nScript finished. Total time: {end_time - start_time:.2f} sec.")
            print(f"Links successfully processed: {success_count}, Failed (after retries): {fail_count}.")

            if not downloads_data:
                print("No download data was successfully extracted.")
                return None, "No successful download data extracted."

            # --- Write Files ---
            all_output_file = 'cursor_downloads_all.json'
            try:
                with open(all_output_file, 'w', encoding='utf-8') as f:
                    json.dump(downloads_data, f, ensure_ascii=False, indent=4)
                print(f"Successfully wrote all data to {all_output_file}")
            except Exception as write_err:
                print(f"Error writing all data to {all_output_file}: {write_err}")

            latest_linux_data = {}
            if downloads_data:
                try:
                    latest_version_key = sorted(downloads_data.keys(), key=lambda v: [int(p) for p in v.split('.')], reverse=True)[0]
                except:
                     latest_version_key = next(iter(downloads_data))

                print(f"Identifying latest version as: {latest_version_key}")
                latest_version_downloads = downloads_data.get(latest_version_key, [])
                latest_linux_items = [
                    item for item in latest_version_downloads
                    if item.get("platform", "").upper() == "LINUX"
                ]

                if latest_linux_items: # Check if list is not empty
                    latest_linux_data[latest_version_key] = latest_linux_items
                    latest_linux_output_file = 'cursor_downloads_latest_linux.json'
                    try:
                        with open(latest_linux_output_file, 'w', encoding='utf-8') as f:
                            json.dump(latest_linux_data, f, ensure_ascii=False, indent=4)
                        print(f"Successfully wrote latest Linux data to {latest_linux_output_file}")
                    except Exception as write_err:
                        print(f"Error writing latest Linux data to {latest_linux_output_file}: {write_err}")
                else:
                    print(f"No successful Linux downloads found for the latest version ({latest_version_key}).")


            return downloads_data, None

    except Exception as e:
        print(f"A critical error occurred: {e}")
        if browser and browser.is_connected():
            print("Attempting to close browser after critical error...")
            try: await browser.close()
            except Exception as close_err: print(f"Error closing browser during error handling: {close_err}")
        return None, f"Critical error: {str(e)}"

async def main():
    print("Starting V6: Serial fetch with page reload per section, retries, file output...")
    final_data, error_message = await get_cursor_downloads_final_reload()
    if error_message:
        print(f"\n--- SCRIPT FAILED ---")
        print(error_message)
    elif final_data:
        print(f"\n--- SCRIPT COMPLETED SUCCESSFULLY ---")
    else:
        print("\n--- SCRIPT FINISHED BUT NO DATA COLLECTED ---")

if __name__ == "__main__":
    asyncio.run(main())