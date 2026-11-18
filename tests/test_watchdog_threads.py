"""The per-test timeout must not run a Python thread next to Qt tests (#90).

pytest-timeout's thread method (the only one on Windows) starts a Python
timer thread for every test. A garbage collection that runs in that thread
can free Qt wrappers left by an earlier test off the GUI thread. Windows CI
44253243874 died with an access violation inside QApplication.processEvents
while that thread was alive. The watchdog must time out a hung test without
any extra Python thread.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

if not os.environ.get("CI"):
    pytest.importorskip("pytest_timeout")

PROBE = (
    "import threading, time\n\n"
    "def test_probe():\n"
    "    print('THREADS=%d' % threading.active_count())\n\n"
    "def test_hangs():\n"
    "    time.sleep(60)\n"
)


def _run(tmp_path: Path, mode: str):
    (tmp_path / "test_probe.py").write_text(PROBE, encoding="utf-8")
    env = os.environ.copy()
    env["LEASEGRID_TEST_WATCHDOG"] = mode
    env["PYTHONPATH"] = os.pathsep.join([str(ROOT), env.get("PYTHONPATH", "")])
    started = time.monotonic()
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-s", "-p", "no:cacheprovider",
         "-p", "tests._watchdog", "-o", "timeout=3", "-o", "timeout_method=thread",
         str(tmp_path / "test_probe.py")],
        cwd=tmp_path, capture_output=True, text=True, timeout=90, env=env, check=False,
    )
    return proc, time.monotonic() - started


def test_watchdog_runs_no_python_thread_and_still_stops_a_hang(tmp_path: Path):
    proc, took = _run(tmp_path, "faulthandler")
    out = proc.stdout + proc.stderr
    assert "THREADS=1" in out, out
    assert proc.returncode != 0, out
    assert "test_hangs" in out or "time.sleep" in out, out
    assert took < 60, "hung test ran %.0fs" % took
