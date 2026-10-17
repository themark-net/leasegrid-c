"""More → Settings: open the logs folder."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

PyQt5 = pytest.importorskip("PyQt5")

from leasegrid_sync.app import MainWindow  # noqa: E402
from leasegrid_sync.backend import SyncError  # noqa: E402
from tests.buyer_text import assert_no_raw_user_text  # noqa: E402


def _window(tmp_path: Path) -> MainWindow:
    home = tmp_path / "home"
    nodedir = tmp_path / "tahoe"
    nodedir.mkdir()
    (nodedir / "tahoe.cfg").write_text("[node]\n", encoding="utf-8")
    with patch(
        "leasegrid_sync.app.TahoeClient.join_existing",
        side_effect=SyncError("could not join this friendnet. No Tahoe.", "Retry."),
    ):
        return MainWindow(nodedir=nodedir, home=home)


def _close(window: MainWindow) -> None:
    window.poll.stop()
    window.win.hide()
    if window.tray is not None:
        window.tray.hide()


def test_open_logs_button_opens_the_real_logs_directory(tmp_path: Path) -> None:
    window = _window(tmp_path)
    button = window.settings_tab.findChild(window.QtWidgets.QPushButton, "openLogsButton")
    assert button is not None
    assert button.text() == "Open logs folder"
    try:
        with patch("PyQt5.QtGui.QDesktopServices.openUrl", return_value=True) as open_url:
            button.click()
        logs = window.home / "logs"
        assert logs.is_dir()
        url = open_url.call_args[0][0]
        assert Path(url.toLocalFile()) == logs
    finally:
        _close(window)


def test_open_logs_failure_shows_the_path_without_exception_text(tmp_path: Path) -> None:
    window = _window(tmp_path)
    button = window.open_logs_btn
    try:
        with patch("PyQt5.QtGui.QDesktopServices.openUrl", return_value=False):
            button.click()
        text = window.settings_status.text()
        assert str(window.home / "logs") in text
        assert_no_raw_user_text(text)
        assert (window.home / "logs").is_dir()
    finally:
        _close(window)
