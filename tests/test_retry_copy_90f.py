"""#90 slice F: Design's Retry rule (1:40am PT copy).

Retry shows only after a network or unreachable error, and only on a control
that reruns the same action. Never after a bad, cut-off or invalid link.

Fake servers only: an unused local port is the unreachable storage server, a
local listener is the reachable one, and a fake `tahoe` binary is the join that
cannot reach the grid.
"""

from __future__ import annotations

import os
import re
import socket
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from leasegrid_sync import backend as backend_mod  # noqa: E402
from leasegrid_sync import servers as servers_mod  # noqa: E402
from leasegrid_sync.backend import (  # noqa: E402
    INVALID_CODE_MSG,
    INVALID_CODE_NEXT,
    SyncError,
    join_process_failure,
    join_spawn_failure,
)

STORAGE_MSG = "Couldn't reach the storage server."
STORAGE_NEXT = "Check that the server is running and this computer is online, then click Retry."
JOIN_MSG = "Couldn't join the shared folder."
JOIN_NEXT = (
    "Check that this computer is online and that the person who invited you has Leasegrid Sync "
    "open, then click Retry. If it still fails, ask them for a new join link."
)
JOIN_FURL = "pb://hashhashhash@127.0.0.1:45001/swissnumswiss"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _storage_link(port: int) -> str:
    return "pb://hashhashhash@127.0.0.1:%d/swissnumswiss" % port


def _network_join_errors() -> list[SyncError]:
    timeout = subprocess.TimeoutExpired(cmd=["tahoe"], timeout=5)
    return [
        join_process_failure("7-alpha-bravo", "ConnectionRefusedError: connection refused", code=True),
        join_process_failure(JOIN_FURL, "twisted ... Connection refused", code=False),
        join_spawn_failure(timeout, invite="7-alpha-bravo", code=True, timeout=5),
        join_spawn_failure(timeout, invite=JOIN_FURL, code=False, timeout=5),
    ]


# Guard ---------------------------------------------------------------------


def test_unreachable_storage_server_is_designs_pair():
    assert servers_mod.UNREACHABLE == STORAGE_MSG
    assert servers_mod.UNREACHABLE_NEXT == STORAGE_NEXT


@pytest.mark.parametrize("index", range(4))
def test_network_join_failures_are_designs_pair(index: int):
    err = _network_join_errors()[index]
    assert (err.message, err.next_hint) == (JOIN_MSG, JOIN_NEXT)
    assert getattr(err, "retryable", False) is True


def test_join_that_reaches_no_introducer_is_designs_pair(tmp_path: Path):
    nodedir = tmp_path / "tahoe"
    nodedir.mkdir()
    (nodedir / "tahoe.cfg").write_text("[node]\n", encoding="utf-8")
    client = backend_mod.TahoeClient(nodedir=nodedir, home=tmp_path, tahoe_bin="")
    offline = backend_mod.ConnectionStatus(state="Offline", detail="introducer not connected")
    with patch.object(client, "is_reachable", return_value=True), \
         patch.object(client, "wait_connected", return_value=offline):
        with pytest.raises(SyncError) as exc:
            client.join_existing()
    assert (exc.value.message, exc.value.next_hint) == (JOIN_MSG, JOIN_NEXT)


def _rule_hints() -> list[tuple[str, str, bool]]:
    """(message, next, network?) for every hint this rule covers."""
    out = [
        (servers_mod.UNREACHABLE, servers_mod.UNREACHABLE_NEXT, True),
        (servers_mod.ADD_FAIL, servers_mod.ADD_FAIL_NEXT, False),
        (INVALID_CODE_MSG, INVALID_CODE_NEXT, False),
    ]
    out += [(e.message, e.next_hint, True) for e in _network_join_errors()]
    for raw in ("", "https://example.invalid/", "not-a-code", "pb://abc", "pb://tub@host:1"):
        try:
            backend_mod.validate_introducer_furl(raw)
        except SyncError as exc:
            out.append((exc.message, exc.next_hint, False))
    for raw in ("http://x/", "pb://x", "pb://t@127.0.0.1:1"):
        try:
            servers_mod.parse_storage_furl(raw)
        except SyncError as exc:
            out.append((exc.message, exc.next_hint, False))
    return out


def test_retry_only_in_network_pairs_and_no_host_or_slash():
    hints = _rule_hints()
    assert len(hints) >= 12
    for message, nxt, network in hints:
        text = message + " " + nxt
        if network:
            assert "Retry" in nxt, nxt
        else:
            assert "retry" not in text.lower(), text
        if network:
            assert "/" not in text, text
            assert not re.search(r"\bhosts?\b", text, re.I), text


# Behavior: storage dialog ---------------------------------------------------


@pytest.fixture
def window(tmp_path: Path):
    pytest.importorskip("PyQt5")
    from leasegrid_sync.app import MainWindow

    nodedir = tmp_path / "home" / "tahoe"
    nodedir.mkdir(parents=True)
    (nodedir / "tahoe.cfg").write_text("[node]\n", encoding="utf-8")
    win = MainWindow(nodedir=nodedir, home=tmp_path / "home", autoload=False)
    win.poll.stop()
    return win


def _dialog(window):
    from leasegrid_sync.app import AddStorageServerDialog

    dlg = AddStorageServerDialog(window.win, window, window.QtWidgets)
    dlg.paste_radio.setChecked(True)
    return dlg


def _log_text(window) -> str:
    logs = Path(window.home) / "logs"
    return "".join(p.read_text(encoding="utf-8") for p in logs.glob("*.log*")) if logs.is_dir() else ""


def test_unreachable_server_makes_add_retry_and_retry_reruns_until_success_restores_add(window):
    dlg = _dialog(window)
    port = _free_port()
    dlg.furl_edit.setText(_storage_link(port))
    dlg.add_btn.click()
    assert dlg.add_btn.text() == "Retry"
    assert STORAGE_MSG in dlg.error.text()
    assert "Next: " + STORAGE_NEXT in dlg.error.text()
    assert not servers_mod.servers_path(window.home).exists()
    with socket.socket() as srv:
        srv.bind(("127.0.0.1", port))
        srv.listen(4)
        with patch.object(window.tahoe, "reload_static_servers", return_value=None):
            dlg.add_btn.click()
    assert dlg.add_btn.text() == "Add server"
    assert dlg.dlg.result() == window.QtWidgets.QDialog.Accepted
    pins = servers_mod.load_book(window.home)["pins"]
    assert [p["furl"] for p in pins] == [_storage_link(port)]


def test_editing_the_link_after_an_unreachable_error_puts_add_back(window):
    from PyQt5.QtTest import QTest

    dlg = _dialog(window)
    dlg.furl_edit.setText(_storage_link(_free_port()))
    dlg.add_btn.click()
    assert dlg.add_btn.text() == "Retry"
    QTest.keyClicks(dlg.furl_edit, "x")
    assert dlg.add_btn.text() == "Add server"


@pytest.mark.parametrize("link", ["pb://hashhashhash@127.0.0.1:9", "http://127.0.0.1:3456/", "pb://x"])
def test_an_invalid_link_keeps_add_with_no_retry_and_saves_nothing(window, link: str):
    dlg = _dialog(window)
    dlg.furl_edit.setText(_storage_link(_free_port()))
    dlg.add_btn.click()
    assert dlg.add_btn.text() == "Retry"
    dlg.furl_edit.setText(link)
    with patch("socket.create_connection") as connect:
        dlg.add_btn.click()
    assert not connect.called
    assert dlg.add_btn.text() == "Add server"
    shown = dlg.error.text()
    assert servers_mod.ADD_FAIL in shown and servers_mod.ADD_FAIL_NEXT in shown
    assert "Retry" not in shown
    assert not servers_mod.servers_path(window.home).exists()
    assert not (window.tahoe.nodedir / "private" / "servers.yaml").exists()


def test_repeated_storage_retries_show_the_same_pair_and_log_the_real_error(window):
    dlg = _dialog(window)
    dlg.furl_edit.setText(_storage_link(_free_port()))
    shown = []
    for _ in range(3):
        dlg.add_btn.click()
        shown.append(dlg.error.text())
        assert dlg.add_btn.text() == "Retry"
    assert len(set(shown)) == 1
    for bad in ("Errno", "refused", "127.0.0.1", "pb://", "1", "2", "3", "attempt"):
        assert bad not in shown[0], bad
    log = _log_text(window)
    assert "add-storage" in log
    assert "Error" in log
    assert "swissnumswiss" not in log


# Behavior: join -------------------------------------------------------------


def _fake_tahoe(tmp_path: Path) -> str:
    from tests.qr_decode import write_executable

    body = "\n".join(
        [
            "import sys",
            "sys.stderr.write('Traceback: ConnectionRefusedError: [Errno 111] Connection refused '",
            "                 'reaching pb://hashhashhash@127.0.0.1:45001/swissnumswiss\\n')",
            "raise SystemExit(1)",
        ]
    )
    return write_executable(tmp_path / "fakebin", body, name="tahoe")


def test_unreachable_join_shows_the_pair_and_retry_rejoins(tmp_path: Path):
    pytest.importorskip("PyQt5")
    from leasegrid_sync.app import MainWindow

    home = tmp_path / "home"
    window = MainWindow(nodedir=home / "tahoe", home=home, autoload=False)
    window.poll.stop()
    window.tahoe.tahoe_bin = _fake_tahoe(tmp_path)
    window.threat_ack.setChecked(True)
    window.offer_storage_cb.setChecked(False)
    window.invite_edit.setText(JOIN_FURL)
    shown = []
    for _ in range(3):
        window.join_btn.click()
        shown.append(window.join_error.text())
        assert window.join_btn.text() == "Retry"
        assert window.invite_edit.text() == JOIN_FURL
        assert not (home / "tahoe").exists()
    assert len(set(shown)) == 1
    assert JOIN_MSG in shown[0] and "Next: " + JOIN_NEXT in shown[0]
    for bad in ("Errno", "refused", "Traceback", "pb://", "127.0.0.1", "1", "2", "3"):
        assert bad not in shown[0], bad
    log = _log_text(window)
    assert "Connection refused" in log
    assert "swissnumswiss" not in log
    ok = backend_mod.ConnectionStatus(state="Connected", detail="introducer up", introducer_ok=True)
    with patch.object(window.tahoe, "join_invite", return_value=ok) as rejoin, \
         patch.object(window, "_enter_main") as entered:
        window.join_btn.click()
    rejoin.assert_called_once()
    assert rejoin.call_args.args[0] == JOIN_FURL
    entered.assert_called_once()
    assert window.join_btn.text() == "Join friendnet"


def test_a_cut_join_link_keeps_the_join_label_and_no_retry(tmp_path: Path):
    pytest.importorskip("PyQt5")
    from leasegrid_sync.app import MainWindow

    home = tmp_path / "home"
    window = MainWindow(nodedir=home / "tahoe", home=home, autoload=False)
    window.poll.stop()
    window.tahoe.tahoe_bin = _fake_tahoe(tmp_path)
    window.threat_ack.setChecked(True)
    window.offer_storage_cb.setChecked(False)
    window.invite_edit.setText(JOIN_FURL)
    window.join_btn.click()
    assert window.join_btn.text() == "Retry"
    window.invite_edit.setText("pb://hashhashhash@127.0.0.1")
    window.join_btn.click()
    assert window.join_btn.text() == "Join friendnet"
    assert "Retry" not in window.join_error.text()
