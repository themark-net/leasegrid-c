"""A quit signal in the first moment of startup exits 0 and drops the lock.

The window handler is installed only when the Qt loop is about to start.
Until then a SIGTERM used to kill the process and leave the home lock.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from leasegrid_sync.app import instance_lock_path

_HOOKED_MAIN = """\
import sys
import leasegrid_sync.app as appmod
appmod._TEST_HOOKS = True
from leasegrid_sync.cli import main
rc = main(sys.argv[1:])
raise SystemExit(0 if rc is None else int(rc))
"""


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="Windows SIGTERM is TerminateProcess and cannot run a handler",
)
def test_signal_during_early_startup_exits_0_and_drops_the_lock(tmp_path: Path) -> None:
    """SIGTERM while the lock is held and the window is not up yet.

    Fails when the process dies from the signal (return code is not 0) or
    when the lock file is still there. Recovers by exiting 0, removing the
    lock, and never reaching the Qt-loop signal handler.
    """
    home = tmp_path / "home"
    nodedir = tmp_path / "tahoe"
    home.mkdir()
    nodedir.mkdir()
    pause = tmp_path / "pause"
    ready = tmp_path / "signal-ready"
    err_path = tmp_path / "app.err"
    driver = tmp_path / "hooked_main.py"
    driver.write_text(_HOOKED_MAIN, encoding="utf-8")
    env = os.environ.copy()
    env["LEASEGRID_SYNC_HOME"] = str(home)
    env["LEASEGRID_TAHOE_NODEDIR"] = str(nodedir)
    env["LEASEGRID_TEST_EARLY_PAUSE"] = str(pause)
    env["LEASEGRID_TEST_SIGNAL_READY"] = str(ready)
    env["QT_QPA_PLATFORM"] = "offscreen"
    err_f = err_path.open("w", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, str(driver), "--offscreen", "--nodedir", str(nodedir)],
        stdout=subprocess.DEVNULL,
        stderr=err_f,
        env=env,
        start_new_session=True,
    )
    try:
        deadline = time.time() + 20
        while time.time() < deadline and not pause.is_file() and proc.poll() is None:
            time.sleep(0.05)
        assert pause.is_file() and proc.poll() is None, err_path.read_text(encoding="utf-8")
        os.kill(proc.pid, signal.SIGTERM)
        deadline = time.time() + 5
        while time.time() < deadline and proc.poll() is None:
            time.sleep(0.05)
        err = err_path.read_text(encoding="utf-8")
        assert proc.poll() is not None, "still running after SIGTERM: %s" % err
        assert proc.returncode == 0, "exit %s: %s" % (proc.returncode, err)
        assert not instance_lock_path(home).exists()
        assert not ready.is_file()
    finally:
        err_f.close()
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)
