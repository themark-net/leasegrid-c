"""A leftover daemon for our node dir is stopped on the next launch.

Real processes. A sleeper whose command line names a different directory is
left alone, including when its pid sits in our pid file.
"""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
from tests.proc_util import pid_alive

from leasegrid_sync.backend import MagicFolderCtl, TahoeClient

pytestmark = pytest.mark.skipif(
    sys.platform == "win32",
    reason="orphan stop reads /proc or ps command lines; Windows has no safe cmdline check here",
)

# Our orphan ignores SIGTERM, so a stop that only signals TERM leaves it alive.
# The spare does not: a mistaken SIGTERM kills it and the test fails.
_SLEEPER = r'''
import os
import signal
import sys
import time
from pathlib import Path

ignore = "--ignore-term" in sys.argv
if ignore:
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
directory = sys.argv[1]
pid_path = Path(sys.argv[2])
child_arg = sys.argv[3] if len(sys.argv) > 3 else "-"
if child_arg != "-" and os.fork() == 0:
    if ignore:
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
    Path(child_arg).write_text(str(os.getpid()), encoding="utf-8")
    while True:
        time.sleep(30)
    os._exit(0)
pid_path.write_text(str(os.getpid()), encoding="utf-8")
while True:
    time.sleep(30)
'''

_TAHOE = r'''
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import socketserver
from pathlib import Path


class _Server(ThreadingHTTPServer):
    def server_bind(self):
        socketserver.TCPServer.server_bind(self)
        self.server_name = "127.0.0.1"
        self.server_port = self.server_address[1]


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b'{"introducers":{"statuses":["connected"]},"servers":[]}'
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
        raise SystemExit(0)
    nodedir = Path(args[args.index("run") + 1])
    server = _Server(("127.0.0.1", 0), _Handler)
    port = server.server_address[1]
    (nodedir / "node.url").write_text("http://127.0.0.1:%d/\n" % port, encoding="utf-8")
    server.serve_forever()


if __name__ == "__main__":
    main()
'''

_MF = r'''
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b"{}"
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        return


def main():
    if "run" not in sys.argv:
        raise SystemExit(0)
    port = int(os.environ["LEASEGRID_TEST_MF_PORT"])
    config = None
    args = sys.argv[1:]
    if "--config" in args:
        config = Path(args[args.index("--config") + 1])
    server = ThreadingHTTPServer(("127.0.0.1", port), _Handler)
    if config is not None:
        (config / "api_client_endpoint").write_text(
            "tcp:127.0.0.1:%d\n" % port, encoding="utf-8"
        )
    server.serve_forever()


if __name__ == "__main__":
    main()
'''

# Quit during Magic Folder spawn. The stub never becomes ready on its own;
# ensure_running has to notice the signal and reap it.
_MF_QUIT = r'''
import os
import signal
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from leasegrid_sync import backend as backend_mod

request_quit = getattr(backend_mod, "request_quit", lambda: None)
ShutdownRequested = getattr(
    backend_mod, "ShutdownRequested", type("ShutdownRequested", (Exception,), {})
)
MagicFolderCtl = backend_mod.MagicFolderCtl


def _handler(signum, frame):
    request_quit()


signal.signal(signal.SIGTERM, _handler)
signal.signal(signal.SIGINT, _handler)
config = Path(sys.argv[1])
nodedir = Path(sys.argv[2])
binary = sys.argv[3]
(config / "api_token").write_text("test-token\n", encoding="utf-8")
ctl = MagicFolderCtl(config_dir=config, nodedir=nodedir, mf_bin=binary)
try:
    ctl.ensure_running()
except ShutdownRequested:
    raise SystemExit(0)
time.sleep(30)
raise SystemExit(2)
'''

_MF_HANG = r'''
import os
import signal
import sys
import time
from pathlib import Path

signal.signal(signal.SIGTERM, signal.SIG_IGN)
if "run" not in sys.argv:
    raise SystemExit(0)
pidfile = os.environ.get("LEASEGRID_TEST_MF_PIDFILE", "")
if pidfile:
    Path(pidfile).write_text(str(os.getpid()), encoding="utf-8")
while True:
    time.sleep(30)
'''


def _executable(directory: Path, name: str, body: str) -> str:
    directory.mkdir(parents=True, exist_ok=True)
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


def _spawn(script: str, args: list[str], cwd: Path | None = None) -> subprocess.Popen[bytes]:
    kwargs = {}
    if sys.platform != "win32":
        kwargs["start_new_session"] = True
    if cwd is not None:
        kwargs["cwd"] = str(cwd)
    return subprocess.Popen(
        [sys.executable, "-c", script, *args],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        **kwargs,
    )


def _wait_file(path: Path, timeout: float = 5) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if path.is_file() and path.read_text(encoding="utf-8").strip().isdigit():
            return
        time.sleep(0.02)
    raise AssertionError("pid file was not written: %s" % path)


def _stop(proc: subprocess.Popen) -> None:
    if proc.poll() is None:
        proc.kill()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass


def _free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])
    finally:
        sock.close()


def test_start_stops_our_tahoe_orphan_and_spares_another_nodedir(tmp_path: Path, monkeypatch) -> None:
    """Our crashed tahoe is stopped. A process for a different node dir is not."""
    home = tmp_path / "home"
    nodedir = tmp_path / "tahoe"
    other = tmp_path / "other-node"
    home.mkdir()
    nodedir.mkdir()
    other.mkdir()
    (nodedir / "tahoe.cfg").write_text("[node]\nnickname = t\n", encoding="utf-8")
    monkeypatch.setenv("LEASEGRID_SYNC_HOME", str(home))
    our_pid_path = nodedir / "leasegrid-tahoe.pid"
    child_path = tmp_path / "grandchild.pid"
    spare_pid_path = tmp_path / "spare.pid"
    our = _spawn(
        _SLEEPER,
        [str(nodedir.resolve()), str(our_pid_path), str(child_path), "--ignore-term"],
    )
    spare = _spawn(_SLEEPER, [str(other.resolve()), str(spare_pid_path), "-"])
    binary = _executable(tmp_path / "bin", "tahoe", _TAHOE)
    client = TahoeClient(nodedir=nodedir, tahoe_bin=binary, home=home)
    try:
        _wait_file(our_pid_path)
        _wait_file(child_path)
        _wait_file(spare_pid_path)
        leader = int(our_pid_path.read_text(encoding="utf-8").strip())
        child = int(child_path.read_text(encoding="utf-8").strip())
        spare_pid = int(spare_pid_path.read_text(encoding="utf-8").strip())
        # A foreign pid recorded beside ours. Matching cmdline is required.
        (nodedir / "twistd.pid").write_text("%d\n" % spare_pid, encoding="utf-8")
        client.start(timeout=8)
        try:
            our.wait(timeout=3)
        except subprocess.TimeoutExpired:
            raise AssertionError("orphan tahoe was still running") from None
        assert not pid_alive(leader)
        deadline = time.time() + 3
        while time.time() < deadline and pid_alive(child):
            time.sleep(0.05)
        assert not pid_alive(child), "grandchild of our tahoe survived"
        assert spare.poll() is None, "a different node dir was signalled"
        assert pid_alive(spare_pid)
        assert client._proc is not None and pid_alive(client._proc.pid)
    finally:
        client.stop()
        _stop(our)
        _stop(spare)


def test_pid_one_in_our_pid_file_is_not_signalled(tmp_path: Path, monkeypatch) -> None:
    """A pid file that names pid 1 does not signal it. The new daemon still starts."""
    home = tmp_path / "home"
    nodedir = tmp_path / "tahoe"
    home.mkdir()
    nodedir.mkdir()
    (nodedir / "tahoe.cfg").write_text("[node]\nnickname = t\n", encoding="utf-8")
    monkeypatch.setenv("LEASEGRID_SYNC_HOME", str(home))
    (nodedir / "twistd.pid").write_text("1\n", encoding="utf-8")
    binary = _executable(tmp_path / "bin", "tahoe", _TAHOE)
    client = TahoeClient(nodedir=nodedir, tahoe_bin=binary, home=home)
    try:
        client.start(timeout=8)
        assert Path("/proc/1").exists() or pid_alive(1)
        assert client._proc is not None and pid_alive(client._proc.pid)
    finally:
        client.stop()


def test_magic_folder_start_stops_our_orphan_only(tmp_path: Path, monkeypatch) -> None:
    """Our leftover magic-folder is stopped. Another config dir's process is not."""
    home = tmp_path / "home"
    nodedir = tmp_path / "tahoe"
    config = home / "magic-folder"
    other = tmp_path / "other-config"
    home.mkdir()
    nodedir.mkdir()
    config.mkdir()
    other.mkdir()
    (nodedir / "tahoe.cfg").write_text("[node]\nnickname = t\n", encoding="utf-8")
    (config / "api_token").write_text("test-token\n", encoding="utf-8")
    monkeypatch.setenv("LEASEGRID_SYNC_HOME", str(home))
    port = _free_port()
    monkeypatch.setenv("LEASEGRID_MF_PORT", str(port))
    monkeypatch.setenv("LEASEGRID_TEST_MF_PORT", str(port))
    our_pid_path = config / "leasegrid-magic-folder.pid"
    spare_pid_path = tmp_path / "spare.pid"
    our = _spawn(
        _SLEEPER,
        [str(config.resolve()), str(our_pid_path), "-", "--ignore-term"],
    )
    spare = _spawn(_SLEEPER, [str(other.resolve()), str(spare_pid_path), "-"])
    binary = _executable(tmp_path / "bin", "magic-folder", _MF)
    ctl = MagicFolderCtl(config_dir=config, nodedir=nodedir, mf_bin=binary)
    try:
        _wait_file(our_pid_path)
        _wait_file(spare_pid_path)
        spare_pid = int(spare_pid_path.read_text(encoding="utf-8").strip())
        ctl.ensure_running()
        try:
            our.wait(timeout=3)
        except subprocess.TimeoutExpired:
            raise AssertionError("orphan magic-folder was still running") from None
        assert spare.poll() is None, "a different magic-folder config was signalled"
        assert pid_alive(spare_pid)
        assert ctl._proc is not None and pid_alive(ctl._proc.pid)
    finally:
        ctl.stop()
        _stop(our)
        _stop(spare)


def test_sigterm_during_magic_folder_spawn_reaps_it(tmp_path: Path, monkeypatch) -> None:
    """SIGTERM while magic-folder is spawning reaps it instead of leaving it up."""
    home = tmp_path / "home"
    config = home / "magic-folder"
    nodedir = tmp_path / "tahoe"
    home.mkdir()
    config.mkdir()
    nodedir.mkdir()
    monkeypatch.setenv("LEASEGRID_SYNC_HOME", str(home))
    port = _free_port()
    pidfile = tmp_path / "mf.pid"
    bins = tmp_path / "bin"
    binary = _executable(bins, "magic-folder", _MF_HANG)
    driver = tmp_path / "quit_driver.py"
    driver.write_text(_MF_QUIT, encoding="utf-8")
    env = os.environ.copy()
    env["LEASEGRID_SYNC_HOME"] = str(home)
    env["LEASEGRID_MF_PORT"] = str(port)
    env["LEASEGRID_TEST_MF_PIDFILE"] = str(pidfile)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    proc = subprocess.Popen(
        [sys.executable, str(driver), str(config), str(nodedir), binary],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        env=env,
        start_new_session=True,
    )
    try:
        deadline = time.time() + 8
        while time.time() < deadline and not pidfile.is_file() and proc.poll() is None:
            time.sleep(0.02)
        assert pidfile.is_file(), "magic-folder did not spawn: %s" % (
            proc.stderr.read().decode("utf-8", "replace") if proc.stderr is not None else ""
        )
        stub = int(pidfile.read_text(encoding="utf-8").strip())
        os.kill(proc.pid, signal.SIGTERM)
        try:
            rc = proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            raise AssertionError("spawn survived SIGTERM") from None
        assert rc == 0, rc
        deadline = time.time() + 3
        while time.time() < deadline and pid_alive(stub):
            time.sleep(0.05)
        assert not pid_alive(stub), "magic-folder survived SIGTERM during spawn"
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)
        if pidfile.is_file():
            try:
                stub = int(pidfile.read_text(encoding="utf-8").strip())
            except ValueError:
                stub = 0
            if stub > 1 and pid_alive(stub):
                os.kill(stub, signal.SIGKILL)


def test_relative_nodedir_orphan_is_stopped_and_a_lookalike_is_not(
    tmp_path: Path, monkeypatch
) -> None:
    """A leftover started as ./tahoe is stopped once that folder is resolved.

    The next launch is in another working directory. The old process still
    has the relative path, so the match has to use that process's directory.
    A process started as ./tahoe-not is a different folder and stays up, even
    when its pid is written in this node's pid file.
    """
    if not os.path.exists("/proc/self/cwd"):
        pytest.skip("relative orphan match reads /proc/<pid>/cwd")
    work = tmp_path / "work"
    nodedir = work / "tahoe"
    elsewhere = tmp_path / "elsewhere"
    home = tmp_path / "home"
    nodedir.mkdir(parents=True)
    elsewhere.mkdir()
    home.mkdir()
    (nodedir / "tahoe.cfg").write_text("[node]\nnickname = t\n", encoding="utf-8")
    monkeypatch.setenv("LEASEGRID_SYNC_HOME", str(home))
    outside_pid = tmp_path / "our.pid"
    spare_pid_path = tmp_path / "spare.pid"
    our = _spawn(
        _SLEEPER,
        ["./tahoe", str(outside_pid), "-", "--ignore-term"],
        cwd=work,
    )
    spare = _spawn(
        _SLEEPER,
        ["./tahoe-not", str(spare_pid_path), "-"],
        cwd=work,
    )
    binary = _executable(tmp_path / "bin", "tahoe", _TAHOE)
    client = TahoeClient(nodedir=nodedir, tahoe_bin=binary, home=home)
    try:
        _wait_file(outside_pid)
        _wait_file(spare_pid_path)
        leader = int(outside_pid.read_text(encoding="utf-8").strip())
        spare_pid = int(spare_pid_path.read_text(encoding="utf-8").strip())
        (nodedir / "leasegrid-tahoe.pid").write_text("%d\n" % leader, encoding="utf-8")
        (nodedir / "twistd.pid").write_text("%d\n" % spare_pid, encoding="utf-8")
        monkeypatch.chdir(elsewhere)
        client.start(timeout=8)
        try:
            our.wait(timeout=3)
        except subprocess.TimeoutExpired:
            raise AssertionError("relative orphan tahoe was still running") from None
        assert not pid_alive(leader)
        assert spare.poll() is None, "a lookalike folder was signalled"
        assert pid_alive(spare_pid)
        assert client._proc is not None and pid_alive(client._proc.pid)
    finally:
        client.stop()
        _stop(our)
        _stop(spare)
