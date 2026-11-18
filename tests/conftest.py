"""Shared pytest setup for the leasegrid-c test suite."""

from __future__ import annotations

import sys

import pytest

pytest_plugins = ["tests._watchdog"]


def _top_level_widgets() -> list:
    """Live top-level Qt widgets, or [] when the test never loaded Qt."""
    if "PyQt5.QtWidgets" not in sys.modules:
        return []
    from PyQt5 import QtWidgets

    if QtWidgets.QApplication.instance() is None:
        return []
    return list(QtWidgets.QApplication.topLevelWidgets())


def _address(widget) -> int:
    """The C++ address: stable even when Qt hands back a fresh Python wrapper."""
    from PyQt5 import sip

    return int(sip.unwrapinstance(widget))


def _dispose(widgets: list) -> None:
    """Stop timers, hide and delete widgets now, at a point where no Qt event is running."""
    from PyQt5 import QtCore, QtWidgets, sip

    for widget in widgets:
        if sip.isdeleted(widget):
            continue
        for timer in widget.findChildren(QtCore.QTimer):
            timer.stop()
        for tray in widget.findChildren(QtWidgets.QSystemTrayIcon):
            tray.hide()
        widget.hide()
        widget.deleteLater()
    QtWidgets.QApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


@pytest.fixture(autouse=True)
def _delete_qt_windows_after_each_test():
    """Delete every top-level window or dialog a test opened (#90).

    Leaked test windows kept Qt state alive for the rest of the run, and a
    later processEvents segfaulted on CI. Widgets that existed before the test
    (a module-scoped window, for one) are left for their own fixture.
    """
    before = {_address(w) for w in _top_level_widgets()}
    yield
    new = [w for w in _top_level_widgets() if _address(w) not in before]
    if new:
        _dispose(new)
