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

ROOT = Path(__file__).resolve().parents[1] / "app/src/main/python"
sys.path.insert(0, str(ROOT))

import leasegrid_read  # noqa: E402

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
