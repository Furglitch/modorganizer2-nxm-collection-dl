import mobase
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QMainWindow
from .gui import StepURL

class PluginInfo(mobase.IPluginTool):

    _organizer: mobase.IOrganizer

    def __init__(self):
        super().__init__()

    def init(self, organizer: mobase.IOrganizer):
        self._organizer = organizer
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
        dlg = getattr(self, "_StepURL", None) or StepURL()
        dlg.exec()

    def settings(self): 
        return [ mobase.PluginSetting("enabled", "Enable", True) ]

    def onUserInterfaceInitializedCallback(self, main_window : "QMainWindow"):
        self._StepURL = StepURL(main_window)