import mobase

class MyPlugin(mobase.IPluginTool):
    def __init__(self):
        super().__init__()

    def init(self, organizer: mobase.IOrganizer) -> bool:
        organizer.dow  # (1)
        return True

    def name(self) -> int:
        return 0


def createPlugin() -> mobase.IPlugin:
    return MyPlugin()