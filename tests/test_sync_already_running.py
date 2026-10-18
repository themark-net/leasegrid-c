"""A second launch shows the already-running box and does not abort.

Older tests patch QMessageBox.information, so they never construct a widget
and miss an application object that is thrown away. This driver only turns
on _TEST_HOOKS. The box is the real one. A timer accepts it and writes its
text. The invite in the dump is a fake.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from leasegrid_sync.app import (
    ALREADY_RUNNING,
    _JOIN_HANDOFF_MAX,
    instance_lock_path,
    join_endpoint,
)

# Wormhole-shaped fake. Not a secret. The already-running box must not contain it.
HANDOFF = "7-guitarist-revenge"
OVERSIZE = "x" * (_JOIN_HANDOFF_MAX + 1)

_HOOKED_MAIN = """\
import sys
import leasegrid_sync.app as appmod
appmod._TEST_HOOKS = True
from leasegrid_sync.cli import main
rc = main(sys.argv[1:])
raise SystemExit(0 if rc is None else int(rc))
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


def _launch(
    tmp_path: Path,
    *args: str,
    text_file: Path | None = None,
    dismiss: bool = False,
    shown: Path | None = None,
):
    home = tmp_path / "home"
    nodedir = tmp_path / "missing-node"
    if shown is not None:
        tag = shown.name
    elif text_file is not None:
        tag = text_file.name
    else:
        tag = "first"
    err_path = tmp_path / ("second-%s.err" % tag)
    env = os.environ.copy()
    env["LEASEGRID_SYNC_HOME"] = str(home)
    env["QT_QPA_PLATFORM"] = _QPA
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.pop("LEASEGRID_TAHOE_BIN", None)
    env.pop("LEASEGRID_MAGIC_FOLDER_BIN", None)
    if shown is not None:
        env["LEASEGRID_TEST_ALREADY_SHOWN"] = str(shown)
    elif not dismiss:
        env["LEASEGRID_TEST_JOIN_READY"] = str(tmp_path / "join-ready")
        env["LEASEGRID_TEST_SIGNAL_READY"] = str(tmp_path / "signal-ready")
        env["LEASEGRID_TEST_INVITE_DUMP"] = str(tmp_path / "invite-dump")
    else:
        env["LEASEGRID_TEST_AUTODISMISS_MS"] = "0"
        if text_file is not None:
            env["LEASEGRID_TEST_ALREADY_TEXT"] = str(text_file)
    err_f = err_path.open("w", encoding="utf-8")
    driver = tmp_path / "hooked_main.py"
    driver.write_text(_HOOKED_MAIN, encoding="utf-8")
    kwargs: dict = {}
    if sys.platform == "win32" and not dismiss:
        # Own group, like the other handoff tests, so console events stay local.
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    proc = subprocess.Popen(
        [sys.executable, str(driver), *_QPA_ARGS, "--nodedir", str(nodedir), *args],
        stdout=subprocess.DEVNULL,
        stderr=err_f,
        env=env,
        **kwargs,
    )
    return proc, err_path, err_f


def _stderr(err_path: Path) -> str:
    try:
        return err_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _stop(proc: subprocess.Popen) -> None:
    if proc.poll() is None:
        proc.kill()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass


def test_unmocked_second_launch_shows_already_running_and_stays_up(tmp_path: Path) -> None:
    """Plain relaunch exits 0. An oversized --join while the lock is held exits 1.

    Neither aborts, and the first window still accepts a later handoff.
    """
    ready = tmp_path / "join-ready"
    dump = tmp_path / "invite-dump"
    plain_text = tmp_path / "plain-text"
    held_text = tmp_path / "held-text"
    first, first_err, first_f = _launch(tmp_path)
    second = None
    third = None
    try:
        assert _wait_until(lambda: ready.is_file() or first.poll() is not None, 25), (
            "first app did not listen: rc %s %s" % (first.poll(), _stderr(first_err)[-800:])
        )
        assert first.poll() is None, _stderr(first_err)
        home = tmp_path / "home"
        endpoint = join_endpoint(home)
        assert endpoint
        if sys.platform != "win32":
            assert _wait_until(lambda: Path(endpoint).exists(), 5), endpoint
        assert instance_lock_path(home).is_file()

        second, second_err, second_f = _launch(tmp_path, text_file=plain_text, dismiss=True)
        try:
            second.wait(timeout=20)
        except subprocess.TimeoutExpired:
            _stop(second)
            pytest.fail("plain relaunch still alive: %s" % _stderr(second_err)[-500:])
        finally:
            if not second_f.closed:
                second_f.close()
        plain_err = _stderr(second_err)
        assert second.returncode == 0, "rc %s stderr %s" % (second.returncode, plain_err[-500:])
        assert second.returncode not in (134, -6, -11)
        assert "Must construct a QApplication" not in plain_err
        assert plain_text.is_file(), "no box text; stderr %s" % plain_err[-500:]
        assert plain_text.read_text(encoding="utf-8") == ALREADY_RUNNING
        assert first.poll() is None, _stderr(first_err)

        third, third_err, third_f = _launch(
            tmp_path, "--join", OVERSIZE, text_file=held_text, dismiss=True
        )
        try:
            third.wait(timeout=20)
        except subprocess.TimeoutExpired:
            _stop(third)
            pytest.fail("held relaunch still alive")
        finally:
            if not third_f.closed:
                third_f.close()
        held_err = _stderr(third_err)
        assert third.returncode == 1, "rc %s stderr %s" % (third.returncode, held_err[-500:])
        assert third.returncode not in (134, -6, -11)
        assert "Must construct a QApplication" not in held_err
        assert OVERSIZE not in held_err
        assert held_text.read_text(encoding="utf-8") == ALREADY_RUNNING
        assert OVERSIZE not in held_text.read_text(encoding="utf-8")
        assert first.poll() is None, _stderr(first_err)

        # The real client path, as a user's second launch would hand it off.
        sender, sender_err, sender_f = _launch(
            tmp_path, "--join", HANDOFF, text_file=tmp_path / "sender-text", dismiss=True
        )
        try:
            sender.wait(timeout=20)
        except subprocess.TimeoutExpired:
            _stop(sender)
            pytest.fail("handoff launch still alive: %s" % _stderr(sender_err)[-500:])
        finally:
            if not sender_f.closed:
                sender_f.close()
        assert sender.returncode == 0, "rc %s stderr %s" % (
            sender.returncode,
            _stderr(sender_err)[-500:],
        )
        assert _wait_until(
            lambda: ("field=%s\n" % HANDOFF) in dump.read_text(encoding="utf-8")
            if dump.is_file()
            else False,
            10,
        ), dump.read_text(encoding="utf-8") if dump.is_file() else "no dump"
        assert first.poll() is None
        assert instance_lock_path(home).is_file()
    finally:
        if not first_f.closed:
            first_f.close()
        _stop(first)
        if second is not None:
            _stop(second)
        if third is not None:
            _stop(third)


_BOX_QUIT_SIGNALS = [signal.SIGTERM, signal.SIGINT]
if getattr(signal, "SIGHUP", None) is not None:
    _BOX_QUIT_SIGNALS.append(signal.SIGHUP)


def _signal_name(sig: int) -> str:
    try:
        return signal.Signals(sig).name
    except ValueError:
        return str(sig)


@pytest.mark.skipif(
    sys.platform == "win32",
    reason=(
        "TerminateProcess cannot be caught. The already-running box does not "
        "install SIGINT, SIGTERM, or SIGHUP handlers on Windows."
    ),
)
@pytest.mark.parametrize("sig", _BOX_QUIT_SIGNALS, ids=_signal_name)
def test_already_running_second_launch_exits_0_on_sigterm(tmp_path: Path, sig: int) -> None:
    """A plain second launch on the box exits 0 for SIGTERM, SIGINT, and SIGHUP.

    SIGINT used to raise KeyboardInterrupt inside the Qt slot and abort (rc -6).
    SIGHUP used to kill the process (rc -1). The first app and its lock stay.
    """
    ready = tmp_path / "join-ready"
    shown = tmp_path / "shown"
    name = _signal_name(sig)
    first, first_err, first_f = _launch(tmp_path)
    second = None
    second_f = None
    try:
        assert _wait_until(lambda: ready.is_file() or first.poll() is not None, 25), (
            "first app did not listen: rc %s %s" % (first.poll(), _stderr(first_err)[-800:])
        )
        assert first.poll() is None, _stderr(first_err)
        second, second_err, second_f = _launch(tmp_path, shown=shown)
        assert _wait_until(lambda: shown.is_file() or second.poll() is not None, 20), (
            "second launch did not show the box: rc %s %s"
            % (second.poll(), _stderr(second_err)[-800:])
        )
        assert second.poll() is None, _stderr(second_err)
        assert shown.read_text(encoding="utf-8") == ALREADY_RUNNING
        lock_path = instance_lock_path(tmp_path / "home")
        lock_before = lock_path.read_bytes()
        os.kill(second.pid, sig)
        try:
            rc = second.wait(timeout=15)
        except subprocess.TimeoutExpired:
            _stop(second)
            pytest.fail(
                "second launch still alive after %s: %s" % (name, _stderr(second_err)[-800:])
            )
        err = _stderr(second_err)
        assert rc == 0, "rc %s stderr %s" % (rc, err[-800:])
        assert rc not in (-6, 134), "aborted on %s rc %s" % (name, rc)
        assert "Traceback" not in err
        assert "KeyboardInterrupt" not in err
        assert first.poll() is None, _stderr(first_err)
        assert lock_path.is_file()
        assert lock_path.read_bytes() == lock_before
    finally:
        if not first_f.closed:
            first_f.close()
        _stop(first)
        if second is not None:
            _stop(second)
        if second_f is not None and not second_f.closed:
            second_f.close()


def test_already_running_box_stays_up_without_a_signal(tmp_path: Path) -> None:
    """No signal and no click: the second launch is still on the box after 1s.

    The wakeup timer fires every 100 ms. It must not close the box by itself.
    """
    ready = tmp_path / "join-ready"
    shown = tmp_path / "shown"
    first, first_err, first_f = _launch(tmp_path)
    second = None
    second_f = None
    try:
        assert _wait_until(lambda: ready.is_file() or first.poll() is not None, 25), (
            "first app did not listen: rc %s %s" % (first.poll(), _stderr(first_err)[-800:])
        )
        assert first.poll() is None, _stderr(first_err)
        second, second_err, second_f = _launch(tmp_path, shown=shown)
        assert _wait_until(lambda: shown.is_file() or second.poll() is not None, 20), (
            "second launch did not show the box: rc %s %s"
            % (second.poll(), _stderr(second_err)[-800:])
        )
        assert second.poll() is None, _stderr(second_err)
        assert shown.read_text(encoding="utf-8") == ALREADY_RUNNING
        time.sleep(1.2)
        err = _stderr(second_err)
        assert second.poll() is None, "box closed by itself: rc %s %s" % (second.poll(), err[-800:])
        assert shown.read_text(encoding="utf-8") == ALREADY_RUNNING
        assert first.poll() is None, _stderr(first_err)
    finally:
        if not first_f.closed:
            first_f.close()
        _stop(first)
        if second is not None:
            _stop(second)
        if second_f is not None and not second_f.closed:
            second_f.close()
