"""Native Leasegrid Sync window (PyQt). Gridsync folder-list mental model.

Leasegrid Sync does not use the Tahoe web UI as the buyer surface.
"""

from __future__ import annotations

import os
import re
import sys
import time
import traceback
from pathlib import Path
from typing import Optional

from . import APP_NAME, __version__
from .backend import (
    ConnectionStatus,
    DiskSlices,
    FolderRow,
    MagicFolderCtl,
    SyncError,
    TahoeClient,
    apply_offer_percent,
    default_home,
    format_bytes,
    is_wormhole_code,
    read_disk_offer,
    write_probe_file,
    wait_for_file_status,
)
from .credit import (
    DENOMINATION_NOTE,
    EXPAND_FACTOR,
    LAB_NOTE,
    REVIEW_HEAD,
    XMR_LATER,
    XMR_TIERS,
    ZERO_FOLDER_MSG,
    ZERO_FOLDER_NEXT,
    CreditCtl,
    CreditSnapshot,
    credit_enforced,
    credit_gate,
    format_remaining,
    underpaid_copy,
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
    "You are joining a friendnet you trust — not Dropbox-the-company and not Filecoin.\n"
    "1. Same invite, same process — joining and offering disk are one unpaid step. "
    "This device syncs folders and, by default, also stores shares for the friendnet.\n"
    "2. No storage proofs — dead nodes are dropped and shares moved, not slashed.\n"
    "3. Share over I2P — the join URL is a page you host; the address lives after # "
    "so the eepsite never sees it. Folder sync may still use LAN/WAN.\n"
    "4. Recovery — lose the recovery key and this device and access can be gone forever. "
    "Export one from the Recovery place after you join."
)


def _qt_api():
    from PyQt5 import QtCore, QtGui, QtWidgets

    return QtCore, QtGui, QtWidgets


UI_LOG_NAME = "sync-ui.log"
UNEXPECTED_NEXT = "Retry. If it repeats, send logs/%s to your friendnet operator." % UI_LOG_NAME


def format_status_chip(status: ConnectionStatus) -> str:
    """Buyer-facing chip. Tahoe 'introducer up · N storage' stays in --status."""
    if status.state == "Connected":
        n = int(status.servers_connected or 0)
        if n <= 0:
            m = re.search(r"(\d+)\s+storage", status.detail or "")
            n = int(m.group(1)) if m else 0
        if n <= 0:
            return "Online — connected to the friendnet"
        if n == 1:
            return "Online — 1 computer storing files"
        return "Online — %d computers storing files" % n
    if status.state == "Connecting":
        return "Connecting…"
    if status.state == "FAIL":
        return "Can't reach the friendnet"
    if status.state == "Offline":
        return "Offline"
    return status.state


def log_exception(home: Path, where: str, exc: BaseException) -> Path:
    """Append a traceback to <home>/logs/sync-ui.log; never raises."""
    path = Path(home) / "logs" / UI_LOG_NAME
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write("%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), where))
            f.write("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))
            f.write("\n")
    except OSError:
        pass
    return path


def _make_disk_pie(parent):
    """Paint used / offered / free as a pie. No Tahoe web view."""
    _QtCore, QtGui, QtWidgets = _qt_api()

    class DiskPie(QtWidgets.QWidget):
        def __init__(self) -> None:
            super().__init__(parent)
            self.setObjectName("diskPie")
            self.setMinimumSize(148, 148)
            self.setMaximumSize(180, 180)
            self._slices: Optional[DiskSlices] = None

        def set_slices(self, slices: Optional[DiskSlices]) -> None:
            self._slices = slices
            self.update()

        def paintEvent(self, _event) -> None:
            painter = QtGui.QPainter(self)
            painter.setRenderHint(QtGui.QPainter.Antialiasing)
            side = min(self.width(), self.height()) - 8
            rect = _QtCore.QRectF(
                (self.width() - side) / 2.0,
                (self.height() - side) / 2.0,
                side,
                side,
            )
            painter.setPen(_QtCore.Qt.NoPen)
            slices = self._slices
            parts: list[tuple[int, QtGui.QColor]] = []
            if slices is not None:
                parts = [
                    (slices.used, QtGui.QColor("#6b7280")),
                    (slices.offered, QtGui.QColor("#1f6feb")),
                    (slices.kept, QtGui.QColor("#d1d5db")),
                ]
            total = sum(v for v, _c in parts)
            if total <= 0:
                painter.setBrush(QtGui.QColor("#e5e7eb"))
                painter.drawEllipse(rect)
                painter.end()
                return
            start = 90 * 16
            for value, color in parts:
                if value <= 0:
                    continue
                span = -int(round(360 * 16 * value / total))
                if span == 0:
                    continue
                painter.setBrush(color)
                painter.drawPie(rect, start, span)
                start += span
            painter.end()

    return DiskPie()


def unexpected_error(exc: BaseException, what: str) -> SyncError:
    """Wrap a non-SyncError so it can be shown as a FAIL banner instead of aborting."""
    detail = str(exc).strip().splitlines()[0] if str(exc).strip() else ""
    msg = "%s Unexpected error: %s%s" % (what, type(exc).__name__, (" — " + detail) if detail else "")
    return SyncError(msg, UNEXPECTED_NEXT)


def install_excepthook(ui: "MainWindow") -> None:
    """Keep the window alive on an uncaught exception in a Qt slot.

    With the default sys.excepthook, PyQt5 turns any Python exception that
    reaches a slot boundary into qFatal(): the app aborts with no UI. This hook
    logs the traceback and shows one REVIEW box instead.
    """

    def hook(exc_type, exc, tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc, tb)
            return
        path = log_exception(ui.home, "uncaught", exc)
        sys.__excepthook__(exc_type, exc, tb)
        try:
            ui.show_unexpected(exc, path)
        except Exception:
            pass  # logging already happened; never let the hook itself abort

    sys.excepthook = hook


class TopUpDialog:
    """U5: quote XMR → pay URI → poll → collect. Lab faucet stays as a second button."""

    def __init__(self, parent, credit: CreditCtl, qt) -> None:
        from PyQt5 import QtCore

        QtWidgets = qt
        self.QtWidgets = QtWidgets
        self.QtCore = QtCore
        self.credit = credit
        self.snapshot: Optional[CreditSnapshot] = None
        self.quote: Optional[dict] = None
        self._amount_xmr = ""
        self.page = "choose"
        self.dlg = QtWidgets.QDialog(parent)
        self.dlg.setWindowTitle("Top up")
        self.dlg.setObjectName("topUpDialog")
        self.dlg.setModal(True)
        v = QtWidgets.QVBoxLayout(self.dlg)
        self.stack = QtWidgets.QStackedWidget()
        self.choose_page = QtWidgets.QWidget()
        self.pay_page = QtWidgets.QWidget()
        self.stack.addWidget(self.choose_page)
        self.stack.addWidget(self.pay_page)
        v.addWidget(self.stack)

        cv = QtWidgets.QVBoxLayout(self.choose_page)
        title = QtWidgets.QLabel("Buy credit with XMR")
        font = title.font()
        font.setBold(True)
        title.setFont(font)
        cv.addWidget(title)
        intro = QtWidgets.QLabel("Prepaid share-capacity for this friendnet. Not a 1:1 disk meter.")
        intro.setWordWrap(True)
        cv.addWidget(intro)
        cv.addWidget(QtWidgets.QLabel("Amount"))
        self.amount_group = QtWidgets.QButtonGroup(self.dlg)
        self.radios = {}
        labels = {
            "small": "Small (≈ %d GiB·mo)" % XMR_TIERS["small"],
            "medium": "Medium (≈ %d GiB·mo)" % XMR_TIERS["medium"],
            "large": "Large (≈ %d GiB·mo)" % XMR_TIERS["large"],
        }
        for key, label in labels.items():
            radio = QtWidgets.QRadioButton(label)
            radio.setObjectName("tier_%s" % key)
            self.amount_group.addButton(radio)
            self.radios[key] = radio
            cv.addWidget(radio)
        self.radios["medium"].setChecked(True)
        xmr = QtWidgets.QLabel(XMR_LATER)
        xmr.setWordWrap(True)
        xmr.setObjectName("xmrLaterLabel")
        cv.addWidget(xmr)

        pv = QtWidgets.QVBoxLayout(self.pay_page)
        pay_title = QtWidgets.QLabel("Pay this quote")
        pf = pay_title.font()
        pf.setBold(True)
        pay_title.setFont(pf)
        pv.addWidget(pay_title)
        hint = QtWidgets.QLabel(
            "Send exactly this amount. After the timer we still credit for 24 h at this price."
        )
        hint.setWordWrap(True)
        hint.setObjectName("payHint")
        pv.addWidget(hint)
        self.pay_amount = QtWidgets.QLabel("")
        self.pay_amount.setObjectName("payAmount")
        self.pay_amount.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        pv.addWidget(self.pay_amount)
        self.pay_address = QtWidgets.QLabel("")
        self.pay_address.setObjectName("payAddress")
        self.pay_address.setWordWrap(True)
        self.pay_address.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        pv.addWidget(self.pay_address)
        crow = QtWidgets.QHBoxLayout()
        self.copy_address_btn = QtWidgets.QPushButton("Copy address")
        self.copy_address_btn.setObjectName("copyAddressButton")
        self.copy_address_btn.clicked.connect(self.on_copy_address)
        self.copy_amount_btn = QtWidgets.QPushButton("Copy amount")
        self.copy_amount_btn.setObjectName("copyAmountButton")
        self.copy_amount_btn.clicked.connect(self.on_copy_amount)
        crow.addWidget(self.copy_address_btn)
        crow.addWidget(self.copy_amount_btn)
        crow.addStretch(1)
        pv.addLayout(crow)

        self.status = QtWidgets.QLabel("")
        self.status.setObjectName("topUpStatus")
        self.status.setWordWrap(True)
        v.addWidget(self.status)
        row = QtWidgets.QHBoxLayout()
        self.continue_btn = QtWidgets.QPushButton("Continue")
        self.continue_btn.setObjectName("topUpContinue")
        self.continue_btn.clicked.connect(self.on_continue)
        self.request_btn = QtWidgets.QPushButton("Request faucet credit")
        self.request_btn.setObjectName("requestFaucetButton")
        self.request_btn.clicked.connect(self.on_request)
        self.cancel_btn = QtWidgets.QPushButton("Cancel")
        self.cancel_btn.setObjectName("topUpCancel")
        self.cancel_btn.clicked.connect(self.dlg.reject)
        row.addWidget(self.continue_btn)
        row.addWidget(self.request_btn)
        row.addWidget(self.cancel_btn)
        row.addStretch(1)
        v.addLayout(row)
        self._timer = None
        self.dlg.finished.connect(self._stop_poll)

    def _selected_tier(self) -> str:
        for key, radio in self.radios.items():
            if radio.isChecked():
                return key
        return "medium"

    def _tokens(self) -> int:
        return int(XMR_TIERS.get(self._selected_tier(), 50))

    def on_continue(self) -> None:
        self.status.setStyleSheet("")
        self.status.setText("Asking the issuer for a quote…")
        self.continue_btn.setEnabled(False)
        self.QtWidgets.QApplication.processEvents()
        try:
            self.quote = self.credit.quote_topup(self._tokens())
        except SyncError as exc:
            self.status.setStyleSheet("color: #8b1a1a;")
            self.status.setText(exc.banner())
            self.continue_btn.setEnabled(True)
            self.continue_btn.setText("Retry")
            return
        self._show_pay()

    def _show_pay(self) -> None:
        q = self.quote or {}
        self.page = "pay"
        self._amount_xmr = str(q.get("amount_xmr") or "")
        self.pay_amount.setText("%s XMR" % self._amount_xmr)
        self.pay_address.setText(str(q.get("address") or ""))
        self.stack.setCurrentWidget(self.pay_page)
        self.continue_btn.hide()
        self.request_btn.hide()
        self.cancel_btn.setText("Close")
        self.status.setText("Waiting for payment…")
        self._start_poll()

    def _start_poll(self) -> None:
        if self._timer is None:
            self._timer = self.QtCore.QTimer(self.dlg)
            self._timer.setInterval(2000)
            self._timer.timeout.connect(self.on_poll)
        self._timer.start()

    def _stop_poll(self, _result: int = 0) -> None:
        if self._timer is not None:
            self._timer.stop()

    def on_poll(self) -> None:
        try:
            self._on_poll()
        except Exception:
            try:
                self.status.setStyleSheet("color: #8b1a1a;")
                self.status.setText(
                    "REVIEW — Could not check this quote. Payments already sent are safe; retry later."
                )
            except Exception:
                pass

    def _on_poll(self) -> None:
        if not self.quote:
            return
        try:
            r = self.credit.poll_topup(self.quote["vid"])
        except SyncError as exc:
            self.status.setStyleSheet("color: #8b1a1a;")
            self.status.setText(exc.banner())
            return
        state = str(r.get("state") or "")
        v = r.get("voucher") or {}
        if state == "issued":
            self._stop_poll()
            try:
                self.snapshot = self.credit.load_balance()
            except SyncError:
                self.snapshot = None
            n = int(r.get("tokens_added") or r.get("tokens") or 0)
            bal = self.snapshot.balance.tokens if self.snapshot else n
            self.page = "done"
            self.status.setStyleSheet("")
            self.status.setText("+%d credits. Balance: %d" % (n, bal))
            self.cancel_btn.setText("Done")
            self.cancel_btn.clicked.disconnect()
            self.cancel_btn.clicked.connect(self.dlg.accept)
            return
        if state == "underpaid":
            quoted = (self.quote or {}).get("amount_piconero") or (self.quote or {}).get("amount_due")
            self.status.setText(underpaid_copy(v, quoted))
            return
        if state in ("seen", "confirming"):
            need = v.get("confirmations_required") or (self.quote or {}).get("confirmations_required") or 2
            have = v.get("confirmations") or 0
            self.status.setText("Payment seen. Confirming %s of %s…" % (have, need))
            return
        if state == "quoted":
            self.status.setText("Waiting for payment…")

    def on_copy_address(self) -> None:
        self.QtWidgets.QApplication.clipboard().setText(self.pay_address.text())

    def on_copy_amount(self) -> None:
        self.QtWidgets.QApplication.clipboard().setText(self._amount_xmr)

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
        self.app.setQuitOnLastWindowClosed(True)

        self.win = QtWidgets.QMainWindow()
        self.win.setWindowTitle(APP_NAME)
        self.win.resize(920, 620)
        self.win.closeEvent = self._on_close  # type: ignore[method-assign]

        central = QtWidgets.QWidget()
        self.win.setCentralWidget(central)
        self.stack = QtWidgets.QStackedWidget()
        layout = QtWidgets.QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        # In-window REVIEW, not QMessageBox: PyQt5's offscreen plugin on Windows
        # access-violates in QMessageBox.show() (CI test_excepthook_…).
        self.unexpected_review = QtWidgets.QLabel("")
        self.unexpected_review.setObjectName("unexpectedReview")
        self.unexpected_review.setWordWrap(True)
        self.unexpected_review.setStyleSheet("color: #8b1a1a; padding: 8px 12px;")
        self.unexpected_review.hide()
        layout.addWidget(self.unexpected_review)
        layout.addWidget(self.stack)

        self.join_page = self._build_join_page()
        self.main_page = self._build_main_page()
        self.stack.addWidget(self.join_page)
        self.stack.addWidget(self.main_page)

        self.tray = None
        self.tray_credit_action = None
        self._init_tray()
        self._sync_gated_chrome()

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
        title = QtWidgets.QLabel("Join a friendnet")
        title.setObjectName("joinTitle")
        font = title.font()
        font.setPointSize(16)
        font.setBold(True)
        title.setFont(font)
        v.addWidget(title)
        intro = QtWidgets.QLabel("Paste a link, short code, or the text from a QR.")
        intro.setWordWrap(True)
        intro.setObjectName("joinIntro")
        v.addWidget(intro)
        self.invite_edit = QtWidgets.QLineEdit()
        self.invite_edit.setPlaceholderText("http://….i2p/join#…   or   7-word-word")
        self.invite_edit.setObjectName("inviteEdit")
        self.invite_edit.returnPressed.connect(self.on_join_invite)
        v.addWidget(self.invite_edit)
        self.offer_storage_cb = QtWidgets.QCheckBox("Offer disk on this device")
        self.offer_storage_cb.setObjectName("offerStorage")
        self.offer_storage_cb.setChecked(True)
        v.addWidget(self.offer_storage_cb)
        self.join_btn = QtWidgets.QPushButton("Join friendnet")
        self.join_btn.setObjectName("joinButton")
        self.join_btn.setAutoDefault(True)
        self.join_btn.setDefault(True)
        self.join_btn.clicked.connect(self.on_join_invite)
        v.addWidget(self.join_btn)
        self.existing_btn = QtWidgets.QPushButton("Use existing Tahoe node")
        self.existing_btn.setObjectName("existingButton")
        self.existing_btn.setFlat(True)
        self.existing_btn.setAutoDefault(False)
        self.existing_btn.clicked.connect(self.on_join_existing)
        v.addWidget(self.existing_btn)
        self.import_key_btn = QtWidgets.QPushButton("Import recovery key instead…")
        self.import_key_btn.setObjectName("importKeyButton")
        self.import_key_btn.setFlat(True)
        self.import_key_btn.setAutoDefault(False)
        self.import_key_btn.clicked.connect(self.on_import_recovery)
        v.addWidget(self.import_key_btn)
        self.details_btn = QtWidgets.QPushButton("What's a friendnet?")
        self.details_btn.setObjectName("joinDetails")
        self.details_btn.setFlat(True)
        self.details_btn.setAutoDefault(False)
        self.details_btn.clicked.connect(self.on_join_details)
        v.addWidget(self.details_btn)
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
        self.back_btn = QtWidgets.QPushButton("Folders")
        self.back_btn.setObjectName("backToFolders")
        self.back_btn.setFlat(True)
        self.back_btn.clicked.connect(lambda: self.show_place(self.folders_tab))
        self.back_btn.hide()
        chrome.addWidget(self.back_btn)
        chrome.addWidget(self.status_chip)
        self.more_btn = QtWidgets.QToolButton()
        self.more_btn.setText("More")
        self.more_btn.setObjectName("moreButton")
        self.more_btn.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        more = QtWidgets.QMenu(self.more_btn)
        more.setObjectName("moreMenu")
        self.credit_action = more.addAction("Credit")
        self.credit_action.setObjectName("creditPlaceAction")
        self.credit_action.triggered.connect(self.open_credit_place)
        self.recovery_action = more.addAction("Recovery")
        self.recovery_action.triggered.connect(lambda: self.show_place(self.recovery_tab))
        self.settings_action = more.addAction("Settings")
        self.settings_action.triggered.connect(lambda: self.show_place(self.settings_tab))
        self.more_btn.setMenu(more)
        chrome.addWidget(self.more_btn)
        v.addLayout(chrome)

        self.places = QtWidgets.QStackedWidget()
        self.places.setObjectName("places")
        self.folders_tab = QtWidgets.QWidget()
        self.folders_tab.setObjectName("foldersTab")
        self.credit_tab = QtWidgets.QWidget()
        self.credit_tab.setObjectName("creditTab")
        self.recovery_tab = QtWidgets.QWidget()
        self.recovery_tab.setObjectName("recoveryTab")
        self.settings_tab = QtWidgets.QWidget()
        self.places.addWidget(self.folders_tab)
        self.places.addWidget(self.credit_tab)
        self.places.addWidget(self.recovery_tab)
        self.places.addWidget(self.settings_tab)
        self.places.currentChanged.connect(self._on_place_changed)
        v.addWidget(self.places)

        fl = QtWidgets.QVBoxLayout(self.folders_tab)
        head = QtWidgets.QHBoxLayout()
        folders_title = QtWidgets.QLabel("Folders")
        folders_title.setObjectName("foldersTitle")
        font = folders_title.font()
        font.setPointSize(14)
        font.setBold(True)
        folders_title.setFont(font)
        head.addWidget(folders_title)
        head.addStretch(1)
        self.add_btn = QtWidgets.QPushButton("Add folder")
        self.add_btn.setObjectName("addFolderButton")
        self.add_btn.clicked.connect(self.on_add_folder)
        head.addWidget(self.add_btn)
        fl.addLayout(head)
        self.empty_label = QtWidgets.QLabel(
            "No folders on this device yet.\n"
            "Add a local folder to keep in sync here."
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
        fl.addWidget(self.table, 1)
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
        fl.addWidget(self._build_offer_box())

        self._build_credit_tab()
        self._build_recovery_tab()
        self._build_settings_tab()
        self._sync_gated_chrome()
        return page

    def _build_offer_box(self):
        QtWidgets = self.QtWidgets
        box = QtWidgets.QGroupBox("Offer storage on this disk")
        box.setObjectName("offerBox")
        lay = QtWidgets.QHBoxLayout(box)
        self.disk_pie = _make_disk_pie(box)
        self.disk_offer: Optional[DiskSlices] = None
        lay.addWidget(self.disk_pie)
        col = QtWidgets.QVBoxLayout()
        self.offer_percent = QtWidgets.QLabel("Offering 0% of this disk")
        self.offer_percent.setObjectName("offerPercent")
        font = self.offer_percent.font()
        font.setPointSize(13)
        font.setBold(True)
        self.offer_percent.setFont(font)
        self.offer_percent.setWordWrap(True)
        col.addWidget(self.offer_percent)
        self.offer_legend = QtWidgets.QLabel("Used  ·  Free  ·  Offered")
        self.offer_legend.setObjectName("offerLegend")
        self.offer_legend.setWordWrap(True)
        col.addWidget(self.offer_legend)
        hint = QtWidgets.QLabel(
            "Offered is free space on this disk that this device will store for the friendnet."
        )
        hint.setObjectName("offerHint")
        hint.setWordWrap(True)
        col.addWidget(hint)
        slider_row = QtWidgets.QHBoxLayout()
        slider_row.addWidget(QtWidgets.QLabel("Offer"))
        self.offer_slider = QtWidgets.QSlider(self.QtCore.Qt.Horizontal)
        self.offer_slider.setObjectName("offerSlider")
        self.offer_slider.setRange(0, 100)
        self.offer_slider.setValue(0)
        self.offer_slider.sliderReleased.connect(self.on_offer_percent_chosen)
        slider_row.addWidget(self.offer_slider, 1)
        col.addLayout(slider_row)
        self.offer_status = QtWidgets.QLabel("")
        self.offer_status.setObjectName("offerStatus")
        self.offer_status.setWordWrap(True)
        col.addWidget(self.offer_status)
        col.addStretch(1)
        lay.addLayout(col, 1)
        return box

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
        self.credit_pending = QtWidgets.QLabel("")
        self.credit_pending.setObjectName("creditPending")
        self.credit_pending.setWordWrap(True)
        self.credit_pending.hide()
        body.addWidget(self.credit_pending)
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
        if result.credit_recovered:
            note += " %d credits re-collected from the issuer (confirmed as you sync)." % result.credit_recovered
        if result.credit_recover_error:
            note += " Credit could not be re-collected yet (%s); Credit → Retry later." % result.credit_recover_error
        note += " Files download from the friendnet as this device (%s)." % result.author_name
        if not self._joined:
            self._enter_main("Connected", result.grid)
        else:
            self.refresh()
        self.show_place(self.folders_tab)
        self.folder_error.setText(note)
        self.recovery_status.setText(note)

    def _build_settings_tab(self) -> None:
        QtWidgets = self.QtWidgets
        sl = QtWidgets.QVBoxLayout(self.settings_tab)
        sl.addWidget(QtWidgets.QLabel("Settings"))
        share_box = QtWidgets.QGroupBox("Invite others")
        share_box.setObjectName("shareBox")
        sb = QtWidgets.QVBoxLayout(share_box)
        share_hint = QtWidgets.QLabel(
            "Share the link or QR. Host the exported page on your I2P eepsite."
        )
        share_hint.setWordWrap(True)
        sb.addWidget(share_hint)
        self.share_url_edit = QtWidgets.QLineEdit()
        self.share_url_edit.setObjectName("shareUrl")
        self.share_url_edit.setReadOnly(True)
        self.share_url_edit.setPlaceholderText("Join a friendnet first")
        sb.addWidget(self.share_url_edit)
        srow = QtWidgets.QHBoxLayout()
        self.copy_share_btn = QtWidgets.QPushButton("Copy link")
        self.copy_share_btn.setObjectName("copyShare")
        self.copy_share_btn.clicked.connect(self.on_copy_share_url)
        self.export_page_btn = QtWidgets.QPushButton("Export I2P page…")
        self.export_page_btn.setObjectName("exportInvitePage")
        self.export_page_btn.clicked.connect(self.on_export_invite_page)
        srow.addWidget(self.copy_share_btn)
        srow.addWidget(self.export_page_btn)
        srow.addStretch(1)
        sb.addLayout(srow)
        self.share_qr = QtWidgets.QLabel("")
        self.share_qr.setObjectName("shareQr")
        self.share_qr.setMinimumSize(160, 160)
        sb.addWidget(self.share_qr)
        sl.addWidget(share_box)
        self._refresh_share()
        note = QtWidgets.QLabel(
            "Join links are I2P pages (secret in the #fragment). Folder sync may still "
            "use LAN/WAN.\n\n"
            "Coming later\n"
            "· .deb package (AppImage / macOS / Windows installers ship now)\n\n"
            "This device offers disk on Join unless you uncheck it. The pie on Folders "
            "is how much of this disk that is. Reachable from other machines only if "
            "LEASEGRID_STORAGE_HOSTNAME is a LAN name or IP (lab default is 127.0.0.1).\n\n"
            "About\n"
            "%s (buyer) · version %s\n"
            "Grid: lab-friendnet"
            % (APP_NAME, __version__)
        )
        note.setWordWrap(True)
        note.setObjectName("settingsNote")
        sl.addWidget(note)
        self.payment_lecture = QtWidgets.QLabel(
            "This friendnet charges for storage.\n"
            "Credit → Top up quotes XMR. Open Credit from More to see the balance."
        )
        self.payment_lecture.setWordWrap(True)
        self.payment_lecture.setObjectName("paymentLecture")
        self.payment_lecture.hide()
        sl.addWidget(self.payment_lecture)
        sl.addStretch(1)

    def on_join_details(self) -> None:
        QtWidgets = self.QtWidgets
        dlg = QtWidgets.QDialog(self.win)
        dlg.setWindowTitle("What's a friendnet?")
        dlg.setObjectName("joinDetailsDialog")
        lay = QtWidgets.QVBoxLayout(dlg)
        lab = QtWidgets.QLabel(THREAT_COPY)
        lab.setWordWrap(True)
        lab.setObjectName("threatCopy")
        lay.addWidget(lab)
        close = QtWidgets.QPushButton("Close")
        close.clicked.connect(dlg.accept)
        lay.addWidget(close)
        dlg.exec_()

    def current_share_url(self) -> str:
        from .invite import share_url_for_nodedir

        try:
            return share_url_for_nodedir(self.tahoe.nodedir)
        except SyncError:
            return ""

    def _refresh_share(self) -> None:
        url = self.current_share_url()
        self.share_url_edit.setText(url)
        self.share_url_edit.setCursorPosition(0)
        self.share_url_edit.setToolTip(url)
        self.copy_share_btn.setEnabled(bool(url))
        self.export_page_btn.setEnabled(bool(url))
        if not url:
            self.share_qr.clear()
            return
        try:
            from .invite import qr_png

            pix = self.QtGui.QPixmap()
            pix.loadFromData(qr_png(url))
            self.share_qr.setPixmap(pix.scaled(160, 160, self.QtCore.Qt.KeepAspectRatio))
        except Exception:
            self.share_qr.setText("QR unavailable")

    def on_copy_share_url(self) -> None:
        url = self.share_url_edit.text().strip() or self.current_share_url()
        if url:
            self.QtWidgets.QApplication.clipboard().setText(url)

    def on_export_invite_page(self) -> None:
        url = self.current_share_url()
        if not url:
            return
        path, _ = self.QtWidgets.QFileDialog.getSaveFileName(
            self.win, "Export I2P invite page", str(Path.home() / "join.html"), "HTML (*.html)"
        )
        if not path:
            return
        from .invite import invite_page_html

        Path(path).write_text(invite_page_html(url), encoding="utf-8")

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
        self.tray_credit_action = menu.addAction("Credit")
        self.tray_credit_action.triggered.connect(self.open_credit_place)
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
        """The window is the app. X quits; hiding to tray looked like a crash."""
        event.accept()
        self.quit()

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
        if getattr(self, "_quitting", False):
            return
        self._quitting = True
        self.poll.stop()
        self.shutdown()
        self.app.quit()

    def show_join_error(self, err: SyncError) -> None:
        self.join_error.setText(err.banner())

    def show_unexpected(self, exc: BaseException, log_path: Optional[Path] = None) -> None:
        """One in-window REVIEW banner for an exception no place-specific handler caught."""
        err = unexpected_error(exc, "Leasegrid Sync kept running, but the last action failed.")
        self.status_chip.setText("REVIEW  " + err.message.split(" Unexpected error: ")[-1])
        text = err.banner()
        if log_path is not None:
            text += "\nLog: %s" % log_path
        self.unexpected_review.setText(text)
        self.unexpected_review.show()

    def show_folder_error(self, err: SyncError, open_credit: bool = False) -> None:
        self.folder_error.setStyleSheet("color: #8b1a1a;")
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
        self._join_busy(True, "Tahoe node found at %s — connecting…" % self.tahoe.nodedir)
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
        self.import_key_btn.setEnabled(not busy)
        self.details_btn.setEnabled(not busy)
        self.invite_edit.setEnabled(not busy)
        self.offer_storage_cb.setEnabled(not busy)
        self.join_progress.setText(text)
        self.QtWidgets.QApplication.processEvents()

    def on_join_invite(self) -> None:
        self.clear_errors()
        invite = self.invite_edit.text()
        offer = self.offer_storage_cb.isChecked()
        kind = "sync + storage" if offer else "sync only"
        progress = (
            "Joining… starting this Tahoe node (%s) and waiting for the introducer "
            "(this can take up to a minute the first time)." % kind
        )
        if self.tahoe.has_nodedir():
            progress = "Connecting to the existing Tahoe node…"
        elif is_wormhole_code(invite):
            progress = (
                "Joining… collecting the friendnet settings behind code %s from your "
                "inviter, then starting this Tahoe node (%s)."
                % (invite.strip().lower(), kind)
            )
        self._join_busy(True, progress)
        try:
            status = self.tahoe.join_invite(invite, offer_storage=offer)
        except SyncError as exc:
            self._join_busy(False)
            self.show_join_error(exc)
            return
        self._join_busy(False)
        self._enter_main(status.state, status.detail)

    def on_join_existing(self) -> None:
        self.clear_errors()
        self._join_busy(True, "Connecting to the existing Tahoe node…")
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
        st = self.tahoe.connection_status()
        self.status_chip.setText(format_status_chip(st) if st.state else "%s  %s" % (state, detail))
        self.stack.setCurrentWidget(self.main_page)
        self.show_place(self.folders_tab)
        self._sync_gated_chrome()
        self.poll.start()
        self._refresh_share()
        self.refresh()

    def _sync_gated_chrome(self) -> None:
        """Payment lecture stays hidden until this friendnet charges."""
        gated = credit_enforced()
        if getattr(self, "credit_action", None) is not None:
            self.credit_action.setVisible(gated)
        tray_act = getattr(self, "tray_credit_action", None)
        if tray_act is not None:
            tray_act.setVisible(gated)
        lecture = getattr(self, "payment_lecture", None)
        if lecture is not None:
            lecture.setVisible(gated)

    def _refresh_offer_viz(self) -> None:
        try:
            slices = read_disk_offer(self.tahoe.nodedir, self.home)
        except SyncError as exc:
            self._show_offer_fail(exc)
            return
        except Exception as exc:
            self._log_exception("offer-pie", exc)
            self._show_offer_fail(unexpected_error(exc, "could not read this disk."))
            return
        self._show_offer_slices(slices, saved=False)

    def _show_offer_fail(self, err: SyncError) -> None:
        self.disk_offer = None
        self.disk_pie.set_slices(None)
        self.offer_percent.setText("% of this disk")
        self.offer_legend.setText("Used  ·  Free  ·  Offered")
        self.offer_status.setStyleSheet("color: #8b1a1a;")
        self.offer_status.setText(err.banner())

    def _show_offer_slices(self, slices: DiskSlices, saved: bool) -> None:
        self.disk_offer = slices
        self.disk_pie.set_slices(slices)
        self.offer_percent.setText("Offering %d%% of this disk" % slices.offered_percent)
        self.offer_legend.setText(
            "Used %s  ·  Free %s  ·  Offered %s"
            % (format_bytes(slices.used), format_bytes(slices.kept), format_bytes(slices.offered))
        )
        if not self.offer_slider.isSliderDown():
            self.offer_slider.blockSignals(True)
            self.offer_slider.setValue(slices.offered_percent)
            self.offer_slider.blockSignals(False)
        self.offer_status.setStyleSheet("")
        if saved:
            self.offer_status.setText(
                "Saved. This device will offer %d%% of this disk." % slices.offered_percent
            )
        else:
            self.offer_status.setText("")

    def on_offer_percent_chosen(self) -> None:
        percent = self.offer_slider.value()
        try:
            slices = apply_offer_percent(self.tahoe.nodedir, self.home, percent)
        except SyncError as exc:
            self._refresh_offer_viz()
            self.offer_status.setStyleSheet("color: #8b1a1a;")
            self.offer_status.setText(exc.banner())
            return
        except Exception as exc:
            self._log_exception("offer-percent", exc)
            self._refresh_offer_viz()
            self.offer_status.setStyleSheet("color: #8b1a1a;")
            self.offer_status.setText(unexpected_error(exc, "could not offer disk.").banner())
            return
        self._show_offer_slices(slices, saved=True)

    def refresh(self) -> None:
        if not self._joined:
            return
        status = self.tahoe.connection_status()
        self.status_chip.setText(format_status_chip(status))
        self._refresh_offer_viz()
        try:
            rows = self.mf.list_folders()
        except SyncError as exc:
            self.show_folder_error(exc)
            return
        except Exception as exc:
            self._log_exception("refresh", exc)
            self.show_folder_error(unexpected_error(exc, "could not list folders."))
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
        if credit_enforced() and credit_gate(remaining, 0) == "zero":
            self.show_folder_error(SyncError(ZERO_FOLDER_MSG, ZERO_FOLDER_NEXT), open_credit=True)
            return
        path = QtWidgets.QFileDialog.getExistingDirectory(
            self.win, "Choose a local folder to sync", str(Path.home())
        )
        if not path:
            return
        need = self.credit.estimate_tokens(Path(path))
        gate = credit_gate(remaining, need) if credit_enforced() else "ok"
        if gate == "zero":
            self.show_folder_error(SyncError(ZERO_FOLDER_MSG, ZERO_FOLDER_NEXT), open_credit=True)
            return
        if gate == "review":
            if not self._review_expansion(need, remaining):
                return
        self.folder_error.setStyleSheet("")
        self.folder_error.setText("Adding folder… first time can take a minute.")
        self.QtWidgets.QApplication.processEvents()
        try:
            name = self.mf.add_folder(path)
        except SyncError as exc:
            # A gated node refusing the folder's directories surfaces as a Magic
            # Folder 500; the spender's event tells the real story.
            if not self._show_refusal_if_any():
                self.show_folder_error(exc)
            return
        except Exception as exc:
            self._log_exception("on_add_folder", exc)
            self.show_folder_error(unexpected_error(exc, "folder not added."))
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

    def show_place(self, widget) -> None:
        self.places.setCurrentWidget(widget)

    def open_credit_place(self) -> None:
        self.show()
        if self.stack.currentWidget() is not self.main_page:
            return
        if self.places.currentWidget() is self.credit_tab:
            self.load_credit()
            return
        self.show_place(self.credit_tab)

    def _on_place_changed(self, idx: int) -> None:
        widget = self.places.widget(idx)
        self.back_btn.setVisible(widget is not self.folders_tab)
        if not self._joined:
            return
        if widget is self.credit_tab:
            self.load_credit()
        elif widget is self.settings_tab:
            self._refresh_share()

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
            self._show_credit_error(exc)
            return
        except Exception as exc:  # a slot must never let this reach Qt (PyQt5 aborts)
            self._log_exception("load_credit", exc)
            self._show_credit_error(unexpected_error(exc, "could not load credit balance."))
            return
        self.apply_credit_snapshot(snap)

    def _show_credit_error(self, exc: SyncError) -> None:
        self.credit_loading.hide()
        self.credit_body.hide()
        self.credit_error.setText(exc.banner())
        self.credit_error.show()
        self.credit_retry_btn.show()

    def _log_exception(self, where: str, exc: BaseException) -> Path:
        return log_exception(self.home, where, exc)

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
        self._render_pending()

    def _render_pending(self) -> None:
        pending = []
        try:
            pending = self.credit.pending_topups()
        except Exception:
            pending = []
        if not pending:
            self.credit_pending.hide()
            self.credit_pending.setText("")
            return
        lines = ["Pending"]
        for row in pending:
            state = str(row.get("state") or "waiting")
            n = row.get("tokens_quoted") or row.get("n") or "?"
            amt = row.get("amount_xmr") or ""
            extra = (" · %s XMR" % amt) if amt else ""
            lines.append("· %s · %s credits%s" % (state, n, extra))
        self.credit_pending.setText("\n".join(lines))
        self.credit_pending.show()

    def on_top_up(self) -> None:
        dlg = TopUpDialog(self.win, self.credit, self.QtWidgets)
        result = dlg.dlg.exec_()
        self._apply_topup_result(dlg, result)

    def _apply_topup_result(self, dlg: TopUpDialog, result) -> None:
        if result == self.QtWidgets.QDialog.Accepted and dlg.snapshot is not None:
            note = "Top-up complete.\n" + dlg.snapshot.remaining_text
            self.apply_credit_snapshot(dlg.snapshot, success_note=note)
            return
        self._render_pending()

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
    offer_storage: bool = True,
) -> int:
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    ui = MainWindow(nodedir=nodedir, issuer_url=issuer_url, autoload=False)
    install_excepthook(ui)
    ui.show()
    ui.QtWidgets.QApplication.processEvents()
    try:
        if invite:
            # Headless join first (creates + starts the node); the modes below then
            # attach to it as an existing node and quit stops what we started.
            try:
                ui.tahoe.join_invite(invite.strip(), offer_storage=offer_storage)
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
        if dogfood_folder is None:
            return 0
        # both flags: top up first, then the upload that spends it (paid-path CI)
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
