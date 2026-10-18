"""The --join handoff must not send an invite to a squatter.

POSIX checks are skipped on Windows because there is no AF_UNIX socket file
there. The pipe ACL is covered by test_join_server_is_user_only, which runs
on every platform.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PyQt5 = pytest.importorskip("PyQt5")

import leasegrid_sync.app as appmod  # noqa: E402
from leasegrid_sync.app import (  # noqa: E402
    MainWindow,
    _close_join_server,
    _start_join_server,
    hand_join_invite,
    join_endpoint,
    join_server_name,
)

# A wormhole-shaped fake. Not a secret.
FAKE_INVITE = "7-guitarist-revenge"

_POSIX_ONLY = pytest.mark.skipif(
    sys.platform == "win32",
    reason="AF_UNIX owner, mode, and socket-type checks are POSIX-only",
)

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


class _Listener:
    """AF_UNIX listener with a short accept timeout so a miss fails the assertion."""

    def __init__(self, path: str) -> None:
        self.path = path
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.bind(path)
        self.sock.listen(1)
        self.sock.settimeout(0.4)

    def received(self) -> bytes:
        try:
            conn, _addr = self.sock.accept()
        except socket.timeout:
            return b""
        conn.settimeout(0.4)
        try:
            chunks = []
            while True:
                try:
                    chunk = conn.recv(4096)
                except socket.timeout:
                    break
                if not chunk:
                    break
                chunks.append(chunk)
            return b"".join(chunks)
        finally:
            conn.close()

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass
        try:
            os.unlink(self.path)
        except OSError:
            pass


def _short_home() -> tuple[Path, Path]:
    """A home whose <home>/run/<name> path fits in the AF_UNIX budget.

    The uid is then not part of the path, so a fake getuid() only affects
    the owner check.
    """
    root = Path(tempfile.mkdtemp(prefix="lgj", dir="/tmp" if Path("/tmp").is_dir() else None))
    home = root / "h"
    home.mkdir()
    os.chmod(home, 0o700)
    if sys.platform != "win32":
        endpoint = join_endpoint(home)
        primary = os.path.join(str(home.resolve()), "run", join_server_name(home))
        if endpoint != primary:
            shutil.rmtree(root, ignore_errors=True)
            raise AssertionError("short home did not use <home>/run: %s" % endpoint)
    return root, home


def _prepare_private(home: Path, mode: int) -> str:
    endpoint = join_endpoint(home)
    assert endpoint
    parent = Path(endpoint).parent
    parent.mkdir(parents=True)
    os.chmod(parent, mode)
    return endpoint


def _spy_connect(monkeypatch):
    connects: list = []
    real = socket.socket

    class Spy(real):  # type: ignore[misc, valid-type]
        def connect(self, address):
            connects.append(address)
            return super().connect(address)

    monkeypatch.setattr(appmod.socket, "socket", Spy)
    return connects


def _spy_run(monkeypatch):
    runs: list = []
    real_run = subprocess.run

    def spy(*args, **kwargs):
        runs.append(args[0] if args else kwargs.get("args"))
        return real_run(*args, **kwargs)

    monkeypatch.setattr(appmod.subprocess, "run", spy)
    return runs


@_POSIX_ONLY
def test_old_path_squatter_receives_nothing_when_the_lock_is_free(monkeypatch) -> None:
    root, home = _short_home()
    monkeypatch.setenv("LEASEGRID_SYNC_HOME", str(home))
    old = Path(tempfile.gettempdir()) / join_server_name(home)
    if old.is_symlink() or (old.exists() and not old.is_dir()):
        old.unlink()
    listener = _Listener(str(old))
    try:
        assert hand_join_invite(FAKE_INVITE) == "free"
        assert listener.received() == b""
        log = home / "logs" / "sync-ui.log"
        if log.is_file():
            assert FAKE_INVITE not in log.read_text(encoding="utf-8")
    finally:
        listener.close()
        shutil.rmtree(root, ignore_errors=True)


def test_free_lock_does_not_connect(monkeypatch) -> None:
    root, home = _short_home()
    monkeypatch.setenv("LEASEGRID_SYNC_HOME", str(home))
    listener = None
    if sys.platform != "win32":
        endpoint = _prepare_private(home, 0o700)
        listener = _Listener(endpoint)
    connects = _spy_connect(monkeypatch)
    runs = _spy_run(monkeypatch)
    try:
        assert hand_join_invite(FAKE_INVITE) == "free"
        assert connects == []
        assert runs == []
        if listener is not None:
            assert listener.received() == b""
    finally:
        if listener is not None:
            listener.close()
        shutil.rmtree(root, ignore_errors=True)


@_POSIX_ONLY
def test_shared_directory_receives_nothing(monkeypatch) -> None:
    root, home = _short_home()
    monkeypatch.setenv("LEASEGRID_SYNC_HOME", str(home))
    endpoint = _prepare_private(home, 0o755)
    parent = Path(endpoint).parent
    listener = _Listener(endpoint)
    holder = _hold(home)
    try:
        assert hand_join_invite(FAKE_INVITE) == "busy"
        assert listener.received() == b""
        assert stat.S_IMODE(os.lstat(parent).st_mode) == 0o755
        log = home / "logs" / "sync-ui.log"
        assert log.is_file()
        assert FAKE_INVITE not in log.read_text(encoding="utf-8")
    finally:
        listener.close()
        _release(holder)
        shutil.rmtree(root, ignore_errors=True)


@_POSIX_ONLY
def test_server_refuses_a_shared_directory_and_the_window_stays_up(monkeypatch) -> None:
    root, home = _short_home()
    monkeypatch.setenv("LEASEGRID_SYNC_HOME", str(home))
    endpoint = _prepare_private(home, 0o755)
    parent = Path(endpoint).parent
    window = MainWindow(nodedir=root / "missing-node", home=home, autoload=False)
    try:
        _start_join_server(window)
        assert getattr(window, "_join_server", None) is None
        assert stat.S_IMODE(os.lstat(parent).st_mode) == 0o755
        assert window.win.windowTitle()
    finally:
        _close_join_server(window)
        window.poll.stop()
        window.win.hide()
        shutil.rmtree(root, ignore_errors=True)


@_POSIX_ONLY
def test_symlinked_directory_receives_nothing(monkeypatch) -> None:
    root, home = _short_home()
    monkeypatch.setenv("LEASEGRID_SYNC_HOME", str(home))
    endpoint = join_endpoint(home)
    assert endpoint
    real = root / "real"
    real.mkdir()
    os.chmod(real, 0o700)
    parent = Path(endpoint).parent
    parent.symlink_to(real)
    listener = _Listener(endpoint)
    holder = _hold(home)
    try:
        assert hand_join_invite(FAKE_INVITE) == "busy"
        assert listener.received() == b""
        assert stat.S_ISLNK(os.lstat(parent).st_mode)
    finally:
        listener.close()
        _release(holder)
        shutil.rmtree(root, ignore_errors=True)


def _stat_with_uid(st: os.stat_result, uid: int) -> os.stat_result:
    """Same file, different owner. A foreign-uid socket needs root to chown."""
    return os.stat_result(
        (
            st.st_mode,
            st.st_ino,
            st.st_dev,
            st.st_nlink,
            uid,
            st.st_gid,
            st.st_size,
            st.st_atime,
            st.st_mtime,
            st.st_ctime,
        )
    )


@_POSIX_ONLY
def test_socket_with_a_foreign_uid_is_not_sent(monkeypatch) -> None:
    """Refuse when the socket owner is not us, and send nothing.

    The directory lstat stays real. Only this socket path reports another
    uid: a socket owned by someone else cannot be planted without root.
    """
    root, home = _short_home()
    monkeypatch.setenv("LEASEGRID_SYNC_HOME", str(home))
    endpoint = _prepare_private(home, 0o700)
    listener = _Listener(endpoint)
    holder = _hold(home)
    real_lstat = os.lstat
    real_stat = os.stat

    def _foreign(follow, path, *args, **kwargs):
        st = follow(path, *args, **kwargs)
        # dir_fd lookups are shutil and the like, not the socket-path check.
        if args or kwargs:
            return st
        if os.path.abspath(path) == os.path.abspath(endpoint):
            return _stat_with_uid(st, os.getuid() + 1)
        return st

    monkeypatch.setattr(appmod.os, "lstat", lambda path, *a, **k: _foreign(real_lstat, path, *a, **k))
    monkeypatch.setattr(appmod.os, "stat", lambda path, *a, **k: _foreign(real_stat, path, *a, **k))
    try:
        assert hand_join_invite(FAKE_INVITE) == "busy"
        assert listener.received() == b""
        parent = os.lstat(os.path.dirname(endpoint))
        assert parent.st_uid == os.getuid()
    finally:
        listener.close()
        _release(holder)
        shutil.rmtree(root, ignore_errors=True)


@_POSIX_ONLY
def test_wrong_owner_receives_nothing(monkeypatch) -> None:
    root, home = _short_home()
    monkeypatch.setenv("LEASEGRID_SYNC_HOME", str(home))
    endpoint = _prepare_private(home, 0o700)
    listener = _Listener(endpoint)
    holder = _hold(home)
    real_uid = os.getuid()
    monkeypatch.setattr(appmod.os, "getuid", lambda: real_uid + 1)
    try:
        assert hand_join_invite(FAKE_INVITE) == "busy"
        assert listener.received() == b""
    finally:
        listener.close()
        _release(holder)
        shutil.rmtree(root, ignore_errors=True)


@_POSIX_ONLY
def test_server_keeps_a_planted_file_and_does_not_listen(monkeypatch) -> None:
    """A non-socket at the endpoint stays. The server does not listen there."""
    root, home = _short_home()
    monkeypatch.setenv("LEASEGRID_SYNC_HOME", str(home))
    endpoint = _prepare_private(home, 0o700)
    planted = "planted-not-a-socket\n"
    Path(endpoint).write_text(planted, encoding="utf-8")
    window = MainWindow(nodedir=root / "missing-node", home=home, autoload=False)
    try:
        _start_join_server(window)
        assert getattr(window, "_join_server", None) is None
        assert Path(endpoint).is_file()
        assert Path(endpoint).read_text(encoding="utf-8") == planted
    finally:
        _close_join_server(window)
        window.poll.stop()
        window.win.hide()
        shutil.rmtree(root, ignore_errors=True)


@_POSIX_ONLY
@pytest.mark.parametrize("kind", ["file", "fifo"])
def test_non_socket_receives_nothing(monkeypatch, kind: str) -> None:
    root, home = _short_home()
    monkeypatch.setenv("LEASEGRID_SYNC_HOME", str(home))
    endpoint = _prepare_private(home, 0o700)
    fd = None
    if kind == "file":
        Path(endpoint).write_text("not-a-socket\n", encoding="utf-8")
    else:
        os.mkfifo(endpoint)
        fd = os.open(endpoint, os.O_RDONLY | os.O_NONBLOCK)
    holder = _hold(home)
    connects = _spy_connect(monkeypatch)
    try:
        assert hand_join_invite(FAKE_INVITE) == "busy"
        assert connects == []
        if kind == "file":
            assert FAKE_INVITE not in Path(endpoint).read_text(encoding="utf-8")
        else:
            assert fd is not None
            try:
                got = os.read(fd, 4096)
            except BlockingIOError:
                got = b""
            assert got == b""
    finally:
        if fd is not None:
            os.close(fd)
        _release(holder)
        shutil.rmtree(root, ignore_errors=True)


@_POSIX_ONLY
def test_long_home_still_hands_off(monkeypatch, tmp_path: Path) -> None:
    deep = tmp_path
    for _ in range(8):
        deep = deep / ("n" * 30)
    home = deep / "home"
    home.mkdir(parents=True)
    name = join_server_name(home)
    primary = os.path.join(str(home.resolve()), "run", name)
    assert len(os.fsencode(primary)) >= 100
    digest = hashlib.sha256(str(home.resolve()).encode("utf-8")).hexdigest()
    uid_part = "leasegrid-sync-%d" % os.getuid()
    base = Path("/tmp") if Path("/tmp").is_dir() else Path(tempfile.gettempdir())
    token = "lgf%s" % os.getpid()
    tmp = None
    for extra in range(0, 80):
        candidate = base / (token + ("t" * extra))
        full = candidate / uid_part / name
        short = candidate / uid_part / digest[:16]
        if len(os.fsencode(str(full))) >= 100 and len(os.fsencode(str(short))) < 100:
            tmp = candidate
            break
    assert tmp is not None
    tmp.mkdir()
    xdg = base / (("lgx%s" % os.getpid()) + ("x" * 40))
    xdg.mkdir()
    xdg_path = xdg / "leasegrid-sync" / name
    assert len(os.fsencode(str(xdg_path))) >= 100
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(xdg))
    monkeypatch.setenv("TMPDIR", str(tmp))
    monkeypatch.setenv("LEASEGRID_SYNC_HOME", str(home))
    endpoint = join_endpoint(home)
    holder = _hold(home)
    window = MainWindow(nodedir=tmp_path / "missing-node", home=home, autoload=False)
    try:
        assert endpoint
        assert len(os.fsencode(endpoint)) < 100
        assert Path(endpoint).parent.name == uid_part
        _start_join_server(window)
        assert getattr(window, "_join_server", None) is not None
        result = hand_join_invite(FAKE_INVITE)
        for _ in range(30):
            window.app.processEvents()
            if window.invite_edit.text() == FAKE_INVITE:
                break
            time.sleep(0.05)
        assert result == "sent"
        assert window.invite_edit.text() == FAKE_INVITE
        assert window._joined is False
    finally:
        _close_join_server(window)
        window.poll.stop()
        window.win.hide()
        _release(holder)
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.rmtree(xdg, ignore_errors=True)


def test_join_server_is_user_only(monkeypatch) -> None:
    root, home = _short_home()
    monkeypatch.setenv("LEASEGRID_SYNC_HOME", str(home))
    window = MainWindow(nodedir=root / "missing-node", home=home, autoload=False)
    try:
        _start_join_server(window)
        server = getattr(window, "_join_server", None)
        assert server is not None
        from PyQt5.QtNetwork import QLocalServer

        assert int(server.socketOptions()) & int(QLocalServer.UserAccessOption)
    finally:
        _close_join_server(window)
        window.poll.stop()
        window.win.hide()
        shutil.rmtree(root, ignore_errors=True)
