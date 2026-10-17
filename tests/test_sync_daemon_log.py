"""tahoe.log and magic-folder.log rotate before the daemon starts.

A failure to rotate must still start the daemon. Skipping the rotate call
leaves the oversized file as the live log.
"""

from __future__ import annotations

import os
import socket
import sys
from pathlib import Path

import pytest

from leasegrid_sync.backend import LOG_ROTATE_BYTES, MagicFolderCtl, TahoeClient

_LIMIT = LOG_ROTATE_BYTES
_MARKER = b"OLD-DAEMON-LOG\n"

_STUB = r"""
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b'{"introducers":{"statuses":["connected"]},"servers":[{"nickname":"stub","connection_status":"connected"}]}'
        if self.path.startswith("/v1/magic-folder"):
            body = b"{}"
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        return


def main() -> None:
    args = sys.argv[1:]
    if "init" in args:
        sys.exit(0)
    if "run" not in args:
        sys.exit(0)
    config = None
    if "--config" in args:
        config = Path(args[args.index("--config") + 1])
    elif args[0] != "run":
        pass
    nodedir = None
    if args[0] == "run":
        nodedir = Path(args[1])
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    if nodedir is not None:
        (nodedir / "node.url").write_text("http://127.0.0.1:%d/\n" % port, encoding="utf-8")
    if config is not None:
        config.mkdir(parents=True, exist_ok=True)
        (config / "api_token").write_text("stub-token\n", encoding="utf-8")
        (config / "api_client_endpoint").write_text(
            "tcp:127.0.0.1:%d\n" % port, encoding="utf-8"
        )
    sys.stdout.write("daemon-started\n")
    sys.stdout.flush()
    server.serve_forever()


if __name__ == "__main__":
    main()
"""


def _executable(directory: Path, name: str) -> str:
    directory.mkdir(parents=True, exist_ok=True)
    script = directory / (name + ".py")
    script.write_text(_STUB, encoding="utf-8")
    if os.name == "nt":
        bat = directory / (name + ".bat")
        bat.write_text('@"%s" "%s" %%*\n' % (sys.executable, script), encoding="utf-8")
        return str(bat)
    bin_ = directory / name
    bin_.write_text("#!%s\n%s" % (sys.executable, _STUB), encoding="utf-8")
    bin_.chmod(0o755)
    return str(bin_)


def _oversized(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_MARKER * ((_LIMIT // len(_MARKER)) + 3))
    assert path.stat().st_size > _LIMIT


def _free_port() -> int:
    sock = socket.socket()
    try:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]
    finally:
        sock.close()


def _start(kind: str, tmp_path: Path, bin_path: str):
    home = tmp_path / "home"
    nodedir = home / "tahoe"
    nodedir.mkdir(parents=True)
    (nodedir / "tahoe.cfg").write_text("[node]\nnickname = stub\n", encoding="utf-8")
    if kind == "tahoe":
        client = TahoeClient(nodedir=nodedir, home=home, tahoe_bin=bin_path)
        log = client.log_path
        _oversized(log)
        client.start(timeout=10)
        return client, log
    mf = MagicFolderCtl(
        config_dir=home / "magic-folder",
        nodedir=nodedir,
        mf_bin=bin_path,
        listen_port=_free_port(),
    )
    log = mf.log_path
    _oversized(log)
    mf.ensure_running()
    return mf, log


def _stop(ctl) -> None:
    ctl.stop(terminate_timeout=0.5)


@pytest.mark.parametrize("kind", ["tahoe", "magic-folder"])
def test_daemon_log_rotates_when_the_daemon_starts(tmp_path: Path, monkeypatch, kind: str) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("LEASEGRID_SYNC_HOME", str(home))
    bin_path = _executable(tmp_path / "bin", "daemon")
    ctl, log = _start(kind, tmp_path, bin_path)
    try:
        backup = log.with_name(log.name + ".1")
        live = log.read_bytes()
        assert backup.is_file()
        assert _MARKER in backup.read_bytes()
        assert len(live) < _LIMIT
        assert _MARKER not in live
        assert b"daemon-started" in live
    finally:
        _stop(ctl)


@pytest.mark.parametrize("kind", ["tahoe", "magic-folder"])
def test_daemon_starts_when_log_rotation_fails(tmp_path: Path, monkeypatch, kind: str) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("LEASEGRID_SYNC_HOME", str(home))
    bin_path = _executable(tmp_path / "bin", "daemon")
    nodedir = home / "tahoe"
    nodedir.mkdir(parents=True)
    (nodedir / "tahoe.cfg").write_text("[node]\nnickname = stub\n", encoding="utf-8")
    if kind == "tahoe":
        ctl = TahoeClient(nodedir=nodedir, home=home, tahoe_bin=bin_path)
    else:
        ctl = MagicFolderCtl(
            config_dir=home / "magic-folder",
            nodedir=nodedir,
            mf_bin=bin_path,
            listen_port=_free_port(),
        )
    log = ctl.log_path
    _oversized(log)
    blocker = log.with_name(log.name + ".1")
    blocker.mkdir()
    (blocker / "busy").write_text("x", encoding="utf-8")
    try:
        if kind == "tahoe":
            ctl.start(timeout=10)
        else:
            ctl.ensure_running()
        assert ctl._proc is not None
        assert ctl._proc.poll() is None
        assert blocker.is_dir()
    finally:
        _stop(ctl)
