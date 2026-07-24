from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from collection_helpers import (
    downloadedFileKeys,
    installerDefaultActionLabel,
    normalizedButtonLabel,
    parseCollectionAddress,
    staleZeroByteUnfinishedEntries,
    unfinishedDownloadEntries,
)


class ParseCollectionAddressTests(unittest.TestCase):
    def test_parses_nexus_collection_url_without_revision(self):
        parsed = parseCollectionAddress(
            "https://www.nexusmods.com/games/skyrimspecialedition/collections/8vdyr1"
        )

        self.assertEqual(
            parsed,
            {
                "uri": "https://www.nexusmods.com/games/skyrimspecialedition/collections/8vdyr1",
                "game": "skyrimspecialedition",
                "collection": "8vdyr1",
                "revision": None,
            },
        )

    def test_parses_nexus_collection_url_with_revision(self):
        parsed = parseCollectionAddress(
            "https://www.nexusmods.com/games/skyrimspecialedition/collections/xxsqm4/revisions/99"
        )

        self.assertEqual(parsed["collection"], "xxsqm4")
        self.assertEqual(parsed["revision"], 99)

    def test_parses_nxm_collection_url(self):
        parsed = parseCollectionAddress(
            "nxm://skyrimspecialedition/collections/xxsqm4/revisions/99"
        )

        self.assertEqual(
            parsed["uri"],
            "https://www.nexusmods.com/games/skyrimspecialedition/collections/xxsqm4",
        )
        self.assertEqual(parsed["game"], "skyrimspecialedition")
        self.assertEqual(parsed["collection"], "xxsqm4")
        self.assertEqual(parsed["revision"], 99)

    def test_rejects_non_collection_nxm_url(self):
        self.assertIsNone(
            parseCollectionAddress("nxm://skyrimspecialedition/mods/123/files/456")
        )


class DownloadedFileKeysTests(unittest.TestCase):
    def test_returns_only_completed_archives_with_valid_metadata(self):
        with TemporaryDirectory() as tmp:
            downloads = Path(tmp)
            archive = downloads / "Example Mod-123-456.7z"
            archive.write_bytes(b"archive")
            (downloads / "Example Mod-123-456.7z.meta").write_text(
                "[General]\nmodID=123\nfileID=456\n", encoding="utf-8"
            )

            unfinished = downloads / "Partial Mod-111-222.7z.unfinished"
            unfinished.write_bytes(b"partial")
            (downloads / "Partial Mod-111-222.7z.unfinished.meta").write_text(
                "[General]\nmodID=111\nfileID=222\n", encoding="utf-8"
            )

            missing_archive = downloads / "Missing Archive-333-444.7z.meta"
            missing_archive.write_text(
                "[General]\nmodID=333\nfileID=444\n", encoding="utf-8"
            )

            self.assertEqual(downloadedFileKeys(downloads), {(123, 456)})


class UnfinishedDownloadEntriesTests(unittest.TestCase):
    def test_returns_unfinished_archive_entries_by_nexus_key(self):
        with TemporaryDirectory() as tmp:
            downloads = Path(tmp)
            archive = downloads / "Partial Mod-111-222.7z.unfinished"
            archive.write_bytes(b"")
            metadata = downloads / "Partial Mod-111-222.7z.unfinished.meta"
            metadata.write_text("[General]\nmodID=111\nfileID=222\n", encoding="utf-8")

            entries = unfinishedDownloadEntries(downloads)

            self.assertEqual(set(entries), {(111, 222)})
            self.assertEqual(entries[(111, 222)][0]["archive"], archive)
            self.assertEqual(entries[(111, 222)][0]["metadata"], metadata)
            self.assertEqual(entries[(111, 222)][0]["archive_size"], 0)

    def test_ignores_unfinished_metadata_without_nexus_ids(self):
        with TemporaryDirectory() as tmp:
            downloads = Path(tmp)
            (downloads / "Broken.7z.unfinished").write_bytes(b"")
            (downloads / "Broken.7z.unfinished.meta").write_text(
                "[General]\nmodID=bad\n", encoding="utf-8"
            )

            self.assertEqual(unfinishedDownloadEntries(downloads), {})

    def test_identifies_stale_zero_byte_unfinished_entries(self):
        entries = [
            {
                "archive": Path("Partial.7z.unfinished"),
                "metadata": Path("Partial.7z.unfinished.meta"),
                "archive_size": 0,
                "mtime": 100,
            }
        ]

        self.assertEqual(staleZeroByteUnfinishedEntries(entries, 200, 60), entries)

    def test_preserves_fresh_or_non_empty_unfinished_entries(self):
        fresh_entry = {
            "archive": Path("Fresh.7z.unfinished"),
            "metadata": Path("Fresh.7z.unfinished.meta"),
            "archive_size": 0,
            "mtime": 190,
        }
        partial_entry = {
            "archive": Path("Partial.7z.unfinished"),
            "metadata": Path("Partial.7z.unfinished.meta"),
            "archive_size": 128,
            "mtime": 100,
        }

        self.assertEqual(staleZeroByteUnfinishedEntries([fresh_entry], 200, 60), [])
        self.assertEqual(staleZeroByteUnfinishedEntries([partial_entry], 200, 60), [])


class InstallerDefaultActionLabelTests(unittest.TestCase):
    def test_normalizes_decorated_button_labels(self):
        self.assertEqual(normalizedButtonLabel("&Next >"), "next")
        self.assertEqual(normalizedButtonLabel("< &Back"), "back")

    def test_selects_enabled_next_on_fomod_dialog(self):
        self.assertEqual(
            installerDefaultActionLabel(
                "Glorious Doors of Skyrim (GDOS) SE",
                [("&Back", False), ("&Next >", True), ("Cancel", True)],
            ),
            "next",
        )

    def test_selects_enabled_install_on_final_fomod_page(self):
        self.assertEqual(
            installerDefaultActionLabel(
                "UNP Female Body Renewal",
                [("&Back", True), ("Install", True), ("Cancel", True)],
            ),
            "install",
        )

    def test_ignores_mo2_known_dialogs(self):
        for title in ("Quick Install", "Mod Exists", "Error"):
            self.assertIsNone(
                installerDefaultActionLabel(
                    title,
                    [("Next", True), ("Install", True), ("Cancel", True)],
                )
            )

    def test_requires_cancel_button_to_avoid_generic_next_prompts(self):
        self.assertIsNone(
            installerDefaultActionLabel("NXM Collection Link Handler", [("Next", True)])
        )


if __name__ == "__main__":
    unittest.main()
