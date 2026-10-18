"""A second launch's --join is filled into the open window. It does not auto-join."""

from __future__ import annotations

import os
import signal
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest

PyQt5 = pytest.importorskip("PyQt5")

from leasegrid_sync.app import (  # noqa: E402
    ALREADY_RUNNING,
    HANDED_INVITE_DROPPED,
    MainWindow,
    hand_join_invite,
    instance_lock_path,
    join_endpoint,
)

# A wormhole-shaped fake. Not a secret, and the app must not write it to the log.
FAKE_INVITE = "7-guitarist-revenge"

# The real module entry leaves _TEST_HOOKS false. This driver arms it, then calls main.
_HOOKED_MAIN = """\
import sys
import leasegrid_sync.app as appmod
appmod._TEST_HOOKS = True
from leasegrid_sync.cli import main
rc = main(sys.argv[1:])
raise SystemExit(0 if rc is None else int(rc))
"""

_SECOND = r"""
import os
import sys

from PyQt5 import QtWidgets


def info(parent, title, text, *args, **kwargs):
    sys.stdout.write("MSGBOX:%s\n" % text)
    sys.stdout.flush()
    return QtWidgets.QMessageBox.Ok


QtWidgets.QMessageBox.information = staticmethod(info)

from leasegrid_sync.cli import main

rc = main(
    [
        "--join",
        os.environ["LEASEGRID_TEST_JOIN_TEXT"],
        "--nodedir",
        os.environ["LEASEGRID_TEST_NODEDIR"],
    ]
)
sys.stdout.write("EXIT:%s\n" % rc)
sys.stdout.flush()
raise SystemExit(0 if rc is None else int(rc))
"""

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


def _wait_until(predicate, timeout: float) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return False


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


def _env(home: Path, nodedir: Path, ready: Path, dump: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["LEASEGRID_SYNC_HOME"] = str(home)
    env["LEASEGRID_TEST_JOIN_READY"] = str(ready)
    env["LEASEGRID_TEST_INVITE_DUMP"] = str(dump)
    env["LEASEGRID_TEST_JOIN_TEXT"] = FAKE_INVITE
    env["LEASEGRID_TEST_NODEDIR"] = str(nodedir)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env.pop("LEASEGRID_TAHOE_BIN", None)
    env.pop("LEASEGRID_MAGIC_FOLDER_BIN", None)
    return env


def _reap(proc: subprocess.Popen) -> None:
    if proc.poll() is None:
        proc.kill()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


def _fields(dump: Path) -> dict[str, str]:
    found: dict[str, str] = {}
    for line in dump.read_text(encoding="utf-8").splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        found[key] = value
    return found


def _assert_log_has_no_invite(home: Path, err_path: Path) -> None:
    log = home / "logs" / "sync-ui.log"
    if log.is_file():
        assert FAKE_INVITE not in log.read_text(encoding="utf-8")
    if err_path.is_file():
        assert FAKE_INVITE not in err_path.read_text(encoding="utf-8", errors="replace")


def test_second_launch_fills_the_open_join_field(tmp_path: Path) -> None:
    home = tmp_path / "home"
    nodedir = tmp_path / "missing-node"
    ready = tmp_path / "join-ready"
    dump = tmp_path / "invite-dump"
    err_path = tmp_path / "app.err"
    env = _env(home, nodedir, ready, dump)
    err_f = err_path.open("w", encoding="utf-8")
    driver = tmp_path / "hooked_main.py"
    driver.write_text(_HOOKED_MAIN, encoding="utf-8")
    kwargs: dict = {}
    if sys.platform == "win32":
        # A new group so SIGBREAK reaches this process and not the pytest console.
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    app = subprocess.Popen(
        [sys.executable, str(driver), "--offscreen", "--nodedir", str(nodedir)],
        stdout=subprocess.DEVNULL,
        stderr=err_f,
        env=env,
        **kwargs,
    )
    second: subprocess.Popen[str] | None = None
    try:
        assert _wait_until(lambda: ready.is_file() or app.poll() is not None, 25), (
            "app did not listen: %s" % err_path.read_text(encoding="utf-8")
        )
        assert app.poll() is None, err_path.read_text(encoding="utf-8")
        second = subprocess.Popen(
            [sys.executable, "-c", _SECOND],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True,
        )
        assert _wait_until(lambda: second.poll() is not None, 15)
        out, err = second.communicate(timeout=5)
        assert second.returncode == 0, err
        assert "MSGBOX" not in out
        assert _wait_until(dump.is_file, 10), err_path.read_text(encoding="utf-8")
        fields = _fields(dump)
        assert fields.get("field") == FAKE_INVITE
        assert fields.get("joined") == "no"
        assert fields.get("ack") == "0"
        assert FAKE_INVITE not in out
        assert FAKE_INVITE not in err
        _assert_log_has_no_invite(home, err_path)
        os.kill(app.pid, signal.SIGTERM if sys.platform != "win32" else signal.CTRL_BREAK_EVENT)
        assert _wait_until(lambda: app.poll() is not None, 15)
        assert app.returncode == 0
        assert not instance_lock_path(home).exists()
    finally:
        err_f.close()
        if second is not None:
            _reap(second)
        _reap(app)
        if sys.platform != "win32":
            try:
                endpoint = join_endpoint(home)
                if endpoint:
                    os.unlink(endpoint)
            except OSError:
                pass


def test_stale_socket_keeps_the_already_running_message(tmp_path: Path) -> None:
    """A held lock with nothing listening still shows today's already-running note.

    On Windows there is no unix socket file. A live lock and a refused connect
    is the stale case there. On POSIX a leftover regular file stands in for the
    dead socket as well.
    """
    home = tmp_path / "home"
    home.mkdir()
    nodedir = tmp_path / "missing-node"
    stale = None
    if sys.platform != "win32":
        endpoint = join_endpoint(home)
        assert endpoint
        parent = Path(endpoint).parent
        parent.mkdir(parents=True, exist_ok=True)
        os.chmod(parent, 0o700)
        stale = Path(endpoint)
        stale.write_text("not-a-socket\n", encoding="utf-8")
    holder = _hold(home)
    env = _env(home, nodedir, tmp_path / "unused-ready", tmp_path / "unused-dump")
    second: subprocess.Popen[str] | None = None
    try:
        second = subprocess.Popen(
            [sys.executable, "-c", _SECOND],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True,
        )
        assert _wait_until(lambda: second.poll() is not None, 15)
        out, err = second.communicate(timeout=5)
        assert second.returncode == 0, err
        assert "MSGBOX:%s" % ALREADY_RUNNING in out
        assert FAKE_INVITE not in out
        assert not nodedir.exists()
        if stale is not None:
            assert FAKE_INVITE not in stale.read_text(encoding="utf-8")
    finally:
        if second is not None:
            _reap(second)
        _release(holder)
        if stale is not None:
            try:
                stale.unlink()
            except OSError:
                pass


def test_already_joined_window_drops_the_handed_invite(tmp_path: Path) -> None:
    home = tmp_path / "home"
    window = MainWindow(nodedir=tmp_path / "missing-node", home=home, autoload=False)
    try:
        window._joined = True
        window.receive_handed_invite(FAKE_INVITE)
        assert window.folder_error.text() == HANDED_INVITE_DROPPED
        assert FAKE_INVITE not in window.folder_error.text()
        assert window.invite_edit.text() == ""
        assert window.threat_ack.isChecked() is False
        log = home / "logs" / "sync-ui.log"
        if log.is_file():
            assert FAKE_INVITE not in log.read_text(encoding="utf-8")
    finally:
        window.poll.stop()
        window.win.hide()


def test_handed_invite_is_not_dumped_when_hooks_are_off(tmp_path: Path, monkeypatch) -> None:
    """The invite field still fills. The dump file is a test hook."""
    import leasegrid_sync.app as appmod

    appmod._TEST_HOOKS = False
    dump = tmp_path / "invite-dump"
    monkeypatch.setenv("LEASEGRID_TEST_INVITE_DUMP", str(dump))
    home = tmp_path / "home"
    window = MainWindow(nodedir=tmp_path / "missing-node", home=home, autoload=False)
    try:
        window.receive_handed_invite(FAKE_INVITE)
        assert window.invite_edit.text() == FAKE_INVITE
        assert not dump.exists()
    finally:
        appmod._TEST_HOOKS = False
        window.poll.stop()
        window.win.hide()


def test_real_entry_does_not_dump_an_invite_from_the_env(tmp_path: Path, monkeypatch) -> None:
    """python -m leasegrid_sync never arms the hooks. The env var alone writes nothing."""
    home = tmp_path / "home"
    nodedir = tmp_path / "missing-node"
    dump = tmp_path / "invite-dump"
    ready = tmp_path / "join-ready"
    err_path = tmp_path / "app.err"
    monkeypatch.setenv("LEASEGRID_SYNC_HOME", str(home))
    env = os.environ.copy()
    env["LEASEGRID_SYNC_HOME"] = str(home)
    env["LEASEGRID_TEST_INVITE_DUMP"] = str(dump)
    env["LEASEGRID_TEST_JOIN_READY"] = str(ready)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env.pop("LEASEGRID_TAHOE_BIN", None)
    env.pop("LEASEGRID_MAGIC_FOLDER_BIN", None)
    err_f = err_path.open("w", encoding="utf-8")
    kwargs: dict = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    proc = subprocess.Popen(
        [sys.executable, "-m", "leasegrid_sync", "--offscreen", "--nodedir", str(nodedir)],
        stdout=subprocess.DEVNULL,
        stderr=err_f,
        env=env,
        **kwargs,
    )

    def listening() -> bool:
        if proc.poll() is not None:
            return True
        if not instance_lock_path(home).is_file():
            return False
        if sys.platform == "win32":
            return True
        endpoint = join_endpoint(home)
        if not endpoint:
            return False
        try:
            mode = os.lstat(endpoint).st_mode
        except OSError:
            return False
        return stat.S_ISSOCK(mode)

    try:
        assert _wait_until(listening, 25), err_path.read_text(encoding="utf-8")
        assert proc.poll() is None, err_path.read_text(encoding="utf-8")
        sent = False
        deadline = time.time() + 10
        while time.time() < deadline and proc.poll() is None:
            if hand_join_invite(FAKE_INVITE) == "sent":
                sent = True
                break
            time.sleep(0.05)
        assert sent, err_path.read_text(encoding="utf-8")
        deadline = time.time() + 1
        while time.time() < deadline and not dump.exists():
            time.sleep(0.05)
        assert not dump.exists()
        assert not ready.exists()
        log = home / "logs" / "sync-ui.log"
        if log.is_file():
            assert FAKE_INVITE not in log.read_text(encoding="utf-8")
    finally:
        err_f.close()
        _reap(proc)
