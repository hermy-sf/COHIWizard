"""Minimal stand-in for PyQt5.QtCore, installed only if PyQt5 is not importable (headless CI,
no GUI libraries).  Provides what the smisdr drivers use: QObject and pyqtSignal with
connect / disconnect / emit (direct calls, which is what a PyQt5 signal does between objects
living in the same thread)."""
import sys
import types


class _BoundSignal:
    def __init__(self):
        self._slots = []

    def connect(self, slot):
        self._slots.append(slot)

    def disconnect(self, slot=None):
        if slot is None:
            self._slots.clear()
        else:
            self._slots.remove(slot)

    def emit(self, *args):
        for slot in list(self._slots):
            slot(*args)


class pyqtSignal:
    def __init__(self, *types):
        self._name = None

    def __set_name__(self, owner, name):
        self._name = "_sig_" + name

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        bound = obj.__dict__.get(self._name)
        if bound is None:
            bound = obj.__dict__[self._name] = _BoundSignal()
        return bound


class QObject:
    def __init__(self, *args, **kwargs):
        pass


class QMutex:
    def lock(self): pass
    def unlock(self): pass


class QThread(QObject):
    pass



def install():
    try:
        import PyQt5.QtCore  # noqa: F401
        return False
    except ImportError:
        pass
    pkg = types.ModuleType("PyQt5")
    core = types.ModuleType("PyQt5.QtCore")
    core.QObject = QObject
    core.pyqtSignal = pyqtSignal
    core.QMutex = QMutex
    core.QThread = QThread
    pkg.QtCore = core
    sys.modules["PyQt5"] = pkg
    sys.modules["PyQt5.QtCore"] = core
    return True
