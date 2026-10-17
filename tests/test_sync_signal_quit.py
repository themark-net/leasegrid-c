"""A quit signal takes the normal quit path and reaps a stubborn Tahoe child.

The stub ignores SIGTERM, so a handler that only returns — or a default
SIGTERM that kills Sync without stop() — leaves the stub alive and the
instance lock in place.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from leasegrid_sync.app import instance_lock_path

# The real module entry leaves _TEST_HOOKS false. This driver arms it, then calls main.
_HOOKED_MAIN = """\
import sys
import leasegrid_sync.app as appmod
appmod._TEST_HOOKS = True
from leasegrid_sync.cli import main
rc = main(sys.argv[1:])
raise SystemExit(0 if rc is None else int(rc))
"""

_STUB = """
import json
import os
import signal
import subprocess
import sys
import socketserver
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

signal.signal(signal.SIGTERM, signal.SIG_IGN)



class _QuickServer(ThreadingHTTPServer):
    # HTTPServer.server_bind calls socket.getfqdn(host). On macOS runners that
    # reverse lookup can stall for many seconds, past the start timeout.
    def server_bind(self):
        socketserver.TCPServer.server_bind(self)
        self.server_name = "127.0.0.1"
        self.server_port = self.server_address[1]


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps(
            {
                "introducers": {"statuses": ["connected"]},
                "servers": [{"nickname": "stub", "connection_status": "connected"}],
            }
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        return


def main():
    args = sys.argv[1:]
    if "run" not in args:
        sys.exit(0)
    nodedir = Path(args[args.index("run") + 1])
    server = _QuickServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    (nodedir / "node.url").write_text("http://127.0.0.1:%d/\\n" % port, encoding="utf-8")
    pidfile = os.environ.get("LEASEGRID_TEST_TAHOE_PIDFILE", "")
    if pidfile:
        Path(pidfile).write_text(str(os.getpid()), encoding="utf-8")
    child_pidfile = os.environ.get("LEASEGRID_TEST_TAHOE_CHILD_PID", "")
    if child_pidfile:
        # Same process group as this stub, so the app's group kill reaches it.
        # The test's finally kills only this pid, never a reused group.
        subprocess.Popen(
            [
                sys.executable,
                "-c",
                "import os, signal, sys, time\\n"
                "from pathlib import Path\\n"
                "try:\\n"
                "    signal.signal(signal.SIGTERM, signal.SIG_IGN)\\n"
                "except (OSError, ValueError):\\n"
                "    pass\\n"
                "Path(sys.argv[1]).write_text(str(os.getpid()), encoding='utf-8')\\n"
                "while True:\\n"
                "    time.sleep(60)\\n",
                child_pidfile,
            ]
        )
    server.serve_forever()


if __name__ == "__main__":
    main()
"""

_MF_STUB = """
import sys
sys.exit(1)
"""


def _signals():
    term = pytest.param(
        signal.SIGTERM,
        id="SIGTERM",
        marks=pytest.mark.skipif(
            sys.platform == "win32",
            reason="Windows SIGTERM is TerminateProcess and cannot run a handler",
        ),
    )
    interrupt = pytest.param(
        signal.SIGINT,
        id="SIGINT",
        marks=pytest.mark.skipif(
            sys.platform == "win32",
            reason=(
                "CTRL_C_EVENT is delivered to the whole console, not one child; "
                "SIGBREAK is the Windows interrupt this test can aim"
            ),
        ),
    )
    hangup = pytest.param(
        getattr(signal, "SIGHUP", signal.SIGTERM),
        id="SIGHUP",
        marks=pytest.mark.skipif(
            sys.platform == "win32",
            reason="Windows has no SIGHUP",
        ),
    )
    cases = [term, interrupt, hangup]
    if sys.platform == "win32":
        cases.append(pytest.param(signal.SIGBREAK, id="SIGBREAK"))
    return cases


def _executable(directory: Path, name: str, body: str) -> str:
    script = directory / (name + ".py")
    script.write_text(body, encoding="utf-8")
    if os.name == "nt":
        bat = directory / (name + ".bat")
        bat.write_text('@"%s" "%s" %%*\n' % (sys.executable, script), encoding="utf-8")
        return str(bat)
    bin_ = directory / name
    bin_.write_text("#!%s\n%s" % (sys.executable, body), encoding="utf-8")
    bin_.chmod(0o755)
    return str(bin_)


def _is_zombie(pid: int) -> bool:
    try:
        text = Path("/proc/%d/stat" % pid).read_text(encoding="utf-8")
    except OSError:
        return False
    tail = text.rsplit(")", 1)[-1].split()
    return bool(tail) and tail[0] == "Z"


def _reaped(pid: int) -> bool:
    if _is_zombie(pid):
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    except OSError:
        return True
    return False


# Pids the stubs wrote. The module fixture asserts every one is gone.
_STUB_PIDS: list[int] = []


def _remember(pid: int) -> None:
    if pid > 0 and pid not in _STUB_PIDS:
        _STUB_PIDS.append(pid)


def _pids_in(path: Path) -> list[int]:
    if not path.is_file():
        return []
    found: list[int] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.isdigit():
            found.append(int(line))
    return found


def _kill_pid(pid: int) -> None:
    """SIGKILL one recorded stub. Do not signal its process group."""
    if pid <= 0 or _reaped(pid):
        return
    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        return
    deadline = time.time() + 2
    while time.time() < deadline and not _reaped(pid):
        time.sleep(0.05)


@pytest.fixture(scope="module", autouse=True)
def _no_stub_left_after_the_module():
    """After every test in this file, each stub pid the tests recorded is dead."""
    yield
    alive = [pid for pid in _STUB_PIDS if not _reaped(pid)]
    try:
        assert alive == [], alive
    finally:
        for pid in alive:
            _kill_pid(pid)


def _wait_until(predicate, timeout: float) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return False


@pytest.mark.parametrize("sig", _signals())
def test_signal_quits_and_reaps_the_stub(tmp_path: Path, sig: int) -> None:
    home = tmp_path / "home"
    nodedir = home / "tahoe"
    nodedir.mkdir(parents=True)
    (nodedir / "tahoe.cfg").write_text("[node]\nnickname = stub\n", encoding="utf-8")
    bins = tmp_path / "bin"
    bins.mkdir()
    tahoe_bin = _executable(bins, "tahoe", _STUB)
    mf_bin = _executable(bins, "magic-folder", _MF_STUB)
    pidfile = tmp_path / "tahoe.pid"
    child_pidfile = tmp_path / "tahoe-child.pid"
    ready = tmp_path / "signal-ready"
    err_path = tmp_path / "app.err"
    lock = instance_lock_path(home)
    env = os.environ.copy()
    env["LEASEGRID_SYNC_HOME"] = str(home)
    env["LEASEGRID_TAHOE_NODEDIR"] = str(nodedir)
    env["LEASEGRID_TAHOE_BIN"] = tahoe_bin
    env["LEASEGRID_MAGIC_FOLDER_BIN"] = mf_bin
    env["LEASEGRID_TEST_TAHOE_PIDFILE"] = str(pidfile)
    env["LEASEGRID_TEST_TAHOE_CHILD_PID"] = str(child_pidfile)
    env["LEASEGRID_TEST_SIGNAL_READY"] = str(ready)
    env["QT_QPA_PLATFORM"] = "offscreen"
    err_f = err_path.open("w", encoding="utf-8")
    driver = tmp_path / "hooked_main.py"
    driver.write_text(_HOOKED_MAIN, encoding="utf-8")
    kwargs = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    proc = subprocess.Popen(
        [sys.executable, str(driver), "--offscreen", "--nodedir", str(nodedir)],
        stdout=subprocess.DEVNULL,
        stderr=err_f,
        env=env,
        **kwargs,
    )
    stub_pid = 0
    try:
        assert _wait_until(lambda: ready.is_file() or proc.poll() is not None, 25), (
            "app did not arm signal handlers: %s" % err_path.read_text(encoding="utf-8")
        )
        assert proc.poll() is None, err_path.read_text(encoding="utf-8")
        assert pidfile.is_file(), "stub Tahoe did not start"
        assert _wait_until(child_pidfile.is_file, 10), "stub grandchild did not start"
        stub_pid = int(pidfile.read_text(encoding="utf-8").strip())
        child_pid = int(child_pidfile.read_text(encoding="utf-8").strip())
        _remember(stub_pid)
        _remember(child_pid)
        assert stub_pid > 0 and child_pid > 0 and stub_pid != child_pid
        # os.kill(pid, SIGBREAK) on Windows is TerminateProcess(pid, 21), not a
        # console event. CTRL_BREAK_EVENT reaches the child's process group.
        send = sig
        if sys.platform == "win32" and sig == getattr(signal, "SIGBREAK", None):
            send = signal.CTRL_BREAK_EVENT
        os.kill(proc.pid, send)
        assert _wait_until(lambda: proc.poll() is not None, 20)
        assert proc.returncode == 0
        assert not lock.exists()
        assert _wait_until(lambda: _reaped(stub_pid), 5)
        assert _reaped(stub_pid)
        assert _wait_until(lambda: _reaped(child_pid), 5)
        assert _reaped(child_pid)
    finally:
        err_f.close()
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)
        for path in (pidfile, child_pidfile):
            for pid in _pids_in(path):
                _remember(pid)
                _kill_pid(pid)
