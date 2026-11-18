"""A cut join link fails at once on desktop, before any Tahoe node exists.

Android has refused these since #80 F1. Before this, desktop created a node,
waited for the connect timeout and blamed the network. The fake grid here
always connects, so a cut link that got through would join.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch
from urllib.parse import quote

import pytest

from leasegrid_sync.backend import ConnectionStatus, SyncError, TahoeClient
from leasegrid_sync.invite import parse_invite
from tests.test_sync_backend import GOOD_FURL, _assert_no_raw_failure, _fake_tahoe

# Fakes. Each one is a whole fixture link with a piece missing.
CUT = [
    "pb://hashhashhash@127.0.0.1:45001/",  # cut after the last slash
    "pb://hashhashhash@127.0.0.1:45001/cut",  # swissnum cut short
    "pb://@127.0.0.1:45001/swissnumswiss",  # no tub id
    "pb://hashhashhash/swissnumswiss",  # no location
    "pb://hashhashhash@/swissnumswiss",  # empty location
    "pb://hashhashhash@extra@127.0.0.1:45001/swissnumswiss",  # two @
]

ONLINE = ConnectionStatus(
    state="Connected",
    detail="introducer up · 3 storage",
    introducer_ok=True,
    servers_connected=3,
)


def _forms(furl: str) -> list[str]:
    frag = "v=1&i=%s&n=2&h=3&t=3" % quote(furl, safe="")
    return [furl, "http://leasegrid.i2p/join#" + frag, "leasegrid:join#" + frag]


def _client(tmp_path: Path) -> TahoeClient:
    return TahoeClient(
        nodedir=tmp_path / "home" / "tahoe",
        tahoe_bin=_fake_tahoe(tmp_path),
        home=tmp_path / "home",
    )


@pytest.mark.parametrize("furl", CUT)
def test_cut_link_fails_before_a_node_is_made(tmp_path: Path, furl: str):
    for form in _forms(furl):
        client = _client(tmp_path)
        with patch.object(client, "is_reachable", return_value=True), patch.object(
            client, "wait_connected", return_value=ONLINE
        ) as waited:
            with pytest.raises(SyncError) as exc:
                client.join_invite(form)
        blob = exc.value.banner()
        assert "That join link is cut off." in blob, form
        assert "furl" not in blob.lower()
        assert "Introducer is unreachable" not in blob
        assert "\nNext:" in blob
        assert furl not in blob
        _assert_no_raw_failure(blob)
        assert not client.nodedir.exists(), form
        waited.assert_not_called()


def test_cut_link_then_the_whole_link_joins(tmp_path: Path):
    client = _client(tmp_path)
    with patch.object(client, "is_reachable", return_value=True), patch.object(
        client, "wait_connected", return_value=ONLINE
    ):
        with pytest.raises(SyncError):
            client.join_invite(_forms(CUT[0])[1])
        status = client.join_invite(_forms(GOOD_FURL)[1])
    assert status.state == "Connected"
    cfg = (client.nodedir / "tahoe.cfg").read_text(encoding="utf-8")
    assert GOOD_FURL in cfg


def test_real_shape_furls_still_parse():
    tub = "a" * 32
    swiss = "b" * 32
    for furl in (
        "pb://%s@tcp:grid.example:45001/%s" % (tub, swiss),
        "pb://%s@tcp:10.0.0.2:1,tor:abc.onion:2/%s" % (tub, swiss),
        GOOD_FURL,
        "pb://hashhashhash@127.0.0.1:45001/swissnum",  # 8, the Android bound
    ):
        for form in _forms(furl):
            assert parse_invite(form).token == furl


def test_seven_character_swissnum_is_cut():
    with pytest.raises(SyncError) as exc:
        parse_invite("pb://hashhashhash@127.0.0.1:45001/swissnu")
    assert "That join link is cut off." in exc.value.banner()
