from PyQt6.QtCore import qDebug as _qDebug
# TODO Merge with fallback handler from #32


def qDebug(msg):
    text = str(msg)
    try:
        _qDebug(text)
        return
    except UnicodeEncodeError:
        pass

    try:
        ascii_safe = text.encode("ascii", errors="backslashreplace").decode("ascii")
        _qDebug(ascii_safe)
        return
    except Exception:
        pass

    try:
        ascii_repr = (
            repr(text).encode("ascii", errors="backslashreplace").decode("ascii")
        )
        _qDebug(ascii_repr)
    except Exception:
        return
