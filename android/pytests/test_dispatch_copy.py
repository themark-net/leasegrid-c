"""The phone shows dispatch's message and next line as they are.

A real failure inside dispatch must not put a Python exception class name on
that copy. The class goes to the log. No grid required.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "app/src/main/python"
sys.path.insert(0, str(ROOT))

import leasegrid_read  # noqa: E402
from lg_tahoe import ReadFail  # noqa: E402

_CLASS_NAME = re.compile(r"[A-Z][A-Za-z]*(Error|Exception|Warning)\b")


def _no_class_name(reply: dict) -> None:
    for key in ("message", "next"):
        text = reply.get(key, "")
        assert not _CLASS_NAME.search(text), "%s names a class: %r" % (key, text)


def test_a_download_that_cannot_be_written_does_not_name_the_class(tmp_path, monkeypatch, caplog):
    # The bytes arrive. Writing them fails for real: the folder is missing.
    monkeypatch.setattr(leasegrid_read, "download_file", lambda cap, servers: b"file body")
    dest = tmp_path / "missing-folder" / "photo.jpg"
    payload = json.dumps({"cap": "URI:CHK:test-only", "dest": str(dest), "servers": []})
    with caplog.at_level(logging.WARNING, logger="leasegrid_read"):
        reply = json.loads(leasegrid_read.dispatch("download", payload))
    assert reply["ok"] is False
    assert reply["message"] == "could not download this file. Network error or not enough free space."
    assert reply["next"] == "check network / free space; Retry."
    _no_class_name(reply)
    assert not dest.exists()
    assert "FileNotFoundError" in caplog.text


def test_an_unexpected_failure_does_not_name_the_class(caplog):
    # A timeout that is not a number fails inside dispatch before any network call.
    payload = json.dumps({"furl": "pb://test-only@127.0.0.1:1/x", "timeout": "soon"})
    with caplog.at_level(logging.WARNING, logger="leasegrid_read"):
        reply = json.loads(leasegrid_read.dispatch("learn", payload))
    assert reply["ok"] is False
    assert reply["message"] == "could not complete that."
    assert reply["next"] == "Retry. If it repeats, check the network and the invite."
    _no_class_name(reply)
    assert "ValueError" in caplog.text


def test_the_log_line_keeps_only_the_class_not_the_payload(caplog):
    payload = json.dumps({"furl": "pb://test-only-secret@127.0.0.1:1/x", "timeout": "soon"})
    with caplog.at_level(logging.WARNING, logger="leasegrid_read"):
        leasegrid_read.dispatch("learn", payload)
    assert "test-only-secret" not in caplog.text
    assert "soon" not in caplog.text


def test_fetch_share_keeps_the_server_error_off_the_next_line(monkeypatch, caplog):
    """lg_tahoe used to append the last server error to next as "(...)".

    That text can name an exception class or repeat a sentence. It goes to the log.
    """
    import lg_tahoe

    def refuse(*_args, **_kwargs):
        raise lg_tahoe.ReadFail("ConnectionRefusedError: [Errno 111] refused", "x")

    monkeypatch.setattr(lg_tahoe, "_http_get", refuse)
    server = lg_tahoe.StorageServer("pb://test-only@127.0.0.1:1/swissnumswiss")
    caplog.set_level(logging.WARNING, logger="lg_tahoe")
    try:
        lg_tahoe.fetch_share([server], "immutable", b"\x00" * 16, 0, timeout=0.1)
    except lg_tahoe.ReadFail as exc:
        reply = {"message": exc.message, "next": exc.next_hint}
    else:
        raise AssertionError("fetch_share should fail")
    _no_class_name(reply)
    assert reply["next"] == "check network / free space; Retry."
    assert "ConnectionRefusedError" in caplog.text
    assert "swissnumswiss" not in caplog.text


def _dir_cap() -> str:
    import lg_tahoe

    return "URI:DIR2:%s:%s" % (lg_tahoe.b2a(b"w" * 16), lg_tahoe.b2a(b"f" * 32))


def _chk_cap() -> str:
    import lg_tahoe

    # total=10: an unreachable download used to wait out ten share timeouts.
    return "URI:CHK:%s:%s:1:10:100" % (lg_tahoe.b2a(b"k" * 16), lg_tahoe.b2a(b"u" * 32))


def _slow_storage(monkeypatch, deadline_s: float = 0.35):
    """Unreachable storage: each connect blocks for the caller's socket timeout.

    The sleep is capped so a build without an overall deadline still finishes,
    and the connect count is what shows the old multi-share wait.
    """
    import time

    import lg_tahoe

    connects = {"n": 0}

    def slow(address, timeout=None, *args, **kwargs):
        connects["n"] += 1
        delay = 30.0 if timeout is None else float(timeout)
        time.sleep(min(delay, 0.05))
        raise TimeoutError("timed out")

    monkeypatch.setattr(lg_tahoe.socket, "create_connection", slow)
    monkeypatch.setattr(lg_tahoe, "STORAGE_DEADLINE_S", deadline_s, raising=False)
    return connects


def test_unreachable_list_download_and_remove_stop_at_one_deadline(tmp_path, monkeypatch):
    """One budget for the whole call. Each share used to sit on its own timeout.

    A fake backend that never accepts a connection must not be asked once per
    share. The card is the plain failure, with no exception class name.
    """
    import time

    import lg_tahoe

    # One budget, same length the phone already waits for learn.
    assert lg_tahoe.STORAGE_DEADLINE_S == 25.0
    connects = _slow_storage(monkeypatch)
    server = [{"furl": "pb://testid@203.0.113.9:1/swissnumswiss", "nickname": "s1"}]
    started = time.monotonic()
    cases = (
        ("list", {"cap": _dir_cap(), "servers": server}),
        ("download", {"cap": _chk_cap(), "dest": str(tmp_path / "photo.jpg"), "servers": server}),
        (
            "remove",
            {"cap": _dir_cap(), "name": "notes.txt", "shares": [2, 3, 3], "servers": server},
        ),
    )
    for op, payload in cases:
        before = connects["n"]
        reply = json.loads(leasegrid_read.dispatch(op, json.dumps(payload)))
        used = connects["n"] - before
        assert reply["ok"] is False, op
        _no_class_name(reply)
        assert "Retry" in reply["next"], op
        # Old code: list and remove probe 16 shares, download probes 10.
        assert used <= 8, "%s opened %d connections" % (op, used)
    assert time.monotonic() - started < 3.0


def test_list_and_remove_oserror_does_not_say_download(monkeypatch):
    """The OSError fallback used the download sentence for every action."""

    def boom(*_args, **_kwargs):
        raise OSError(5, "input/output error")

    monkeypatch.setattr(leasegrid_read, "list_folder_view", boom)
    monkeypatch.setattr(leasegrid_read, "remove_file", boom)
    server = [{"furl": "pb://testid@203.0.113.9:1/swissnumswiss", "nickname": "s1"}]
    cases = {
        "list": (
            {"cap": _dir_cap(), "servers": server},
            "could not load folders. Network error talking to storage.",
            "check network; Retry.",
        ),
        "remove": (
            {"cap": _dir_cap(), "name": "notes.txt", "shares": [2, 3, 3], "servers": server},
            "could not remove this file.",
            "Retry.",
        ),
    }
    for op, (payload, message, nxt) in cases.items():
        reply = json.loads(leasegrid_read.dispatch(op, json.dumps(payload)))
        assert reply["ok"] is False, op
        assert reply["message"] == message, op
        assert reply["next"] == nxt, op
        assert "download" not in reply["message"].lower(), reply
        assert "download" not in reply["next"].lower(), reply
        _no_class_name(reply)


def _put_blob(tmp_path: Path) -> Path:
    blob = tmp_path / "notes.txt"
    blob.write_bytes(b"hello from the phone")
    return blob


def test_unreachable_put_stops_at_one_deadline(tmp_path, monkeypatch):
    """The folder list already stops at one budget. The upload after it did not.

    Ten shares on a server that never accepts a connection must not each open
    their own socket. The card says the add failed, and Retry is the next step.
    """
    import time

    import lg_tahoe
    import lg_write

    assert lg_tahoe.STORAGE_DEADLINE_S == 25.0
    connects = _slow_storage(monkeypatch)
    monkeypatch.setattr(lg_write, "list_folder_view", lambda cap, servers: [])
    server = [{"furl": "pb://testid@203.0.113.9:1/swissnumswiss", "nickname": "s1"}]
    payload = {
        "cap": _dir_cap(),
        "name": "notes.txt",
        "path": str(_put_blob(tmp_path)),
        "replace": False,
        "shares": [1, 1, 10],
        "author_seed_b64": "",
        "phone_dmd": "",
        "servers": server,
    }
    started = connects["n"]
    began = time.monotonic()
    reply = json.loads(leasegrid_read.dispatch("put", json.dumps(payload)))
    used = connects["n"] - started
    assert reply["ok"] is False
    assert reply["message"] == "could not add this file.", reply
    assert "download" not in reply["message"].lower()
    assert "Retry" in reply["next"], reply
    _no_class_name(reply)
    # Old code opens one connection per share (10). One budget stops sooner.
    assert used <= 8, used
    assert time.monotonic() - began < 3.0


@pytest.mark.skipif(
    sys.platform == "win32",
    reason=(
        "chmod(0o555) does not deny creating a file on Windows; "
        "this test is the Android (POSIX) permission copy"
    ),
)
def test_download_permission_denied_does_not_say_network(tmp_path, monkeypatch):
    """The bytes arrived. The phone refused to save them. That is not the network."""
    monkeypatch.setattr(leasegrid_read, "download_file", lambda cap, servers: b"file body")
    blocked = tmp_path / "blocked"
    blocked.mkdir()
    blocked.chmod(0o555)
    dest = blocked / "photo.jpg"
    try:
        payload = json.dumps({"cap": "URI:CHK:test-only", "dest": str(dest), "servers": []})
        reply = json.loads(leasegrid_read.dispatch("download", payload))
    finally:
        blocked.chmod(0o755)
    assert reply["ok"] is False
    assert "would not allow" in reply["message"].lower(), reply
    assert "permission" in reply["next"].lower(), reply
    assert "network" not in reply["message"].lower(), reply
    assert "free space" not in reply["message"].lower(), reply
    assert "Retry" in reply["next"], reply
    _no_class_name(reply)
    assert not dest.exists()


@pytest.mark.skipif(
    sys.platform == "win32",
    reason=(
        "chmod(0) does not deny reading a file on Windows; "
        "this test is the Android (POSIX) permission copy"
    ),
)
def test_put_permission_denied_does_not_say_pick_it_again(tmp_path):
    """A file the phone cannot read is a permission failure, not a bad pick."""
    src = _put_blob(tmp_path)
    src.chmod(0)
    try:
        payload = {
            "cap": _dir_cap(),
            "name": "notes.txt",
            "path": str(src),
            "shares": [1, 1, 1],
            "servers": [{"furl": "pb://testid@203.0.113.9:1/swissnumswiss", "nickname": "s1"}],
        }
        reply = json.loads(leasegrid_read.dispatch("put", json.dumps(payload)))
    finally:
        src.chmod(0o644)
    assert reply["ok"] is False
    assert "would not allow" in reply["message"].lower(), reply
    assert "permission" in reply["next"].lower(), reply
    assert "pick it again" not in reply["next"].lower(), reply
    assert "Retry" in reply["next"], reply
    _no_class_name(reply)


def _open_raises_permission(monkeypatch, path: Path, mode_has: str) -> None:
    """open() of ``path`` raises PermissionError when the mode contains ``mode_has``."""
    real_open = open

    def guarded(file, mode="r", *args, **kwargs):
        text = mode if isinstance(mode, str) else ""
        if os.fspath(file) == os.fspath(path) and mode_has in text:
            raise PermissionError(13, "Permission denied", os.fspath(path))
        return real_open(file, mode, *args, **kwargs)

    monkeypatch.setattr(leasegrid_read, "open", guarded, raising=False)


def _icacls_deny(path: Path, rights: str) -> None:
    user = os.environ.get("USERNAME")
    if not user:
        pytest.fail("USERNAME is unset, so icacls cannot name the deny ACE")
    proc = subprocess.run(
        ["icacls", os.fspath(path), "/deny", "%s:%s" % (user, rights)],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        pytest.fail("icacls /deny failed (%s): %s" % (proc.returncode, detail))


def _icacls_reset(path: Path) -> None:
    subprocess.run(
        ["icacls", os.fspath(path), "/reset"],
        capture_output=True,
        text=True,
        check=False,
    )


def test_download_permission_error_does_not_say_network(tmp_path, monkeypatch):
    """PermissionError while saving is the phone-would-not-allow copy, on every OS."""
    monkeypatch.setattr(leasegrid_read, "download_file", lambda cap, servers: b"file body")
    dest = tmp_path / "photo.jpg"
    _open_raises_permission(monkeypatch, dest, "w")
    payload = json.dumps({"cap": "URI:CHK:test-only", "dest": str(dest), "servers": []})
    reply = json.loads(leasegrid_read.dispatch("download", payload))
    assert reply["ok"] is False
    assert "would not allow" in reply["message"].lower(), reply
    assert "permission" in reply["next"].lower(), reply
    assert "network" not in reply["message"].lower(), reply
    assert "free space" not in reply["message"].lower(), reply
    assert "Retry" in reply["next"], reply
    _no_class_name(reply)
    assert not dest.exists()


def test_put_permission_error_does_not_say_pick_it_again(tmp_path, monkeypatch):
    """PermissionError while reading an add is the would-not-allow copy, on every OS."""
    src = _put_blob(tmp_path)
    _open_raises_permission(monkeypatch, src, "r")
    payload = {
        "cap": _dir_cap(),
        "name": "notes.txt",
        "path": str(src),
        "shares": [1, 1, 1],
        "servers": [{"furl": "pb://testid@203.0.113.9:1/swissnumswiss", "nickname": "s1"}],
    }
    reply = json.loads(leasegrid_read.dispatch("put", json.dumps(payload)))
    assert reply["ok"] is False
    assert "would not allow" in reply["message"].lower(), reply
    assert "permission" in reply["next"].lower(), reply
    assert "pick it again" not in reply["next"].lower(), reply
    assert "Retry" in reply["next"], reply
    _no_class_name(reply)


@pytest.mark.skipif(
    sys.platform != "win32",
    reason=(
        "icacls deny (OI)(CI)(W) is the Windows stand-in for chmod(0o555) on a directory; "
        "this host is not Windows"
    ),
)
def test_download_windows_acl_deny_does_not_say_network(tmp_path, monkeypatch):
    """The bytes arrived. Windows refused to create the file. That is not the network."""
    monkeypatch.setattr(leasegrid_read, "download_file", lambda cap, servers: b"file body")
    blocked = tmp_path / "blocked"
    blocked.mkdir()
    dest = blocked / "photo.jpg"
    _icacls_deny(blocked, "(OI)(CI)(W)")
    try:
        payload = json.dumps({"cap": "URI:CHK:test-only", "dest": str(dest), "servers": []})
        reply = json.loads(leasegrid_read.dispatch("download", payload))
    finally:
        _icacls_reset(blocked)
    assert reply["ok"] is False
    assert "would not allow" in reply["message"].lower(), reply
    assert "permission" in reply["next"].lower(), reply
    assert "network" not in reply["message"].lower(), reply
    assert "free space" not in reply["message"].lower(), reply
    assert "Retry" in reply["next"], reply
    _no_class_name(reply)
    assert not dest.exists()


@pytest.mark.skipif(
    sys.platform != "win32",
    reason=(
        "icacls deny (R) is the Windows stand-in for chmod(0) on a file; "
        "this host is not Windows"
    ),
)
def test_put_windows_acl_deny_does_not_say_pick_it_again(tmp_path):
    """A file Windows will not let this user read is a permission failure, not a bad pick."""
    src = _put_blob(tmp_path)
    _icacls_deny(src, "(R)")
    try:
        payload = {
            "cap": _dir_cap(),
            "name": "notes.txt",
            "path": str(src),
            "shares": [1, 1, 1],
            "servers": [{"furl": "pb://testid@203.0.113.9:1/swissnumswiss", "nickname": "s1"}],
        }
        reply = json.loads(leasegrid_read.dispatch("put", json.dumps(payload)))
    finally:
        _icacls_reset(src)
    assert reply["ok"] is False
    assert "would not allow" in reply["message"].lower(), reply
    assert "permission" in reply["next"].lower(), reply
    assert "pick it again" not in reply["next"].lower(), reply
    assert "Retry" in reply["next"], reply
    _no_class_name(reply)


def test_unreachable_remove_does_not_say_download(monkeypatch):
    """A remove that cannot reach storage says remove, not download or list."""
    connects = _slow_storage(monkeypatch)
    server = [{"furl": "pb://testid@203.0.113.9:1/swissnumswiss", "nickname": "s1"}]
    started = connects["n"]
    reply = json.loads(
        leasegrid_read.dispatch(
            "remove",
            json.dumps(
                {"cap": _dir_cap(), "name": "notes.txt", "shares": [2, 3, 3], "servers": server}
            ),
        )
    )
    assert connects["n"] > started
    assert reply["ok"] is False
    assert reply["message"] == "could not remove this file.", reply
    assert "download" not in reply["message"].lower()
    assert "download" not in reply["next"].lower()
    _no_class_name(reply)


def test_learn_next_line_does_not_name_the_exception_class(monkeypatch, caplog):
    """lg_intro used to append the exception class to the learn next line.

    The phone does not show that line today. It still must not carry the class,
    or a later change that displays it will.
    """
    import lg_intro
    import twisted.internet.threads as threads

    monkeypatch.setattr(lg_intro, "_ensure_reactor", lambda: object())

    def boom(_reactor, _fn):
        raise RuntimeError("pb://test-only-secret")

    monkeypatch.setattr(threads, "blockingCallFromThread", boom)
    caplog.set_level(logging.WARNING, logger="lg_intro")
    with pytest.raises(ReadFail) as caught:
        lg_intro.learn_servers("pb://testid@203.0.113.9:1/swissnumswiss", timeout=0.1)
    exc = caught.value
    assert exc.message == "could not join this friendnet. Introducer is unreachable."
    assert exc.next_hint == (
        "check the network path to the introducer (and that it is running); Retry."
    )
    _no_class_name({"message": exc.message, "next": exc.next_hint})
    assert "test-only-secret" not in exc.message
    assert "test-only-secret" not in exc.next_hint
    assert "RuntimeError" in caplog.text
    assert "test-only-secret" not in caplog.text
    # Both raise sites use the helper. The old format is gone.
    source = Path(lg_intro.__file__).read_text(encoding="utf-8")
    assert "Retry. (%s)" not in source
    assert source.count("raise _unreachable(") == 2
