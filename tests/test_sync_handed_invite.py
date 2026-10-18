"""A handed invite does not replace text the user already typed."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

PyQt5 = pytest.importorskip("PyQt5")

from leasegrid_sync.app import HANDED_INVITE_REPLACE, MainWindow  # noqa: E402
from leasegrid_sync.backend import SyncError  # noqa: E402

# Wormhole-shaped fakes. Letters do not parse, so a Yes that joined would
# raise before any daemon started. Not secrets.
INVITE_A = "7-guitarist-revenge"
INVITE_B = "8-pianist-kindness"

_WINDOWS_BOX = (
    "Showing a real QMessageBox inside the shared pytest QApplication "
    "access-violates on Windows CI (window-, application- and non-modal "
    "alike); the old version mocked exec_. The real-process tests in "
    "test_sync_join_replace.py show the real box on Windows."
)


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


def _stay_up_tahoe(tmp_path: Path, marker: Path) -> str:
    """A ``tahoe run`` that records a spawn and stays up. POSIX wrapper."""
    script = tmp_path / "stay_tahoe.py"
    script.write_text(
        "import sys\n"
        "import time\n"
        "from pathlib import Path\n"
        "args = sys.argv[1:]\n"
        "marker = Path(%r)\n"
        "if args and args[0] == 'run' and len(args) > 1:\n"
        "    Path(args[1], 'node.url').write_text('http://127.0.0.1:1/\\n', encoding='utf-8')\n"
        "    marker.write_text('spawned\\n', encoding='utf-8')\n"
        "    while True:\n"
        "        time.sleep(0.2)\n"
        "raise SystemExit(0)\n" % str(marker),
        encoding="utf-8",
    )
    exe = tmp_path / "tahoe-stay"
    exe.write_text(
        "#!/bin/sh\nexec \"%s\" \"%s\" \"$@\"\n" % (sys.executable, script),
        encoding="utf-8",
    )
    exe.chmod(0o755)
    return str(exe)


def _welcome_when_ready(client):
    def welcome(timeout: float = 5.0):
        if not (client.nodedir / "node.url").is_file():
            raise SyncError("could not join this friendnet. Tahoe client is not reachable.")
        return {
            "introducers": {"statuses": ["Connected to tcp:127.0.0.1:45001 via tcp"]},
            "servers": [{"nickname": "storage-1", "connection_status": "connected"}],
        }

    return welcome


@pytest.mark.skipif(sys.platform == "win32", reason=_WINDOWS_BOX)
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


@pytest.mark.skipif(sys.platform == "win32", reason=_WINDOWS_BOX)
def test_yes_on_handed_replace_does_not_start_a_join(tmp_path: Path) -> None:
    """Yes puts the pending invite in the field. The user still has to press Join.

    A Yes handler that calls the join action spawns Tahoe. The threat box is
    checked so that path is not refused before the spawn.
    """
    window = _window(tmp_path)
    marker = tmp_path / "spawned"
    window.tahoe.tahoe_bin = _stay_up_tahoe(tmp_path, marker)
    window.threat_ack.setChecked(True)
    try:
        window.invite_edit.setText(INVITE_A)
        window.receive_handed_invite(INVITE_B)
        with patch.object(window.tahoe, "welcome", side_effect=_welcome_when_ready(window.tahoe)):
            _click(window, window.QtWidgets.QMessageBox.Yes)
        assert window.invite_edit.text() == INVITE_B
        assert window._joined is False
        assert window._joining is False
        assert not marker.is_file()
        assert window.tahoe._proc is None
    finally:
        window.tahoe.stop()
        _close(window)


@pytest.mark.skipif(sys.platform == "win32", reason=_WINDOWS_BOX)
def test_rehanding_the_current_invite_drops_the_older_pending(tmp_path: Path) -> None:
    """The latest hand wins. Re-handing the field invite clears an older pending Yes.

    Leaving the pending text in place would apply that older invite on a later Yes.
    """
    window = _window(tmp_path)
    try:
        window.invite_edit.setText(INVITE_A)
        window.receive_handed_invite(INVITE_B)
        assert window._handed_replace_pending == INVITE_B
        assert len(_replace_boxes(window)) == 1
        window.receive_handed_invite(INVITE_A)
        assert (getattr(window, "_handed_replace_pending", "") or "") == ""
        assert _replace_boxes(window) == []
        assert window.invite_edit.text() == INVITE_A
        window._on_handed_replace_finished(window.QtWidgets.QMessageBox.Yes)
        assert window.invite_edit.text() == INVITE_A
        assert window._joined is False
    finally:
        _close(window)
