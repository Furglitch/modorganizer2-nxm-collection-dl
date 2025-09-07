import mobase

class PluginInfo(mobase.IPluginTool):

    _organizer: mobase.IOrganizer

    def __init__(self):
        super().__init__()

    def init(self, organizer: mobase.IOrganizer):
        self._organizer = organizer
        return True

    def name(self) -> str:
        return "Nexus Collections Downloader"
    
    def displayName(self):
        return "Nexus Collections Downloader"

    def author(self) -> str:
        return "Furglitch"

    def description(self) -> str:
        return "Allows downloading NXM collections directly in MO2"

    def version(self) -> mobase.VersionInfo:
        return mobase.VersionInfo(1, 0, 0, mobase.ReleaseType.ALPHA)

    def isActive(self) -> bool:
        return self._organizer.pluginSetting(self.name(), "enabled")

    def settings(self):
        return [
            mobase.PluginSetting("enabled", "Enable this plugin", True)
        ]
