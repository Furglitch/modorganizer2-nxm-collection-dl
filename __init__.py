import mobase

from .__meta__ import CollectionModPage, DownloadCollectionTool, InstallCollectionTool


def createPlugins() -> list[mobase.IPlugin]:
    return [DownloadCollectionTool(), InstallCollectionTool(), CollectionModPage()]
