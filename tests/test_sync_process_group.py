"""stop() kills the daemon and a grandchild that ignores SIGTERM.

Killing only the leader leaves the grandchild. The daemon is started through
TahoeClient.start, which is the real popen_hidden path.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

from unittest.mock import patch

import pytest
from tests.proc_util import kill_pid, pid_alive

from leasegrid_sync.backend import TahoeClient, popen_hidden, reap_child

_STUB = r"""
import json
import os
import signal
import subprocess
import sys
import time
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


def grandchild() -> None:
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    Path(sys.argv[2]).write_text(str(os.getpid()), encoding="utf-8")
    time.sleep(120)


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "grandchild":
        grandchild()
        return
    args = sys.argv[1:]
    if "run" not in args:
        sys.exit(0)
    nodedir = Path(args[args.index("run") + 1])
    child_file = os.environ.get("LEASEGRID_TEST_CHILD_PID", "")
    if child_file:
        subprocess.Popen([sys.executable, sys.argv[0], "grandchild", child_file])
        deadline = time.time() + 5
        while time.time() < deadline and not Path(child_file).is_file():
            time.sleep(0.02)
    server = _QuickServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    (nodedir / "node.url").write_text("http://127.0.0.1:%d/\n" % port, encoding="utf-8")
    leader_file = os.environ.get("LEASEGRID_TEST_LEADER_PID", "")
    if leader_file:
        Path(leader_file).write_text(str(os.getpid()), encoding="utf-8")
    server.serve_forever()


if __name__ == "__main__":
    main()
"""


def _executable(directory: Path, body: str) -> str:
    script = directory / "tahoe.py"
    script.write_text(body, encoding="utf-8")
    if os.name == "nt":
        bat = directory / "tahoe.bat"
        bat.write_text('@"%s" "%s" %%*\n' % (sys.executable, script), encoding="utf-8")
        return str(bat)
    bin_ = directory / "tahoe"
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
    # Not os.kill(pid, 0): on Windows that terminates the process.
    return pid > 0 and not pid_alive(pid)


def _wait_reaped(pid: int, timeout: float = 5.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _reaped(pid):
            return True
        time.sleep(0.05)
    return False


_STUB_PIDS: list[int] = []


def _remember(pid: int) -> None:
    if pid > 0 and pid not in _STUB_PIDS:
        _STUB_PIDS.append(pid)


@pytest.fixture(scope="module", autouse=True)
def _no_stub_left_after_the_module():
    """Stub pids this file recorded, including the grandchild, are dead."""
    yield
    alive = [pid for pid in _STUB_PIDS if not _reaped(pid)]
    assert alive == [], alive


def test_stop_kills_daemon_and_grandchild(tmp_path: Path) -> None:
    home = tmp_path / "home"
    nodedir = home / "tahoe"
    nodedir.mkdir(parents=True)
    (nodedir / "tahoe.cfg").write_text("[node]\nnickname = stub\n", encoding="utf-8")
    bins = tmp_path / "bin"
    bins.mkdir()
    leader_file = tmp_path / "leader.pid"
    child_file = tmp_path / "child.pid"
    env_leader = "LEASEGRID_TEST_LEADER_PID"
    env_child = "LEASEGRID_TEST_CHILD_PID"
    old_leader = os.environ.get(env_leader)
    old_child = os.environ.get(env_child)
    os.environ[env_leader] = str(leader_file)
    os.environ[env_child] = str(child_file)
    leader = 0
    child = 0
    client = TahoeClient(nodedir=nodedir, home=home, tahoe_bin=_executable(bins, _STUB))
    try:
        client.start(timeout=10)
        assert leader_file.is_file()
        assert child_file.is_file()
        leader = int(leader_file.read_text(encoding="utf-8").strip())
        child = int(child_file.read_text(encoding="utf-8").strip())
        _remember(leader)
        _remember(child)
        assert leader > 0 and child > 0 and leader != child
        if sys.platform != "win32":
            assert os.getpgid(child) == os.getpgid(leader)
            assert os.getpgid(leader) != os.getpgrp()
        client.stop(terminate_timeout=0.3)
        assert client._proc is None
        assert _wait_reaped(leader)
        assert _wait_reaped(child)
        assert _reaped(leader)
        assert _reaped(child)
    finally:
        os.environ.pop(env_leader, None)
        if old_leader is not None:
            os.environ[env_leader] = old_leader
        os.environ.pop(env_child, None)
        if old_child is not None:
            os.environ[env_child] = old_child
        proc = client._proc
        if proc is not None and proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)
        for path in (leader_file, child_file):
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8").strip()
            if not text.isdigit():
                continue
            pid = int(text)
            _remember(pid)
            if not _reaped(pid):
                try:
                    kill_pid(pid)
                except OSError:
                    pass


def test_reap_of_an_exited_leader_sends_no_signal(tmp_path: Path) -> None:
    """A leader that has already been reaped must not be signalled again."""
    log = open(os.devnull, "wb")
    proc = popen_hidden([sys.executable, "-c", "import os; os._exit(0)"], log)
    try:
        proc.wait(timeout=5)
        assert proc.poll() is not None
        if sys.platform == "win32":
            with patch("leasegrid_sync.backend.subprocess.run") as run:
                reap_child(proc, 0.2)
            for call in run.call_args_list:
                cmd = call.args[0] if call.args else call.kwargs.get("args")
                assert not cmd or "taskkill" not in cmd[0]
        else:
            with patch("leasegrid_sync.backend.os.killpg") as killpg, patch(
                "leasegrid_sync.backend.os.kill"
            ) as kill:
                reap_child(proc, 0.2)
            assert killpg.call_count == 0
            assert kill.call_count == 0
    finally:
        log.close()
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="POSIX process-group ids are reused; Windows has no killpg",
)
def test_reaped_leader_does_not_signal_a_reused_pid() -> None:
    """An unrelated session that now owns the old pid must survive stop()."""
    log = open(os.devnull, "wb")
    proc = popen_hidden([sys.executable, "-c", "import os; os._exit(0)"], log)
    victim = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(600)"],
        start_new_session=True,
    )
    try:
        proc.wait(timeout=5)
        assert proc.poll() is not None
        proc.pid = victim.pid
        reap_child(proc, 0.5)
        # SIGKILL is visible to poll() only after the kernel has reaped it.
        time.sleep(0.3)
        assert victim.poll() is None
    finally:
        log.close()
        if victim.poll() is None:
            victim.kill()
            victim.wait(timeout=5)


# Leader uses the default SIGTERM action. The grandchild ignores SIGTERM and
# stays in the leader's process group. A foreign-uid socket is not involved.
_OBEY_LEADER = r"""
import subprocess
import sys
import time
from pathlib import Path

grandchild = (
    "import os, signal, sys, time\n"
    "from pathlib import Path\n"
    "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
    "Path(sys.argv[1]).write_text(str(os.getpid()), encoding='utf-8')\n"
    "time.sleep(600)\n"
)
subprocess.Popen([sys.executable, "-c", grandchild, sys.argv[1]])
if sys.argv[2] == "exit":
    deadline = time.time() + 5
    while time.time() < deadline and not Path(sys.argv[1]).is_file():
        time.sleep(0.02)
    raise SystemExit(0)
time.sleep(600)
"""


def _wait_for_file(path: Path, timeout: float = 5.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if path.is_file() and path.read_text(encoding="utf-8").strip().isdigit():
            return True
        time.sleep(0.02)
    return False


def _leader_is_unreaped_zombie(proc: subprocess.Popen, timeout: float = 5.0) -> bool:
    """True when waitid sees the exit and nothing has collected it."""
    if not hasattr(os, "waitid"):
        return False
    flags = os.WEXITED | os.WNOWAIT | os.WNOHANG
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.returncode is not None:
            return False
        try:
            info = os.waitid(os.P_PID, proc.pid, flags)
        except (ChildProcessError, OSError):
            return False
        if info is not None:
            return True
        time.sleep(0.05)
    return False


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="POSIX process groups; Windows stop is CTRL_BREAK then taskkill /T",
)
def test_reap_kills_grandchild_when_the_leader_obeys_term(tmp_path: Path) -> None:
    """SIGTERM reaps an obedient leader. The grandchild must still die."""
    child_file = tmp_path / "child.pid"
    log = open(os.devnull, "wb")
    proc = popen_hidden(
        [sys.executable, "-c", _OBEY_LEADER, str(child_file), "stay"],
        log,
    )
    child = 0
    try:
        _remember(proc.pid)
        assert _wait_for_file(child_file), "grandchild did not start"
        child = int(child_file.read_text(encoding="utf-8").strip())
        _remember(child)
        assert child != proc.pid
        reap_child(proc, 2.0)
        assert proc.returncode is not None
        assert _wait_reaped(child), "grandchild survived reap_child"
        assert _reaped(child)
    finally:
        log.close()
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)
        if child and not _reaped(child):
            kill_pid(child)


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="POSIX process groups; Windows stop is CTRL_BREAK then taskkill /T",
)
def test_stop_kills_grandchild_after_the_leader_exits_on_its_own(tmp_path: Path) -> None:
    """An unreaped leader still pins the group. stop() must kill the grandchild."""
    home = tmp_path / "home"
    nodedir = home / "tahoe"
    nodedir.mkdir(parents=True)
    child_file = tmp_path / "child.pid"
    log = open(os.devnull, "wb")
    proc = popen_hidden(
        [sys.executable, "-c", _OBEY_LEADER, str(child_file), "exit"],
        log,
    )
    child = 0
    client = TahoeClient(nodedir=nodedir, home=home)
    try:
        _remember(proc.pid)
        assert _wait_for_file(child_file), "grandchild did not start"
        child = int(child_file.read_text(encoding="utf-8").strip())
        _remember(child)
        assert _leader_is_unreaped_zombie(proc), "leader was reaped before stop()"
        assert not _reaped(child)
        client._proc = proc
        client.stop(terminate_timeout=1.0)
        assert client._proc is None
        assert proc.returncode is not None
        assert _wait_reaped(child), "grandchild survived stop()"
        assert _reaped(child)
    finally:
        log.close()
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)
        if child and not _reaped(child):
            kill_pid(child)
