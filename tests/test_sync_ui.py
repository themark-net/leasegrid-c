"""Offscreen Qt smoke: window title, join FAIL in-window, no WUI CTA."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PyQt5 = pytest.importorskip("PyQt5")

from leasegrid_sync import APP_NAME  # noqa: E402
from leasegrid_sync.app import MainWindow  # noqa: E402
from leasegrid_sync.backend import ConnectionStatus, SyncError  # noqa: E402


@pytest.fixture
def ui(tmp_path: Path):
    home = tmp_path / "sync-home"
    nodedir = tmp_path / "tahoe"
    nodedir.mkdir()
    (nodedir / "tahoe.cfg").write_text("[node]\n", encoding="utf-8")
    with patch(
        "leasegrid_sync.app.TahoeClient.join_existing",
        side_effect=SyncError("could not join this friendnet. No Tahoe.", "Retry."),
    ):
        window = MainWindow(nodedir=nodedir, home=home)
    yield window
    window.poll.stop()
    window.win.hide()
    if window.tray is not None:
        window.tray.hide()


def test_window_title_is_leasegrid_sync(ui: MainWindow):
    assert ui.win.windowTitle() == APP_NAME
    assert "Leasegrid Sync" in ui.win.windowTitle()


def test_join_failure_is_in_window_not_silent(ui: MainWindow):
    ui.invite_edit.setText("nope")
    ui.on_join_invite()
    text = ui.join_error.text()
    assert text
    assert "FAIL" in text
    assert "web UI" not in text.lower() or "does not use the Tahoe web UI" in text


def test_empty_invite_fail(ui: MainWindow):
    ui.invite_edit.setText("")
    ui.on_join_invite()
    assert "FAIL" in ui.join_error.text()


def test_no_wui_cta_widgets(ui: MainWindow):
    labels = ui.win.findChildren(PyQt5.QtWidgets.QLabel)
    buttons = ui.win.findChildren(PyQt5.QtWidgets.QPushButton)
    blob = " ".join(w.text() for w in list(labels) + list(buttons))
    for needle in ("Open web UI", "Open Tahoe WUI", "use the web UI"):
        assert needle.lower() not in blob.lower()
    assert "Join friendnet" in blob
    assert "Add folder" in blob


def test_add_folder_failure_in_window(ui: MainWindow, tmp_path: Path):
    ui._enter_main("Connected", "lab")
    with patch(
        "leasegrid_sync.app.MagicFolderCtl.add_folder",
        side_effect=SyncError("folder not added. Path unreadable.", "fix path; Retry."),
    ):
        with patch.object(
            ui.QtWidgets.QFileDialog, "getExistingDirectory", return_value=str(tmp_path)
        ):
            ui.on_add_folder()
    assert "FAIL" in ui.folder_error.text()
    assert "folder not added" in ui.folder_error.text()


def test_enter_main_shows_folders_tab(ui: MainWindow):
    st = ConnectionStatus(state="Connected", detail="introducer up", introducer_ok=True)
    with patch.object(ui.tahoe, "connection_status", return_value=st):
        with patch.object(ui.mf, "list_folders", return_value=[]):
            ui._enter_main("Connected", "introducer up")
    assert ui.stack.currentWidget() is ui.main_page
    assert ui.tabs.tabText(0) == "Folders"
    assert ui.status_chip.text().startswith("Connected")


def test_settings_stub_names_deferred_slices(ui: MainWindow):
    note = ui.settings_tab.findChild(PyQt5.QtWidgets.QLabel, "settingsNote")
    text = note.text() if note is not None else ""
    assert "U2" in text and "U3" in text and "U4" in text and "U5" in text


def test_connected_autoload_skips_join(tmp_path: Path):
    home = tmp_path / "home"
    nodedir = tmp_path / "tahoe"
    nodedir.mkdir()
    (nodedir / "tahoe.cfg").write_text("[node]\n", encoding="utf-8")
    st = ConnectionStatus(state="Connected", detail="lab", introducer_ok=True)
    with patch("leasegrid_sync.app.TahoeClient.join_existing", return_value=st):
        with patch("leasegrid_sync.app.MagicFolderCtl.list_folders", return_value=[]):
            window = MainWindow(nodedir=nodedir, home=home)
    try:
        assert window.stack.currentWidget() is window.main_page
        assert window.win.windowTitle() == APP_NAME
    finally:
        window.poll.stop()
        window.win.hide()
        if window.tray is not None:
            window.tray.hide()
