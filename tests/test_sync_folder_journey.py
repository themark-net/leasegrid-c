"""One desktop journey: add, share, conflict and rename, remove, restart, offline.

Tahoe's welcome page and the Magic Folder daemon are local stand-ins. The
window, the add command, and the folder HTTP client are the real ones.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PyQt5 = pytest.importorskip("PyQt5")
pytest.importorskip("segno")

from leasegrid_sync.app import MainWindow  # noqa: E402
from leasegrid_sync.backend import MagicFolderCtl  # noqa: E402
from tests.buyer_text import assert_no_raw_user_text  # noqa: E402
from tests.qr_decode import INVITE_JOIN_TAHOE, decode_qr_png, write_executable  # noqa: E402

FURL = "pb://hashhashhash@127.0.0.1:45001/swissnumswiss"
CODE = "7-orange-tunnel"


class _QuietHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        return


def _json_response(handler: BaseHTTPRequestHandler, payload, status: int = 200) -> None:
    raw = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(raw)))
    handler.end_headers()
    handler.wfile.write(raw)


def _wait_until(request) -> None:
    """The listener thread may not be inside accept yet."""
    deadline = time.time() + 5
    last = ""
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(request, timeout=0.5) as resp:
                resp.read()
            return
        except Exception as exc:
            last = str(exc)
            time.sleep(0.05)
    target = getattr(request, "full_url", request)
    raise AssertionError("stand-in did not answer %s (%s)" % (target, last))


def _free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])
    finally:
        sock.close()


class _Welcome(threading.Thread):
    """Tahoe GET /?t=json. The test swaps the body to drop the friendnet."""

    def __init__(self) -> None:
        super().__init__(daemon=True)
        self.online = {
            "introducers": {"statuses": ["Connected to tcp:127.0.0.1:1 via tcp"]},
            "servers": [
                {
                    "nickname": "storage-1",
                    "nodeid": "abc",
                    "connection_status": "connected",
                }
            ],
        }
        self.offline = {
            "introducers": {"statuses": ["not connected"]},
            "servers": [
                {
                    "nickname": "storage-1",
                    "nodeid": "abc",
                    "connection_status": "",
                }
            ],
        }
        self.body = self.online
        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self.port = int(self._httpd.server_address[1])

    def _handler(self):
        owner = self

        class Handler(_QuietHandler):
            def do_GET(self) -> None:  # noqa: N802
                path = self.path.split("?", 1)[0]
                if path not in ("/", ""):
                    _json_response(self, {}, status=404)
                    return
                _json_response(self, owner.body)

        return Handler

    def run(self) -> None:
        self._httpd.serve_forever()

    def stop(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()


class _MagicFolder(threading.Thread):
    """The folder HTTP API Sync actually calls, plus an add spool from the CLI."""

    def __init__(self, spool: Path) -> None:
        super().__init__(daemon=True)
        self.spool = spool
        self.token = "journey-token"
        self.down = False
        self.folders: dict[str, dict] = {}
        self._lock = threading.Lock()
        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self.port = int(self._httpd.server_address[1])

    def _apply_spool(self) -> None:
        if not self.spool.is_file():
            return
        text = self.spool.read_text(encoding="utf-8")
        self.spool.write_text("", encoding="utf-8")
        for line in text.splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            name = str(item["name"])
            if name not in self.folders:
                self.folders[name] = {
                    "path": str(item["path"]),
                    "files": [],
                    "recent": [],
                    "conflicts": {},
                }

    def _handler(self):
        owner = self

        class Handler(_QuietHandler):
            def do_GET(self) -> None:  # noqa: N802
                if self.headers.get("Authorization") != "Bearer %s" % owner.token:
                    _json_response(self, {}, status=401)
                    return
                with owner._lock:
                    if owner.down:
                        _json_response(self, {}, status=503)
                        return
                    owner._apply_spool()
                    payload = owner._payload(self.path.split("?", 1)[0])
                if payload is None:
                    _json_response(self, {}, status=404)
                    return
                _json_response(self, payload)

        return Handler

    def _payload(self, path: str):
        if path == "/v1/magic-folder":
            return {
                name: {"magic_path": row["path"], "poll_interval": 5}
                for name, row in self.folders.items()
            }
        prefix = "/v1/magic-folder/"
        if not path.startswith(prefix):
            return None
        rest = path[len(prefix):]
        name, _, kind = rest.partition("/")
        row = self.folders.get(name)
        if row is None:
            return None
        if kind == "file-status":
            return list(row["files"])
        if kind == "recent-changes":
            return list(row["recent"])
        if kind == "conflicts":
            return dict(row["conflicts"])
        return None

    def run(self) -> None:
        self._httpd.serve_forever()

    def stop(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()


def _mf_cli(spool: Path) -> str:
    return "\n".join(
        [
            "import json, sys",
            "from pathlib import Path",
            "args = sys.argv[1:]",
            "if 'add' in args:",
            "    name = args[args.index('--name') + 1]",
            "    path = args[-1]",
            "    spool = Path(%r)" % str(spool),
            "    with spool.open('a', encoding='utf-8') as fh:",
            "        fh.write(json.dumps({'name': name, 'path': path}) + '\\n')",
            "raise SystemExit(0)",
        ]
    )


def _close(window: MainWindow) -> None:
    session = getattr(window, "_invite_session", None)
    if session is not None:
        session.close()
        window._invite_session = None
    window.poll.stop()
    window.tahoe.stop()
    window.mf.stop()
    window.win.hide()
    if window.tray is not None:
        window.tray.hide()


def _status(window: MainWindow) -> str:
    item = window.table.item(0, 1)
    assert item is not None
    return item.text()


def _png(window: MainWindow, pixmap) -> bytes:
    buf = window.QtCore.QBuffer()
    buf.open(window.QtCore.QIODevice.WriteOnly)
    assert pixmap.save(buf, "PNG")
    return bytes(buf.data())


def test_folder_journey_add_share_conflict_remove_restart_offline(tmp_path: Path, monkeypatch):
    """Add a folder, share, resolve a conflict by rename, remove, restart, go offline.

    A second directory with the same name must fail and leave the first folder.
    A conflict that is not one of the five newest changes must stay Conflict
    until the conflict copy is renamed away. Quitting and opening Sync again
    keeps the folder. A dead folder daemon, then a dropped friendnet, each
    recover on the next refresh.
    """
    home = tmp_path / "home"
    nodedir = home / "tahoe"
    nodedir.mkdir(parents=True)
    docs = tmp_path / "Docs"
    docs.mkdir()
    (docs / "note.txt").write_text("hello\n", encoding="utf-8")
    other = tmp_path / "other" / "Docs"
    other.mkdir(parents=True)
    spool = tmp_path / "mf-add.jsonl"
    welcome = _Welcome()
    daemon = _MagicFolder(spool)
    welcome.start()
    daemon.start()
    _wait_until("http://127.0.0.1:%d/?t=json" % welcome.port)
    _wait_until(
        urllib.request.Request(
            "http://127.0.0.1:%d/v1/magic-folder" % daemon.port,
            headers={"Authorization": "Bearer %s" % daemon.token},
        )
    )
    mf_cfg = home / "magic-folder"
    mf_cfg.mkdir(parents=True)
    (mf_cfg / "api_token").write_text(daemon.token + "\n", encoding="utf-8")
    (mf_cfg / "api_client_endpoint").write_text(
        "tcp:127.0.0.1:%d\n" % daemon.port, encoding="utf-8"
    )
    (nodedir / "node.url").write_text("http://127.0.0.1:%d/\n" % welcome.port, encoding="utf-8")
    (nodedir / "tahoe.cfg").write_text(
        "\n".join(
            [
                "[node]",
                "nickname = alice",
                "[client]",
                "introducer.furl = %s" % FURL,
                "shares.needed = 2",
                "shares.happy = 3",
                "shares.total = 3",
                "[storage]",
                "enabled = false",
                "",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("LEASEGRID_SYNC_HOME", str(home))
    monkeypatch.setenv("LEASEGRID_MF_PORT", str(_free_port()))
    monkeypatch.setenv("LEASEGRID_JOIN_ORIGIN", "http://alice.i2p/join")
    monkeypatch.delenv("LEASEGRID_GATED", raising=False)
    mf_bin = write_executable(tmp_path / "bin", _mf_cli(spool), name="magic-folder")
    monkeypatch.setenv("LEASEGRID_MAGIC_FOLDER_BIN", mf_bin)
    picks = {"paths": [str(docs), str(other), str(docs)]}

    def pick_directory(*_args, **_kwargs) -> str:
        return picks["paths"].pop(0)

    window = None
    restarted = None
    try:
        window = MainWindow(nodedir=nodedir, home=home, autoload=True)
        window.poll.stop()
        window.tahoe.tahoe_bin = write_executable(tmp_path / "bin", INVITE_JOIN_TAHOE)
        window.win.show()
        window.QtWidgets.QApplication.processEvents()
        assert window.stack.currentWidget() is window.main_page
        assert window.table.rowCount() == 0

        with patch.object(window.QtWidgets.QFileDialog, "getExistingDirectory", pick_directory):
            window.add_btn.click()
        assert window.table.rowCount() == 1
        assert window.table.item(0, 0).text() == "Docs"
        assert _status(window) == "Syncing"
        assert window.table.item(0, 2).text() == str(docs)
        assert "Added folder Docs" in window.folder_error.text()

        with daemon._lock:
            daemon.folders["Docs"]["files"] = [{"relpath": "note.txt", "size": 6, "mtime": 1}]
            daemon.folders["Docs"]["recent"] = [{"relpath": "note.txt", "conflicted": False}]
        window.refresh()
        assert _status(window) == "Up to date"

        with patch.object(window.QtWidgets.QFileDialog, "getExistingDirectory", pick_directory):
            window.add_btn.click()
        clash = window.folder_error.text()
        assert clash.startswith("FAIL")
        assert "already syncing" in clash
        assert "\nNext: " in clash
        assert "Added folder" not in clash
        assert_no_raw_user_text(clash)
        assert window.table.rowCount() == 1
        assert window.table.item(0, 2).text() == str(docs)
        assert not any(daemon.folders[name]["path"] == str(other) for name in daemon.folders)

        with patch.object(window.QtWidgets.QFileDialog, "getExistingDirectory", pick_directory):
            window.add_btn.click()
        assert window.folder_error.text() == "Added folder Docs"
        assert window.table.rowCount() == 1
        assert _status(window) == "Up to date"

        def share_modal(dlg):
            code = dlg.findChild(PyQt5.QtWidgets.QLineEdit, "inviteDialogCode")
            assert code is not None
            assert code.text() == CODE
            assert "pb://" not in code.text()
            link = dlg.findChild(PyQt5.QtWidgets.QLineEdit, "inviteDialogLink")
            assert link is not None and link.isHidden()
            qr = dlg.findChild(PyQt5.QtWidgets.QLabel, "inviteDialogQr")
            assert qr is not None
            pix = qr.pixmap()
            assert pix is not None and not pix.isNull()
            assert decode_qr_png(_png(window, pix)) == CODE
            copy = dlg.findChild(PyQt5.QtWidgets.QPushButton, "inviteDialogCopy")
            assert copy is not None
            copy.click()
            assert window.QtWidgets.QApplication.clipboard().text() == CODE
            status = dlg.findChild(PyQt5.QtWidgets.QLabel, "inviteDialogStatus")
            assert status is not None
            assert "pb://" not in status.text()
            assert_no_raw_user_text(status.text())
            dlg.accept()
            return PyQt5.QtWidgets.QDialog.Accepted

        with patch.object(window.QtWidgets.QDialog, "exec_", share_modal):
            window.share_invite_btn.click()
        assert window._invite_session is not None
        window._invite_session.close()
        window._invite_session = None
        assert _status(window) == "Up to date"

        for index in range(5):
            (docs / ("photo-%d.jpg" % index)).write_bytes(b"x")
        (docs / "note.txt.conflict-laptop").write_text("their copy\n", encoding="utf-8")
        with daemon._lock:
            daemon.folders["Docs"]["files"] = [{"relpath": "note.txt", "size": 6, "mtime": 1}] + [
                {"relpath": "photo-%d.jpg" % index, "size": 1, "mtime": 1} for index in range(5)
            ]
            # Five newer files. note.txt is not in this window. The conflicts
            # list is the only place that still names it.
            daemon.folders["Docs"]["recent"] = [
                {"relpath": "photo-%d.jpg" % index, "conflicted": False} for index in range(5)
            ]
            daemon.folders["Docs"]["conflicts"] = {"note.txt": ["laptop"]}
        window.refresh()
        assert _status(window) == "Conflict"
        conflict = window.folder_error.text()
        assert "Docs has a sync conflict on note.txt" in conflict
        assert "rename or remove the conflict copy" in conflict
        assert "\nNext: " in conflict
        assert "pb://" not in conflict
        assert_no_raw_user_text(conflict)
        assert window.table.item(0, 0).text() == "Docs"

        marker = docs / "note.txt.conflict-laptop"
        renamed = docs / "note-from-laptop.txt"
        marker.rename(renamed)
        with daemon._lock:
            daemon.folders["Docs"]["conflicts"] = {}
            daemon.folders["Docs"]["recent"] = [
                {"relpath": "note-from-laptop.txt", "conflicted": False},
                {"relpath": "note.txt", "conflicted": False},
            ]
            daemon.folders["Docs"]["files"] = [
                {"relpath": "note.txt", "size": 6, "mtime": 1},
                {"relpath": "note-from-laptop.txt", "size": 11, "mtime": 2},
            ]
        window.refresh()
        assert _status(window) == "Up to date"
        assert "sync conflict" not in window.folder_error.text()
        assert renamed.read_text(encoding="utf-8") == "their copy\n"
        assert not marker.exists()

        shutil.rmtree(docs)
        window.refresh()
        assert _status(window) == "Missing"
        missing = window.folder_error.text()
        assert "not on this computer" in missing
        assert "\nNext: " in missing
        assert_no_raw_user_text(missing)
        with patch("PyQt5.QtGui.QDesktopServices.openUrl") as open_url:
            window.table.itemDoubleClicked.emit(window.table.item(0, 0))
        assert open_url.call_count == 0

        docs.mkdir()
        (docs / "note.txt").write_text("hello\n", encoding="utf-8")
        with daemon._lock:
            daemon.folders["Docs"]["conflicts"] = {}
            daemon.folders["Docs"]["files"] = [{"relpath": "note.txt", "size": 6, "mtime": 1}]
            daemon.folders["Docs"]["recent"] = [{"relpath": "note.txt", "conflicted": False}]
        window.refresh()
        assert _status(window) == "Up to date"
        assert "not on this computer" not in window.folder_error.text()

        window.poll.stop()
        window.win.hide()
        restarted = MainWindow(nodedir=nodedir, home=home, autoload=True)
        restarted.poll.stop()
        restarted.win.show()
        restarted.QtWidgets.QApplication.processEvents()
        assert restarted.stack.currentWidget() is restarted.main_page
        assert restarted.table.rowCount() == 1
        assert restarted.table.item(0, 0).text() == "Docs"
        assert restarted.table.item(0, 1).text() == "Up to date"
        assert restarted.table.item(0, 2).text() == str(docs)

        with daemon._lock:
            daemon.down = True
        restarted.refresh()
        stalled = restarted.folder_error.text()
        assert "could not refresh folders" in stalled
        assert "Restart Sync" in stalled
        assert restarted.table.item(0, 0).text() == "Docs"
        assert restarted.table.item(0, 1).text() == "Up to date"
        assert_no_raw_user_text(stalled)
        with daemon._lock:
            daemon.down = False
        restarted.refresh()
        assert restarted.folder_error.text() == ""
        assert restarted.table.item(0, 1).text() == "Up to date"

        welcome.body = welcome.offline
        restarted.refresh()
        assert restarted.status_chip.text() == "Offline"
        offline = restarted.folder_error.text()
        assert "could not reach this friendnet" in offline
        assert "\nNext: " in offline
        assert "introducer" not in offline.lower()
        assert "tahoe" not in offline.lower()
        assert "pb://" not in offline
        assert_no_raw_user_text(offline)
        assert restarted.table.item(0, 1).text() == "Up to date"
        welcome.body = welcome.online
        restarted.refresh()
        assert restarted.status_chip.text().startswith("Online")
        assert "1 computer" in restarted.status_chip.text()
        assert restarted.folder_error.text() == ""
        assert restarted.table.item(0, 0).text() == "Docs"
        assert restarted.table.item(0, 1).text() == "Up to date"
    finally:
        if restarted is not None:
            _close(restarted)
        if window is not None:
            _close(window)
        daemon.stop()
        welcome.stop()
        welcome.join(timeout=3)
        daemon.join(timeout=3)


def _open_seeded_folder(tmp_path: Path, monkeypatch, docs: Path):
    """A joined window whose one folder is ``docs``. The stand-in lists no conflicts."""
    home = tmp_path / "home"
    nodedir = home / "tahoe"
    nodedir.mkdir(parents=True)
    docs.mkdir(parents=True)
    (docs / "note.txt").write_text("hello\n", encoding="utf-8")
    spool = tmp_path / "mf-add.jsonl"
    welcome = _Welcome()
    daemon = _MagicFolder(spool)
    daemon.folders["Docs"] = {
        "path": str(docs),
        "files": [{"relpath": "note.txt", "size": 6, "mtime": 1}],
        "recent": [{"relpath": "note.txt", "conflicted": False}],
        "conflicts": {},
    }
    welcome.start()
    daemon.start()
    _wait_until("http://127.0.0.1:%d/?t=json" % welcome.port)
    _wait_until(
        urllib.request.Request(
            "http://127.0.0.1:%d/v1/magic-folder" % daemon.port,
            headers={"Authorization": "Bearer %s" % daemon.token},
        )
    )
    mf_cfg = home / "magic-folder"
    mf_cfg.mkdir(parents=True)
    (mf_cfg / "api_token").write_text(daemon.token + "\n", encoding="utf-8")
    (mf_cfg / "api_client_endpoint").write_text(
        "tcp:127.0.0.1:%d\n" % daemon.port, encoding="utf-8"
    )
    (nodedir / "node.url").write_text("http://127.0.0.1:%d/\n" % welcome.port, encoding="utf-8")
    (nodedir / "tahoe.cfg").write_text(
        "\n".join(
            [
                "[node]",
                "nickname = alice",
                "[client]",
                "introducer.furl = %s" % FURL,
                "shares.needed = 2",
                "shares.happy = 3",
                "shares.total = 3",
                "[storage]",
                "enabled = false",
                "",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("LEASEGRID_SYNC_HOME", str(home))
    monkeypatch.setenv("LEASEGRID_MF_PORT", str(_free_port()))
    monkeypatch.delenv("LEASEGRID_GATED", raising=False)
    mf_bin = write_executable(tmp_path / "bin", "raise SystemExit(0)\n", name="magic-folder")
    monkeypatch.setenv("LEASEGRID_MAGIC_FOLDER_BIN", mf_bin)
    window = MainWindow(nodedir=nodedir, home=home, autoload=True)
    window.poll.stop()
    window.win.show()
    window.QtWidgets.QApplication.processEvents()
    return window, daemon, welcome


def test_disk_conflict_copy_shows_until_renamed(tmp_path: Path, monkeypatch):
    """A ``.conflict-`` file on disk is a conflict until that copy is renamed.

    The conflicts list is empty and the newest change is not conflicted.
    A nested copy still counts. An ordinary extra file does not. Renaming
    the copy clears the line and keeps the bytes.
    """
    docs = tmp_path / "Docs"
    window, daemon, welcome = _open_seeded_folder(tmp_path, monkeypatch, docs)
    try:
        assert window.stack.currentWidget() is window.main_page
        assert window.table.item(0, 0).text() == "Docs"
        assert _status(window) == "Up to date"
        assert "sync conflict" not in window.folder_error.text()

        notes = docs / "notes"
        notes.mkdir()
        (notes / "draft.txt.bak").write_text("local edit\n", encoding="utf-8")
        window.refresh()
        assert _status(window) == "Up to date"
        assert "sync conflict" not in window.folder_error.text()

        marker = notes / "draft.txt.conflict-laptop"
        marker.write_text("their copy\n", encoding="utf-8")
        with daemon._lock:
            assert daemon.folders["Docs"]["conflicts"] == {}
            assert daemon.folders["Docs"]["recent"] == [
                {"relpath": "note.txt", "conflicted": False}
            ]
        window.refresh()
        assert _status(window) == "Conflict"
        conflict = window.folder_error.text()
        assert "Docs has a sync conflict on notes/draft.txt" in conflict
        assert "rename or remove the conflict copy" in conflict
        assert "\nNext: " in conflict
        assert "pb://" not in conflict
        assert_no_raw_user_text(conflict)

        renamed = notes / "draft-from-laptop.txt"
        marker.rename(renamed)
        window.refresh()
        assert _status(window) == "Up to date"
        assert "sync conflict" not in window.folder_error.text()
        assert renamed.read_text(encoding="utf-8") == "their copy\n"
        assert not marker.exists()
        assert (notes / "draft.txt.bak").read_text(encoding="utf-8") == "local edit\n"
    finally:
        _close(window)
        daemon.stop()
        welcome.stop()
        welcome.join(timeout=3)
        daemon.join(timeout=3)


def test_conflict_outside_recent_changes_stays_conflict(tmp_path: Path):
    """The conflicts list is the whole set. The newest change is not."""
    ctl = MagicFolderCtl(config_dir=tmp_path / "mf", nodedir=tmp_path / "tahoe", mf_bin="/bin/true")
    folder = tmp_path / "Docs"
    folder.mkdir()
    (folder / "note.txt").write_text("hello\n", encoding="utf-8")

    def http_get(path, base=None, timeout=10.0):
        if path.endswith("/file-status"):
            return [{"relpath": "photo.jpg", "size": 1, "mtime": 1}]
        if "recent-changes" in path:
            return [{"relpath": "photo.jpg", "conflicted": False}]
        if path.endswith("/conflicts"):
            return {"note.txt": ["laptop"]}
        return {}

    with patch.object(ctl, "_http_get", side_effect=http_get):
        status, detail = ctl.folder_status("Docs", str(folder))
    assert status == "Conflict"
    assert detail == "note.txt"
