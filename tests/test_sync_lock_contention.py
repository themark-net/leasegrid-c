"""Windows lock contention is a short retry, then held or "already running" (#90).

On Windows, QLockFile reports PermissionError when CreateFile is refused
because a rival is deleting the lock file (delete pending) or holds it. CI
44255442462 showed a starter raising "could not write its lock file" in that
race. The lock call must retry for about 1 to 2 seconds and then either hold
the lock or report "already running" (False). The raw lock-write error is only
for a real permission problem with no lock file and no rival.
"""

from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path

import pytest

PyQt5 = pytest.importorskip("PyQt5")

from PyQt5 import QtCore  # noqa: E402

import leasegrid_sync.app as appmod  # noqa: E402
from leasegrid_sync.app import (  # noqa: E402
    SyncError,
    acquire_instance_lock,
    instance_lock_path,
    release_instance_lock,
)

_REAL = QtCore.QLockFile


class _Scripted:
    """tryLock answers come from a script: 'perm', 'busy' (held elsewhere) or 'ok'. The last answer repeats."""

    PermissionError = _REAL.PermissionError
    LockFailedError = _REAL.LockFailedError
    script: list[str] = []
    calls = 0

    def __init__(self, path: str) -> None:
        self.path = path
        self._err = _REAL.NoError

    def setStaleLockTime(self, _ms: int) -> None:
        pass

    def tryLock(self, _timeout: int = 0) -> bool:
        i = min(_Scripted.calls, len(_Scripted.script) - 1)
        _Scripted.calls += 1
        answer = _Scripted.script[i]
        if answer == "ok":
            self._err = _REAL.NoError
            return True
        self._err = _REAL.PermissionError if answer == "perm" else _REAL.LockFailedError
        return False

    def error(self):
        return self._err

    def getLockInfo(self):
        return (False, 0, "", "")

    def unlock(self) -> None:
        pass


def _setup(tmp_path: Path, monkeypatch, script: list[str], lock_file: bool = True):
    home = tmp_path / "home"
    home.mkdir()
    lock = instance_lock_path(home)
    lock.parent.mkdir(parents=True, exist_ok=True)
    if lock_file:
        lock.write_bytes(b"")
    _Scripted.script = script
    _Scripted.calls = 0
    sleeps: list[float] = []
    monkeypatch.setattr(QtCore, "QLockFile", _Scripted)
    monkeypatch.setattr(appmod, "_lock_writer_grace", lambda: None)
    monkeypatch.setattr(appmod, "_lock_contention_sleep", sleeps.append, raising=False)
    return home, lock, sleeps


@pytest.fixture(autouse=True)
def _release():
    yield
    release_instance_lock()


def test_permission_error_that_clears_takes_the_lock(tmp_path, monkeypatch):
    home, _lock, sleeps = _setup(tmp_path, monkeypatch, ["perm", "perm", "ok"])
    assert acquire_instance_lock(home) is True
    assert _Scripted.calls == 3
    assert len(sleeps) == 2


def test_contention_that_never_clears_is_already_running_not_an_error(tmp_path, monkeypatch):
    home, _lock, sleeps = _setup(tmp_path, monkeypatch, ["perm"])
    assert acquire_instance_lock(home) is False
    assert _Scripted.calls >= 4, "a few tries, not one"
    # Bounded backoff: about 1 to 2 seconds in total, growing, never zero.
    assert 1.0 <= sum(sleeps) <= 2.0, sleeps
    assert all(s > 0 for s in sleeps)
    assert sleeps == sorted(sleeps)


def test_delete_pending_lock_counts_as_contention(tmp_path, monkeypatch):
    home, lock, _sleeps = _setup(tmp_path, monkeypatch, ["perm"], lock_file=False)
    real_stat = os.stat
    target = os.path.normcase(os.path.abspath(lock))

    def stat(path, *args, **kwargs):
        if os.path.normcase(os.path.abspath(os.fspath(path))) == target:
            raise PermissionError(13, "Access is denied", os.fspath(path))
        return real_stat(path, *args, **kwargs)

    monkeypatch.setattr(appmod.os, "stat", stat)
    assert acquire_instance_lock(home) is False


def test_real_permission_problem_with_no_lock_file_still_says_so(tmp_path, monkeypatch):
    home, _lock, sleeps = _setup(tmp_path, monkeypatch, ["perm"], lock_file=False)
    with pytest.raises(SyncError) as exc:
        acquire_instance_lock(home)
    assert exc.value.message == "Leasegrid Sync could not write its lock file."
    assert sleeps, "the real-permission verdict comes after the retries, not on the first refusal"


def test_contention_on_the_second_try_is_already_running(tmp_path, monkeypatch):
    """Held elsewhere first (no PID yet), then the rival is deleting the file."""
    home, _lock, _sleeps = _setup(tmp_path, monkeypatch, ["busy", "perm"])
    monkeypatch.setattr(appmod, "_lock_pid_readable", lambda _lock: False)
    monkeypatch.setattr(appmod, "_lock_read_state", lambda _path, tries=3: appmod._LOCK_READABLE)
    assert acquire_instance_lock(home) is False


def test_contention_on_the_second_try_that_clears_takes_the_lock(tmp_path, monkeypatch):
    home, _lock, _sleeps = _setup(tmp_path, monkeypatch, ["busy", "perm", "ok"])
    monkeypatch.setattr(appmod, "_lock_pid_readable", lambda _lock: False)
    assert acquire_instance_lock(home) is True


# ---- real Windows delete-pending race ---------------------------------------

_win = pytest.mark.skipif(sys.platform != "win32", reason="delete-pending is a Windows file state")


def _delete_pending(path: Path):
    """Open the lock with DELETE and mark it for legacy (non-POSIX) delete. The name stays until close."""
    import ctypes
    from ctypes import wintypes

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateFileW.restype = wintypes.HANDLE
    k32.CreateFileW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
        wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
    ]
    k32.SetFileInformationByHandle.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    k32.CloseHandle.argtypes = [wintypes.HANDLE]
    delete, generic_read, share_all, open_existing, normal = 0x00010000, 0x80000000, 7, 3, 0x80
    handle = k32.CreateFileW(str(path), delete | generic_read, share_all, None, open_existing, normal, None)
    if handle in (None, ctypes.c_void_p(-1).value):
        raise ctypes.WinError(ctypes.get_last_error())

    class _Disposition(ctypes.Structure):
        _fields_ = [("DeleteFile", wintypes.BOOLEAN)]

    info = _Disposition(True)
    if not k32.SetFileInformationByHandle(handle, 4, ctypes.byref(info), ctypes.sizeof(info)):
        err = ctypes.get_last_error()
        k32.CloseHandle(handle)
        raise ctypes.WinError(err)
    return lambda: k32.CloseHandle(handle)


def _pending_lock(tmp_path: Path):
    home = tmp_path / "home"
    home.mkdir()
    lock = instance_lock_path(home)
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_bytes(b"")
    close = _delete_pending(lock)
    # Delete pending: the name is still listed (os.stat falls back to the
    # directory entry), but opening it is denied until the handle closes.
    assert os.path.exists(lock)
    with pytest.raises(PermissionError):
        open(lock, "rb").close()
    return home, lock, close


@_win
def test_windows_lock_being_deleted_by_a_rival_is_taken_once_it_is_gone(tmp_path):
    home, lock, close = _pending_lock(tmp_path)
    timer = threading.Timer(0.3, close)
    timer.start()
    try:
        assert acquire_instance_lock(home) is True
        assert lock.is_file()
    finally:
        timer.join()


@_win
def test_windows_lock_still_being_deleted_after_the_retries_is_already_running(tmp_path):
    home, _lock, close = _pending_lock(tmp_path)
    try:
        started = time.monotonic()
        assert acquire_instance_lock(home) is False
        assert time.monotonic() - started < 3.0
    finally:
        close()
