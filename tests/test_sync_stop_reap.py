"""stop() must reap a child that ignores SIGTERM, and a second stop is a no-op."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from leasegrid_sync.backend import MagicFolderCtl, TahoeClient


def _child_ignoring_sigterm() -> subprocess.Popen:
    proc = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import signal, sys, time\n"
            "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
            "sys.stdout.write('ready\\n')\n"
            "sys.stdout.flush()\n"
            "time.sleep(60)\n",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    ready = proc.stdout.readline() if proc.stdout is not None else b""
    if ready.strip() != b"ready":
        proc.kill()
        raise AssertionError("child did not install the SIGTERM ignore: %r" % ready)
    return proc


def _is_zombie(pid: int) -> bool:
    try:
        text = Path("/proc/%d/stat" % pid).read_text(encoding="utf-8")
    except OSError:
        return False
    tail = text.rsplit(")", 1)[-1].split()
    return bool(tail) and tail[0] == "Z"


def _ctl(kind: str, tmp_path: Path):
    if kind == "tahoe":
        return TahoeClient(nodedir=tmp_path / "node", home=tmp_path / "home")
    return MagicFolderCtl(config_dir=tmp_path / "mf", nodedir=tmp_path / "node")


@pytest.mark.skipif(sys.platform == "win32", reason="SIGTERM cannot be ignored on Windows")
@pytest.mark.parametrize("kind", ["tahoe", "magic-folder"])
def test_stop_reaps_child_that_ignores_sigterm(tmp_path: Path, kind: str) -> None:
    proc = _child_ignoring_sigterm()
    pid = proc.pid
    ctl = _ctl(kind, tmp_path)
    ctl._proc = proc
    try:
        ctl.stop(terminate_timeout=0.3)
        assert proc.poll() is not None
        assert not _is_zombie(pid)
        ctl.stop()
        assert proc.poll() is not None
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=2)


def test_quit_stops_tahoe_and_magic_folder(tmp_path: Path) -> None:
    """The window quit path must stop both daemons, not only call shutdown."""
    pytest.importorskip("PyQt5")
    from leasegrid_sync.app import MainWindow

    window = MainWindow(home=tmp_path / "home", nodedir=tmp_path / "tahoe", autoload=False)
    procs: list[subprocess.Popen] = []
    try:
        for ctl in (window.tahoe, window.mf):
            proc = subprocess.Popen(
                [sys.executable, "-c", "import time; time.sleep(60)"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            ctl._proc = proc
            procs.append(proc)
        window.quit()
        for proc in procs:
            assert proc.poll() is not None
    finally:
        for proc in procs:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=5)
        window.poll.stop()
        window.win.hide()
        if window.tray is not None:
            window.tray.hide()


def test_stop_is_safe_when_the_child_already_exited(tmp_path: Path) -> None:
    proc = subprocess.Popen([sys.executable, "-c", "import sys; sys.exit(0)"])
    proc.wait(timeout=5)
    ctl = TahoeClient(nodedir=tmp_path / "node", home=tmp_path / "home")
    ctl._proc = proc
    ctl.stop(terminate_timeout=0.3)
    ctl.stop()
    assert proc.poll() is not None
    bare = MagicFolderCtl(config_dir=tmp_path / "mf", nodedir=tmp_path / "node")
    bare.stop()
    bare.stop()
