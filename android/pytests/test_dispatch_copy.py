"""The phone shows dispatch's message and next line as they are.

A real failure inside dispatch must not put a Python exception class name on
that copy. The class goes to the log. No grid required.
"""

from __future__ import annotations

import json
import logging
import re
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
