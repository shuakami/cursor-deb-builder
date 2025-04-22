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