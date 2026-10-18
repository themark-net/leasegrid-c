"""A handed invite asks at most once, outside the socket slot.

A burst used to nest QMessageBox.exec_() inside the readyRead slot. SIGTERM
then never quit, or the process aborted. These tests drive a real offscreen
process. The invite dump is a test hook and holds only the fake invites below.
"""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

from leasegrid_sync.app import instance_lock_path, join_endpoint

# Wormhole-shaped fakes. Not secrets. The app must not write them to the log.
PREFILL = "7-guitarist-revenge"
YES_B = "8-guitarist-revenge"
YES_C = "9-guitarist-revenge"
SEQ_A = "7-alone-opulent"
SEQ_B = "8-alone-opulent"
SEQ_NONL = "9-alone-opulent"
FLOOD_COUNT = 400

_HOOKED_MAIN = """\
import sys
import leasegrid_sync.app as appmod
appmod._TEST_HOOKS = True
from leasegrid_sync.cli import main
rc = main(sys.argv[1:])
raise SystemExit(0 if rc is None else int(rc))
"""

# One helper sends every payload. A QCoreApplication in the test would stick.
_WIN_SEND = r"""
import sys
from PyQt5.QtCore import QCoreApplication
from PyQt5.QtNetwork import QLocalSocket

app = QCoreApplication([])
name = sys.argv[1]
raw = sys.stdin.buffer.read()
for payload in raw.split(b"\0"):
    if not payload:
        continue
    sock = QLocalSocket()
    sock.connectToServer(name)
    if not sock.waitForConnected(2000):
        raise SystemExit(2)
    sock.write(payload)
    if not sock.waitForBytesWritten(2000):
        raise SystemExit(2)
    sock.abort()
raise SystemExit(0)
"""


# Windows CI: the offscreen plugin access-violates in any QMessageBox show
# (rc 3221225477), a harness-only crash. These real-process tests show a real
# box, so on Windows they use the native platform the shipped app uses.
_QPA = "windows" if sys.platform == "win32" else "offscreen"
_QPA_ARGS = [] if sys.platform == "win32" else ["--offscreen"]


def _wait_until(predicate, timeout: float) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return False


def _dump(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _send_one(endpoint: str, payload: bytes) -> None:
    """Connect, write, close. Retry when the 8-deep accept queue is full."""
    deadline = time.time() + 10
    last: BaseException | None = None
    while time.time() < deadline:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(2)
        try:
            sock.connect(endpoint)
            if payload:
                sock.sendall(payload)
            return
        except (BlockingIOError, ConnectionRefusedError, TimeoutError, InterruptedError) as exc:
            last = exc
            time.sleep(0.01)
        finally:
            sock.close()
    raise AssertionError("could not hand off: %s" % last)


def _send_payloads(endpoint: str, payloads: list[bytes]) -> None:
    if sys.platform == "win32":
        proc = subprocess.run(
            [sys.executable, "-c", _WIN_SEND, endpoint],
            input=b"\0".join(payloads),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=120,
            check=False,
        )
        assert proc.returncode == 0, proc.stderr
        return
    for payload in payloads:
        _send_one(endpoint, payload)


def _launch(tmp_path: Path, click_file: Path | None = None):
    home = tmp_path / "home"
    nodedir = tmp_path / "missing-node"
    ready = tmp_path / "join-ready"
    signal_ready = tmp_path / "signal-ready"
    dump = tmp_path / "invite-dump"
    err_path = tmp_path / "app.err"
    env = os.environ.copy()
    env["LEASEGRID_SYNC_HOME"] = str(home)
    env["LEASEGRID_TEST_JOIN_READY"] = str(ready)
    env["LEASEGRID_TEST_SIGNAL_READY"] = str(signal_ready)
    env["LEASEGRID_TEST_INVITE_DUMP"] = str(dump)
    env["QT_QPA_PLATFORM"] = _QPA
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if click_file is not None:
        env["LEASEGRID_TEST_REPLACE_CLICK_FILE"] = str(click_file)
    env.pop("LEASEGRID_TAHOE_BIN", None)
    env.pop("LEASEGRID_MAGIC_FOLDER_BIN", None)
    err_f = err_path.open("w", encoding="utf-8")
    driver = tmp_path / "hooked_main.py"
    driver.write_text(_HOOKED_MAIN, encoding="utf-8")
    kwargs: dict = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    proc = subprocess.Popen(
        [sys.executable, str(driver), *_QPA_ARGS, "--nodedir", str(nodedir)],
        stdout=subprocess.DEVNULL,
        stderr=err_f,
        env=env,
        **kwargs,
    )
    return proc, home, dump, err_path, err_f, ready, signal_ready


def _stop(proc: subprocess.Popen, err_f) -> None:
    err_f.close()
    if proc.poll() is None:
        proc.kill()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass


def _ready(proc, err_path: Path, ready: Path, signal_ready: Path, home: Path) -> str:
    assert _wait_until(
        lambda: (ready.is_file() and signal_ready.is_file()) or proc.poll() is not None,
        25,
    ), err_path.read_text(encoding="utf-8")
    assert proc.poll() is None, err_path.read_text(encoding="utf-8")
    endpoint = join_endpoint(home)
    assert endpoint
    if sys.platform != "win32":
        assert _wait_until(lambda: Path(endpoint).exists(), 5), endpoint
    return endpoint


def _sigterm(proc: subprocess.Popen, timeout: float = 15) -> int:
    os.kill(proc.pid, signal.SIGTERM)
    if _wait_until(lambda: proc.poll() is not None, timeout):
        return int(proc.returncode)
    proc.kill()
    proc.wait(timeout=5)
    return int(proc.returncode)


def test_flood_of_different_invites_keeps_one_box_and_quits(tmp_path: Path) -> None:
    proc, home, dump, err_path, err_f, ready, signal_ready = _launch(tmp_path)
    try:
        endpoint = _ready(proc, err_path, ready, signal_ready, home)
        _send_payloads(endpoint, [(PREFILL + "\n").encode("utf-8")])
        assert _wait_until(lambda: "field=%s\n" % PREFILL in _dump(dump), 10), _dump(dump)
        last = "8-guitarist-%04d" % (FLOOD_COUNT - 1)
        payloads = [("8-guitarist-%04d\n" % i).encode("utf-8") for i in range(FLOOD_COUNT)]
        _send_payloads(endpoint, payloads)
        assert proc.poll() is None, err_path.read_text(encoding="utf-8")

        def _one_box() -> bool:
            text = _dump(dump)
            return "boxes=1\n" in text and "pending=%s\n" % last in text

        saw_one = _wait_until(_one_box, 10)
        snap = _dump(dump)
        assert proc.poll() is None, err_path.read_text(encoding="utf-8")
        log = home / "logs" / "sync-ui.log"
        if log.is_file():
            logged = log.read_text(encoding="utf-8")
            assert PREFILL not in logged
            assert last not in logged
        if sys.platform == "win32":
            # Windows SIGTERM is TerminateProcess and cannot run the quit handler.
            assert saw_one, snap
            return
        os.kill(proc.pid, signal.SIGTERM)
        quit_in_time = _wait_until(lambda: proc.poll() is not None, 15)
        assert quit_in_time, "app still alive 15s after SIGTERM"
        assert proc.returncode == 0, proc.returncode
        assert not instance_lock_path(home).exists()
        assert saw_one, snap
        assert "field=%s\n" % PREFILL in snap
    finally:
        _stop(proc, err_f)


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="Windows SIGTERM is TerminateProcess and cannot run the quit handler",
)
def test_sigterm_with_the_replace_question_open_exits_zero(tmp_path: Path) -> None:
    """Tester sequence A, B, B, no-newline, sleep 2. Base aborted with -6 or -11."""
    proc, home, dump, err_path, err_f, ready, signal_ready = _launch(tmp_path)
    try:
        endpoint = _ready(proc, err_path, ready, signal_ready, home)
        _send_payloads(endpoint, [(SEQ_A + "\n").encode("utf-8")])
        assert _wait_until(lambda: "field=%s\n" % SEQ_A in _dump(dump), 10), _dump(dump)
        _send_payloads(
            endpoint,
            [
                (SEQ_B + "\n").encode("utf-8"),
                (SEQ_B + "\n").encode("utf-8"),
                SEQ_NONL.encode("utf-8"),
            ],
        )
        time.sleep(2)
        assert proc.poll() is None, "died during sequence rc=%s" % proc.returncode
        code = _sigterm(proc)
        assert code == 0, code
        assert not instance_lock_path(home).exists()
    finally:
        _stop(proc, err_f)


@pytest.mark.parametrize("choice,field", [("yes", YES_C), ("no", PREFILL)])
def test_latest_handed_invite_wins(tmp_path: Path, choice: str, field: str) -> None:
    click = tmp_path / "click"
    click.write_text("", encoding="utf-8")
    proc, home, dump, err_path, err_f, ready, signal_ready = _launch(tmp_path, click)
    try:
        endpoint = _ready(proc, err_path, ready, signal_ready, home)
        _send_payloads(endpoint, [(PREFILL + "\n").encode("utf-8")])
        assert _wait_until(lambda: "field=%s\n" % PREFILL in _dump(dump), 10), _dump(dump)
        _send_payloads(
            endpoint,
            [(YES_B + "\n").encode("utf-8"), (YES_C + "\n").encode("utf-8")],
        )

        def _pending_c() -> bool:
            text = _dump(dump)
            return "boxes=1\n" in text and "pending=%s\n" % YES_C in text

        assert _wait_until(_pending_c, 10), _dump(dump)
        click.write_text(choice, encoding="utf-8")

        def _answered() -> bool:
            text = _dump(dump)
            return (
                "field=%s\n" % field in text
                and "boxes=0\n" in text
                and "pending=\n" in text
            )

        assert _wait_until(_answered, 10), _dump(dump)
        log = home / "logs" / "sync-ui.log"
        if log.is_file():
            logged = log.read_text(encoding="utf-8")
            assert PREFILL not in logged
            assert YES_B not in logged
            assert YES_C not in logged
        assert proc.poll() is None
    finally:
        _stop(proc, err_f)
