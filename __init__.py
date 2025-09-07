import mobase

from .__meta__ import PluginInfo

def createPlugin() -> mobase.IPlugin:
    return PluginInfo()