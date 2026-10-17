"""sync-ui.log rotates at 1 MiB and still records the new entry if rotate fails."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from leasegrid_sync.app import UI_LOG_NAME, log_exception

# The file rotates when it is over 1 MiB, not at exactly 1 MiB.
_LIMIT = 1024 * 1024


def _log(home: Path) -> Path:
    return home / "logs" / UI_LOG_NAME


def _backup(home: Path) -> Path:
    return home / "logs" / (UI_LOG_NAME + ".1")


def test_log_rotates_when_over_one_mebibyte_and_keeps_one_backup(tmp_path: Path) -> None:
    home = tmp_path / "home"
    path = _log(home)
    path.parent.mkdir(parents=True)
    path.write_bytes(b"A" * _LIMIT)
    log_exception(home, "at-limit", RuntimeError("limit"))
    assert not _backup(home).exists()
    assert b"A" * 100 in path.read_bytes()

    path.write_bytes(b"B" * (_LIMIT + 1))
    log_exception(home, "first-rotate", RuntimeError("one"))
    assert _backup(home).read_bytes().startswith(b"B")
    fresh = path.read_text(encoding="utf-8")
    assert "first-rotate" in fresh
    assert "RuntimeError" in fresh

    path.write_bytes(b"C" * (_LIMIT + 1))
    log_exception(home, "second-rotate", RuntimeError("two"))
    rolled = _backup(home).read_bytes()
    assert rolled.startswith(b"C")
    assert b"B" * 100 not in rolled
    names = sorted(p.name for p in path.parent.glob("sync-ui.log*"))
    assert names == ["sync-ui.log", "sync-ui.log.1"]
    assert "second-rotate" in path.read_text(encoding="utf-8")


def _assert_entry_appended(home: Path, path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    assert "rotate-failed" in text
    assert "kept" in text
    assert text.encode("utf-8").startswith(b"D")


def test_rotation_failure_still_appends_and_does_not_raise(tmp_path: Path) -> None:
    """A backup name that can't be replaced (a non-empty directory) fails on every OS."""
    home = tmp_path / "home"
    path = _log(home)
    path.parent.mkdir(parents=True)
    path.write_bytes(b"D" * (_LIMIT + 1))
    blocker = _backup(home)
    blocker.mkdir()
    (blocker / "busy").write_text("x", encoding="utf-8")
    returned = log_exception(home, "rotate-failed", RuntimeError("kept"))
    assert returned == path
    assert blocker.is_dir()
    _assert_entry_appended(home, path)


@pytest.mark.skipif(
    sys.platform == "win32" or (hasattr(os, "geteuid") and os.geteuid() == 0),
    reason="a read-only directory does not block rename on Windows or as root",
)
def test_rotation_in_read_only_dir_still_appends(tmp_path: Path) -> None:
    home = tmp_path / "home"
    path = _log(home)
    path.parent.mkdir(parents=True)
    path.write_bytes(b"D" * (_LIMIT + 1))
    path.chmod(0o644)
    path.parent.chmod(0o555)
    try:
        returned = log_exception(home, "rotate-failed", RuntimeError("kept"))
    finally:
        path.parent.chmod(0o755)
    assert returned == path
    assert not _backup(home).exists()
    _assert_entry_appended(home, path)
