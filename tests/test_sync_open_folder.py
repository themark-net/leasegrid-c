"""Double-click or Open folder opens a folder's local path."""

from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import patch

import pytest

PyQt5 = pytest.importorskip("PyQt5")

from leasegrid_sync.app import MainWindow, display_path  # noqa: E402
from leasegrid_sync.backend import ConnectionStatus, FolderRow, SyncError  # noqa: E402
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
        assert "That path is not a folder: %s" % display_path(target) in text
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
        assert "That folder is not on this computer any more: %s" % display_path(missing) in text
        assert "\nNext: " in text
        assert_no_raw_user_text(text)
    finally:
        _close(window)


def test_folder_removed_while_syncing_is_missing_until_it_returns(tmp_path: Path) -> None:
    """Deleting the directory is not Idle and not Up to date. Putting it back resumes."""
    window = _window(tmp_path)
    folder = tmp_path / "Docs"
    folder.mkdir()
    (folder / "note.txt").write_text("hello\n", encoding="utf-8")
    window._joined = True

    def listing(path: str):
        if path != "/v1/magic-folder":
            return None
        return {"Docs": {"magic_path": str(folder), "poll_interval": 60}}

    scan_files: list[dict] = []

    def http_get(path, base=None, timeout=10.0):
        found = listing(path)
        if found is not None:
            return found
        if path.endswith("/file-status"):
            return list(scan_files)
        if "recent-changes" in path:
            return []
        return []

    online = ConnectionStatus(
        state="Connected",
        detail="introducer up · 1 storage",
        introducer_ok=True,
        servers_connected=1,
    )

    def refresh() -> None:
        with patch.object(window.tahoe, "connection_status", return_value=online), patch.object(
            window.mf, "ensure_running", return_value=None
        ), patch.object(window.mf, "_http_get", side_effect=http_get):
            window.refresh()

    try:
        refresh()
        assert window.table.item(0, 1).text() == "Syncing"
        shutil.rmtree(folder)
        refresh()
        assert window.table.item(0, 1).text() == "Missing"
        text = window.folder_error.text()
        assert "not on this computer" in text
        assert "\nNext: " in text
        assert_no_raw_user_text(text)
        with patch("PyQt5.QtGui.QDesktopServices.openUrl") as open_url:
            window.table.itemDoubleClicked.emit(window.table.item(0, 0))
        assert open_url.call_count == 0

        scan_files.append({"relpath": "note.txt", "size": 6, "mtime": 1})
        refresh()
        assert window.table.item(0, 1).text() == "Missing"

        folder.mkdir()
        (folder / "note.txt").write_text("hello\n", encoding="utf-8")
        refresh()
        assert window.table.item(0, 1).text() == "Up to date"
        assert "not on this computer" not in window.folder_error.text()
        with patch("PyQt5.QtGui.QDesktopServices.openUrl", return_value=True) as open_url:
            window.table.itemDoubleClicked.emit(window.table.item(0, 0))
        assert Path(open_url.call_args[0][0].toLocalFile()) == folder

        shutil.rmtree(folder)
        refresh()
        assert window.table.item(0, 1).text() == "Missing"
        window.folder_error.setText("Restored 1 folder(s): Docs.")
        folder.mkdir()
        (folder / "note.txt").write_text("hello\n", encoding="utf-8")
        refresh()
        assert window.table.item(0, 1).text() == "Up to date"
        assert window.folder_error.text() == "Restored 1 folder(s): Docs."
    finally:
        _close(window)
