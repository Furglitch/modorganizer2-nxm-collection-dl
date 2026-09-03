import importlib

qtgui = None
try:
    qtgui = importlib.import_module("PyQt5.QtGui")
except Exception:
    qtgui = None

if qtgui is not None:
    for _name in dir(qtgui):
        if not _name.startswith("_"):
            globals()[_name] = getattr(qtgui, _name)
