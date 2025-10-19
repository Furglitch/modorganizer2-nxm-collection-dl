import mobase
from PyQt6.QtCore import qDebug
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QMainWindow
from .gui import stepURL

class PluginInfo(mobase.IPluginTool):

    _organizer: mobase.IOrganizer

    def __init__(self):
        super().__init__()
        self._organizer = None

    def init(self, organizer: mobase.IOrganizer):
        self._organizer = organizer
        try:
            import sys as _sys
            _sys.modules[__name__]._active_plugin = self
        except Exception:
            pass
        self._organizer.onUserInterfaceInitialized(self.onUserInterfaceInitializedCallback)
        return True

    def name(self) -> str:
        return "NXM Collections Downloader"
    
    def displayName(self):
        return "NXM Collections Downloader"

    def author(self) -> str:
        return "Furglitch"

    def description(self) -> str:
        return "Allows downloading NXM collections directly in MO2"

    def version(self) -> mobase.VersionInfo:
        return mobase.VersionInfo(1, 0, 0, mobase.ReleaseType.ALPHA)

    def isActive(self) -> bool:
        return self._organizer.pluginSetting(self.name(), "enabled")
    
    def icon(self):
        return QIcon()
    
    def tooltip(self):
        return ""
    
    def setParentWidget(self, widget):
        self._parent = widget
    
    def display(self) -> None:
        dlg = getattr(self, "_stepURL", None) or stepURL()
        dlg.exec()

    def settings(self): 
        return [ mobase.PluginSetting("enabled", "Enable", True) ]

    def onUserInterfaceInitializedCallback(self, main_window : "QMainWindow"):
        self._stepURL = stepURL(main_window)
        
    def downloadMod(self, modInfo: dict):
        modID = int(modInfo['file']['mod']['modId'])
        fileID = int(modInfo['file']['fileId'])
        qDebug(f"Downloading mod {modID} file {fileID}")
        self._organizer.downloadManager().startDownloadNexusFile(modID, fileID)
        if hasattr(self, "_dialogFiles") and self._dialogFiles:
            try:
                self._dialogFiles.close()
            except Exception:
                pass