# MO2 Nexus Collection Downloader

A Mod Organizer 2 plugin that lets you download Nexus Mods collections directly within MO2. Simply paste a collection URL, pick a revision, and download the mods you want.

## Features
- Enter a NXM collection URL and inspect the collection metadata (name, author, description, thumbnail).
- Choose a specific revision of the collection.
- View counts for essential, optional, external and bundled resources.
- Select optional/external items to include before downloading.
- Opens mod downloads in web browser if the user does not have Premium

#### Currently Unimplemented:
- FOMOD Selections (need to see if possible)
- Cannot auto-detect user Premium status
- Unable to implement bundled resources (Not in Nexus API documentation, will check if possible soon.)

## Installation

1. Download the [latest release](https://github.com/Furglitch/modorganizer2-nxm-collection-dl/releases/latest)
2. Extract it into your MO2 `plugins` folder
3. Enable "NXM Collections Downloader" in MO2's Plugins manager, if it's not already enabled.
4. Find it under Tools → NXM Collections Downloader

## How to Use

1. Open the plugin from the Tools menu
2. Paste a collection URL (e.g., `https://www.nexusmods.com/games/skyrimspecialedition/collections/qdurkx`)
3. Choose a revision
4. Select any optional items you want
5. Download via the 'Download Collection' tool
   - If you don't have Premium, make sure to check the 'Open in Browser' option to open the mod pages in your web browser for manual downloading.
6. Install the downloaded mods in MO2 using the 'Install Downloaded Collection' tool.

The installer processes one downloaded archive at a time and waits briefly before
starting the next archive. This avoids overlapping MO2 installer sessions while
still allowing normal MO2 installer dialogs to appear when a mod needs manual
choices. Installed mods are not enabled by default; enable
`activate_mods_after_install` in the plugin settings if you want the install pass
to check them in MO2 after it finishes. Collection files are installed as
separate MO2 mod rows by default; repeated files from the same Nexus mod use
`#2`, `#3`, and later suffixes instead of silently merging into one row. FOMOD
choice replay is not implemented, but `auto_advance_fomod_defaults` can
optionally advance visible FOMOD installers by accepting their selected default
choices.

## Contributing

Contributions welcome! Feel free to open issues or submit pull requests.

Set up the dev environment with `uv sync`, set up pre-commit hooks, then copy the files to your MO2 plugins directory to test.
