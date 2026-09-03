import importlib

qtwidgets = None
try:
    qtwidgets = importlib.import_module("PyQt5.QtWidgets")
except Exception:
    qtwidgets = None

if qtwidgets is not None:
    for _name in dir(qtwidgets):
        if not _name.startswith("_"):
            globals()[_name] = getattr(qtwidgets, _name)
