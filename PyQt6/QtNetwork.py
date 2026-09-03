import importlib

qtnetwork = None
try:
    qtnetwork = importlib.import_module("PyQt5.QtNetwork")
except Exception:
    qtnetwork = None

if qtnetwork is not None:
    for _name in dir(qtnetwork):
        if not _name.startswith("_"):
            globals()[_name] = getattr(qtnetwork, _name)
