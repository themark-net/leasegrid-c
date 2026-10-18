"""A handed invite does not replace text the user already typed."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

PyQt5 = pytest.importorskip("PyQt5")

from leasegrid_sync.app import HANDED_INVITE_REPLACE, MainWindow  # noqa: E402
from leasegrid_sync.backend import SyncError  # noqa: E402


def _window(tmp_path: Path) -> MainWindow:
    home = tmp_path / "home"
    nodedir = tmp_path / "tahoe"
    nodedir.mkdir()
    (nodedir / "tahoe.cfg").write_text("[node]\n", encoding="utf-8")
    with patch(
        "leasegrid_sync.app.TahoeClient.join_existing",
        side_effect=SyncError("could not join this friendnet. No Tahoe.", "Retry."),
    ):
        return MainWindow(nodedir=nodedir, home=home)


def _close(window: MainWindow) -> None:
    window.poll.stop()
    window.win.hide()


def _replace_boxes(window: MainWindow) -> list:
    return [
        box
        for box in window.win.findChildren(window.QtWidgets.QMessageBox)
        if box.objectName() == "handedInviteReplace"
    ]


def _click(window: MainWindow, answer: int) -> None:
    """Click Yes or No. A fuse clicks No if a nested exec_() is still in the way."""
    QtCore = window.QtCore
    QtWidgets = window.QtWidgets
    fuse = QtCore.QTimer(window.win)
    fuse.setSingleShot(True)

    def _no() -> None:
        for box in _replace_boxes(window):
            button = box.button(QtWidgets.QMessageBox.No)
            if button is not None:
                button.click()

    fuse.timeout.connect(_no)
    fuse.start(1500)
    try:
        boxes = _replace_boxes(window)
        assert len(boxes) == 1
        button = boxes[0].button(answer)
        assert button is not None
        button.click()
        window.app.processEvents()
    finally:
        fuse.stop()


def test_handed_invite_keeps_typed_text_unless_the_user_says_yes(tmp_path: Path) -> None:
    window = _window(tmp_path)
    QtWidgets = window.QtWidgets
    try:
        window.invite_edit.setText("A")
        # Armed before the handoff so a nested exec_() cannot hang this test.
        fuse = window.QtCore.QTimer(window.win)
        fuse.setSingleShot(True)
        fuse.timeout.connect(lambda: _click(window, QtWidgets.QMessageBox.No))
        fuse.start(1500)
        window.receive_handed_invite("B")
        fuse.stop()
        assert window.invite_edit.text() == "A"
        boxes = _replace_boxes(window)
        assert len(boxes) == 1
        box = boxes[0]
        assert box.text() == HANDED_INVITE_REPLACE
        assert box.text() == "Another invite arrived. Use it?"
        assert box.defaultButton() is box.button(QtWidgets.QMessageBox.No)
        assert box.escapeButton() is box.button(QtWidgets.QMessageBox.No)
        _click(window, QtWidgets.QMessageBox.No)
        assert window.invite_edit.text() == "A"
        assert _replace_boxes(window) == []
        window.receive_handed_invite("B")
        _click(window, QtWidgets.QMessageBox.Yes)
        assert window.invite_edit.text() == "B"
        log = window.home / "logs" / "sync-ui.log"
        if log.is_file():
            logged = log.read_text(encoding="utf-8")
            assert "invite arrived" not in logged
            assert "\nB\n" not in logged
    finally:
        _close(window)
