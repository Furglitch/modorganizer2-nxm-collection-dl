# MO2 Nexus Collection Downloader
A small Mod Organizer 2 (MO2) plugin that lets you download Nexus Mods (NXM) Collections directly from within MO2.
This plugin parses a NXM collection URL, shows available revisions, and helps you fetch the mods and resources included in that revision so you can install them in MO2.

## Features
- Enter a NXM collection URL and inspect the collection metadata (name, author, description, thumbnail).
- Choose a specific revision of the collection.
- View counts for essential, optional, external and bundled resources.
- Select optional/external items to include before downloading.

#### Currently Unimplemented:
- Installation of bundled resources (unable to find a collection to test them)

## Installation
1. Download the [latest release](https://github.com/Furglitch/modorganizer2-nxm-collection-dl/releases/latest)
2. Extract the downloaded file into your MO2 `plugins` directory.
3. In MO2, open the Plugins manager and enable "NXM Collections Downloader" if it is not enabled by default.
4. Restart MO2 if needed. You should find the tool under the Tools menu.

## Usage
1. Open the plugin (Tools -> NXM Collections Downloader).
2. Paste a NXM collection URL (example: `https://www.nexusmods.com/games/skyrimspecialedition/collections/qdurkx`).
3. Select the collection revision you'd like to install.
4. Review and select optional/external items as prompted.
5. Proceed to download/install using MO2's normal workflow (the plugin gathers the mod/file IDs and resources).