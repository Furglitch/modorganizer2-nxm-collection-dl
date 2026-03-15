import mobase

from .__meta__ import DownloadCollectionTool, InstallCollectionTool


def createPlugins() -> list[mobase.IPlugin]:
    return [DownloadCollectionTool(), InstallCollectionTool()]
