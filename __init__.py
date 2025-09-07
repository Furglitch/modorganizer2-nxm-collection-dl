import mobase  # For type-checking createPlugin().

from .plugin import MyPlugin  # Always use relative import:

def createPlugin() -> mobase.IPlugin:
    return MyPlugin()