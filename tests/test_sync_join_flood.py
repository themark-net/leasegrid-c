"""A burst of handoff connections must not kill the open window.

About 354 rapid connections segfaulted the process. The cap is 8 pending
sockets. Windows uses fewer connects because a named-pipe burst is slower
than AF_UNIX, and 80 is still ten times the cap.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

from leasegrid_sync.app import _JOIN_PENDING_MAX, join_endpoint

# A wormhole-shaped fake. Not a secret, and the app must not write it to the log.
FAKE_INVITE = "7-guitarist-revenge"
# Named-pipe connect on Windows is slower than an AF_UNIX burst.
FLOOD_COUNT = 80 if sys.platform == "win32" else 400

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

from leasegrid_sync.cli import main

rc = main(
    [
        "--join",
        os.environ["LEASEGRID_TEST_JOIN_TEXT"],
        "--nodedir",
        os.environ["LEASEGRID_TEST_NODEDIR"],
    ]
)
raise SystemExit(0 if rc is None else int(rc))
"""

_WIN_FLOOD = r"""
import sys
import time

from PyQt5.QtCore import QCoreApplication
from PyQt5.QtNetwork import QLocalSocket

app = QCoreApplication([])
name = sys.argv[1]
count = int(sys.argv[2])
held = []
for _ in range(count):
    sock = QLocalSocket()
    sock.connectToServer(name)
    if sock.waitForConnected(200):
        held.append(sock)
    else:
        sock.abort()
for _ in range(10):
    app.processEvents()
    time.sleep(0.05)
alive = sum(1 for sock in held if sock.state() == QLocalSocket.ConnectedState)
for sock in held:
    sock.abort()
print(alive)
"""


def _wait_until(predicate, timeout: float) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return False


def _still_open(sock: socket.socket) -> bool:
    sock.setblocking(False)
    try:
        data = sock.recv(1)
    except BlockingIOError:
        return True
    except OSError:
        return False
    return bool(data)


def _burst(endpoint: str, count: int) -> int:
    """Hold ``count`` connections open, then return how many the server kept.

    A sequential connect-and-close never has more than one socket pending, so
    the cap is invisible that way. These stay open together.
    """
    if sys.platform == "win32":
        proc = subprocess.run(
            [sys.executable, "-c", _WIN_FLOOD, endpoint, str(count)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=60,
            check=False,
        )
        assert proc.returncode == 0, proc.stderr
        return int(proc.stdout.strip() or "0")
    held: list[socket.socket] = []
    try:
        for _ in range(count):
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(0.5)
            try:
                sock.connect(endpoint)
            except OSError:
                sock.close()
                continue
            held.append(sock)
        time.sleep(0.3)
        return sum(1 for sock in held if _still_open(sock))
    finally:
        for sock in held:
            sock.close()


def test_join_flood_leaves_the_app_alive_for_a_later_handoff(tmp_path: Path) -> None:
    home = tmp_path / "home"
    nodedir = tmp_path / "missing-node"
    ready = tmp_path / "join-ready"
    dump = tmp_path / "invite-dump"
    err_path = tmp_path / "app.err"
    env = os.environ.copy()
    env["LEASEGRID_SYNC_HOME"] = str(home)
    env["LEASEGRID_TEST_JOIN_READY"] = str(ready)
    env["LEASEGRID_TEST_INVITE_DUMP"] = str(dump)
    env["LEASEGRID_TEST_JOIN_TEXT"] = FAKE_INVITE
    env["LEASEGRID_TEST_NODEDIR"] = str(nodedir)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env.pop("LEASEGRID_TAHOE_BIN", None)
    env.pop("LEASEGRID_MAGIC_FOLDER_BIN", None)
    err_f = err_path.open("w", encoding="utf-8")
    driver = tmp_path / "hooked_main.py"
    driver.write_text(_HOOKED_MAIN, encoding="utf-8")
    kwargs: dict = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    app = subprocess.Popen(
        [sys.executable, str(driver), "--offscreen", "--nodedir", str(nodedir)],
        stdout=subprocess.DEVNULL,
        stderr=err_f,
        env=env,
        **kwargs,
    )
    second: subprocess.Popen | None = None
    try:
        assert _wait_until(lambda: ready.is_file() or app.poll() is not None, 25), (
            err_path.read_text(encoding="utf-8")
        )
        assert app.poll() is None, err_path.read_text(encoding="utf-8")
        endpoint = join_endpoint(home)
        assert endpoint
        alive = _burst(endpoint, FLOOD_COUNT)
        assert app.poll() is None, err_path.read_text(encoding="utf-8")
        assert 1 <= alive <= _JOIN_PENDING_MAX, alive
        second = subprocess.Popen(
            [sys.executable, "-c", _SECOND],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            env=env,
        )
        assert _wait_until(lambda: second.poll() is not None, 20)
        err = second.stderr.read() if second.stderr is not None else b""
        assert second.returncode == 0, err
        assert _wait_until(dump.is_file, 10), err_path.read_text(encoding="utf-8")
        text = dump.read_text(encoding="utf-8")
        assert "field=%s" % FAKE_INVITE in text
        assert app.poll() is None
        log = home / "logs" / "sync-ui.log"
        if log.is_file():
            assert FAKE_INVITE not in log.read_text(encoding="utf-8")
    finally:
        err_f.close()
        if second is not None and second.poll() is None:
            second.kill()
            second.wait(timeout=5)
        if app.poll() is None:
            app.kill()
            app.wait(timeout=5)
