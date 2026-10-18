"""U1 backend: join FAIL, furl validation, no WUI path, Magic Folder status parse."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from leasegrid_sync import backend as backend_mod
from leasegrid_sync.app import display_path
from tests.buyer_text import POISON, assert_no_raw_user_text
from leasegrid_sync.backend import (
    ConnectionStatus,
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
    monkeypatch.setattr(
        "leasegrid_sync.backend.subprocess.CREATE_NEW_PROCESS_GROUP", 0x00000200, raising=False
    )
    popen_hidden(["tahoe", "run", "x"], log_f=None)
    flags = seen["kwargs"]["creationflags"]
    assert flags & 0x08000000
    assert flags & 0x00000200
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
    assert st.announced_servers[0]["nickname"] == "maximum"
    assert st.announced_servers[1]["connection_status"] == "connected"


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
if sub in ("create-node", "create-client"):
    # Real tahoe refuses a basedir that is already there. --join creates the
    # folder before the handshake, so a dead code leaves it behind unless the
    # caller deletes it. The next create then fails.
    if nodedir.exists():
        sys.stderr.write("The base directory already exists: %s\\n" % nodedir)
        sys.exit(1)
    nodedir.mkdir(parents=True)
    if join and join[0] == "--join=0-dead-code":
        sys.stderr.write("Traceback (most recent call last):\\n")
        sys.stderr.write("wormhole.errors.LonelyError\\n")
        sys.exit(1)
    if join and join[0] == "--join=3-bad-code":
        sys.stderr.write("wormhole.errors.WrongPasswordError\\n")
        sys.exit(1)
    if join and join[0] == "--join=1-net-down":
        sys.stderr.write("ConnectionRefusedError: [Errno 111] Connection refused\\n")
        sys.exit(1)
    if join and join[0] == "--join=9-weird-error":
        sys.stderr.write("foo.bar.WeirdError: secret-ish detail\\n")
        sys.exit(1)
    if any(a.startswith("--introducer=pb://weird") for a in args):
        sys.stderr.write("foo.bar.WeirdError: secret-ish detail\\n")
        sys.exit(1)
    if any(a.startswith("--introducer=pb://bad") for a in args):
        sys.stderr.write("Traceback (most recent call last):\\n")
        sys.stderr.write("ValueError: shares.needed\\n")
        sys.exit(1)
    if join:
        # tahoe 1.20 --join writes the invited encoding as bytes reprs.
        (nodedir / "tahoe.cfg").write_text(
            "# argv: " + " ".join(args) + "\\n[node]\\nnickname = alice\\n[client]\\n"
            "introducer.furl =\\nshares.needed = b'2'\\nshares.happy = b'3'\\n"
            "shares.total = b'3'\\n", encoding="utf-8")
    else:
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


def _assert_no_raw_failure(text: str) -> None:
    assert "wormhole." not in text
    assert "Error" not in text
    assert "Traceback" not in text


def test_join_wormhole_dead_code_fails_clean_and_leaves_no_nodedir(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("LEASEGRID_WORMHOLE_SERVER", raising=False)
    nodedir = tmp_path / "home" / "tahoe"
    client = TahoeClient(nodedir=nodedir, tahoe_bin=_fake_tahoe(tmp_path), home=tmp_path / "home")
    with pytest.raises(SyncError) as exc:
        client.join_invite("0-dead-code")
    blob = exc.value.banner()
    assert "expire" in blob.lower()
    assert "not accepted" not in blob.lower()
    _assert_no_raw_failure(blob)
    assert "fresh one" in exc.value.next_hint
    # The fake refuses a basedir that is already there, so a leftover folder
    # fails the next create. Cleanup is what lets the retry connect.
    assert not nodedir.exists()
    assert not client.has_nodedir()
    try:
        with patch.object(client, "welcome", side_effect=_welcome_when_node_url(client)):
            st = client.join_invite("7-guitarist-revenge")
        assert st.state == "Connected"
    finally:
        client.stop()


def test_join_errors_distinguish_expired_rejected_and_network(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("LEASEGRID_WORMHOLE_SERVER", raising=False)
    nodedir = tmp_path / "home" / "tahoe"
    client = TahoeClient(nodedir=nodedir, tahoe_bin=_fake_tahoe(tmp_path), home=tmp_path / "home")
    seen = {}
    for code, needle in (
        ("0-dead-code", "expire"),
        ("3-bad-code", "not accepted"),
        ("1-net-down", "mailbox"),
    ):
        with pytest.raises(SyncError) as exc:
            client.join_invite(code)
        blob = exc.value.banner()
        assert needle in blob.lower()
        _assert_no_raw_failure(blob)
        assert not nodedir.exists()
        seen[code] = exc.value.message
    assert len(set(seen.values())) == 3
    assert "expire" not in seen["3-bad-code"].lower()
    assert "not accepted" not in seen["0-dead-code"].lower()
    assert "mailbox" not in seen["0-dead-code"].lower()


def _assert_no_spawn_leak(text: str, *banned: str) -> None:
    """Join banners never carry an exception class, a module, or a path."""
    for needle in (
        "FileNotFoundError",
        "TimeoutExpired",
        "OSError",
        "Traceback",
        "No such file",
        "timed out after",
        "Errno",
        "foo.bar",
        "WeirdError",
        "secret-ish",
    ):
        assert needle not in text
    for item in banned:
        assert item not in text


def test_join_missing_tahoe_is_friendly(tmp_path: Path):
    """A path that is not a binary, and a start of an existing node, stay friendly."""
    missing = tmp_path / "missing-bin" / "tahoe"
    home = tmp_path / "home"
    fresh = TahoeClient(nodedir=home / "tahoe", tahoe_bin=str(missing), home=home)
    with pytest.raises(SyncError) as exc:
        fresh.join_invite(GOOD_FURL)
    blob = exc.value.banner()
    assert "not installed" in blob
    assert "[sync,tahoe]" in blob
    _assert_no_spawn_leak(blob, str(missing), str(home))

    nodedir = tmp_path / "existing" / "tahoe"
    nodedir.mkdir(parents=True)
    (nodedir / "tahoe.cfg").write_text("[node]\n", encoding="utf-8")
    started = TahoeClient(nodedir=nodedir, tahoe_bin=str(missing), home=home)
    with pytest.raises(SyncError) as exc:
        started.join_invite(GOOD_FURL)
    blob = exc.value.banner()
    assert "not installed" in blob
    _assert_no_spawn_leak(blob, str(missing))


def test_join_timeout_is_friendly(tmp_path: Path, monkeypatch):
    """TimeoutExpired from create-node is not copied into the banner."""
    raw_token = str(tmp_path / "raw-exc-token" / "tahoe")

    def raise_timeout(cmd, **kwargs):
        raise subprocess.TimeoutExpired(
            cmd=[raw_token, *list(cmd)], timeout=kwargs.get("timeout", 1)
        )

    monkeypatch.setattr("leasegrid_sync.backend.subprocess.run", raise_timeout)
    home = tmp_path / "home"
    client = TahoeClient(nodedir=home / "tahoe", tahoe_bin=raw_token, home=home)
    with pytest.raises(SyncError) as exc:
        client.join_invite(GOOD_FURL)
    blob = exc.value.banner()
    assert "did not finish" in blob
    assert "network path" in blob
    _assert_no_spawn_leak(blob, raw_token, GOOD_FURL, str(home))

    code = "7-guitarist-revenge"
    with pytest.raises(SyncError) as exc:
        client.join_invite(code)
    blob = exc.value.banner()
    assert "Nobody answered" in blob
    assert code in blob
    _assert_no_spawn_leak(blob, raw_token, str(home))


def test_join_unrecognised_stderr_is_never_echoed(tmp_path: Path, monkeypatch):
    """A stderr line we do not recognise is not copied into the buyer banner."""
    monkeypatch.delenv("LEASEGRID_WORMHOLE_SERVER", raising=False)
    home = tmp_path / "home"
    nodedir = home / "tahoe"
    client = TahoeClient(nodedir=nodedir, tahoe_bin=_fake_tahoe(tmp_path), home=home)
    with pytest.raises(SyncError) as exc:
        client.join_invite("9-weird-error")
    blob = exc.value.banner()
    assert "not accepted" in blob
    assert "secret-ish detail" not in blob
    assert "foo.bar.WeirdError" not in blob
    _assert_no_raw_failure(blob)
    _assert_no_spawn_leak(blob)
    assert not nodedir.exists()

    weird = "pb://weirdweirdweir@127.0.0.1:9/swissnumswiss"
    with pytest.raises(SyncError) as exc:
        client.join_invite(weird)
    blob = exc.value.banner()
    assert "could not create a node" in blob
    assert "secret-ish detail" not in blob
    assert "foo.bar.WeirdError" not in blob
    _assert_no_raw_failure(blob)
    _assert_no_spawn_leak(blob, weird)
    assert not nodedir.exists()


# Furl shape, not a prefix check alone: tub id, host:port, swissnum.
_FURL_SHAPE = re.compile(r"pb://[^\s/]+@[^\s/]+/[^\s]+", re.IGNORECASE)
_EXC_CLASS = re.compile(r"\b[A-Za-z_][\w.]*(?:Error|Exception)\b")


def _assert_join_phrase_once(text: str) -> None:
    assert text.lower().count("could not join this friendnet.") <= 1


def _exit_immediately_tahoe(tmp_path: Path) -> str:
    script = tmp_path / "exit_tahoe.py"
    script.write_text("import sys\nsys.exit(1)\n", encoding="utf-8")
    if os.name == "nt":
        bat = tmp_path / "exit_tahoe.bat"
        bat.write_text('@"%s" "%s" %%*\n' % (sys.executable, script), encoding="utf-8")
        return str(bat)
    bin_ = tmp_path / "exit_tahoe"
    bin_.write_text("#!%s\nimport sys\nsys.exit(1)\n" % sys.executable, encoding="utf-8")
    bin_.chmod(0o755)
    return str(bin_)


def test_start_log_tail_is_not_shown(tmp_path: Path):
    """A crashed `tahoe run` must not paste tahoe.log into the buyer text."""
    home = tmp_path / "home"
    nodedir = home / "tahoe"
    nodedir.mkdir(parents=True)
    (nodedir / "tahoe.cfg").write_text("[node]\n", encoding="utf-8")
    log = home / "logs" / "tahoe.log"
    log.parent.mkdir(parents=True)
    # Obviously fake. The window must not grow this line back.
    seeded = "pb://FAKE-TUBID@127.0.0.1:1/FAKE-SWISS"
    log.write_text(
        "Traceback (most recent call last):\n"
        '  File "/opt/fake-tahoe/src/allmydata/node.py", line 3, in start\n'
        "RuntimeError: introducer failed\n" + seeded + "\n",
        encoding="utf-8",
    )
    client = TahoeClient(nodedir=nodedir, tahoe_bin=_exit_immediately_tahoe(tmp_path), home=home)
    with pytest.raises(SyncError) as exc:
        client.start(timeout=3)
    blob = exc.value.banner()
    assert "Tahoe exited while starting" in blob
    assert "pb://" not in blob
    assert _FURL_SHAPE.search(blob) is None
    assert "Traceback" not in blob
    assert _EXC_CLASS.search(blob) is None
    assert "allmydata" not in blob
    assert seeded not in blob
    _assert_join_phrase_once(blob)


def test_magic_folder_exit_log_tail_is_not_shown(tmp_path: Path, monkeypatch):
    """A Magic Folder daemon that exits must not paste its log into the buyer text."""
    monkeypatch.setattr(backend_mod, "_port_free", lambda _port, host="127.0.0.1": True)
    home = tmp_path / "home"
    config = home / "magic-folder"
    config.mkdir(parents=True)
    (config / "api_token").write_text("not-a-secret\n", encoding="utf-8")
    log = home / "logs" / "magic-folder.log"
    log.parent.mkdir(parents=True)
    # Obviously fake. The window must not grow this line back.
    seeded = "pb://FAKE-TUBID@127.0.0.1:1/FAKE-SWISS"
    log.write_text(
        "Traceback (most recent call last):\n"
        '  File "mf.py", line 1, in run\n'
        "RuntimeError: daemon failed\n" + seeded + "\n",
        encoding="utf-8",
    )
    ctl = MagicFolderCtl(
        config_dir=config,
        nodedir=home / "tahoe",
        mf_bin=_exit_immediately_tahoe(tmp_path),
    )
    ctl.log_path = log
    with pytest.raises(SyncError) as exc:
        ctl.ensure_running()
    blob = exc.value.banner()
    assert "Magic Folder stopped while starting" in blob
    assert display_path(log) in blob
    assert "#30" not in blob
    assert "known issue" not in blob.lower()
    assert "pb://" not in blob
    assert _FURL_SHAPE.search(blob) is None
    assert "Traceback" not in blob
    assert _EXC_CLASS.search(blob) is None
    assert seeded not in blob
    assert "daemon failed" not in blob


def test_join_permission_denied_is_friendly(tmp_path: Path, monkeypatch):
    """A read-only storage directory must not show Errno text or the path."""
    tahoe_bin = _fake_tahoe(tmp_path)
    real_mkdir = Path.mkdir

    def mkdir(self, *args, **kwargs):
        if self.name == "storage":
            raise PermissionError(13, "Permission denied", str(self))
        return real_mkdir(self, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", mkdir)
    home = tmp_path / "home"
    client = TahoeClient(nodedir=home / "tahoe", tahoe_bin=tahoe_bin, home=home)
    with pytest.raises(SyncError) as exc:
        client.join_invite(GOOD_FURL)
    blob = exc.value.banner()
    assert "save its files" in blob
    assert "Permission denied" not in blob
    assert "Errno" not in blob
    assert str(home) not in blob
    _assert_join_phrase_once(blob)
    _assert_no_spawn_leak(blob)


def test_join_other_oserror_text_is_not_echoed(tmp_path: Path, monkeypatch):
    """Generic OSError strerror must not appear. Kills an echo on the non-permission branch."""
    tahoe_bin = _fake_tahoe(tmp_path)
    real_mkdir = Path.mkdir

    def mkdir(self, *args, **kwargs):
        if self.name == "storage":
            raise OSError(5, "other OSError text", str(self))
        return real_mkdir(self, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", mkdir)
    home = tmp_path / "home"
    client = TahoeClient(nodedir=home / "tahoe", tahoe_bin=tahoe_bin, home=home)
    with pytest.raises(SyncError) as exc:
        client.join_invite(GOOD_FURL)
    blob = exc.value.banner()
    assert "other OSError text" not in blob
    assert "Errno" not in blob
    assert "save its files" in blob
    assert str(home) not in blob
    _assert_join_phrase_once(blob)


def test_join_spawn_oserror_text_is_not_echoed(tmp_path: Path, monkeypatch):
    """`tahoe create-node` raising OSError must not copy the strerror either."""

    def raise_oserror(cmd, **kwargs):
        raise OSError(5, "other OSError text")

    monkeypatch.setattr("leasegrid_sync.backend.subprocess.run", raise_oserror)
    home = tmp_path / "home"
    client = TahoeClient(
        nodedir=home / "tahoe", tahoe_bin=str(tmp_path / "tahoe-bin"), home=home
    )
    with pytest.raises(SyncError) as exc:
        client.join_invite(GOOD_FURL)
    blob = exc.value.banner()
    assert "other OSError text" not in blob
    assert "Errno" not in blob
    assert "could not be started" in blob
    _assert_join_phrase_once(blob)


def test_join_file_not_found_removes_partial_nodedir(tmp_path: Path, monkeypatch):
    nodedir = tmp_path / "home" / "tahoe"

    def boom(cmd, **kwargs):
        path = Path(cmd[-1])
        path.mkdir(parents=True)
        (path / "partial").write_text("x", encoding="utf-8")
        raise FileNotFoundError(2, "No such file or directory", cmd[0])

    monkeypatch.setattr("leasegrid_sync.backend.subprocess.run", boom)
    client = TahoeClient(
        nodedir=nodedir, tahoe_bin=str(tmp_path / "missing-tahoe"), home=tmp_path / "home"
    )
    with pytest.raises(SyncError) as exc:
        client.join_invite(GOOD_FURL)
    blob = exc.value.banner()
    assert "not installed" in blob
    assert "No such file" not in blob
    assert not nodedir.exists()
    _assert_join_phrase_once(blob)


def test_join_phrase_appears_at_most_once(tmp_path: Path, monkeypatch):
    """welcome()'s lead must not be prefixed a second time."""
    monkeypatch.setenv("PATH", str(tmp_path / "empty-path"))
    monkeypatch.delenv("LEASEGRID_TAHOE_BIN", raising=False)
    nodedir = tmp_path / "tahoe"
    nodedir.mkdir()
    (nodedir / "tahoe.cfg").write_text("[node]\n", encoding="utf-8")
    client = TahoeClient(nodedir=nodedir, home=tmp_path / "home")
    assert client.tahoe_bin is None
    with pytest.raises(SyncError) as exc:
        client.join_existing()
    blob = exc.value.banner()
    _assert_join_phrase_once(blob)
    assert "could not join this friendnet." in blob

    nodedir2 = tmp_path / "up" / "tahoe"
    nodedir2.mkdir(parents=True)
    (nodedir2 / "tahoe.cfg").write_text("[node]\n", encoding="utf-8")
    started = TahoeClient(
        nodedir=nodedir2, tahoe_bin=_fake_tahoe(tmp_path), home=tmp_path / "up"
    )
    fail = ConnectionStatus(
        state="FAIL",
        detail="could not join this friendnet. Tahoe client is not reachable.",
    )
    with patch.object(started, "is_reachable", return_value=True):
        with patch.object(started, "wait_connected", return_value=fail):
            with pytest.raises(SyncError) as exc2:
                started.join_existing()
    blob = exc2.value.banner()
    _assert_join_phrase_once(blob)
    assert "Tahoe client is not reachable" in blob


def test_join_furl_failure_hides_the_tahoe_traceback(tmp_path: Path):
    nodedir = tmp_path / "home" / "tahoe"
    client = TahoeClient(nodedir=nodedir, tahoe_bin=_fake_tahoe(tmp_path), home=tmp_path / "home")
    bad = "pb://badbadbadbad@127.0.0.1:1/swissnumswiss"
    with pytest.raises(SyncError) as exc:
        client.join_invite(bad)
    blob = exc.value.banner()
    assert "could not create a node" in blob
    _assert_no_raw_failure(blob)
    assert "ValueError" not in blob
    assert bad not in blob
    assert not nodedir.exists()


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


def test_parse_reserved_space_sizes_and_percent():
    from leasegrid_sync.backend import parse_reserved_space

    assert parse_reserved_space("1024", 10**9) == 1024
    assert parse_reserved_space("1K", 10**9) == 1024
    assert parse_reserved_space("1KiB", 10**9) == 1024
    assert parse_reserved_space("1KB", 10**9) == 1000
    assert parse_reserved_space("1G", 10**12) == 1024**3
    assert parse_reserved_space("50%", 1000) == 500
    assert parse_reserved_space("", 1000) == 0
    with pytest.raises(SyncError) as exc:
        parse_reserved_space("lots", 1000)
    assert "reserved_space" in exc.value.message
    assert exc.value.next_hint


def test_disk_slices_used_free_offered(tmp_path: Path):
    from collections import namedtuple

    from leasegrid_sync.backend import format_bytes, read_disk_offer

    nodedir = tmp_path / "tahoe"
    home = tmp_path / "home"
    nodedir.mkdir()
    home.mkdir()
    (nodedir / "tahoe.cfg").write_text(
        "[storage]\nenabled = true\nreserved_space = 100\n", encoding="utf-8"
    )
    usage = namedtuple("usage", "total used free")(1000, 400, 600)
    with patch("leasegrid_sync.backend.shutil.disk_usage", return_value=usage):
        slices = read_disk_offer(nodedir, home)
    assert slices.used == 400
    assert slices.kept == 100
    assert slices.offered == 500
    assert slices.offered_percent == 50
    assert format_bytes(400) == "400 B"
    assert format_bytes(1500) == "1.5 KB"


def test_read_disk_offer_not_offering_is_zero_percent(tmp_path: Path):
    from collections import namedtuple

    from leasegrid_sync.backend import read_disk_offer

    nodedir = tmp_path / "tahoe"
    home = tmp_path / "home"
    nodedir.mkdir()
    home.mkdir()
    (nodedir / "tahoe.cfg").write_text("[node]\n", encoding="utf-8")
    usage = namedtuple("usage", "total used free")(1000, 250, 750)
    with patch("leasegrid_sync.backend.shutil.disk_usage", return_value=usage):
        slices = read_disk_offer(nodedir, home)
    assert slices.offered == 0
    assert slices.kept == 750
    assert slices.offered_percent == 0


def test_apply_offer_percent_writes_reserve(tmp_path: Path):
    from collections import namedtuple

    from leasegrid_sync.backend import apply_offer_percent

    nodedir = tmp_path / "tahoe"
    home = tmp_path / "home"
    nodedir.mkdir()
    home.mkdir()
    (nodedir / "tahoe.cfg").write_text(
        "[node]\nnickname = sync\n[storage]\nenabled = true\n", encoding="utf-8"
    )
    usage = namedtuple("usage", "total used free")(1000, 200, 800)
    with patch("leasegrid_sync.backend.shutil.disk_usage", return_value=usage):
        slices = apply_offer_percent(nodedir, home, 25)
    assert slices.offered == 250
    assert slices.kept == 550
    assert slices.offered_percent == 25
    text = (nodedir / "tahoe.cfg").read_text(encoding="utf-8")
    assert "nickname = sync" in text
    assert "enabled = true" in text
    assert "reserved_space = 550" in text


def test_apply_offer_percent_zero_disables_storage(tmp_path: Path):
    from collections import namedtuple

    from leasegrid_sync.backend import apply_offer_percent, storage_offered

    nodedir = tmp_path / "tahoe"
    home = tmp_path / "home"
    nodedir.mkdir()
    home.mkdir()
    (nodedir / "tahoe.cfg").write_text("[storage]\nenabled = true\n", encoding="utf-8")
    usage = namedtuple("usage", "total used free")(1000, 200, 800)
    with patch("leasegrid_sync.backend.shutil.disk_usage", return_value=usage):
        slices = apply_offer_percent(nodedir, home, 0)
    assert slices.offered == 0
    assert storage_offered(nodedir) is False


def test_apply_offer_percent_sync_only_fails(tmp_path: Path):
    from collections import namedtuple

    from leasegrid_sync.backend import apply_offer_percent

    nodedir = tmp_path / "tahoe"
    home = tmp_path / "home"
    nodedir.mkdir()
    home.mkdir()
    (nodedir / "tahoe.cfg").write_text("[node]\n", encoding="utf-8")
    usage = namedtuple("usage", "total used free")(1000, 200, 800)
    with patch("leasegrid_sync.backend.shutil.disk_usage", return_value=usage):
        with pytest.raises(SyncError) as exc:
            apply_offer_percent(nodedir, home, 40)
    assert "sync-only" in exc.value.message
    assert "Offer disk" in exc.value.next_hint


def test_read_disk_offer_oserror_is_fail(tmp_path: Path):
    from leasegrid_sync.backend import read_disk_offer

    nodedir = tmp_path / "tahoe"
    home = tmp_path / "home"
    nodedir.mkdir()
    home.mkdir()
    (nodedir / "tahoe.cfg").write_text("[node]\n", encoding="utf-8")
    with patch("leasegrid_sync.backend.shutil.disk_usage", side_effect=OSError("no disk")):
        with pytest.raises(SyncError) as exc:
            read_disk_offer(nodedir, home)
    assert "could not read this disk" in exc.value.message
    assert "mounted" in exc.value.next_hint
    assert "no disk" not in exc.value.banner()


def _poison_script(tmp_path: Path, name: str = "mf-fail") -> str:
    if os.name == "nt":
        script = tmp_path / (name + ".py")
        script.write_text(
            "import sys\nsys.stderr.write(%r)\nsys.exit(1)\n" % POISON,
            encoding="utf-8",
        )
        bat = tmp_path / (name + ".bat")
        bat.write_text('@"%s" "%s" %%*\n' % (sys.executable, script), encoding="utf-8")
        return str(bat)
    bin_ = tmp_path / name
    bin_.write_text(
        "#!%s\nimport sys\nsys.stderr.write(%r)\nsys.exit(1)\n" % (sys.executable, POISON),
        encoding="utf-8",
    )
    bin_.chmod(0o755)
    return str(bin_)


def _mf_api_ready(tmp_path: Path) -> MagicFolderCtl:
    cfg = tmp_path / "mf"
    cfg.mkdir()
    (cfg / "api_token").write_text("not-a-secret\n", encoding="utf-8")
    (cfg / "api_client_endpoint").write_text("tcp:127.0.0.1:9\n", encoding="utf-8")
    return MagicFolderCtl(config_dir=cfg, nodedir=tmp_path / "tahoe", mf_bin="/bin/true")


def _poison_http(code: int):
    import io
    import urllib.error
    from email.message import EmailMessage

    return urllib.error.HTTPError(
        "http://127.0.0.1:9/v1/magic-folder",
        code,
        POISON,
        EmailMessage(),
        io.BytesIO(POISON.encode("utf-8")),
    )


def test_magic_folder_http_get_hides_body(tmp_path: Path, monkeypatch):
    """GET must not put the HTTP body or reason on the Next line."""
    ctl = _mf_api_ready(tmp_path)

    def boom(req, timeout=10):
        code = 500 if req.full_url.endswith("/v1/magic-folder") else 400
        raise _poison_http(code)

    monkeypatch.setattr(backend_mod.urllib.request, "urlopen", boom)
    with pytest.raises(SyncError) as exc:
        ctl._http_get("/v1/magic-folder")
    blob = exc.value.banner()
    assert "#30" in blob
    assert "Magic Folder HTTP 500" in blob
    assert "docs/TESTERS.md" in blob
    assert_no_raw_user_text(blob)
    with pytest.raises(SyncError) as exc:
        ctl._http_get("/v1/magic-folder/Photos/file-status")
    blob = exc.value.banner()
    assert "Magic Folder API error (400)." in blob
    assert "#30" not in blob
    assert_no_raw_user_text(blob)


def test_magic_folder_http_post_hides_body(tmp_path: Path, monkeypatch):
    """POST must not put the HTTP body or reason on the Next line."""
    ctl = _mf_api_ready(tmp_path)
    calls = {"n": 0}

    def boom(req, timeout=10):
        calls["n"] += 1
        raise _poison_http(500 if calls["n"] == 1 else 400)

    monkeypatch.setattr(backend_mod.urllib.request, "urlopen", boom)
    with pytest.raises(SyncError) as exc:
        ctl._http_post("/v1/magic-folder/Photos/scan-local")
    blob = exc.value.banner()
    assert "#30" in blob
    assert "Magic Folder HTTP 500" in blob
    assert_no_raw_user_text(blob)
    with pytest.raises(SyncError) as exc:
        ctl._http_post("/v1/magic-folder/Photos/participants", body={"author": {"name": "a"}})
    blob = exc.value.banner()
    assert "Magic Folder API error (400)." in blob
    assert "#30" not in blob
    assert_no_raw_user_text(blob)


def test_magic_folder_init_stderr_is_not_shown(tmp_path: Path):
    nodedir = tmp_path / "tahoe"
    nodedir.mkdir()
    (nodedir / "tahoe.cfg").write_text("[node]\n", encoding="utf-8")
    ctl = MagicFolderCtl(
        config_dir=tmp_path / "mf-init",
        nodedir=nodedir,
        mf_bin=_poison_script(tmp_path, "mf-init"),
    )
    with pytest.raises(SyncError) as exc:
        ctl.ensure_init()
    blob = exc.value.banner()
    assert "Could not initialize Magic Folder." in blob
    assert_no_raw_user_text(blob)


def test_magic_folder_add_stderr_is_not_shown(tmp_path: Path):
    folder = tmp_path / "docs"
    folder.mkdir()
    ctl = MagicFolderCtl(config_dir=tmp_path / "mf", nodedir=tmp_path / "tahoe", mf_bin="/bin/true")
    streams = ({"stdout": "", "stderr": POISON}, {"stdout": POISON, "stderr": ""})
    for stream in streams:
        proc = subprocess.CompletedProcess(args=["add"], returncode=1, **stream)
        with patch.object(ctl, "ensure_running", return_value=None), patch.object(
            ctl, "_http_get", return_value={}
        ), patch.object(ctl, "_run_cli", return_value=proc):
            with pytest.raises(SyncError) as exc:
                ctl.add_folder(str(folder))
        blob = exc.value.banner()
        assert "could not add this folder" in blob
        assert_no_raw_user_text(blob)


def test_magic_folder_spawn_oserror_is_not_shown(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(backend_mod, "_port_free", lambda _port, host="127.0.0.1": True)
    ctl = _mf_api_ready(tmp_path)
    ctl.log_path = tmp_path / "logs" / "magic-folder.log"
    monkeypatch.setattr(ctl, "is_running", lambda: False)

    def boom(_cmd, _log_f):
        raise OSError(POISON)

    monkeypatch.setattr(backend_mod, "popen_hidden", boom)
    with pytest.raises(SyncError) as exc:
        ctl.ensure_running()
    blob = exc.value.banner()
    assert "Could not start Magic Folder." in blob
    assert_no_raw_user_text(blob)


def test_read_disk_offer_oserror_hides_exception_text(tmp_path: Path):
    from leasegrid_sync.backend import offer_disk_path, read_disk_offer

    nodedir = tmp_path / "tahoe"
    home = tmp_path / "home"
    nodedir.mkdir()
    home.mkdir()
    (nodedir / "tahoe.cfg").write_text("[node]\n", encoding="utf-8")
    with patch("leasegrid_sync.backend.shutil.disk_usage", side_effect=OSError(POISON)):
        with pytest.raises(SyncError) as exc:
            read_disk_offer(nodedir, home)
    blob = exc.value.banner()
    assert "could not read this disk" in blob
    assert display_path(offer_disk_path(home, nodedir)) in blob
    assert_no_raw_user_text(blob)


def test_apply_offer_percent_oserror_hides_exception_text(tmp_path: Path):
    from leasegrid_sync.backend import apply_offer_percent, offer_disk_path

    nodedir = tmp_path / "tahoe"
    home = tmp_path / "home"
    nodedir.mkdir()
    home.mkdir()
    (nodedir / "tahoe.cfg").write_text("[node]\n", encoding="utf-8")
    with patch("leasegrid_sync.backend.shutil.disk_usage", side_effect=OSError(POISON)):
        with pytest.raises(SyncError) as exc:
            apply_offer_percent(nodedir, home, 40)
    blob = exc.value.banner()
    assert "could not offer disk" in blob
    assert display_path(offer_disk_path(home, nodedir)) in blob
    assert_no_raw_user_text(blob)


def test_unexpected_error_hides_exception_text():
    from leasegrid_sync.app import unexpected_error

    err = unexpected_error(RuntimeError(POISON), "could not list folders.")
    blob = err.banner()
    assert "could not list folders. Unexpected error." in blob
    assert_no_raw_user_text(blob)


# Obviously fake. Tests must not show any piece of it.
_INVITE_FURL = "pb://FAKETUBID@127.0.0.1:1/FAKESWISSNUMSECRET"


def _assert_no_invite_fragments(blob: str, furl: str = _INVITE_FURL) -> None:
    rest = furl[len("pb://"):]
    tub = rest.split("@", 1)[0]
    swiss = rest.split("/", 1)[1]
    assert "pb://" not in blob
    assert tub not in blob
    assert swiss not in blob
    assert furl[:8] not in blob
    assert furl[-6:] not in blob
    assert (furl[:8] + "…" + furl[-6:]) not in blob
    assert (furl[:8] + "..." + furl[-6:]) not in blob


def _existing_node(tmp_path: Path) -> TahoeClient:
    nodedir = tmp_path / "tahoe"
    nodedir.mkdir()
    (nodedir / "tahoe.cfg").write_text("[node]\n", encoding="utf-8")
    return TahoeClient(nodedir=nodedir, tahoe_bin="/bin/true", home=tmp_path / "home")


def _offline_join(client: TahoeClient):
    offline = ConnectionStatus(state="Offline", detail="introducer down")
    return patch.object(client, "is_reachable", return_value=True), patch.object(
        client, "wait_connected", return_value=offline
    )


def test_existing_node_furl_join_hides_invite(tmp_path: Path):
    """A node that is already here must not repeat any of the pasted furl."""
    client = _existing_node(tmp_path)
    reachable, waiting = _offline_join(client)
    with reachable, waiting:
        with pytest.raises(SyncError) as exc:
            client.join_invite(_INVITE_FURL)
    blob = exc.value.banner()
    assert "not connected to an introducer" in blob
    assert "pb://" not in blob
    _assert_no_invite_fragments(blob)


def test_existing_node_link_join_hides_invite(tmp_path: Path):
    """A join link takes the same path. The fragment must not reach the window."""
    from leasegrid_sync.invite import format_join_url

    client = _existing_node(tmp_path)
    link = format_join_url(_INVITE_FURL)
    reachable, waiting = _offline_join(client)
    with reachable, waiting:
        with pytest.raises(SyncError) as exc:
            client.join_invite(link)
    blob = exc.value.banner()
    assert "not connected to an introducer" in blob
    assert link not in blob
    assert "pb://" not in blob
    _assert_no_invite_fragments(blob)


def test_recovery_import_existing_node_hides_invite(tmp_path: Path):
    """Import of a recovery key joins with the stored invite and must not show it."""
    from leasegrid_sync.credit import CreditCtl
    from leasegrid_sync.recovery import RecoveryBundle, RecoveryCtl, encode_recovery_file

    bundle = RecoveryBundle(introducer_furl=_INVITE_FURL, shares=(2, 3, 3))
    key = tmp_path / "k.leasegrid-recovery"
    key.write_bytes(encode_recovery_file(bundle, "pw"))
    home = tmp_path / "home"
    home.mkdir()
    nodedir = tmp_path / "tahoe"
    nodedir.mkdir()
    (nodedir / "tahoe.cfg").write_text("[node]\n", encoding="utf-8")
    tahoe = TahoeClient(nodedir=nodedir, tahoe_bin="/bin/true", home=home)
    mf = MagicFolderCtl(config_dir=home / "mf", nodedir=nodedir, mf_bin="/bin/true")
    credit = CreditCtl(home=home)
    ctl = RecoveryCtl(home, tahoe, mf, credit, folder_root=tmp_path / "LG")
    reachable, waiting = _offline_join(tahoe)
    with reachable, waiting:
        with pytest.raises(SyncError) as exc:
            ctl.restore(key, "pw")
    blob = exc.value.banner()
    assert "not connected to an introducer" in blob
    assert "pb://" not in blob
    _assert_no_invite_fragments(blob)


def test_magic_folder_readonly_log_dir_is_friendly(tmp_path: Path, monkeypatch):
    """mkdir and open of the Magic Folder log stay inside the friendly mapping."""
    if os.name == "nt" or (hasattr(os, "geteuid") and os.geteuid() == 0):
        pytest.skip("directory mode does not block this user")
    monkeypatch.setattr(backend_mod, "_port_free", lambda _port, host="127.0.0.1": True)
    ctl = _mf_api_ready(tmp_path)
    monkeypatch.setattr(ctl, "is_running", lambda: False)

    parent = tmp_path / "ro-parent"
    parent.mkdir()
    parent.chmod(0o555)
    ctl.log_path = parent / "logs" / "magic-folder.log"
    try:
        with pytest.raises(SyncError) as exc:
            ctl.ensure_running()
        blob = exc.value.banner()
        assert "save its files" in blob
        assert display_path(ctl.log_path.parent) in blob
        assert "Permission denied" not in blob
        assert "Read-only" not in blob
        assert_no_raw_user_text(blob)
    finally:
        parent.chmod(0o755)

    log_dir = tmp_path / "ro-logs"
    log_dir.mkdir()
    log_dir.chmod(0o555)
    ctl.log_path = log_dir / "magic-folder.log"
    try:
        with pytest.raises(SyncError) as exc:
            ctl.ensure_running()
        blob = exc.value.banner()
        assert "save its files" in blob
        assert display_path(log_dir) in blob
        assert "Permission denied" not in blob
        assert "Read-only" not in blob
        assert_no_raw_user_text(blob)
    finally:
        log_dir.chmod(0o755)


def test_parse_reserved_space_hides_raw_value():
    from leasegrid_sync.backend import parse_reserved_space

    raw = _INVITE_FURL
    with pytest.raises(SyncError) as exc:
        parse_reserved_space(raw, 1000)
    blob = exc.value.banner()
    assert "not a size" in blob
    assert "reserved_space" in blob
    assert raw not in blob
    assert "pb://" not in blob
    _assert_no_invite_fragments(blob)


def test_refresh_http_500_does_not_say_folder_not_added(tmp_path: Path, monkeypatch):
    """Refresh lists folders. That HTTP 500 is not an add."""
    ctl = _mf_api_ready(tmp_path)

    def boom(req, timeout=10):
        raise _poison_http(500)

    monkeypatch.setattr(backend_mod.urllib.request, "urlopen", boom)
    with patch.object(ctl, "ensure_running", return_value=None):
        with pytest.raises(SyncError) as exc:
            ctl.list_folders()
    blob = exc.value.banner()
    assert "folder not added" not in blob.lower()
    assert "could not refresh folders" in blob
    assert "Magic Folder HTTP 500" in blob
    assert "#30" in blob
    assert_no_raw_user_text(blob)

    with pytest.raises(SyncError) as exc:
        ctl._http_get("/v1/magic-folder")
    direct = exc.value.banner()
    assert "folder not added" in direct
    assert "could not refresh folders" not in direct


def test_refresh_row_http_500_does_not_say_folder_not_added(tmp_path: Path, monkeypatch):
    ctl = _mf_api_ready(tmp_path)
    payload = b'{"Photos": {"magic_path": "/tmp/Photos", "poll_interval": 5}}'

    class _Body:
        def read(self):
            return payload

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    def boom(req, timeout=10):
        if req.full_url.rstrip("/").endswith("/v1/magic-folder"):
            return _Body()
        raise _poison_http(500)

    monkeypatch.setattr(backend_mod.urllib.request, "urlopen", boom)
    with patch.object(ctl, "ensure_running", return_value=None):
        rows = ctl.list_folders()
    assert len(rows) == 1
    assert rows[0].status == "FAIL"
    assert "folder not added" not in rows[0].detail.lower()
    assert "could not refresh folders" in rows[0].detail
    assert "HTTP 500" in rows[0].detail
    assert_no_raw_user_text(rows[0].detail)


def _exiting_magic_folder(tmp_path: Path, monkeypatch) -> tuple[MagicFolderCtl, Path, str]:
    """A Magic Folder daemon that exits on startup. Log text is planted and fake."""
    monkeypatch.setattr(backend_mod, "_port_free", lambda _port, host="127.0.0.1": True)
    home = tmp_path / "home"
    config = home / "magic-folder"
    config.mkdir(parents=True)
    (config / "api_token").write_text("not-a-secret\n", encoding="utf-8")
    log = home / "logs" / "magic-folder.log"
    log.parent.mkdir(parents=True)
    seeded = "pb://FAKE-TUBID@127.0.0.1:1/FAKE-SWISS"
    log.write_text(
        "Traceback (most recent call last):\n"
        '  File "mf.py", line 1, in run\n'
        "RuntimeError: daemon failed\n" + seeded + "\n",
        encoding="utf-8",
    )
    ctl = MagicFolderCtl(
        config_dir=config,
        nodedir=home / "tahoe",
        mf_bin=_exit_immediately_tahoe(tmp_path),
    )
    ctl.log_path = log
    return ctl, log, seeded


def _assert_log_not_pasted(blob: str, log: Path, seeded: str) -> None:
    assert display_path(log) in blob
    assert seeded not in blob
    assert "Traceback" not in blob
    assert "daemon failed" not in blob
    assert_no_raw_user_text(blob)


def test_refresh_daemon_exit_does_not_say_folder_not_added(tmp_path: Path, monkeypatch):
    """Refresh starts the daemon. That exit is not an add, and the log stays out."""
    ctl, log, seeded = _exiting_magic_folder(tmp_path, monkeypatch)
    with pytest.raises(SyncError) as exc:
        ctl.list_folders()
    blob = exc.value.banner()
    assert "could not refresh folders" in blob
    assert "folder not added" not in blob.lower()
    assert "Magic Folder stopped while starting" in blob
    assert "Restart Sync." in blob
    assert "#30" not in blob
    _assert_log_not_pasted(blob, log, seeded)

    bare = MagicFolderCtl(config_dir=tmp_path / "mf", nodedir=tmp_path / "tahoe", mf_bin=None)
    # mf_bin=None falls back to PATH; CI has magic-folder installed. Force "missing".
    bare.mf_bin = None
    with pytest.raises(SyncError) as missing:
        bare.list_folders()
    missing_blob = missing.value.banner()
    assert "could not refresh folders" in missing_blob
    assert "not installed" in missing_blob
    assert "folder not added" not in missing_blob.lower()
    assert "install magic-folder" in missing_blob


def test_add_folder_daemon_exit_still_says_folder_not_added(tmp_path: Path, monkeypatch):
    """Add folder still owns the ensure_running sentences."""
    ctl, log, seeded = _exiting_magic_folder(tmp_path, monkeypatch)
    folder = tmp_path / "docs"
    folder.mkdir()
    with pytest.raises(SyncError) as exc:
        ctl.add_folder(str(folder))
    blob = exc.value.banner()
    assert "folder not added" in blob
    assert "could not refresh folders" not in blob
    assert "Magic Folder stopped while starting" in blob
    assert "Restart Sync." in blob
    _assert_log_not_pasted(blob, log, seeded)

    bare = MagicFolderCtl(config_dir=tmp_path / "mf-add", nodedir=tmp_path / "tahoe", mf_bin=None)
    # mf_bin=None falls back to PATH; CI has magic-folder installed. Force "missing".
    bare.mf_bin = None
    with pytest.raises(SyncError) as missing:
        bare.add_folder(str(folder))
    missing_blob = missing.value.banner()
    assert "folder not added" in missing_blob
    assert "could not refresh folders" not in missing_blob
    assert "not installed" in missing_blob


def test_refresh_http_500_maps_on_status_code_not_text(tmp_path: Path, monkeypatch):
    """#30 on refresh is the HTTP status, not the words "HTTP 500" in the sentence."""
    ctl = _mf_api_ready(tmp_path)
    fake = SyncError(
        "folder not added. This is known issue #30 (Magic Folder HTTP 500).",
        "Retry. If it keeps failing, file a bug per docs/TESTERS.md.",
    )
    assert fake.http_status is None
    mapped = ctl._refresh_http_message(fake)
    assert "could not refresh folders" not in mapped.message
    assert "folder not added" in mapped.message
    assert mapped.http_status != 500

    other = SyncError(
        "folder not added. This is known issue #30 (Magic Folder HTTP 500).",
        "Retry. If it keeps failing, file a bug per docs/TESTERS.md.",
        http_status=404,
    )
    mapped_other = ctl._refresh_http_message(other)
    assert "could not refresh folders" not in mapped_other.message
    assert mapped_other.http_status == 404

    def raise_fake(_path, base=None, timeout=10.0):
        raise fake

    with patch.object(ctl, "ensure_running", return_value=None), patch.object(
        ctl, "_http_get", raise_fake
    ):
        with pytest.raises(SyncError) as listed:
            ctl.list_folders()
    assert "could not refresh folders" not in listed.value.message
    assert "folder not added" in listed.value.message
    assert listed.value.http_status != 500

    def boom(req, timeout=10):
        raise _poison_http(500)

    monkeypatch.setattr(backend_mod.urllib.request, "urlopen", boom)
    with patch.object(ctl, "ensure_running", return_value=None):
        with pytest.raises(SyncError) as exc:
            ctl.list_folders()
    assert exc.value.http_status == 500
    blob = exc.value.banner()
    assert "could not refresh folders" in blob
    assert "folder not added" not in blob.lower()
    assert "Magic Folder HTTP 500" in blob
    assert "#30" in blob
    assert "docs/TESTERS.md" in blob
    assert_no_raw_user_text(blob)


@pytest.mark.parametrize(
    ("code", "is_30"),
    [(400, False), (499, False), (500, True), (501, False), (502, False), (503, False)],
)
def test_issue_30_is_exactly_http_500(code: int, is_30: bool):
    """#30 is HTTP 500 only. 499 and 501 (and other 5xx) are not #30."""
    assert backend_mod.is_issue_30_status(code) is is_30


def test_issue_30_status_none_is_not_30():
    assert backend_mod.is_issue_30_status(None) is False


@pytest.mark.parametrize(
    ("code", "is_30"), [(499, False), (500, True), (501, False), (503, False)]
)
def test_http_failure_names_30_only_for_500(tmp_path: Path, code: int, is_30: bool):
    ctl = _mf_api_ready(tmp_path)
    err = ctl._http_failure(_poison_http(code))
    blob = err.message + " " + err.next_hint
    assert err.http_status == code
    assert ("#30" in blob) is is_30
    if not is_30:
        assert "Magic Folder API error (%d)." % code == err.message
    assert_no_raw_user_text(blob)


@pytest.mark.parametrize(
    ("code", "is_30"), [(499, False), (500, True), (501, False), (503, False)]
)
def test_add_and_refresh_name_30_only_for_500(
    tmp_path: Path, monkeypatch, code: int, is_30: bool
):
    """Add says #30 only on 500; refresh rewrites to 'could not refresh' only on 500."""
    ctl = _mf_api_ready(tmp_path)

    def boom(req, timeout=10):
        raise _poison_http(code)

    monkeypatch.setattr(backend_mod.urllib.request, "urlopen", boom)
    with patch.object(ctl, "ensure_running", return_value=None):
        with pytest.raises(SyncError) as listed:
            ctl.list_folders()
        with pytest.raises(SyncError) as posted:
            ctl._http_post("/v1/magic-folder", body={"name": "x"})
    refresh = listed.value.message + " " + listed.value.next_hint
    add = posted.value.message + " " + posted.value.next_hint
    assert listed.value.http_status == code
    assert posted.value.http_status == code
    assert ("#30" in refresh) is is_30
    assert ("#30" in add) is is_30
    assert ("could not refresh folders" in refresh) is is_30
    assert ("folder not added" in add) is is_30
    assert "folder not added" not in refresh
    assert_no_raw_user_text(refresh)
    assert_no_raw_user_text(add)


@pytest.mark.parametrize(
    ("code", "is_30"), [(499, False), (500, True), (501, False), (503, False)]
)
def test_refresh_http_message_rewrites_only_status_500(tmp_path: Path, code: int, is_30: bool):
    """The refresh rewrite keys on http_status == 500 alone, even for add-shaped text."""
    ctl = _mf_api_ready(tmp_path)
    err = SyncError(
        "folder not added. This is known issue #30 (Magic Folder HTTP 500).",
        "Retry. If it keeps failing, file a bug per docs/TESTERS.md.",
        http_status=code,
    )
    mapped = ctl._refresh_http_message(err)
    assert mapped.http_status == code
    assert ("could not refresh folders" in mapped.message) is is_30
    assert (mapped is err) is (not is_30)


def _exited_unreaped(pid: int) -> bool:
    """True when ``pid`` has exited and this process has not collected it.

    ``poll`` and ``wait`` are not used. Either would set ``Popen.returncode``,
    and ``_leader_state`` would then report ``reaped`` without looking at the
    zombie.
    """
    if sys.platform == "linux":
        from tests.proc_util import is_zombie

        return is_zombie(pid)
    if sys.platform == "win32":
        from tests.proc_util import pid_alive

        return not pid_alive(pid)
    try:
        out = subprocess.run(
            ["ps", "-o", "state=", "-p", str(pid)],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return False
    return out.stdout.strip().startswith("Z")


def _respawn_tahoe(tmp_path: Path) -> str:
    """First ``run`` exits at once. A later ``run`` writes node.url and stays up."""
    script = tmp_path / "respawn_tahoe.py"
    script.write_text(
        "import os\n"
        "import sys\n"
        "import time\n"
        "from pathlib import Path\n"
        "args = sys.argv[1:]\n"
        "if not args or args[0] != 'run' or len(args) < 2:\n"
        "    raise SystemExit(0)\n"
        "nodedir = Path(args[1])\n"
        "count_path = nodedir / 'run-count'\n"
        "count = 0\n"
        "if count_path.is_file():\n"
        "    try:\n"
        "        count = int(count_path.read_text(encoding='utf-8') or '0')\n"
        "    except ValueError:\n"
        "        count = 0\n"
        "count_path.write_text(str(count + 1) + '\\n', encoding='utf-8')\n"
        "if count == 0:\n"
        "    raise SystemExit(0)\n"
        "(nodedir / 'node.url').write_text('http://127.0.0.1:1/\\n', encoding='utf-8')\n"
        "(nodedir / 'spawned.pid').write_text(str(os.getpid()) + '\\n', encoding='utf-8')\n"
        "while True:\n"
        "    time.sleep(0.2)\n",
        encoding="utf-8",
    )
    if os.name == "nt":
        bat = tmp_path / "tahoe.bat"
        bat.write_text('@\"%s\" \"%s\" %%*\n' % (sys.executable, script), encoding="utf-8")
        return str(bat)
    exe = tmp_path / "tahoe-bin"
    exe.write_text(
        "#!/bin/sh\nexec \"%s\" \"%s\" \"$@\"\n" % (sys.executable, script),
        encoding="utf-8",
    )
    exe.chmod(0o755)
    return str(exe)


def test_start_respawns_an_unreaped_exited_leader(tmp_path: Path) -> None:
    """A dead unreaped leader is not left in place. start() reaps it and spawns.

    The first ``run`` is planted on the client and not collected. Calling
    start() for that run would reap it inside the startup wait, so the next
    start() would not be looking at a zombie.
    """
    from tests.proc_util import pid_alive

    nodedir = tmp_path / "tahoe"
    nodedir.mkdir()
    (nodedir / "tahoe.cfg").write_text("[node]\n", encoding="utf-8")
    home = tmp_path / "home"
    binary = _respawn_tahoe(tmp_path)
    client = TahoeClient(nodedir=nodedir, tahoe_bin=binary, home=home)
    kwargs: dict = {}
    if sys.platform != "win32":
        kwargs["start_new_session"] = True
    leader = subprocess.Popen(
        [binary, "run", str(nodedir)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        **kwargs,
    )
    leader._leasegrid_group = True  # type: ignore[attr-defined]
    try:
        deadline = time.time() + 5
        while time.time() < deadline and not _exited_unreaped(leader.pid):
            time.sleep(0.02)
        assert leader.returncode is None
        assert _exited_unreaped(leader.pid), "planted leader was reaped or never exited"
        client._proc = leader
        with patch.object(client, "welcome", side_effect=_welcome_when_node_url(client)):
            client.start(timeout=5)
        spawned_path = nodedir / "spawned.pid"
        assert spawned_path.is_file(), "no new daemon was spawned"
        new_pid = int(spawned_path.read_text(encoding="utf-8").strip())
        assert new_pid != leader.pid
        assert pid_alive(new_pid)
        assert client._proc is not None
        assert client._proc.pid == new_pid
        assert client.owns_process()
    finally:
        client.stop()
        if leader.returncode is None:
            try:
                leader.wait(timeout=2)
            except subprocess.TimeoutExpired:
                leader.kill()
                try:
                    leader.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    pass
