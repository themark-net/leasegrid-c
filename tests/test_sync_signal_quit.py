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
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

signal.signal(signal.SIGTERM, signal.SIG_IGN)


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
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    (nodedir / "node.url").write_text("http://127.0.0.1:%d/\\n" % port, encoding="utf-8")
    pidfile = os.environ.get("LEASEGRID_TEST_TAHOE_PIDFILE", "")
    if pidfile:
        Path(pidfile).write_text(str(os.getpid()), encoding="utf-8")
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
    ready = tmp_path / "signal-ready"
    err_path = tmp_path / "app.err"
    lock = instance_lock_path(home)
    env = os.environ.copy()
    env["LEASEGRID_SYNC_HOME"] = str(home)
    env["LEASEGRID_TAHOE_NODEDIR"] = str(nodedir)
    env["LEASEGRID_TAHOE_BIN"] = tahoe_bin
    env["LEASEGRID_MAGIC_FOLDER_BIN"] = mf_bin
    env["LEASEGRID_TEST_TAHOE_PIDFILE"] = str(pidfile)
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
        stub_pid = int(pidfile.read_text(encoding="utf-8").strip())
        assert stub_pid > 0
        os.kill(proc.pid, sig)
        assert _wait_until(lambda: proc.poll() is not None, 20)
        assert proc.returncode == 0
        assert not lock.exists()
        assert _wait_until(lambda: _reaped(stub_pid), 5)
        assert _reaped(stub_pid)
    finally:
        err_f.close()
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)
        if stub_pid and not _reaped(stub_pid):
            try:
                os.kill(stub_pid, signal.SIGKILL)
            except OSError:
                pass
            try:
                os.waitpid(stub_pid, os.WNOHANG)
            except OSError:
                pass
