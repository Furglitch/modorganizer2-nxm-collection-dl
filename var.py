import json, re

uri = None
game = None
collection = None
revision = None
author = "Unknown Author"
name = "Unknown Collection"
summary = "No description available."
thumbnail = None

essentialMods = []
optionalMods = []
externalMods = []
bundledMods = []

chosenOptional = []
chosenExternal = True

def cleanJson(data, visible=False):
    data = json.dumps(data, ensure_ascii=True)
    if visible: data = re.sub(r'\\u[0-9a-fA-F]{4}', '', data)
    return data