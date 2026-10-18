"""An idle join socket with no newline is closed, and a later handoff still works.

The server starts a 2s read timer on each accepted socket. This drives a real
offscreen process. The invite is a fake.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

from leasegrid_sync.app import instance_lock_path, join_endpoint

PARTIAL = b"7-partial-invite"
VALID = "7-guitarist-revenge"

_HOOKED_MAIN = """\
import sys
import leasegrid_sync.app as appmod
appmod._TEST_HOOKS = True
from leasegrid_sync.cli import main
rc = main(sys.argv[1:])
raise SystemExit(0 if rc is None else int(rc))
"""

_WIN_PARTIAL = r"""
import sys
import time
from PyQt5.QtCore import QCoreApplication
from PyQt5.QtNetwork import QLocalSocket

app = QCoreApplication([])
name = sys.argv[1]
sock = QLocalSocket()
sock.connectToServer(name)
if not sock.waitForConnected(5000):
    raise SystemExit(2)
sock.write(sys.stdin.buffer.read())
if not sock.waitForBytesWritten(2000):
    raise SystemExit(2)
deadline = time.time() + 5
while time.time() < deadline:
    app.processEvents()
    if sock.state() == QLocalSocket.UnconnectedState:
        raise SystemExit(0)
    time.sleep(0.05)
raise SystemExit(1)
"""

_WIN_SEND = r"""
import sys
from PyQt5.QtCore import QCoreApplication
from PyQt5.QtNetwork import QLocalSocket

app = QCoreApplication([])
name = sys.argv[1]
payload = sys.stdin.buffer.read()
sock = QLocalSocket()
sock.connectToServer(name)
if not sock.waitForConnected(2000):
    raise SystemExit(2)
sock.write(payload)
if not sock.waitForBytesWritten(2000):
    raise SystemExit(2)
sock.abort()
raise SystemExit(0)
"""


def _wait_until(predicate, timeout: float) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return False


def _launch(tmp_path: Path):
    home = tmp_path / "home"
    nodedir = tmp_path / "missing-node"
    ready = tmp_path / "join-ready"
    dump = tmp_path / "invite-dump"
    err_path = tmp_path / "app.err"
    env = os.environ.copy()
    env["LEASEGRID_SYNC_HOME"] = str(home)
    env["LEASEGRID_TEST_JOIN_READY"] = str(ready)
    env["LEASEGRID_TEST_INVITE_DUMP"] = str(dump)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.pop("LEASEGRID_TAHOE_BIN", None)
    env.pop("LEASEGRID_MAGIC_FOLDER_BIN", None)
    err_f = err_path.open("w", encoding="utf-8")
    driver = tmp_path / "hooked_main.py"
    driver.write_text(_HOOKED_MAIN, encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, str(driver), "--offscreen", "--nodedir", str(nodedir)],
        stdout=subprocess.DEVNULL,
        stderr=err_f,
        env=env,
    )
    return proc, home, dump, err_path, err_f, ready


def _stop(proc: subprocess.Popen, err_f) -> None:
    if not err_f.closed:
        err_f.close()
    if proc.poll() is None:
        proc.kill()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass


def _send_valid(endpoint: str) -> None:
    payload = (VALID + "\n").encode("utf-8")
    if sys.platform == "win32":
        proc = subprocess.run(
            [sys.executable, "-c", _WIN_SEND, endpoint],
            input=payload,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
            check=False,
        )
        assert proc.returncode == 0, proc.stderr
        return
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(2)
    try:
        sock.connect(endpoint)
        sock.sendall(payload)
    finally:
        sock.close()


def _partial_is_closed(endpoint: str) -> None:
    """Keep a partial line open until the server closes it."""
    if sys.platform == "win32":
        proc = subprocess.run(
            [sys.executable, "-c", _WIN_PARTIAL, endpoint],
            input=PARTIAL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=15,
            check=False,
        )
        assert proc.returncode == 0, proc.stderr
        return
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(5)
    try:
        sock.connect(endpoint)
        sock.sendall(PARTIAL)
        started = time.time()
        try:
            data = sock.recv(64)
        except socket.timeout:
            data = b"still-open"
        elapsed = time.time() - started
    finally:
        sock.close()
    assert data == b"", data
    assert elapsed < 4.0, elapsed


def test_idle_partial_line_is_closed_and_a_later_handoff_works(tmp_path: Path) -> None:
    proc, home, dump, err_path, err_f, ready = _launch(tmp_path)
    try:
        assert _wait_until(lambda: ready.is_file() or proc.poll() is not None, 25), (
            err_path.read_text(encoding="utf-8") if err_path.is_file() else ""
        )
        assert proc.poll() is None, err_path.read_text(encoding="utf-8")
        endpoint = join_endpoint(home)
        assert endpoint
        if sys.platform != "win32":
            assert _wait_until(lambda: Path(endpoint).exists(), 5), endpoint
        _partial_is_closed(endpoint)
        assert proc.poll() is None, err_path.read_text(encoding="utf-8")
        _send_valid(endpoint)

        def _field() -> bool:
            try:
                return ("field=%s\n" % VALID) in dump.read_text(encoding="utf-8")
            except OSError:
                return False

        assert _wait_until(_field, 10), dump.read_text(encoding="utf-8") if dump.is_file() else ""
        text = dump.read_text(encoding="utf-8")
        assert PARTIAL.decode("ascii") not in text
        assert instance_lock_path(home).is_file()
    finally:
        _stop(proc, err_f)
