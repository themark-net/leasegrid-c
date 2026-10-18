"""Tahoe + Magic Folder control plane for Leasegrid Sync (no Qt, no WUI)."""

from __future__ import annotations

import json
import os
import re
import shutil
import signal
import socket
import stat
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote

from . import APP_ID

DEFAULT_TAHOE_NODEDIR = Path.home() / ".tahoe"
DEFAULT_MF_PORT = 19780
GRID_NICKNAME = "lab-friendnet"
# needed, happy, total for a client Sync creates itself. The lab friendnet has
# three storage nodes with shares.happy = 3; Tahoe's 3/7/10 default would make
# every upload fail there. Override with LEASEGRID_SHARES="n,h,t".
DEFAULT_SHARES = (2, 3, 3)
CREDIT_PLUGIN_NAME = "leasegrid-zkap-v0"
CREDIT_PLUGIN_SECTION = "[storageclient.plugins.%s]" % CREDIT_PLUGIN_NAME
TAHOE_START_TIMEOUT = 30.0
STORAGE_SETTLE_SECONDS = 6.0
# `tahoe invite` prints a code only once the inviter is parked on the relay, so a
# code join normally completes in seconds; this bounds a dead code / relay.
WORMHOLE_JOIN_TIMEOUT = 120.0
TAHOE_CONNECT_TIMEOUT = 30.0
# stop() waits this long for SIGTERM, then SIGKILL, then waits again.
TAHOE_STOP_WAIT = 10.0
MF_STOP_WAIT = 5.0
# Daemon logs and sync-ui.log rotate when they are over this size, not at it.
LOG_ROTATE_BYTES = 1024 * 1024


class SyncError(Exception):
    """Buyer-visible failure. ``next_hint`` is the in-window Next line.

    ``http_status`` is set only for a Magic Folder HTTP response.
    """

    def __init__(
        self,
        message: str,
        next_hint: str = "",
        http_status: Optional[int] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.next_hint = next_hint
        self.http_status = http_status

    def banner(self) -> str:
        text = self.message if self.message.startswith("FAIL") else "FAIL — " + self.message
        if self.next_hint:
            text = text + "\nNext: " + self.next_hint
        # Every window label renders this string. Mask at that moment, not when
        # the error is built, so the stored message keeps the real path.
        from .app import mask_shown_paths

        return mask_shown_paths(text)


@dataclass
class ConnectionStatus:
    state: str  # Connecting | Connected | Offline | FAIL
    detail: str = ""
    introducer_ok: bool = False
    servers_connected: int = 0
    server_nicknames: list[str] = field(default_factory=list)
    # Introducer-announced storage servers (nickname / nodeid / connection_status).
    announced_servers: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class FolderRow:
    name: str
    path: str
    status: str
    detail: str = ""


#: Known issue #30 is Magic Folder answering exactly HTTP 500. Not 5xx: a 501,
#: 502 or 503 is some other failure and must not be reported as #30.
ISSUE_30_HTTP_STATUS = 500


def is_issue_30_status(status: Optional[int]) -> bool:
    """True only for HTTP 500 (#30). ``None`` (no HTTP response) is never #30."""
    return status is not None and status == ISSUE_30_HTTP_STATUS


def default_home(platform: Optional[str] = None) -> Path:
    """Sync's data dir: Tahoe node, Magic Folder config, wallet, logs.

    LEASEGRID_SYNC_HOME wins. Otherwise the OS convention: %LOCALAPPDATA% on
    Windows, ~/Library/Application Support on macOS, $XDG_DATA_HOME or
    ~/.local/share elsewhere.
    """
    override = os.environ.get("LEASEGRID_SYNC_HOME")
    if override:
        return Path(override).expanduser()
    plat = platform or sys.platform
    if plat.startswith("win"):
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        return (Path(base) if base else Path.home() / "AppData" / "Local") / APP_ID
    if plat == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_ID
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / APP_ID
    return Path.home() / ".local" / "share" / APP_ID


def default_nodedir() -> Path:
    """Explicit env wins; then a pre-existing ~/.tahoe; else a Sync-owned dir.

    A fresh install has no ~/.tahoe, and Sync should create its own node under
    its data home rather than squat on Tahoe's default path.
    """
    env = os.environ.get("LEASEGRID_TAHOE_NODEDIR")
    if env:
        return Path(env).expanduser()
    if (DEFAULT_TAHOE_NODEDIR / "tahoe.cfg").is_file():
        return DEFAULT_TAHOE_NODEDIR
    return default_home() / "tahoe"


def storage_hostname() -> str:
    """Where this node advertises storage. Lab default is loopback.

    Set ``LEASEGRID_STORAGE_HOSTNAME`` to a LAN name or IP when other machines
    should put shares here. Unpaid join and offer use the same invite either way.
    """
    return (os.environ.get("LEASEGRID_STORAGE_HOSTNAME") or "127.0.0.1").strip() or "127.0.0.1"


def shares_config() -> tuple[int, int, int]:
    raw = os.environ.get("LEASEGRID_SHARES", "")
    if raw:
        try:
            parts = [int(p) for p in raw.split(",")]
        except ValueError:
            parts = []
        if len(parts) == 3 and 0 < parts[0] <= parts[1] <= parts[2]:
            return parts[0], parts[1], parts[2]
    return DEFAULT_SHARES


def frozen_sibling(name: str) -> Optional[str]:
    """In a PyInstaller bundle the daemons sit next to this executable.

    The bundle ships `tahoe` / `magic-folder` (`.exe` on Windows) beside
    `leasegrid-sync`; those must win over anything on the user's PATH so the
    versions we tested together are the ones that run.
    """
    if not getattr(sys, "frozen", False):
        return None
    here = Path(sys.executable).parent
    for candidate in (here / name, here / (name + ".exe")):
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def which_bin(name: str, env_key: str) -> Optional[str]:
    env = os.environ.get(env_key)
    if env:
        p = Path(env).expanduser()
        if p.is_file() and os.access(p, os.X_OK):
            return str(p)
    sibling = frozen_sibling(name)
    if sibling:
        return sibling
    found = shutil.which(name)
    return found


def redact_furl(value: str) -> str:
    text = value.strip()
    if text.startswith("pb://") and len(text) > 12:
        return text[:8] + "…" + text[-6:]
    return text


def _owns_process_group(proc: subprocess.Popen) -> bool:
    """True only for a daemon this process put in its own group."""
    return bool(getattr(proc, "_leasegrid_group", False))


def _foreign_pgid(proc: subprocess.Popen) -> Optional[int]:
    """Group id to signal, or None when that would hit our own group."""
    if sys.platform == "win32" or not _owns_process_group(proc):
        return None
    try:
        # nosemgrep: posix-only-process-api -- win32 returned above; this pid is a child we started
        pgid = os.getpgid(proc.pid)
    except OSError:
        # macOS getpgid fails (ESRCH) on a zombie. popen_hidden used
        # start_new_session, so the group id is the leader's pid, and while
        # returncode is None nobody has reaped it, so that id is still pinned.
        if proc.returncode is not None:
            return None
        pgid = proc.pid
    try:
        # nosemgrep: posix-only-process-api -- win32 returned above; used only to avoid signalling our own group
        own = os.getpgrp()
    except OSError:
        own = None
    if pgid <= 0 or pgid == own:
        return None
    return pgid


def _signal_group(pgid: int, sig: int) -> None:
    try:
        # nosemgrep: posix-only-process-api, signal-to-stored-pid -- caller passes a pgid from _foreign_pgid only while the leader we started is still unreaped; never our own group
        os.killpg(pgid, sig)
    except OSError:
        pass


def _taskkill_tree(pid: int) -> None:
    """Windows tree kill. ``taskkill /T /F`` is the supported equivalent of killpg."""
    if pid <= 0:
        return
    subprocess.run(
        ["taskkill", "/PID", str(pid), "/T", "/F"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def _close_stdin(proc: subprocess.Popen) -> None:
    try:
        if proc.stdin:
            proc.stdin.close()
    except OSError:
        pass


def _wait_proc(proc: subprocess.Popen, timeout: float) -> None:
    try:
        proc.wait(timeout=timeout)
    except (subprocess.TimeoutExpired, OSError):
        pass


def _waitid_flags() -> Optional[int]:
    """waitid flags that observe an exit without reaping, or None when absent."""
    if sys.platform == "win32" or not hasattr(os, "waitid"):
        return None
    if not all(hasattr(os, name) for name in ("WEXITED", "WNOWAIT", "WNOHANG")):
        return None
    return os.WEXITED | os.WNOWAIT | os.WNOHANG  # type: ignore[attr-defined]


def _darwin_leader_state(pid: int) -> str:
    """macOS: 'running' or 'exited', observed with kqueue and never reaped.

    macOS waitid with WNOWAIT and WNOHANG is not reliable (it can collect the
    child or report nothing), so it is not used there. EVFILT_PROC NOTE_EXIT
    only watches. ESRCH on attach means the leader has already exited; the
    caller has not reaped it (returncode is None), so it is still a zombie
    that pins the group id.
    """
    import errno
    import select

    try:
        kq = select.kqueue()
    except OSError:
        return "running"
    try:
        ev = select.kevent(
            pid,
            filter=select.KQ_FILTER_PROC,
            flags=select.KQ_EV_ADD | select.KQ_EV_ONESHOT,
            fflags=select.KQ_NOTE_EXIT,
        )
        try:
            events = kq.control([ev], 1, 0)
        except ProcessLookupError:
            return "exited"
        except OSError as exc:
            return "exited" if exc.errno == errno.ESRCH else "running"
        for got in events:
            if got.flags & select.KQ_EV_ERROR:
                return "exited" if got.data == errno.ESRCH else "running"
            if got.fflags & select.KQ_NOTE_EXIT:
                return "exited"
        return "running"
    finally:
        kq.close()


def _leader_state(proc: subprocess.Popen) -> str:
    """'running', 'exited' (zombie, group id still pinned), or 'reaped'.

    waitid with WNOWAIT does not collect the zombie. poll() would, and the
    process-group id could then be reused before the group is killed.
    ChildProcessError and OSError mean the leader is already gone. Windows
    has no waitid; poll() there observes and reaps, which the Windows
    tree-kill path already does.
    """
    if proc.returncode is not None:
        return "reaped"
    if sys.platform == "darwin":
        return _darwin_leader_state(proc.pid)
    flags = _waitid_flags()
    if flags is None:
        return "running" if proc.poll() is None else "reaped"
    try:
        info = os.waitid(os.P_PID, proc.pid, flags)
    except (ChildProcessError, OSError):
        return "reaped"
    if info is None:
        return "running"
    return "exited"


def _wait_leader_state(proc: subprocess.Popen, timeout: float) -> str:
    """Poll without reaping until the leader has left or the timeout is up."""
    deadline = time.time() + max(0.0, timeout)
    while True:
        state = _leader_state(proc)
        if state != "running":
            return state
        remaining = deadline - time.time()
        if remaining <= 0:
            return "running"
        time.sleep(min(0.05, remaining))


def _finish_exited_group(proc: subprocess.Popen, pgid: int, terminate_timeout: float) -> None:
    """SIGKILL a group whose leader is an unreaped zombie, then reap the leader."""
    if _leader_state(proc) == "reaped":
        return
    # nosemgrep: posix-only-process-api -- pgid is None on Windows, so this SIGKILL is not reached there
    _signal_group(pgid, signal.SIGKILL)
    _wait_proc(proc, terminate_timeout)


def reap_child(proc: subprocess.Popen, terminate_timeout: float) -> None:
    """Stop a child and reap it so it cannot stay a zombie.

    A daemon this process started in its own session owns that process group.
    SIGTERM goes to the group, then the leader's exit is observed with
    os.waitid(WNOWAIT) (kqueue NOTE_EXIT on macOS, where waitid WNOWAIT is
    unreliable) so the zombie still pins the group id. Members that
    obey SIGTERM get a short grace, at most half a second. The group then
    gets SIGKILL, and only after that does proc.wait() reap the leader.
    A grandchild that ignores SIGTERM dies in that SIGKILL. If the leader
    had already exited and is still unreaped, the group is still SIGKILLed
    before the reap.

    poll() is the wrong check here: it reaps the leader, so the SIGKILL was
    skipped and a TERM-ignoring grandchild survived. Once the leader is
    already reaped (returncode is set, or waitid raises ChildProcessError
    or OSError), the group is not signalled, because that id may have been
    reused.

    A process we did not put in a new group is signalled alone. This
    process's own group is never signalled. On Windows the group path is
    CTRL_BREAK_EVENT and then ``taskkill /T /F``. Only ``TimeoutExpired``
    and ``OSError`` are caught on the lone-process path.
    """
    # returncode is set only after a reap. Do this before any use of the pid.
    if proc.returncode is not None:
        return
    pgid = _foreign_pgid(proc)
    windows_tree = sys.platform == "win32" and _owns_process_group(proc)
    _close_stdin(proc)
    if pgid is not None:
        state = _leader_state(proc)
        if state == "reaped":
            return
        if state == "running":
            _signal_group(pgid, signal.SIGTERM)
            state = _wait_leader_state(proc, terminate_timeout)
            if state == "reaped":
                return
            if state == "running":
                # nosemgrep: posix-only-process-api -- pgid is None on Windows, so this SIGKILL is not reached there
                _signal_group(pgid, signal.SIGKILL)
                _wait_proc(proc, terminate_timeout)
                return
            # The leader is already a zombie. TERM-obeying members get a
            # short grace; a member that ignores SIGTERM still needs SIGKILL.
            grace = min(0.5, max(0.0, terminate_timeout))
            deadline = time.time() + grace
            while time.time() < deadline:
                if _leader_state(proc) == "reaped":
                    return
                time.sleep(min(0.05, max(0.0, deadline - time.time())))
        _finish_exited_group(proc, pgid, terminate_timeout)
        return
    if windows_tree:
        if proc.poll() is not None:
            return
        try:
            proc.send_signal(signal.CTRL_BREAK_EVENT)
        except OSError:
            pass
        _wait_proc(proc, terminate_timeout)
        if proc.poll() is None:
            _taskkill_tree(proc.pid)
            _wait_proc(proc, terminate_timeout)
        return
    try:
        proc.terminate()
        proc.wait(timeout=terminate_timeout)
        return
    except subprocess.TimeoutExpired:
        pass
    except OSError:
        pass
    try:
        proc.kill()
        proc.wait(timeout=terminate_timeout)
    except subprocess.TimeoutExpired:
        pass
    except OSError:
        pass


def rotate_log(path: Path) -> None:
    """If ``path`` is over 1 MiB, rename it to ``<name>.1``. Never raises.

    An older ``.1`` is replaced. A failure (read-only directory, busy name)
    leaves the current file in place so the caller can still open it.
    """
    try:
        if not path.is_file() or path.stat().st_size <= LOG_ROTATE_BYTES:
            return
        backup = path.with_name(path.name + ".1")
        try:
            if backup.exists():
                backup.unlink()
        except OSError:
            return
        os.replace(path, backup)
    except OSError:
        return


def popen_hidden(cmd: list[str], log_f) -> subprocess.Popen:
    """Spawn a daemon in its own process group, without a console flash.

    POSIX uses ``start_new_session`` so the child's pid is the process-group
    id. Windows ORs ``CREATE_NEW_PROCESS_GROUP`` with ``CREATE_NO_WINDOW``.
    ``stop`` will signal that group only when this flag is set.
    """
    kwargs: dict[str, Any] = {
        "stdin": subprocess.PIPE,
        "stdout": log_f,
        "stderr": subprocess.STDOUT,
    }
    if sys.platform == "win32":
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        flags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        kwargs["creationflags"] = flags
    else:
        kwargs["start_new_session"] = True
    proc = subprocess.Popen(cmd, **kwargs)
    proc._leasegrid_group = True  # type: ignore[attr-defined]
    return proc


def storage_offered(nodedir: Path) -> bool:
    """True when this Tahoe node is configured to store shares for others."""
    import configparser

    cfg = configparser.ConfigParser()
    path = Path(nodedir) / "tahoe.cfg"
    if not path.is_file():
        return False
    cfg.read(path, encoding="utf-8")
    if not cfg.has_section("storage"):
        return False
    try:
        return cfg.getboolean("storage", "enabled", fallback=True)
    except ValueError:
        return True


@dataclass(frozen=True)
class DiskSlices:
    """One local disk, split into used / free-kept / offered.

    ``free`` is the raw free bytes from the OS. ``kept`` is the free bytes this
    device is not offering. ``offered`` is the free bytes it will store for the
    friendnet. used + kept + offered == used + free.
    """

    total: int
    used: int
    free: int
    offered: int
    kept: int

    @property
    def offered_percent(self) -> int:
        if self.total <= 0:
            return 0
        return int(round(100.0 * self.offered / self.total))


def format_bytes(n: int) -> str:
    """Short size for the offer legend (1000-based, one decimal past bytes)."""
    n = max(0, int(n))
    units = ("B", "KB", "MB", "GB", "TB")
    value = float(n)
    idx = 0
    while value >= 1000.0 and idx < len(units) - 1:
        value /= 1000.0
        idx += 1
    if idx == 0:
        return "%d B" % n
    return "%.1f %s" % (value, units[idx])


def offer_disk_path(home: Path, nodedir: Path) -> Path:
    """Filesystem path whose ``disk_usage`` is 'this disk' for the offer pie."""
    for candidate in (Path(home) / "storage", Path(nodedir), Path(home)):
        if candidate.exists():
            return candidate
    return Path(home)


def storage_reserved_raw(nodedir: Path) -> Optional[str]:
    """``[storage] reserved_space`` as written, or None when unset.

    Line scan, not ConfigParser: a value like ``50%`` is not an interpolation.
    """
    path = Path(nodedir) / "tahoe.cfg"
    if not path.is_file():
        return None
    in_storage = False
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_storage = stripped.lower() == "[storage]"
            continue
        if not in_storage or not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, val = stripped.split("=", 1)
        if key.strip().lower() == "reserved_space":
            return val.strip()
    return None


_RESERVED_PCT = re.compile(r"^(\d+(?:\.\d+)?)%$")
_RESERVED_SIZE = re.compile(r"^(\d+(?:\.\d+)?)([kmgt]i?b?)?$", re.IGNORECASE)
_RESERVED_MULT = {
    "": 1,
    "k": 1024,
    "kb": 1000,
    "kib": 1024,
    "m": 1024**2,
    "mb": 1000**2,
    "mib": 1024**2,
    "g": 1024**3,
    "gb": 1000**3,
    "gib": 1024**3,
    "t": 1024**4,
    "tb": 1000**4,
    "tib": 1024**4,
}


def parse_reserved_space(raw: str, total: int) -> int:
    """Tahoe ``reserved_space``: bytes, ``1G`` / ``1GiB`` / ``1GB``, or ``50%``."""
    text = (raw or "").strip().replace(" ", "")
    if not text:
        return 0
    pct = _RESERVED_PCT.fullmatch(text)
    if pct:
        return max(0, int(float(pct.group(1)) / 100.0 * max(0, total)))
    size = _RESERVED_SIZE.fullmatch(text)
    if size is None:
        mult = None
    elif size.group(2):
        mult = _RESERVED_MULT.get(size.group(2).lower())
    else:
        mult = 1
    if size is None or mult is None:
        raise SyncError(
            "could not read this disk offer. reserved_space is not a size.",
            "set reserved_space to bytes, a size like 1G, or a percent; Retry.",
        )
    return max(0, int(float(size.group(1)) * mult))


def compute_slices(total: int, used: int, free: int, *, offering: bool, reserved: int) -> DiskSlices:
    """Partition this disk. Offered is free space beyond the Tahoe reserve."""
    total = max(0, int(total))
    used = max(0, int(used))
    free = max(0, int(free))
    if not offering:
        return DiskSlices(total=total, used=used, free=free, offered=0, kept=free)
    kept = min(free, max(0, int(reserved)))
    return DiskSlices(total=total, used=used, free=free, offered=free - kept, kept=kept)


HOSTED_FAIL_MSG = "could not load how much you are hosting for others."
HOSTED_FAIL_NEXT = "Retry. Disk Offer slider and pie still work."
SETTLEMENT_FAIL_MSG = "could not load settlement status."
SETTLEMENT_FAIL_NEXT = "Retry; check network / issuer; do not assume you were paid."


@dataclass(frozen=True)
class HostedShares:
    """Share files this node stores under Tahoe ``storage/shares``.

    Not disk-pie Used. ``bytes_hosted`` is the sum of regular files in that
    tree; zero files is an honest empty, not a failure.
    """

    bytes_hosted: int
    files: int


def read_hosted_shares(nodedir: Path) -> HostedShares:
    """Local shares hosted for the grid. Does not read ``disk_usage``."""
    root = Path(nodedir) / "storage" / "shares"
    if not root.exists():
        return HostedShares(bytes_hosted=0, files=0)
    if not root.is_dir():
        raise SyncError(HOSTED_FAIL_MSG, HOSTED_FAIL_NEXT)
    total = 0
    files = 0
    try:
        for dirpath, dirnames, names in os.walk(root):
            dirnames.sort()
            for name in sorted(names):
                path = Path(dirpath) / name
                try:
                    st = path.lstat()
                except OSError as exc:
                    raise SyncError(HOSTED_FAIL_MSG, HOSTED_FAIL_NEXT) from exc
                if not stat.S_ISREG(st.st_mode):
                    continue
                total += st.st_size
                files += 1
    except SyncError:
        raise
    except OSError as exc:
        raise SyncError(HOSTED_FAIL_MSG, HOSTED_FAIL_NEXT) from exc
    return HostedShares(bytes_hosted=total, files=files)


def format_hosted_strip(
    shares: HostedShares,
    *,
    accepted: Optional[int] = None,
    settlement_error: str = "",
) -> str:
    """Operator copy for the Offer hosted strip. Never a disk-used figure."""
    if shares.files <= 0 and shares.bytes_hosted <= 0:
        empty = (
            "Nothing hosted for others yet.\n"
            "When buyers store shares here, usage shows up for settlement."
        )
        if settlement_error:
            return settlement_error + "\n" + empty
        return empty
    lines = ["Hosting %s for the friendnet" % format_bytes(shares.bytes_hosted)]
    if settlement_error:
        lines.append(settlement_error)
    elif accepted is not None and accepted > 0:
        # One spent ZKAP token is one GiB-share-month (v0 denomination).
        lines.append("(%d GiB·share·mo accepted toward settlement)" % accepted)
    else:
        lines.append("Settlement status: not available on this network yet.")
        lines.append("Hosted size still shown from local storage.")
    return "\n".join(lines)


def _ini_section(nodedir: Path, section: str) -> dict[str, str]:
    """Keys in one ``tahoe.cfg`` section. Missing file or section → empty."""
    path = Path(nodedir) / "tahoe.cfg"
    if not path.is_file():
        return {}
    want = "[" + section.strip().lower() + "]"
    in_section = False
    out: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise SyncError(SETTLEMENT_FAIL_MSG, SETTLEMENT_FAIL_NEXT) from exc
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_section = stripped.lower() == want
            continue
        if not in_section or not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, val = stripped.split("=", 1)
        out[key.strip().lower()] = val.strip()
    return out


def zkap_storage_plugin(nodedir: Path) -> dict[str, str]:
    """``[storageserver.plugins.leasegrid-zkap-v0]`` as written. No defaults invented."""
    return _ini_section(nodedir, "storageserver.plugins.%s" % CREDIT_PLUGIN_NAME)


def read_my_nodeid(nodedir: Path) -> str:
    path = Path(nodedir) / "my_nodeid"
    if not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def zkap_plugin_issuer(nodedir: Path) -> str:
    plugin = zkap_storage_plugin(nodedir)
    return (plugin.get("issuer-url") or plugin.get("issuer_url") or "").strip()


def zkap_plugin_nodeid(nodedir: Path) -> str:
    plugin = zkap_storage_plugin(nodedir)
    node = (plugin.get("nodeid") or plugin.get("node-id") or "").strip()
    if node:
        return node
    return read_my_nodeid(nodedir)


def read_local_accepted(nodedir: Path) -> Optional[tuple[int, bool]]:
    """Spent-set token count on this node, or None when no path is configured.

    ``(count, same_epoch)``. A missing file at a configured path is zero
    accepted, not an error. Unreadable or malformed JSON raises ``SyncError``.
    """
    plugin = zkap_storage_plugin(nodedir)
    raw = (plugin.get("spent-set-path") or plugin.get("spent_set_path") or "").strip()
    if not raw:
        return None
    path = Path(raw)
    if not path.is_absolute():
        path = Path(nodedir) / path
    if not path.exists():
        return (0, True)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SyncError(SETTLEMENT_FAIL_MSG, SETTLEMENT_FAIL_NEXT) from exc
    spent = data.get("spent") if isinstance(data, dict) else None
    if not isinstance(spent, list):
        raise SyncError(SETTLEMENT_FAIL_MSG, SETTLEMENT_FAIL_NEXT)
    epochs: list[Any] = []
    for row in spent:
        if not isinstance(row, dict) or not isinstance(row.get("t"), str) or not row.get("t"):
            raise SyncError(SETTLEMENT_FAIL_MSG, SETTLEMENT_FAIL_NEXT)
        if "token_epoch" in row:
            epochs.append(row.get("token_epoch"))
    same = len(set(epochs)) <= 1
    return (len(spent), same)


def read_disk_offer(nodedir: Path, home: Path) -> DiskSlices:
    """Local disk pie inputs. Raises ``SyncError`` when the disk cannot be read."""
    path = offer_disk_path(home, nodedir)
    try:
        usage = shutil.disk_usage(path)
    except OSError as exc:
        # ``str(exc)`` is an errno line. The path stays; the errno text does not.
        raise SyncError(
            "could not read this disk.",
            "check that %s is mounted; Retry." % path,
        ) from exc
    if usage.total <= 0:
        raise SyncError(
            "could not read this disk. Reported size is zero.",
            "check that the disk is mounted; Retry.",
        )
    offering = storage_offered(nodedir)
    reserved = 0
    if offering:
        raw = storage_reserved_raw(nodedir)
        if raw:
            reserved = parse_reserved_space(raw, usage.total)
    return compute_slices(usage.total, usage.used, usage.free, offering=offering, reserved=reserved)


def node_can_offer_storage(nodedir: Path, home: Path) -> bool:
    """True when this node was created with storage, not ``--no-storage``."""
    if storage_offered(nodedir):
        return True
    for candidate in (Path(home) / "storage", Path(nodedir) / "storage"):
        if candidate.is_dir():
            return True
    return False


def _upsert_storage(nodedir: Path, values: dict[str, str]) -> None:
    """Set keys in ``[storage]``, creating the section when missing."""
    path = Path(nodedir) / "tahoe.cfg"
    if not path.is_file():
        raise SyncError(
            "could not offer disk. No Tahoe node config on this device.",
            "join the friendnet first; Retry.",
        )
    lines = path.read_text(encoding="utf-8").splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip().lower() == "[storage]":
            start = i
            break
    pending = {k.lower(): v for k, v in values.items()}
    if start is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append("[storage]")
        for key, val in pending.items():
            lines.append("%s = %s" % (key, val))
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return
    end = len(lines)
    for j in range(start + 1, len(lines)):
        stripped = lines[j].strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            end = j
            break
    section = [lines[start]]
    seen: set[str] = set()
    for line in lines[start + 1 : end]:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            section.append(line)
            continue
        key = stripped.split("=", 1)[0].strip().lower()
        if key in pending:
            section.append("%s = %s" % (key, pending[key]))
            seen.add(key)
        else:
            section.append(line)
    for key, val in pending.items():
        if key not in seen:
            section.append("%s = %s" % (key, val))
    path.write_text("\n".join(lines[:start] + section + lines[end:]) + "\n", encoding="utf-8")


def apply_offer_percent(nodedir: Path, home: Path, percent: int) -> DiskSlices:
    """Persist how much of this disk to offer. 0% turns storage off.

    A sync-only node (no storage dir, storage disabled) cannot be flipped on
    from here — that needs a rejoin with Offer disk checked.
    """
    percent = max(0, min(100, int(percent)))
    path = offer_disk_path(home, nodedir)
    try:
        usage = shutil.disk_usage(path)
    except OSError as exc:
        raise SyncError(
            "could not offer disk.",
            "check that %s is mounted; Retry." % path,
        ) from exc
    if usage.total <= 0:
        raise SyncError(
            "could not offer disk. Reported size is zero.",
            "check that the disk is mounted; Retry.",
        )
    if percent == 0:
        _upsert_storage(nodedir, {"enabled": "false"})
        return compute_slices(usage.total, usage.used, usage.free, offering=False, reserved=0)
    if not node_can_offer_storage(nodedir, home):
        raise SyncError(
            "could not offer disk. This device joined sync-only.",
            "rejoin with Offer disk checked; Retry.",
        )
    desired = int(round(usage.total * (percent / 100.0)))
    if desired > usage.free:
        desired = usage.free
    if desired <= 0:
        _upsert_storage(nodedir, {"enabled": "false"})
        return compute_slices(usage.total, usage.used, usage.free, offering=False, reserved=0)
    reserved = usage.free - desired
    _upsert_storage(nodedir, {"enabled": "true", "reserved_space": str(reserved)})
    return compute_slices(
        usage.total, usage.used, usage.free, offering=True, reserved=reserved
    )


# magic-wormhole code as printed by `tahoe invite`: "7-guitarist-revenge"
WORMHOLE_CODE_RE = re.compile(r"^[0-9]{1,3}(-[a-z0-9]+){2,}$")


def is_wormhole_code(text: str) -> bool:
    return bool(WORMHOLE_CODE_RE.match((text or "").strip().lower()))


# Tahoe 1.20 `create-node --join` (and create-client) writes the invited encoding as bytes reprs
# ("shares.needed = b'3'"), which `tahoe run` then rejects with ValueError.
JOINED_BYTES_RE = re.compile(r"^(\s*shares\.(?:needed|happy|total)\s*=\s*)b'([0-9]+)'\s*$")


def fix_joined_shares(cfg_path: Path) -> bool:
    """Rewrite b'N' share counts left by `--join`. Returns True if changed."""
    if not cfg_path.is_file():
        return False
    changed = False
    out: list[str] = []
    for line in cfg_path.read_text(encoding="utf-8").splitlines():
        m = JOINED_BYTES_RE.match(line)
        if m:
            line = "%s%s" % (m.group(1), m.group(2))
            changed = True
        out.append(line)
    if changed:
        cfg_path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return changed


# stderr fragments from magic-wormhole and Tahoe. Matched case-insensitively.
# The buyer message must not repeat these (no module path, no exception class).
_EXPIRED_MARKERS = ("lonelyerror", "lonely", "code expired", "has expired")
_REJECTED_MARKERS = ("wrongpassword", "wrong password", "rejected", "crowded")
_NETWORK_MARKERS = (
    "connectionrefused",
    "connection refused",
    "connection reset",
    "connection aborted",
    "serverconnection",
    "welcomeerror",
    "network is unreachable",
    "network unreachable",
    "no route to host",
    "name or service not known",
    "temporary failure in name resolution",
    "nodename nor servname",
    "timed out",
    "timeout",
    "gaierror",
    "could not connect",
    "failed to connect",
)


def _stderr_mentions(raw: str, markers: tuple[str, ...]) -> bool:
    text = (raw or "").lower()
    return any(marker in text for marker in markers)


def join_process_failure(invite: str, raw: str, *, code: bool) -> SyncError:
    """Buyer copy for a failed ``tahoe create-node``. Never echoes stderr."""
    if code:
        if _stderr_mentions(raw, _EXPIRED_MARKERS):
            return SyncError(
                "could not join this friendnet. Invite code %s expired before anyone answered."
                % invite,
                "codes are single-use and expire; ask your inviter for a fresh one; Retry.",
            )
        if _stderr_mentions(raw, _NETWORK_MARKERS):
            return SyncError(
                "could not join this friendnet. Invite code %s could not reach the invite mailbox."
                % invite,
                "check the network path, then Retry.",
            )
        if _stderr_mentions(raw, _REJECTED_MARKERS):
            return SyncError(
                "could not join this friendnet. Invite code %s was not accepted." % invite,
                "ask your inviter for a fresh code; Retry.",
            )
        return SyncError(
            "could not join this friendnet. Invite code %s was not accepted." % invite,
            "codes are single-use and expire; ask your inviter for a fresh one; Retry.",
        )
    if _stderr_mentions(raw, _NETWORK_MARKERS):
        return SyncError(
            "could not join this friendnet. Tahoe could not reach the friendnet.",
            "check the network path to the introducer; Retry.",
        )
    return SyncError(
        "could not join this friendnet. Tahoe could not create a node.",
        "check the invite with your inviter; Retry.",
    )


def join_tahoe_missing() -> SyncError:
    """Buyer copy when ``tahoe`` is not on disk. No path and no exception text."""
    return SyncError(
        "could not join this friendnet. The Tahoe client is not installed.",
        "install it next to Sync: pip install 'leasegrid-zkap-lab[sync,tahoe]'; Retry.",
    )


def join_spawn_failure(
    exc: BaseException, *, invite: str, code: bool, timeout: float
) -> SyncError:
    """Buyer copy when ``tahoe create-node`` does not return stderr.

    FileNotFoundError and TimeoutExpired used to be interpolated into the
    banner. The buyer text matches the expired / rejected / network mapping
    and never includes the exception, a module, or a filesystem path.
    A generic OSError (anything other than a missing binary) uses the same
    rule: the strerror is not copied into the window.
    """
    if isinstance(exc, subprocess.TimeoutExpired):
        if code:
            return SyncError(
                "could not join this friendnet. Nobody answered invite code %s in %ds."
                % (invite, int(timeout)),
                "your inviter must keep `tahoe invite` running until you join; "
                "get a fresh code; Retry.",
            )
        return SyncError(
            "could not join this friendnet. Tahoe did not finish creating a node in time.",
            "check the network path to the introducer; Retry.",
        )
    if isinstance(exc, FileNotFoundError):
        return join_tahoe_missing()
    # Any other spawn failure, including OSError. Do not append str(exc).
    return SyncError(
        "could not join this friendnet. The Tahoe client could not be started.",
        "install it next to Sync: pip install 'leasegrid-zkap-lab[sync,tahoe]'; Retry.",
    )


def join_filesystem_failure(exc: BaseException) -> SyncError:
    """Buyer copy when join cannot create a directory or open a file.

    ``str(exc)`` is an errno line plus a path, or a decode reason. Every
    filesystem failure uses the same sentence. Do not append ``str(exc)``.
    """
    return SyncError(
        "could not join this friendnet. This computer would not let "
        "Leasegrid Sync save its files.",
        "check that the Sync folder is writable, then Retry.",
    )


def _join_message(detail: str) -> str:
    """One ``could not join this friendnet.`` lead.

    Connection status already stores that lead inside ``detail`` when welcome()
    failed. Prefixing it again put the phrase in the window twice.
    """
    lead = "could not join this friendnet."
    text = (detail or "").strip()
    if text.lower().startswith(lead):
        return text
    if not text:
        return lead
    return "%s %s" % (lead, text)


def validate_invite(raw: str) -> str:
    """Accept a join URL, a pb:// introducer furl, or a short `tahoe invite` code."""
    from .invite import parse_invite

    return parse_invite(raw).token


def validate_introducer_furl(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        raise SyncError(
            "could not join this friendnet. Invite is empty.",
            "paste the invite from your inviter (a short code like 7-word-word, or a pb:// furl).",
        )
    low = text.lower()
    if low.startswith("http://") or low.startswith("https://"):
        raise SyncError(
            "could not join this friendnet. That looks like a web URL.",
            "Leasegrid Sync does not use the Tahoe web UI. Paste the invite code or pb:// furl.",
        )
    if not text.startswith("pb://"):
        raise SyncError(
            "could not join this friendnet. Invite code invalid.",
            "ask your inviter for a fresh invite (short code like 7-word-word, or pb://…); Retry.",
        )
    rest = text[5:]
    if "/" not in rest or len(rest) < 12:
        raise SyncError(
            "could not join this friendnet. Invite furl is malformed.",
            "get a fresh code from your inviter; check network; Retry.",
        )
    return text


def endpoint_to_url(endpoint: str) -> str:
    text = endpoint.strip()
    if text in ("", "not running"):
        raise SyncError(
            "Magic Folder daemon is not running.",
            "Restart Sync. If this persists, check that magic-folder is on PATH.",
        )
    parts = text.split(":")
    if parts[0] != "tcp" or len(parts) < 3:
        raise SyncError(
            "Magic Folder endpoint is unreadable.",
            "Restart Sync. Delete the daemon config only if you know it is stale.",
        )
    host = parts[1] or "127.0.0.1"
    port = parts[2]
    if "=" in host:
        host = "127.0.0.1"
    return "http://%s:%s" % (host, port)


class TahoeClient:
    def __init__(
        self,
        nodedir: Optional[Path] = None,
        tahoe_bin: Optional[str] = None,
        home: Optional[Path] = None,
    ) -> None:
        self.nodedir = Path(nodedir) if nodedir else default_nodedir()
        self.tahoe_bin = tahoe_bin or which_bin("tahoe", "LEASEGRID_TAHOE_BIN")
        self.home = Path(home) if home else default_home()
        self.log_path = self.home / "logs" / "tahoe.log"
        self._proc: Optional[subprocess.Popen] = None

    # -- process management -------------------------------------------------

    def require_bin(self) -> str:
        if not self.tahoe_bin:
            raise join_tahoe_missing()
        return self.tahoe_bin

    def is_reachable(self) -> bool:
        try:
            self.welcome(timeout=2.0)
            return True
        except SyncError:
            return False

    def create_client(self, invite: str, shares: Optional[tuple[int, int, int]] = None) -> None:
        """Client-only node: ``create-node --no-storage``. Prefer ``create_node``."""
        self.create_node(invite, shares=shares, offer_storage=False)

    def create_node(
        self,
        invite: str,
        shares: Optional[tuple[int, int, int]] = None,
        offer_storage: bool = True,
    ) -> None:
        """``tahoe create-node`` into self.nodedir.

        Unpaid join and offer are the same command. ``offer_storage=False`` adds
        ``--no-storage --listen=none``. ``invite`` is a pb:// introducer furl
        (we pick the encoding) or a short ``tahoe invite`` code (the inviter's
        introducer + encoding arrive through magic-wormhole).
        """
        if self.has_nodedir():
            return
        if self.nodedir.exists() and any(self.nodedir.iterdir()):
            raise SyncError(
                "could not join this friendnet. %s exists but is not a Tahoe node."
                % self.nodedir,
                "move that directory aside or set LEASEGRID_TAHOE_NODEDIR; Retry.",
            )
        cmd = [self.require_bin()]
        relay = os.environ.get("LEASEGRID_WORMHOLE_SERVER")
        if relay:
            cmd += ["--wormhole-server", relay]
        cmd += [
            "create-node",
            "--nickname=%s" % (os.environ.get("LEASEGRID_NICKNAME") or "leasegrid-sync"),
            "--webport=tcp:0:interface=127.0.0.1",
        ]
        if offer_storage:
            storage_dir = self.home / "storage"
            try:
                storage_dir.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                raise join_filesystem_failure(exc) from exc
            cmd += [
                "--listen=tcp",
                "--hostname=%s" % storage_hostname(),
                "--storage-dir=%s" % storage_dir,
            ]
        else:
            cmd += ["--no-storage", "--listen=none"]
        code = is_wormhole_code(invite)
        if code:
            cmd.append("--join=%s" % invite.strip().lower())
            timeout = WORMHOLE_JOIN_TIMEOUT
        else:
            needed, happy, total = shares or shares_config()
            cmd += [
                "--introducer=%s" % invite,
                "--shares-needed=%d" % needed,
                "--shares-happy=%d" % happy,
                "--shares-total=%d" % total,
            ]
            timeout = 120
        cmd.append(str(self.nodedir))
        try:
            self.nodedir.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise join_filesystem_failure(exc) from exc
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout, check=False
            )
        except (subprocess.TimeoutExpired, OSError) as exc:
            # A missing binary can still leave the basedir tahoe was about to use.
            if isinstance(exc, (subprocess.TimeoutExpired, FileNotFoundError)):
                shutil.rmtree(self.nodedir, ignore_errors=True)
            raise join_spawn_failure(
                exc, invite=invite, code=bool(code), timeout=timeout
            ) from exc
        if proc.returncode != 0:
            shutil.rmtree(self.nodedir, ignore_errors=True)
            raw = (proc.stderr or proc.stdout or "").strip()
            raise join_process_failure(invite, raw, code=bool(code))
        if code:
            fix_joined_shares(self.nodedir / "tahoe.cfg")
        self.ensure_credit_plugin()

    def ensure_credit_plugin(self) -> bool:
        """Enable the ZKAP storage plugin in tahoe.cfg, pointed at this app's wallet.

        Harmless on an ungated grid (Tahoe falls back to anonymous storage when a
        node does not announce the plugin); on a gated grid it is what pays for
        uploads. force_foolscap is required: 1.20 prefers GBS/HTTP when a node
        announces it, and the HTTP path never consults storage plugins.
        Edits are line-based so Tahoe's commented template survives.
        Returns True when the file changed (a running node needs a restart).
        """
        cfg_path = self.nodedir / "tahoe.cfg"
        if not cfg_path.is_file():
            return False
        text = cfg_path.read_text(encoding="utf-8")
        if CREDIT_PLUGIN_SECTION in text:
            return False
        lines = text.splitlines()
        out: list[str] = []
        in_client = False
        added_plugins = False
        client_lines = ["storage.plugins = %s" % CREDIT_PLUGIN_NAME, "force_foolscap = true"]
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                if in_client and not added_plugins:
                    out += client_lines
                    added_plugins = True
                in_client = stripped == "[client]"
            elif in_client and (
                stripped.startswith("storage.plugins") or stripped.startswith("force_foolscap")
            ):
                continue  # replaced by client_lines
            out.append(line)
        if in_client and not added_plugins:
            out += client_lines
            added_plugins = True
        if not added_plugins:
            out += ["", "[client]"] + client_lines
        out += [
            "",
            CREDIT_PLUGIN_SECTION,
            "wallet-path = %s" % (self.home / "credit-wallet.json"),
            "grants-path = %s" % (self.home / "credit-grants.json"),
            "recent-path = %s" % (self.home / "credit-recent.json"),
        ]
        cfg_path.write_text("\n".join(out) + "\n", encoding="utf-8")
        return True

    def start(self, timeout: float = TAHOE_START_TIMEOUT) -> None:
        """Run `tahoe run` as a child, holding stdin (Tahoe exits when stdin closes)."""
        if self.is_reachable():
            return
        if not self.has_nodedir():
            raise SyncError(
                "could not join this friendnet. No Tahoe node at %s." % self.nodedir,
                "paste an introducer furl to create one; Retry.",
            )
        if self._proc is not None:
            if _leader_state(self._proc) == "running":
                return
            # Exited but unreaped: the zombie still pins the group. Kill the
            # group before starting another daemon.
            reap_child(self._proc, TAHOE_STOP_WAIT)
            self._proc = None
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            rotate_log(self.log_path)
            log_f = open(self.log_path, "ab")  # noqa: SIM115  daemon keeps this handle for its lifetime
        except OSError as exc:
            raise join_filesystem_failure(exc) from exc
        try:
            self._proc = popen_hidden(
                [self.require_bin(), "run", str(self.nodedir)],
                log_f,
            )
        except OSError as exc:
            log_f.close()
            raise join_spawn_failure(exc, invite="", code=False, timeout=0) from exc
        deadline = time.time() + timeout
        while time.time() < deadline:
            if _leader_state(self._proc) != "running":
                proc = self._proc
                self._proc = None
                reap_child(proc, TAHOE_STOP_WAIT)
                # The log can hold a traceback and a furl. The window names the
                # file (operators asked to keep paths) and does not paste it.
                raise SyncError(
                    "could not join this friendnet. Tahoe exited while starting.",
                    "see %s; Retry." % self.log_path,
                )
            if self.is_reachable():
                return
            time.sleep(0.3)
        raise SyncError(
            "could not join this friendnet. Tahoe did not become ready in %ds." % int(timeout),
            "see %s; Retry." % self.log_path,
        )

    def stop(self, terminate_timeout: Optional[float] = None) -> None:
        proc = self._proc
        if proc is None:
            return
        timeout = TAHOE_STOP_WAIT if terminate_timeout is None else terminate_timeout
        reap_child(proc, timeout)
        self._proc = None

    def owns_process(self) -> bool:
        """True while this process still has to reap the daemon it started.

        An unreaped zombie counts: its process-group id is still the one
        stop() must signal. poll() is not used, because that would reap the
        leader and skip the group kill.
        """
        proc = self._proc
        if proc is None:
            return False
        return _leader_state(proc) != "reaped"

    def reload_static_servers(self) -> None:
        """Restart a node this process started so ``servers.yaml`` is picked up.

        A node Sync did not launch is left alone (we do not kill an external client).
        """
        if not self.owns_process():
            return
        self.stop()
        try:
            self.start()
        except SyncError as exc:
            raise SyncError(
                "could not reload storage servers. The storage client did not restart.",
                "Retry.",
            ) from exc

    def wait_connected(self, timeout: float = TAHOE_CONNECT_TIMEOUT) -> ConnectionStatus:
        """Poll until the introducer reports connected; return the last status otherwise."""
        deadline = time.time() + timeout
        status = self.connection_status()
        while status.state != "Connected" and time.time() < deadline:
            time.sleep(0.5)
            status = self.connection_status()
        # Storage (Foolscap) handshakes land a beat after the introducer; don't
        # report "0 storage" for a grid that is simply still connecting.
        settle = time.time() + STORAGE_SETTLE_SECONDS
        while status.state == "Connected" and "0 storage" in status.detail and time.time() < settle:
            time.sleep(0.5)
            status = self.connection_status()
        return status

    # -- status -------------------------------------------------------------

    def node_url(self) -> str:
        path = self.nodedir / "node.url"
        if not path.is_file():
            raise SyncError(
                "could not join this friendnet. No Tahoe client is configured at %s."
                % self.nodedir,
                "create or point LEASEGRID_TAHOE_NODEDIR at a running client; Retry.",
            )
        url = path.read_text(encoding="utf-8").strip()
        if not url:
            raise SyncError(
                "could not join this friendnet. Tahoe node.url is empty.",
                "start the Tahoe client and Retry.",
            )
        return url.rstrip("/")

    def welcome(self, timeout: float = 5.0) -> dict[str, Any]:
        url = self.node_url() + "/?t=json"
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                body = resp.read().decode("utf-8")
        except urllib.error.URLError as exc:
            raise SyncError(
                "could not join this friendnet. Tahoe client is not reachable.",
                "start Tahoe (tahoe run %s) and Retry." % self.nodedir,
            ) from exc
        try:
            data = json.loads(body)
        except json.JSONDecodeError as exc:
            raise SyncError(
                "could not join this friendnet. Tahoe returned unreadable status.",
                "check the Tahoe client logs; Retry.",
            ) from exc
        if not isinstance(data, dict):
            raise SyncError(
                "could not join this friendnet. Tahoe returned unreadable status.",
                "check the Tahoe client logs; Retry.",
            )
        return data

    def mkdir(self, timeout: float = 60.0) -> str:
        """Create an empty mutable directory on the grid; return its write cap."""
        url = self.node_url() + "/uri?t=mkdir"
        req = urllib.request.Request(url, data=b"", method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                cap = resp.read().decode("utf-8").strip()
        except urllib.error.URLError as exc:
            raise SyncError(
                "could not create a folder on the friendnet. Tahoe returned an error.",
                "check that storage nodes are connected; Retry.",
            ) from exc
        if not cap.startswith("URI:DIR2:"):
            raise SyncError(
                "could not create a folder on the friendnet. Unexpected reply from Tahoe.",
                "check the Tahoe client log; Retry.",
            )
        return cap

    def connection_status(self) -> ConnectionStatus:
        try:
            data = self.welcome()
        except SyncError as exc:
            return ConnectionStatus(state="FAIL", detail=exc.message)

        intro = data.get("introducers") or {}
        statuses = intro.get("statuses") or []
        introducer_ok = any(
            isinstance(s, str) and s.lower().startswith("connected") for s in statuses
        )
        servers = data.get("servers") or []
        nicknames = []
        announced: list[dict[str, Any]] = []
        connected = 0
        for srv in servers:
            if not isinstance(srv, dict):
                continue
            nick = str(srv.get("nickname") or "")
            raw_status = str(srv.get("connection_status") or "")
            st = raw_status.lower()
            if nick:
                nicknames.append(nick)
            if st.startswith("connected"):
                connected += 1
            announced.append(
                {
                    "nickname": nick,
                    "nodeid": str(srv.get("nodeid") or ""),
                    "connection_status": raw_status,
                }
            )
        if introducer_ok:
            state = "Connected"
            detail = "introducer up · %d storage" % connected
        elif connected:
            state = "Connecting"
            detail = "storage visible, introducer not confirmed"
        else:
            state = "Offline"
            detail = "Tahoe is up but the friendnet introducer is not connected"
        return ConnectionStatus(
            state=state,
            detail=detail,
            introducer_ok=introducer_ok,
            servers_connected=connected,
            server_nicknames=nicknames,
            announced_servers=announced,
        )

    def has_nodedir(self) -> bool:
        return (self.nodedir / "tahoe.cfg").is_file()

    def _bring_up(self) -> ConnectionStatus:
        """Reach the node (starting it if we can), then wait for the introducer."""
        if not self.is_reachable():
            if not self.tahoe_bin:
                status = self.connection_status()
                raise SyncError(
                    _join_message(status.detail),
                    "start the Tahoe client (tahoe run %s); Retry." % self.nodedir,
                )
            # Node is down anyway, so this is the safe moment to (re)enable paying.
            self.ensure_credit_plugin()
            self.start()
        status = self.wait_connected()
        if status.state == "FAIL":
            raise SyncError(
                _join_message(status.detail),
                "start the Tahoe client; check network; Retry.",
            )
        if status.state == "Offline":
            raise SyncError(
                "could not join this friendnet. Introducer is unreachable.",
                "check the network path to the introducer (and that it is running); Retry.",
            )
        return status

    def join_existing(self) -> ConnectionStatus:
        """Attach to a Tahoe node already configured at self.nodedir.

        If the node exists but is not running and `tahoe` is available, Sync
        starts it and owns that process until quit.
        """
        if not self.has_nodedir():
            raise SyncError(
                "could not join this friendnet. No Tahoe node at %s." % self.nodedir,
                "paste an introducer furl, or set LEASEGRID_TAHOE_NODEDIR; Retry.",
            )
        return self._bring_up()

    def join_invite(self, invite: str, offer_storage: bool = True) -> ConnectionStatus:
        """Join from a join URL, pb:// introducer furl, or short `tahoe invite` code.

        No node yet: create a Tahoe node for that friendnet (client+storage
        unless ``offer_storage`` is false), start it, wait for the introducer.
        Node already present: reuse it (start it if needed) and confirm it
        reaches an introducer. Unpaid join and offer are this same path.
        """
        from .invite import parse_invite

        parsed = parse_invite(invite)
        furl = parsed.token
        if self.has_nodedir():
            try:
                return self._bring_up()
            except SyncError as exc:
                if "Introducer is unreachable" not in exc.message:
                    raise
                raise SyncError(
                    "could not join this friendnet. A Tahoe node already exists at %s "
                    "but is not connected to an introducer."
                    % self.nodedir,
                    "if that node belongs to another grid, set LEASEGRID_TAHOE_NODEDIR "
                    "to a new path; otherwise check the introducer is up; Retry.",
                ) from exc
        self.create_node(furl, shares=parsed.shares, offer_storage=offer_storage)
        return self._bring_up()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


class MagicFolderCtl:
    def __init__(
        self,
        config_dir: Optional[Path] = None,
        nodedir: Optional[Path] = None,
        mf_bin: Optional[str] = None,
        listen_port: int = DEFAULT_MF_PORT,
    ) -> None:
        home = default_home()
        self.config_dir = Path(config_dir) if config_dir else home / "magic-folder"
        self.nodedir = Path(nodedir) if nodedir else default_nodedir()
        self.mf_bin = mf_bin or which_bin("magic-folder", "LEASEGRID_MAGIC_FOLDER_BIN")
        self.listen_port = int(os.environ.get("LEASEGRID_MF_PORT") or listen_port)
        self._proc: Optional[subprocess.Popen] = None
        self.log_path = default_home() / "logs" / "magic-folder.log"

    def require_bin(self) -> str:
        if not self.mf_bin:
            raise SyncError(
                "folder not added. The Magic Folder daemon is not installed.",
                "install magic-folder on PATH (see docs/ops/u1-dogfood.md) and Retry.",
            )
        return self.mf_bin

    def _run_cli(self, args: list[str], timeout: float = 60.0) -> subprocess.CompletedProcess:
        bin_ = self.require_bin()
        cmd = [bin_, "--config", str(self.config_dir), *args]
        try:
            return subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except FileNotFoundError as exc:
            raise SyncError(
                "folder not added. magic-folder executable is missing.",
                "install magic-folder on PATH; Retry.",
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise SyncError(
                "folder not added. Magic Folder command timed out.",
                "check the daemon log at %s; Retry." % self.log_path,
            ) from exc

    def ensure_init(self) -> None:
        self.require_bin()
        if (self.config_dir / "global.sqlite").is_file() or (
            self.config_dir / "api_token"
        ).is_file():
            return
        if not (self.nodedir / "tahoe.cfg").is_file():
            raise SyncError(
                "folder not added. Tahoe node directory is missing.",
                "join the friendnet first, then Add folder.",
            )
        # magic-folder init requires the config directory to not exist yet.
        if self.config_dir.is_dir():
            try:
                next(self.config_dir.iterdir())
            except StopIteration:
                self.config_dir.rmdir()
            else:
                raise SyncError(
                    "folder not added. Magic Folder config dir exists but is not initialized.",
                    "remove %s if it is leftover, then Retry." % self.config_dir,
                )
        self.config_dir.parent.mkdir(parents=True, exist_ok=True)
        listen = "tcp:%d:interface=127.0.0.1" % self.listen_port
        proc = subprocess.run(
            [
                self.require_bin(),
                "--config",
                str(self.config_dir),
                "init",
                "--listen-endpoint",
                listen,
                "--node-directory",
                str(self.nodedir),
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if proc.returncode != 0:
            # stderr can be a traceback or a furl. Do not paste the first line.
            raise SyncError(
                "folder not added. Could not initialize Magic Folder.",
                "fix the Magic Folder config path; Restart Sync.",
            )

    def is_running(self) -> bool:
        ep = self.config_dir / "api_client_endpoint"
        if not ep.is_file():
            return False
        try:
            url = endpoint_to_url(_read_text(ep))
        except SyncError:
            return False
        try:
            self._http_get("/v1/magic-folder", base=url, timeout=1.5)
            return True
        except SyncError:
            return False

    def ensure_running(self) -> None:
        self.ensure_init()
        if self.is_running():
            return
        if not _port_free(self.listen_port) and not self.is_running():
            raise SyncError(
                "folder not added. Port %d is busy and Magic Folder is not answering."
                % self.listen_port,
                "stop the other process or set LEASEGRID_MF_PORT; Restart Sync.",
            )
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            rotate_log(self.log_path)
            log_f = open(self.log_path, "ab")  # noqa: SIM115  daemon keeps this handle for its lifetime
        except OSError as exc:
            raise SyncError(
                "folder not added. This computer would not let Leasegrid Sync save its files.",
                "check that %s is writable, then Restart Sync." % self.log_path.parent,
            ) from exc
        try:
            self._proc = popen_hidden(
                [self.require_bin(), "--config", str(self.config_dir), "run"],
                log_f,
            )
        except OSError as exc:
            log_f.close()
            raise SyncError(
                "folder not added. Could not start Magic Folder.",
                "install magic-folder; Restart Sync.",
            ) from exc
        deadline = time.time() + 20
        while time.time() < deadline:
            if _leader_state(self._proc) != "running":
                proc = self._proc
                self._proc = None
                reap_child(proc, MF_STOP_WAIT)
                # magic-folder.log can hold a traceback and a furl. A process
                # exit is not an HTTP 500. Name the log. Do not paste it.
                raise SyncError(
                    "folder not added. Magic Folder stopped while starting; see %s."
                    % self.log_path,
                    "Restart Sync.",
                )
            if self.is_running():
                return
            time.sleep(0.2)
        raise SyncError(
            "folder not added. Magic Folder daemon did not become ready.",
            "see %s; Restart Sync." % self.log_path,
        )

    def stop(self, terminate_timeout: Optional[float] = None) -> None:
        proc = self._proc
        if proc is None:
            return
        timeout = MF_STOP_WAIT if terminate_timeout is None else terminate_timeout
        reap_child(proc, timeout)
        self._proc = None

    def _auth_headers(self) -> dict[str, str]:
        token_path = self.config_dir / "api_token"
        if not token_path.is_file():
            raise SyncError(
                "Magic Folder API token is missing.",
                "Restart Sync so the daemon can rewrite its config.",
            )
        token = token_path.read_bytes().decode("ascii", "replace").strip()
        return {"Authorization": "Bearer %s" % token}

    def _base_url(self) -> str:
        ep = self.config_dir / "api_client_endpoint"
        if not ep.is_file():
            raise SyncError(
                "Magic Folder daemon is not running.",
                "Restart Sync.",
            )
        return endpoint_to_url(_read_text(ep))

    def _http_get(self, path: str, base: Optional[str] = None, timeout: float = 10.0) -> Any:
        url = (base or self._base_url()) + path
        req = urllib.request.Request(url, headers=self._auth_headers())
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            raise self._http_failure(exc) from exc
        except urllib.error.URLError as exc:
            raise SyncError(
                "Magic Folder daemon is not reachable.",
                "Restart Sync.",
            ) from exc
        if not body:
            return {}
        try:
            return json.loads(body)
        except json.JSONDecodeError as exc:
            raise SyncError(
                "Magic Folder returned unreadable JSON.",
                "see %s; Restart Sync." % self.log_path,
            ) from exc

    def _http_failure(self, exc: urllib.error.HTTPError) -> SyncError:
        """Buyer copy for a Magic Folder HTTP error.

        The body and ``exc.reason`` can hold a traceback or a furl. Drain the
        body and do not copy it. Status 500 is known issue #30.
        """
        try:
            exc.read()
        except Exception:
            pass
        if is_issue_30_status(exc.code):
            return SyncError(
                "folder not added. This is known issue #30 (Magic Folder HTTP 500).",
                "Retry. If it keeps failing, file a bug per docs/TESTERS.md.",
                http_status=exc.code,
            )
        return SyncError(
            "Magic Folder API error (%s)." % exc.code,
            "Restart Sync. If it keeps failing, file a bug per docs/TESTERS.md.",
            http_status=exc.code,
        )

    def _http_post(self, path: str, timeout: float = 30.0, body: Optional[dict] = None) -> Any:
        url = self._base_url() + path
        headers = self._auth_headers()
        data = b""
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, method="POST", headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            raise self._http_failure(exc) from exc
        except urllib.error.URLError as exc:
            raise SyncError(
                "Magic Folder daemon is not reachable.",
                "Restart Sync.",
            ) from exc
        if not body:
            return {}
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return {"raw": body}

    def _refresh_add_copy(self, exc: SyncError) -> SyncError:
        """A folder list did not try to add a folder. Keep the Next line."""
        prefix = "folder not added. "
        if not exc.message.startswith(prefix):
            return exc
        return SyncError(
            "could not refresh folders. " + exc.message[len(prefix):],
            exc.next_hint,
            http_status=exc.http_status,
        )

    def _refresh_http_message(self, exc: SyncError) -> SyncError:
        """Listing folders is a refresh. HTTP 500 there is not an add.

        The status is ``exc.http_status``. The words "HTTP 500" in some other
        sentence are not issue #30.
        """
        if not is_issue_30_status(exc.http_status):
            return exc
        return self._refresh_add_copy(exc)

    def list_folders(self) -> list[FolderRow]:
        try:
            self.ensure_running()
        except SyncError as exc:
            mapped = self._refresh_add_copy(exc)
            if mapped is not exc:
                raise mapped from exc
            raise
        try:
            data = self._http_get("/v1/magic-folder")
        except SyncError as exc:
            mapped = self._refresh_http_message(exc)
            if mapped is not exc:
                raise mapped from exc
            raise
        if not isinstance(data, dict):
            return []
        rows = []
        for name, details in data.items():
            if not isinstance(details, dict):
                details = {}
            path = str(details.get("magic_path") or "")
            rows.append(
                FolderRow(
                    name=str(name),
                    path=path,
                    status="Idle",
                    detail="poll %ss" % details.get("poll_interval", "?"),
                )
            )
        for row in rows:
            row.status, row.detail = self.folder_status(row.name)
        return rows

    def folder_status(self, name: str) -> tuple[str, str]:
        try:
            files = self._http_get(
                "/v1/magic-folder/%s/file-status" % quote(name, safe="")
            )
            recent = self._http_get(
                "/v1/magic-folder/%s/recent-changes?number=5" % quote(name, safe="")
            )
        except SyncError as exc:
            return "FAIL", self._refresh_http_message(exc).message
        nfiles = len(files) if isinstance(files, list) else 0
        last = ""
        if isinstance(recent, list) and recent:
            item = recent[0]
            if isinstance(item, dict):
                last = str(item.get("relpath") or "")
                if item.get("conflicted"):
                    return "Conflict", last
        if nfiles == 0:
            return "Idle", "empty"
        if last:
            return "Up to date", "%d files · last %s" % (nfiles, last)
        return "Up to date", "%d files" % nfiles

    def add_folder(self, local_path: str, name: Optional[str] = None, author: Optional[str] = None) -> str:
        path = Path(local_path).expanduser()
        if not path.exists() or not path.is_dir():
            raise SyncError(
                "folder not added. Path is not a readable directory.",
                "pick an existing local folder; Retry.",
            )
        if not os.access(path, os.R_OK | os.W_OK):
            raise SyncError(
                "folder not added. Path is not readable/writable.",
                "fix permissions on %s; Retry." % path,
            )
        folder_name = name or path.name or "folder"
        folder_name = "".join(ch if ch.isalnum() or ch in "-_." else "-" for ch in folder_name)
        if not folder_name:
            raise SyncError(
                "folder not added. Folder name is empty.",
                "choose a different directory name; Retry.",
            )
        author = author or os.environ.get("USER") or os.environ.get("LOGNAME") or "leasegrid"
        self.ensure_running()
        existing = self._http_get("/v1/magic-folder")
        if isinstance(existing, dict) and folder_name in existing:
            return folder_name
        proc = self._run_cli(
            [
                "add",
                "--author",
                author,
                "--name",
                folder_name,
                "--poll-interval",
                "5",
                "--scan-interval",
                "5",
                str(path),
            ],
            timeout=120,
        )
        if proc.returncode != 0:
            # The first stderr line can be a traceback or a furl. Do not paste it.
            raise SyncError(
                "folder not added. Magic Folder could not add this folder.",
                "fix the path; Restart Sync; Retry Add folder.",
            )
        return folder_name

    def scan_local(self, name: str) -> None:
        path = "/v1/magic-folder/%s/scan-local" % quote(name, safe="")
        try:
            self._http_post(path, timeout=60)
            return
        except SyncError:
            pass
        try:
            self._http_get(path, timeout=60)
        except SyncError:
            pass

    def file_status(self, name: str) -> list[dict[str, Any]]:
        data = self._http_get("/v1/magic-folder/%s/file-status" % quote(name, safe=""))
        return data if isinstance(data, list) else []

    def recent_changes(self, name: str, number: int = 10) -> list[dict[str, Any]]:
        data = self._http_get(
            "/v1/magic-folder/%s/recent-changes?number=%d" % (quote(name, safe=""), number)
        )
        return data if isinstance(data, list) else []

    def participants(self, name: str) -> dict[str, Any]:
        data = self._http_get("/v1/magic-folder/%s/participants" % quote(name, safe=""))
        return data if isinstance(data, dict) else {}

    def add_participant(self, name: str, author_name: str, personal_dmd_readcap: str) -> None:
        """Register another device's personal DMD in this folder's collective."""
        self._http_post(
            "/v1/magic-folder/%s/participants" % quote(name, safe=""),
            timeout=60,
            body={"author": {"name": author_name}, "personal_dmd": personal_dmd_readcap},
        )

    def snapshots(self, name: Optional[str] = None) -> dict[str, Any]:
        data = self._http_get("/v1/snapshot")
        if not isinstance(data, dict):
            return {}
        if name:
            item = data.get(name) or {}
            return item if isinstance(item, dict) else {}
        return data


def _port_free(port: int, host: str = "127.0.0.1") -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.settimeout(0.3)
        return sock.connect_ex((host, port)) != 0
    finally:
        sock.close()


def write_probe_file(folder: Path, name: str = "u1-hello.txt") -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_text("leasegrid-u1 %s\n" % time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), encoding="utf-8")
    return path


def wait_for_file_status(
    ctl: MagicFolderCtl,
    folder_name: str,
    relpath: str,
    timeout: float = 90.0,
) -> dict[str, Any]:
    deadline = time.time() + timeout
    last: list[dict[str, Any]] = []
    while time.time() < deadline:
        try:
            ctl.scan_local(folder_name)
        except SyncError:
            pass
        try:
            last = ctl.file_status(folder_name)
        except SyncError:
            last = []
        for item in last:
            if isinstance(item, dict) and str(item.get("relpath") or "") == relpath:
                return item
        try:
            recent = ctl.recent_changes(folder_name)
        except SyncError:
            recent = []
        for item in recent:
            if isinstance(item, dict) and str(item.get("relpath") or "") == relpath:
                return item
        time.sleep(1.0)
    raise SyncError(
        "sync paused for %r. Local file %s did not appear in Magic Folder status."
        % (folder_name, relpath),
        "wait/retry; confirm Tahoe is connected; see %s." % ctl.log_path,
    )
