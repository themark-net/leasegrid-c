"""#30 on --dogfood-folder: hosts are checked against shares.happy before the add.

Tahoe's welcome page and the Magic Folder daemon are local HTTP stand-ins, and
`magic-folder` is a fake binary. The join, the hosts check, the add command and
the exit code are the real ones.
"""

from __future__ import annotations

import json
import os
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PyQt5 = pytest.importorskip("PyQt5")
pytest.importorskip("segno")

from leasegrid_sync import app as app_mod  # noqa: E402
from leasegrid_sync.app import MainWindow, _run_modes  # noqa: E402
from tests.qr_decode import write_executable  # noqa: E402
from tests.test_sync_folder_journey import (  # noqa: E402
    FURL,
    _free_port,
    _json_response,
    _QuietHandler,
    _wait_until,
)


class _Grid(threading.Thread):
    """Tahoe GET /?t=json with a host count the test can change.

    When ``drop_on`` exists (the fake add wrote it), every host reads as gone.
    """

    def __init__(self, hosts: int, drop_on: Path) -> None:
        super().__init__(daemon=True)
        self.hosts = hosts
        self.drop_on = drop_on
        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self.port = int(self._httpd.server_address[1])

    def body(self) -> dict:
        up = 0 if self.drop_on.exists() else self.hosts
        return {
            "introducers": {"statuses": ["Connected to tcp:127.0.0.1:1 via tcp"]},
            "servers": [
                {"nickname": "storage-%d" % i, "nodeid": "n%d" % i,
                 "connection_status": "connected" if i <= up else ""}
                for i in (1, 2, 3)
            ],
        }

    def _handler(self):
        owner = self

        class Handler(_QuietHandler):
            def do_GET(self) -> None:  # noqa: N802
                _json_response(self, owner.body())

        return Handler

    def run(self) -> None:
        self._httpd.serve_forever()

    def stop(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()


class _Daemon(threading.Thread):
    """Magic Folder API: folder list, scan, file status.

    Once ``fail_500`` is set, the daemon still answers the next list (the
    is-it-running probe) and then answers the folder list with HTTP 500.
    """

    def __init__(self, spool: Path) -> None:
        super().__init__(daemon=True)
        self.spool = spool
        self.token = "dogfood-token"
        self.fail_500 = False
        self._ok_left = 1
        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self.port = int(self._httpd.server_address[1])

    def folders(self) -> dict:
        out = {}
        if self.spool.is_file():
            for line in self.spool.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    item = json.loads(line)
                    out[item["name"]] = {"magic_path": item["path"], "poll_interval": 5}
        return out

    def _handler(self):
        owner = self

        class Handler(_QuietHandler):
            def _authed(self) -> bool:
                if self.headers.get("Authorization") != "Bearer %s" % owner.token:
                    _json_response(self, {}, status=401)
                    return False
                return True

            def do_GET(self) -> None:  # noqa: N802
                if not self._authed():
                    return
                path = self.path.split("?", 1)[0]
                if path == "/v1/magic-folder":
                    if owner.fail_500 and owner._ok_left > 0:
                        owner._ok_left -= 1
                    elif owner.fail_500:
                        _json_response(self, {"traceback": "boom"}, status=500)
                        return
                    _json_response(self, owner.folders())
                    return
                if path.endswith("/file-status"):
                    _json_response(self, [{"relpath": "u1-hello.txt", "size": 1}])
                    return
                _json_response(self, [])

            def do_PUT(self) -> None:  # noqa: N802
                if self._authed():
                    _json_response(self, {})

        return Handler

    def run(self) -> None:
        self._httpd.serve_forever()

    def stop(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()


def _mf_cli(spool: Path, drop_on: Path, exit_code: int) -> str:
    """Fake `magic-folder add`: record the add, optionally drop the hosts, exit."""
    return "\n".join(
        [
            "import json, sys",
            "from pathlib import Path",
            "args = sys.argv[1:]",
            "if 'add' in args:",
            "    name = args[args.index('--name') + 1]",
            "    if %d == 0:" % exit_code,
            "        with Path(%r).open('a', encoding='utf-8') as fh:" % str(spool),
            "            fh.write(json.dumps({'name': name, 'path': args[-1]}) + '\\n')",
            "    if %r:" % bool(exit_code),
            "        Path(%r).write_text('dropped', encoding='utf-8')" % str(drop_on),
            "    Path(%r).with_suffix('.called').write_text('add', encoding='utf-8')" % str(spool),
            "raise SystemExit(%d)" % exit_code,
        ]
    )


@pytest.fixture
def grid(tmp_path: Path, monkeypatch):
    home = tmp_path / "home"
    nodedir = home / "tahoe"
    nodedir.mkdir(parents=True)
    spool = tmp_path / "mf-add.jsonl"
    drop_on = tmp_path / "hosts-dropped"
    made = {}

    def build(hosts: int, add_exit: int = 0) -> tuple[MainWindow, _Grid, _Daemon, Path]:
        g = _Grid(hosts, drop_on)
        d = _Daemon(spool)
        g.start()
        d.start()
        made["g"], made["d"] = g, d
        _wait_until("http://127.0.0.1:%d/?t=json" % g.port)
        _wait_until(urllib.request.Request(
            "http://127.0.0.1:%d/v1/magic-folder" % d.port,
            headers={"Authorization": "Bearer %s" % d.token},
        ))
        cfg = home / "magic-folder"
        cfg.mkdir(parents=True, exist_ok=True)
        (cfg / "api_token").write_text(d.token + "\n", encoding="utf-8")
        (cfg / "api_client_endpoint").write_text("tcp:127.0.0.1:%d\n" % d.port, encoding="utf-8")
        (nodedir / "node.url").write_text("http://127.0.0.1:%d/\n" % g.port, encoding="utf-8")
        (nodedir / "tahoe.cfg").write_text(
            "[node]\nnickname = alice\n[client]\nintroducer.furl = %s\n"
            "shares.needed = 2\nshares.happy = 3\nshares.total = 3\n[storage]\nenabled = false\n" % FURL,
            encoding="utf-8",
        )
        monkeypatch.setenv("LEASEGRID_SYNC_HOME", str(home))
        monkeypatch.setenv("LEASEGRID_MF_PORT", str(_free_port()))
        monkeypatch.delenv("LEASEGRID_GATED", raising=False)
        monkeypatch.setenv(
            "LEASEGRID_MAGIC_FOLDER_BIN",
            write_executable(tmp_path / "bin", _mf_cli(spool, drop_on, add_exit), name="magic-folder"),
        )
        window = MainWindow(nodedir=nodedir, home=home, autoload=False)
        window.poll.stop()
        made["w"] = window
        return window, g, d, spool

    yield build
    w = made.get("w")
    if w is not None:
        w.poll.stop()
        w.win.hide()
        if w.tray is not None:
            w.tray.hide()
    for key in ("g", "d"):
        if key in made:
            made[key].stop()


def _run(window: MainWindow, folder: Path) -> int:
    return _run_modes(window, None, folder, False, "medium")


def test_too_few_hosts_exits_nonzero_before_magic_folder_is_asked(grid, tmp_path: Path, capsys, monkeypatch):
    monkeypatch.setattr(app_mod, "ADD_FOLDER_HOSTS_WAIT", 1.0, raising=False)
    window, _g, _d, spool = grid(hosts=1)
    rc = _run(window, tmp_path / "sync")
    err = capsys.readouterr().err
    assert rc != 0
    assert "folder not added. Hosts connected: 1 of 3 needed." in err
    assert "#30" not in err
    assert not spool.with_suffix(".called").exists(), "magic-folder add ran with too few hosts"


def test_hosts_that_settle_within_the_wait_let_the_add_run(grid, tmp_path: Path, capsys, monkeypatch):
    """Right after a join a healthy grid can show 1 of 3. The dogfood path waits for it."""
    monkeypatch.setattr(app_mod, "ADD_FOLDER_HOSTS_WAIT", 10.0, raising=False)
    window, g, _d, spool = grid(hosts=1)
    threading.Timer(1.0, lambda: setattr(g, "hosts", 3)).start()
    rc = _run(window, tmp_path / "sync")
    out = capsys.readouterr()
    assert rc == 0, out.err
    assert "U1 dogfood" in out.out
    assert spool.with_suffix(".called").exists()


def test_enough_hosts_adds_the_folder(grid, tmp_path: Path, capsys):
    window, _g, _d, spool = grid(hosts=3)
    rc = _run(window, tmp_path / "sync")
    out = capsys.readouterr()
    assert rc == 0, out.err
    assert "u1-dogfood" in spool.read_text(encoding="utf-8")


def test_hosts_dropping_mid_add_name_the_hosts_not_issue_30(grid, tmp_path: Path, capsys):
    window, _g, _d, spool = grid(hosts=3, add_exit=1)
    rc = _run(window, tmp_path / "sync")
    err = capsys.readouterr().err
    assert spool.with_suffix(".called").exists()
    assert rc != 0
    assert "folder not added. Hosts connected: 0 of 3 needed." in err
    assert "#30" not in err


def test_http_500_with_enough_hosts_still_names_issue_30(grid, tmp_path: Path, capsys):
    window, _g, d, _spool = grid(hosts=3)
    real_add = window.mf.add_folder

    def add_then_daemon_fails(*args, **kwargs):
        d.fail_500 = True
        return real_add(*args, **kwargs)

    with patch.object(window.mf, "add_folder", side_effect=add_then_daemon_fails):
        rc = _run(window, tmp_path / "sync")
    err = capsys.readouterr().err
    assert rc != 0
    assert "#30" in err
    assert "Hosts connected" not in err
