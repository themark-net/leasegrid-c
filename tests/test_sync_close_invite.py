"""Closing the window asks before it cancels a live invite."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

PyQt5 = pytest.importorskip("PyQt5")

from leasegrid_sync.app import INVITE_CLOSE_QUESTION, MainWindow  # noqa: E402
from leasegrid_sync.backend import SyncError  # noqa: E402
from leasegrid_sync.invite import InviteCodeSession  # noqa: E402


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
    if window.tray is not None:
        window.tray.hide()


def _live_session() -> InviteCodeSession:
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return InviteCodeSession(code="7-alpha-bravo", proc=proc)


def _choose(label: str):
    def exec_(self) -> int:
        labels = [button.text() for button in self.buttons()]
        assert "Quit" in labels
        assert "Keep open" in labels
        assert self.text() == INVITE_CLOSE_QUESTION
        assert self.defaultButton().text() == "Keep open"
        self._choice = label
        return 0

    def clicked(self):
        for button in self.buttons():
            if button.text() == getattr(self, "_choice", ""):
                return button
        return None

    return exec_, clicked


def test_keep_open_ignores_close_and_leaves_the_invite(tmp_path: Path, monkeypatch) -> None:
    window = _window(tmp_path)
    session = _live_session()
    window._invite_session = session
    exec_, clicked = _choose("Keep open")
    monkeypatch.setattr(window.QtWidgets.QMessageBox, "exec_", exec_)
    monkeypatch.setattr(window.QtWidgets.QMessageBox, "clickedButton", clicked)
    event = window.QtGui.QCloseEvent()
    try:
        with patch.object(window, "quit", side_effect=AssertionError("quit")):
            window._on_close(event)
        assert not event.isAccepted()
        assert session.proc is not None and session.proc.poll() is None
    finally:
        session.close()
        _close(window)


def test_quit_accepts_close_and_closes_the_invite(tmp_path: Path, monkeypatch) -> None:
    window = _window(tmp_path)
    session = _live_session()
    window._invite_session = session
    exec_, clicked = _choose("Quit")
    monkeypatch.setattr(window.QtWidgets.QMessageBox, "exec_", exec_)
    monkeypatch.setattr(window.QtWidgets.QMessageBox, "clickedButton", clicked)
    event = window.QtGui.QCloseEvent()
    try:
        window._on_close(event)
        assert event.isAccepted()
        assert session.proc is None or session.proc.poll() is not None
        assert window._invite_session is None
    finally:
        if session.proc is not None and session.proc.poll() is None:
            session.close()
        _close(window)


def test_close_without_a_live_invite_quits_without_a_dialog(tmp_path: Path) -> None:
    window = _window(tmp_path)
    event = window.QtGui.QCloseEvent()
    called: list[bool] = []
    try:
        with patch.object(window, "quit", side_effect=lambda: called.append(True)), patch.object(
            window.QtWidgets.QMessageBox,
            "__init__",
            side_effect=AssertionError("dialog"),
        ):
            window._on_close(event)
        assert called == [True]
        assert event.isAccepted()
    finally:
        _close(window)
