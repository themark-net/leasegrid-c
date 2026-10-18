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
# Patching the box means this file does not catch a QApplication that is
# discarded before the widget exists. The unmocked gate is
# tests/test_sync_already_running.py.
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


def test_empty_lock_mid_write_is_not_taken(tmp_path: Path, monkeypatch) -> None:
    """A PID that appears during the short wait keeps the lock.

    Another starter has created the lock file but not yet written its PID.
    The grace hook stands in for that starter finishing its write during the
    wait, so the order is the same on every runner. Stealing the file on the
    first unreadable look would start a second instance.
    """
    import leasegrid_sync.app as appmod
    from leasegrid_sync.app import acquire_instance_lock, release_instance_lock

    home = tmp_path / "home"
    home.mkdir()
    lock = instance_lock_path(home)
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_bytes(b"")
    # pid, application name, hostname: the shape QLockFile writes.
    payload = "%d\nleasegrid-sync\n%s\n" % (os.getpid(), socket.gethostname())
    graced: list[bool] = []

    def finish_write() -> None:
        graced.append(True)
        lock.write_bytes(payload.encode("utf-8"))

    monkeypatch.setattr(appmod, "_lock_writer_grace", finish_write)
    took = acquire_instance_lock(home)
    try:
        assert graced == [True], "the empty lock was not given a grace wait"
        assert took is False
        assert lock.read_text(encoding="utf-8") == payload
    finally:
        if took:
            release_instance_lock()


def test_second_trylock_takes_the_lock_after_the_writer_grace(tmp_path: Path, monkeypatch) -> None:
    """The writer removes the empty file during the grace, so the second try takes it.

    One holder afterwards: a rival tryLock fails. Treating the first miss as
    final would leave the home unlocked.
    """
    import leasegrid_sync.app as appmod
    from PyQt5.QtCore import QLockFile
    from leasegrid_sync.app import acquire_instance_lock, release_instance_lock

    home = tmp_path / "home"
    home.mkdir()
    lock_path = instance_lock_path(home)
    lock_path.write_bytes(b"")
    graced: list[bool] = []

    def writer_finishes() -> None:
        graced.append(True)
        try:
            lock_path.unlink()
        except OSError:
            pass

    monkeypatch.setattr(appmod, "_lock_writer_grace", writer_finishes)
    took = acquire_instance_lock(home)
    try:
        assert graced == [True]
        assert took is True
        assert lock_path.is_file()
        rival = QLockFile(str(lock_path))
        rival.setStaleLockTime(2000)
        assert rival.tryLock(0) is False
    finally:
        if took:
            release_instance_lock()


def _refused(monkeypatch, home: Path) -> None:
    """A launch through cli.main shows already-running and opens no window."""
    monkeypatch.setenv("LEASEGRID_SYNC_HOME", str(home))
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    nodedir = home / "tahoe"
    with patch("leasegrid_sync.app.MainWindow", side_effect=AssertionError("window")) as window, patch(
        "PyQt5.QtWidgets.QMessageBox.information", return_value=0
    ) as box:
        code = main(["--offscreen", "--nodedir", str(nodedir)])
    assert code == 0
    assert window.call_count == 0
    assert box.call_count == 1
    assert box.call_args[0][2] == ALREADY_RUNNING


def test_fresh_empty_lock_is_refused(tmp_path: Path, monkeypatch) -> None:
    """A PID-less lock younger than 2s is a rival or a crash mid-write.

    It must not be deleted, and the refusal must not wait out Qt's 30s stale time.
    """
    home = tmp_path / "home"
    home.mkdir()
    lock = instance_lock_path(home)
    lock.write_bytes(b"")
    started = time.monotonic()
    _refused(monkeypatch, home)
    assert time.monotonic() - started < 5
    assert lock.read_bytes() == b""


def test_fresh_garbage_lock_is_refused(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    lock = instance_lock_path(home)
    payload = b"not a qt lock\n%%%\n"
    lock.write_bytes(payload)
    started = time.monotonic()
    _refused(monkeypatch, home)
    assert time.monotonic() - started < 5
    assert lock.read_bytes() == payload


def test_empty_lock_past_the_age_threshold_relaunches_quickly(tmp_path: Path, monkeypatch) -> None:
    """Past 2s, a PID-less lock is taken without waiting for Qt's 30s stale time.

    Qt's stale time is the gate. Dropping setStaleLockTime leaves the 30s
    default, and this 5s-old file is refused.
    """
    home = tmp_path / "home"
    home.mkdir()
    lock = instance_lock_path(home)
    lock.write_bytes(b"")
    past = time.time() - 5
    os.utime(lock, (past, past))
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


# Six real processes call acquire_instance_lock on one home per round.
# Holders are counted before any of them releases.
_LOCK_RACE = r'''
import os
import sys
import time
from pathlib import Path

N = 6


def worker(k, root, trials):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from leasegrid_sync.app import acquire_instance_lock, release_instance_lock

    for t in range(trials):
        d = root / str(t)
        while not (d / "go").exists():
            time.sleep(0.0005)
        ok = acquire_instance_lock(d)
        (d / ("r%d_%d" % (k, int(ok)))).write_text("1", encoding="utf-8")
        while not (d / "done").exists():
            time.sleep(0.0005)
        if ok:
            release_instance_lock()
    os._exit(0)


def _wait_kids(kids):
    if os.name == "posix":
        for pid in kids:
            os.waitpid(pid, 0)
        return
    for proc in kids:
        proc.wait(timeout=120)


def main():
    trials = int(sys.argv[1])
    root = Path(sys.argv[2])
    kind = sys.argv[3]
    if os.name == "posix":
        kids = []
        for k in range(N):
            pid = os.fork()
            if pid == 0:
                try:
                    worker(k, root, trials)
                except Exception:
                    os._exit(1)
            kids.append(pid)
    else:
        import subprocess

        kids = []
        for k in range(N):
            kids.append(
                subprocess.Popen(
                    [sys.executable, __file__, "worker", str(k), str(root), str(trials)]
                )
            )
    # Let the workers import Qt before the first round.
    time.sleep(2)
    multi = 0
    zero = 0
    for t in range(trials):
        d = root / str(t)
        d.mkdir(parents=True)
        if kind in ("empty", "aged"):
            lock = d / ".leasegrid-sync.lock"
            lock.write_text("", encoding="utf-8")
            if kind == "aged":
                old = time.time() - 5
                os.utime(lock, (old, old))
        elif kind == "garbage":
            (d / ".leasegrid-sync.lock").write_text("junk\n", encoding="utf-8")
        (d / "go").write_text("", encoding="utf-8")
        deadline = time.time() + 30
        while len([p for p in d.iterdir() if p.name.startswith("r")]) < N:
            if time.time() > deadline:
                print("TIMEOUT round %d" % t)
                os._exit(2)
            time.sleep(0.001)
        wins = len([p for p in d.iterdir() if p.name.endswith("_1")])
        if wins > 1:
            multi += 1
        if wins == 0:
            zero += 1
        (d / "done").write_text("", encoding="utf-8")
    _wait_kids(kids)
    print("multi=%d zero=%d trials=%d kind=%s" % (multi, zero, trials, kind))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "worker":
        worker(int(sys.argv[2]), Path(sys.argv[3]), int(sys.argv[4]))
    else:
        main()
'''


def test_six_callers_never_double_hold(tmp_path: Path) -> None:
    """Concurrent acquire_instance_lock calls never overlap on one home.

    A fresh empty lock is refused (zero holders). No pre-existing lock, and a
    PID-less lock older than 2s, each have exactly one holder. Counted while
    every caller is still inside the call.
    """
    script = tmp_path / "race.py"
    script.write_text(_LOCK_RACE, encoding="utf-8")
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    # 200 rounds per kind. The macOS Intel runner is about 3x slower than
    # Linux, so each kind gets its own generous timeout instead of a shared
    # 60 s wall-clock assertion; a hang still fails by timeout.
    rounds = 200
    for kind, expect_zero in (("empty", True), ("none", False), ("aged", False)):
        root = tmp_path / kind
        root.mkdir()
        proc = subprocess.run(
            [sys.executable, str(script), str(rounds), str(root), kind],
            capture_output=True,
            text=True,
            env=env,
            timeout=180,
            check=False,
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr
        line = proc.stdout.strip().splitlines()[-1]
        assert line.startswith("multi=0 "), line
        if expect_zero:
            assert " zero=%d " % rounds in line, line
        else:
            assert " zero=0 " in line, line
