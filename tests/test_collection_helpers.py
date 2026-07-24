from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from collection_helpers import (
    allocateUniqueModName,
    coerceDownloadId,
    downloadCompletionPlan,
    downloadedFileKeys,
    hasPartialUnfinishedEntries,
    installerDefaultActionLabel,
    normalizedButtonLabel,
    parseCollectionAddress,
    sanitizeModName,
    staleZeroByteUnfinishedEntries,
    unfinishedDownloadEntries,
    zeroByteUnfinishedEntries,
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

    def test_identifies_zero_byte_unfinished_entries_for_prequeue_cleanup(self):
        entries = [
            {
                "archive": Path("Queued.7z.unfinished"),
                "metadata": Path("Queued.7z.unfinished.meta"),
                "archive_size": 0,
                "mtime": 200,
            }
        ]

        self.assertEqual(zeroByteUnfinishedEntries(entries), entries)

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
        self.assertEqual(zeroByteUnfinishedEntries([partial_entry]), [])

    def test_identifies_resumable_partial_unfinished_entries(self):
        partial_entry = {
            "archive": Path("Partial.7z.unfinished"),
            "metadata": Path("Partial.7z.unfinished.meta"),
            "archive_size": 128,
            "mtime": 100,
        }
        empty_entry = {
            "archive": Path("Empty.7z.unfinished"),
            "metadata": Path("Empty.7z.unfinished.meta"),
            "archive_size": 0,
            "mtime": 100,
        }

        self.assertTrue(hasPartialUnfinishedEntries([partial_entry]))
        self.assertTrue(hasPartialUnfinishedEntries([empty_entry, partial_entry]))
        self.assertFalse(hasPartialUnfinishedEntries([empty_entry]))
        self.assertFalse(hasPartialUnfinishedEntries([]))


class CoerceDownloadIdTests(unittest.TestCase):
    def test_accepts_non_negative_integer_values(self):
        self.assertEqual(coerceDownloadId(0), 0)
        self.assertEqual(coerceDownloadId("42"), 42)

    def test_rejects_missing_invalid_and_negative_values(self):
        self.assertIsNone(coerceDownloadId(None))
        self.assertIsNone(coerceDownloadId("not-an-id"))
        self.assertIsNone(coerceDownloadId(-1))


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


class DownloadCompletionPlanTests(unittest.TestCase):
    def test_failed_downloads_keep_dialog_open_for_review(self):
        self.assertEqual(
            downloadCompletionPlan(
                failed_count=1,
                has_on_complete=True,
                close_on_success=True,
                delay_ms=5000,
            ),
            {
                "run_complete": False,
                "close_immediately": False,
                "close_delay_ms": 0,
            },
        )

    def test_auto_install_flow_closes_before_running_callback(self):
        self.assertEqual(
            downloadCompletionPlan(
                failed_count=0,
                has_on_complete=True,
                close_on_success=True,
                delay_ms=5000,
            ),
            {
                "run_complete": True,
                "close_immediately": True,
                "close_delay_ms": 0,
            },
        )

    def test_manual_followup_flow_still_gets_success_close_delay(self):
        self.assertEqual(
            downloadCompletionPlan(
                failed_count=0,
                has_on_complete=True,
                close_on_success=False,
                delay_ms=5000,
            ),
            {
                "run_complete": True,
                "close_immediately": False,
                "close_delay_ms": 5000,
            },
        )

    def test_plain_success_flow_uses_success_close_delay(self):
        self.assertEqual(
            downloadCompletionPlan(
                failed_count=0,
                has_on_complete=False,
                close_on_success=False,
                delay_ms=5000,
            ),
            {
                "run_complete": False,
                "close_immediately": False,
                "close_delay_ms": 5000,
            },
        )


class AllocateUniqueModNameTests(unittest.TestCase):
    def test_sanitizes_path_separators_and_empty_names(self):
        self.assertEqual(sanitizeModName(" A/B\\C  "), "A-B-C")
        self.assertEqual(sanitizeModName("   "), "Collection Mod")

    def test_uses_base_name_when_available(self):
        used = set()
        counts = {}

        self.assertEqual(
            allocateUniqueModName("New Statue", used, counts), "New Statue"
        )
        self.assertEqual(used, {"New Statue"})
        self.assertEqual(counts, {"New Statue": 2})

    def test_suffixes_duplicate_collection_entries(self):
        used = set()
        counts = {}

        self.assertEqual(
            allocateUniqueModName("New Statue", used, counts), "New Statue"
        )
        self.assertEqual(
            allocateUniqueModName("New Statue", used, counts), "New Statue #2"
        )
        self.assertEqual(
            allocateUniqueModName("New Statue", used, counts), "New Statue #3"
        )

    def test_skips_existing_profile_names(self):
        used = {"New Statue", "New Statue #2"}
        counts = {}

        self.assertEqual(
            allocateUniqueModName("New Statue", used, counts), "New Statue #3"
        )
        self.assertEqual(counts, {"New Statue": 4})


if __name__ == "__main__":
    unittest.main()
