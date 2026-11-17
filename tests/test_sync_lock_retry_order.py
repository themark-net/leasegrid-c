"""#87 lock retry and ordering, as behaviour (Tester gate at 530dd52).

``acquire_instance_lock`` may read the lock file only after tryLock failed and
no PID could be read. That read retries a few times over about 100 ms, because
Windows reports a file a rival is deleting as access denied. Each test below
fails if one of those rules is broken:

- three reads, not one: a denial that clears on the third read is not "unreadable"
- a real wait between reads: a denial that clears after 80 ms is not "unreadable"
- the read never runs before tryLock: a stale lock is taken even when Python
  reads of it are always denied
- the PID guard: a rival that wrote its PID by the second tryLock is "already
  running", not "could not read its lock file"
- a missing file is not unreadable: a lock a rival just deleted is not an error
- B2: a stat or read that is denied for the whole time before tryLock does not
  block a takeable stale lock, and a lock that vanishes during the reads is
  tried once more instead of reported as already running
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

PyQt5 = pytest.importorskip("PyQt5")

from PyQt5 import QtCore  # noqa: E402

import leasegrid_sync.app as appmod  # noqa: E402
from leasegrid_sync.app import SyncError, acquire_instance_lock, instance_lock_path, release_instance_lock  # noqa: E402

_REAL_QLOCKFILE = QtCore.QLockFile


class _HeldLock:
    """A QLockFile that some other process holds: every tryLock fails, not for permission."""

    PermissionError = _REAL_QLOCKFILE.PermissionError
    events: list[str] = []

    def __init__(self, path: str) -> None:
        self.path = path

    def setStaleLockTime(self, _ms: int) -> None:
        pass

    def tryLock(self, _timeout: int = 0) -> bool:
        _HeldLock.events.append("tryLock")
        return False

    def error(self):
        return _REAL_QLOCKFILE.LockFailedError

    def getLockInfo(self):
        return (False, 0, "", "")

    def unlock(self) -> None:
        pass


class _HolderQuits(_HeldLock):
    """Held for the first two tryLocks, free on the third (the holder quit and its file is gone)."""

    def tryLock(self, _timeout: int = 0) -> bool:
        _HeldLock.events.append("tryLock")
        return _HeldLock.events.count("tryLock") >= 3


def _home(tmp_path: Path) -> tuple[Path, Path]:
    home = tmp_path / "home"
    home.mkdir()
    lock = instance_lock_path(home)
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_bytes(b"")
    return home, lock


def _patch_lock_reads(monkeypatch, lock: Path, answer) -> list[float]:
    """builtins.open of the lock calls answer(n) first. answer raises or returns None (read for real)."""
    real_open = open
    target = os.path.normcase(os.path.abspath(lock))
    reads: list[float] = []

    def guarded(file, mode="r", *args, **kwargs):
        try:
            got = os.path.normcase(os.path.abspath(os.fspath(file)))
        except (TypeError, ValueError):
            got = ""
        if got == target:
            reads.append(time.monotonic())
            _HeldLock.events.append("read")
            answer(len(reads))
        return real_open(file, mode, *args, **kwargs)

    monkeypatch.setattr("builtins.open", guarded)
    return reads


def _held_elsewhere(monkeypatch, pid_answers=None) -> None:
    _HeldLock.events = []
    monkeypatch.setattr(QtCore, "QLockFile", _HeldLock)
    monkeypatch.setattr(appmod, "_lock_writer_grace", lambda: None)
    if pid_answers is not None:
        seq = list(pid_answers)
        monkeypatch.setattr(appmod, "_lock_pid_readable", lambda _lock: seq.pop(0) if seq else False)


def _denied(path: Path) -> PermissionError:
    return PermissionError(13, "Permission denied", str(path))


def test_a_denial_that_clears_on_the_third_read_is_already_running_not_unreadable(tmp_path, monkeypatch):
    home, lock = _home(tmp_path)
    _held_elsewhere(monkeypatch)

    def answer(n: int) -> None:
        if n <= 2:
            raise _denied(lock)

    reads = _patch_lock_reads(monkeypatch, lock, answer)
    assert acquire_instance_lock(home) is False
    assert len(reads) == 3


def test_reads_wait_so_a_rival_delete_that_takes_80ms_is_not_unreadable(tmp_path, monkeypatch):
    home, lock = _home(tmp_path)
    _held_elsewhere(monkeypatch)
    start = time.monotonic()

    def answer(_n: int) -> None:
        if time.monotonic() - start < 0.08:
            raise _denied(lock)

    reads = _patch_lock_reads(monkeypatch, lock, answer)
    assert acquire_instance_lock(home) is False
    assert reads[-1] - reads[0] >= 0.06


def test_a_lock_that_stays_denied_is_unreadable_after_three_reads(tmp_path, monkeypatch):
    home, lock = _home(tmp_path)
    _held_elsewhere(monkeypatch)

    def answer(_n: int) -> None:
        raise _denied(lock)

    reads = _patch_lock_reads(monkeypatch, lock, answer)
    with pytest.raises(SyncError) as err:
        acquire_instance_lock(home)
    assert err.value.args[0] == appmod._LOCK_UNREADABLE[0]
    assert len(reads) == 3
    assert reads[-1] - reads[0] >= 0.06


def test_the_read_runs_only_after_trylock_failed(tmp_path, monkeypatch):
    home, lock = _home(tmp_path)
    _held_elsewhere(monkeypatch)

    def answer(_n: int) -> None:
        raise _denied(lock)

    _patch_lock_reads(monkeypatch, lock, answer)
    with pytest.raises(SyncError):
        acquire_instance_lock(home)
    events = _HeldLock.events
    assert "read" in events
    assert events.index("read") > events.index("tryLock")
    assert events[: events.index("read")].count("tryLock") == 2, events


def test_a_stale_lock_is_taken_even_when_python_reads_are_always_denied(tmp_path, monkeypatch):
    """Windows delete pending: Python reads say access denied, Qt can still take the stale file."""
    home, lock = _home(tmp_path)
    past = time.time() - 120
    os.utime(lock, (past, past))

    def answer(_n: int) -> None:
        raise _denied(lock)

    reads = _patch_lock_reads(monkeypatch, lock, answer)
    try:
        assert acquire_instance_lock(home) is True
    finally:
        release_instance_lock()
    assert reads == [], "the lock was read before tryLock"


def test_a_rival_that_wrote_its_pid_by_the_second_trylock_is_already_running(tmp_path, monkeypatch):
    home, lock = _home(tmp_path)
    # Before the grace, after the grace, then at the guard after the second tryLock.
    _held_elsewhere(monkeypatch, pid_answers=[False, False, True])

    def answer(_n: int) -> None:
        raise _denied(lock)

    _patch_lock_reads(monkeypatch, lock, answer)
    assert acquire_instance_lock(home) is False


def test_a_lock_a_rival_just_deleted_is_not_unreadable(tmp_path, monkeypatch):
    home, lock = _home(tmp_path)
    _held_elsewhere(monkeypatch)

    def answer(n: int) -> None:
        if n == 1:
            raise _denied(lock)
        raise FileNotFoundError(2, "No such file or directory", str(lock))

    reads = _patch_lock_reads(monkeypatch, lock, answer)
    assert acquire_instance_lock(home) is False
    assert len(reads) == 2


def test_a_missing_lock_is_not_unreadable(tmp_path, monkeypatch):
    home, lock = _home(tmp_path)
    _held_elsewhere(monkeypatch)

    def answer(_n: int) -> None:
        raise FileNotFoundError(2, "No such file or directory", str(lock))

    reads = _patch_lock_reads(monkeypatch, lock, answer)
    assert acquire_instance_lock(home) is False
    assert len(reads) == 1


def test_a_lock_that_vanishes_during_the_reads_is_taken_not_already_running(tmp_path, monkeypatch):
    home, lock = _home(tmp_path)
    _held_elsewhere(monkeypatch)
    monkeypatch.setattr(QtCore, "QLockFile", _HolderQuits)

    def answer(n: int) -> None:
        if n == 1:
            raise _denied(lock)
        raise FileNotFoundError(2, "No such file or directory", str(lock))

    _patch_lock_reads(monkeypatch, lock, answer)
    try:
        assert acquire_instance_lock(home) is True
    finally:
        release_instance_lock()
    assert _HeldLock.events.count("tryLock") == 3


def test_a_stale_lock_is_taken_when_stat_and_reads_are_denied_until_trylock(tmp_path, monkeypatch):
    """B2: Windows delete pending makes stat and open say access denied. That is not "unreadable" before tryLock."""
    home, lock = _home(tmp_path)
    past = time.time() - 120
    os.utime(lock, (past, past))
    target = os.path.normcase(os.path.abspath(lock))
    real_stat = Path.stat
    stats = {"n": 0}

    def denied_stat(self, *args, **kwargs):
        if os.path.normcase(os.path.abspath(self)) == target:
            stats["n"] += 1
            raise _denied(lock)
        return real_stat(self, *args, **kwargs)

    def answer(_n: int) -> None:
        raise _denied(lock)

    monkeypatch.setattr(Path, "stat", denied_stat)
    reads = _patch_lock_reads(monkeypatch, lock, answer)
    try:
        assert acquire_instance_lock(home) is True
    finally:
        release_instance_lock()
    assert stats["n"] >= 1, "the pre-tryLock stat check did not run"
    assert reads == []
