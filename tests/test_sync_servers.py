"""Buyer storage roster: Join-first helpers, bad furl FAIL, local Disconnect."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from leasegrid_sync.backend import SyncError
from leasegrid_sync.servers import (
    ADD_FAIL,
    SERVERS_HONESTY,
    add_storage_server,
    disconnect_copy,
    disconnect_server,
    load_book,
    roster,
    use_available_server,
)

FURL = "pb://hashhashhash@127.0.0.1:9/swissnumswiss"


def _node(tmp_path: Path) -> tuple[Path, Path]:
    home = tmp_path / "home"
    nodedir = home / "tahoe"
    nodedir.mkdir(parents=True)
    (nodedir / "tahoe.cfg").write_text("[node]\n", encoding="utf-8")
    return home, nodedir


def test_bad_storage_furl_fails_without_writing_a_pin(tmp_path: Path):
    home, nodedir = _node(tmp_path)
    with pytest.raises(SyncError) as exc:
        add_storage_server(home, nodedir, "http://127.0.0.1:3456/")
    assert ADD_FAIL in exc.value.message
    assert "Retry" in exc.value.next_hint
    banner = exc.value.banner().lower()
    assert "fail" in banner
    assert "forever" not in banner
    assert "web ui" not in banner
    assert not (home / "servers.json").exists()
    assert not (nodedir / "private" / "servers.yaml").exists()


def test_unreachable_storage_furl_fails(tmp_path: Path):
    home, nodedir = _node(tmp_path)
    with pytest.raises(SyncError) as exc:
        add_storage_server(
            home,
            nodedir,
            "pb://hashhashhash@127.0.0.1:1/swissnumswiss",
            timeout=0.4,
        )
    text = exc.value.banner().lower()
    assert "could not add this storage server" in text
    assert "unreachable" in text
    assert "forever" not in text
    assert not (home / "servers.json").exists()


def test_disconnect_is_local_only_and_can_be_seen_again(tmp_path: Path):
    home, nodedir = _node(tmp_path)
    copy = disconnect_copy("home-nas")
    lowered = copy.lower()
    assert "this sync home" in lowered
    assert "for everyone" in lowered
    assert "already stored" in lowered
    assert "forever" not in lowered
    assert "permanently" not in lowered
    assert "forever" not in SERVERS_HONESTY.lower()

    with patch("leasegrid_sync.servers.probe_storage_furl"):
        row = add_storage_server(home, nodedir, FURL, "home-nas")
    yaml_path = nodedir / "private" / "servers.yaml"
    assert FURL in yaml_path.read_text(encoding="utf-8")
    assert load_book(home)["pins"][0]["furl"] == FURL

    disconnect_server(home, nodedir, row.key, name=row.name)
    book = load_book(home)
    assert book["pins"] == []
    assert FURL not in yaml_path.read_text(encoding="utf-8")
    assert "home-nas" in book["forgotten"]

    announced = [
        {
            "nickname": "home-nas",
            "nodeid": "v0-abc",
            "connection_status": "connected",
        }
    ]
    used, available = roster(home, announced)
    assert used == []
    assert available[0].source == "Seen again"
    assert "Not used until you Add" in available[0].note
    assert available[0].section == "available"

    use_available_server(home, nodedir, available[0].key, available[0].name)
    used_again, available_again = roster(home, announced)
    assert any(item.name == "home-nas" and item.section == "used" for item in used_again)
    assert available_again == []
    # Restoring the pin puts the storage furl back; still only this home's file.
    assert FURL in yaml_path.read_text(encoding="utf-8")


def test_announced_connected_server_is_on_the_roster(tmp_path: Path):
    home, _nodedir = _node(tmp_path)
    used, available = roster(
        home,
        [
            {
                "nickname": "friend-laptop",
                "nodeid": "v0-abc",
                "connection_status": "Connected to tcp:127.0.0.1:9",
            }
        ],
    )
    assert len(used) == 1
    assert used[0].name == "friend-laptop"
    assert used[0].status == "Connected"
    assert used[0].source == "Announced"
    assert available == []
