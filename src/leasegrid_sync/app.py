"""Native Leasegrid Sync window (PyQt). Gridsync folder-list mental model.

Leasegrid Sync does not use the Tahoe web UI as the buyer surface.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

from . import APP_NAME
from .backend import (
    FolderRow,
    MagicFolderCtl,
    SyncError,
    TahoeClient,
    default_home,
    write_probe_file,
    wait_for_file_status,
)

THREAT_COPY = (
    "You are joining a paid friendnet you trust — not Dropbox-the-company and not Filecoin.\n"
    "1. Issuer trust — credit is minted by this friendnet's issuer after payment.\n"
    "2. No storage proofs — dead or unpaid nodes are dropped and shares moved, not slashed.\n"
    "3. Tor vs sync — full privacy often wants Tor; folder sync may use LAN/WAN. "
    "Transport policy is a visible setting (U4 polish).\n"
    "4. Recovery — lose the recovery key and this device and access can be gone (U4)."
)


def _qt_api():
    from PyQt5 import QtCore, QtGui, QtWidgets

    return QtCore, QtGui, QtWidgets


class MainWindow:
    """Thin wrapper so tests can construct the window without exec_."""

    def __init__(self, nodedir: Optional[Path] = None, home: Optional[Path] = None) -> None:
        QtCore, QtGui, QtWidgets = _qt_api()
        self.QtCore = QtCore
        self.QtGui = QtGui
        self.QtWidgets = QtWidgets
        self.tahoe = TahoeClient(nodedir=nodedir)
        self.home = Path(home) if home else default_home()
        self.home.mkdir(parents=True, exist_ok=True)
        self.mf = MagicFolderCtl(config_dir=self.home / "magic-folder", nodedir=self.tahoe.nodedir)
        self._joined = False

        self.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
        self.app.setApplicationName(APP_NAME)
        self.app.setQuitOnLastWindowClosed(False)

        self.win = QtWidgets.QMainWindow()
        self.win.setWindowTitle(APP_NAME)
        self.win.resize(920, 620)
        self.win.closeEvent = self._on_close  # type: ignore[method-assign]

        central = QtWidgets.QWidget()
        self.win.setCentralWidget(central)
        self.stack = QtWidgets.QStackedWidget()
        layout = QtWidgets.QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.stack)

        self.join_page = self._build_join_page()
        self.main_page = self._build_main_page()
        self.stack.addWidget(self.join_page)
        self.stack.addWidget(self.main_page)

        self.tray = None
        self._init_tray()

        self.poll = QtCore.QTimer(self.win)
        self.poll.setInterval(3000)
        self.poll.timeout.connect(self.refresh)

        self._try_autoload()

    def _build_join_page(self):
        QtWidgets = self.QtWidgets
        page = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(page)
        v.setContentsMargins(28, 24, 28, 24)
        title = QtWidgets.QLabel("Welcome to %s" % APP_NAME)
        title.setObjectName("joinTitle")
        font = title.font()
        font.setPointSize(16)
        font.setBold(True)
        title.setFont(font)
        v.addWidget(title)
        intro = QtWidgets.QLabel("Sync folders with a paid friendnet you trust.")
        v.addWidget(intro)
        threat = QtWidgets.QLabel(THREAT_COPY)
        threat.setWordWrap(True)
        threat.setObjectName("threatCopy")
        v.addWidget(threat)
        v.addWidget(QtWidgets.QLabel("Invite (introducer furl)"))
        self.invite_edit = QtWidgets.QLineEdit()
        self.invite_edit.setPlaceholderText("paste pb:// introducer furl…")
        self.invite_edit.setObjectName("inviteEdit")
        v.addWidget(self.invite_edit)
        row = QtWidgets.QHBoxLayout()
        self.join_btn = QtWidgets.QPushButton("Join friendnet")
        self.join_btn.setObjectName("joinButton")
        self.join_btn.clicked.connect(self.on_join_invite)
        self.existing_btn = QtWidgets.QPushButton("Use existing Tahoe node")
        self.existing_btn.setObjectName("existingButton")
        self.existing_btn.clicked.connect(self.on_join_existing)
        row.addWidget(self.join_btn)
        row.addWidget(self.existing_btn)
        row.addStretch(1)
        v.addLayout(row)
        self.join_error = QtWidgets.QLabel("")
        self.join_error.setObjectName("joinError")
        self.join_error.setWordWrap(True)
        self.join_error.setStyleSheet("color: #8b1a1a;")
        v.addWidget(self.join_error)
        v.addStretch(1)
        return page

    def _build_main_page(self):
        QtWidgets = self.QtWidgets
        page = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(page)
        v.setContentsMargins(12, 8, 12, 8)
        chrome = QtWidgets.QHBoxLayout()
        self.status_chip = QtWidgets.QLabel("Connecting…")
        self.status_chip.setObjectName("statusChip")
        chrome.addWidget(QtWidgets.QLabel(APP_NAME))
        chrome.addStretch(1)
        chrome.addWidget(self.status_chip)
        v.addLayout(chrome)

        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setObjectName("places")
        self.folders_tab = QtWidgets.QWidget()
        self.settings_tab = QtWidgets.QWidget()
        self.tabs.addTab(self.folders_tab, "Folders")
        self.tabs.addTab(self.settings_tab, "Settings")
        v.addWidget(self.tabs)

        fl = QtWidgets.QVBoxLayout(self.folders_tab)
        head = QtWidgets.QHBoxLayout()
        head.addWidget(QtWidgets.QLabel("Folders"))
        head.addStretch(1)
        self.add_btn = QtWidgets.QPushButton("Add folder")
        self.add_btn.setObjectName("addFolderButton")
        self.add_btn.clicked.connect(self.on_add_folder)
        head.addWidget(self.add_btn)
        fl.addLayout(head)
        self.empty_label = QtWidgets.QLabel(
            "No sync folders yet.\n"
            "Add a local folder to sync encrypted shares to your friendnet "
            "(Dropbox-shaped — not a web file browser)."
        )
        self.empty_label.setWordWrap(True)
        self.empty_label.setObjectName("foldersEmpty")
        fl.addWidget(self.empty_label)
        self.table = QtWidgets.QTableWidget(0, 3)
        self.table.setObjectName("folderTable")
        self.table.setHorizontalHeaderLabels(["Name", "Status", "Local path"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        fl.addWidget(self.table)
        self.folder_error = QtWidgets.QLabel("")
        self.folder_error.setObjectName("folderError")
        self.folder_error.setWordWrap(True)
        self.folder_error.setStyleSheet("color: #8b1a1a;")
        fl.addWidget(self.folder_error)

        sl = QtWidgets.QVBoxLayout(self.settings_tab)
        sl.addWidget(QtWidgets.QLabel("Settings (U1 stub)"))
        note = QtWidgets.QLabel(
            "Transport policy: full privacy claims often want Tor; Magic Folder sync "
            "that feels normal may use LAN/WAN. This is a visible design flag — polish in U4.\n\n"
            "Deferred (not this spike): Credit panel (U2), AppImage/.deb (U3), "
            "recovery-key HITL (U4), XMR top-up (U5)."
        )
        note.setWordWrap(True)
        note.setObjectName("settingsNote")
        sl.addWidget(note)
        sl.addStretch(1)
        return page

    def _init_tray(self) -> None:
        QtWidgets = self.QtWidgets
        QtGui = self.QtGui
        if not QtWidgets.QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray = QtWidgets.QSystemTrayIcon(self.win)
        pix = QtGui.QPixmap(16, 16)
        pix.fill(QtGui.QColor("#1f6feb"))
        self.tray.setIcon(QtGui.QIcon(pix))
        self.tray.setToolTip(APP_NAME)
        menu = QtWidgets.QMenu()
        open_act = menu.addAction("Open Sync")
        open_act.triggered.connect(self.show)
        quit_act = menu.addAction("Quit")
        quit_act.triggered.connect(self.quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()

    def _tray_activated(self, reason) -> None:
        QtWidgets = self.QtWidgets
        if reason in (
            QtWidgets.QSystemTrayIcon.Trigger,
            QtWidgets.QSystemTrayIcon.DoubleClick,
        ):
            self.show()

    def _on_close(self, event) -> None:
        if self.tray is not None and self.tray.isVisible():
            self.win.hide()
            event.ignore()
            return
        event.ignore()
        self.win.showMinimized()

    def show(self) -> None:
        self.win.show()
        self.win.raise_()
        self.win.activateWindow()

    def quit(self) -> None:
        try:
            self.mf.stop()
        except Exception:
            pass
        self.app.quit()

    def show_join_error(self, err: SyncError) -> None:
        self.join_error.setText(err.banner())

    def show_folder_error(self, err: SyncError) -> None:
        self.folder_error.setText(err.banner())

    def clear_errors(self) -> None:
        self.join_error.setText("")
        self.folder_error.setText("")

    def _try_autoload(self) -> None:
        try:
            status = self.tahoe.join_existing()
        except SyncError:
            self.stack.setCurrentWidget(self.join_page)
            return
        self._enter_main(status.state, status.detail)

    def on_join_invite(self) -> None:
        self.clear_errors()
        try:
            status = self.tahoe.join_invite(self.invite_edit.text())
        except SyncError as exc:
            self.show_join_error(exc)
            return
        self._enter_main(status.state, status.detail)

    def on_join_existing(self) -> None:
        self.clear_errors()
        try:
            status = self.tahoe.join_existing()
        except SyncError as exc:
            self.show_join_error(exc)
            return
        self._enter_main(status.state, status.detail)

    def _enter_main(self, state: str, detail: str) -> None:
        self._joined = True
        self.status_chip.setText("%s  %s" % (state, detail))
        self.stack.setCurrentWidget(self.main_page)
        self.poll.start()
        self.refresh()

    def refresh(self) -> None:
        if not self._joined:
            return
        status = self.tahoe.connection_status()
        self.status_chip.setText("%s  %s" % (status.state, status.detail))
        try:
            rows = self.mf.list_folders()
        except SyncError as exc:
            self.show_folder_error(exc)
            return
        self._render_rows(rows)

    def _render_rows(self, rows: list[FolderRow]) -> None:
        self.table.setRowCount(len(rows))
        self.empty_label.setVisible(not rows)
        self.table.setVisible(bool(rows))
        QtWidgets = self.QtWidgets
        for i, row in enumerate(rows):
            self.table.setItem(i, 0, QtWidgets.QTableWidgetItem(row.name))
            self.table.setItem(i, 1, QtWidgets.QTableWidgetItem(row.status))
            self.table.setItem(i, 2, QtWidgets.QTableWidgetItem(row.path))

    def on_add_folder(self) -> None:
        QtWidgets = self.QtWidgets
        self.clear_errors()
        path = QtWidgets.QFileDialog.getExistingDirectory(
            self.win, "Choose a local folder to sync", str(Path.home())
        )
        if not path:
            return
        try:
            name = self.mf.add_folder(path)
        except SyncError as exc:
            self.show_folder_error(exc)
            return
        self.refresh()
        self.folder_error.setText("Added folder %s" % name)

    def grab_to(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        pix = self.win.grab()
        pix.save(str(path))

    def dogfood_one_folder(self, folder: Path, screenshot: Optional[Path] = None) -> dict:
        """Join existing friendnet, add one Magic Folder, write a file, wait for status."""
        self.clear_errors()
        status = self.tahoe.join_existing()
        self._enter_main(status.state, status.detail)
        folder.mkdir(parents=True, exist_ok=True)
        name = self.mf.add_folder(str(folder), name="u1-dogfood")
        probe = write_probe_file(folder)
        self.mf.scan_local(name)
        seen = wait_for_file_status(self.mf, name, probe.name)
        self.refresh()
        if screenshot:
            self.grab_to(screenshot)
        return {
            "folder": str(folder),
            "name": name,
            "probe": str(probe),
            "status": seen,
            "grid": status.detail,
        }


def run_app(
    nodedir: Optional[Path] = None,
    screenshot: Optional[Path] = None,
    dogfood_folder: Optional[Path] = None,
) -> int:
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    ui = MainWindow(nodedir=nodedir)
    ui.show()
    if dogfood_folder is not None:
        try:
            result = ui.dogfood_one_folder(dogfood_folder, screenshot=screenshot)
        except SyncError as exc:
            ui.show_folder_error(exc)
            if screenshot:
                ui.grab_to(screenshot)
            print(exc.banner(), file=sys.stderr)
            return 1
        print("U1 dogfood folder=%s probe=%s status=%s" % (
            result["folder"], result["probe"], result["status"]
        ))
        return 0
    if screenshot:
        ui.QtCore.QTimer.singleShot(400, lambda: ui.grab_to(screenshot))
        ui.QtCore.QTimer.singleShot(800, ui.app.quit)
    return ui.app.exec_()
