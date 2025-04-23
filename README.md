# Cursor DEB Builder

This repository automatically builds Debian (`.deb`) packages for the latest Linux version of the Cursor editor using Github Actions.

## How it works

1.  A scheduled Github Action runs daily (or can be triggered manually).
2.  It uses a Python script (`main.py` with Playwright) to scrape the official Cursor download page for the latest Linux AppImage version and URL.
3.  It checks if a Github Release for this version already exists.
4.  If the version is new:
    *   It downloads the AppImage.
    *   It uses the `make-deb.sh` script to package the AppImage into a `.deb` file.
    *   It creates a new Github Release tagged with the version number and uploads the `.deb` file as an asset.

## Usage

Check the [Releases](https://github.com/shuakami/cursor-deb-builder/releases) page for the latest `.deb` packages.

## Installation

### Via APT (Debian/Ubuntu/Zorin and derivatives)

1.  **Set up the repository:**
    Run the following command to add the Cloudsmith repository and its GPG key to your system. You might need to install `curl` first (`sudo apt install curl`).
    ```bash
    curl -1sLf \
      'https://dl.cloudsmith.io/QhHWEwzA2fBaF9VC/shuakami/cursor-linux/setup.deb.sh' \
      | sudo -E bash
    ```

2.  **Install Cursor:**
    After setting up the repository, update your package list and install Cursor:
    ```bash
    sudo apt-get update
    sudo apt-get install cursor
    ```
    This will install the latest available version.

    *(Optional) Install a specific version (e.g., 0.48):*
    ```bash
    # sudo apt-get install cursor=0.48
    ``` 