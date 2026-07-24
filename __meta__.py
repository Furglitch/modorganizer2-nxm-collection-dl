import mobase  # type: ignore
from PyQt6.QtCore import QTimer, QUrl, qDebug
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QMainWindow
from .collection_helpers import parseCollectionAddress
from .download import stepCollectionLinkFlow, stepURL
from .install import stepSelectCollection
from pathlib import Path

PLUGIN_VERSION = mobase.VersionInfo(1, 0, 0, mobase.ReleaseType.ALPHA)
_active_collection_link_flow = None


def icon(icon_name: str) -> QIcon:
    return QIcon(str(Path(__file__).parent / "icons" / icon_name))


def pendingLinkFiles(organizer: mobase.IOrganizer):
    """Return rendezvous paths for external nxm:// collection handlers.

    The MO2 data directory is the preferred path. The plugin directory is a
    fallback because it maps cleanly as both /home/... on Linux and Z:/home/...
    inside Wine/Proton.
    """
    return [
        Path(organizer.basePath()) / "collections" / "pending-nxm-link.txt",
        Path(__file__).parent / "pending-nxm-link.txt",
    ]


def consumePendingCollectionLink(organizer: mobase.IOrganizer, parent):
    global _active_collection_link_flow
    if _active_collection_link_flow and _active_collection_link_flow.isVisible():
        return

    url = None
    for pending_file in pendingLinkFiles(organizer):
        try:
            if not pending_file.exists():
                continue
            url = pending_file.read_text(encoding="utf-8").strip()
            pending_file.unlink()
            break
        except OSError as e:
            qDebug(f"[NXMColDL] Failed to consume pending collection link: {e}")
            return

    if not url:
        return

    if not parseCollectionAddress(url):
        qDebug(f"[NXMColDL] Ignoring invalid pending collection link: {url}")
        return

    qDebug(f"[NXMColDL] Consuming pending collection link: {url}")
    _active_collection_link_flow = stepCollectionLinkFlow(
        url,
        parent,
        auto_install=organizer.pluginSetting(
            "NXM Collection Link Handler", "auto_install_after_download"
        ),
    )
    _active_collection_link_flow.exec()
    _active_collection_link_flow = None


def startPendingLinkWatcher(plugin):
    if getattr(plugin, "_pending_link_timer", None):
        return

    plugin._pending_link_timer = QTimer()
    plugin._pending_link_timer.timeout.connect(
        lambda: consumePendingCollectionLink(plugin._organizer, plugin._parent)
    )
    plugin._pending_link_timer.start(1000)
    paths = ", ".join(str(path) for path in pendingLinkFiles(plugin._organizer))
    qDebug(f"[NXMColDL] Watching for collection links at {paths}")


class DownloadCollectionTool(mobase.IPluginTool):
    _organizer: mobase.IOrganizer

    def __init__(self):
        super().__init__()
        self._organizer = None
        self._parent = None
        self._pending_link_timer = None

    def init(self, organizer: mobase.IOrganizer):
        self._organizer = organizer
        qDebug("[NXMColDL] Initializing Download Collection plugin")
        try:
            import sys as _sys

            _sys.modules[__name__]._download_plugin = self
        except Exception:
            pass
        self._organizer.onUserInterfaceInitialized(
            self.onUserInterfaceInitializedCallback
        )
        return True

    def name(self) -> str:
        return "NXM Collections Downloader"

    def displayName(self):
        return "NXM Collections/Download Collection"

    def author(self) -> str:
        return "Furglitch"

    def description(self) -> str:
        return "Allows downloading NXM collections directly in MO2"

    def version(self) -> mobase.VersionInfo:
        return PLUGIN_VERSION

    def isActive(self) -> bool:
        return self._organizer.pluginSetting(self.name(), "enabled")

    def icon(self):
        return icon("download.ico")

    def tooltip(self):
        return "Download a Nexus Mods collection"

    def setParentWidget(self, widget):
        self._parent = widget

    def display(self) -> None:
        dlg = getattr(self, "_stepURL", None) or stepURL()
        dlg.exec()

    def settings(self):
        return [
            mobase.PluginSetting("enabled", "Enable", True),
            mobase.PluginSetting(
                "modpage_browser_default",
                "Open mod download sites in browser by default (set True if non-Premium user)",
                False,
            ),
            mobase.PluginSetting(
                "modpage_batch_size", "Number of mod websites to open at once", 5
            ),
            mobase.PluginSetting(
                "externalmods_browser_default",
                "Open external mod URLs in browser by default",
                True,
            ),
            mobase.PluginSetting(
                "download_retry_count",
                "Retry failed collection downloads this many times",
                2,
            ),
            mobase.PluginSetting(
                "download_success_close_delay_seconds",
                "Close successful download progress dialogs after this many seconds (0 disables)",
                5,
            ),
            mobase.PluginSetting(
                "stale_unfinished_retry_seconds",
                "Retry zero-byte unfinished downloads after this many idle seconds (0 disables)",
                60,
            ),
        ]

    def onUserInterfaceInitializedCallback(self, main_window: "QMainWindow"):
        self._parent = main_window
        self._stepURL = stepURL(main_window)
        startPendingLinkWatcher(self)

    def downloadMod(self, modInfo: dict):
        modID = int(modInfo["file"]["mod"]["modId"])
        fileID = int(modInfo["file"]["fileId"])
        qDebug(f"[NXMColDL] Downloading mod {modID} file {fileID}")
        return self._organizer.downloadManager().startDownloadNexusFile(modID, fileID)


class InstallCollectionTool(mobase.IPluginTool):
    _organizer: mobase.IOrganizer

    def __init__(self):
        super().__init__()
        self._organizer = None

    def init(self, organizer: mobase.IOrganizer):
        self._organizer = organizer
        qDebug("[NXMColDL] Initializing Install Collection plugin")
        try:
            import sys

            sys.modules[__name__]._install_plugin = self
        except Exception:
            pass
        self._organizer.onUserInterfaceInitialized(
            self.onUserInterfaceInitializedCallback
        )
        return True

    def name(self) -> str:
        return "NXM Collections Installer"

    def displayName(self):
        return "NXM Collections/Install Downloaded Collection"

    def author(self) -> str:
        return "Furglitch"

    def description(self) -> str:
        return self.tooltip()

    def version(self) -> mobase.VersionInfo:
        return PLUGIN_VERSION

    def isActive(self) -> bool:
        return self._organizer.pluginSetting(self.name(), "enabled")

    def icon(self):
        return icon("install.ico")

    def tooltip(self):
        return "Installs mods from an already downloaded Nexus Mods collection"

    def setParentWidget(self, widget):
        self._parent = widget

    def display(self) -> None:
        dlg = getattr(self, "_stepSelectCollection", None) or stepSelectCollection()
        dlg.exec()

    def settings(self):
        return [
            mobase.PluginSetting("enabled", "Enable", True),
            mobase.PluginSetting(
                "auto_accept_quick_install",
                "Automatically accept MO2 Quick Install dialogs",
                True,
            ),
            mobase.PluginSetting(
                "auto_dismiss_known_post_install_errors",
                "Automatically dismiss known MO2 post-install error dialogs",
                True,
            ),
            mobase.PluginSetting(
                "auto_merge_existing_mods",
                "Automatically merge when MO2 reports that a mod already exists",
                True,
            ),
            mobase.PluginSetting(
                "install_files_as_separate_mods",
                "Install each collection file as a separate named MO2 mod",
                True,
            ),
            mobase.PluginSetting(
                "activate_mods_after_install",
                "Activate installed mods after the collection install pass completes",
                True,
            ),
        ]

    def onUserInterfaceInitializedCallback(self, main_window: "QMainWindow"):
        self._stepSelectCollection = stepSelectCollection(main_window)


class CollectionModPage(mobase.IPluginModPage):
    _organizer: mobase.IOrganizer

    def __init__(self):
        super().__init__()
        self._organizer = None
        self._parent = None

    def init(self, organizer: mobase.IOrganizer):
        self._organizer = organizer
        qDebug("[NXMColDL] Initializing Nexus collection link handler")
        self._organizer.onUserInterfaceInitialized(
            self.onUserInterfaceInitializedCallback
        )
        return True

    def name(self) -> str:
        return "NXM Collection Link Handler"

    def displayName(self):
        return "Nexus Mods Collections"

    def author(self) -> str:
        return "Furglitch"

    def description(self) -> str:
        return "Handles Nexus Mods Add Collection links"

    def version(self) -> mobase.VersionInfo:
        return PLUGIN_VERSION

    def isActive(self) -> bool:
        return self._organizer.pluginSetting(self.name(), "enabled")

    def icon(self):
        return icon("download.ico")

    def pageURL(self):
        return QUrl("https://www.nexusmods.com")

    def useIntegratedBrowser(self):
        return False

    def setParentWidget(self, widget):
        self._parent = widget

    def onUserInterfaceInitializedCallback(self, main_window: "QMainWindow"):
        self._parent = main_window

    def settings(self):
        return [
            mobase.PluginSetting("enabled", "Enable", True),
            mobase.PluginSetting(
                "auto_install_after_download",
                "Automatically install a collection after Add Collection downloads finish",
                False,
            ),
        ]

    def handlesDownload(self, page_url, download_url, fileinfo):
        url = next(
            (
                candidate
                for candidate in (download_url.toString(), page_url.toString())
                if parseCollectionAddress(candidate)
            ),
            None,
        )
        if not url:
            return False

        qDebug(f"[NXMColDL] Handling collection link from Nexus: {url}")
        auto_install = self._organizer.pluginSetting(
            self.name(), "auto_install_after_download"
        )
        QTimer.singleShot(0, lambda: self.startCollectionFlow(url, auto_install))
        return True

    def startCollectionFlow(self, url, auto_install):
        global _active_collection_link_flow
        if _active_collection_link_flow and _active_collection_link_flow.isVisible():
            qDebug("[NXMColDL] Collection link ignored; another flow is already active")
            return

        _active_collection_link_flow = stepCollectionLinkFlow(
            url, self._parent, auto_install=auto_install
        )
        _active_collection_link_flow.exec()
        _active_collection_link_flow = None
