"""U1 backend: join FAIL, furl validation, no WUI path, Magic Folder status parse."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from leasegrid_sync.backend import (
    MagicFolderCtl,
    SyncError,
    TahoeClient,
    endpoint_to_url,
    redact_furl,
    validate_introducer_furl,
)


def test_validate_empty_invite_fails():
    with pytest.raises(SyncError) as exc:
        validate_introducer_furl("  ")
    assert "FAIL" in exc.value.banner()
    assert "pb://" in exc.value.banner()
    assert "web UI" not in exc.value.banner().lower() or "does not use the Tahoe web UI" in exc.value.banner()


def test_validate_http_url_is_not_wui_cta():
    with pytest.raises(SyncError) as exc:
        validate_introducer_furl("http://127.0.0.1:3456/")
    text = exc.value.banner()
    assert "does not use the Tahoe web UI" in text
    assert "Open web UI" not in text
    assert "use the web UI" not in text.lower()


def test_validate_good_furl():
    furl = "pb://hashhashhash@10.42.0.70:42831/swissnumswiss"
    assert validate_introducer_furl(furl) == furl


def test_redact_furl_does_not_leak():
    furl = "pb://secrethashvalue@10.42.0.70:42831/swissnum"
    out = redact_furl(furl)
    assert "secrethashvalue" not in out
    assert out.startswith("pb://")


def test_endpoint_to_url():
    assert endpoint_to_url("tcp:127.0.0.1:19780") == "http://127.0.0.1:19780"
    with pytest.raises(SyncError):
        endpoint_to_url("not running")


def test_join_existing_missing_nodedir(tmp_path: Path):
    client = TahoeClient(nodedir=tmp_path / "missing")
    with pytest.raises(SyncError) as exc:
        client.join_existing()
    assert "FAIL" in exc.value.banner()


def test_join_existing_connected(tmp_path: Path):
    nodedir = tmp_path / "tahoe"
    nodedir.mkdir()
    (nodedir / "tahoe.cfg").write_text("[node]\n", encoding="utf-8")
    (nodedir / "node.url").write_text("http://127.0.0.1:3456/\n", encoding="utf-8")
    welcome = {
        "introducers": {"statuses": ["Connected to tcp:10.42.0.70:42831 via tcp"]},
        "servers": [
            {"nickname": "maximum", "connection_status": "connected"},
            {"nickname": "leasegrid-2", "connection_status": "connected"},
        ],
    }
    client = TahoeClient(nodedir=nodedir)
    with patch.object(TahoeClient, "welcome", return_value=welcome):
        st = client.join_existing()
    assert st.state == "Connected"
    assert st.introducer_ok
    assert st.servers_connected == 2


def test_join_invite_garbage(tmp_path: Path):
    client = TahoeClient(nodedir=tmp_path / "none")
    with pytest.raises(SyncError) as exc:
        client.join_invite("not-a-code")
    assert "invalid" in exc.value.message.lower()


def test_add_folder_bad_path(tmp_path: Path):
    ctl = MagicFolderCtl(config_dir=tmp_path / "mf", nodedir=tmp_path / "tahoe", mf_bin="/bin/true")
    with pytest.raises(SyncError) as exc:
        ctl.add_folder(str(tmp_path / "no-such-dir"))
    assert "FAIL" in exc.value.banner()
    assert "folder not added" in exc.value.banner()


def test_add_folder_missing_magic_folder_bin(tmp_path: Path):
    folder = tmp_path / "docs"
    folder.mkdir()
    ctl = MagicFolderCtl(config_dir=tmp_path / "mf", nodedir=tmp_path / "tahoe", mf_bin=None)
    with pytest.raises(SyncError) as exc:
        ctl.add_folder(str(folder))
    assert "not installed" in exc.value.banner().lower() or "missing" in exc.value.banner().lower()


def test_list_folders_parses_api(tmp_path: Path):
    cfg = tmp_path / "mf"
    cfg.mkdir()
    (cfg / "api_token").write_text("dGVzdC10b2tlbi10aGF0LWlzLTMyYnl0ZXMh", encoding="utf-8")
    (cfg / "api_client_endpoint").write_text("tcp:127.0.0.1:19780\n", encoding="utf-8")
    ctl = MagicFolderCtl(config_dir=cfg, nodedir=tmp_path, mf_bin="/bin/true")
    payload = {
        "Photos": {
            "magic_path": "/tmp/Photos",
            "poll_interval": 5,
            "author": {"name": "nimo"},
        }
    }

    def fake_get(path, base=None, timeout=10.0):
        if path == "/v1/magic-folder":
            return payload
        if path.endswith("/file-status"):
            return [{"relpath": "hi.txt", "size": 4, "mtime": 1}]
        if "recent-changes" in path:
            return [{"relpath": "hi.txt", "modified": 1, "last-updated": 1, "conflicted": False}]
        return {}

    with patch.object(MagicFolderCtl, "ensure_running", return_value=None):
        with patch.object(MagicFolderCtl, "_http_get", side_effect=fake_get):
            rows = ctl.list_folders()
    assert len(rows) == 1
    assert rows[0].name == "Photos"
    assert rows[0].path == "/tmp/Photos"
    assert rows[0].status == "Up to date"


def test_welcome_json_roundtrip_shape():
    raw = json.dumps(
        {
            "introducers": {"statuses": ["Connected to tcp:10.42.0.70:42831 via tcp"]},
            "servers": [{"nickname": "maximum", "connection_status": "connected"}],
        }
    )
    data = json.loads(raw)
    assert "introducers" in data
