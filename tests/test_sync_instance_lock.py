"""One Sync window per Sync home. The lock is a real QLockFile in a second process."""

from __future__ import annotations

import os
import signal
import socket
import stat
import subprocess
import sys
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest

PyQt5 = pytest.importorskip("PyQt5")

from leasegrid_sync.app import ALREADY_RUNNING, _lock_path_problem, instance_lock_path  # noqa: E402
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


def test_young_other_host_lock_is_not_stolen(tmp_path: Path, monkeypatch) -> None:
    """A lock from another host, a few seconds old, is not taken and does not block.

    Qt's 2s stale time treats that file as stale and steals it at once. The
    launch must refuse immediately instead, and leave the file unchanged.
    Same-host dead pids stay on the path covered by the killed-process test.
    """
    home = tmp_path / "home"
    home.mkdir()
    lock = instance_lock_path(home)
    payload = b"1\nleasegrid-sync\nnot-this-host\n"
    lock.write_bytes(payload)
    past = time.time() - 3
    os.utime(lock, (past, past))
    started = time.monotonic()
    _refused(monkeypatch, home)
    assert time.monotonic() - started < 5
    assert lock.read_bytes() == payload


def _lock_failure(monkeypatch, home: Path, capsys) -> tuple[int, str]:
    """Launch. Return the exit code and the text the user can see."""
    monkeypatch.setenv("LEASEGRID_SYNC_HOME", str(home))
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    nodedir = home / "tahoe"
    with patch("leasegrid_sync.app.MainWindow", side_effect=AssertionError("window")) as window, patch(
        "PyQt5.QtWidgets.QMessageBox.information", return_value=0
    ) as box:
        code = main(["--offscreen", "--nodedir", str(nodedir)])
    err = capsys.readouterr().err
    shown = ""
    if box.call_count:
        shown = str(box.call_args[0][2])
    assert window.call_count == 0
    return code, err + "\n" + shown


def test_lock_path_that_is_a_directory_names_the_next_step(tmp_path: Path, monkeypatch, capsys) -> None:
    """A directory where the lock file should be fails in one sentence, with a next step."""
    home = tmp_path / "home"
    home.mkdir()
    lock = instance_lock_path(home)
    lock.mkdir()
    code, text = _lock_failure(monkeypatch, home, capsys)
    assert code == 1
    assert "Traceback" not in text
    assert "lock path is a directory" in text
    assert "Next:" in text
    assert "already running" not in text.lower()
    assert lock.is_dir()


@pytest.mark.skipif(
    sys.platform == "win32",
    reason=(
        "chmod(0) only sets the Windows read-only attribute; "
        "it does not create a mode-000 file or deny the owner read"
    ),
)
def test_lock_file_mode_000_names_the_next_step(tmp_path: Path, monkeypatch, capsys) -> None:
    """A lock file with mode 000 fails in one sentence. It does not start a second instance."""
    home = tmp_path / "home"
    home.mkdir()
    lock = instance_lock_path(home)
    lock.write_bytes(b"")
    lock.chmod(0)
    try:
        code, text = _lock_failure(monkeypatch, home, capsys)
        assert code == 1
        assert "Traceback" not in text
        assert "could not read its lock file" in text
        assert "Next:" in text
        assert "already running" not in text.lower()
        assert lock.is_file()
    finally:
        lock.chmod(0o644)


def _raise_permission_on_lock_read(monkeypatch, lock: Path) -> None:
    """builtins.open of this lock, for read, raises PermissionError.

    ``_lock_read_state`` (run only after tryLock failed) uses that open;
    ``_lock_path_problem`` only stats. ``pathlib`` reads go through
    ``io.open``, which this patch leaves alone.
    """
    real_open = open
    target = os.path.normcase(os.path.abspath(lock))

    def guarded(file, mode="r", *args, **kwargs):
        text = mode if isinstance(mode, str) else ""
        try:
            got = os.path.normcase(os.path.abspath(os.fspath(file)))
        except (TypeError, ValueError):
            got = ""
        if got == target and (text.startswith("r") or text == ""):
            raise PermissionError(13, "Permission denied", os.fspath(file))
        return real_open(file, mode, *args, **kwargs)

    monkeypatch.setattr("builtins.open", guarded)


def test_lock_file_permission_error_names_the_next_step(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """A lock the user cannot read names the next step. It is not already running.

    Mode 000 is not how Windows denies a read. PermissionError on open is.
    """
    home = tmp_path / "home"
    home.mkdir()
    lock = instance_lock_path(home)
    lock.write_bytes(b"")
    _raise_permission_on_lock_read(monkeypatch, lock)
    code, text = _lock_failure(monkeypatch, home, capsys)
    assert code == 1
    assert "Traceback" not in text
    assert "could not read its lock file" in text
    assert "Next:" in text
    assert "already running" not in text.lower()
    assert lock.is_file()


def test_mode_000_is_unreadable_without_opening(tmp_path: Path, monkeypatch) -> None:
    """Mode 000 is reported before open. Root can read that file; the mode still counts."""
    lock = tmp_path / ".leasegrid-sync.lock"
    lock.write_bytes(b"x")

    class _Mode0:
        st_mode = stat.S_IFREG

    real_stat = Path.stat

    def fake_stat(self, *args, **kwargs):
        if Path(self) == lock:
            return _Mode0()
        return real_stat(self, *args, **kwargs)

    def refuse_open(*args, **kwargs):
        raise AssertionError("mode 000 must be reported before the file is opened")

    monkeypatch.setattr(Path, "stat", fake_stat)
    monkeypatch.setattr("builtins.open", refuse_open)
    problem = _lock_path_problem(lock)
    assert problem is not None
    assert "could not read its lock file" in problem[0]
    assert "Next:" not in problem[0]
    assert problem[1]


def _icacls_deny(path: Path, rights: str) -> str:
    user = os.environ.get("USERNAME")
    if not user:
        pytest.fail("USERNAME is unset, so icacls cannot name the deny ACE")
    proc = subprocess.run(
        ["icacls", os.fspath(path), "/deny", "%s:%s" % (user, rights)],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        pytest.fail("icacls /deny failed (%s): %s" % (proc.returncode, detail))
    return user


def _icacls_reset(path: Path) -> None:
    subprocess.run(
        ["icacls", os.fspath(path), "/reset"],
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.skipif(
    sys.platform != "win32",
    reason="icacls deny (R) is the Windows stand-in for a mode-000 lock file",
)
def test_lock_file_windows_acl_deny_names_the_next_step(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """A Windows read deny on the lock file names the next step, not already running."""
    home = tmp_path / "home"
    home.mkdir()
    lock = instance_lock_path(home)
    lock.write_bytes(b"")
    _icacls_deny(lock, "(R)")
    try:
        code, text = _lock_failure(monkeypatch, home, capsys)
        assert code == 1
        assert "Traceback" not in text
        assert "could not read its lock file" in text
        assert "Next:" in text
        assert "already running" not in text.lower()
        assert lock.is_file()
    finally:
        _icacls_reset(lock)


def test_lock_home_that_cannot_be_created_names_the_next_step(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """A home whose parent is not a directory must not start a second window.

    mkdir failing used to return success, so this launch took no lock and
    opened the app. After the sentence, a real home still starts.
    """
    blocked = tmp_path / "not-a-directory"
    blocked.write_text("stay", encoding="utf-8")
    home = blocked / "sync-home"
    code, text = _lock_failure(monkeypatch, home, capsys)
    assert code == 1
    assert "Traceback" not in text
    assert "could not create its home folder" in text
    assert "Next:" in text
    assert "already running" not in text.lower()
    assert blocked.read_text(encoding="utf-8") == "stay"
    assert not home.exists()
    good = tmp_path / "home"
    good.mkdir()
    _recovered(monkeypatch, good)


def test_unwritable_home_does_not_pretend_the_app_is_already_running(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """A home we cannot write a lock into is not an already-running app.

    Restoring the mode lets the next launch take the lock.
    """
    if os.name == "nt" or (hasattr(os, "geteuid") and os.geteuid() == 0):
        pytest.skip("directory mode does not block this user")
    home = tmp_path / "home"
    home.mkdir()
    home.chmod(0o555)
    try:
        code, text = _lock_failure(monkeypatch, home, capsys)
        assert code == 1
        assert "Traceback" not in text
        assert "could not write its lock file" in text
        assert "Next:" in text
        assert "already running" not in text.lower()
        assert not instance_lock_path(home).exists()
    finally:
        home.chmod(0o755)
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
import faulthandler
import os
import signal
import sys
import time
import traceback
from pathlib import Path

N = 6
# Seconds one round may take before the race gives up. Every wait below is
# bounded, so a dead or stuck worker fails the race instead of hanging it.
ROUND_S = float(os.environ.get("LEASEGRID_RACE_ROUND_S") or "30")


def _wait_for(path, what):
    deadline = time.monotonic() + 3 * ROUND_S
    while not path.exists():
        if time.monotonic() > deadline:
            sys.stderr.write("worker gave up waiting for %s (%s)\n" % (what, path))
            sys.stderr.flush()
            os._exit(3)
        time.sleep(0.0005)


def worker(k, root, trials):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    (root / ("pid%d" % k)).write_text(str(os.getpid()), encoding="utf-8")
    from leasegrid_sync.app import acquire_instance_lock, release_instance_lock

    for t in range(trials):
        d = root / str(t)
        _wait_for(d / "go", "go %d" % t)
        if os.environ.get("LEASEGRID_RACE_FAULT") == "crash:%d:%d" % (k, t):
            raise RuntimeError("injected worker crash k=%d t=%d" % (k, t))
        # If acquire_instance_lock itself blocks, dump where before the
        # round times out, so a hang in the app's lock path is visible.
        faulthandler.dump_traceback_later(ROUND_S * 0.8, exit=False)
        ok = acquire_instance_lock(d)
        faulthandler.cancel_dump_traceback_later()
        (d / ("r%d_%d" % (k, int(ok)))).write_text("1", encoding="utf-8")
        _wait_for(d / "done", "done %d" % t)
        if ok:
            release_instance_lock()


def _run_worker(k, root, trials):
    try:
        worker(k, root, trials)
    except BaseException:
        traceback.print_exc()
        sys.stderr.flush()
        os._exit(1)
    sys.stderr.flush()
    os._exit(0)


def _kill_kids(kids):
    for kid in kids:
        try:
            if os.name == "posix":
                os.kill(kid, signal.SIGKILL)
                os.waitpid(kid, 0)
            else:
                kid.kill()
                kid.wait(timeout=10)
        except Exception:
            pass


def _wait_kids(kids, root):
    deadline = time.monotonic() + 3 * ROUND_S
    bad = []
    for k, kid in enumerate(kids):
        if os.name == "posix":
            while True:
                pid, status = os.waitpid(kid, os.WNOHANG)
                if pid:
                    code = os.waitstatus_to_exitcode(status)
                    break
                if time.monotonic() > deadline:
                    code = None
                    break
                time.sleep(0.01)
        else:
            try:
                code = kid.wait(timeout=max(0.1, deadline - time.monotonic()))
            except Exception:
                code = None
        if code != 0:
            bad.append((k, code))
    if bad:
        _kill_kids(kids)
        _fail("workers did not exit cleanly: %s" % bad, root)


def _fail(msg, root):
    print(msg)
    for k in range(N):
        log = root / ("w%d.log" % k)
        text = log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""
        if text.strip():
            print("--- worker %d ---" % k)
            print(text.rstrip())
    sys.stdout.flush()
    os._exit(2)


def main():
    trials = int(sys.argv[1])
    root = Path(sys.argv[2])
    kind = sys.argv[3]
    kids = []
    if os.name == "posix":
        for k in range(N):
            log = open(root / ("w%d.log" % k), "w", encoding="utf-8")
            pid = os.fork()
            if pid == 0:
                os.dup2(log.fileno(), 1)
                os.dup2(log.fileno(), 2)
                _run_worker(k, root, trials)
            log.close()
            kids.append(pid)
    else:
        import subprocess

        for k in range(N):
            with open(root / ("w%d.log" % k), "w", encoding="utf-8") as log:
                kids.append(
                    subprocess.Popen(
                        [sys.executable, __file__, "worker", str(k), str(root), str(trials)],
                        stdin=subprocess.DEVNULL,
                        stdout=log,
                        stderr=subprocess.STDOUT,
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
        deadline = time.monotonic() + ROUND_S
        while len([p for p in d.iterdir() if p.name.startswith("r")]) < N:
            if time.monotonic() > deadline:
                seen = sorted(p.name for p in d.iterdir() if p.name.startswith("r"))
                _kill_kids(kids)
                _fail("TIMEOUT round %d: reported %s" % (t, seen), root)
            time.sleep(0.001)
        wins = len([p for p in d.iterdir() if p.name.endswith("_1")])
        if wins > 1:
            multi += 1
        if wins == 0:
            zero += 1
        (d / "done").write_text("", encoding="utf-8")
    _wait_kids(kids, root)
    print("multi=%d zero=%d trials=%d kind=%s" % (multi, zero, trials, kind))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "worker":
        _run_worker(int(sys.argv[2]), Path(sys.argv[3]), int(sys.argv[4]))
    else:
        main()
'''


def _kill_pid(pid: int) -> None:
    try:
        os.kill(pid, signal.SIGKILL if os.name == "posix" else signal.SIGTERM)
    except OSError:
        pass


def _run_lock_race(script, rounds, root, kind, env, timeout):
    """Run one race script and return (code, stdout, stderr) within timeout.

    Output goes to files, not pipes. Workers inherit the race's stdout and
    stderr, and with pipes a leftover worker kept them open, so reading to
    end of file never finished. On Windows subprocess.run(timeout=...) then
    reads again after the kill with no timeout, which hung CI for 30 minutes.
    Any worker still alive afterwards is killed by the PID it wrote.
    """
    out_path = root.parent / (root.name + ".stdout")
    err_path = root.parent / (root.name + ".stderr")
    with open(out_path, "w", encoding="utf-8") as out, open(err_path, "w", encoding="utf-8") as err:
        proc = subprocess.Popen(
            [sys.executable, str(script), str(rounds), str(root), kind],
            stdin=subprocess.DEVNULL,
            stdout=out,
            stderr=err,
            env=env,
        )
        try:
            code = proc.wait(timeout=timeout)
            note = ""
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=30)
            code = -1
            note = "\nrace harness timed out after %ss\n" % timeout
    for pid_file in root.glob("pid*"):
        try:
            pid = int(pid_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if _pid_alive(pid):
            _kill_pid(pid)
            note += "killed leftover race worker %d\n" % pid
    stdout = out_path.read_text(encoding="utf-8", errors="replace")
    stderr = err_path.read_text(encoding="utf-8", errors="replace") + note
    return code, stdout, stderr


def _pid_alive(pid: int) -> bool:
    if os.name == "posix":
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        try:
            done, _ = os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            done = 0
        return done == 0
    import ctypes

    k32 = ctypes.windll.kernel32
    handle = k32.OpenProcess(0x1000 | 0x00100000, False, pid)
    if not handle:
        return False
    try:
        return k32.WaitForSingleObject(handle, 0) == 0x102
    finally:
        k32.CloseHandle(handle)


def test_lock_race_fails_fast_and_leaves_no_workers_when_one_dies(tmp_path: Path) -> None:
    """A dead race worker must fail the race quickly, not hang CI.

    CI run 44232510371 (Windows) sat in this module until the 30 minute job
    timeout. When one worker died, the others waited forever for the next
    round while still holding the parent's stdout and stderr pipes, so the
    harness never saw end of file. The race must report the dead worker,
    stop within its own budget, and leave no worker running.
    """
    script = tmp_path / "race.py"
    script.write_text(_LOCK_RACE, encoding="utf-8")
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["LEASEGRID_RACE_FAULT"] = "crash:0:1"
    env["LEASEGRID_RACE_ROUND_S"] = "5"
    root = tmp_path / "faulty"
    root.mkdir()
    started = time.monotonic()
    code, out, err = _run_lock_race(script, 3, root, "none", env, timeout=60)
    took = time.monotonic() - started
    assert code != 0, out + err
    assert "injected worker crash k=0 t=1" in out + err
    assert took < 45, "race took %.0fs to report a dead worker" % took
    pids = [int(p.read_text()) for p in root.glob("pid*")]
    assert len(pids) == 6, pids
    deadline = time.monotonic() + 10
    while any(_pid_alive(pid) for pid in pids) and time.monotonic() < deadline:
        time.sleep(0.1)
    assert not [pid for pid in pids if _pid_alive(pid)], "race workers still running"


@pytest.mark.timeout(600)
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
        code, out, err = _run_lock_race(script, rounds, root, kind, env, timeout=180)
        assert code == 0, out + err
        line = out.strip().splitlines()[-1]
        assert line.startswith("multi=0 "), line
        if expect_zero:
            assert " zero=%d " % rounds in line, line
        else:
            assert " zero=0 " in line, line


def test_transient_permission_error_on_a_stale_lock_still_takes_it(tmp_path: Path, monkeypatch) -> None:
    """A Python open of the lock that fails once must not block a takeable lock.

    Windows reports a file a rival is deleting (delete pending) as access
    denied. A read probe before tryLock then said "could not read its lock
    file" while the stale lock was about to be gone, and its open handle could
    block the rival's delete. The probe now runs only after tryLock has failed
    and no PID could be read.
    """
    from leasegrid_sync.app import acquire_instance_lock, release_instance_lock

    home = tmp_path / "home"
    home.mkdir()
    lock = instance_lock_path(home)
    lock.write_bytes(b"")
    _age_lock(lock)
    real_open = open
    target = os.path.normcase(os.path.abspath(lock))
    calls = {"n": 0}

    def flaky(file, mode="r", *args, **kwargs):
        try:
            got = os.path.normcase(os.path.abspath(os.fspath(file)))
        except (TypeError, ValueError):
            got = ""
        if got == target and calls["n"] == 0:
            calls["n"] += 1
            raise PermissionError(13, "Permission denied", os.fspath(file))
        return real_open(file, mode, *args, **kwargs)

    monkeypatch.setattr("builtins.open", flaky)
    try:
        assert acquire_instance_lock(home) is True
    finally:
        release_instance_lock()
