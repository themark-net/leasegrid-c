"""Platform-safe pid liveness and kill for test helpers.

On Windows ``os.kill(pid, 0)`` is ``TerminateProcess(pid, 0)``: it kills the
process instead of probing it, and ``signal.SIGKILL`` does not exist. Tests
that check or clean up recorded pids use these helpers instead.
"""

from __future__ import annotations

import os
import signal
import sys
from pathlib import Path


def is_zombie(pid: int) -> bool:
    """Linux only: a zombie still has a pid but is no longer running."""
    try:
        text = Path("/proc/%d/stat" % pid).read_text(encoding="utf-8")
    except OSError:
        return False
    tail = text.rsplit(")", 1)[-1].split()
    return bool(tail) and tail[0] == "Z"


def _alive_windows(pid: int) -> bool:
    import ctypes
    from ctypes import wintypes

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    STILL_ACTIVE = 259
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        # No such process, or no access to one: treat it as gone for our pids.
        return False
    try:
        code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
            return False
        return code.value == STILL_ACTIVE
    finally:
        kernel32.CloseHandle(handle)


def pid_alive(pid: int) -> bool:
    """True while ``pid`` is running. A Linux zombie counts as alive (unreaped)."""
    if pid <= 0:
        return False
    if sys.platform == "win32":
        return _alive_windows(pid)
    if is_zombie(pid):
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def kill_pid(pid: int) -> None:
    """Hard-kill one pid (never its group). No-op when it is already gone."""
    if pid <= 0 or not pid_alive(pid):
        return
    sig = getattr(signal, "SIGKILL", signal.SIGTERM)  # SIGTERM on Windows is TerminateProcess
    try:
        os.kill(pid, sig)
    except OSError:
        pass
