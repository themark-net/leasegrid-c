"""Every Qt window and dialog a test opens is deleted when that test ends.

Leaked test windows kept Qt state alive across the run, and on CI a later
processEvents crashed (segfault in test_sync_close_invite, #90 slice E). The
autouse fixture in tests/conftest.py deletes each test's new top-level
widgets at a safe point. These two tests run in order: the first opens a
window and a dialog, the second checks they are gone.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PyQt5 = pytest.importorskip("PyQt5")

from PyQt5 import QtWidgets, sip  # noqa: E402

_LEFT: dict = {}


def test_a_window_and_a_dialog_opened_by_a_test(tmp_path: Path):
    from leasegrid_sync.app import AddStorageServerDialog, MainWindow

    nodedir = tmp_path / "tahoe"
    nodedir.mkdir()
    (nodedir / "tahoe.cfg").write_text("[node]\n", encoding="utf-8")
    window = MainWindow(nodedir=nodedir, home=tmp_path / "home", autoload=False)
    dlg = AddStorageServerDialog(window.win, window, window.QtWidgets)
    loose = QtWidgets.QDialog()
    loose.show()
    _LEFT.update(win=window.win, dlg=dlg.dlg, loose=loose, poll=window.poll)
    assert not sip.isdeleted(window.win)


def test_are_deleted_once_that_test_ends():
    if not _LEFT:
        pytest.skip("runs only after the test above")
    for key in ("win", "dlg", "loose"):
        assert sip.isdeleted(_LEFT[key]), "%s outlived its test" % key
    assert sip.isdeleted(_LEFT["poll"]) or not _LEFT["poll"].isActive()
    alive = [w for w in QtWidgets.QApplication.topLevelWidgets() if w.isVisible()]
    assert alive == []
