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


def test_handed_invite_keeps_typed_text_unless_the_user_says_yes(tmp_path: Path) -> None:
    window = _window(tmp_path)
    QtWidgets = window.QtWidgets
    try:
        window.invite_edit.setText("A")
        boxes: list = []

        def exec_no(box) -> int:
            boxes.append(box)
            return QtWidgets.QMessageBox.No

        with patch.object(QtWidgets.QMessageBox, "exec_", exec_no):
            window.receive_handed_invite("B")
        assert window.invite_edit.text() == "A"
        assert len(boxes) == 1
        box = boxes[0]
        assert box.text() == HANDED_INVITE_REPLACE
        assert box.text() == "Another invite arrived. Use it?"
        assert box.defaultButton() is box.button(QtWidgets.QMessageBox.No)
        with patch.object(QtWidgets.QMessageBox, "exec_", lambda _box: QtWidgets.QMessageBox.Yes):
            window.receive_handed_invite("B")
        assert window.invite_edit.text() == "B"
        log = window.home / "logs" / "sync-ui.log"
        if log.is_file():
            logged = log.read_text(encoding="utf-8")
            assert "invite arrived" not in logged
    finally:
        _close(window)
