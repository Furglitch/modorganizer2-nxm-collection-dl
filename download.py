import time
from pathlib import Path
from PyQt6.QtCore import QObject, QSize, QThread, QTimer, Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QFontMetrics
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)

from .api import fetchRevisions, fetchInfo, fetchModInfo
from . import __meta__
from . import var
from .collection_helpers import (
    downloadedFileKeys,
    parseCollectionAddress,
    staleZeroByteUnfinishedEntries,
    unfinishedDownloadEntries,
    zeroByteUnfinishedEntries,
)

qDebug = var.debug


def downloadDirectory():
    plugin_instance = getattr(__meta__, "_download_plugin", None)
    organizer = getattr(plugin_instance, "_organizer", None)
    if not organizer:
        return None
    return Path(organizer.basePath()) / "downloads"


def selectLatestRevision():
    revisions = fetchRevisions(var.uri)
    revision_list = (
        revisions.get("collection", {}).get("revisions", []) if revisions else []
    )
    revision_numbers = [
        revision.get("revisionNumber")
        for revision in revision_list
        if revision.get("revisionNumber") is not None
    ]
    return max(revision_numbers) if revision_numbers else None


def applyCollectionAddress(address):
    parsed = parseCollectionAddress(address)
    if not parsed:
        return None
    var.uri = parsed["uri"]
    var.game = parsed["game"]
    var.collection = parsed["collection"]
    var.revision = parsed["revision"]
    qDebug(
        "[NXMColDL] Collection address parsed: "
        f"{var.game}/{var.collection} rev {var.revision or 'latest'}"
    )
    return parsed


def populateCollectionInfo():
    collection_data = fetchInfo(var.uri)
    qDebug(f"[NXMColDL] Collection Info: {var.cleanJson(collection_data)}")
    if not collection_data:
        return False

    collection = collection_data["collection"]
    var.author = collection["user"]["name"]
    var.name = collection["name"]
    var.summary = var.cleanJson(collection["summary"], True)
    var.thumbnail = collection.get("tileImage", {}).get("thumbnailUrl")
    qDebug(f"[NXMColDL] Collection Name: {var.name}")
    qDebug(f"[NXMColDL] Collection Author: {var.author}")
    qDebug(f"[NXMColDL] Collection Summary: {var.summary}")
    qDebug(f"[NXMColDL] Collection Thumbnail: {var.thumbnail}")
    return True


def populateCollectionMods(mods):
    var.essentialMods.clear()
    var.optionalMods.clear()
    var.chosenOptional.clear()
    var.externalMods.clear()
    var.bundledMods.clear()

    for mod in mods.get("collectionRevision", {}).get("modFiles", []):
        mod_info = mod.get("file", {}).get("mod", {})
        mod_domain = mod_info.get("game", {}).get("domainName")
        if mod_domain and mod_domain != var.game:
            mod_id = mod_info.get("modId")
            var.externalMods.append(
                {
                    "id": mod_id,
                    "name": mod_info.get("name", "External Nexus resource"),
                    "resourceType": f"Nexus {mod_domain}",
                    "resourceUrl": f"https://www.nexusmods.com/{mod_domain}/mods/{mod_id}",
                }
            )
            qDebug(
                "[NXMColDL] Cross-domain mod added as external resource: "
                f"{mod_info.get('name')} ({mod_domain})"
            )
            continue

        if not mod.get("optional"):
            var.essentialMods.append(mod)
            qDebug(f"[NXMColDL] Essential mod added: {mod['file']['mod']['name']}")
        else:
            var.optionalMods.append(mod)
            qDebug(f"[NXMColDL] Optional mod added: {mod['file']['mod']['name']}")

    for mod in mods.get("collectionRevision", {}).get("externalResources", []):
        if mod.get("resourceUrl"):
            var.externalMods.append(mod)
            qDebug(f"[NXMColDL] External resource added: {mod.get('name')}")
        else:
            var.bundledMods.append(mod)
            qDebug(f"[NXMColDL] Bundled resource added: {mod.get('name')}")


class ModInfoWorker(QObject):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, uri):
        super().__init__()
        self.uri = uri

    def run(self):
        try:
            mods = fetchModInfo(self.uri)
            if mods is None:
                self.error.emit("Failed to fetch mod info")
            else:
                self.finished.emit(mods)
        except Exception as e:
            qDebug(f"[NXMColDL] Error fetching mod info: {str(e)}")
            self.error.emit(str(e))


class stepURL(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        qDebug("[NXMColDL] Initializing stepURL dialog")
        self.setWindowTitle("NXM Collection Downloader - Enter URL")
        self.setMinimumWidth(400)

        layout = QVBoxLayout()

        self.label = QLabel("Enter Nexus Collection URL:")
        layout.addWidget(self.label)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText(
            "https://nexusmods.com/games/.../collections/.../"
        )
        layout.addWidget(self.url_input)

        self.submit_btn = QPushButton("Submit")
        self.submit_btn.clicked.connect(self.submit)
        layout.addWidget(self.submit_btn)

        self.setLayout(layout)

    def get_url(self):
        input_url = self.url_input.text().strip()
        qDebug(f"[NXMColDL] URL entered: {input_url}")
        return applyCollectionAddress(input_url)

    def check_valid(self, url):
        valid = parseCollectionAddress(url)
        if valid:
            qDebug("[NXMColDL] URL is valid")
        return valid

    def submit(self):
        matched = self.get_url()
        if not matched:
            qDebug("[NXMColDL] stepURL: URL validation failed")
            QMessageBox.critical(
                self,
                "Error",
                "The URL you entered is not a valid Nexus Collection URL.",
            )
            return
        self.close()
        if var.revision:
            stepModCount(self.parent()).exec()
        else:
            stepVersion(self.parent()).exec()


class stepVersion(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        qDebug("[NXMColDL] Initializing stepVersion dialog")
        self.setWindowTitle("NXM Collection Downloader - Select Revision")
        self.setMinimumWidth(300)
        self.network_manager = None

        layout = QVBoxLayout()

        qDebug("[NXMColDL] Fetching collection info...")
        populateCollectionInfo()

        infoBox = QHBoxLayout()

        self.thumb_label = QLabel()
        self.thumb_label.setMaximumHeight(128)
        self.thumb_label.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self.thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if var.thumbnail:
            self.network_manager = var.loadThumbnail(
                var.thumbnail, self.thumb_label, self.network_manager
            )
            infoBox.addWidget(self.thumb_label)

        self.info = QLabel(f"""
							<h2 style="margin:0;padding:0">{var.name}</h2>
							<br>
							by <i>{var.author}</i>
							<br>
							<br>
							{var.summary}
							""")
        self.info.setWordWrap(True)
        infoBox.addWidget(self.info)

        layout.addLayout(infoBox)

        layout.addSpacing(10)

        self.label = QLabel("Select Revision:")
        layout.addWidget(self.label)

        self.dropdown = QComboBox()
        self.getList()
        layout.addWidget(self.dropdown)

        self.submit_btn = QPushButton("Submit")
        self.submit_btn.clicked.connect(self.submit)
        layout.addWidget(self.submit_btn)

        self.setLayout(layout)

    def getList(self):
        qDebug("[NXMColDL] stepVersion: Fetching revisions list")
        revisions = fetchRevisions(var.uri)
        if revisions:
            revision_list = revisions.get("collection", {}).get("revisions", [])
            qDebug(
                f"[NXMColDL] stepVersion: Adding {len(revision_list)} revisions to dropdown"
            )
            for data in revision_list:
                created = (
                    data.get("createdAt", "").split("T")[0]
                    if data.get("createdAt")
                    else ""
                )
                revision_num = data.get("revisionNumber", "?")
                self.dropdown.addItem(f"Revision {revision_num} ({created})")
                qDebug(
                    f"[NXMColDL] stepVersion: Added revision {revision_num} created on {created}"
                )
        else:
            qDebug("[NXMColDL] stepVersion: No revisions found or fetch failed")

    def submit(self):
        revision_text = self.dropdown.currentText()
        if not revision_text:
            qDebug("[NXMColDL] No revision selected")
            return

        try:
            revision_str = revision_text.replace("Revision ", "").split(" (")[0].strip()
            if not revision_str or revision_str == "?":
                qDebug(f"[NXMColDL] Invalid revision text: {revision_text}")
                return
            var.revision = int(revision_str)
            qDebug(f"[NXMColDL] Selected Revision: {var.revision}")
            self.close()
            stepModCount(self.parent()).exec()
        except (ValueError, IndexError) as e:
            qDebug(f"[NXMColDL] Failed to parse revision from '{revision_text}': {e}")
            return


class stepModCount(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        qDebug("[NXMColDL] Initializing stepModCount dialog")
        self.setWindowTitle("NXM Collection Downloader - Mod Count")
        self.setMinimumWidth(300)

        layout = QVBoxLayout()
        label = QLabel("This collection contains the following:")
        layout.addWidget(label)

        self.essentialLabel = QLabel("Loading essential mods...")
        self.optionalLabel = QLabel("Loading optional mods...")
        self.externalLabel = QLabel("Loading external resources...")
        self.bundledLabel = QLabel("Loading bundled resources...")

        layout.addWidget(self.essentialLabel)
        layout.addWidget(self.optionalLabel)
        layout.addWidget(self.externalLabel)
        layout.addWidget(self.bundledLabel)

        self.submit_btn = QPushButton("Next")
        self.submit_btn.setEnabled(False)  # disabled until data is loaded
        self.submit_btn.clicked.connect(self.submit)
        layout.addWidget(self.submit_btn)

        self.setLayout(layout)

        self.getMods()

    def getMods(self):
        # background process for loading modlist
        self._thread = QThread(self)
        self._worker = ModInfoWorker(var.uri)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_mods_fetched)
        self._worker.error.connect(self._on_mods_error)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()
        qDebug("[NXMColDL] stepModCount: Worker thread started")

    def _on_mods_error(self, err):
        qDebug(f"[NXMColDL] Error fetching mods: {err}")
        QMessageBox.critical(self, "Error", f"Failed to load mod information: {err}")
        self.essentialLabel.setText("Error loading essential mods")
        self.optionalLabel.setText("Error loading optional mods")
        self.externalLabel.setText("Error loading external resources")
        self.bundledLabel.setText("Error loading bundled resources")

    def _on_mods_fetched(self, mods):
        qDebug("[NXMColDL] stepModCount: Processing fetched mod data")
        qDebug(f"[NXMColDL] Mods Info: {var.cleanJson(mods)}")
        populateCollectionMods(mods)

        essentialCount = len(var.essentialMods)
        optionalCount = len(var.optionalMods)
        externalCount = len(var.externalMods)
        bundledCount = len(var.bundledMods)

        qDebug(
            f"[NXMColDL] stepModCount: Totals - Essential: {essentialCount}, Optional: {optionalCount}, External: {externalCount}, Bundled: {bundledCount}"
        )

        self.essentialLabel.setText(f"{essentialCount} essential mods")
        self.optionalLabel.setText(f"{optionalCount} optional mods")
        self.externalLabel.setText(f"{externalCount} external resources")
        self.bundledLabel.setText(f"{bundledCount} bundled resources")

        self.submit_btn.setEnabled(True)

    def submit(self):
        qDebug(
            "[NXMColDL] stepModCount: Proceeding to next dialog based on available mod types"
        )
        self.close()
        if var.essentialMods:
            qDebug("[NXMColDL] stepModCount: Opening stepEssential")
            stepEssential(self.parent()).exec()
        elif var.optionalMods:
            qDebug("[NXMColDL] stepModCount: Opening stepOptional")
            stepOptional(self.parent()).exec()
        elif var.externalMods:
            qDebug("[NXMColDL] stepModCount: Opening stepExternal")
            stepExternal(self.parent()).exec()
        elif var.bundledMods:
            qDebug("[NXMColDL] stepModCount: Opening stepBundled")
            stepBundled(self.parent()).exec()
        else:
            qDebug("[NXMColDL] stepModCount: No mods found, opening stepSummary")
            stepSummary(self.parent()).exec()


class stepEssential(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("NXM Collection Downloader - Essential Mods")
        self.setMinimumWidth(300)

        layout = QVBoxLayout()
        label = QLabel("Included 'Essential' mods:")
        layout.addWidget(label)

        self.modlist = QListWidget()
        self.modlist.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.modlist.setAlternatingRowColors(True)
        for mod in var.essentialMods:
            item_text = f"Mod: {mod['file']['mod']['name']}\nFile: {mod['file']['name']} - {mod['file']['version']}\nby {mod['file']['mod']['author']}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, mod)
            self.modlist.addItem(item)
        self.modlist.setMinimumHeight(200)
        layout.addWidget(self.modlist)

        self.submit_btn = QPushButton("Next")
        self.submit_btn.clicked.connect(self.submit)
        layout.addWidget(self.submit_btn)

        self.setLayout(layout)

    def submit(self):
        self.close()
        if var.optionalMods:
            stepOptional(self.parent()).exec()
        elif var.externalMods:
            stepExternal(self.parent()).exec()
        elif var.bundledMods:
            stepBundled(self.parent()).exec()
        else:
            stepSummary(self.parent()).exec()


class stepOptional(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("NXM Collection Downloader - Optional Mods")
        self.setMinimumWidth(300)

        layout = QVBoxLayout()
        label = QLabel("Select 'Optional' mods:")
        layout.addWidget(label)

        self.modlist = QListWidget()
        self.modlist.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.modlist.setAlternatingRowColors(True)
        for mod in var.optionalMods:
            item_text = f"Mod: {mod['file']['mod']['name']}\nFile: {mod['file']['name']} - {mod['file']['version']}\nby {mod['file']['mod']['author']}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, mod)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            item.setSizeHint(
                QSize(0, QFontMetrics(self.modlist.font()).lineSpacing() * 3 + 8)
            )
            self.modlist.addItem(item)
        self.modlist.setMinimumHeight(200)
        layout.addWidget(self.modlist)

        self.submit_btn = QPushButton("Next")
        self.submit_btn.clicked.connect(self.submit)
        layout.addWidget(self.submit_btn)

        self.setLayout(layout)

    def submit(self):
        var.chosenOptional = []
        for i in range(self.modlist.count()):
            item = self.modlist.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                mod_data = item.data(Qt.ItemDataRole.UserRole)
                var.chosenOptional.append(mod_data)
                qDebug(
                    f"[NXMColDL] Optional mod selected: {mod_data['file']['mod']['name']}"
                )

        qDebug(f"[NXMColDL] Total optional mods selected: {len(var.chosenOptional)}")

        self.close()
        if var.externalMods:
            stepExternal(self.parent()).exec()
        elif var.bundledMods:
            stepBundled(self.parent()).exec()
        else:
            stepSummary(self.parent()).exec()


class stepExternal(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("NXM Collection Downloader - External Mods")
        self.setMinimumWidth(300)

        layout = QVBoxLayout()
        label = QLabel("Included 'External' mods:")
        layout.addWidget(label)

        self.modlist = QListWidget()
        self.modlist.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.modlist.setAlternatingRowColors(True)
        for mod in var.externalMods:
            item = QListWidgetItem(f"{mod['name']}")
            item.setData(Qt.ItemDataRole.UserRole, mod)
            self.modlist.addItem(item)
        self.modlist.setMinimumHeight(200)
        layout.addWidget(self.modlist)

        plugin_instance = getattr(__meta__, "_download_plugin", None)
        if plugin_instance and plugin_instance._organizer:
            var.openModWebsites = plugin_instance._organizer.pluginSetting(
                plugin_instance.name(), "modpage_browser_default"
            )

        self.urlCheck = QCheckBox("Open URLs in Browser")
        self.urlCheck.setChecked(var.chosenExternal)
        self.urlCheck.stateChanged.connect(
            lambda s: setattr(var, "chosenExternal", bool(s))
        )
        layout.addWidget(self.urlCheck)

        self.submit_btn = QPushButton("Next")
        self.submit_btn.clicked.connect(self.submit)
        layout.addWidget(self.submit_btn)

        self.setLayout(layout)

    def submit(self):
        self.close()
        if not var.chosenExternal:
            var.externalMods.clear()  # clear if not chosen
        if var.bundledMods:
            stepBundled(self.parent()).exec()
        else:
            stepSummary(self.parent()).exec()


class stepBundled(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("NXM Collection Downloader - Bundled Mods Warning")
        self.setMinimumWidth(300)

        layout = QVBoxLayout()
        explanation = QLabel(
            """
Bundled assets are currently unsupported as there are no public APIs for retreiving them.
They can only be retreived with the Vortex client, and are listed here for your information.
"""
        )
        label = QLabel("The following bundled assets will NOT be installed:")
        label.setStyleSheet("color: red; font-weight: bold;")
        layout.addWidget(explanation)
        layout.addWidget(label)
        self.modlist = QListWidget()
        self.modlist.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.modlist.setAlternatingRowColors(True)
        for mod in var.bundledMods:
            item = QListWidgetItem(f"{mod['name']}")
            item.setData(Qt.ItemDataRole.UserRole, mod)
            self.modlist.addItem(item)
        self.modlist.setMinimumHeight(200)
        layout.addWidget(self.modlist)

        self.submit_btn = QPushButton("Acknowledge")
        self.submit_btn.clicked.connect(self.submit)
        layout.addWidget(self.submit_btn)

        self.setLayout(layout)

    def submit(self):
        self.close()
        stepSummary(self.parent()).exec()


class stepSummary(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("NXM Collection Downloader - Summary")
        self.setMinimumWidth(300)

        layout = QVBoxLayout()
        label = QLabel("Summary of selected mods:")
        layout.addWidget(label)

        essentialCount = len(var.essentialMods)
        optionalCount = len(var.chosenOptional)
        externalCount = len(var.externalMods)
        bundledCount = len(var.bundledMods)

        labelEssential = QLabel(f"{essentialCount} essential mods")
        labelOptional = QLabel(f"{optionalCount} optional mods")
        labelExternal = QLabel(f"{externalCount} external resources")
        labelBundled = QLabel(f"{bundledCount} bundled resources")

        layout.addWidget(labelEssential)
        layout.addWidget(labelOptional)
        layout.addWidget(labelExternal)
        layout.addWidget(labelBundled)

        plugin_instance = getattr(__meta__, "_download_plugin", None)
        if plugin_instance and plugin_instance._organizer:
            var.openModWebsites = plugin_instance._organizer.pluginSetting(
                plugin_instance.name(), "modpage_browser_default"
            )

        self.urlCheck = QCheckBox(
            "Open Mod Websites in Browser (Required for non-Premium users)"
        )
        self.urlCheck.setChecked(var.openModWebsites)
        self.urlCheck.stateChanged.connect(
            lambda s: setattr(var, "openModWebsites", bool(s))
        )
        layout.addWidget(self.urlCheck)

        self.submit_btn = QPushButton("Finish")
        self.submit_btn.clicked.connect(self.submit)
        layout.addWidget(self.submit_btn)

        self.setLayout(layout)

    def submit(self):
        self.close()
        stepDownload(self.parent()).exec()


class stepDownloadProgress(QDialog):
    """Progress dialog that tracks download completion"""

    def __init__(
        self,
        parent=None,
        mods_to_download=None,
        on_complete=None,
        max_retries=2,
        retry_delay_ms=2500,
        stale_unfinished_seconds=60,
        close_on_success=False,
        success_close_delay_ms=0,
    ):
        super().__init__(parent)
        self.setWindowTitle("NXM Collection Downloader - Download Progress")
        self.setMinimumWidth(350)

        self.mods_to_download = mods_to_download or []
        self.total_mods = len(self.mods_to_download)
        self.on_complete = on_complete
        self.max_retries = max(0, int(max_retries or 0))
        self.retry_delay_ms = retry_delay_ms
        self.stale_unfinished_seconds = max(0, int(stale_unfinished_seconds or 0))
        self.close_on_success = close_on_success
        self.success_close_delay_ms = max(0, int(success_close_delay_ms or 0))
        self.completed_count = 0
        self.failed_count = 0
        self.retry_count = 0
        self.prequeue_cleanup_count = 0
        self.is_tracking = True
        self.download_ids = {}
        self.completed_keys = set()
        self.failed_keys = set()
        self.retry_attempts = {}
        self.key_counts = {}
        self.queued_keys = set()
        self.reconcile_timer = QTimer(self)
        self.reconcile_timer.setInterval(1000)
        self.reconcile_timer.timeout.connect(self.reconcile_completed_downloads)
        for mod in self.mods_to_download:
            key = self.mod_key(mod)
            self.key_counts[key] = self.key_counts.get(key, 0) + 1
        self.already_downloaded_keys = downloadedFileKeys(downloadDirectory())

        layout = QVBoxLayout()

        self.label = QLabel(f"Downloading mods: 0/{self.total_mods} completed")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label)

        self.progress = QProgressBar()
        self.progress.setMinimum(0)
        self.progress.setMaximum(self.total_mods)
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        self.detail_label = QLabel("Downloads have been queued...")
        self.detail_label.setWordWrap(True)
        self.detail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.detail_label)

        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        layout.addWidget(self.close_btn)

        self.setLayout(layout)

        # Register callbacks with download manager
        plugin_instance = getattr(__meta__, "_download_plugin", None)
        if plugin_instance and hasattr(plugin_instance, "_organizer"):
            self.download_manager = plugin_instance._organizer.downloadManager()
            self.download_manager.onDownloadComplete(self.on_download_complete)
            self.download_manager.onDownloadFailed(self.on_download_failed)
            self.download_manager.onDownloadPaused(self.on_download_paused)
            self.download_manager.onDownloadRemoved(self.on_download_removed)
        else:
            self.download_manager = None

        QTimer.singleShot(0, self.queue_downloads)
        self.reconcile_timer.start()

    def mod_key(self, mod):
        return (int(mod["file"]["mod"]["modId"]), int(mod["file"]["fileId"]))

    def mod_label(self, mod):
        return mod["file"]["mod"].get("name") or mod["file"].get("name") or "mod"

    def queue_downloads(self):
        plugin_instance = getattr(__meta__, "_download_plugin", None)
        if not plugin_instance or not getattr(plugin_instance, "_organizer", None):
            self.detail_label.setText(
                "Failed to access Mod Organizer download manager."
            )
            self.detail_label.setStyleSheet("color: red;")
            self.is_tracking = False
            return

        skipped = 0
        for mod in self.mods_to_download:
            key = self.mod_key(mod)
            if key in self.completed_keys or key in self.queued_keys:
                continue
            if key in self.already_downloaded_keys:
                self.completed_keys.add(key)
                skipped += self.key_counts.get(key, 1)
                continue
            self.cleanup_stale_unfinished_before_queue(key)
            self.queued_keys.add(key)
            self.queue_mod(mod)

        if skipped:
            self.completed_count = skipped
            qDebug(
                f"[NXMColDL Progress] Skipped {skipped} already-downloaded archive(s)"
            )
            self.update_progress()

        if self.total_mods == 0:
            self.finish_if_complete()
        elif self.completed_count >= self.total_mods:
            self.finish_if_complete()

    def cleanup_stale_unfinished_before_queue(self, key):
        """Remove empty leftovers before MO2 sees a duplicate file."""
        entries = unfinishedDownloadEntries(downloadDirectory()).get(key)
        cleanup_entries = zeroByteUnfinishedEntries(entries)
        if not cleanup_entries:
            return

        for entry in cleanup_entries:
            for path_key in ("archive", "metadata"):
                try:
                    entry[path_key].unlink(missing_ok=True)
                except OSError as exc:
                    qDebug(
                        "[NXMColDL Progress] Failed removing stale unfinished "
                        f"{path_key} for ModID {key[0]}, FileID {key[1]}: {exc}"
                    )

        self.prequeue_cleanup_count += 1
        qDebug(
            "[NXMColDL Progress] Removed zero-byte unfinished download "
            f"before queueing ModID {key[0]}, FileID {key[1]}"
        )

    def queue_mod(self, mod):
        plugin_instance = getattr(__meta__, "_download_plugin", None)
        key = self.mod_key(mod)
        mod_id, file_id = key
        mod_name = self.mod_label(mod)
        qDebug(
            "[NXMColDL] Queueing download - "
            f"ModID: {mod_id}, FileID: {file_id}, Name: {mod_name}"
        )
        download_id = plugin_instance.downloadMod(mod)
        self.download_ids[int(download_id)] = key
        qDebug(
            "[NXMColDL Progress] Tracking download "
            f"ID {download_id} for ModID {mod_id}, FileID {file_id}"
        )

    def requeue_mod(self, mod, key):
        """Requeue a download after clearing empty placeholders for the same file."""
        if not self.is_tracking:
            return
        if key in self.completed_keys or key in self.failed_keys:
            return

        self.cleanup_stale_unfinished_before_queue(key)
        self.queued_keys.add(key)
        self.queue_mod(mod)

    def mod_by_key(self, key):
        for mod in self.mods_to_download:
            if self.mod_key(mod) == key:
                return mod
        return None

    def on_download_complete(self, download_id):
        """Called when a download completes successfully"""
        if not self.is_tracking:
            return

        key = self.download_ids.pop(int(download_id), None)
        if key is None or key in self.completed_keys:
            return

        qDebug(f"[NXMColDL Progress] Download completed: ID {download_id}")
        self.completed_keys.add(key)
        self.completed_count += self.key_counts.get(key, 1)
        self.update_progress()
        self.finish_if_complete()

    def on_download_failed(self, download_id):
        """Called when a download fails"""
        if not self.is_tracking:
            return

        key = self.download_ids.pop(int(download_id), None)
        if key is None or key in self.completed_keys or key in self.failed_keys:
            return

        qDebug(f"[NXMColDL Progress] Download failed: ID {download_id}")
        attempts = self.retry_attempts.get(key, 0)
        if attempts < self.max_retries:
            self.retry_attempts[key] = attempts + 1
            self.retry_count += 1
            self.queued_keys.discard(key)
            mod = self.mod_by_key(key)
            mod_name = self.mod_label(mod) if mod else f"ModID {key[0]}"
            self.detail_label.setText(
                f"Retrying {mod_name} ({attempts + 1}/{self.max_retries})..."
            )
            self.detail_label.setStyleSheet("color: orange;")
            qDebug(
                "[NXMColDL Progress] Requeueing failed download "
                f"ModID {key[0]}, FileID {key[1]} "
                f"({attempts + 1}/{self.max_retries})"
            )
            if mod:
                QTimer.singleShot(
                    self.retry_delay_ms,
                    lambda m=mod, k=key: self.requeue_mod(m, k),
                )
            return

        self.failed_keys.add(key)
        self.failed_count += 1
        self.completed_count += self.key_counts.get(key, 1)
        self.update_progress()
        self.finish_if_complete()

    def on_download_paused(self, download_id):
        if not self.is_tracking or int(download_id) not in self.download_ids:
            return
        qDebug(f"[NXMColDL Progress] Download paused: ID {download_id}")
        self.detail_label.setText("A tracked download is paused in MO2.")
        self.detail_label.setStyleSheet("color: orange;")

    def on_download_removed(self, download_id):
        if not self.is_tracking:
            return

        key = self.download_ids.pop(int(download_id), None)
        if key is None or key in self.completed_keys or key in self.failed_keys:
            return

        qDebug(f"[NXMColDL Progress] Download removed: ID {download_id}")
        self.failed_keys.add(key)
        self.failed_count += 1
        self.completed_count += self.key_counts.get(key, 1)
        self.update_progress()
        self.finish_if_complete()

    def reconcile_completed_downloads(self):
        """Credit downloads that MO2 completed without emitting a tracked callback."""
        if not self.is_tracking:
            self.reconcile_timer.stop()
            return

        completed_on_disk = downloadedFileKeys(downloadDirectory())
        newly_completed = (
            completed_on_disk
            & set(self.key_counts) - self.completed_keys - self.failed_keys
        )
        for key in newly_completed:
            download_ids = [
                download_id
                for download_id, download_key in self.download_ids.items()
                if download_key == key
            ]
            for download_id in download_ids:
                self.download_ids.pop(download_id, None)

            self.completed_keys.add(key)
            self.completed_count += self.key_counts.get(key, 1)
            qDebug(
                "[NXMColDL Progress] Reconciled completed download from disk: "
                f"ModID {key[0]}, FileID {key[1]}"
            )

        if newly_completed:
            self.update_progress()
            self.finish_if_complete()

        if self.is_tracking:
            self.retry_stale_unfinished_downloads()

    def retry_stale_unfinished_downloads(self):
        """Requeue zero-byte unfinished files that MO2 left idle without a callback."""
        if not self.stale_unfinished_seconds:
            return

        downloads_dir = downloadDirectory()
        pending_keys = set(self.key_counts) - self.completed_keys - self.failed_keys
        entries_by_key = unfinishedDownloadEntries(downloads_dir)
        now = time.time()

        for key in pending_keys:
            entries = entries_by_key.get(key)
            stale_entries = staleZeroByteUnfinishedEntries(
                entries, now, self.stale_unfinished_seconds
            )
            if not stale_entries:
                continue

            attempts = self.retry_attempts.get(key, 0)
            if attempts >= self.max_retries:
                self.failed_keys.add(key)
                self.failed_count += 1
                self.completed_count += self.key_counts.get(key, 1)
                qDebug(
                    "[NXMColDL Progress] Zero-byte unfinished download exhausted retries: "
                    f"ModID {key[0]}, FileID {key[1]}"
                )
                continue

            mod = self.mod_by_key(key)
            if not mod:
                continue

            self.retry_attempts[key] = attempts + 1
            self.retry_count += 1
            self.queued_keys.discard(key)
            download_ids = [
                download_id
                for download_id, download_key in self.download_ids.items()
                if download_key == key
            ]
            for download_id in download_ids:
                self.download_ids.pop(download_id, None)

            for entry in stale_entries:
                for path_key in ("archive", "metadata"):
                    try:
                        entry[path_key].unlink(missing_ok=True)
                    except OSError as exc:
                        qDebug(
                            "[NXMColDL Progress] Failed removing stale unfinished "
                            f"{path_key} for ModID {key[0]}, FileID {key[1]}: {exc}"
                        )

            mod_name = self.mod_label(mod)
            self.detail_label.setText(
                f"Retrying stalled {mod_name} ({attempts + 1}/{self.max_retries})..."
            )
            self.detail_label.setStyleSheet("color: orange;")
            qDebug(
                "[NXMColDL Progress] Requeueing stale zero-byte unfinished download "
                f"ModID {key[0]}, FileID {key[1]} "
                f"({attempts + 1}/{self.max_retries})"
            )
            QTimer.singleShot(
                self.retry_delay_ms,
                lambda m=mod, k=key: self.requeue_mod(m, k),
            )

        self.update_progress()
        self.finish_if_complete()

    def finish_if_complete(self):
        if self.completed_count < self.total_mods:
            return

        qDebug(
            f"[NXMColDL Progress] Download tracking complete. {self.failed_count} failed."
        )
        self.is_tracking = False
        self.reconcile_timer.stop()
        if self.failed_count == 0 and self.on_complete:
            if self.close_on_success:
                self.accept()
            QTimer.singleShot(0, self.on_complete)
        elif self.failed_count == 0 and self.success_close_delay_ms:
            QTimer.singleShot(self.success_close_delay_ms, self.accept)

    def update_progress(self):
        """Update the progress display"""
        self.progress.setValue(self.completed_count)
        self.label.setText(
            f"Downloading mods: {self.completed_count}/{self.total_mods} completed"
        )

        if self.failed_count > 0:
            self.detail_label.setText(
                f"{self.failed_count} download(s) failed. Check the Downloads tab for details."
            )
            self.detail_label.setStyleSheet("color: orange;")
        elif self.completed_count >= self.total_mods:
            if self.retry_count:
                self.detail_label.setText(
                    f"All downloads completed after {self.retry_count} retry attempt(s)!"
                )
            else:
                self.detail_label.setText("All downloads completed!")
            self.detail_label.setStyleSheet("color: green;")
        else:
            self.detail_label.setText(
                f"Downloading... {self.total_mods - self.completed_count} remaining"
            )
            self.detail_label.setStyleSheet("")


class stepDownload(QDialog):
    def __init__(self, parent=None, on_complete=None):
        super().__init__(parent)
        self.setWindowTitle("NXM Collection Downloader - Downloading...")
        self.setMinimumWidth(150)
        self.on_complete = on_complete

        self.layout = QVBoxLayout()
        self.label = QLabel("Preparing to download selected mods...")

        self.mod_urls_to_open = []
        self.current_batch = 0
        self.batch_btn = None
        self.progress_dialog = None

        plugin_instance = getattr(__meta__, "_download_plugin", None)
        if plugin_instance is not None:
            try:
                base_path = Path(plugin_instance._organizer.basePath())
                metadata_file = var.saveCollectionMetadata(base_path)
                qDebug(f"[NXMColDL] Collection metadata saved to: {metadata_file}")
            except (ValueError, IOError) as e:
                qDebug(f"[NXMColDL] Failed to save collection metadata: {e}")
                QMessageBox.warning(
                    self,
                    "Warning",
                    f"Failed to save collection metadata:\n\n{e}\n\n"
                    "You will not be able to install this collection automatically later.",
                )

            # Always open external resources if user chose to
            if var.chosenExternal and var.externalMods:
                for mod in var.externalMods:
                    QDesktopServices.openUrl(QUrl(mod["resourceUrl"]))

            if var.openModWebsites:
                # User chose to open websites instead of downloading
                qDebug(
                    "[NXMColDL] stepDownload: Opening mod websites mode (user is non-Premium or chose this option)"
                )
                for mod in var.essentialMods + var.chosenOptional:
                    mod_id = mod["file"]["mod"]["modId"]
                    mod_url = f"https://www.nexusmods.com/{var.game}/mods/{mod_id}"
                    self.mod_urls_to_open.append((mod["file"]["mod"]["name"], mod_url))
                self.label.setText(
                    f"Ready to open {len(self.mod_urls_to_open)} mod website(s) in batches."
                )
            else:
                # Queue downloads and show progress tracker
                qDebug(
                    "[NXMColDL] stepDownload: Queueing downloads via MO2 download manager"
                )
                mods_to_download = var.essentialMods + var.chosenOptional
                qDebug(f"[NXMColDL] Queueing {len(mods_to_download)} downloads")
                max_retries = int(
                    plugin_instance._organizer.pluginSetting(
                        plugin_instance.name(), "download_retry_count"
                    )
                    or 0
                )
                success_close_delay_ms = 1000 * int(
                    plugin_instance._organizer.pluginSetting(
                        plugin_instance.name(), "download_success_close_delay_seconds"
                    )
                    or 0
                )
                stale_unfinished_seconds = int(
                    plugin_instance._organizer.pluginSetting(
                        plugin_instance.name(), "stale_unfinished_retry_seconds"
                    )
                    or 0
                )
                self.progress_dialog = stepDownloadProgress(
                    self.parent(),
                    mods_to_download,
                    on_complete=self.on_complete,
                    max_retries=max_retries,
                    stale_unfinished_seconds=stale_unfinished_seconds,
                    success_close_delay_ms=success_close_delay_ms,
                )

                self.label.setText(f"Queued {len(mods_to_download)} downloads in MO2.")
        else:
            qDebug(
                "[NXMColDL] downloadMod called without active plugin instance; Aborting"
            )
            self.close()
            return

        self.layout.addWidget(self.label)

        # Add button for opening mod websites in batches if needed
        if self.mod_urls_to_open:
            self.batch_btn = QPushButton()
            self.batch_btn.clicked.connect(self.open_next_batch)
            self.layout.addWidget(self.batch_btn)
            self.update_batch_button()

        self.submit_btn = QPushButton("Finish")
        self.submit_btn.clicked.connect(self.submit)
        self.layout.addWidget(self.submit_btn)
        self.setLayout(self.layout)

        if self.progress_dialog is not None:
            QTimer.singleShot(0, self.show_progress_dialog)

    def show_progress_dialog(self):
        """Run the progress dialog after this step's modal event loop starts."""
        self.hide()
        self.progress_dialog.exec()
        self.accept()

    def update_batch_button(self):
        plugin_instance = getattr(__meta__, "_download_plugin", None)
        if plugin_instance and hasattr(plugin_instance, "_organizer"):
            batch_size = int(
                plugin_instance._organizer.pluginSetting(
                    plugin_instance.name(), "modpage_batch_size"
                )
                or 5
            )
        else:
            batch_size = 5
        remaining = len(self.mod_urls_to_open) - (self.current_batch * batch_size)
        if remaining > 0:
            next_batch_count = min(batch_size, remaining)
            self.batch_btn.setText(
                f"Open Next {next_batch_count} Mod Website(s) ({remaining} remaining)"
            )
            self.batch_btn.setEnabled(True)
        else:
            self.batch_btn.setText("All mod websites opened")
            self.batch_btn.setEnabled(False)

    def open_next_batch(self):
        plugin_instance = getattr(__meta__, "_download_plugin", None)
        if plugin_instance and hasattr(plugin_instance, "_organizer"):
            batch_size = int(
                plugin_instance._organizer.pluginSetting(
                    plugin_instance.name(), "modpage_batch_size"
                )
                or 5
            )
        else:
            batch_size = 5
        start_idx = self.current_batch * batch_size
        end_idx = min(start_idx + batch_size, len(self.mod_urls_to_open))

        if start_idx >= len(self.mod_urls_to_open):
            return  # All done

        for i in range(start_idx, end_idx):
            mod_name, mod_url = self.mod_urls_to_open[i]
            QDesktopServices.openUrl(QUrl(mod_url))
            qDebug(f"[NXMColDL] Opening mod website: {mod_url}")

        self.current_batch += 1
        self.update_batch_button()

    def submit(self):
        self.close()


class stepCollectionLinkFlow(QDialog):
    """Fetch, download, and optionally install a collection from a direct link."""

    def __init__(self, collection_url, parent=None, auto_install=True):
        super().__init__(parent)
        self.collection_url = collection_url
        self.auto_install = auto_install
        self.metadata = None
        self.setWindowTitle("NXM Collection Downloader")
        self.setMinimumWidth(420)

        layout = QVBoxLayout()
        self.label = QLabel("Preparing collection download...")
        self.label.setWordWrap(True)
        layout.addWidget(self.label)

        self.setLayout(layout)
        QTimer.singleShot(0, self.start)

    def fail(self, message):
        qDebug(f"[NXMColDL] Direct collection flow failed: {message}")
        QMessageBox.critical(self, "Collection Download Failed", message)
        self.reject()

    def start(self):
        if not applyCollectionAddress(self.collection_url):
            self.fail("The Nexus collection link was not recognized.")
            return

        if not populateCollectionInfo():
            self.fail("Failed to fetch collection information from Nexus Mods.")
            return

        if var.revision is None:
            var.revision = selectLatestRevision()
            if var.revision is None:
                self.fail("Failed to determine the latest collection revision.")
                return

        self.label.setText(f"Fetching collection manifest for {var.name}...")
        mods = fetchModInfo(var.uri)
        if mods is None:
            self.fail("Failed to fetch collection mod information from Nexus Mods.")
            return

        populateCollectionMods(mods)
        var.chosenOptional = list(var.optionalMods)

        plugin_instance = getattr(__meta__, "_download_plugin", None)
        if not plugin_instance or not getattr(plugin_instance, "_organizer", None):
            self.fail("Failed to access Mod Organizer.")
            return

        try:
            base_path = Path(plugin_instance._organizer.basePath())
            metadata_file = var.saveCollectionMetadata(base_path)
            self.metadata = var.loadCollectionMetadata(
                base_path, var.game, var.collection, var.revision
            )
            qDebug(f"[NXMColDL] Collection metadata saved to: {metadata_file}")
        except (ValueError, IOError) as e:
            self.fail(f"Failed to save collection metadata:\n\n{e}")
            return

        if var.chosenExternal and var.externalMods:
            for mod in var.externalMods:
                QDesktopServices.openUrl(QUrl(mod["resourceUrl"]))

        if var.bundledMods:
            qDebug(
                "[NXMColDL] Direct collection flow found unsupported bundled "
                f"resources: {len(var.bundledMods)}"
            )

        mods_to_download = var.essentialMods + var.chosenOptional
        max_retries = int(
            plugin_instance._organizer.pluginSetting(
                plugin_instance.name(), "download_retry_count"
            )
            or 0
        )
        success_close_delay_ms = 1000 * int(
            plugin_instance._organizer.pluginSetting(
                plugin_instance.name(), "download_success_close_delay_seconds"
            )
            or 0
        )
        stale_unfinished_seconds = int(
            plugin_instance._organizer.pluginSetting(
                plugin_instance.name(), "stale_unfinished_retry_seconds"
            )
            or 0
        )
        self.progress_dialog = stepDownloadProgress(
            self.parent(),
            mods_to_download,
            on_complete=self.install_after_download if self.auto_install else None,
            max_retries=max_retries,
            stale_unfinished_seconds=stale_unfinished_seconds,
            close_on_success=self.auto_install,
            success_close_delay_ms=success_close_delay_ms,
        )
        self.hide()
        self.progress_dialog.exec()
        self.accept()

    def install_after_download(self):
        if not self.metadata:
            return
        from .install import installCollectionMetadata

        installCollectionMetadata(self.metadata, self.parent())
