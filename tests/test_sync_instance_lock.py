"""One Sync window per Sync home. The lock is a real QLockFile in a second process."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

PyQt5 = pytest.importorskip("PyQt5")

from leasegrid_sync.app import ALREADY_RUNNING  # noqa: E402
from leasegrid_sync.cli import main  # noqa: E402

_HOLDER = """
import sys
import time
from pathlib import Path

from PyQt5.QtCore import QLockFile
from leasegrid_sync.app import instance_lock_path

path = instance_lock_path(Path(sys.argv[1]))
path.parent.mkdir(parents=True, exist_ok=True)
lock = QLockFile(str(path))
lock.setStaleLockTime(0)
ok = lock.tryLock(0)
print("LOCKED" if ok else "NO", flush=True)
if not ok:
    sys.exit(1)
time.sleep(60)
"""


def _hold(home: Path) -> subprocess.Popen[str]:
    proc = subprocess.Popen(
        [sys.executable, "-c", _HOLDER, str(home)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    line = proc.stdout.readline().strip() if proc.stdout is not None else ""
    if line != "LOCKED":
        err = proc.stderr.read() if proc.stderr is not None else ""
        proc.kill()
        proc.wait(timeout=5)
        raise AssertionError("holder did not take the lock: %r %s" % (line, err))
    return proc


def _release(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is None:
        proc.kill()
    proc.wait(timeout=5)


def _quiet_modes(ui, *_args, **_kwargs) -> int:
    """Stop a real window from entering the event loop during an allowed launch."""
    ui.poll.stop()
    ui.win.hide()
    if ui.tray is not None:
        ui.tray.hide()
    return 0


def test_second_instance_on_the_same_home_starts_no_window(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("LEASEGRID_SYNC_HOME", str(home))
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    holder = _hold(home)
    try:
        with patch("leasegrid_sync.app.MainWindow", side_effect=AssertionError("window")) as window, patch(
            "PyQt5.QtWidgets.QMessageBox.information", return_value=0
        ) as box:
            code = main([])
        assert code == 0
        assert window.call_count == 0
        assert box.call_count == 1
        assert box.call_args[0][2] == ALREADY_RUNNING
    finally:
        _release(holder)


def test_a_different_sync_home_is_not_blocked(tmp_path: Path, monkeypatch) -> None:
    held = tmp_path / "held"
    other = tmp_path / "other"
    held.mkdir()
    other.mkdir()
    monkeypatch.setenv("LEASEGRID_SYNC_HOME", str(other))
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    holder = _hold(held)
    try:
        with patch("leasegrid_sync.app._run_modes", side_effect=_quiet_modes) as modes, patch(
            "PyQt5.QtWidgets.QMessageBox.information", return_value=0
        ) as box:
            code = main([])
        assert code == 0
        assert modes.call_count == 1
        assert box.call_count == 0
    finally:
        _release(holder)


def test_stale_lock_from_a_killed_process_is_recovered(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("LEASEGRID_SYNC_HOME", str(home))
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    holder = _hold(home)
    _release(holder)
    with patch("leasegrid_sync.app._run_modes", side_effect=_quiet_modes) as modes, patch(
        "PyQt5.QtWidgets.QMessageBox.information", return_value=0
    ) as box:
        code = main([])
    assert code == 0
    assert modes.call_count == 1
    assert box.call_count == 0


def test_status_cli_is_not_blocked_by_the_home_lock(tmp_path: Path, monkeypatch, capsys) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("LEASEGRID_SYNC_HOME", str(home))
    holder = _hold(home)
    try:
        with patch("PyQt5.QtWidgets.QMessageBox.information", return_value=0) as box:
            code = main(["--status", "--nodedir", str(tmp_path / "missing-node")])
        captured = capsys.readouterr()
        assert box.call_count == 0
        assert "already running" not in (captured.out + captured.err).lower()
        assert code == 1
    finally:
        _release(holder)
