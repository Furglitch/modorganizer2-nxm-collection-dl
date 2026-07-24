import re
from configparser import ConfigParser
from pathlib import Path

FOMOD_ADVANCE_EXCLUDED_TITLES = {
    "",
    "Error",
    "Install Mods",
    "Mod Exists",
    "Quick Install",
    "NXM Collection Installer - Installing Mods",
    "NXM Collection Installer - Select Collection",
}


def normalizedButtonLabel(label):
    return " ".join(
        str(label)
        .replace("&", "")
        .replace("<", "")
        .replace(">", "")
        .strip()
        .lower()
        .split()
    )


def installerDefaultActionLabel(window_title, buttons):
    """Return the FOMOD default action to click, or None when unsafe.

    ``buttons`` is an iterable of ``(label, enabled)`` pairs. The helper is kept
    GUI-free so the dialog classification can be unit-tested outside MO2.
    """
    if window_title in FOMOD_ADVANCE_EXCLUDED_TITLES:
        return None

    enabled_by_label = {}
    labels = set()
    for label, enabled in buttons:
        normalized = normalizedButtonLabel(label)
        labels.add(normalized)
        enabled_by_label[normalized] = bool(enabled)

    if "cancel" not in labels:
        return None

    for label in ("next", "install"):
        if enabled_by_label.get(label):
            return label

    return None


def parseCollectionAddress(address):
    """Parse supported Nexus collection web and nxm:// addresses."""
    normalized = address.strip()
    normalized = normalized.replace("http://", "https://")
    normalized = normalized.split("?", 1)[0].split("#", 1)[0]
    for suffix in ["/mods", "/comments", "/changelog", "/bugs"]:
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)]

    web_match = re.match(
        r"^https:\/\/(?:www\.)?nexusmods\.com\/games\/([a-zA-Z0-9_\-]+)"
        r"\/collections\/([a-zA-Z0-9_\-]+)"
        r"(?:\/revisions\/([0-9]+))?\/?$",
        normalized,
    )
    if web_match:
        return {
            "uri": (
                "https://www.nexusmods.com/games/"
                f"{web_match.group(1)}/collections/{web_match.group(2)}"
            ),
            "game": web_match.group(1),
            "collection": web_match.group(2),
            "revision": int(web_match.group(3)) if web_match.group(3) else None,
        }

    nxm_match = re.match(
        r"^nxm:\/\/([a-zA-Z0-9_\-]+)\/collections\/([a-zA-Z0-9_\-]+)"
        r"\/revisions\/([0-9]+)\/?$",
        normalized,
    )
    if nxm_match:
        return {
            "uri": (
                "https://www.nexusmods.com/games/"
                f"{nxm_match.group(1)}/collections/{nxm_match.group(2)}"
            ),
            "game": nxm_match.group(1),
            "collection": nxm_match.group(2),
            "revision": int(nxm_match.group(3)),
        }

    return None


def downloadedFileKeys(downloads_dir):
    """Return Nexus (mod_id, file_id) pairs with a completed archive on disk."""
    keys = set()
    if not downloads_dir or not downloads_dir.exists():
        return keys

    for metadata_file in downloads_dir.glob("*.meta"):
        if metadata_file.name.endswith(".unfinished.meta"):
            continue

        parser = ConfigParser()
        try:
            parser.read(metadata_file, encoding="utf-8")
            general = parser["General"]
            mod_id = int(general["modID"])
            file_id = int(general["fileID"])
        except (OSError, KeyError, ValueError):
            continue

        archive_file = metadata_file.with_suffix("")
        if archive_file.exists() and archive_file.stat().st_size > 0:
            keys.add((mod_id, file_id))

    return keys


def readDownloadMetaKey(metadata_file):
    """Read a Nexus (mod_id, file_id) pair from an MO2 download metadata file."""
    parser = ConfigParser()
    try:
        parser.read(metadata_file, encoding="utf-8")
        general = parser["General"]
        return (int(general["modID"]), int(general["fileID"]))
    except (OSError, KeyError, ValueError):
        return None


def unfinishedDownloadEntries(downloads_dir):
    """Return unfinished MO2 download files indexed by Nexus (mod_id, file_id)."""
    entries = {}
    if not downloads_dir or not downloads_dir.exists():
        return entries

    for metadata_file in downloads_dir.glob("*.unfinished.meta"):
        key = readDownloadMetaKey(metadata_file)
        if key is None:
            continue

        archive_file = Path(str(metadata_file)[: -len(".meta")])
        try:
            archive_size = archive_file.stat().st_size if archive_file.exists() else 0
            metadata_mtime = metadata_file.stat().st_mtime
            archive_mtime = archive_file.stat().st_mtime if archive_file.exists() else 0
        except OSError:
            continue

        entries.setdefault(key, []).append(
            {
                "archive": archive_file,
                "metadata": metadata_file,
                "archive_size": archive_size,
                "mtime": max(metadata_mtime, archive_mtime),
            }
        )

    return entries


def staleZeroByteUnfinishedEntries(entries, now, stale_seconds):
    """Return unfinished entries safe to discard before a retry.

    MO2 may leave a zero-byte ``.unfinished`` archive behind when a download
    never actually starts. Requeueing the same file while that stale entry is
    present can trigger a blocking "Download again?" dialog. Non-empty partial
    downloads are intentionally preserved so MO2 can resume them.
    """
    if stale_seconds <= 0 or not entries:
        return []
    if any(entry["archive_size"] > 0 for entry in entries):
        return []

    newest_mtime = max(entry["mtime"] for entry in entries)
    if now - newest_mtime < stale_seconds:
        return []

    return list(entries)
