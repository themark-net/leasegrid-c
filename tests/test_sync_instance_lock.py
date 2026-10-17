"""One Sync window per Sync home. The lock is a real QLockFile in a second process."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest

PyQt5 = pytest.importorskip("PyQt5")

from leasegrid_sync.app import ALREADY_RUNNING, instance_lock_path  # noqa: E402
from leasegrid_sync.cli import main  # noqa: E402

# Qt's default stale time is 30s. Aging the file beats sleeping in CI.
_STALE_AGE_S = 120

# The app process itself is the holder. The box is patched so a refusal can
# print and exit, and a close sentinel asks the first window to quit cleanly.
_APP_DRIVER = r'''
import os
import sys

from PyQt5 import QtCore, QtWidgets


def info(parent, title, text, *args, **kwargs):
    sys.stdout.write("MSGBOX:%s\n" % text)
    sys.stdout.flush()
    return QtWidgets.QMessageBox.Ok


QtWidgets.QMessageBox.information = staticmethod(info)

import leasegrid_sync.app as appmod

_orig_show = appmod.MainWindow.show


def show(self):
    _orig_show(self)
    sys.stdout.write("WINDOW_SHOWN\n")
    sys.stdout.flush()
    sentinel = os.environ.get("LEASEGRID_TEST_CLOSE_FILE", "")
    if not sentinel:
        return

    def poll():
        if os.path.exists(sentinel):
            self.win.close()
        else:
            QtCore.QTimer.singleShot(50, poll)

    QtCore.QTimer.singleShot(50, poll)


appmod.MainWindow.show = show

from leasegrid_sync.cli import main

rc = main(sys.argv[1:])
sys.stdout.write("EXIT:%s\n" % rc)
sys.stdout.flush()
raise SystemExit(0 if rc is None else int(rc))
'''

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


def _age_lock(path: Path) -> None:
    past = time.time() - _STALE_AGE_S
    os.utime(path, (past, past))


def _recovered(monkeypatch, home: Path) -> None:
    """A launch through cli.main takes the lock and does not show already-running."""
    monkeypatch.setenv("LEASEGRID_SYNC_HOME", str(home))
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    nodedir = home / "tahoe"
    with patch("leasegrid_sync.app._run_modes", side_effect=_quiet_modes) as modes, patch(
        "PyQt5.QtWidgets.QMessageBox.information", return_value=0
    ) as box:
        code = main(["--offscreen", "--nodedir", str(nodedir)])
    assert code == 0
    assert modes.call_count == 1
    assert box.call_count == 0


def test_empty_lock_older_than_stale_time_is_recovered(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    lock = instance_lock_path(home)
    lock.write_bytes(b"")
    _age_lock(lock)
    _recovered(monkeypatch, home)


def test_garbage_lock_older_than_stale_time_is_recovered(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    lock = instance_lock_path(home)
    lock.write_bytes(b"not a qt lock\n%%%\n")
    _age_lock(lock)
    _recovered(monkeypatch, home)


_MID_WRITE = r"""
import os
import socket
import sys
import time
from pathlib import Path

path = Path(sys.argv[1])
path.parent.mkdir(parents=True, exist_ok=True)
path.write_bytes(b"")
print("READY", flush=True)
time.sleep(0.05)
# pid, application name, hostname. getLockInfo treats a positive pid as readable.
payload = "%d\nleasegrid-sync\n%s\n" % (os.getpid(), socket.gethostname())
path.write_bytes(payload.encode("utf-8"))
print("WROTE", flush=True)
time.sleep(30)
"""


def test_empty_lock_mid_write_is_not_taken(tmp_path: Path) -> None:
    """A PID that appears during the short wait keeps the lock.

    The helper leaves an empty file, then writes a live pid about 50 ms later.
    Stealing the file on the first unreadable look would start a second instance.
    """
    from PyQt5.QtCore import QLockFile

    from leasegrid_sync.app import acquire_instance_lock, release_instance_lock

    QLockFile(str(tmp_path / "warm.lock"))
    home = tmp_path / "home"
    home.mkdir()
    lock = instance_lock_path(home)
    proc = subprocess.Popen(
        [sys.executable, "-c", _MID_WRITE, str(lock)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    took = False
    try:
        assert proc.stdout is not None
        line = ""
        box: list[str] = []

        def _read_ready() -> None:
            box.append(proc.stdout.readline() if proc.stdout is not None else "")

        reader = threading.Thread(target=_read_ready, daemon=True)
        reader.start()
        reader.join(5)
        assert not reader.is_alive(), "helper did not report READY"
        line = box[0].strip() if box else ""
        assert line == "READY"
        assert lock.read_bytes() == b""
        took = acquire_instance_lock(home)
        assert took is False
        text = lock.read_text(encoding="utf-8")
        assert text.startswith("%d\n" % proc.pid)
        assert socket.gethostname() in text
    finally:
        if took:
            release_instance_lock()
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=5)


def test_fresh_empty_lock_relaunches_at_once(tmp_path: Path, monkeypatch) -> None:
    """A crash mid-write leaves an empty lock of age 0. It must not wait 30s."""
    home = tmp_path / "home"
    home.mkdir()
    lock = instance_lock_path(home)
    lock.write_bytes(b"")
    started = time.monotonic()
    _recovered(monkeypatch, home)
    assert time.monotonic() - started < 5


def test_fresh_garbage_lock_relaunches_at_once(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    lock = instance_lock_path(home)
    lock.write_bytes(b"not a qt lock\n%%%\n")
    started = time.monotonic()
    _recovered(monkeypatch, home)
    assert time.monotonic() - started < 5


def test_foreign_host_lock_older_than_stale_time_is_recovered(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    lock = instance_lock_path(home)
    # pid, application name, hostname. Not this machine, and old enough to be stale.
    lock.write_bytes(b"1\nleasegrid-sync\nnot-this-host\n")
    _age_lock(lock)
    _recovered(monkeypatch, home)


class _Pipe:
    def __init__(self, proc: subprocess.Popen[str]) -> None:
        self.proc = proc
        self.lines: list[str] = []
        self.err_lines: list[str] = []
        self.shown = threading.Event()
        self.done = threading.Event()

        def read_out() -> None:
            stdout = proc.stdout
            if stdout is None:
                self.done.set()
                self.shown.set()
                return
            for line in stdout:
                self.lines.append(line)
                if "WINDOW_SHOWN" in line or "MSGBOX:" in line:
                    self.shown.set()
            self.done.set()
            self.shown.set()

        def read_err() -> None:
            stderr = proc.stderr
            if stderr is None:
                return
            for line in stderr:
                self.err_lines.append(line)

        threading.Thread(target=read_out, daemon=True).start()
        threading.Thread(target=read_err, daemon=True).start()

    def text(self) -> str:
        return "".join(self.lines)

    def errors(self) -> str:
        return "".join(self.err_lines)


def _spawn_app(
    home: Path, nodedir: Path, close_file: Path, driver: Path
) -> tuple[subprocess.Popen[str], _Pipe]:
    env = os.environ.copy()
    env["LEASEGRID_SYNC_HOME"] = str(home)
    env["LEASEGRID_TAHOE_NODEDIR"] = str(nodedir)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["LEASEGRID_TEST_CLOSE_FILE"] = str(close_file)
    proc = subprocess.Popen(
        [sys.executable, str(driver), "--offscreen", "--nodedir", str(nodedir)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    return proc, _Pipe(proc)


def _stop(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is None:
        proc.kill()
    proc.wait(timeout=5)


def _wait_shown(pipe: _Pipe, proc: subprocess.Popen[str], timeout: float) -> str:
    if not pipe.shown.wait(timeout):
        _stop(proc)
        raise AssertionError("app did not report in time: %s %s" % (pipe.text(), pipe.errors()))
    return pipe.text()


def test_live_app_refuses_a_second_launch_and_releases_on_quit(tmp_path: Path) -> None:
    """The first instance is the real app. Refusal does not wait out the stale time.

    The second launch runs as soon as the first window is up, while that process
    is still alive and the lock file is only seconds old. A 35s wait is the case
    Tester checked by hand; CI only needs the holder to be alive.
    """
    home = tmp_path / "home"
    nodedir = tmp_path / "no-tahoe"
    home.mkdir()
    close_file = tmp_path / "close-now"
    driver = tmp_path / "driver.py"
    driver.write_text(_APP_DRIVER, encoding="utf-8")
    lock = instance_lock_path(home)
    first, first_pipe = _spawn_app(home, nodedir, close_file, driver)
    second: subprocess.Popen[str] | None = None
    third: subprocess.Popen[str] | None = None
    try:
        opened = _wait_shown(first_pipe, first, 20)
        assert "WINDOW_SHOWN" in opened
        assert lock.is_file()
        assert not nodedir.exists()
        second, second_pipe = _spawn_app(home, nodedir, tmp_path / "unused-close", driver)
        if not second_pipe.done.wait(20):
            raise AssertionError("second launch did not exit: %s" % second_pipe.text())
        refused = second_pipe.text()
        assert second.wait(timeout=5) == 0
        assert ("MSGBOX:%s" % ALREADY_RUNNING) in refused
        assert "WINDOW_SHOWN" not in refused
        assert not nodedir.exists()
        assert "Traceback" not in second_pipe.errors()
        close_file.write_text("quit", encoding="utf-8")
        if not first_pipe.done.wait(20):
            raise AssertionError("first app did not quit: %s" % first_pipe.text())
        assert first.wait(timeout=5) == 0
        assert not lock.exists()
        third_close = tmp_path / "close-third"
        third, third_pipe = _spawn_app(home, nodedir, third_close, driver)
        accepted = _wait_shown(third_pipe, third, 20)
        assert "WINDOW_SHOWN" in accepted
        assert ("MSGBOX:%s" % ALREADY_RUNNING) not in accepted
        third_close.write_text("quit", encoding="utf-8")
        if not third_pipe.done.wait(20):
            raise AssertionError("third launch did not quit: %s" % third_pipe.text())
        assert third.wait(timeout=5) == 0
        assert not lock.exists()
    finally:
        _stop(first)
        if second is not None:
            _stop(second)
        if third is not None:
            _stop(third)


def test_six_concurrent_starts_open_one_window(tmp_path: Path) -> None:
    """Six launches at once still produce one window. The other five are refused."""
    home = tmp_path / "home"
    nodedir = tmp_path / "no-tahoe"
    home.mkdir()
    close_file = tmp_path / "close-now"
    driver = tmp_path / "driver.py"
    driver.write_text(_APP_DRIVER, encoding="utf-8")
    procs: list[subprocess.Popen[str]] = []
    pipes: list[_Pipe] = []
    try:
        for _ in range(6):
            proc, pipe = _spawn_app(home, nodedir, close_file, driver)
            procs.append(proc)
            pipes.append(pipe)
        shown = 0
        boxes = 0
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            shown = sum("WINDOW_SHOWN" in pipe.text() for pipe in pipes)
            boxes = sum(("MSGBOX:%s" % ALREADY_RUNNING) in pipe.text() for pipe in pipes)
            finished = sum(proc.poll() is not None for proc in procs)
            if shown == 1 and boxes == 5 and finished >= 5:
                break
            time.sleep(0.05)
        else:
            details = [
                (proc.poll(), pipe.text(), pipe.errors()) for proc, pipe in zip(procs, pipes)
            ]
            raise AssertionError("six starts did not settle: %s" % (details,))
        assert shown == 1
        assert boxes == 5
        assert not (nodedir / "tahoe.cfg").is_file()
        close_file.write_text("quit", encoding="utf-8")
        winner = next(
            proc for proc, pipe in zip(procs, pipes) if "WINDOW_SHOWN" in pipe.text()
        )
        assert winner.wait(timeout=15) == 0
        assert not instance_lock_path(home).exists()
    finally:
        for proc in procs:
            _stop(proc)
