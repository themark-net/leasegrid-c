"""Native Leasegrid Sync window (PyQt). Gridsync folder-list mental model.

Leasegrid Sync does not use the Tahoe web UI as the buyer surface.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Optional

from . import APP_NAME, __version__
from .backend import (
    FolderRow,
    MagicFolderCtl,
    SyncError,
    TahoeClient,
    default_home,
    write_probe_file,
    wait_for_file_status,
)
from .credit import (
    DENOMINATION_NOTE,
    EXPAND_FACTOR,
    LAB_NOTE,
    REVIEW_HEAD,
    TIER_TOKENS,
    XMR_LATER,
    ZERO_FOLDER_MSG,
    ZERO_FOLDER_NEXT,
    CreditCtl,
    CreditSnapshot,
    credit_gate,
    format_remaining,
)
from .recovery import (
    ACK_LOSS,
    ACK_STORE,
    EXPORT_STOP,
    EXPORT_WARN,
    NO_PASSPHRASE_NOTE,
    RECOVERY_INTRO,
    RECOVERY_SUFFIX,
    SCARY_LOSS,
    RecoveryCtl,
    RestoreResult,
)

THREAT_COPY = (
    "You are joining a paid friendnet you trust — not Dropbox-the-company and not Filecoin.\n"
    "1. Issuer trust — credit is minted by this friendnet's issuer after payment.\n"
    "2. No storage proofs — dead or unpaid nodes are dropped and shares moved, not slashed.\n"
    "3. Tor vs sync — full privacy often wants Tor; folder sync may use LAN/WAN. "
    "Transport policy is a visible setting.\n"
    "4. Recovery — lose the recovery key and this device and access can be gone forever. "
    "Export one from the Recovery place after you join."
)


def _qt_api():
    from PyQt5 import QtCore, QtGui, QtWidgets

    return QtCore, QtGui, QtWidgets


class TopUpDialog:
    """Lab faucet stub. No XMR pay fields. Redeem or in-window FAIL."""

    def __init__(self, parent, credit: CreditCtl, qt) -> None:
        QtWidgets = qt
        self.QtWidgets = QtWidgets
        self.credit = credit
        self.snapshot: Optional[CreditSnapshot] = None
        self.dlg = QtWidgets.QDialog(parent)
        self.dlg.setWindowTitle("Top up")
        self.dlg.setObjectName("topUpDialog")
        self.dlg.setModal(True)
        v = QtWidgets.QVBoxLayout(self.dlg)
        title = QtWidgets.QLabel("Lab faucet (stub)")
        font = title.font()
        font.setBold(True)
        title.setFont(font)
        v.addWidget(title)
        intro = QtWidgets.QLabel("Request prepaid credit for this friendnet.")
        intro.setWordWrap(True)
        v.addWidget(intro)
        v.addWidget(QtWidgets.QLabel("Amount"))
        self.amount_group = QtWidgets.QButtonGroup(self.dlg)
        self.radios = {}
        labels = {
            "small": "Small (≈ %d GiB·mo)" % TIER_TOKENS["small"],
            "medium": "Medium (≈ %d)" % TIER_TOKENS["medium"],
            "large": "Large (≈ %d GiB·mo)" % TIER_TOKENS["large"],
        }
        for key, label in labels.items():
            radio = QtWidgets.QRadioButton(label)
            radio.setObjectName("tier_%s" % key)
            self.amount_group.addButton(radio)
            self.radios[key] = radio
            v.addWidget(radio)
        self.radios["medium"].setChecked(True)
        xmr = QtWidgets.QLabel(XMR_LATER)
        xmr.setWordWrap(True)
        xmr.setObjectName("xmrLaterLabel")
        v.addWidget(xmr)
        self.status = QtWidgets.QLabel("")
        self.status.setObjectName("topUpStatus")
        self.status.setWordWrap(True)
        v.addWidget(self.status)
        row = QtWidgets.QHBoxLayout()
        self.request_btn = QtWidgets.QPushButton("Request faucet credit")
        self.request_btn.setObjectName("requestFaucetButton")
        self.request_btn.clicked.connect(self.on_request)
        self.cancel_btn = QtWidgets.QPushButton("Cancel")
        self.cancel_btn.setObjectName("topUpCancel")
        self.cancel_btn.clicked.connect(self.dlg.reject)
        row.addWidget(self.request_btn)
        row.addWidget(self.cancel_btn)
        row.addStretch(1)
        v.addLayout(row)

    def _selected_tier(self) -> str:
        for key, radio in self.radios.items():
            if radio.isChecked():
                return key
        return "medium"

    def on_request(self) -> None:
        self.status.setStyleSheet("")
        self.status.setText("Requesting credit from faucet…")
        self.request_btn.setEnabled(False)
        self.QtWidgets.QApplication.processEvents()
        try:
            self.snapshot = self.credit.redeem_faucet(self._selected_tier())
        except SyncError as exc:
            self.status.setStyleSheet("color: #8b1a1a;")
            self.status.setText(exc.banner())
            self.request_btn.setText("Retry")
            self.request_btn.setEnabled(True)
            self.cancel_btn.setText("Close")
            return
        self.dlg.accept()


class ExportRecoveryDialog:
    """Wireframe 4b: scary gate, two ACKs, optional passphrase, path, write."""

    def __init__(self, parent, recovery: RecoveryCtl, qt, default_dir: Optional[Path] = None) -> None:
        QtWidgets = qt
        self.QtWidgets = QtWidgets
        self.recovery = recovery
        self.written: Optional[Path] = None
        self.dlg = QtWidgets.QDialog(parent)
        self.dlg.setWindowTitle("Export recovery key")
        self.dlg.setObjectName("exportRecoveryDialog")
        self.dlg.setModal(True)
        v = QtWidgets.QVBoxLayout(self.dlg)
        stop = QtWidgets.QLabel(EXPORT_STOP)
        font = stop.font()
        font.setBold(True)
        stop.setFont(font)
        v.addWidget(stop)
        warn = QtWidgets.QLabel(EXPORT_WARN)
        warn.setWordWrap(True)
        warn.setObjectName("exportWarn")
        v.addWidget(warn)
        self.ack_loss = QtWidgets.QCheckBox(ACK_LOSS)
        self.ack_loss.setObjectName("ackLoss")
        self.ack_store = QtWidgets.QCheckBox(ACK_STORE)
        self.ack_store.setObjectName("ackStore")
        v.addWidget(self.ack_loss)
        v.addWidget(self.ack_store)
        v.addWidget(QtWidgets.QLabel("Passphrase (recommended)"))
        row = QtWidgets.QHBoxLayout()
        self.pass_edit = QtWidgets.QLineEdit()
        self.pass_edit.setEchoMode(QtWidgets.QLineEdit.Password)
        self.pass_edit.setObjectName("passEdit")
        self.confirm_edit = QtWidgets.QLineEdit()
        self.confirm_edit.setEchoMode(QtWidgets.QLineEdit.Password)
        self.confirm_edit.setPlaceholderText("confirm")
        self.confirm_edit.setObjectName("confirmEdit")
        row.addWidget(self.pass_edit)
        row.addWidget(self.confirm_edit)
        v.addLayout(row)
        self.pass_note = QtWidgets.QLabel(NO_PASSPHRASE_NOTE)
        self.pass_note.setWordWrap(True)
        self.pass_note.setObjectName("passNote")
        v.addWidget(self.pass_note)
        v.addWidget(QtWidgets.QLabel("Save to"))
        prow = QtWidgets.QHBoxLayout()
        self.path_edit = QtWidgets.QLineEdit()
        self.path_edit.setObjectName("pathEdit")
        base = Path(default_dir) if default_dir else Path.home()
        self.path_edit.setText(str(base / ("leasegrid-recovery" + RECOVERY_SUFFIX)))
        browse = QtWidgets.QPushButton("Browse…")
        browse.setObjectName("browseButton")
        browse.clicked.connect(self.on_browse)
        prow.addWidget(self.path_edit)
        prow.addWidget(browse)
        v.addLayout(prow)
        self.status = QtWidgets.QLabel("")
        self.status.setObjectName("exportStatus")
        self.status.setWordWrap(True)
        v.addWidget(self.status)
        brow = QtWidgets.QHBoxLayout()
        self.write_btn = QtWidgets.QPushButton("Write recovery key")
        self.write_btn.setObjectName("writeButton")
        self.write_btn.setEnabled(False)
        self.write_btn.clicked.connect(self.on_write)
        cancel = QtWidgets.QPushButton("Cancel")
        cancel.setObjectName("exportCancel")
        cancel.clicked.connect(self.dlg.reject)
        brow.addWidget(self.write_btn)
        brow.addWidget(cancel)
        brow.addStretch(1)
        v.addLayout(brow)
        for w in (self.ack_loss, self.ack_store):
            w.toggled.connect(self._update_gate)
        for w in (self.pass_edit, self.confirm_edit, self.path_edit):
            w.textChanged.connect(self._update_gate)
        self._update_gate()

    def _update_gate(self, *_args) -> None:
        ok = self.ack_loss.isChecked() and self.ack_store.isChecked()
        ok = ok and bool(self.path_edit.text().strip())
        ok = ok and self.pass_edit.text() == self.confirm_edit.text()
        self.write_btn.setEnabled(ok)
        self.pass_note.setVisible(not self.pass_edit.text())

    def on_browse(self) -> None:
        path, _ = self.QtWidgets.QFileDialog.getSaveFileName(
            self.dlg,
            "Save recovery key",
            self.path_edit.text(),
            "Leasegrid recovery key (*%s)" % RECOVERY_SUFFIX,
        )
        if path:
            if not path.endswith(RECOVERY_SUFFIX):
                path += RECOVERY_SUFFIX
            self.path_edit.setText(path)

    def on_write(self) -> None:
        self.status.setStyleSheet("")
        self.status.setText("Writing recovery key…")
        self.write_btn.setEnabled(False)
        self.QtWidgets.QApplication.processEvents()
        path = Path(self.path_edit.text().strip()).expanduser()
        try:
            self.recovery.export(path, self.pass_edit.text())
        except SyncError as exc:
            self.status.setStyleSheet("color: #8b1a1a;")
            self.status.setText(exc.banner())
            self.write_btn.setText("Retry export")
            self.write_btn.setEnabled(True)
            return
        self.written = path
        self.dlg.accept()


class ImportRecoveryDialog:
    """Wireframe 4e: pick file, passphrase, restore with progress + in-window FAIL."""

    def __init__(self, parent, recovery: RecoveryCtl, qt, path: Optional[Path] = None) -> None:
        QtWidgets = qt
        self.QtWidgets = QtWidgets
        self.recovery = recovery
        self.result: Optional[RestoreResult] = None
        self.dlg = QtWidgets.QDialog(parent)
        self.dlg.setWindowTitle("Import recovery key")
        self.dlg.setObjectName("importRecoveryDialog")
        self.dlg.setModal(True)
        v = QtWidgets.QVBoxLayout(self.dlg)
        intro = QtWidgets.QLabel(
            "Restores your folders on this device. This device joins each folder as a new "
            "participant; files download from the friendnet into ~/Leasegrid/<folder>."
        )
        intro.setWordWrap(True)
        v.addWidget(intro)
        v.addWidget(QtWidgets.QLabel("Recovery key file"))
        prow = QtWidgets.QHBoxLayout()
        self.path_edit = QtWidgets.QLineEdit(str(path) if path else "")
        self.path_edit.setObjectName("importPathEdit")
        browse = QtWidgets.QPushButton("Browse…")
        browse.setObjectName("importBrowseButton")
        browse.clicked.connect(self.on_browse)
        prow.addWidget(self.path_edit)
        prow.addWidget(browse)
        v.addLayout(prow)
        v.addWidget(QtWidgets.QLabel("Passphrase (leave empty if none was set)"))
        self.pass_edit = QtWidgets.QLineEdit()
        self.pass_edit.setEchoMode(QtWidgets.QLineEdit.Password)
        self.pass_edit.setObjectName("importPassEdit")
        v.addWidget(self.pass_edit)
        self.status = QtWidgets.QLabel("")
        self.status.setObjectName("importStatus")
        self.status.setWordWrap(True)
        v.addWidget(self.status)
        brow = QtWidgets.QHBoxLayout()
        self.import_btn = QtWidgets.QPushButton("Import recovery key")
        self.import_btn.setObjectName("importButton")
        self.import_btn.clicked.connect(self.on_import)
        cancel = QtWidgets.QPushButton("Cancel")
        cancel.setObjectName("importCancel")
        cancel.clicked.connect(self.dlg.reject)
        brow.addWidget(self.import_btn)
        brow.addWidget(cancel)
        brow.addStretch(1)
        v.addLayout(brow)

    def on_browse(self) -> None:
        path, _ = self.QtWidgets.QFileDialog.getOpenFileName(
            self.dlg,
            "Open recovery key",
            str(Path.home()),
            "Leasegrid recovery key (*%s);;All files (*)" % RECOVERY_SUFFIX,
        )
        if path:
            self.path_edit.setText(path)

    def _progress(self, text: str) -> None:
        self.status.setStyleSheet("")
        self.status.setText(text)
        self.QtWidgets.QApplication.processEvents()

    def on_import(self) -> None:
        path = Path(self.path_edit.text().strip()).expanduser()
        if not path.is_file():
            self.status.setStyleSheet("color: #8b1a1a;")
            self.status.setText(
                SyncError(
                    "could not import this recovery key. File not found.",
                    "pick the file from your backup; Retry.",
                ).banner()
            )
            return
        self.import_btn.setEnabled(False)
        self._progress("Importing recovery key…")
        try:
            self.result = self.recovery.restore(path, self.pass_edit.text(), progress=self._progress)
        except SyncError as exc:
            self.status.setStyleSheet("color: #8b1a1a;")
            self.status.setText(exc.banner())
            self.import_btn.setText("Retry import")
            self.import_btn.setEnabled(True)
            return
        self.dlg.accept()


class MainWindow:
    """Thin wrapper so tests can construct the window without exec_."""

    def __init__(
        self,
        nodedir: Optional[Path] = None,
        home: Optional[Path] = None,
        issuer_url: Optional[str] = None,
        credit: Optional[CreditCtl] = None,
        autoload: bool = True,
    ) -> None:
        QtCore, QtGui, QtWidgets = _qt_api()
        self.QtCore = QtCore
        self.QtGui = QtGui
        self.QtWidgets = QtWidgets
        self.home = Path(home) if home else default_home()
        self.home.mkdir(parents=True, exist_ok=True)
        self.tahoe = TahoeClient(nodedir=nodedir, home=self.home)
        self.mf = MagicFolderCtl(config_dir=self.home / "magic-folder", nodedir=self.tahoe.nodedir)
        self.credit = credit or CreditCtl(home=self.home, issuer_url=issuer_url)
        self.recovery = RecoveryCtl(self.home, self.tahoe, self.mf, self.credit)
        self._joined = False
        self._credit_loaded = False

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

        if autoload:
            self._try_autoload()
        else:
            self.stack.setCurrentWidget(self.join_page)

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
        self.invite_edit.returnPressed.connect(self.on_join_invite)
        v.addWidget(self.invite_edit)
        hint = QtWidgets.QLabel(
            "Joining creates a Tahoe client for this friendnet on this device and keeps it "
            "running while Sync is open. Nothing is uploaded until you add a folder."
        )
        hint.setWordWrap(True)
        hint.setObjectName("joinHint")
        v.addWidget(hint)
        row = QtWidgets.QHBoxLayout()
        self.join_btn = QtWidgets.QPushButton("Join friendnet")
        self.join_btn.setObjectName("joinButton")
        self.join_btn.clicked.connect(self.on_join_invite)
        self.existing_btn = QtWidgets.QPushButton("Use existing Tahoe node")
        self.existing_btn.setObjectName("existingButton")
        self.existing_btn.clicked.connect(self.on_join_existing)
        row.addWidget(self.join_btn)
        row.addWidget(self.existing_btn)
        self.import_key_btn = QtWidgets.QPushButton("Import recovery key instead…")
        self.import_key_btn.setObjectName("importKeyButton")
        self.import_key_btn.clicked.connect(self.on_import_recovery)
        row.addWidget(self.import_key_btn)
        row.addStretch(1)
        v.addLayout(row)
        self.join_progress = QtWidgets.QLabel("")
        self.join_progress.setObjectName("joinProgress")
        self.join_progress.setWordWrap(True)
        v.addWidget(self.join_progress)
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
        self.credit_tab = QtWidgets.QWidget()
        self.credit_tab.setObjectName("creditTab")
        self.recovery_tab = QtWidgets.QWidget()
        self.recovery_tab.setObjectName("recoveryTab")
        self.settings_tab = QtWidgets.QWidget()
        self.tabs.addTab(self.folders_tab, "Folders")
        self.tabs.addTab(self.credit_tab, "Credit")
        self.tabs.addTab(self.recovery_tab, "Recovery")
        self.tabs.addTab(self.settings_tab, "Settings")
        self.tabs.currentChanged.connect(self._on_place_changed)
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
        self.open_credit_btn = QtWidgets.QPushButton("Open Credit")
        self.open_credit_btn.setObjectName("openCreditButton")
        self.open_credit_btn.clicked.connect(self.open_credit_place)
        self.open_credit_btn.hide()
        fl.addWidget(self.open_credit_btn)

        self._build_credit_tab()
        self._build_recovery_tab()
        self._build_settings_tab()
        return page

    def _build_credit_tab(self) -> None:
        QtWidgets = self.QtWidgets
        cl = QtWidgets.QVBoxLayout(self.credit_tab)
        head = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Credit")
        font = title.font()
        font.setBold(True)
        title.setFont(font)
        head.addWidget(title)
        head.addStretch(1)
        self.credit_refresh_btn = QtWidgets.QPushButton("Refresh")
        self.credit_refresh_btn.setObjectName("creditRefreshButton")
        self.credit_refresh_btn.clicked.connect(self.load_credit)
        head.addWidget(self.credit_refresh_btn)
        cl.addLayout(head)

        self.credit_loading = QtWidgets.QLabel("Loading credit balance…")
        self.credit_loading.setObjectName("creditLoading")
        self.credit_loading.hide()
        cl.addWidget(self.credit_loading)

        self.credit_error = QtWidgets.QLabel("")
        self.credit_error.setObjectName("creditError")
        self.credit_error.setWordWrap(True)
        self.credit_error.setStyleSheet("color: #8b1a1a;")
        self.credit_error.hide()
        cl.addWidget(self.credit_error)
        self.credit_retry_btn = QtWidgets.QPushButton("Retry")
        self.credit_retry_btn.setObjectName("creditRetryButton")
        self.credit_retry_btn.clicked.connect(self.load_credit)
        self.credit_retry_btn.hide()
        cl.addWidget(self.credit_retry_btn)

        self.credit_body = QtWidgets.QWidget()
        self.credit_body.setObjectName("creditBody")
        body = QtWidgets.QVBoxLayout(self.credit_body)
        body.setContentsMargins(0, 0, 0, 0)
        remaining_box = QtWidgets.QGroupBox("Remaining")
        remaining_box.setObjectName("creditRemainingBox")
        rb = QtWidgets.QVBoxLayout(remaining_box)
        self.credit_remaining = QtWidgets.QLabel(format_remaining(0))
        self.credit_remaining.setObjectName("creditRemaining")
        self.credit_remaining.setWordWrap(True)
        rb.addWidget(self.credit_remaining)
        denom = QtWidgets.QLabel(DENOMINATION_NOTE)
        denom.setObjectName("creditDenomination")
        denom.setWordWrap(True)
        rb.addWidget(denom)
        body.addWidget(remaining_box)
        self.credit_topup_btn = QtWidgets.QPushButton("Top up")
        self.credit_topup_btn.setObjectName("creditTopUpButton")
        self.credit_topup_btn.clicked.connect(self.on_top_up)
        body.addWidget(self.credit_topup_btn)
        lab = QtWidgets.QLabel(LAB_NOTE)
        lab.setObjectName("creditLabNote")
        lab.setWordWrap(True)
        body.addWidget(lab)
        self.credit_success = QtWidgets.QLabel("")
        self.credit_success.setObjectName("creditSuccess")
        self.credit_success.setWordWrap(True)
        self.credit_success.hide()
        body.addWidget(self.credit_success)
        self.credit_recent = QtWidgets.QLabel("")
        self.credit_recent.setObjectName("creditRecent")
        self.credit_recent.setWordWrap(True)
        body.addWidget(self.credit_recent)
        body.addStretch(1)
        cl.addWidget(self.credit_body)
        cl.addStretch(1)

    def _build_recovery_tab(self) -> None:
        QtWidgets = self.QtWidgets
        rl = QtWidgets.QVBoxLayout(self.recovery_tab)
        title = QtWidgets.QLabel("Recovery")
        font = title.font()
        font.setBold(True)
        title.setFont(font)
        rl.addWidget(title)
        intro = QtWidgets.QLabel(RECOVERY_INTRO)
        intro.setWordWrap(True)
        intro.setObjectName("recoveryIntro")
        rl.addWidget(intro)
        scary = QtWidgets.QLabel("⚠  " + SCARY_LOSS)
        scary.setWordWrap(True)
        scary.setObjectName("recoveryScary")
        scary.setStyleSheet("color: #8b1a1a; font-weight: bold;")
        rl.addWidget(scary)
        row = QtWidgets.QHBoxLayout()
        self.export_key_btn = QtWidgets.QPushButton("Export recovery key…")
        self.export_key_btn.setObjectName("exportKeyButton")
        self.export_key_btn.clicked.connect(self.on_export_recovery)
        self.import_key_btn2 = QtWidgets.QPushButton("Import recovery key…")
        self.import_key_btn2.setObjectName("importKeyButton2")
        self.import_key_btn2.clicked.connect(self.on_import_recovery)
        row.addWidget(self.export_key_btn)
        row.addWidget(self.import_key_btn2)
        row.addStretch(1)
        rl.addLayout(row)
        self.recovery_status = QtWidgets.QLabel("")
        self.recovery_status.setObjectName("recoveryStatus")
        self.recovery_status.setWordWrap(True)
        rl.addWidget(self.recovery_status)
        self.last_export_label = QtWidgets.QLabel("")
        self.last_export_label.setObjectName("lastExportLabel")
        rl.addWidget(self.last_export_label)
        self._refresh_last_export()
        rl.addStretch(1)

    def _refresh_last_export(self) -> None:
        info = self.recovery.last_export()
        if not info:
            self.last_export_label.setText("Last export: never")
            return
        when = time.strftime("%Y-%m-%d %H:%M", time.localtime(float(info["last_export"])))
        self.last_export_label.setText("Last export: %s  →  %s" % (when, info.get("path", "")))

    def on_export_recovery(self) -> None:
        self.recovery_status.setStyleSheet("")
        self.recovery_status.setText("")
        dlg = ExportRecoveryDialog(self.win, self.recovery, self.QtWidgets)
        if dlg.dlg.exec_() == self.QtWidgets.QDialog.Accepted and dlg.written is not None:
            self.recovery_status.setText(
                "Recovery key written to %s. Move it somewhere safe and offline." % dlg.written
            )
            self._refresh_last_export()

    def on_import_recovery(self) -> None:
        dlg = ImportRecoveryDialog(self.win, self.recovery, self.QtWidgets)
        if dlg.dlg.exec_() != self.QtWidgets.QDialog.Accepted or dlg.result is None:
            return
        self.apply_restore_result(dlg.result)

    def apply_restore_result(self, result: RestoreResult) -> None:
        note = "Restored %d folder(s): %s." % (len(result.folders), ", ".join(result.folders) or "none")
        if result.skipped:
            note += " Already here: %s." % ", ".join(result.skipped)
        if result.wallet_restored:
            note += " Credit wallet restored."
        note += " Files download from the friendnet as this device (%s)." % result.author_name
        if not self._joined:
            self._enter_main("Connected", result.grid)
        else:
            self.refresh()
        self.tabs.setCurrentWidget(self.folders_tab)
        self.folder_error.setText(note)
        self.recovery_status.setText(note)

    def _build_settings_tab(self) -> None:
        QtWidgets = self.QtWidgets
        sl = QtWidgets.QVBoxLayout(self.settings_tab)
        sl.addWidget(QtWidgets.QLabel("Settings"))
        note = QtWidgets.QLabel(
            "Transport policy: full privacy claims often want Tor; Magic Folder sync "
            "that feels normal may use LAN/WAN. This is a visible design flag; a transport setting is still to come.\n\n"
            "Coming later\n"
            "· .deb / macOS / Windows installers (Linux AppImage ships now)\n"
            "· Monero (XMR) top-up — U5 (after mint rails)\n\n"
            "About\n"
            "%s (buyer) · version %s\n"
            "Grid: lab-friendnet\n"
            "Credit: open the Credit place to view balance / Top up."
            % (APP_NAME, __version__)
        )
        note.setWordWrap(True)
        note.setObjectName("settingsNote")
        sl.addWidget(note)
        sl.addStretch(1)

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
        credit_act = menu.addAction("Credit")
        credit_act.triggered.connect(self.open_credit_place)
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

    def shutdown(self) -> None:
        """Stop the daemons this Sync process started (Magic Folder, then Tahoe)."""
        for ctl in (self.mf, self.tahoe):
            try:
                ctl.stop()
            except Exception:
                pass

    def quit(self) -> None:
        self.shutdown()
        self.app.quit()

    def show_join_error(self, err: SyncError) -> None:
        self.join_error.setText(err.banner())

    def show_folder_error(self, err: SyncError, open_credit: bool = False) -> None:
        self.folder_error.setText(err.banner())
        self.open_credit_btn.setVisible(open_credit)

    def clear_errors(self) -> None:
        self.join_error.setText("")
        self.join_progress.setText("")
        self.folder_error.setText("")
        self.open_credit_btn.hide()
        self.credit_error.setText("")
        self.credit_error.hide()
        self.credit_success.hide()

    def _try_autoload(self) -> None:
        """Attach to a configured node on launch; otherwise land on the join page."""
        if not self.tahoe.has_nodedir():
            self.stack.setCurrentWidget(self.join_page)
            return
        self.stack.setCurrentWidget(self.join_page)
        self._join_busy(True, "Tahoe client found at %s — connecting…" % self.tahoe.nodedir)
        try:
            status = self.tahoe.join_existing()
        except SyncError as exc:
            self._join_busy(False)
            self.show_join_error(exc)
            return
        self._join_busy(False)
        self._enter_main(status.state, status.detail)

    def _join_busy(self, busy: bool, text: str = "") -> None:
        self.join_btn.setEnabled(not busy)
        self.existing_btn.setEnabled(not busy)
        self.invite_edit.setEnabled(not busy)
        self.join_progress.setText(text)
        self.QtWidgets.QApplication.processEvents()

    def on_join_invite(self) -> None:
        self.clear_errors()
        invite = self.invite_edit.text()
        progress = (
            "Joining… starting the Tahoe client and waiting for the introducer "
            "(this can take up to a minute the first time)."
        )
        if self.tahoe.has_nodedir():
            progress = "Connecting to the existing Tahoe client…"
        self._join_busy(True, progress)
        try:
            status = self.tahoe.join_invite(invite)
        except SyncError as exc:
            self._join_busy(False)
            self.show_join_error(exc)
            return
        self._join_busy(False)
        self._enter_main(status.state, status.detail)

    def on_join_existing(self) -> None:
        self.clear_errors()
        self._join_busy(True, "Connecting to the existing Tahoe client…")
        try:
            status = self.tahoe.join_existing()
        except SyncError as exc:
            self._join_busy(False)
            self.show_join_error(exc)
            return
        self._join_busy(False)
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
        self._show_refusal_if_any()

    def _show_refusal_if_any(self) -> bool:
        """Storage refused a write for lack of credit (spender event): say so on Folders."""
        reason = self.credit.recent_refusal()
        if not reason:
            return False
        self.show_folder_error(
            SyncError(
                "sync is paused by the friendnet. %s." % reason,
                "Credit → Top up; uploads resume on the next scan.",
            ),
            open_credit=True,
        )
        return True

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
        remaining = self.credit.remaining_tokens()
        if credit_gate(remaining, 0) == "zero":
            self.show_folder_error(SyncError(ZERO_FOLDER_MSG, ZERO_FOLDER_NEXT), open_credit=True)
            return
        path = QtWidgets.QFileDialog.getExistingDirectory(
            self.win, "Choose a local folder to sync", str(Path.home())
        )
        if not path:
            return
        need = self.credit.estimate_tokens(Path(path))
        gate = credit_gate(remaining, need)
        if gate == "zero":
            self.show_folder_error(SyncError(ZERO_FOLDER_MSG, ZERO_FOLDER_NEXT), open_credit=True)
            return
        if gate == "review":
            if not self._review_expansion(need, remaining):
                return
        try:
            name = self.mf.add_folder(path)
        except SyncError as exc:
            # A gated node refusing the folder's directories surfaces as a Magic
            # Folder 500; the spender's event tells the real story.
            if not self._show_refusal_if_any():
                self.show_folder_error(exc)
            return
        self.refresh()
        self.folder_error.setText("Added folder %s" % name)

    def _review_expansion(self, need: int, remaining: int) -> bool:
        QtWidgets = self.QtWidgets
        box = QtWidgets.QMessageBox(self.win)
        box.setObjectName("expansionReview")
        box.setWindowTitle("REVIEW")
        box.setText(REVIEW_HEAD)
        box.setInformativeText(
            "Share expansion is expected. Estimated need: ~%.1f× upload.\n"
            "Uploading 1 GiB uses more than 1 GiB of credit.\n"
            "Need about %d GiB·mo; remaining %d GiB·mo."
            % (EXPAND_FACTOR, need, remaining)
        )
        topup = box.addButton("Top up", QtWidgets.QMessageBox.AcceptRole)
        box.addButton("Cancel add", QtWidgets.QMessageBox.RejectRole)
        box.exec_()
        if box.clickedButton() is topup:
            self.open_credit_place()
            self.on_top_up()
        return False

    def open_credit_place(self) -> None:
        self.show()
        if self.stack.currentWidget() is not self.main_page:
            return
        self.tabs.setCurrentWidget(self.credit_tab)
        self.load_credit()

    def _on_place_changed(self, idx: int) -> None:
        if not self._joined:
            return
        if self.tabs.widget(idx) is self.credit_tab:
            self.load_credit()

    def load_credit(self) -> None:
        self.credit_success.hide()
        self.credit_error.hide()
        self.credit_retry_btn.hide()
        self.credit_body.hide()
        self.credit_loading.show()
        self.QtWidgets.QApplication.processEvents()
        try:
            snap = self.credit.load_balance()
        except SyncError as exc:
            self.credit_loading.hide()
            self.credit_error.setText(exc.banner())
            self.credit_error.show()
            self.credit_retry_btn.show()
            return
        self.apply_credit_snapshot(snap)

    def apply_credit_snapshot(self, snap: CreditSnapshot, success_note: str = "") -> None:
        self._credit_loaded = True
        self.credit_loading.hide()
        self.credit_error.hide()
        self.credit_retry_btn.hide()
        self.credit_body.show()
        self.credit_remaining.setText(snap.remaining_text)
        if snap.recent:
            lines = ["Recent"]
            for row in snap.recent:
                lines.append("· %s  %s    %s" % (row.title, row.delta, row.when))
            self.credit_recent.setText("\n".join(lines))
            self.credit_recent.show()
        else:
            self.credit_recent.setText("")
            self.credit_recent.hide()
        if success_note:
            self.credit_success.setText(success_note)
            self.credit_success.show()
        else:
            self.credit_success.hide()

    def on_top_up(self) -> None:
        dlg = TopUpDialog(self.win, self.credit, self.QtWidgets)
        result = dlg.dlg.exec_()
        if result == self.QtWidgets.QDialog.Accepted and dlg.snapshot is not None:
            note = "Top-up complete.\n" + dlg.snapshot.remaining_text
            self.apply_credit_snapshot(dlg.snapshot, success_note=note)

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

    def dogfood_credit(self, screenshot: Optional[Path] = None, tier: str = "medium") -> dict:
        """Join existing friendnet, redeem lab faucet, show updated Credit balance."""
        self.clear_errors()
        status = self.tahoe.join_existing()
        self._enter_main(status.state, status.detail)
        before = self.credit.remaining_tokens()
        self.open_credit_place()
        snap = self.credit.redeem_faucet(tier)
        note = "Top-up complete.\n" + snap.remaining_text
        self.apply_credit_snapshot(snap, success_note=note)
        if screenshot:
            self.grab_to(screenshot)
        return {
            "before": before,
            "after": snap.balance.tokens,
            "remaining": snap.remaining_text,
            "issuer": snap.balance.issuer_pubkey_id,
            "grid": status.detail,
        }


def run_app(
    nodedir: Optional[Path] = None,
    screenshot: Optional[Path] = None,
    dogfood_folder: Optional[Path] = None,
    issuer_url: Optional[str] = None,
    credit_dogfood: bool = False,
    credit_tier: str = "medium",
    invite: Optional[str] = None,
) -> int:
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    ui = MainWindow(nodedir=nodedir, issuer_url=issuer_url, autoload=False)
    ui.show()
    ui.QtWidgets.QApplication.processEvents()
    try:
        if invite:
            # Headless join first (creates + starts the client); the modes below then
            # attach to it as an existing node and quit stops what we started.
            try:
                ui.tahoe.join_invite(invite.strip())
            except SyncError as exc:
                ui.show_join_error(exc)
                if screenshot:
                    ui.grab_to(screenshot)
                print(exc.banner(), file=sys.stderr)
                return 1
        return _run_modes(ui, screenshot, dogfood_folder, credit_dogfood, credit_tier)
    finally:
        ui.shutdown()


def _run_modes(
    ui: MainWindow,
    screenshot: Optional[Path],
    dogfood_folder: Optional[Path],
    credit_dogfood: bool,
    credit_tier: str,
) -> int:
    if not (credit_dogfood or dogfood_folder is not None):
        # Window is visible first so a slow Tahoe start shows progress copy, not a blank desktop.
        ui._try_autoload()
    if credit_dogfood:
        try:
            result = ui.dogfood_credit(screenshot=screenshot, tier=credit_tier)
        except SyncError as exc:
            ui.open_credit_place()
            ui.credit_loading.hide()
            ui.credit_error.setText(exc.banner())
            ui.credit_error.show()
            ui.credit_retry_btn.show()
            if screenshot:
                ui.grab_to(screenshot)
            print(exc.banner(), file=sys.stderr)
            return 1
        print(
            "U2 credit-dogfood before=%s after=%s remaining=%s"
            % (result["before"], result["after"], result["remaining"].split("\n")[0])
        )
        return 0
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
