import importlib

try:
    qtcore = importlib.import_module("PyQt5.QtCore")
except Exception:
    qtcore = None

if qtcore is not None:
    for _name in dir(qtcore):
        if not _name.startswith("_"):
            globals()[_name] = getattr(qtcore, _name)

if "qDebug" not in globals():

    def qDebug(*args, **kwargs):
        return None
