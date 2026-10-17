"""Double-click or Open folder opens a folder's local path."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

PyQt5 = pytest.importorskip("PyQt5")

from leasegrid_sync.app import MainWindow  # noqa: E402
from leasegrid_sync.backend import FolderRow, SyncError  # noqa: E402
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


def _row_pos(window: MainWindow):
    window.win.show()
    window.QtWidgets.QApplication.processEvents()
    window.table.setRowHeight(0, 24)
    rect = window.table.visualRect(window.table.model().index(0, 0))
    return rect.center()


def test_double_click_opens_an_existing_folder(tmp_path: Path) -> None:
    window = _window(tmp_path)
    folder = tmp_path / "docs"
    folder.mkdir()
    window._render_rows([FolderRow(name="Docs", path=str(folder), status="Up to date")])
    item = window.table.item(0, 0)
    try:
        with patch("PyQt5.QtGui.QDesktopServices.openUrl", return_value=True) as open_url:
            window.table.itemDoubleClicked.emit(item)
        url = open_url.call_args[0][0]
        assert Path(url.toLocalFile()) == folder
    finally:
        _close(window)


def test_context_menu_open_folder_uses_the_same_path(tmp_path: Path) -> None:
    window = _window(tmp_path)
    folder = tmp_path / "docs"
    folder.mkdir()
    window._render_rows([FolderRow(name="Docs", path=str(folder), status="Up to date")])

    def choose_open(menu, *_args, **_kwargs):
        for action in menu.actions():
            if action.text() == "Open folder":
                return action
        raise AssertionError("Open folder missing")

    try:
        with patch("PyQt5.QtGui.QDesktopServices.openUrl", return_value=True) as open_url, patch.object(
            window.QtWidgets.QMenu, "exec_", choose_open
        ):
            window.on_folder_context_menu(_row_pos(window))
        url = open_url.call_args[0][0]
        assert Path(url.toLocalFile()) == folder
    finally:
        _close(window)


def test_a_file_path_never_reaches_open_url(tmp_path: Path) -> None:
    window = _window(tmp_path)
    target = tmp_path / "notes.txt"
    target.write_text("hello", encoding="utf-8")
    target.chmod(0o755)
    window._render_rows([FolderRow(name="Notes", path=str(target), status="Up to date")])
    try:
        with patch("PyQt5.QtGui.QDesktopServices.openUrl") as open_url:
            window.table.itemDoubleClicked.emit(window.table.item(0, 0))
        assert open_url.call_count == 0
        text = window.folder_error.text()
        assert "That path is not a folder: %s" % target in text
        assert "\nNext: " in text
        assert_no_raw_user_text(text)
    finally:
        _close(window)


def test_missing_folder_shows_a_banner_and_does_not_crash(tmp_path: Path) -> None:
    window = _window(tmp_path)
    missing = tmp_path / "gone"
    window._render_rows([FolderRow(name="Gone", path=str(missing), status="Error")])
    try:
        with patch("PyQt5.QtGui.QDesktopServices.openUrl") as open_url:
            window.table.itemDoubleClicked.emit(window.table.item(0, 0))
        assert open_url.call_count == 0
        text = window.folder_error.text()
        assert "That folder is not on this computer any more: %s" % missing in text
        assert "\nNext: " in text
        assert_no_raw_user_text(text)
    finally:
        _close(window)
