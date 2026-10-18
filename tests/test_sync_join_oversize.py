"""An invite longer than the handoff cap must not join, and must not be sent."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from leasegrid_sync.app import ALREADY_RUNNING, _JOIN_HANDOFF_MAX, instance_lock_path
from leasegrid_sync.backend import TahoeClient
from leasegrid_sync.cli import main

PyQt5 = pytest.importorskip("PyQt5")
from PyQt5.QtCore import QLockFile  # noqa: E402

OVERSIZE = "x" * (_JOIN_HANDOFF_MAX + 1)


def _refuse_join(*_args, **_kwargs):
    raise AssertionError("join was attempted")


def _refuse_send(*_args, **_kwargs):
    raise AssertionError("invite was sent")


def test_oversized_join_with_a_held_lock_says_already_running(tmp_path: Path, monkeypatch) -> None:
    # The box is patched, so this checks the message and that join is not
    # attempted. It does not catch a missing QApplication. The unmocked gate
    # is tests/test_sync_already_running.py.
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("LEASEGRID_SYNC_HOME", str(home))
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    lock = QLockFile(str(instance_lock_path(home)))
    assert lock.tryLock(0)
    monkeypatch.setattr("leasegrid_sync.app._send_invite_posix", _refuse_send)
    monkeypatch.setattr("leasegrid_sync.app._send_invite_windows", _refuse_send)
    monkeypatch.setattr(TahoeClient, "join_invite", _refuse_join)
    try:
        with patch("PyQt5.QtWidgets.QMessageBox.information", return_value=0) as box:
            code = main(["--offscreen", "--join", OVERSIZE, "--nodedir", str(tmp_path / "node")])
        assert code != 0
        assert box.call_count == 1
        assert box.call_args[0][2] == ALREADY_RUNNING
        assert OVERSIZE not in box.call_args[0][2]
    finally:
        lock.unlock()


def test_oversized_join_with_a_free_lock_is_rejected(tmp_path: Path, monkeypatch, capsys) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("LEASEGRID_SYNC_HOME", str(home))
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setattr("leasegrid_sync.app._send_invite_posix", _refuse_send)
    monkeypatch.setattr("leasegrid_sync.app._send_invite_windows", _refuse_send)
    monkeypatch.setattr(TahoeClient, "join_invite", _refuse_join)
    code = main(["--offscreen", "--join", OVERSIZE, "--nodedir", str(tmp_path / "node")])
    assert code != 0
    err = capsys.readouterr().err
    assert err.strip() == "That invite is too long."
    assert OVERSIZE not in err
