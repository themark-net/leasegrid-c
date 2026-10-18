# Fixture for `semgrep --test tools/semgrep`. Each ruleid line must match; each ok line must not.
import os
import pickle
import signal
import socket
import sys
import tempfile
from pathlib import Path

from PyQt5.QtCore import QLockFile
from PyQt5.QtNetwork import QLocalServer


def ipc_paths(name):
    # ruleid: ipc-endpoint-in-shared-tmp
    a = os.path.join(tempfile.gettempdir(), name)
    # ruleid: ipc-endpoint-in-shared-tmp
    b = Path(tempfile.gettempdir()) / name
    # ruleid: ipc-endpoint-in-shared-tmp
    c = os.path.join("/tmp", name)
    # ok: ipc-endpoint-in-shared-tmp
    d = os.path.join(os.environ["XDG_RUNTIME_DIR"], name)
    return a, b, c, d


def server_bad(app, name):
    server = QLocalServer(app)
    # ruleid: qlocalserver-listen-without-user-access-option
    server.listen(name)


def server_good(app, name):
    server = QLocalServer(app)
    server.setSocketOptions(QLocalServer.UserAccessOption)
    # ok: qlocalserver-listen-without-user-access-option
    server.listen(name)


def locks(path):
    lock = QLockFile(path)
    # ruleid: qlockfile-manual-stale-removal
    lock.setStaleLockTime(0)
    # ruleid: qlockfile-manual-stale-removal
    lock.removeStaleLockFile()
    # ok: qlockfile-manual-stale-removal
    lock.setStaleLockTime(30000)
    return lock.tryLock(0)


def kills(pgid, pid, proc):
    # ruleid: signal-to-stored-pid, posix-only-process-api
    os.killpg(pgid, signal.SIGTERM)
    # ruleid: signal-to-stored-pid
    os.kill(pid, signal.SIGTERM)
    # ok: signal-to-stored-pid
    proc.terminate()


def restore(win, blob, data):
    # ruleid: restore-untrusted-serialized-state
    win.restoreGeometry(blob)
    # ruleid: restore-untrusted-serialized-state
    obj = pickle.loads(data)
    # ok: restore-untrusted-serialized-state
    win.resize(800, 600)
    return obj


def posix_unguarded():
    # ruleid: posix-only-process-api
    return signal.SIGKILL


def posix_guarded(pid):
    if sys.platform != "win32":
        # ok: posix-only-process-api
        return os.getpgid(pid)
    return None


def posix_early_return(pid):
    if sys.platform == "win32":
        return None
    # ok: posix-only-process-api
    return os.getpgid(pid)


def unix_socket():
    # ruleid: af-unix-path-length
    return socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
