"""U1 backend: join FAIL, furl validation, no WUI path, Magic Folder status parse."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from leasegrid_sync import backend as backend_mod
from leasegrid_sync.backend import (
    MagicFolderCtl,
    SyncError,
    TahoeClient,
    default_home,
    endpoint_to_url,
    fix_joined_shares,
    is_wormhole_code,
    popen_hidden,
    redact_furl,
    storage_offered,
    validate_introducer_furl,
    validate_invite,
    which_bin,
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


def test_popen_hidden_uses_create_no_window_on_windows(monkeypatch):
    seen = {}

    class FakePopen:
        def __init__(self, cmd, **kwargs):
            seen["cmd"] = cmd
            seen["kwargs"] = kwargs

    monkeypatch.setattr("leasegrid_sync.backend.subprocess.Popen", FakePopen)
    monkeypatch.setattr("leasegrid_sync.backend.sys.platform", "win32")
    monkeypatch.setattr("leasegrid_sync.backend.subprocess.CREATE_NO_WINDOW", 0x08000000, raising=False)
    popen_hidden(["tahoe", "run", "x"], log_f=None)
    assert seen["kwargs"]["creationflags"] == 0x08000000
    assert seen["kwargs"]["stdin"] is not None


def test_storage_offered_reads_tahoe_cfg(tmp_path: Path):
    nodedir = tmp_path / "tahoe"
    nodedir.mkdir()
    (nodedir / "tahoe.cfg").write_text("[node]\n[storage]\nenabled = true\n", encoding="utf-8")
    assert storage_offered(nodedir) is True
    (nodedir / "tahoe.cfg").write_text("[node]\n[storage]\nenabled = false\n", encoding="utf-8")
    assert storage_offered(nodedir) is False
    (nodedir / "tahoe.cfg").write_text("[node]\n", encoding="utf-8")
    assert storage_offered(nodedir) is False


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


FAKE_TAHOE = """#!/usr/bin/env python3
import pathlib, sys, time
args = sys.argv[1:]
nodedir = pathlib.Path(args[-1])
if "create-node" in args:
    sub = "create-node"
elif "create-client" in args:
    sub = "create-client"
else:
    sub = args[0]
join = [a for a in args if a.startswith("--join=")]
if sub in ("create-node", "create-client") and join:
    # tahoe 1.20 --join: basedir exists before the wormhole handshake; the
    # invited encoding is written as bytes reprs; a dead code fails non-zero.
    nodedir.mkdir(parents=True)
    if join[0] == "--join=0-dead-code":
        sys.stderr.write("wormhole.errors.LonelyError\\n")
        sys.exit(1)
    (nodedir / "tahoe.cfg").write_text(
        "# argv: " + " ".join(args) + "\\n[node]\\nnickname = alice\\n[client]\\n"
        "introducer.furl =\\nshares.needed = b'2'\\nshares.happy = b'3'\\n"
        "shares.total = b'3'\\n", encoding="utf-8")
elif sub in ("create-node", "create-client"):
    nodedir.mkdir(parents=True)
    (nodedir / "tahoe.cfg").write_text("\\n".join(args), encoding="utf-8")
elif args[0] == "run":
    (nodedir / "node.url").write_text("http://127.0.0.1:1/\\n", encoding="utf-8")
    while True:
        time.sleep(0.2)
"""

GOOD_FURL = "pb://hashhashhash@127.0.0.1:45001/swissnumswiss"


def _fake_tahoe(tmp_path: Path) -> str:
    (tmp_path / "bin").mkdir(exist_ok=True)
    script = tmp_path / "bin" / "tahoe.py"
    script.write_text(FAKE_TAHOE, encoding="utf-8")
    if os.name == "nt":
        # No shebang execution on Windows: a .bat that runs the script with this Python.
        bin_ = tmp_path / "bin" / "tahoe.bat"
        bin_.write_text('@"%s" "%s" %%*\n' % (sys.executable, script), encoding="utf-8")
        return str(bin_)
    bin_ = tmp_path / "bin" / "tahoe"
    bin_.write_text(FAKE_TAHOE, encoding="utf-8")
    bin_.chmod(0o755)
    return str(bin_)


def _welcome_when_node_url(client: TahoeClient):
    """Behave like a live Tahoe: unreachable until `run` has written node.url."""

    def welcome(timeout: float = 5.0):
        if not (client.nodedir / "node.url").is_file():
            raise SyncError("could not join this friendnet. Tahoe client is not reachable.")
        return {
            "introducers": {"statuses": ["Connected to tcp:127.0.0.1:45001 via tcp"]},
            "servers": [{"nickname": "storage-1", "connection_status": "connected"}],
        }

    return welcome


def test_join_invite_creates_node_and_starts_it(tmp_path: Path, monkeypatch):
    """Unpaid join = offer: one create-node, no --no-storage."""
    monkeypatch.setenv("LEASEGRID_SHARES", "2,3,3")
    monkeypatch.delenv("LEASEGRID_STORAGE_HOSTNAME", raising=False)
    nodedir = tmp_path / "home" / "tahoe"
    home = tmp_path / "home"
    client = TahoeClient(nodedir=nodedir, tahoe_bin=_fake_tahoe(tmp_path), home=home)
    try:
        with patch.object(client, "welcome", side_effect=_welcome_when_node_url(client)):
            st = client.join_invite(GOOD_FURL)
        assert st.state == "Connected"
        assert client.owns_process()
        cfg = (nodedir / "tahoe.cfg").read_text(encoding="utf-8")
        assert "create-node" in cfg
        assert "create-client" not in cfg
        assert "--no-storage" not in cfg
        assert "--listen=tcp" in cfg
        assert "--hostname=127.0.0.1" in cfg
        assert "--storage-dir=%s" % (home / "storage") in cfg
        assert "--introducer=%s" % GOOD_FURL in cfg
        assert "--shares-needed=2" in cfg and "--shares-happy=3" in cfg
        assert "--shares-total=3" in cfg
        assert "--webport=tcp:0:interface=127.0.0.1" in cfg
        assert client.log_path.parent == tmp_path / "home" / "logs"
    finally:
        client.stop()
    assert not client.owns_process()


def test_join_invite_accepts_i2p_join_url(tmp_path: Path, monkeypatch):
    from leasegrid_sync.invite import format_join_url

    monkeypatch.setenv("LEASEGRID_SHARES", "1,1,1")
    nodedir = tmp_path / "home" / "tahoe"
    home = tmp_path / "home"
    url = format_join_url(GOOD_FURL, shares=(2, 3, 3), origin="http://alice.i2p/join")
    client = TahoeClient(nodedir=nodedir, tahoe_bin=_fake_tahoe(tmp_path), home=home)
    try:
        with patch.object(client, "welcome", side_effect=_welcome_when_node_url(client)):
            st = client.join_invite(url)
        assert st.state == "Connected"
        cfg = (nodedir / "tahoe.cfg").read_text(encoding="utf-8")
        assert "--introducer=%s" % GOOD_FURL in cfg
        assert "--shares-needed=2" in cfg
        assert "--shares-happy=3" in cfg
        assert "http://alice.i2p" not in cfg
    finally:
        client.stop()


def test_join_invite_opt_out_does_not_offer_storage(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("LEASEGRID_SHARES", "2,3,3")
    nodedir = tmp_path / "home" / "tahoe"
    client = TahoeClient(nodedir=nodedir, tahoe_bin=_fake_tahoe(tmp_path), home=tmp_path / "home")
    try:
        with patch.object(client, "welcome", side_effect=_welcome_when_node_url(client)):
            st = client.join_invite(GOOD_FURL, offer_storage=False)
        assert st.state == "Connected"
        cfg = (nodedir / "tahoe.cfg").read_text(encoding="utf-8")
        assert "create-node" in cfg
        assert "--no-storage" in cfg
        assert "--listen=none" in cfg
        assert "--hostname=" not in cfg
        assert "--storage-dir=" not in cfg
        assert "--introducer=%s" % GOOD_FURL in cfg
    finally:
        client.stop()


def test_storage_hostname_env(monkeypatch):
    from leasegrid_sync.backend import storage_hostname

    monkeypatch.delenv("LEASEGRID_STORAGE_HOSTNAME", raising=False)
    assert storage_hostname() == "127.0.0.1"
    monkeypatch.setenv("LEASEGRID_STORAGE_HOSTNAME", "alice.local")
    assert storage_hostname() == "alice.local"


def test_join_invite_uses_storage_hostname_env(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("LEASEGRID_STORAGE_HOSTNAME", "alice.local")
    nodedir = tmp_path / "home" / "tahoe"
    client = TahoeClient(nodedir=nodedir, tahoe_bin=_fake_tahoe(tmp_path), home=tmp_path / "home")
    try:
        with patch.object(client, "welcome", side_effect=_welcome_when_node_url(client)):
            client.join_invite(GOOD_FURL)
        cfg = (nodedir / "tahoe.cfg").read_text(encoding="utf-8")
        assert "--hostname=alice.local" in cfg
        assert "--listen=tcp" in cfg
        assert "--no-storage" not in cfg
    finally:
        client.stop()


@pytest.mark.parametrize(
    "text, ok",
    [
        ("7-guitarist-revenge", True),
        ("  2-Tradition-Dreadful ", True),  # `tahoe invite` codes are case-insensitive words
        ("123-a-b-c", True),
        ("7-guitarist", False),  # one word: too short to be a wormhole code
        ("guitarist-revenge", False),  # no nameplate
        ("pb://x@127.0.0.1:1/y", False),
        ("", False),
    ],
)
def test_is_wormhole_code(text: str, ok: bool):
    assert is_wormhole_code(text) is ok


def test_validate_invite_accepts_code_or_furl():
    assert validate_invite(" 7-Guitarist-Revenge ") == "7-guitarist-revenge"
    assert validate_invite(GOOD_FURL) == GOOD_FURL
    with pytest.raises(SyncError) as exc:
        validate_invite("7-guitarist")
    assert "short code like 7-word-word" in exc.value.next_hint


def test_fix_joined_shares_rewrites_tahoe_120_bytes_repr(tmp_path: Path):
    cfg = tmp_path / "tahoe.cfg"
    cfg.write_text(
        "[client]\nshares.needed = b'2'\nshares.happy = b'3'\nshares.total = 3\n"
        "nickname = b'keep'\n",
        encoding="utf-8",
    )
    assert fix_joined_shares(cfg) is True
    text = cfg.read_text(encoding="utf-8")
    assert "shares.needed = 2\nshares.happy = 3\nshares.total = 3\n" in text
    assert "nickname = b'keep'" in text  # only share counts are touched
    assert fix_joined_shares(cfg) is False
    assert fix_joined_shares(tmp_path / "missing.cfg") is False


def test_join_wormhole_code_creates_client_via_join(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("LEASEGRID_WORMHOLE_SERVER", "ws://127.0.0.1:45040/v1")
    nodedir = tmp_path / "home" / "tahoe"
    client = TahoeClient(nodedir=nodedir, tahoe_bin=_fake_tahoe(tmp_path), home=tmp_path / "home")
    try:
        with patch.object(client, "welcome", side_effect=_welcome_when_node_url(client)):
            st = client.join_invite(" 7-Guitarist-Revenge ")
        assert st.state == "Connected"
        cfg = (nodedir / "tahoe.cfg").read_text(encoding="utf-8")
        argv = cfg.splitlines()[0]
        assert "--join=7-guitarist-revenge" in argv
        assert "--wormhole-server ws://127.0.0.1:45040/v1 create-node" in argv
        assert "create-client" not in argv
        assert "--no-storage" not in argv
        assert "--listen=tcp" in argv
        assert "--introducer" not in argv and "--shares-needed" not in argv
        # the inviter chooses the encoding; 1.20's b'N' output is repaired
        assert "shares.needed = 2\nshares.happy = 3\nshares.total = 3\n" in cfg
        assert "b'" not in cfg.split("[client]")[1]
        assert "storage.plugins = leasegrid-zkap-v0" in cfg
    finally:
        client.stop()


def test_join_wormhole_dead_code_fails_clean_and_leaves_no_nodedir(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("LEASEGRID_WORMHOLE_SERVER", raising=False)
    nodedir = tmp_path / "home" / "tahoe"
    client = TahoeClient(nodedir=nodedir, tahoe_bin=_fake_tahoe(tmp_path), home=tmp_path / "home")
    with pytest.raises(SyncError) as exc:
        client.join_invite("0-dead-code")
    assert "Invite code 0-dead-code was not accepted" in exc.value.message
    assert "fresh one" in exc.value.next_hint
    # a half-made basedir would make the next Join say "client already exists"
    assert not nodedir.exists()
    assert not client.has_nodedir()


def test_join_existing_starts_stopped_node(tmp_path: Path):
    nodedir = tmp_path / "tahoe"
    nodedir.mkdir()
    (nodedir / "tahoe.cfg").write_text("[node]\n", encoding="utf-8")
    client = TahoeClient(nodedir=nodedir, tahoe_bin=_fake_tahoe(tmp_path), home=tmp_path / "home")
    try:
        with patch.object(client, "welcome", side_effect=_welcome_when_node_url(client)):
            st = client.join_existing()
        assert st.state == "Connected"
        assert client.owns_process()
    finally:
        client.stop()


def test_join_invite_without_tahoe_binary_is_a_clear_fail(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path / "empty-bin"))
    monkeypatch.delenv("LEASEGRID_TAHOE_BIN", raising=False)
    client = TahoeClient(nodedir=tmp_path / "tahoe", home=tmp_path)
    assert client.tahoe_bin is None
    with pytest.raises(SyncError) as exc:
        client.join_invite(GOOD_FURL)
    text = exc.value.banner()
    assert "FAIL" in text
    assert "not installed" in text
    assert "[sync,tahoe]" in text


def test_join_invite_refuses_non_tahoe_dir(tmp_path: Path):
    nodedir = tmp_path / "tahoe"
    nodedir.mkdir()
    (nodedir / "random.txt").write_text("x", encoding="utf-8")
    client = TahoeClient(nodedir=nodedir, tahoe_bin=_fake_tahoe(tmp_path), home=tmp_path)
    with pytest.raises(SyncError) as exc:
        client.join_invite(GOOD_FURL)
    assert "not a Tahoe node" in exc.value.message


def test_default_home_follows_os_conventions(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("LEASEGRID_SYNC_HOME", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "AppData" / "Local"))
    assert default_home("linux") == tmp_path / ".local" / "share" / "leasegrid-sync"
    assert default_home("darwin") == (
        tmp_path / "Library" / "Application Support" / "leasegrid-sync"
    )
    assert default_home("win32") == tmp_path / "AppData" / "Local" / "leasegrid-sync"
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    assert default_home("linux") == tmp_path / "xdg" / "leasegrid-sync"
    monkeypatch.setenv("LEASEGRID_SYNC_HOME", str(tmp_path / "explicit"))
    for plat in ("linux", "darwin", "win32"):
        assert default_home(plat) == tmp_path / "explicit"


def test_which_bin_prefers_frozen_sibling_over_path(tmp_path: Path, monkeypatch):
    """In a bundle the daemons next to our exe win over a system tahoe on PATH."""
    monkeypatch.delenv("LEASEGRID_TAHOE_BIN", raising=False)
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    for name in ("leasegrid-sync", "tahoe.exe"):
        (bundle / name).write_text("#!/bin/sh\n", encoding="utf-8")
        (bundle / name).chmod(0o755)
    system = tmp_path / "usr-bin"
    system.mkdir()
    # shutil.which on Windows only finds PATHEXT names
    sys_tahoe = system / ("tahoe.exe" if os.name == "nt" else "tahoe")
    sys_tahoe.write_text("#!/bin/sh\n", encoding="utf-8")
    sys_tahoe.chmod(0o755)
    monkeypatch.setenv("PATH", str(system))
    # not frozen: PATH wins
    monkeypatch.setattr(backend_mod.sys, "frozen", False, raising=False)
    # Windows' shutil.which returns the PATHEXT spelling (tahoe.EXE)
    assert which_bin("tahoe", "LEASEGRID_TAHOE_BIN").lower() == str(sys_tahoe).lower()
    # frozen: the sibling (with or without .exe) wins
    monkeypatch.setattr(backend_mod.sys, "frozen", True, raising=False)
    monkeypatch.setattr(backend_mod.sys, "executable", str(bundle / "leasegrid-sync"))
    assert which_bin("tahoe", "LEASEGRID_TAHOE_BIN") == str(bundle / "tahoe.exe")
    # frozen but no sibling: fall back to PATH rather than fail
    assert which_bin("magic-folder", "LEASEGRID_MAGIC_FOLDER_BIN") is None
    # explicit env still beats everything
    monkeypatch.setenv("LEASEGRID_TAHOE_BIN", str(sys_tahoe))
    assert which_bin("tahoe", "LEASEGRID_TAHOE_BIN") == str(sys_tahoe)


def test_default_nodedir_order(tmp_path: Path, monkeypatch):
    from leasegrid_sync import backend

    monkeypatch.delenv("LEASEGRID_TAHOE_NODEDIR", raising=False)
    monkeypatch.setenv("LEASEGRID_SYNC_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(backend, "DEFAULT_TAHOE_NODEDIR", tmp_path / "dot-tahoe")
    assert backend.default_nodedir() == tmp_path / "home" / "tahoe"
    (tmp_path / "dot-tahoe").mkdir()
    (tmp_path / "dot-tahoe" / "tahoe.cfg").write_text("[node]\n", encoding="utf-8")
    assert backend.default_nodedir() == tmp_path / "dot-tahoe"
    monkeypatch.setenv("LEASEGRID_TAHOE_NODEDIR", str(tmp_path / "explicit"))
    assert backend.default_nodedir() == tmp_path / "explicit"


def test_shares_config_env(monkeypatch):
    from leasegrid_sync.backend import DEFAULT_SHARES, shares_config

    monkeypatch.delenv("LEASEGRID_SHARES", raising=False)
    assert shares_config() == DEFAULT_SHARES
    monkeypatch.setenv("LEASEGRID_SHARES", "3,5,7")
    assert shares_config() == (3, 5, 7)
    monkeypatch.setenv("LEASEGRID_SHARES", "garbage")
    assert shares_config() == DEFAULT_SHARES
    monkeypatch.setenv("LEASEGRID_SHARES", "5,3,1")
    assert shares_config() == DEFAULT_SHARES


def test_ensure_credit_plugin_edits_cfg_once(tmp_path: Path):
    nodedir = tmp_path / "tahoe"
    nodedir.mkdir()
    (nodedir / "tahoe.cfg").write_text(
        "[node]\nnickname = x\n\n[client]\n# comment kept\nintroducer.furl =\n"
        "shares.needed = 2\n\n[storage]\nenabled = false\n",
        encoding="utf-8",
    )
    home = tmp_path / "home"
    client = TahoeClient(nodedir=nodedir, tahoe_bin="/bin/true", home=home)
    assert client.ensure_credit_plugin() is True
    text = (nodedir / "tahoe.cfg").read_text(encoding="utf-8")
    assert "# comment kept" in text
    client_section = text.split("[client]", 1)[1].split("[storage]", 1)[0]
    assert "storage.plugins = leasegrid-zkap-v0" in client_section
    assert "[storageclient.plugins.leasegrid-zkap-v0]" in text
    assert "wallet-path = %s" % (home / "credit-wallet.json") in text
    assert "recent-path = %s" % (home / "credit-recent.json") in text
    assert client.ensure_credit_plugin() is False  # idempotent
    assert text == (nodedir / "tahoe.cfg").read_text(encoding="utf-8")
    import configparser

    cfg = configparser.ConfigParser()
    cfg.read(nodedir / "tahoe.cfg")
    assert cfg.get("client", "storage.plugins") == "leasegrid-zkap-v0"
    assert cfg.getboolean("client", "force_foolscap") is True


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
