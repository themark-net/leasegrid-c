"""Native Leasegrid Sync window (PyQt). Gridsync folder-list mental model.

Leasegrid Sync does not use the Tahoe web UI as the buyer surface.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path
from typing import Optional

from . import APP_NAME, __version__
from .pgp_words import WORMHOLE_WORDS
from .backend import (
    ConnectionStatus,
    DiskSlices,
    FolderRow,
    MagicFolderCtl,
    SyncError,
    TahoeClient,
    apply_offer_percent,
    default_home,
    format_bytes,
    format_hosted_strip,
    WORMHOLE_CODE_RE,
    is_wormhole_code,
    join_filesystem_failure,
    rotate_log,
    read_disk_offer,
    read_hosted_shares,
    read_local_accepted,
    write_probe_file,
    wait_for_file_status,
)
from .credit import (
    DENOMINATION_NOTE,
    EXPAND_FACTOR,
    LAB_NOTE,
    REVIEW_HEAD,
    XMR_LATER,
    XMR_TIERS,
    ZERO_FOLDER_MSG,
    ZERO_FOLDER_NEXT,
    CreditCtl,
    CreditSnapshot,
    HostSettlement,
    credit_enforced,
    credit_gate,
    format_host_settlement,
    format_remaining,
    load_host_settlement,
    underpaid_copy,
)
from .recovery import (
    ACK_LOSS,
    ACK_STORE,
    EXPORT_STOP,
    EXPORT_WARN,
    NO_PASSPHRASE_NOTE,
    RECOVERY_INTRO,
    RECOVERY_SUFFIX,
    SCARY_LOSS,
    RecoveryCtl,
    RestoreResult,
)
from .servers import (
    SERVERS_HONESTY,
    ServerRow,
    add_storage_server,
    disconnect_copy,
    disconnect_server,
    roster,
    use_available_server,
)

THREAT_COPY = (
    "You are joining a friendnet you trust — not Dropbox-the-company and not Filecoin.\n"
    "1. Same invite, same process — joining and offering disk are one unpaid step. "
    "This device syncs folders and, by default, also stores shares for the friendnet.\n"
    "2. No storage proofs — dead nodes are dropped and shares moved, not slashed.\n"
    "3. Share over I2P — the join URL is a page you host; the address lives after # "
    "so the eepsite never sees it. Folder sync may still use LAN/WAN.\n"
    "4. Recovery — lose the recovery key and this device and access can be gone forever. "
    "Export one from the Recovery place after you join."
)
JOIN_THREAT_ACK = "I understand the four points above."
JOIN_ACK_MSG = "could not join this friendnet. The four points above are not acknowledged."
JOIN_ACK_NEXT = "check “I understand the four points above.”, then Join."


def _qt_api():
    from PyQt5 import QtCore, QtGui, QtWidgets

    return QtCore, QtGui, QtWidgets


def _style_primary(btn) -> None:
    """Filled weight for lead-journey CTAs. Not a theme rebrand."""
    btn.setMinimumHeight(36)
    btn.setStyleSheet(
        "QPushButton { background-color: #1f6feb; color: white; padding: 8px 16px;"
        " font-weight: 600; border: none; border-radius: 6px; }"
        "QPushButton:disabled { background-color: #b9cbe8; color: #f7f9fc; }"
    )


UI_LOG_NAME = "sync-ui.log"
UNEXPECTED_NEXT = "Retry. If it repeats, send logs/%s to your friendnet operator." % UI_LOG_NAME
ALREADY_RUNNING = "Leasegrid Sync is already running. Use the open window."
INVITE_CLOSE_QUESTION = "An invite is still open. Quit and cancel it?"
INVITE_KEEP_OPEN = "Keep open"
INVITE_QUIT_BUTTON = "Quit"
OPEN_LOGS_BUTTON = "Open logs folder"
COPY_BUG_BUTTON = "Copy bug-report details"
FOLDER_MISSING_BANNER = "That folder is not on this computer any more: %s"
FOLDER_FILE_BANNER = "That path is not a folder: %s"
HANDED_INVITE_DROPPED = (
    "Leasegrid Sync is already on a friendnet. This invite was not opened."
)
HANDED_INVITE_REPLACE = "Another invite arrived. Use it?"
_JOIN_HANDOFF_MAX = 4096
# A burst of a few hundred handoff sockets segfaulted the process. Extra
# connections are aborted, and an idle socket is dropped after this long.
_JOIN_PENDING_MAX = 8
_JOIN_READ_TIMEOUT_MS = 2000
_INSTANCE_LOCK = None
# Test drivers in tests/ set this before main(). An env var alone does nothing.
_TEST_HOOKS = False


def _test_env(name: str) -> str:
    """Read a LEASEGRID_TEST_* variable only when a test driver armed the hooks."""
    if not _TEST_HOOKS:
        return ""
    return os.environ.get(name) or ""


def display_path(path: object) -> str:
    """Home-relative form for a path a person sees or copies.

    ``~/…`` on POSIX and ``~\\…`` on Windows. Files on disk keep the real path.
    A path outside the account home is unchanged.
    """
    text = str(path)
    try:
        home = Path.home()
        rel = Path(text).expanduser().absolute().relative_to(home)
    except (OSError, ValueError, TypeError):
        return text
    tail = str(rel)
    if tail in ("", "."):
        return "~"
    if sys.platform == "win32":
        return "~\\" + tail.replace("/", "\\")
    return "~/" + tail.replace("\\", "/")


def instance_lock_path(home: Path) -> Path:
    return Path(home) / ".leasegrid-sync.lock"


def _lock_pid_readable(lock) -> bool:
    """True when getLockInfo can read a PID. Empty and garbage files cannot.

    PyQt5 returns (ok, pid, hostname, appname). The pid slot is uninitialized
    when ok is false, so the flag is the check.
    """
    info = lock.getLockInfo()
    if isinstance(info, tuple) and info and isinstance(info[0], bool):
        return bool(info[0])
    if isinstance(info, tuple) and info:
        return bool(info[0])
    return False


def _lock_writer_grace() -> None:
    """Give a starter that has created the lock time to write its PID."""
    time.sleep(0.1)


# A PID-less lock younger than this is a rival still writing, or a crash
# mid-write. Qt takes an older one inside tryLock. This code does not unlink
# the file: a rename or removeStaleLockFile deletes a rival's new lock.
_LOCK_PIDLESS_MAX_AGE_S = 2.0


def _pidless_lock_is_young(path: Path) -> bool:
    """True when a lock with no readable PID must not be taken.

    A missing stat or a timestamp in the future counts as young.
    """
    try:
        age = time.time() - path.stat().st_mtime
    except OSError:
        return True
    return age < _LOCK_PIDLESS_MAX_AGE_S


def acquire_instance_lock(home: Path) -> bool:
    """Lock this Sync home. A dead, empty, garbage, or other-host lock is taken over.

    Qt recovers a dead PID at once. A PID-less file (empty, garbage, or a
    crash mid-write) is taken only once it is older than 2s, inside tryLock,
    so two callers cannot both delete it. A younger PID-less file is left in
    place and this call refuses. Wait briefly first so a starter that is still
    writing its PID can finish. A readable PID is refused. The QLockFile object
    stays referenced until a clean quit, or the destructor would unlock it
    early. Returns False when another live process holds the lock.
    """
    global _INSTANCE_LOCK
    from PyQt5.QtCore import QLockFile

    path = instance_lock_path(home)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        return True
    lock = QLockFile(str(path))
    lock.setStaleLockTime(int(_LOCK_PIDLESS_MAX_AGE_S * 1000))
    if not lock.tryLock(0):
        if not _lock_pid_readable(lock):
            # The other starter may be between O_EXCL create and the PID write.
            _lock_writer_grace()
        if _lock_pid_readable(lock) or _pidless_lock_is_young(path):
            return False
        if not lock.tryLock(0):
            return False
    _INSTANCE_LOCK = lock
    return True


def release_instance_lock() -> None:
    """Unlock and remove the Sync-home lock. Safe when no lock is held."""
    global _INSTANCE_LOCK
    lock = _INSTANCE_LOCK
    _INSTANCE_LOCK = None
    if lock is None:
        return
    try:
        lock.unlock()
    except Exception:
        return


# Stay under the AF_UNIX cap (about 104 bytes on macOS, 108 on Linux).
_JOIN_PATH_MAX = 100


def _home_digest(home: Path) -> str:
    raw = str(Path(home).resolve()).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def join_server_name(home: Path) -> str:
    """Per-home local-server name. The invite is never part of the name."""
    return "leasegrid-sync-" + _home_digest(home)[:32]


def join_endpoint(home: Path) -> Optional[str]:
    """Absolute socket path, or the Windows pipe name, shared by both sides.

    POSIX prefers ``<Sync home>/run/<name>`` when that path is under 100 bytes,
    then ``$XDG_RUNTIME_DIR/leasegrid-sync/<name>``, then a 0700 directory
    ``leasegrid-sync-<uid>`` under ``$TMPDIR``. The Windows pipe name is the
    hash. There is no portable way to read the pipe owner from the client.
    """
    name = join_server_name(home)
    if sys.platform == "win32":
        return name
    primary = os.path.join(str(Path(home).resolve()), "run", name)
    if len(os.fsencode(primary)) < _JOIN_PATH_MAX:
        return primary
    xdg = os.environ.get("XDG_RUNTIME_DIR", "").strip()
    if xdg:
        secondary = os.path.join(xdg, "leasegrid-sync", name)
        if len(os.fsencode(secondary)) < _JOIN_PATH_MAX:
            return secondary
    return _tmpdir_join_endpoint(home, name)


def _tmpdir_join_endpoint(home: Path, name: str) -> Optional[str]:
    tmp = os.environ.get("TMPDIR", "").strip() or tempfile.gettempdir()
    directory = os.path.join(tmp, "leasegrid-sync-%d" % os.getuid())
    full = os.path.join(directory, name)
    if len(os.fsencode(full)) < _JOIN_PATH_MAX:
        return full
    digest = _home_digest(home)
    for length in range(64, 15, -1):
        candidate = os.path.join(directory, digest[:length])
        if len(os.fsencode(candidate)) < _JOIN_PATH_MAX:
            return candidate
    return None


def _lstat_path(path: str):
    """lstat, so a symlink is not treated as the directory it points at."""
    return os.lstat(path)


def _uid_is_ours(st: os.stat_result) -> bool:
    return st.st_uid == os.getuid()


def _posix_dir_is_private(st: os.stat_result) -> bool:
    """A real directory we own, with no group or other permissions."""
    if not stat.S_ISDIR(st.st_mode):
        return False
    if not _uid_is_ours(st):
        return False
    if st.st_mode & 0o077:
        return False
    return True


def _ensure_private_dir(path: str) -> bool:
    """Create a 0700 directory, or accept one that already passes the checks.

    An existing directory is never chmod'd. A symlink, the wrong owner, or a
    mode that grants group or other access is refused.
    """
    try:
        _lstat_path(path)
    except FileNotFoundError:
        try:
            os.mkdir(path, 0o700)
        except FileExistsError:
            pass
        except OSError:
            return False
        else:
            try:
                # mkdir honors umask. This directory was just created by us.
                os.chmod(path, 0o700)
            except OSError:
                return False
            try:
                return _posix_dir_is_private(_lstat_path(path))
            except OSError:
                return False
    except OSError:
        return False
    try:
        return _posix_dir_is_private(_lstat_path(path))
    except OSError:
        return False


def _clear_owned_socket(path: str) -> bool:
    """Unlink a stale socket we own. Anything else stays, and listening stops."""
    try:
        st = _lstat_path(path)
    except FileNotFoundError:
        return True
    except OSError:
        return False
    if not stat.S_ISSOCK(st.st_mode) or not _uid_is_ours(st):
        return False
    try:
        os.unlink(path)
    except OSError:
        return False
    return True


def _inspect_posix_endpoint(path: str) -> str:
    """'ok' to connect, 'absent' when nothing is there, 'refused' when it is unsafe."""
    parent = os.path.dirname(path)
    try:
        dir_st = _lstat_path(parent)
    except FileNotFoundError:
        return "absent"
    except OSError:
        return "refused"
    if not _posix_dir_is_private(dir_st):
        return "refused"
    try:
        st = _lstat_path(path)
    except FileNotFoundError:
        return "absent"
    except OSError:
        return "refused"
    if not stat.S_ISSOCK(st.st_mode):
        return "refused"
    if not _uid_is_ours(st):
        return "refused"
    return "ok"


def _log_handoff_note(home: Path, note: str) -> None:
    """One fixed line in the Sync log. The invite is not written."""
    path = Path(home) / "logs" / UI_LOG_NAME
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write("%s join handoff: %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), note))
    except OSError:
        pass


def _lock_is_held(home: Path) -> bool:
    """True when a live lock is held. A lock this call takes is released."""
    from PyQt5.QtCore import QLockFile

    path = instance_lock_path(home)
    if not path.parent.is_dir():
        return False
    lock = QLockFile(str(path))
    if lock.tryLock(0):
        lock.unlock()
        return False
    return True


def _send_invite_posix(home: Path, invite: str) -> bool:
    path = join_endpoint(home)
    if not path:
        return False
    state = _inspect_posix_endpoint(path)
    if state != "ok":
        if state == "refused":
            _log_handoff_note(home, "refused the socket before connecting")
        return False
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.settimeout(0.5)
        sock.connect(path)
        sock.sendall((invite + "\n").encode("utf-8"))
        return True
    except OSError:
        return False
    finally:
        try:
            sock.close()
        except OSError:
            pass


# A short-lived helper so a Windows --join does not construct QCoreApplication
# in the caller, and so the invite is not placed on the helper's command line.
_WIN_JOIN_SEND = """
import sys
from PyQt5.QtCore import QCoreApplication
from PyQt5.QtNetwork import QLocalSocket

app = QCoreApplication([])
name = sys.argv[1]
payload = sys.stdin.buffer.read(4096)
if not payload:
    raise SystemExit(2)
if not payload.endswith(b"\\n"):
    payload += b"\\n"
sock = QLocalSocket()
sock.connectToServer(name)
if not sock.waitForConnected(500):
    raise SystemExit(2)
sock.write(payload)
if not sock.waitForBytesWritten(500):
    raise SystemExit(2)
sock.disconnectFromServer()
raise SystemExit(0)
"""


def _send_invite_windows(name: str, invite: str) -> bool:
    """Send on the user-only pipe. The client cannot read the pipe owner."""
    try:
        proc = subprocess.run(
            [sys.executable, "-c", _WIN_JOIN_SEND, name],
            input=(invite + "\n").encode("utf-8"),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0


def hand_join_invite(invite: str) -> str:
    """Offer a second launch's invite to the running window.

    "sent" means the open window took it. "busy" means the home is locked and
    nothing is listening (an old build, or a stale socket). "free" means no
    instance is holding the home, so the caller should join as it does today.
    "rejected" means the text is empty or longer than the handoff cap, and the
    home is free: the caller must not join. "held" is that same text while
    another instance holds the home: say already-running, and do not send.
    """
    text = (invite or "").strip()
    home = default_home()
    if not text or len(text) > _JOIN_HANDOFF_MAX:
        # Never send this, and never start a join. A held home is already running.
        return "held" if _lock_is_held(home) else "rejected"
    # Lock first. A free home joins normally and never connects.
    if not _lock_is_held(home):
        return "free"
    if sys.platform == "win32":
        sent = _send_invite_windows(join_server_name(home), text)
    else:
        sent = _send_invite_posix(home, text)
    return "sent" if sent else "busy"


def _start_join_server(ui) -> None:
    """Listen for a second launch's invite. Failures are logged without the text."""
    try:
        from PyQt5.QtCore import QTimer
        from PyQt5.QtNetwork import QLocalServer
    except ImportError:
        return
    endpoint = join_endpoint(ui.home)
    if not endpoint:
        _log_handoff_note(ui.home, "could not choose a private socket path")
        return
    if sys.platform != "win32":
        parent = os.path.dirname(endpoint)
        if not _ensure_private_dir(parent):
            _log_handoff_note(ui.home, "refused the private socket directory")
            return
        if not _clear_owned_socket(endpoint):
            _log_handoff_note(ui.home, "refused a stale socket that is not ours")
            return
    server = QLocalServer(ui.app)
    # User-only pipe ACL on Windows, and owner-only socket mode on POSIX.
    server.setSocketOptions(QLocalServer.UserAccessOption)
    server.setMaxPendingConnections(_JOIN_PENDING_MAX)
    if sys.platform == "win32":
        QLocalServer.removeServer(endpoint)
    if not server.listen(endpoint):
        _log_handoff_note(ui.home, "could not listen for a second launch")
        return

    pending: list = []

    def drop(sock) -> None:
        """Abort one handoff socket and release it. Safe to call twice."""
        if getattr(sock, "_leasegrid_dropped", False):
            return
        sock._leasegrid_dropped = True
        try:
            pending.remove(sock)
        except ValueError:
            pass
        timer = getattr(sock, "_leasegrid_read_timer", None)
        if timer is not None:
            timer.stop()
        try:
            sock.abort()
        except Exception:
            pass
        sock.deleteLater()

    def on_new() -> None:
        while True:
            sock = server.nextPendingConnection()
            if sock is None:
                return
            if len(pending) >= _JOIN_PENDING_MAX:
                drop(sock)
                continue
            pending.append(sock)
            buf = bytearray()
            timer = QTimer(sock)
            timer.setSingleShot(True)
            sock._leasegrid_read_timer = timer  # type: ignore[attr-defined]

            def take(sock=sock, buf=buf) -> None:
                if getattr(sock, "_leasegrid_dropped", False):
                    return
                if sock.bytesAvailable():
                    chunk = bytes(sock.readAll())
                    if chunk:
                        buf.extend(chunk)
                over = len(buf) > _JOIN_HANDOFF_MAX
                complete = over or b"\n" in buf or sock.state() == sock.UnconnectedState
                if not complete:
                    return
                raw = bytes(buf).split(b"\n", 1)[0]
                del buf[:]
                text = "" if over else raw.decode("utf-8", "replace").strip()
                if text and len(text) <= _JOIN_HANDOFF_MAX:
                    ui.receive_handed_invite(text)
                drop(sock)

            timer.timeout.connect(lambda sock=sock: drop(sock))
            timer.start(_JOIN_READ_TIMEOUT_MS)
            sock.readyRead.connect(take)
            sock.disconnected.connect(take)
            if sock.bytesAvailable():
                take()

    server.newConnection.connect(on_new)
    ui._join_server = server
    ready = _test_env("LEASEGRID_TEST_JOIN_READY")
    if ready:
        try:
            Path(ready).write_text("ready\n", encoding="utf-8")
        except OSError:
            pass


def _close_join_server(ui) -> None:
    server = getattr(ui, "_join_server", None)
    ui._join_server = None
    if server is None:
        return
    try:
        from PyQt5.QtNetwork import QLocalSocket

        for sock in list(server.findChildren(QLocalSocket)):
            try:
                sock.abort()
            except Exception:
                pass
        server.close()
        server.deleteLater()
        app = getattr(ui, "app", None)
        if app is not None:
            app.processEvents()
    except Exception:
        try:
            server.close()
        except Exception:
            pass


def _show_already_running() -> None:
    _QtCore, _QtGui, QtWidgets = _qt_api()
    if QtWidgets.QApplication.instance() is None:
        QtWidgets.QApplication(sys.argv)
    QtWidgets.QMessageBox.information(None, APP_NAME, ALREADY_RUNNING)


def format_status_chip(status: ConnectionStatus) -> str:
    """Buyer-facing chip. Tahoe 'introducer up · N storage' stays in --status."""
    if status.state == "Connected":
        n = int(status.servers_connected or 0)
        if n <= 0:
            m = re.search(r"(\d+)\s+storage", status.detail or "")
            n = int(m.group(1)) if m else 0
        if n <= 0:
            return "Online — connected to the friendnet"
        if n == 1:
            return "Online — 1 computer storing files"
        return "Online — %d computers storing files" % n
    if status.state == "Connecting":
        return "Connecting…"
    if status.state == "FAIL":
        return "Can't reach the friendnet"
    if status.state == "Offline":
        return "Offline"
    return status.state


def about_line() -> str:
    """More → Settings. Buyer-visible version line."""
    return "%s (buyer) · version %s" % (APP_NAME, __version__)


# Whole tokens only. redact_furl keeps a head and a tail, and an 8-character
# fragment is still a leak. A candidate invite is exactly the shape
# WORMHOLE_CODE_RE accepts: 1–3 digits and two or more hyphen segments of
# letters or digits. The boundary is not a letter, digit, or hyphen. A dot
# is a boundary unless a digit sits in front of it, so
# "sentence.7-guitarist-revenge" matches and "v1.2.7-guitarist-revenge" does
# not. A segment counts when its letter prefix is a PGP word and any extra
# characters are trailing digits, and every segment must count (all, not any).
_CODE_BODY = WORMHOLE_CODE_RE.pattern[1:-1] if WORMHOLE_CODE_RE.pattern.startswith("^") else WORMHOLE_CODE_RE.pattern
_BUG_JOIN_RE = re.compile(
    r"leasegrid:\S+|https?://\S+#\S*|(?:(?<=\s)|^)#[^\s]*i(?:=|%3[Dd])[^\s]*",
    re.IGNORECASE,
)
_BUG_PB_RE = re.compile(r"pb://\S+", re.IGNORECASE)
_BUG_CODE_RE = re.compile(
    r"(?<![A-Za-z0-9-])(?<!\d\.)(?:" + _CODE_BODY + r")(?![A-Za-z0-9-])",
    re.IGNORECASE,
)
_SEGMENT_PREFIX_RE = re.compile(r"^([a-z]+)(\d*)$")


def _pgp_segment(segment: str) -> bool:
    match = _SEGMENT_PREFIX_RE.match(segment.lower())
    return bool(match) and match.group(1) in WORMHOLE_WORDS


def _redact_wormhole_code(match: re.Match) -> str:
    token = match.group(0)
    if not is_wormhole_code(token):
        return token
    parts = token.split("-")[1:]
    # all(), not any(): one real PGP word does not redact a mixed token.
    if parts and all(_pgp_segment(part) for part in parts):
        return "[redacted]"
    return token


def scrub_bug_report(text: str) -> str:
    """Remove invite material from a report that is about to be copied."""
    text = _BUG_JOIN_RE.sub("[redacted]", text)
    text = _BUG_PB_RE.sub("[redacted]", text)
    return _BUG_CODE_RE.sub(_redact_wormhole_code, text)


def log_exception(home: Path, where: str, exc: BaseException) -> Path:
    """Append a traceback to <home>/logs/sync-ui.log; never raises."""
    path = Path(home) / "logs" / UI_LOG_NAME
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        rotate_log(path)
        with path.open("a", encoding="utf-8") as f:
            f.write("%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), where))
            f.write("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))
            f.write("\n")
    except OSError:
        pass
    return path


def _make_disk_pie(parent):
    """Paint disk-local used / offered / kept. Hosted-for-others is not a slice."""
    _QtCore, QtGui, QtWidgets = _qt_api()

    class DiskPie(QtWidgets.QWidget):
        def __init__(self) -> None:
            super().__init__(parent)
            self.setObjectName("diskPie")
            self.setMinimumSize(148, 148)
            self.setMaximumSize(180, 180)
            self.setToolTip(
                "Used, kept free, and offered are this disk. Not shares hosted for others."
            )
            self._slices: Optional[DiskSlices] = None

        def set_slices(self, slices: Optional[DiskSlices]) -> None:
            self._slices = slices
            self.update()

        def paintEvent(self, _event) -> None:
            painter = QtGui.QPainter(self)
            painter.setRenderHint(QtGui.QPainter.Antialiasing)
            side = min(self.width(), self.height()) - 8
            rect = _QtCore.QRectF(
                (self.width() - side) / 2.0,
                (self.height() - side) / 2.0,
                side,
                side,
            )
            painter.setPen(_QtCore.Qt.NoPen)
            slices = self._slices
            parts: list[tuple[int, QtGui.QColor]] = []
            if slices is not None:
                parts = [
                    (slices.used, QtGui.QColor("#6b7280")),
                    (slices.offered, QtGui.QColor("#1f6feb")),
                    (slices.kept, QtGui.QColor("#d1d5db")),
                ]
            total = sum(v for v, _c in parts)
            if total <= 0:
                painter.setBrush(QtGui.QColor("#e5e7eb"))
                painter.drawEllipse(rect)
                painter.end()
                return
            start = 90 * 16
            for value, color in parts:
                if value <= 0:
                    continue
                span = -int(round(360 * 16 * value / total))
                if span == 0:
                    continue
                painter.setBrush(color)
                painter.drawPie(rect, start, span)
                start += span
            painter.end()

    return DiskPie()


def unexpected_error(exc: BaseException, what: str) -> SyncError:
    """Wrap a non-SyncError so it can be shown as a FAIL banner instead of aborting.

    The class name and ``str(exc)`` stay in ``logs/sync-ui.log`` via
    ``log_exception``. The banner and the REVIEW chip get ``what`` only.
    """
    lead = what.strip()
    if lead.endswith("."):
        lead = lead[:-1]
    return SyncError("%s. Unexpected error." % lead, UNEXPECTED_NEXT)


def install_excepthook(ui: "MainWindow") -> None:
    """Keep the window alive on an uncaught exception in a Qt slot.

    With the default sys.excepthook, PyQt5 turns any Python exception that
    reaches a slot boundary into qFatal(): the app aborts with no UI. This hook
    logs the traceback and shows one REVIEW box instead.
    """

    def hook(exc_type, exc, tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc, tb)
            return
        path = log_exception(ui.home, "uncaught", exc)
        sys.__excepthook__(exc_type, exc, tb)
        try:
            ui.show_unexpected(exc, path)
        except Exception:
            pass  # logging already happened; never let the hook itself abort

    sys.excepthook = hook


class TopUpDialog:
    """U5 (§11): choose a tier → quote → pay → poll → redeem. No faucet button."""

    def __init__(self, parent, credit: CreditCtl, qt) -> None:
        from PyQt5 import QtCore

        QtWidgets = qt
        self.QtWidgets = QtWidgets
        self.QtCore = QtCore
        self.credit = credit
        self.snapshot: Optional[CreditSnapshot] = None
        self.quote: Optional[dict] = None
        self._amount_xmr = ""
        self.page = "choose"
        self.dlg = QtWidgets.QDialog(parent)
        self.dlg.setWindowTitle("Top up")
        self.dlg.setObjectName("topUpDialog")
        self.dlg.setModal(True)
        v = QtWidgets.QVBoxLayout(self.dlg)
        self.stack = QtWidgets.QStackedWidget()
        self.choose_page = QtWidgets.QWidget()
        self.pay_page = QtWidgets.QWidget()
        self.stack.addWidget(self.choose_page)
        self.stack.addWidget(self.pay_page)
        v.addWidget(self.stack)

        cv = QtWidgets.QVBoxLayout(self.choose_page)
        title = QtWidgets.QLabel("Buy credit with XMR")
        font = title.font()
        font.setBold(True)
        title.setFont(font)
        cv.addWidget(title)
        intro = QtWidgets.QLabel("Prepaid share-capacity for this friendnet. Not a 1:1 disk meter.")
        intro.setWordWrap(True)
        cv.addWidget(intro)
        cv.addWidget(QtWidgets.QLabel("Amount"))
        self.amount_group = QtWidgets.QButtonGroup(self.dlg)
        self.radios = {}
        labels = {
            "small": "Small (≈ %d GiB·mo)" % XMR_TIERS["small"],
            "medium": "Medium (≈ %d GiB·mo)" % XMR_TIERS["medium"],
            "large": "Large (≈ %d GiB·mo)" % XMR_TIERS["large"],
        }
        for key, label in labels.items():
            radio = QtWidgets.QRadioButton(label)
            radio.setObjectName("tier_%s" % key)
            self.amount_group.addButton(radio)
            self.radios[key] = radio
            cv.addWidget(radio)
        self.radios["medium"].setChecked(True)
        xmr = QtWidgets.QLabel(XMR_LATER)
        xmr.setWordWrap(True)
        xmr.setObjectName("xmrLaterLabel")
        cv.addWidget(xmr)

        pv = QtWidgets.QVBoxLayout(self.pay_page)
        pay_title = QtWidgets.QLabel("Pay this quote")
        pf = pay_title.font()
        pf.setBold(True)
        pay_title.setFont(pf)
        pv.addWidget(pay_title)
        hint = QtWidgets.QLabel(
            "Send exactly this amount. After the timer we still credit for 24 h at this price."
        )
        hint.setWordWrap(True)
        hint.setObjectName("payHint")
        pv.addWidget(hint)
        self.pay_amount = QtWidgets.QLabel("")
        self.pay_amount.setObjectName("payAmount")
        self.pay_amount.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        pv.addWidget(self.pay_amount)
        self.pay_address = QtWidgets.QLabel("")
        self.pay_address.setObjectName("payAddress")
        self.pay_address.setWordWrap(True)
        self.pay_address.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        pv.addWidget(self.pay_address)
        crow = QtWidgets.QHBoxLayout()
        self.copy_address_btn = QtWidgets.QPushButton("Copy address")
        self.copy_address_btn.setObjectName("copyAddressButton")
        self.copy_address_btn.clicked.connect(self.on_copy_address)
        self.copy_amount_btn = QtWidgets.QPushButton("Copy amount")
        self.copy_amount_btn.setObjectName("copyAmountButton")
        self.copy_amount_btn.clicked.connect(self.on_copy_amount)
        crow.addWidget(self.copy_address_btn)
        crow.addWidget(self.copy_amount_btn)
        crow.addStretch(1)
        pv.addLayout(crow)

        self.status = QtWidgets.QLabel("")
        self.status.setObjectName("topUpStatus")
        self.status.setWordWrap(True)
        v.addWidget(self.status)
        row = QtWidgets.QHBoxLayout()
        self.continue_btn = QtWidgets.QPushButton("Continue")
        self.continue_btn.setObjectName("topUpContinue")
        self.continue_btn.clicked.connect(self.on_continue)
        self.cancel_btn = QtWidgets.QPushButton("Cancel")
        self.cancel_btn.setObjectName("topUpCancel")
        self.cancel_btn.clicked.connect(self.dlg.reject)
        row.addWidget(self.continue_btn)
        row.addWidget(self.cancel_btn)
        row.addStretch(1)
        v.addLayout(row)
        self._timer = None
        self.dlg.finished.connect(self._stop_poll)

    def _selected_tier(self) -> str:
        for key, radio in self.radios.items():
            if radio.isChecked():
                return key
        return "medium"

    def _tokens(self) -> int:
        return int(XMR_TIERS.get(self._selected_tier(), 50))

    def on_continue(self) -> None:
        self.status.setStyleSheet("")
        self.status.setText("Asking the issuer for a quote…")
        self.continue_btn.setEnabled(False)
        self.QtWidgets.QApplication.processEvents()
        try:
            self.quote = self.credit.quote_topup(self._tokens())
        except SyncError as exc:
            self.status.setStyleSheet("color: #8b1a1a;")
            self.status.setText(exc.banner())
            self.continue_btn.setEnabled(True)
            self.continue_btn.setText("Retry")
            return
        self._show_pay()

    def _show_pay(self) -> None:
        q = self.quote or {}
        self.page = "pay"
        self._amount_xmr = str(q.get("amount_xmr") or "")
        self.pay_amount.setText("%s XMR" % self._amount_xmr)
        self.pay_address.setText(str(q.get("address") or ""))
        self.stack.setCurrentWidget(self.pay_page)
        self.continue_btn.hide()
        self.cancel_btn.setText("Close")
        self.status.setText("Waiting for payment…")
        self._start_poll()
        self._submit_lab_payment()

    def _start_poll(self) -> None:
        if self._timer is None:
            self._timer = self.QtCore.QTimer(self.dlg)
            self._timer.setInterval(2000)
            self._timer.timeout.connect(self.on_poll)
        self._timer.start()

    def _stop_poll(self, _result: int = 0) -> None:
        if self._timer is not None:
            self._timer.stop()

    def on_poll(self) -> None:
        try:
            self._on_poll()
        except Exception:
            try:
                self.status.setStyleSheet("color: #8b1a1a;")
                self.status.setText(
                    "REVIEW — Could not check this quote. Payments already sent are safe; retry later."
                )
            except Exception:
                pass

    def _on_poll(self) -> None:
        if not self.quote:
            return
        try:
            r = self.credit.poll_topup(self.quote["vid"])
        except SyncError as exc:
            self.status.setStyleSheet("color: #8b1a1a;")
            self.status.setText(exc.banner())
            return
        state = str(r.get("state") or "")
        v = r.get("voucher") or {}
        if state == "issued":
            self._stop_poll()
            try:
                self.snapshot = self.credit.load_balance()
            except SyncError:
                self.snapshot = None
            n = int(r.get("tokens_added") or r.get("tokens") or 0)
            bal = self.snapshot.balance.tokens if self.snapshot else n
            self.page = "done"
            self.status.setStyleSheet("")
            self.status.setText("+%d credits. Balance: %d" % (n, bal))
            self.cancel_btn.setText("Done")
            self.cancel_btn.clicked.disconnect()
            self.cancel_btn.clicked.connect(self.dlg.accept)
            return
        if state == "underpaid":
            quoted = (self.quote or {}).get("amount_piconero") or (self.quote or {}).get("amount_due")
            self.status.setText(underpaid_copy(v, quoted))
            return
        if state in ("seen", "confirming"):
            need = v.get("confirmations_required") or (self.quote or {}).get("confirmations_required") or 2
            have = v.get("confirmations") or 0
            self.status.setText("Payment seen. Confirming %s of %s…" % (have, need))
            return
        if state == "quoted":
            self.status.setText("Waiting for payment…")

    def on_copy_address(self) -> None:
        self.QtWidgets.QApplication.clipboard().setText(self.pay_address.text())

    def on_copy_amount(self) -> None:
        self.QtWidgets.QApplication.clipboard().setText(self._amount_xmr)

    def _submit_lab_payment(self) -> None:
        """FakeChain pays the quote here. Stagenet pays when a wallet-rpc is set.

        With no payer configured, the quote stays on screen for an external
        stagenet wallet. Mainnet is refused inside pay_quote.
        """
        pay = getattr(self.credit, "pay_quote", None)
        if pay is None or not self.quote:
            return
        try:
            result = pay(self.quote)
        except SyncError as exc:
            self.status.setStyleSheet("color: #8b1a1a;")
            self.status.setText(exc.banner())
            return
        except Exception:
            self.status.setStyleSheet("color: #8b1a1a;")
            self.status.setText(
                "REVIEW — Could not submit this payment. Payments already sent are safe; retry later."
            )
            return
        if isinstance(result, dict) and result.get("skipped"):
            return
        self.status.setStyleSheet("")
        self.status.setText("Payment submitted. Collecting your credits…")


class ExportRecoveryDialog:
    """Wireframe 4b: scary gate, two ACKs, optional passphrase, path, write."""

    def __init__(self, parent, recovery: RecoveryCtl, qt, default_dir: Optional[Path] = None) -> None:
        QtWidgets = qt
        self.QtWidgets = QtWidgets
        self.recovery = recovery
        self.written: Optional[Path] = None
        self.dlg = QtWidgets.QDialog(parent)
        self.dlg.setWindowTitle("Export recovery key")
        self.dlg.setObjectName("exportRecoveryDialog")
        self.dlg.setModal(True)
        v = QtWidgets.QVBoxLayout(self.dlg)
        stop = QtWidgets.QLabel(EXPORT_STOP)
        font = stop.font()
        font.setBold(True)
        stop.setFont(font)
        v.addWidget(stop)
        warn = QtWidgets.QLabel(EXPORT_WARN)
        warn.setWordWrap(True)
        warn.setObjectName("exportWarn")
        v.addWidget(warn)
        self.ack_loss = QtWidgets.QCheckBox(ACK_LOSS)
        self.ack_loss.setObjectName("ackLoss")
        self.ack_store = QtWidgets.QCheckBox(ACK_STORE)
        self.ack_store.setObjectName("ackStore")
        v.addWidget(self.ack_loss)
        v.addWidget(self.ack_store)
        v.addWidget(QtWidgets.QLabel("Passphrase (recommended)"))
        row = QtWidgets.QHBoxLayout()
        self.pass_edit = QtWidgets.QLineEdit()
        self.pass_edit.setEchoMode(QtWidgets.QLineEdit.Password)
        self.pass_edit.setObjectName("passEdit")
        self.confirm_edit = QtWidgets.QLineEdit()
        self.confirm_edit.setEchoMode(QtWidgets.QLineEdit.Password)
        self.confirm_edit.setPlaceholderText("confirm")
        self.confirm_edit.setObjectName("confirmEdit")
        row.addWidget(self.pass_edit)
        row.addWidget(self.confirm_edit)
        v.addLayout(row)
        self.pass_note = QtWidgets.QLabel(NO_PASSPHRASE_NOTE)
        self.pass_note.setWordWrap(True)
        self.pass_note.setObjectName("passNote")
        v.addWidget(self.pass_note)
        v.addWidget(QtWidgets.QLabel("Save to"))
        prow = QtWidgets.QHBoxLayout()
        self.path_edit = QtWidgets.QLineEdit()
        self.path_edit.setObjectName("pathEdit")
        base = Path(default_dir) if default_dir else Path.home()
        self.path_edit.setText(str(base / ("leasegrid-recovery" + RECOVERY_SUFFIX)))
        browse = QtWidgets.QPushButton("Browse…")
        browse.setObjectName("browseButton")
        browse.clicked.connect(self.on_browse)
        prow.addWidget(self.path_edit)
        prow.addWidget(browse)
        v.addLayout(prow)
        self.status = QtWidgets.QLabel("")
        self.status.setObjectName("exportStatus")
        self.status.setWordWrap(True)
        v.addWidget(self.status)
        brow = QtWidgets.QHBoxLayout()
        self.write_btn = QtWidgets.QPushButton("Write recovery key")
        self.write_btn.setObjectName("writeButton")
        self.write_btn.setEnabled(False)
        self.write_btn.clicked.connect(self.on_write)
        cancel = QtWidgets.QPushButton("Cancel")
        cancel.setObjectName("exportCancel")
        cancel.clicked.connect(self.dlg.reject)
        brow.addWidget(self.write_btn)
        brow.addWidget(cancel)
        brow.addStretch(1)
        v.addLayout(brow)
        for w in (self.ack_loss, self.ack_store):
            w.toggled.connect(self._update_gate)
        for w in (self.pass_edit, self.confirm_edit, self.path_edit):
            w.textChanged.connect(self._update_gate)
        self._update_gate()

    def _update_gate(self, *_args) -> None:
        ok = self.ack_loss.isChecked() and self.ack_store.isChecked()
        ok = ok and bool(self.path_edit.text().strip())
        ok = ok and self.pass_edit.text() == self.confirm_edit.text()
        self.write_btn.setEnabled(ok)
        self.pass_note.setVisible(not self.pass_edit.text())

    def on_browse(self) -> None:
        path, _ = self.QtWidgets.QFileDialog.getSaveFileName(
            self.dlg,
            "Save recovery key",
            self.path_edit.text(),
            "Leasegrid recovery key (*%s)" % RECOVERY_SUFFIX,
        )
        if path:
            if not path.endswith(RECOVERY_SUFFIX):
                path += RECOVERY_SUFFIX
            self.path_edit.setText(path)

    def on_write(self) -> None:
        self.status.setStyleSheet("")
        self.status.setText("Writing recovery key…")
        self.write_btn.setEnabled(False)
        self.QtWidgets.QApplication.processEvents()
        path = Path(self.path_edit.text().strip()).expanduser()
        try:
            self.recovery.export(path, self.pass_edit.text())
        except SyncError as exc:
            self.status.setStyleSheet("color: #8b1a1a;")
            self.status.setText(exc.banner())
            self.write_btn.setText("Retry export")
            self.write_btn.setEnabled(True)
            return
        self.written = path
        self.dlg.accept()


class ImportRecoveryDialog:
    """Wireframe 4e: pick file, passphrase, restore with progress + in-window FAIL."""

    def __init__(self, parent, recovery: RecoveryCtl, qt, path: Optional[Path] = None) -> None:
        QtWidgets = qt
        self.QtWidgets = QtWidgets
        self.recovery = recovery
        self.result: Optional[RestoreResult] = None
        self.dlg = QtWidgets.QDialog(parent)
        self.dlg.setWindowTitle("Import recovery key")
        self.dlg.setObjectName("importRecoveryDialog")
        self.dlg.setModal(True)
        v = QtWidgets.QVBoxLayout(self.dlg)
        intro = QtWidgets.QLabel(
            "Restores your folders on this device. This device joins each folder as a new "
            "participant; files download from the friendnet into ~/Leasegrid/<folder>."
        )
        intro.setWordWrap(True)
        v.addWidget(intro)
        v.addWidget(QtWidgets.QLabel("Recovery key file"))
        prow = QtWidgets.QHBoxLayout()
        self.path_edit = QtWidgets.QLineEdit(str(path) if path else "")
        self.path_edit.setObjectName("importPathEdit")
        browse = QtWidgets.QPushButton("Browse…")
        browse.setObjectName("importBrowseButton")
        browse.clicked.connect(self.on_browse)
        prow.addWidget(self.path_edit)
        prow.addWidget(browse)
        v.addLayout(prow)
        v.addWidget(QtWidgets.QLabel("Passphrase (leave empty if none was set)"))
        self.pass_edit = QtWidgets.QLineEdit()
        self.pass_edit.setEchoMode(QtWidgets.QLineEdit.Password)
        self.pass_edit.setObjectName("importPassEdit")
        v.addWidget(self.pass_edit)
        self.status = QtWidgets.QLabel("")
        self.status.setObjectName("importStatus")
        self.status.setWordWrap(True)
        v.addWidget(self.status)
        brow = QtWidgets.QHBoxLayout()
        self.import_btn = QtWidgets.QPushButton("Import recovery key")
        self.import_btn.setObjectName("importButton")
        self.import_btn.clicked.connect(self.on_import)
        cancel = QtWidgets.QPushButton("Cancel")
        cancel.setObjectName("importCancel")
        cancel.clicked.connect(self.dlg.reject)
        brow.addWidget(self.import_btn)
        brow.addWidget(cancel)
        brow.addStretch(1)
        v.addLayout(brow)
        # Width before any banner. A later sizeHint follows the unwrapped line.
        self._open_width = self.dlg.sizeHint().width()

    def on_browse(self) -> None:
        path, _ = self.QtWidgets.QFileDialog.getOpenFileName(
            self.dlg,
            "Open recovery key",
            str(Path.home()),
            "Leasegrid recovery key (*%s);;All files (*)" % RECOVERY_SUFFIX,
        )
        if path:
            self.path_edit.setText(path)

    def _progress(self, text: str) -> None:
        self.status.setStyleSheet("")
        self.status.setText(text)
        self.QtWidgets.QApplication.processEvents()

    def _fit_status(self) -> None:
        """Grow so a wrapped status banner stays inside the dialog.

        The dialog opens at the empty label's size hint. Offscreen Qt does
        not apply a later hint (``propagateSizeHints`` is unsupported).
        ``adjustSize`` follows the label's unwrapped size hint, which is
        shorter than ``heightForWidth`` at the width on screen.
        """
        dialog = self.dlg
        label = self.status
        layout = dialog.layout()
        layout.activate()
        if dialog.isVisible() and dialog.width() > 100:
            width = dialog.width()
        else:
            width = max(self._open_width, dialog.minimumWidth())
        for _ in range(2):
            layout.activate()
            label_width = label.width()
            if label_width < 40:
                margins = layout.contentsMargins()
                label_width = max(40, width - margins.left() - margins.right())
            needed = label.heightForWidth(label_width)
            if needed < 1:
                needed = label.sizeHint().height()
            label.setMinimumHeight(needed)
            height = max(
                layout.totalHeightForWidth(width),
                layout.minimumSize().height(),
                layout.sizeHint().height(),
            )
            dialog.setMinimumHeight(height)
            if (
                dialog.width() == width
                and dialog.height() >= height
                and label.height() >= needed
            ):
                break
            dialog.resize(width, height)
            self.QtWidgets.QApplication.processEvents()
        layout.activate()

    def on_import(self) -> None:
        path = Path(self.path_edit.text().strip()).expanduser()
        if not path.is_file():
            self.status.setStyleSheet("color: #8b1a1a;")
            self.status.setText(
                SyncError(
                    "could not import this recovery key. File not found.",
                    "pick the file from your backup; Retry.",
                ).banner()
            )
            self._fit_status()
            return
        self.import_btn.setEnabled(False)
        self._progress("Importing recovery key…")
        try:
            self.result = self.recovery.restore(path, self.pass_edit.text(), progress=self._progress)
        except SyncError as exc:
            self.status.setStyleSheet("color: #8b1a1a;")
            self.status.setText(exc.banner())
            self.import_btn.setText("Retry import")
            self.import_btn.setEnabled(True)
            self._fit_status()
            return
        self.dlg.accept()


def fit_share_card(dlg) -> None:
    """Open the card at its size hint.

    Offscreen Qt does not apply size hints (``propagateSizeHints`` is
    unsupported), so a dialog stays at its minimum height. That compresses
    the QR slot and the next row paints over the bottom-left finder.
    """
    dlg.setMinimumSize(0, 0)
    hint = dlg.sizeHint()
    dlg.setMinimumSize(hint)
    dlg.resize(hint)


class InviteSharePanel:
    """#32 share card: short code + QR + Copy. Join link stays collapsed."""

    def __init__(self, layout, window: "MainWindow", qt, names: dict) -> None:
        QtWidgets = qt
        self.window = window
        self.QtWidgets = QtWidgets
        intro = QtWidgets.QLabel(
            "Invite someone to join this friendnet "
            "(they can Offer disk so you get more storage)."
        )
        intro.setWordWrap(True)
        intro.setObjectName(names.get("intro", "inviteShareIntro"))
        layout.addWidget(intro)
        self.qr = QtWidgets.QLabel("")
        self.qr.setObjectName(names["qr"])
        self.qr.setMinimumSize(160, 160)
        self.qr.setAlignment(window.QtCore.Qt.AlignLeft | window.QtCore.Qt.AlignVCenter)
        layout.addWidget(self.qr)
        layout.addWidget(QtWidgets.QLabel("Short code"))
        self.code_edit = QtWidgets.QLineEdit()
        self.code_edit.setObjectName(names["code"])
        self.code_edit.setReadOnly(True)
        self.code_edit.setPlaceholderText("7-word-word")
        font = self.code_edit.font()
        font.setPointSize(14)
        font.setBold(True)
        self.code_edit.setFont(font)
        layout.addWidget(self.code_edit)
        self.copy_btn = QtWidgets.QPushButton("Copy code")
        self.copy_btn.setObjectName(names["copy"])
        self.copy_btn.setAutoDefault(False)
        _style_primary(self.copy_btn)
        self.copy_btn.clicked.connect(self.on_copy)
        layout.addWidget(self.copy_btn)
        self.advanced = QtWidgets.QCheckBox("Show full join link (advanced)")
        self.advanced.setObjectName(names["advanced"])
        self.advanced.toggled.connect(self._on_advanced)
        layout.addWidget(self.advanced)
        self.join_link = QtWidgets.QLineEdit()
        self.join_link.setObjectName(names["link"])
        self.join_link.setReadOnly(True)
        # A long join URL must scroll inside the card, not stretch it.
        self.join_link.setSizePolicy(
            QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Fixed
        )
        self.join_link.hide()
        layout.addWidget(self.join_link)
        self.status = QtWidgets.QLabel("")
        self.status.setObjectName(names["status"])
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

    def _on_advanced(self, checked: bool) -> None:
        self.join_link.setVisible(bool(checked))

    def on_copy(self) -> None:
        self.present(copy=True)

    def present(self, copy: bool = False) -> None:
        self.status.setStyleSheet("")
        self.status.setText("Creating invite code…")
        self.QtWidgets.QApplication.processEvents()
        try:
            code, url = self.window.ensure_invite_code()
        except SyncError as exc:
            self.status.setStyleSheet("color: #8b1a1a;")
            self.status.setText(exc.banner())
            self.code_edit.clear()
            self.qr.clear()
            self.qr.setMinimumSize(160, 160)
            self.qr.setMaximumSize(16777215, 16777215)
            self.qr.setText("")
            return
        except Exception as exc:
            self.window._log_exception("invite-share", exc)
            self.status.setStyleSheet("color: #8b1a1a;")
            self.status.setText(unexpected_error(exc, "could not share this invite.").banner())
            return
        self.code_edit.setText(code)
        self.code_edit.setCursorPosition(0)
        self.join_link.setText(url)
        self.join_link.setCursorPosition(0)
        self.join_link.setToolTip(url)
        self._paint_qr(code)
        if copy:
            self.QtWidgets.QApplication.clipboard().setText(code)
            self.status.setStyleSheet("")
            self.status.setText(
                "Invite code copied. Keep Sync open until they join. "
                "They appear under Storage servers when ready."
            )
        else:
            self.status.setStyleSheet("")
            self.status.setText(
                "Wait for them to Join (+ Offer if storing for you). "
                "They appear under Storage servers when ready."
            )

    def show_existing(self, code: str, url: str) -> None:
        """Paint a code this window already created. Does not start Tahoe."""
        if code:
            self.code_edit.setText(code)
            self.code_edit.setCursorPosition(0)
            self._paint_qr(code)
        if url:
            self.join_link.setText(url)
            self.join_link.setCursorPosition(0)
            self.join_link.setToolTip(url)

    def _paint_qr(self, payload: str) -> None:
        try:
            from .invite import qr_png

            pix = self.window.QtGui.QPixmap()
            if not pix.loadFromData(qr_png(payload)) or pix.isNull():
                raise RuntimeError("empty qr")
            self.qr.setText("")
            # The symbol is 174px for a short code (version 2, scale 6). A
            # 160px slot lets the Short code row paint over the bottom finder.
            self.qr.setFixedSize(pix.size())
            self.qr.setPixmap(pix)
        except Exception:
            self.qr.setMinimumSize(160, 160)
            self.qr.setMaximumSize(16777215, 16777215)
            self.qr.setText("QR unavailable")


class InviteShareDialog:
    """Folders / More entry for the same short-code share card."""

    def __init__(self, parent, window: "MainWindow", qt) -> None:
        QtWidgets = qt
        self.dlg = QtWidgets.QDialog(parent)
        self.dlg.setWindowTitle("Share invite")
        self.dlg.setObjectName("inviteShareDialog")
        self.dlg.setModal(True)
        v = QtWidgets.QVBoxLayout(self.dlg)
        v.setContentsMargins(24, 20, 24, 20)
        self.panel = InviteSharePanel(
            v,
            window,
            qt,
            {
                "intro": "inviteDialogIntro",
                "qr": "inviteDialogQr",
                "code": "inviteDialogCode",
                "copy": "inviteDialogCopy",
                "advanced": "inviteDialogAdvanced",
                "link": "inviteDialogLink",
                "status": "inviteDialogStatus",
            },
        )
        brow = QtWidgets.QHBoxLayout()
        brow.addStretch(1)
        done = QtWidgets.QPushButton("Done")
        done.setObjectName("inviteDialogDone")
        done.setAutoDefault(False)
        done.clicked.connect(self.dlg.accept)
        brow.addWidget(done)
        v.addLayout(brow)
        self.panel.advanced.toggled.connect(lambda _checked: fit_share_card(self.dlg))
        self.panel.present()
        fit_share_card(self.dlg)


class AddStorageServerDialog:
    """Add storage: invite someone to Offer disk, or paste a storage furl."""

    def __init__(self, parent, window: "MainWindow", qt) -> None:
        QtWidgets = qt
        self.QtWidgets = QtWidgets
        self.window = window
        self.dlg = QtWidgets.QDialog(parent)
        self.dlg.setWindowTitle("Add storage server")
        self.dlg.setObjectName("addStorageDialog")
        self.dlg.setModal(True)
        v = QtWidgets.QVBoxLayout(self.dlg)
        prompt = QtWidgets.QLabel("How do you want to add storage?")
        prompt.setObjectName("addStoragePrompt")
        v.addWidget(prompt)

        self.invite_radio = QtWidgets.QRadioButton("Invite someone to Offer disk")
        self.invite_radio.setObjectName("addPathInvite")
        self.invite_radio.setChecked(True)
        v.addWidget(self.invite_radio)
        invite_hint = QtWidgets.QLabel(
            "Share a short code or QR so their computer can store shares."
        )
        invite_hint.setWordWrap(True)
        invite_hint.setObjectName("addInviteHint")
        v.addWidget(invite_hint)
        self.invite_panel = InviteSharePanel(
            v,
            window,
            qt,
            {
                "intro": "addInviteIntro",
                "qr": "addInviteQr",
                "code": "addInviteCode",
                "copy": "copyInviteButton",
                "advanced": "addShowJoinLink",
                "link": "addInviteJoinLink",
                "status": "addInviteStatus",
            },
        )
        self.copy_invite_btn = self.invite_panel.copy_btn
        self.invite_status = self.invite_panel.status
        self.invite_panel.present()

        self.paste_radio = QtWidgets.QRadioButton("Paste a server link")
        self.paste_radio.setObjectName("addPathPaste")
        v.addWidget(self.paste_radio)
        self.paste_hint = QtWidgets.QLabel(
            "Paste a storage server link (pb://…) from a host you trust."
        )
        self.paste_hint.setWordWrap(True)
        self.paste_hint.setObjectName("addPasteHint")
        v.addWidget(self.paste_hint)
        v.addWidget(QtWidgets.QLabel("Server link"))
        self.furl_edit = QtWidgets.QLineEdit()
        self.furl_edit.setObjectName("storageFurlEdit")
        self.furl_edit.setPlaceholderText("pb://…")
        v.addWidget(self.furl_edit)
        v.addWidget(QtWidgets.QLabel("Nickname (optional)"))
        self.nick_edit = QtWidgets.QLineEdit()
        self.nick_edit.setObjectName("storageNickEdit")
        self.nick_edit.setPlaceholderText("home-nas")
        v.addWidget(self.nick_edit)
        self.error = QtWidgets.QLabel("")
        self.error.setObjectName("addStorageError")
        self.error.setWordWrap(True)
        self.error.setStyleSheet("color: #8b1a1a;")
        v.addWidget(self.error)
        brow = QtWidgets.QHBoxLayout()
        cancel = QtWidgets.QPushButton("Cancel")
        cancel.setObjectName("addStorageCancel")
        cancel.setAutoDefault(False)
        cancel.clicked.connect(self.dlg.reject)
        self.add_btn = QtWidgets.QPushButton("Add server")
        self.add_btn.setObjectName("addServerButton")
        self.add_btn.setAutoDefault(False)
        self.add_btn.clicked.connect(self.on_add)
        brow.addWidget(cancel)
        brow.addStretch(1)
        brow.addWidget(self.add_btn)
        v.addLayout(brow)
        self.invite_panel.advanced.toggled.connect(lambda _checked: fit_share_card(self.dlg))
        fit_share_card(self.dlg)

    def on_copy_invite(self) -> None:
        self.invite_panel.on_copy()

    def on_add(self) -> None:
        self.error.setText("")
        furl = self.furl_edit.text()
        self.add_btn.setEnabled(False)
        self.QtWidgets.QApplication.processEvents()
        try:
            add_storage_server(
                self.window.home,
                self.window.tahoe.nodedir,
                furl,
                self.nick_edit.text(),
            )
            self.window.tahoe.reload_static_servers()
        except SyncError as exc:
            self.error.setText(exc.banner())
            self.add_btn.setText("Retry")
            self.add_btn.setEnabled(True)
            return
        except Exception as exc:
            self.window._log_exception("add-storage", exc)
            self.error.setText(unexpected_error(exc, "could not add this storage server.").banner())
            self.add_btn.setText("Retry")
            self.add_btn.setEnabled(True)
            return
        self.dlg.accept()


class DisconnectServerDialog:
    """Confirm Disconnect. Copy is local to this Sync home."""

    def __init__(self, parent, qt, name: str) -> None:
        QtWidgets = qt
        self.dlg = QtWidgets.QDialog(parent)
        self.dlg.setWindowTitle("Disconnect storage server?")
        self.dlg.setObjectName("disconnectServerDialog")
        self.dlg.setModal(True)
        v = QtWidgets.QVBoxLayout(self.dlg)
        self.copy = QtWidgets.QLabel(disconnect_copy(name))
        self.copy.setObjectName("disconnectCopy")
        self.copy.setWordWrap(True)
        v.addWidget(self.copy)
        brow = QtWidgets.QHBoxLayout()
        cancel = QtWidgets.QPushButton("Cancel")
        cancel.setObjectName("disconnectCancel")
        cancel.setAutoDefault(False)
        cancel.clicked.connect(self.dlg.reject)
        ok = QtWidgets.QPushButton("Disconnect")
        ok.setObjectName("confirmDisconnect")
        ok.setAutoDefault(False)
        ok.clicked.connect(self.dlg.accept)
        brow.addWidget(cancel)
        brow.addStretch(1)
        brow.addWidget(ok)
        v.addLayout(brow)


WINDOW_GEOMETRY_FILE = "window-geometry.json"
DEFAULT_WINDOW_SIZE = (920, 620)
_GEOMETRY_VERSION = 2
# A coordinate past this, or a span past Qt's widget maximum, is not a window.
_COORD_LIMIT = 1 << 30
_QWIDGETSIZE_MAX = 16777215
# The part of the title bar a person drags. The whole frame can be wider than
# the desktop and still be a normal on-screen window.
_TITLE_GRAB = (80, 28)


def _record_int(value) -> bool:
    """True for a JSON integer. A bool is an int in Python, and a float is not."""
    if isinstance(value, bool):
        return False
    if not isinstance(value, int):
        return False
    return True


def _window_record(raw) -> Optional[tuple]:
    """Return (x, y, width, height, maximized) or None when the record is not usable.

    Each field is checked on its own. Version 2 is the plain record. An old
    saveGeometry blob is not a record and returns None so the caller can ignore it.
    """
    if not isinstance(raw, dict) or raw.get("version") != _GEOMETRY_VERSION:
        return None
    x = raw.get("x")
    y = raw.get("y")
    width = raw.get("width")
    height = raw.get("height")
    maximized = raw.get("maximized")
    if not _record_int(x):
        return None
    if not _record_int(y):
        return None
    if not _record_int(width):
        return None
    if not _record_int(height):
        return None
    if not isinstance(maximized, bool):
        return None
    if x < -_COORD_LIMIT or x > _COORD_LIMIT:
        return None
    if y < -_COORD_LIMIT or y > _COORD_LIMIT:
        return None
    if width < 1 or width > _QWIDGETSIZE_MAX or width > _COORD_LIMIT:
        return None
    if height < 1 or height > _QWIDGETSIZE_MAX or height > _COORD_LIMIT:
        return None
    return (x, y, width, height, maximized)


class MainWindow:
    """Thin wrapper so tests can construct the window without exec_."""

    def __init__(
        self,
        nodedir: Optional[Path] = None,
        home: Optional[Path] = None,
        issuer_url: Optional[str] = None,
        credit: Optional[CreditCtl] = None,
        autoload: bool = True,
    ) -> None:
        QtCore, QtGui, QtWidgets = _qt_api()
        self.QtCore = QtCore
        self.QtGui = QtGui
        self.QtWidgets = QtWidgets
        self.home = Path(home) if home else default_home()
        self.home.mkdir(parents=True, exist_ok=True)
        self.tahoe = TahoeClient(nodedir=nodedir, home=self.home)
        self.mf = MagicFolderCtl(config_dir=self.home / "magic-folder", nodedir=self.tahoe.nodedir)
        self.credit = credit or CreditCtl(home=self.home, issuer_url=issuer_url)
        self.recovery = RecoveryCtl(self.home, self.tahoe, self.mf, self.credit)
        self._joined = False
        self._joining = False
        self._credit_loaded = False
        self._invite_session = None

        self.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
        self.app.setApplicationName(APP_NAME)
        self.app.setQuitOnLastWindowClosed(True)

        self.win = QtWidgets.QMainWindow()
        self.win.setWindowTitle(APP_NAME)
        self.win.resize(*DEFAULT_WINDOW_SIZE)
        self.win.closeEvent = self._on_close  # type: ignore[method-assign]

        central = QtWidgets.QWidget()
        self.win.setCentralWidget(central)
        self.stack = QtWidgets.QStackedWidget()
        layout = QtWidgets.QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        # In-window REVIEW, not QMessageBox: PyQt5's offscreen plugin on Windows
        # access-violates in QMessageBox.show() (CI test_excepthook_…).
        self.unexpected_review = QtWidgets.QLabel("")
        self.unexpected_review.setObjectName("unexpectedReview")
        self.unexpected_review.setWordWrap(True)
        self.unexpected_review.setStyleSheet("color: #8b1a1a; padding: 8px 12px;")
        self.unexpected_review.hide()
        layout.addWidget(self.unexpected_review)
        layout.addWidget(self.stack)

        self.join_page = self._build_join_page()
        self.main_page = self._build_main_page()
        self.stack.addWidget(self.join_page)
        self.stack.addWidget(self.main_page)

        self.tray = None
        self.tray_credit_action = None
        self._init_tray()
        self._sync_gated_chrome()
        # After the pages exist, so the layout hint is the real window, not an
        # empty shell. An earlier restore treated that shell as the size cap.
        self._restore_window_geometry()

        self.poll = QtCore.QTimer(self.win)
        self.poll.setInterval(3000)
        self.poll.timeout.connect(self.refresh)

        if autoload:
            self._try_autoload()
        else:
            self.stack.setCurrentWidget(self.join_page)

    def _build_join_page(self):
        QtWidgets = self.QtWidgets
        page = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(page)
        v.setContentsMargins(28, 24, 28, 24)
        title = QtWidgets.QLabel("Join a friendnet")
        title.setObjectName("joinTitle")
        font = title.font()
        font.setPointSize(16)
        font.setBold(True)
        title.setFont(font)
        v.addWidget(title)
        intro = QtWidgets.QLabel("Paste a short code, join link, or text from a QR.")
        intro.setWordWrap(True)
        intro.setObjectName("joinIntro")
        v.addWidget(intro)
        threat_box = QtWidgets.QGroupBox("Please read before you join")
        threat_box.setObjectName("threatBlock")
        tb = QtWidgets.QVBoxLayout(threat_box)
        threat = QtWidgets.QLabel(THREAT_COPY)
        threat.setWordWrap(True)
        threat.setObjectName("threatCopy")
        tb.addWidget(threat)
        self.threat_ack = QtWidgets.QCheckBox(JOIN_THREAT_ACK)
        self.threat_ack.setObjectName("threatAck")
        self.threat_ack.toggled.connect(self._on_join_threat_toggled)
        tb.addWidget(self.threat_ack)
        v.addWidget(threat_box)
        invite_label = QtWidgets.QLabel("Invite")
        invite_label.setObjectName("inviteFieldLabel")
        v.addWidget(invite_label)
        self.invite_edit = QtWidgets.QLineEdit()
        self.invite_edit.setPlaceholderText("7-word-word or join link")
        self.invite_edit.setObjectName("inviteEdit")
        self.invite_edit.returnPressed.connect(self.on_join_invite)
        v.addWidget(self.invite_edit)
        self.offer_storage_cb = QtWidgets.QCheckBox("Offer disk on this device")
        self.offer_storage_cb.setObjectName("offerStorage")
        self.offer_storage_cb.setChecked(True)
        v.addWidget(self.offer_storage_cb)
        self.join_btn = QtWidgets.QPushButton("Join friendnet")
        self.join_btn.setObjectName("joinButton")
        self.join_btn.setAutoDefault(True)
        self.join_btn.setDefault(True)
        self.join_btn.setEnabled(False)
        _style_primary(self.join_btn)
        self.join_btn.clicked.connect(self.on_join_invite)
        v.addWidget(self.join_btn)
        self.existing_btn = QtWidgets.QPushButton("Use existing Tahoe node")
        self.existing_btn.setObjectName("existingButton")
        self.existing_btn.setFlat(True)
        self.existing_btn.setAutoDefault(False)
        self.existing_btn.setEnabled(False)
        self.existing_btn.clicked.connect(self.on_join_existing)
        v.addWidget(self.existing_btn)
        self.import_key_btn = QtWidgets.QPushButton("Import recovery key instead…")
        self.import_key_btn.setObjectName("importKeyButton")
        self.import_key_btn.setFlat(True)
        self.import_key_btn.setAutoDefault(False)
        self.import_key_btn.clicked.connect(self.on_import_recovery)
        v.addWidget(self.import_key_btn)
        self.details_btn = QtWidgets.QPushButton("What's a friendnet?")
        self.details_btn.setObjectName("joinDetails")
        self.details_btn.setFlat(True)
        self.details_btn.setAutoDefault(False)
        self.details_btn.clicked.connect(self.on_join_details)
        v.addWidget(self.details_btn)
        self.join_progress = QtWidgets.QLabel("")
        self.join_progress.setObjectName("joinProgress")
        self.join_progress.setWordWrap(True)
        v.addWidget(self.join_progress)
        self.join_error = QtWidgets.QLabel("")
        self.join_error.setObjectName("joinError")
        self.join_error.setWordWrap(True)
        self.join_error.setStyleSheet("color: #8b1a1a;")
        v.addWidget(self.join_error)
        v.addStretch(1)
        return page

    def _build_main_page(self):
        QtWidgets = self.QtWidgets
        page = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(page)
        v.setContentsMargins(16, 12, 16, 16)
        v.setSpacing(10)
        chrome = QtWidgets.QHBoxLayout()
        chrome.setSpacing(8)
        self.status_chip = QtWidgets.QPushButton("Connecting…")
        self.status_chip.setObjectName("statusChip")
        self.status_chip.setFlat(True)
        self.status_chip.setAutoDefault(False)
        self.status_chip.setCursor(self.QtCore.Qt.PointingHandCursor)
        self.status_chip.setToolTip("Open Storage servers")
        self.status_chip.clicked.connect(self.open_storage_servers)
        self.back_btn = QtWidgets.QPushButton("Folders")
        self.back_btn.setObjectName("backToFolders")
        self.back_btn.setAutoDefault(False)
        self.back_btn.clicked.connect(lambda: self.show_place(self.folders_tab))
        chrome.addWidget(self.back_btn)
        self.servers_nav_btn = QtWidgets.QPushButton("Storage servers")
        self.servers_nav_btn.setObjectName("storageServersNav")
        self.servers_nav_btn.setFlat(True)
        self.servers_nav_btn.setAutoDefault(False)
        self.servers_nav_btn.clicked.connect(self.open_storage_servers)
        chrome.addWidget(self.servers_nav_btn)
        chrome.addStretch(1)
        chrome.addWidget(self.status_chip)
        self.more_btn = QtWidgets.QToolButton()
        self.more_btn.setText("More")
        self.more_btn.setObjectName("moreButton")
        self.more_btn.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        more = QtWidgets.QMenu(self.more_btn)
        more.setObjectName("moreMenu")
        self.invite_action = more.addAction("Invite…")
        self.invite_action.setObjectName("invitePlaceAction")
        self.invite_action.triggered.connect(self.open_invite_share)
        self.credit_action = more.addAction("Credit")
        self.credit_action.setObjectName("creditPlaceAction")
        self.credit_action.triggered.connect(self.open_credit_place)
        self.recovery_action = more.addAction("Recovery")
        self.recovery_action.triggered.connect(lambda: self.show_place(self.recovery_tab))
        self.settings_action = more.addAction("Settings")
        self.settings_action.triggered.connect(lambda: self.show_place(self.settings_tab))
        self.more_btn.setMenu(more)
        chrome.addWidget(self.more_btn)
        v.addLayout(chrome)

        self.places = QtWidgets.QStackedWidget()
        self.places.setObjectName("places")
        self.folders_tab = QtWidgets.QWidget()
        self.folders_tab.setObjectName("foldersTab")
        self.servers_tab = QtWidgets.QWidget()
        self.servers_tab.setObjectName("storageServersTab")
        self.credit_tab = QtWidgets.QWidget()
        self.credit_tab.setObjectName("creditTab")
        self.recovery_tab = QtWidgets.QWidget()
        self.recovery_tab.setObjectName("recoveryTab")
        self.settings_tab = QtWidgets.QWidget()
        self.places.addWidget(self.folders_tab)
        self.places.addWidget(self.servers_tab)
        self.places.addWidget(self.credit_tab)
        self.places.addWidget(self.recovery_tab)
        self.places.addWidget(self.settings_tab)
        self.places.currentChanged.connect(self._on_place_changed)
        v.addWidget(self.places)

        fl = QtWidgets.QVBoxLayout(self.folders_tab)
        head = QtWidgets.QHBoxLayout()
        folders_title = QtWidgets.QLabel("Folders")
        folders_title.setObjectName("foldersTitle")
        font = folders_title.font()
        font.setPointSize(14)
        font.setBold(True)
        folders_title.setFont(font)
        head.addWidget(folders_title)
        head.addStretch(1)
        self.add_btn = QtWidgets.QPushButton("Add folder")
        self.add_btn.setObjectName("addFolderButton")
        _style_primary(self.add_btn)
        self.add_btn.clicked.connect(self.on_add_folder)
        head.addWidget(self.add_btn)
        fl.addLayout(head)
        host_row = QtWidgets.QHBoxLayout()
        self.hosts_line = QtWidgets.QLabel("Hosts: none connected yet")
        self.hosts_line.setObjectName("hostsLine")
        self.manage_servers_btn = QtWidgets.QPushButton("Manage storage servers")
        self.manage_servers_btn.setObjectName("manageServersButton")
        self.manage_servers_btn.setAutoDefault(False)
        self.manage_servers_btn.clicked.connect(self.open_storage_servers)
        host_row.addWidget(self.hosts_line)
        host_row.addWidget(self.manage_servers_btn)
        host_row.addStretch(1)
        fl.addLayout(host_row)
        self.empty_label = QtWidgets.QLabel(
            "No folders on this device yet.\n"
            "Add a local folder to keep in sync here."
        )
        self.empty_label.setWordWrap(True)
        self.empty_label.setObjectName("foldersEmpty")
        fl.addWidget(self.empty_label)
        self.table = QtWidgets.QTableWidget(0, 3)
        self.table.setObjectName("folderTable")
        self.table.setHorizontalHeaderLabels(["Name", "Status", "Local path"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.itemDoubleClicked.connect(self.on_folder_double_clicked)
        self.table.setContextMenuPolicy(self.QtCore.Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.on_folder_context_menu)
        fl.addWidget(self.table, 1)
        self.folder_error = QtWidgets.QLabel("")
        self.folder_error.setObjectName("folderError")
        self.folder_error.setWordWrap(True)
        self.folder_error.setStyleSheet("color: #8b1a1a;")
        fl.addWidget(self.folder_error)
        self.open_credit_btn = QtWidgets.QPushButton("Open Credit")
        self.open_credit_btn.setObjectName("openCreditButton")
        self.open_credit_btn.clicked.connect(self.open_credit_place)
        self.open_credit_btn.hide()
        fl.addWidget(self.open_credit_btn)
        fl.addWidget(self._build_offer_box())
        invite_row = QtWidgets.QHBoxLayout()
        invite_row.setContentsMargins(0, 8, 0, 4)
        invite_note = QtWidgets.QLabel("Invite a friend to store files?")
        invite_note.setObjectName("shareInviteNote")
        self.share_invite_btn = QtWidgets.QPushButton("Share invite")
        self.share_invite_btn.setObjectName("shareInviteButton")
        self.share_invite_btn.setAutoDefault(False)
        self.share_invite_btn.clicked.connect(self.open_invite_share)
        invite_row.addWidget(invite_note)
        invite_row.addWidget(self.share_invite_btn)
        invite_row.addStretch(1)
        fl.addLayout(invite_row)
        fl.addWidget(self._build_recovery_nudge())

        self._build_servers_tab()
        self._build_credit_tab()
        self._build_recovery_tab()
        self._build_settings_tab()
        self._sync_gated_chrome()
        return page

    def _build_servers_tab(self) -> None:
        QtWidgets = self.QtWidgets
        sl = QtWidgets.QVBoxLayout(self.servers_tab)
        title = QtWidgets.QLabel("Storage servers")
        title.setObjectName("storageServersTitle")
        font = title.font()
        font.setPointSize(14)
        font.setBold(True)
        title.setFont(font)
        sl.addWidget(title)
        sub = QtWidgets.QLabel("Where your files' shares are stored.")
        sub.setObjectName("storageServersSubtitle")
        sub.setWordWrap(True)
        sl.addWidget(sub)
        self.add_storage_btn = QtWidgets.QPushButton("+ Add storage server")
        self.add_storage_btn.setObjectName("addStorageButton")
        self.add_storage_btn.setAutoDefault(False)
        _style_primary(self.add_storage_btn)
        self.add_storage_btn.clicked.connect(self.on_add_storage)
        sl.addWidget(self.add_storage_btn)
        self.servers_empty = QtWidgets.QLabel(
            "No storage servers connected yet.\n\n"
            "Add a computer that stores your files' shares."
        )
        self.servers_empty.setObjectName("serversEmpty")
        self.servers_empty.setWordWrap(True)
        self.servers_empty.hide()
        sl.addWidget(self.servers_empty)
        self.servers_used_title = QtWidgets.QLabel("Used by this Sync home")
        self.servers_used_title.setObjectName("serversUsedTitle")
        sl.addWidget(self.servers_used_title)
        self.servers_used_box = QtWidgets.QWidget()
        self.servers_used_box.setObjectName("serversUsed")
        self.servers_used_lay = QtWidgets.QVBoxLayout(self.servers_used_box)
        self.servers_used_lay.setContentsMargins(0, 0, 0, 0)
        sl.addWidget(self.servers_used_box)
        self.servers_avail_title = QtWidgets.QLabel("Available on friendnet (not used yet)")
        self.servers_avail_title.setObjectName("serversAvailableTitle")
        sl.addWidget(self.servers_avail_title)
        self.servers_avail_box = QtWidgets.QWidget()
        self.servers_avail_box.setObjectName("serversAvailable")
        self.servers_avail_lay = QtWidgets.QVBoxLayout(self.servers_avail_box)
        self.servers_avail_lay.setContentsMargins(0, 0, 0, 0)
        sl.addWidget(self.servers_avail_box)
        self.servers_error = QtWidgets.QLabel("")
        self.servers_error.setObjectName("serversError")
        self.servers_error.setWordWrap(True)
        self.servers_error.setStyleSheet("color: #8b1a1a;")
        sl.addWidget(self.servers_error)
        honesty = QtWidgets.QLabel(SERVERS_HONESTY)
        honesty.setObjectName("serversHonesty")
        honesty.setWordWrap(True)
        sl.addWidget(honesty)
        sl.addStretch(1)

    def _clear_layout(self, layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    def _add_server_row(self, layout, row: ServerRow) -> None:
        QtWidgets = self.QtWidgets
        wrap = QtWidgets.QWidget()
        wrap.setObjectName("serverRow")
        outer = QtWidgets.QVBoxLayout(wrap)
        outer.setContentsMargins(0, 4, 0, 4)
        top = QtWidgets.QHBoxLayout()
        name = QtWidgets.QLabel(row.name)
        name.setObjectName("serverName")
        status = QtWidgets.QLabel(row.status)
        status.setObjectName("serverStatus")
        source = QtWidgets.QLabel(row.source)
        source.setObjectName("serverSource")
        top.addWidget(name)
        top.addWidget(status)
        top.addWidget(source)
        top.addStretch(1)
        if row.section == "used":
            btn = QtWidgets.QPushButton("Disconnect")
            btn.setObjectName("disconnectServerButton")
            btn.setAutoDefault(False)
            btn.clicked.connect(
                lambda _checked=False, key=row.key, label=row.name: self.on_disconnect_storage(
                    key, label
                )
            )
        else:
            btn = QtWidgets.QPushButton("Add")
            btn.setObjectName("pinServerButton")
            btn.setAutoDefault(False)
            btn.clicked.connect(
                lambda _checked=False, key=row.key, label=row.name: self.on_use_available(
                    key, label
                )
            )
        top.addWidget(btn)
        outer.addLayout(top)
        if row.note:
            note = QtWidgets.QLabel(row.note)
            note.setObjectName("serverNote")
            note.setWordWrap(True)
            outer.addWidget(note)
        layout.addWidget(wrap)

    def _refresh_hosts_line(self, status: ConnectionStatus) -> None:
        n = int(status.servers_connected or 0)
        if n <= 0:
            match = re.search(r"(\d+)\s+storage", status.detail or "")
            n = int(match.group(1)) if match else 0
        if n <= 0:
            self.hosts_line.setText("Hosts: none connected yet")
        elif n == 1:
            self.hosts_line.setText("Hosts: 1 connected")
        else:
            self.hosts_line.setText("Hosts: %d connected" % n)

    def _refresh_servers(self, status: Optional[ConnectionStatus] = None) -> None:
        if not hasattr(self, "servers_used_lay"):
            return
        if status is None:
            status = self.tahoe.connection_status() if self._joined else ConnectionStatus(state="Offline")
        self._refresh_hosts_line(status)
        try:
            used, available = roster(self.home, list(status.announced_servers or []))
        except SyncError as exc:
            self.servers_error.setText(exc.banner())
            return
        self.servers_error.setText("")
        self._clear_layout(self.servers_used_lay)
        self._clear_layout(self.servers_avail_lay)
        for row in used:
            self._add_server_row(self.servers_used_lay, row)
        for row in available:
            self._add_server_row(self.servers_avail_lay, row)
        empty = not used and not available
        self.servers_empty.setVisible(empty)
        self.servers_used_title.setVisible(bool(used))
        self.servers_used_box.setVisible(bool(used))
        self.servers_avail_title.setVisible(bool(available))
        self.servers_avail_box.setVisible(bool(available))

    def open_storage_servers(self) -> None:
        """Folders → Storage servers. No-op before this home has joined."""
        if not self._joined or self.stack.currentWidget() is not self.main_page:
            return
        self.show_place(self.servers_tab)

    def on_add_storage(self) -> None:
        if not self._joined:
            return
        dlg = AddStorageServerDialog(self.win, self, self.QtWidgets)
        if dlg.dlg.exec_() == self.QtWidgets.QDialog.Accepted:
            self.refresh()

    def on_disconnect_storage(self, key: str, name: str) -> None:
        dlg = DisconnectServerDialog(self.win, self.QtWidgets, name)
        if dlg.dlg.exec_() != self.QtWidgets.QDialog.Accepted:
            return
        try:
            disconnect_server(self.home, self.tahoe.nodedir, key, name=name)
            self.tahoe.reload_static_servers()
        except SyncError as exc:
            self.servers_error.setText(exc.banner())
            return
        except Exception as exc:
            self._log_exception("disconnect-storage", exc)
            self.servers_error.setText(
                unexpected_error(exc, "could not disconnect this storage server.").banner()
            )
            return
        self.refresh()

    def on_use_available(self, key: str, name: str) -> None:
        try:
            use_available_server(self.home, self.tahoe.nodedir, key, name)
            self.tahoe.reload_static_servers()
        except SyncError as exc:
            self.servers_error.setText(exc.banner())
            return
        except Exception as exc:
            self._log_exception("use-available", exc)
            self.servers_error.setText(
                unexpected_error(exc, "could not add this storage server.").banner()
            )
            return
        self.refresh()

    def _build_offer_box(self):
        QtWidgets = self.QtWidgets
        box = QtWidgets.QGroupBox("Offer storage on this disk")
        box.setObjectName("offerBox")
        outer = QtWidgets.QVBoxLayout(box)
        lay = QtWidgets.QHBoxLayout()
        self.disk_pie = _make_disk_pie(box)
        self.disk_offer: Optional[DiskSlices] = None
        self._hosted_last = None
        lay.addWidget(self.disk_pie)
        col = QtWidgets.QVBoxLayout()
        self.offer_percent = QtWidgets.QLabel("Offering 0% of this disk")
        self.offer_percent.setObjectName("offerPercent")
        font = self.offer_percent.font()
        font.setPointSize(13)
        font.setBold(True)
        self.offer_percent.setFont(font)
        self.offer_percent.setWordWrap(True)
        col.addWidget(self.offer_percent)
        self.offer_legend = QtWidgets.QLabel("Used  ·  Kept free  ·  Offered")
        self.offer_legend.setObjectName("offerLegend")
        self.offer_legend.setWordWrap(True)
        col.addWidget(self.offer_legend)
        hint = QtWidgets.QLabel(
            "Offered is free space on this disk that this device will store for the friendnet."
        )
        hint.setObjectName("offerHint")
        hint.setWordWrap(True)
        col.addWidget(hint)
        slider_row = QtWidgets.QHBoxLayout()
        slider_row.addWidget(QtWidgets.QLabel("Offer"))
        self.offer_slider = QtWidgets.QSlider(self.QtCore.Qt.Horizontal)
        self.offer_slider.setObjectName("offerSlider")
        self.offer_slider.setRange(0, 100)
        self.offer_slider.setValue(0)
        self.offer_slider.sliderReleased.connect(self.on_offer_percent_chosen)
        slider_row.addWidget(self.offer_slider, 1)
        col.addLayout(slider_row)
        self.offer_status = QtWidgets.QLabel("")
        self.offer_status.setObjectName("offerStatus")
        self.offer_status.setWordWrap(True)
        col.addWidget(self.offer_status)
        col.addStretch(1)
        lay.addLayout(col, 1)
        outer.addLayout(lay)
        outer.addWidget(self._build_hosted_strip(box))
        return box

    def _build_hosted_strip(self, box):
        """Hosted-for-others meter. Separate from the disk pie."""
        QtWidgets = self.QtWidgets
        strip = QtWidgets.QWidget(box)
        strip.setObjectName("offerHostedStrip")
        lay = QtWidgets.QVBoxLayout(strip)
        lay.setContentsMargins(0, 8, 0, 0)
        title = QtWidgets.QLabel("Hosted for others")
        title.setObjectName("offerHostedTitle")
        font = title.font()
        font.setBold(True)
        title.setFont(font)
        lay.addWidget(title)
        self.offer_hosted_body = QtWidgets.QLabel("Nothing hosted for others yet.")
        self.offer_hosted_body.setObjectName("offerHostedBody")
        self.offer_hosted_body.setWordWrap(True)
        lay.addWidget(self.offer_hosted_body)
        self.offer_hosted_retry = QtWidgets.QPushButton("Retry")
        self.offer_hosted_retry.setObjectName("offerHostedRetry")
        self.offer_hosted_retry.setAutoDefault(False)
        _style_primary(self.offer_hosted_retry)
        self._hosted_retry_mode = "hosted"
        self.offer_hosted_retry.clicked.connect(self._on_hosted_retry)
        self.offer_hosted_retry.hide()
        lay.addWidget(self.offer_hosted_retry)
        self.offer_settlement_chip = QtWidgets.QPushButton("Credit & settlement")
        self.offer_settlement_chip.setObjectName("offerSettlementChip")
        self.offer_settlement_chip.setAutoDefault(False)
        self.offer_settlement_chip.clicked.connect(self.on_settlement_chip)
        lay.addWidget(self.offer_settlement_chip)
        return strip

    def _build_recovery_nudge(self):
        """Dismissible export reminder. Does not block Add folder or the Offer slider."""
        QtWidgets = self.QtWidgets
        box = QtWidgets.QWidget()
        box.setObjectName("recoveryNudge")
        lay = QtWidgets.QHBoxLayout(box)
        lay.setContentsMargins(0, 4, 0, 0)
        note = QtWidgets.QLabel("No recovery key exported yet.")
        note.setObjectName("recoveryNudgeNote")
        note.setWordWrap(True)
        lay.addWidget(note, 1)
        export = QtWidgets.QPushButton("Export recovery key…")
        export.setObjectName("nudgeExport")
        export.setAutoDefault(False)
        export.clicked.connect(self.on_export_recovery)
        dismiss = QtWidgets.QPushButton("Dismiss")
        dismiss.setObjectName("nudgeDismiss")
        dismiss.setFlat(True)
        dismiss.setAutoDefault(False)
        dismiss.clicked.connect(self.on_dismiss_recovery_nudge)
        lay.addWidget(export)
        lay.addWidget(dismiss)
        self._refresh_recovery_nudge(box)
        return box

    def _build_credit_tab(self) -> None:
        QtWidgets = self.QtWidgets
        cl = QtWidgets.QVBoxLayout(self.credit_tab)
        head = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Credit")
        font = title.font()
        font.setBold(True)
        title.setFont(font)
        head.addWidget(title)
        head.addStretch(1)
        self.credit_refresh_btn = QtWidgets.QPushButton("Refresh")
        self.credit_refresh_btn.setObjectName("creditRefreshButton")
        self.credit_refresh_btn.clicked.connect(self.load_credit)
        head.addWidget(self.credit_refresh_btn)
        cl.addLayout(head)

        self.credit_loading = QtWidgets.QLabel("Loading credit balance…")
        self.credit_loading.setObjectName("creditLoading")
        self.credit_loading.hide()
        cl.addWidget(self.credit_loading)

        self.credit_error = QtWidgets.QLabel("")
        self.credit_error.setObjectName("creditError")
        self.credit_error.setWordWrap(True)
        self.credit_error.setStyleSheet("color: #8b1a1a;")
        self.credit_error.hide()
        cl.addWidget(self.credit_error)
        self.credit_retry_btn = QtWidgets.QPushButton("Retry")
        self.credit_retry_btn.setObjectName("creditRetryButton")
        self.credit_retry_btn.clicked.connect(self.load_credit)
        self.credit_retry_btn.hide()
        cl.addWidget(self.credit_retry_btn)

        self.credit_body = QtWidgets.QWidget()
        self.credit_body.setObjectName("creditBody")
        body = QtWidgets.QVBoxLayout(self.credit_body)
        body.setContentsMargins(0, 0, 0, 0)
        remaining_box = QtWidgets.QGroupBox("Remaining")
        remaining_box.setObjectName("creditRemainingBox")
        rb = QtWidgets.QVBoxLayout(remaining_box)
        self.credit_remaining = QtWidgets.QLabel(format_remaining(0))
        self.credit_remaining.setObjectName("creditRemaining")
        self.credit_remaining.setWordWrap(True)
        rb.addWidget(self.credit_remaining)
        denom = QtWidgets.QLabel(DENOMINATION_NOTE)
        denom.setObjectName("creditDenomination")
        denom.setWordWrap(True)
        rb.addWidget(denom)
        body.addWidget(remaining_box)
        self.credit_topup_btn = QtWidgets.QPushButton("Top up")
        self.credit_topup_btn.setObjectName("creditTopUpButton")
        self.credit_topup_btn.clicked.connect(self.on_top_up)
        body.addWidget(self.credit_topup_btn)
        self.credit_pending = QtWidgets.QLabel("")
        self.credit_pending.setObjectName("creditPending")
        self.credit_pending.setWordWrap(True)
        self.credit_pending.hide()
        body.addWidget(self.credit_pending)
        lab = QtWidgets.QLabel(LAB_NOTE)
        lab.setObjectName("creditLabNote")
        lab.setWordWrap(True)
        body.addWidget(lab)
        self.credit_success = QtWidgets.QLabel("")
        self.credit_success.setObjectName("creditSuccess")
        self.credit_success.setWordWrap(True)
        self.credit_success.hide()
        body.addWidget(self.credit_success)
        self.credit_recent = QtWidgets.QLabel("")
        self.credit_recent.setObjectName("creditRecent")
        self.credit_recent.setWordWrap(True)
        body.addWidget(self.credit_recent)
        body.addStretch(1)
        cl.addWidget(self.credit_body)

        self.host_settlement_box = QtWidgets.QGroupBox("Host settlement")
        self.host_settlement_box.setObjectName("hostSettlementBox")
        self.host_settlement_box.setFocusPolicy(self.QtCore.Qt.StrongFocus)
        hb = QtWidgets.QVBoxLayout(self.host_settlement_box)
        self.host_settlement_body = QtWidgets.QLabel("")
        self.host_settlement_body.setObjectName("hostSettlementBody")
        self.host_settlement_body.setWordWrap(True)
        hb.addWidget(self.host_settlement_body)
        self.host_settlement_refresh = QtWidgets.QPushButton("Refresh settlement")
        self.host_settlement_refresh.setObjectName("hostSettlementRefresh")
        self.host_settlement_refresh.setAutoDefault(False)
        self.host_settlement_refresh.clicked.connect(self._load_host_settlement)
        hb.addWidget(self.host_settlement_refresh)
        self.host_settlement_retry = QtWidgets.QPushButton("Retry")
        self.host_settlement_retry.setObjectName("hostSettlementRetry")
        self.host_settlement_retry.setAutoDefault(False)
        _style_primary(self.host_settlement_retry)
        self.host_settlement_retry.clicked.connect(self._load_host_settlement)
        self.host_settlement_retry.hide()
        hb.addWidget(self.host_settlement_retry)
        self.host_settlement_box.hide()
        cl.addWidget(self.host_settlement_box)
        cl.addStretch(1)

    def _build_recovery_tab(self) -> None:
        QtWidgets = self.QtWidgets
        rl = QtWidgets.QVBoxLayout(self.recovery_tab)
        title = QtWidgets.QLabel("Recovery")
        font = title.font()
        font.setBold(True)
        title.setFont(font)
        rl.addWidget(title)
        intro = QtWidgets.QLabel(RECOVERY_INTRO)
        intro.setWordWrap(True)
        intro.setObjectName("recoveryIntro")
        rl.addWidget(intro)
        scary = QtWidgets.QLabel("⚠  " + SCARY_LOSS)
        scary.setWordWrap(True)
        scary.setObjectName("recoveryScary")
        scary.setStyleSheet("color: #8b1a1a; font-weight: bold;")
        rl.addWidget(scary)
        row = QtWidgets.QHBoxLayout()
        self.export_key_btn = QtWidgets.QPushButton("Export recovery key…")
        self.export_key_btn.setObjectName("exportKeyButton")
        self.export_key_btn.setDefault(True)
        self.export_key_btn.clicked.connect(self.on_export_recovery)
        self.import_key_btn2 = QtWidgets.QPushButton("Import recovery key…")
        self.import_key_btn2.setObjectName("importKeyButton2")
        self.import_key_btn2.setAutoDefault(False)
        self.import_key_btn2.clicked.connect(self.on_import_recovery)
        row.addWidget(self.export_key_btn)
        row.addWidget(self.import_key_btn2)
        row.addStretch(1)
        rl.addLayout(row)
        self.recovery_status = QtWidgets.QLabel("")
        self.recovery_status.setObjectName("recoveryStatus")
        self.recovery_status.setWordWrap(True)
        rl.addWidget(self.recovery_status)
        self.last_export_label = QtWidgets.QLabel("")
        self.last_export_label.setObjectName("lastExportLabel")
        rl.addWidget(self.last_export_label)
        self._refresh_last_export()
        rl.addStretch(1)

    def _refresh_last_export(self) -> None:
        info = self.recovery.last_export()
        if not info:
            self.last_export_label.setText("Last export: never")
            return
        when = time.strftime("%Y-%m-%d %H:%M", time.localtime(float(info["last_export"])))
        self.last_export_label.setText(
            "Last export: %s  →  %s" % (when, display_path(info.get("path", "")))
        )

    def _refresh_recovery_nudge(self, box=None) -> None:
        widget = box if box is not None else self.win.findChild(self.QtWidgets.QWidget, "recoveryNudge")
        if widget is None:
            return
        show = self.recovery.last_export() is None and not self.recovery.nudge_dismissed()
        widget.setVisible(show)

    def on_dismiss_recovery_nudge(self) -> None:
        self.recovery.dismiss_export_nudge()
        self._refresh_recovery_nudge()

    def on_export_recovery(self) -> None:
        self.recovery_status.setStyleSheet("")
        self.recovery_status.setText("")
        dlg = ExportRecoveryDialog(self.win, self.recovery, self.QtWidgets)
        if dlg.dlg.exec_() == self.QtWidgets.QDialog.Accepted and dlg.written is not None:
            self.recovery_status.setText(
                "Recovery key written to %s. Move it somewhere safe and offline." % dlg.written
            )
            self._refresh_last_export()
            self._refresh_recovery_nudge()

    def on_import_recovery(self) -> None:
        dlg = ImportRecoveryDialog(self.win, self.recovery, self.QtWidgets)
        if dlg.dlg.exec_() != self.QtWidgets.QDialog.Accepted or dlg.result is None:
            return
        self.apply_restore_result(dlg.result)

    def apply_restore_result(self, result: RestoreResult) -> None:
        note = "Restored %d folder(s): %s." % (len(result.folders), ", ".join(result.folders) or "none")
        if result.skipped:
            note += " Already here: %s." % ", ".join(result.skipped)
        if result.wallet_restored:
            note += " Credit wallet restored."
        if result.credit_recovered:
            note += " %d credits re-collected from the issuer (confirmed as you sync)." % result.credit_recovered
        if result.credit_recover_error:
            note += " Credit could not be re-collected yet (%s); Credit → Retry later." % result.credit_recover_error
        note += " Files will download from the friendnet into %s as this device (%s)." % (
            self.recovery.folder_root,
            result.author_name,
        )
        if not self._joined:
            self._enter_main("Connected", result.grid)
        else:
            self.refresh()
        self.show_place(self.folders_tab)
        self.folder_error.setText(note)
        self.recovery_status.setText(note)

    def _build_settings_tab(self) -> None:
        QtWidgets = self.QtWidgets
        sl = QtWidgets.QVBoxLayout(self.settings_tab)
        sl.addWidget(QtWidgets.QLabel("Settings"))
        share_box = QtWidgets.QGroupBox("Invite others")
        share_box.setObjectName("shareBox")
        sb = QtWidgets.QVBoxLayout(share_box)
        share_hint = QtWidgets.QLabel(
            "Share a short code or the QR. They paste it on Join."
        )
        share_hint.setWordWrap(True)
        share_hint.setObjectName("shareHint")
        sb.addWidget(share_hint)
        self.share_panel = InviteSharePanel(
            sb,
            self,
            QtWidgets,
            {
                "intro": "settingsInviteIntro",
                "qr": "shareQr",
                "code": "shareCode",
                "copy": "copyShare",
                "advanced": "showJoinLink",
                "link": "shareUrl",
                "status": "shareStatus",
            },
        )
        self.share_code_edit = self.share_panel.code_edit
        self.share_url_edit = self.share_panel.join_link
        self.share_qr = self.share_panel.qr
        self.copy_share_btn = self.share_panel.copy_btn
        self.export_page_btn = QtWidgets.QPushButton("Export I2P page…")
        self.export_page_btn.setObjectName("exportInvitePage")
        self.export_page_btn.setFlat(True)
        self.export_page_btn.setAutoDefault(False)
        self.export_page_btn.clicked.connect(self.on_export_invite_page)
        sb.addWidget(self.export_page_btn)
        sl.addWidget(share_box)
        self._refresh_share()
        note = QtWidgets.QLabel(
            "Join links are I2P pages (secret in the #fragment). Folder sync may still "
            "use LAN/WAN.\n\n"
            "Coming later\n"
            "· .deb package (AppImage / macOS / Windows installers ship now)\n\n"
            "This device offers disk on Join unless you uncheck it. The pie on Folders "
            "is how much of this disk that is. Reachable from other machines only if "
            "LEASEGRID_STORAGE_HOSTNAME is a LAN name or IP (lab default is 127.0.0.1).\n\n"
            "About\n"
            "%s\n"
            "Grid: lab-friendnet"
            % about_line()
        )
        note.setWordWrap(True)
        note.setObjectName("settingsNote")
        sl.addWidget(note)
        self.payment_lecture = QtWidgets.QLabel(
            "This friendnet charges for storage.\n"
            "Credit → Top up quotes XMR. Open Credit from More to see the balance."
        )
        self.payment_lecture.setWordWrap(True)
        self.payment_lecture.setObjectName("paymentLecture")
        self.payment_lecture.hide()
        sl.addWidget(self.payment_lecture)
        self.open_logs_btn = QtWidgets.QPushButton(OPEN_LOGS_BUTTON)
        self.open_logs_btn.setObjectName("openLogsButton")
        self.open_logs_btn.setAutoDefault(False)
        self.open_logs_btn.clicked.connect(self.on_open_logs)
        sl.addWidget(self.open_logs_btn)
        self.copy_bug_btn = QtWidgets.QPushButton(COPY_BUG_BUTTON)
        self.copy_bug_btn.setObjectName("copyBugReport")
        self.copy_bug_btn.setAutoDefault(False)
        self.copy_bug_btn.clicked.connect(self.on_copy_bug_report)
        sl.addWidget(self.copy_bug_btn)
        self.settings_status = QtWidgets.QLabel("")
        self.settings_status.setObjectName("settingsStatus")
        self.settings_status.setWordWrap(True)
        self.settings_status.setTextInteractionFlags(self.QtCore.Qt.TextSelectableByMouse)
        sl.addWidget(self.settings_status)
        sl.addStretch(1)

    def on_open_logs(self) -> None:
        """Open <Sync home>/logs. On failure, show the path in Settings."""
        logs = self.home / "logs"
        try:
            logs.mkdir(parents=True, exist_ok=True)
        except OSError:
            self.settings_status.setText(display_path(logs))
            return
        QtCore, QtGui, _QtWidgets = _qt_api()
        opened = QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(logs)))
        if not opened:
            self.settings_status.setText(display_path(logs))

    def bug_report_lines(self) -> list[str]:
        """The report lines before scrubbing. An allowlist: nothing else is copied.

        A raw dump (invite code, tahoe.cfg, the share link, a log tail) is an
        extra line here. Scrubbing the joined text is not what keeps it out.
        """
        statuses: list[str] = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 1)
            statuses.append(item.text() if item is not None else "")
        if len(statuses) == 1:
            folders = "1 folder: %s" % statuses[0]
        else:
            folders = "%d folders" % len(statuses)
            if statuses:
                folders += ": " + ", ".join(statuses)
        return [
            about_line(),
            platform.platform(),
            "Chip: %s" % self.status_chip.text(),
            "Joined: %s" % ("yes" if self._joined else "no"),
            folders,
            "Logs: %s" % display_path(self.home / "logs"),
        ]

    def bug_report_text(self) -> str:
        """Short clipboard report. No invite, furl, recovery key, or wallet."""
        return scrub_bug_report("\n".join(self.bug_report_lines()))

    def on_copy_bug_report(self) -> None:
        self.QtWidgets.QApplication.clipboard().setText(self.bug_report_text())
        self.settings_status.setText("Copied. Paste it into your bug report.")

    def on_join_details(self) -> None:
        QtWidgets = self.QtWidgets
        dlg = QtWidgets.QDialog(self.win)
        dlg.setWindowTitle("What's a friendnet?")
        dlg.setObjectName("joinDetailsDialog")
        lay = QtWidgets.QVBoxLayout(dlg)
        lab = QtWidgets.QLabel(THREAT_COPY)
        lab.setWordWrap(True)
        lab.setObjectName("threatCopy")
        lay.addWidget(lab)
        close = QtWidgets.QPushButton("Close")
        close.clicked.connect(dlg.accept)
        lay.addWidget(close)
        dlg.exec_()

    def current_share_url(self) -> str:
        from .invite import share_url_for_nodedir

        try:
            return share_url_for_nodedir(self.tahoe.nodedir)
        except SyncError:
            return ""

    def ensure_invite_code(self) -> tuple[str, str]:
        """Live short code plus the advanced join link. Does not copy a raw furl."""
        from .invite import start_invite_code

        url = self.current_share_url()
        if not url:
            raise SyncError(
                "could not share an invite. No friendnet joined yet.",
                "join a friendnet first, then Invite.",
            )
        session = self._invite_session
        if session is not None and session.alive() and session.code:
            return session.code, url
        if session is not None:
            session.close()
            self._invite_session = None
        session = start_invite_code(self.tahoe.nodedir, tahoe_bin=self.tahoe.tahoe_bin)
        self._invite_session = session
        return session.code, url

    def _refresh_share(self) -> None:
        """Fill the collapsed join link. A short code is created on Copy / Share."""
        url = self.current_share_url()
        self.share_url_edit.setText(url)
        self.share_url_edit.setCursorPosition(0)
        self.share_url_edit.setToolTip(url)
        self.copy_share_btn.setEnabled(True)
        self.export_page_btn.setEnabled(bool(url))
        session = self._invite_session
        code = session.code if session is not None and session.alive() else ""
        if code:
            self.share_panel.show_existing(code, url)
        else:
            self.share_code_edit.clear()
            self.share_qr.clear()
            self.share_qr.setText("")

    def on_copy_share_url(self) -> None:
        self.share_panel.on_copy()

    def open_invite_share(self) -> None:
        if not self._joined or self.stack.currentWidget() is not self.main_page:
            return
        dlg = InviteShareDialog(self.win, self, self.QtWidgets)
        dlg.dlg.exec_()

    def on_export_invite_page(self) -> None:
        url = self.current_share_url()
        if not url:
            return
        path, _ = self.QtWidgets.QFileDialog.getSaveFileName(
            self.win, "Export I2P invite page", str(Path.home() / "join.html"), "HTML (*.html)"
        )
        if not path:
            return
        from .invite import invite_page_html

        Path(path).write_text(invite_page_html(url), encoding="utf-8")

    def _init_tray(self) -> None:
        QtWidgets = self.QtWidgets
        QtGui = self.QtGui
        # The menu exists even when this platform has no tray icon, so Quit is
        # the same action a tray would show. The icon is shown only when a tray
        # is actually there.
        menu = QtWidgets.QMenu()
        menu.setObjectName("trayMenu")
        open_act = menu.addAction("Open Sync")
        open_act.triggered.connect(self.show)
        self.tray_credit_action = menu.addAction("Credit")
        self.tray_credit_action.triggered.connect(self.open_credit_place)
        quit_act = menu.addAction(INVITE_QUIT_BUTTON)
        quit_act.triggered.connect(self._on_tray_quit)
        self.tray_menu = menu
        if not QtWidgets.QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray = QtWidgets.QSystemTrayIcon(self.win)
        pix = QtGui.QPixmap(16, 16)
        pix.fill(QtGui.QColor("#1f6feb"))
        self.tray.setIcon(QtGui.QIcon(pix))
        self.tray.setToolTip(APP_NAME)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()

    def _tray_activated(self, reason) -> None:
        QtWidgets = self.QtWidgets
        if reason in (
            QtWidgets.QSystemTrayIcon.Trigger,
            QtWidgets.QSystemTrayIcon.DoubleClick,
        ):
            self.show()

    def _invite_process_running(self) -> bool:
        session = getattr(self, "_invite_session", None)
        proc = getattr(session, "proc", None)
        return proc is not None and proc.poll() is None

    def _confirm_quit(self) -> bool:
        """True when the app should quit. A live invite asks first.

        Keep open is the default, including Esc. The window close and the tray
        Quit item both use this.
        """
        if not self._invite_process_running():
            return True
        QtWidgets = self.QtWidgets
        box = QtWidgets.QMessageBox(self.win)
        box.setObjectName("inviteClosePrompt")
        box.setWindowTitle(APP_NAME)
        box.setText(INVITE_CLOSE_QUESTION)
        quit_btn = box.addButton(INVITE_QUIT_BUTTON, QtWidgets.QMessageBox.AcceptRole)
        keep_btn = box.addButton(INVITE_KEEP_OPEN, QtWidgets.QMessageBox.RejectRole)
        box.setDefaultButton(keep_btn)
        box.exec_()
        return box.clickedButton() is quit_btn

    def _on_tray_quit(self) -> None:
        if self._confirm_quit():
            self.quit()

    def _on_close(self, event) -> None:
        """The window is the app. X quits; hiding to tray looked like a crash.

        A running invite asks first. Keep open leaves the window and the invite.
        """
        if not self._confirm_quit():
            event.ignore()
            return
        event.accept()
        self.quit()

    def show(self) -> None:
        self.win.show()
        pending = getattr(self, "_pending_geometry_pos", None)
        on_screen = getattr(self, "_pending_title_on_screen", None)
        maximized = getattr(self, "_pending_maximized", False)
        self._pending_geometry_pos = None
        self._pending_title_on_screen = None
        self._pending_maximized = False
        if maximized:
            self.win.showMaximized()
        elif on_screen is False:
            # The offscreen plugin leaves a window that starts above or left of
            # the desktop there. Pull only the title-bar grab back on.
            self._pull_title_bar_on_screen()
        elif pending is not None and on_screen:
            self.win.move(*pending)
        self._guard_applied_size()
        self.win.raise_()
        self.win.activateWindow()

    def shutdown(self) -> None:
        """Stop the daemons this Sync process started (Magic Folder, then Tahoe)."""
        _close_join_server(self)
        session = getattr(self, "_invite_session", None)
        if session is not None:
            session.close()
            self._invite_session = None
        for ctl in (self.mf, self.tahoe):
            try:
                ctl.stop()
            except Exception:
                pass
        release_instance_lock()

    def _accept_handed_invite(self, text: str) -> bool:
        """True when the Join field should become this invite.

        A different non-empty field asks first. No is the default, including
        Esc. The question names neither invite, and nothing here is logged.
        """
        current = self.invite_edit.text()
        if not current.strip() or current == text:
            return True
        QtWidgets = self.QtWidgets
        box = QtWidgets.QMessageBox(self.win)
        box.setObjectName("handedInviteReplace")
        box.setWindowTitle(APP_NAME)
        box.setText(HANDED_INVITE_REPLACE)
        box.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        box.setDefaultButton(QtWidgets.QMessageBox.No)
        return box.exec_() == QtWidgets.QMessageBox.Yes

    def receive_handed_invite(self, invite: str) -> None:
        """Show a second launch's invite. The user still has to join it."""
        text = (invite or "").strip()
        if not text or len(text) > _JOIN_HANDOFF_MAX:
            return
        self.show()
        if self._joined:
            # No second-grid path exists. Say so, and do not keep the invite.
            self.show_place(self.folders_tab)
            self.folder_error.setStyleSheet("")
            self.folder_error.setText(HANDED_INVITE_DROPPED)
        else:
            self.stack.setCurrentWidget(self.join_page)
            if self._accept_handed_invite(text):
                self.invite_edit.setText(text)
                self.invite_edit.setFocus()
        self._dump_handed_invite()

    def _dump_handed_invite(self) -> None:
        """Test hook. Production launches do not set the path, and nothing is logged."""
        path = _test_env("LEASEGRID_TEST_INVITE_DUMP")
        if not path:
            return
        try:
            Path(path).write_text(
                "joined=%s\nack=%s\nfield=%s\n"
                % (
                    "yes" if self._joined else "no",
                    "1" if self.threat_ack.isChecked() else "0",
                    self.invite_edit.text(),
                ),
                encoding="utf-8",
            )
        except OSError:
            pass

    def _rect_on_a_screen(self, rect) -> bool:
        screens = self.QtGui.QGuiApplication.screens()
        if not screens:
            return True
        return any(screen.availableGeometry().intersects(rect) for screen in screens)

    def _title_grab(self, rect):
        width = min(max(rect.width(), 1), _TITLE_GRAB[0])
        height = min(max(rect.height(), 1), _TITLE_GRAB[1])
        return self.QtCore.QRect(rect.x(), rect.y(), width, height)

    def _title_bar_on_a_screen(self, rect) -> bool:
        """True when the saved title-bar grab lies inside a screen's available area."""
        strip = self._title_grab(rect)
        screens = self.QtGui.QGuiApplication.screens()
        if not screens:
            return True
        return any(screen.availableGeometry().contains(strip) for screen in screens)

    def _pull_title_bar_on_screen(self) -> None:
        """Move the least amount that puts the title-bar grab inside a screen."""
        frame = self.win.frameGeometry()
        if self._title_bar_on_a_screen(frame):
            return
        screens = self.QtGui.QGuiApplication.screens()
        if not screens:
            return
        screen = screens[0].availableGeometry()
        for candidate in screens:
            area = candidate.availableGeometry()
            if area.intersects(frame):
                screen = area
                break
        strip = self._title_grab(frame)
        x, y = strip.x(), strip.y()
        if x < screen.left():
            x = screen.left()
        if y < screen.top():
            y = screen.top()
        right = screen.left() + screen.width()
        bottom = screen.top() + screen.height()
        if x + strip.width() > right:
            x = right - strip.width()
        if y + strip.height() > bottom:
            y = bottom - strip.height()
        dx, dy = x - strip.x(), y - strip.y()
        if dx or dy:
            self.win.move(self.win.x() + dx, self.win.y() + dy)

    def _screen_span(self):
        """Bounding available area of every screen, or None when Qt has no screen."""
        screens = self.QtGui.QGuiApplication.screens()
        if not screens:
            return None
        union = screens[0].availableGeometry()
        for screen in screens[1:]:
            union = union.united(screen.availableGeometry())
        return union

    def _oversized(self, width: int, height: int) -> bool:
        """True when a side is past the screen, the default, and the layout hint.

        The join page is taller than the offscreen desktop (about 800x600) and
        the default width is 920, so a raw compare with the screen would treat
        every normal window as untrusted. A size such as 16,777,215 still fails.
        """
        union = self._screen_span()
        if union is None:
            return False
        hint = self.win.minimumSizeHint()
        width_cap = max(union.width(), DEFAULT_WINDOW_SIZE[0], hint.width())
        height_cap = max(union.height(), DEFAULT_WINDOW_SIZE[1], hint.height())
        return width > width_cap or height > height_cap

    def _fitted_size(self, width: int, height: int) -> tuple:
        """Default size when the saved size is oversized. Otherwise keep it."""
        if not self._oversized(width, height):
            return (width, height)
        log_exception(
            self.home,
            "window geometry",
            ValueError("saved window is larger than the screen; using the default size"),
        )
        return DEFAULT_WINDOW_SIZE

    def _reset_default_geometry(self) -> None:
        self._pending_geometry_pos = None
        self._pending_title_on_screen = None
        self._pending_maximized = False
        self.win.resize(*DEFAULT_WINDOW_SIZE)
        self.win.move(0, 0)

    def _guard_applied_size(self, width: Optional[int] = None, height: Optional[int] = None) -> None:
        """Last check: a size past the cap goes back to the default, before Qt resizes."""
        if width is None or height is None:
            width, height = self.win.width(), self.win.height()
        if self._oversized(width, height):
            self._reset_default_geometry()

    def _apply_window_record(self, x: int, y: int, width: int, height: int, maximized: bool) -> None:
        rect = self.QtCore.QRect(int(x), int(y), int(width), int(height))
        if not self._rect_on_a_screen(rect):
            return
        width, height = self._fitted_size(width, height)
        if self._oversized(width, height):
            # The fitter left the saved span. Refuse it before win.resize so a
            # 16-million-pixel size never reaches Qt. The guard puts the default back.
            self._guard_applied_size(width, height)
            return
        self.win.resize(width, height)
        self.win.move(x, y)
        frame = self.win.frameGeometry()
        self._pending_geometry_pos = (x, y)
        self._pending_title_on_screen = self._title_bar_on_a_screen(frame)
        self._pending_maximized = maximized
        self._guard_applied_size()

    def _restore_window_geometry(self) -> None:
        """Apply a saved record with resize and move. Never call restoreGeometry.

        A missing file is a first launch and is not logged. An old
        ``{"geometry": "<base64>"}`` blob is ignored. A version-2 field that
        is the wrong type or out of range is logged once and the default
        size is put back.
        """
        path = self.home / WINDOW_GEOMETRY_FILE
        if not path.is_file():
            return
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if (
                isinstance(raw, dict)
                and raw.get("version") != _GEOMETRY_VERSION
                and "geometry" in raw
            ):
                return
            saved = _window_record(raw)
            if saved is None:
                raise ValueError("saved window geometry is not usable")
            self._apply_window_record(*saved)
        except Exception as exc:
            log_exception(self.home, "window geometry", exc)
            self._reset_default_geometry()

    def _save_window_geometry(self) -> None:
        try:
            if self.win.isMaximized():
                # normalGeometry is the client origin. win.x()/move() are the
                # frame origin. Save the frame origin so a later restore does
                # not walk by the frame margin on every maximize cycle.
                normal = self.win.normalGeometry()
                client = self.win.geometry()
                frame = self.win.frameGeometry()
                x = normal.x() - (client.x() - frame.x())
                y = normal.y() - (client.y() - frame.y())
                width, height = normal.width(), normal.height()
                maximized = True
            else:
                x, y = self.win.x(), self.win.y()
                width, height = self.win.width(), self.win.height()
                maximized = False
            text = json.dumps(
                {
                    "version": _GEOMETRY_VERSION,
                    "x": int(x),
                    "y": int(y),
                    "width": int(width),
                    "height": int(height),
                    "maximized": maximized,
                }
            ) + "\n"
            path = self.home / WINDOW_GEOMETRY_FILE
            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_text(text, encoding="utf-8")
            try:
                os.replace(tmp, path)
            except OSError:
                try:
                    tmp.unlink()
                except OSError:
                    pass
                return
        except OSError:
            return

    def quit(self) -> None:
        if getattr(self, "_quitting", False):
            return
        self._quitting = True
        self._save_window_geometry()
        self.poll.stop()
        self.shutdown()
        self.app.quit()

    def show_join_error(self, err: SyncError) -> None:
        self.join_error.setText(err.banner())

    def show_unexpected(self, exc: BaseException, log_path: Optional[Path] = None) -> None:
        """One in-window REVIEW banner for an exception no place-specific handler caught."""
        err = unexpected_error(exc, "Leasegrid Sync kept running, but the last action failed.")
        self.status_chip.setText("REVIEW  " + err.message.split(" Unexpected error: ")[-1])
        text = err.banner()
        if log_path is not None:
            text += "\nLog: %s" % display_path(log_path)
        self.unexpected_review.setText(text)
        self.unexpected_review.show()

    def show_folder_error(self, err: SyncError, open_credit: bool = False) -> None:
        self.folder_error.setStyleSheet("color: #8b1a1a;")
        self.folder_error.setText(err.banner())
        self.open_credit_btn.setVisible(open_credit)

    def clear_errors(self) -> None:
        self.join_error.setText("")
        self.join_progress.setText("")
        self.folder_error.setText("")
        self.open_credit_btn.hide()
        self.credit_error.setText("")
        self.credit_error.hide()
        self.credit_success.hide()

    def _try_autoload(self) -> None:
        """Attach to a configured node on launch; otherwise land on the join page."""
        if not self.tahoe.has_nodedir():
            self.stack.setCurrentWidget(self.join_page)
            return
        self.stack.setCurrentWidget(self.join_page)
        self._join_busy(True, "Tahoe node found at %s — connecting…" % display_path(self.tahoe.nodedir))
        try:
            status = self.tahoe.join_existing()
        except SyncError as exc:
            self._join_busy(False)
            self.show_join_error(exc)
            return
        self._join_busy(False)
        self._enter_main(status.state, status.detail)

    def _on_join_threat_toggled(self, checked: bool) -> None:
        if self._joining:
            return
        self.join_btn.setEnabled(checked)
        self.existing_btn.setEnabled(checked)

    def _join_refused_without_ack(self) -> bool:
        if self.threat_ack.isChecked():
            return False
        self.show_join_error(SyncError(JOIN_ACK_MSG, JOIN_ACK_NEXT))
        return True

    def _join_busy(self, busy: bool, text: str = "") -> None:
        self._joining = busy
        allowed = (not busy) and self.threat_ack.isChecked()
        self.join_btn.setEnabled(allowed)
        self.existing_btn.setEnabled(allowed)
        self.threat_ack.setEnabled(not busy)
        self.import_key_btn.setEnabled(not busy)
        self.details_btn.setEnabled(not busy)
        self.invite_edit.setEnabled(not busy)
        self.offer_storage_cb.setEnabled(not busy)
        self.join_progress.setText(text)
        self.QtWidgets.QApplication.processEvents()

    def on_join_invite(self) -> None:
        self.clear_errors()
        if self._join_refused_without_ack():
            return
        invite = self.invite_edit.text()
        offer = self.offer_storage_cb.isChecked()
        kind = "sync + storage" if offer else "sync only"
        progress = (
            "Joining… starting this Tahoe node (%s) and waiting for the introducer "
            "(this can take up to a minute the first time)." % kind
        )
        if self.tahoe.has_nodedir():
            progress = "Connecting to the existing Tahoe node…"
        elif is_wormhole_code(invite):
            progress = (
                "Joining… collecting the friendnet settings behind code %s from your "
                "inviter, then starting this Tahoe node (%s)."
                % (invite.strip().lower(), kind)
            )
        self._join_busy(True, progress)
        try:
            try:
                status = self.tahoe.join_invite(invite, offer_storage=offer)
            except SyncError as exc:
                self.show_join_error(exc)
                return
            except OSError as exc:
                self.show_join_error(join_filesystem_failure(exc))
                return
            self._enter_main(status.state, status.detail)
        finally:
            # Join stays clickable even when join_invite raises outside SyncError.
            self._join_busy(False)

    def on_join_existing(self) -> None:
        self.clear_errors()
        if self._join_refused_without_ack():
            return
        self._join_busy(True, "Connecting to the existing Tahoe node…")
        try:
            try:
                status = self.tahoe.join_existing()
            except SyncError as exc:
                self.show_join_error(exc)
                return
            except (OSError, UnicodeDecodeError) as exc:
                self.show_join_error(join_filesystem_failure(exc))
                return
            self._enter_main(status.state, status.detail)
        finally:
            # Join stays clickable even when join_existing raises outside SyncError.
            self._join_busy(False)

    def _enter_main(self, state: str, detail: str) -> None:
        self._joined = True
        st = self.tahoe.connection_status()
        self.status_chip.setText(format_status_chip(st) if st.state else "%s  %s" % (state, detail))
        self.stack.setCurrentWidget(self.main_page)
        self.show_place(self.folders_tab)
        self._sync_gated_chrome()
        self.poll.start()
        self._refresh_share()
        self.refresh()

    def _sync_gated_chrome(self) -> None:
        """Payment lecture stays hidden until this friendnet charges."""
        gated = credit_enforced()
        if getattr(self, "credit_action", None) is not None:
            self.credit_action.setVisible(gated)
        tray_act = getattr(self, "tray_credit_action", None)
        if tray_act is not None:
            tray_act.setVisible(gated)
        lecture = getattr(self, "payment_lecture", None)
        if lecture is not None:
            lecture.setVisible(gated)

    def _refresh_offer_viz(self) -> None:
        try:
            slices = read_disk_offer(self.tahoe.nodedir, self.home)
        except SyncError as exc:
            self._show_offer_fail(exc)
        except Exception as exc:
            self._log_exception("offer-pie", exc)
            self._show_offer_fail(unexpected_error(exc, "could not read this disk."))
        else:
            self._show_offer_slices(slices, saved=False)
        self._refresh_hosted()

    def _show_offer_fail(self, err: SyncError) -> None:
        self.disk_offer = None
        self.disk_pie.set_slices(None)
        self.offer_percent.setText("% of this disk")
        self.offer_legend.setText("Used  ·  Kept free  ·  Offered")
        self.offer_status.setStyleSheet("color: #8b1a1a;")
        self.offer_status.setText(err.banner())

    def _show_offer_slices(self, slices: DiskSlices, saved: bool) -> None:
        self.disk_offer = slices
        self.disk_pie.set_slices(slices)
        self.offer_percent.setText("Offering %d%% of this disk" % slices.offered_percent)
        self.offer_legend.setText(
            "Used %s  ·  Kept free %s  ·  Offered %s"
            % (format_bytes(slices.used), format_bytes(slices.kept), format_bytes(slices.offered))
        )
        if not self.offer_slider.isSliderDown():
            self.offer_slider.blockSignals(True)
            self.offer_slider.setValue(slices.offered_percent)
            self.offer_slider.blockSignals(False)
        self.offer_status.setStyleSheet("")
        if saved:
            self.offer_status.setText(
                "Saved. This device will offer %d%% of this disk." % slices.offered_percent
            )
        else:
            self.offer_status.setText("")

    def on_offer_percent_chosen(self) -> None:
        percent = self.offer_slider.value()
        try:
            slices = apply_offer_percent(self.tahoe.nodedir, self.home, percent)
        except SyncError as exc:
            self._refresh_offer_viz()
            self.offer_status.setStyleSheet("color: #8b1a1a;")
            self.offer_status.setText(exc.banner())
            return
        except Exception as exc:
            self._log_exception("offer-percent", exc)
            self._refresh_offer_viz()
            self.offer_status.setStyleSheet("color: #8b1a1a;")
            self.offer_status.setText(unexpected_error(exc, "could not offer disk.").banner())
            return
        self._show_offer_slices(slices, saved=True)
        self._refresh_hosted()

    def _refresh_hosted(self) -> None:
        """Reload the hosted strip. Disk pie and the Offer slider stay as they are."""
        try:
            shares = read_hosted_shares(self.tahoe.nodedir)
        except SyncError as exc:
            self._show_hosted_fail(exc)
            return
        except Exception as exc:
            self._log_exception("offer-hosted", exc)
            self._show_hosted_fail(
                unexpected_error(exc, "could not load how much you are hosting for others.")
            )
            return
        self._hosted_last = shares
        settlement_error = ""
        accepted = None
        try:
            local = read_local_accepted(self.tahoe.nodedir)
        except SyncError as exc:
            settlement_error = exc.banner()
        except Exception as exc:
            self._log_exception("offer-hosted-settlement", exc)
            settlement_error = unexpected_error(exc, "could not load settlement status.").banner()
        else:
            if local is not None:
                accepted = local[0]
        self._hosted_retry_mode = "hosted"
        self.offer_hosted_body.setStyleSheet("")
        self.offer_hosted_body.setText(
            format_hosted_strip(shares, accepted=accepted, settlement_error=settlement_error)
        )
        self.offer_hosted_retry.setVisible(bool(settlement_error))

    def _on_hosted_retry(self) -> None:
        if self._hosted_retry_mode == "nav":
            self.on_settlement_chip()
            return
        self._refresh_hosted()

    def _show_hosted_fail(self, err: SyncError) -> None:
        text = err.banner()
        last = self._hosted_last
        if last is not None:
            if last.bytes_hosted > 0:
                text += "\nLast known: Hosting %s for the friendnet." % format_bytes(
                    last.bytes_hosted
                )
            else:
                text += "\nLast known: Nothing hosted for others yet."
        self._hosted_retry_mode = "hosted"
        self.offer_hosted_body.setStyleSheet("color: #8b1a1a;")
        self.offer_hosted_body.setText(text)
        self.offer_hosted_retry.show()

    def on_settlement_chip(self) -> None:
        """Open the existing Credit place under More. Does not add a primary tab."""
        if not self._joined or self.stack.currentWidget() is not self.main_page:
            self._show_settlement_nav_fail()
            return
        self.open_credit_place()
        if self.places.currentWidget() is not self.credit_tab:
            self._show_settlement_nav_fail()
            return
        if self._hosted_retry_mode == "nav":
            self._refresh_hosted()
        if self.host_settlement_box.isVisible():
            self.host_settlement_box.setFocus(self.QtCore.Qt.OtherFocusReason)

    def _show_settlement_nav_fail(self) -> None:
        err = SyncError(
            "Credit place could not open.",
            "use More → Credit; Retry.",
        )
        self._hosted_retry_mode = "nav"
        self.offer_hosted_body.setStyleSheet("color: #8b1a1a;")
        self.offer_hosted_body.setText(err.banner())
        self.offer_hosted_retry.show()

    def _load_host_settlement(self) -> None:
        """Optional Credit strip. Hidden unless this home offers disk."""
        issuer_url = getattr(self.credit, "issuer_url", "") or ""
        try:
            row = load_host_settlement(self.tahoe.nodedir, issuer_url=issuer_url)
        except Exception as exc:
            self._log_exception("host-settlement", exc)
            row = HostSettlement(kind="fail")
        self.host_settlement_body.setText(format_host_settlement(row))
        if row.kind == "hidden":
            self.host_settlement_box.hide()
            return
        failed = row.kind == "fail"
        self.host_settlement_body.setStyleSheet("color: #8b1a1a;" if failed else "")
        self.host_settlement_retry.setVisible(failed)
        self.host_settlement_refresh.setVisible(not failed)
        self.host_settlement_box.show()

    def refresh(self) -> None:
        if not self._joined:
            return
        status = self.tahoe.connection_status()
        self.status_chip.setText(format_status_chip(status))
        self._refresh_servers(status)
        self._refresh_offer_viz()
        try:
            rows = self.mf.list_folders()
        except SyncError as exc:
            self.show_folder_error(exc)
            return
        except Exception as exc:
            self._log_exception("refresh", exc)
            self.show_folder_error(unexpected_error(exc, "could not list folders."))
            return
        self._render_rows(rows)
        self._show_refusal_if_any()

    def _show_refusal_if_any(self) -> bool:
        """Storage refused a write for lack of credit (spender event): say so on Folders."""
        reason = self.credit.recent_refusal()
        if not reason:
            return False
        self.show_folder_error(
            SyncError(
                "sync is paused by the friendnet. %s." % reason,
                "Credit → Top up; uploads resume on the next scan.",
            ),
            open_credit=True,
        )
        return True

    def _folder_path_on_row(self, row: int) -> str:
        item = self.table.item(row, 2)
        return item.text() if item is not None else ""

    def on_folder_double_clicked(self, item) -> None:
        self.open_folder_path(self._folder_path_on_row(item.row()))

    def on_folder_context_menu(self, pos) -> None:
        row = self.table.rowAt(pos.y())
        if row < 0:
            return
        QtWidgets = self.QtWidgets
        menu = QtWidgets.QMenu(self.table)
        menu.setObjectName("folderContextMenu")
        action = menu.addAction("Open folder")
        chosen = menu.exec_(self.table.viewport().mapToGlobal(pos))
        if chosen is action:
            self.open_folder_path(self._folder_path_on_row(row))

    def open_folder_path(self, path: str) -> None:
        if not path:
            return
        target = Path(path)
        if not target.is_dir():
            shown = display_path(path)
            if target.is_file():
                message = FOLDER_FILE_BANNER % shown
            else:
                message = FOLDER_MISSING_BANNER % shown
            self.show_folder_error(
                SyncError(message, "Add the folder again if you still want it.")
            )
            return
        QtCore, QtGui, _QtWidgets = _qt_api()
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(path))

    def _render_rows(self, rows: list[FolderRow]) -> None:
        self.table.setRowCount(len(rows))
        self.empty_label.setVisible(not rows)
        self.table.setVisible(bool(rows))
        QtWidgets = self.QtWidgets
        for i, row in enumerate(rows):
            self.table.setItem(i, 0, QtWidgets.QTableWidgetItem(row.name))
            self.table.setItem(i, 1, QtWidgets.QTableWidgetItem(row.status))
            self.table.setItem(i, 2, QtWidgets.QTableWidgetItem(row.path))

    def on_add_folder(self) -> None:
        QtWidgets = self.QtWidgets
        self.clear_errors()
        remaining = self.credit.remaining_tokens()
        if credit_enforced() and credit_gate(remaining, 0) == "zero":
            self.show_folder_error(SyncError(ZERO_FOLDER_MSG, ZERO_FOLDER_NEXT), open_credit=True)
            return
        path = QtWidgets.QFileDialog.getExistingDirectory(
            self.win, "Choose a local folder to sync", str(Path.home())
        )
        if not path:
            return
        need = self.credit.estimate_tokens(Path(path))
        gate = credit_gate(remaining, need) if credit_enforced() else "ok"
        if gate == "zero":
            self.show_folder_error(SyncError(ZERO_FOLDER_MSG, ZERO_FOLDER_NEXT), open_credit=True)
            return
        if gate == "review":
            if not self._review_expansion(need, remaining):
                return
        self.folder_error.setStyleSheet("")
        self.folder_error.setText("Adding folder… first time can take a minute.")
        self.QtWidgets.QApplication.processEvents()
        try:
            name = self.mf.add_folder(path)
        except SyncError as exc:
            # A gated node refusing the folder's directories surfaces as a Magic
            # Folder 500; the spender's event tells the real story.
            if not self._show_refusal_if_any():
                self.show_folder_error(exc)
            return
        except Exception as exc:
            self._log_exception("on_add_folder", exc)
            self.show_folder_error(unexpected_error(exc, "folder not added."))
            return
        self.refresh()
        self.folder_error.setText("Added folder %s" % name)

    def _review_expansion(self, need: int, remaining: int) -> bool:
        QtWidgets = self.QtWidgets
        box = QtWidgets.QMessageBox(self.win)
        box.setObjectName("expansionReview")
        box.setWindowTitle("REVIEW")
        box.setText(REVIEW_HEAD)
        box.setInformativeText(
            "Share expansion is expected. Estimated need: ~%.1f× upload.\n"
            "Uploading 1 GiB uses more than 1 GiB of credit.\n"
            "Need about %d GiB·mo; remaining %d GiB·mo."
            % (EXPAND_FACTOR, need, remaining)
        )
        topup = box.addButton("Top up", QtWidgets.QMessageBox.AcceptRole)
        box.addButton("Cancel add", QtWidgets.QMessageBox.RejectRole)
        box.exec_()
        if box.clickedButton() is topup:
            self.open_credit_place()
            self.on_top_up()
        return False

    def show_place(self, widget) -> None:
        self.places.setCurrentWidget(widget)

    def _style_place_nav(self, widget) -> None:
        """Folders and Storage servers are the two primary places. Credit stays in More."""
        on_folders = widget is self.folders_tab
        on_servers = widget is self.servers_tab
        self.back_btn.setVisible(True)
        folder_font = self.back_btn.font()
        folder_font.setBold(on_folders)
        self.back_btn.setFont(folder_font)
        self.back_btn.setFlat(not on_folders)
        server_font = self.servers_nav_btn.font()
        server_font.setBold(on_servers)
        self.servers_nav_btn.setFont(server_font)
        self.servers_nav_btn.setFlat(not on_servers)

    def open_credit_place(self) -> None:
        self.show()
        if self.stack.currentWidget() is not self.main_page:
            return
        if self.places.currentWidget() is self.credit_tab:
            self.load_credit()
            return
        self.show_place(self.credit_tab)

    def _on_place_changed(self, idx: int) -> None:
        widget = self.places.widget(idx)
        self._style_place_nav(widget)
        if not self._joined:
            return
        if widget is self.credit_tab:
            self.load_credit()
        elif widget is self.servers_tab:
            self._refresh_servers()
        elif widget is self.settings_tab:
            self._refresh_share()

    def load_credit(self) -> None:
        self.credit_success.hide()
        self.credit_error.hide()
        self.credit_retry_btn.hide()
        self.credit_body.hide()
        self.credit_loading.show()
        self.QtWidgets.QApplication.processEvents()
        try:
            snap = self.credit.load_balance()
        except SyncError as exc:
            self._show_credit_error(exc)
            self._load_host_settlement()
            return
        except Exception as exc:  # a slot must never let this reach Qt (PyQt5 aborts)
            self._log_exception("load_credit", exc)
            self._show_credit_error(unexpected_error(exc, "could not load credit balance."))
            self._load_host_settlement()
            return
        self.apply_credit_snapshot(snap)
        self._load_host_settlement()

    def _show_credit_error(self, exc: SyncError) -> None:
        self.credit_loading.hide()
        self.credit_body.hide()
        self.credit_error.setText(exc.banner())
        self.credit_error.show()
        self.credit_retry_btn.show()

    def _log_exception(self, where: str, exc: BaseException) -> Path:
        return log_exception(self.home, where, exc)

    def apply_credit_snapshot(self, snap: CreditSnapshot, success_note: str = "") -> None:
        self._credit_loaded = True
        self.credit_loading.hide()
        self.credit_error.hide()
        self.credit_retry_btn.hide()
        self.credit_body.show()
        self.credit_remaining.setText(snap.remaining_text)
        if snap.recent:
            lines = ["Recent"]
            for row in snap.recent:
                lines.append("· %s  %s    %s" % (row.title, row.delta, row.when))
            self.credit_recent.setText("\n".join(lines))
            self.credit_recent.show()
        else:
            self.credit_recent.setText("")
            self.credit_recent.hide()
        if success_note:
            self.credit_success.setText(success_note)
            self.credit_success.show()
        else:
            self.credit_success.hide()
        self._render_pending()

    def _render_pending(self) -> None:
        pending = []
        try:
            pending = self.credit.pending_topups()
        except Exception:
            pending = []
        if not pending:
            self.credit_pending.hide()
            self.credit_pending.setText("")
            return
        lines = ["Pending"]
        for row in pending:
            state = str(row.get("state") or "waiting")
            n = row.get("tokens_quoted") or row.get("n") or "?"
            amt = row.get("amount_xmr") or ""
            extra = (" · %s XMR" % amt) if amt else ""
            lines.append("· %s · %s credits%s" % (state, n, extra))
        self.credit_pending.setText("\n".join(lines))
        self.credit_pending.show()

    def on_top_up(self) -> None:
        dlg = TopUpDialog(self.win, self.credit, self.QtWidgets)
        result = dlg.dlg.exec_()
        self._apply_topup_result(dlg, result)

    def _apply_topup_result(self, dlg: TopUpDialog, result) -> None:
        if result == self.QtWidgets.QDialog.Accepted and dlg.snapshot is not None:
            note = "Top-up complete.\n" + dlg.snapshot.remaining_text
            self.apply_credit_snapshot(dlg.snapshot, success_note=note)
            return
        self._render_pending()

    def grab_to(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        pix = self.win.grab()
        pix.save(str(path))

    def dogfood_one_folder(self, folder: Path, screenshot: Optional[Path] = None) -> dict:
        """Join existing friendnet, add one Magic Folder, write a file, wait for status."""
        self.clear_errors()
        status = self.tahoe.join_existing()
        self._enter_main(status.state, status.detail)
        folder.mkdir(parents=True, exist_ok=True)
        name = self.mf.add_folder(str(folder), name="u1-dogfood")
        probe = write_probe_file(folder)
        self.mf.scan_local(name)
        seen = wait_for_file_status(self.mf, name, probe.name)
        self.refresh()
        if screenshot:
            self.grab_to(screenshot)
        return {
            "folder": str(folder),
            "name": name,
            "probe": str(probe),
            "status": seen,
            "grid": status.detail,
        }

    def dogfood_credit(self, screenshot: Optional[Path] = None, tier: str = "medium") -> dict:
        """Join existing friendnet, quote → pay → redeem, show the updated balance."""
        self.clear_errors()
        status = self.tahoe.join_existing()
        self._enter_main(status.state, status.detail)
        before = self.credit.remaining_tokens()
        self.open_credit_place()
        snap = self.credit.complete_topup(int(XMR_TIERS.get(tier, XMR_TIERS["medium"])))
        note = "Top-up complete.\n" + snap.remaining_text
        self.apply_credit_snapshot(snap, success_note=note)
        if screenshot:
            self.grab_to(screenshot)
        return {
            "before": before,
            "after": snap.balance.tokens,
            "remaining": snap.remaining_text,
            "issuer": snap.balance.issuer_pubkey_id,
            "grid": status.detail,
        }


def _signal_names() -> tuple:
    """Signals that should take the normal quit path.

    Windows does not deliver SIGHUP, and an outside SIGTERM is
    TerminateProcess, which no handler can see. A console close or Ctrl+Break
    arrives as SIGBREAK. Ctrl+C is SIGINT.
    """
    if sys.platform == "win32":
        names = ("SIGINT", "SIGBREAK")
    else:
        names = ("SIGTERM", "SIGINT", "SIGHUP")
    return tuple(getattr(signal, name) for name in names if hasattr(signal, name))


def _install_signal_quit(ui) -> None:
    """Wake the Qt loop when a quit signal arrives, then call ``ui.quit()``.

    The handler only sets a flag. ``set_wakeup_fd`` writes one byte from C so
    the loop wakes during ``exec_``. The socket notifier and a short timer run
    on the Qt thread and are the only places that touch Qt.
    """
    if getattr(ui, "_signal_quit_state", None) is not None:
        return
    read_s, write_s = socket.socketpair()
    read_s.setblocking(False)
    write_s.setblocking(False)
    prev_fd = signal.set_wakeup_fd(write_s.fileno())
    ui._signal_quit_requested = False

    def _handler(signum, frame) -> None:
        ui._signal_quit_requested = True

    previous = {}
    for sig in _signal_names():
        previous[sig] = signal.signal(sig, _handler)

    notifier = ui.QtCore.QSocketNotifier(
        read_s.fileno(), ui.QtCore.QSocketNotifier.Read, ui.app
    )

    def _drain() -> None:
        try:
            while read_s.recv(256):
                pass
        except (BlockingIOError, InterruptedError, OSError):
            pass

    def _on_signal(*_args) -> None:
        _drain()
        if ui._signal_quit_requested:
            ui.quit()

    notifier.activated.connect(_on_signal)
    timer = ui.QtCore.QTimer(ui.app)
    timer.setInterval(100)
    timer.timeout.connect(_on_signal)
    timer.start()
    ui._signal_quit_state = (read_s, write_s, notifier, timer, prev_fd, previous)
    ready = _test_env("LEASEGRID_TEST_SIGNAL_READY")
    if ready:
        try:
            Path(ready).write_text("ready\n", encoding="utf-8")
        except OSError:
            pass


def _remove_signal_quit(ui) -> None:
    state = getattr(ui, "_signal_quit_state", None)
    if not state:
        return
    ui._signal_quit_state = None
    read_s, write_s, notifier, timer, prev_fd, previous = state
    try:
        timer.stop()
    except Exception:
        pass
    try:
        notifier.setEnabled(False)
    except Exception:
        pass
    for sig, handler in previous.items():
        try:
            signal.signal(sig, handler)
        except OSError:
            pass
    try:
        signal.set_wakeup_fd(prev_fd)
    except (OSError, ValueError):
        try:
            signal.set_wakeup_fd(-1)
        except (OSError, ValueError):
            pass
    for sock in (read_s, write_s):
        try:
            sock.close()
        except OSError:
            pass


def run_app(
    nodedir: Optional[Path] = None,
    screenshot: Optional[Path] = None,
    dogfood_folder: Optional[Path] = None,
    issuer_url: Optional[str] = None,
    credit_dogfood: bool = False,
    credit_tier: str = "medium",
    invite: Optional[str] = None,
    offer_storage: bool = True,
) -> int:
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    # One window per Sync home. Headless CLI commands never reach here.
    if not acquire_instance_lock(default_home()):
        _show_already_running()
        return 0
    ui = MainWindow(nodedir=nodedir, issuer_url=issuer_url, autoload=False)
    install_excepthook(ui)
    ui.show()
    ui.QtWidgets.QApplication.processEvents()
    _start_join_server(ui)
    try:
        if invite:
            # Headless join first (creates + starts the node); the modes below then
            # attach to it as an existing node and quit stops what we started.
            try:
                ui.tahoe.join_invite(invite.strip(), offer_storage=offer_storage)
            except SyncError as exc:
                ui.show_join_error(exc)
                if screenshot:
                    ui.grab_to(screenshot)
                print(exc.banner(), file=sys.stderr)
                return 1
        return _run_modes(ui, screenshot, dogfood_folder, credit_dogfood, credit_tier)
    finally:
        ui.shutdown()


def _run_modes(
    ui: MainWindow,
    screenshot: Optional[Path],
    dogfood_folder: Optional[Path],
    credit_dogfood: bool,
    credit_tier: str,
) -> int:
    if not (credit_dogfood or dogfood_folder is not None):
        # Window is visible first so a slow Tahoe start shows progress copy, not a blank desktop.
        ui._try_autoload()
    if credit_dogfood:
        try:
            result = ui.dogfood_credit(screenshot=screenshot, tier=credit_tier)
        except SyncError as exc:
            ui.open_credit_place()
            ui.credit_loading.hide()
            ui.credit_error.setText(exc.banner())
            ui.credit_error.show()
            ui.credit_retry_btn.show()
            if screenshot:
                ui.grab_to(screenshot)
            print(exc.banner(), file=sys.stderr)
            return 1
        print(
            "U2 credit-dogfood before=%s after=%s remaining=%s"
            % (result["before"], result["after"], result["remaining"].split("\n")[0])
        )
        if dogfood_folder is None:
            return 0
        # both flags: top up first, then the upload that spends it (paid-path CI)
    if dogfood_folder is not None:
        try:
            result = ui.dogfood_one_folder(dogfood_folder, screenshot=screenshot)
        except SyncError as exc:
            ui.show_folder_error(exc)
            if screenshot:
                ui.grab_to(screenshot)
            print(exc.banner(), file=sys.stderr)
            return 1
        print("U1 dogfood folder=%s probe=%s status=%s" % (
            result["folder"], result["probe"], result["status"]
        ))
        return 0
    if screenshot:
        ui.QtCore.QTimer.singleShot(400, lambda: ui.grab_to(screenshot))
        ui.QtCore.QTimer.singleShot(800, ui.app.quit)
    _install_signal_quit(ui)
    try:
        return ui.app.exec_()
    finally:
        _remove_signal_quit(ui)
