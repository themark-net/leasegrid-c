"""pyproject.toml project.version must match what the buyer can see.

That is leasegrid_sync.__version__, `leasegrid-sync --version`, and the
More → Settings About line.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _pyproject_version() -> str:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    if sys.version_info >= (3, 11):
        import tomllib

        data = tomllib.loads(text)
    else:
        tomli = pytest.importorskip("tomli")
        data = tomli.loads(text)
    return data["project"]["version"]


def test_pyproject_version_matches_leasegrid_sync():
    from leasegrid_sync import __version__

    assert _pyproject_version() == __version__


def _run_module_version(module: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run(
        [sys.executable, "-m", module, "--version"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_cli_version_matches_pyproject():
    """Real entries: `python -m leasegrid_sync.cli` and `python -m leasegrid_sync`."""
    from leasegrid_sync import APP_NAME

    expected = "%s %s" % (APP_NAME, _pyproject_version())
    for module in ("leasegrid_sync.cli", "leasegrid_sync"):
        proc = _run_module_version(module)
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.strip() == expected


def test_about_line_matches_pyproject():
    from leasegrid_sync import APP_NAME
    from leasegrid_sync.app import about_line

    expected = "%s (buyer) · version %s" % (APP_NAME, _pyproject_version())
    assert about_line() == expected


def test_settings_note_shows_about_line(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """The More → Settings label. Skips when PyQt5 is not installed."""
    pytest.importorskip("PyQt5")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    for key in ("LEASEGRID_SYNC_HOME", "LEASEGRID_TAHOE_NODEDIR", "LEASEGRID_WALLET"):
        monkeypatch.delenv(key, raising=False)
    from leasegrid_sync import APP_NAME
    from leasegrid_sync.app import MainWindow, about_line

    home = tmp_path / "sync-home"
    nodedir = tmp_path / "tahoe"
    window = MainWindow(nodedir=nodedir, home=home, autoload=False)
    try:
        note = window.settings_tab.findChild(window.QtWidgets.QLabel, "settingsNote")
        assert note is not None
        expected = "%s (buyer) · version %s" % (APP_NAME, _pyproject_version())
        assert about_line() in note.text()
        assert expected in note.text()
    finally:
        window.poll.stop()
        window.win.hide()
        if window.tray is not None:
            window.tray.hide()
