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
from .servers import (
    SERVERS_HONESTY,
    ServerRow,
    add_storage_server,
    disconnect_copy,
    disconnect_server,
    roster,
    use_available_server,
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
JOIN_THREAT_ACK = "I understand the four points above."
JOIN_ACK_MSG = "could not join this friendnet. The four points above are not acknowledged."
JOIN_ACK_NEXT = "check “I understand the four points above.”, then Join."


def _qt_api():
    from PyQt5 import QtCore, QtGui, QtWidgets

    return QtCore, QtGui, QtWidgets


def _style_primary(btn) -> None:
    """Filled weight for lead-journey CTAs. Not a theme rebrand."""
    btn.setMinimumHeight(36)
    btn.setStyleSheet(
        "QPushButton { background-color: #1f6feb; color: white; padding: 8px 16px;"
        " font-weight: 600; border: none; border-radius: 6px; }"
        "QPushButton:disabled { background-color: #b9cbe8; color: #f7f9fc; }"
    )


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
    """U5 (§11): choose a tier → quote → pay → poll → redeem. No faucet button."""

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
        self.cancel_btn = QtWidgets.QPushButton("Cancel")
        self.cancel_btn.setObjectName("topUpCancel")
        self.cancel_btn.clicked.connect(self.dlg.reject)
        row.addWidget(self.continue_btn)
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
        self.cancel_btn.setText("Close")
        self.status.setText("Waiting for payment…")
        self._start_poll()
        self._submit_lab_payment()

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

    def _submit_lab_payment(self) -> None:
        """FakeChain pays the quote here. Stagenet pays when a wallet-rpc is set.

        With no payer configured, the quote stays on screen for an external
        stagenet wallet. Mainnet is refused inside pay_quote.
        """
        pay = getattr(self.credit, "pay_quote", None)
        if pay is None or not self.quote:
            return
        try:
            result = pay(self.quote)
        except SyncError as exc:
            self.status.setStyleSheet("color: #8b1a1a;")
            self.status.setText(exc.banner())
            return
        except Exception:
            self.status.setStyleSheet("color: #8b1a1a;")
            self.status.setText(
                "REVIEW — Could not submit this payment. Payments already sent are safe; retry later."
            )
            return
        if isinstance(result, dict) and result.get("skipped"):
            return
        self.status.setStyleSheet("")
        self.status.setText("Payment submitted. Collecting your credits…")


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


class InviteSharePanel:
    """#32 share card: short code + QR + Copy. Join link stays collapsed."""

    def __init__(self, layout, window: "MainWindow", qt, names: dict) -> None:
        QtWidgets = qt
        self.window = window
        self.QtWidgets = QtWidgets
        intro = QtWidgets.QLabel(
            "Invite someone to join this friendnet "
            "(they can Offer disk so you get more storage)."
        )
        intro.setWordWrap(True)
        intro.setObjectName(names.get("intro", "inviteShareIntro"))
        layout.addWidget(intro)
        self.qr = QtWidgets.QLabel("")
        self.qr.setObjectName(names["qr"])
        self.qr.setMinimumSize(160, 160)
        self.qr.setAlignment(window.QtCore.Qt.AlignLeft | window.QtCore.Qt.AlignVCenter)
        layout.addWidget(self.qr)
        layout.addWidget(QtWidgets.QLabel("Short code"))
        self.code_edit = QtWidgets.QLineEdit()
        self.code_edit.setObjectName(names["code"])
        self.code_edit.setReadOnly(True)
        self.code_edit.setPlaceholderText("7-word-word")
        font = self.code_edit.font()
        font.setPointSize(14)
        font.setBold(True)
        self.code_edit.setFont(font)
        layout.addWidget(self.code_edit)
        self.copy_btn = QtWidgets.QPushButton("Copy code")
        self.copy_btn.setObjectName(names["copy"])
        self.copy_btn.setAutoDefault(False)
        _style_primary(self.copy_btn)
        self.copy_btn.clicked.connect(self.on_copy)
        layout.addWidget(self.copy_btn)
        self.advanced = QtWidgets.QCheckBox("Show full join link (advanced)")
        self.advanced.setObjectName(names["advanced"])
        self.advanced.toggled.connect(self._on_advanced)
        layout.addWidget(self.advanced)
        self.join_link = QtWidgets.QLineEdit()
        self.join_link.setObjectName(names["link"])
        self.join_link.setReadOnly(True)
        self.join_link.hide()
        layout.addWidget(self.join_link)
        self.status = QtWidgets.QLabel("")
        self.status.setObjectName(names["status"])
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

    def _on_advanced(self, checked: bool) -> None:
        self.join_link.setVisible(bool(checked))

    def on_copy(self) -> None:
        self.present(copy=True)

    def present(self, copy: bool = False) -> None:
        self.status.setStyleSheet("")
        self.status.setText("Creating invite code…")
        self.QtWidgets.QApplication.processEvents()
        try:
            code, url = self.window.ensure_invite_code()
        except SyncError as exc:
            self.status.setStyleSheet("color: #8b1a1a;")
            self.status.setText(exc.banner())
            self.code_edit.clear()
            self.qr.clear()
            self.qr.setText("")
            return
        except Exception as exc:
            self.window._log_exception("invite-share", exc)
            self.status.setStyleSheet("color: #8b1a1a;")
            self.status.setText(unexpected_error(exc, "could not share this invite.").banner())
            return
        self.code_edit.setText(code)
        self.code_edit.setCursorPosition(0)
        self.join_link.setText(url)
        self.join_link.setCursorPosition(0)
        self.join_link.setToolTip(url)
        self._paint_qr(code)
        if copy:
            self.QtWidgets.QApplication.clipboard().setText(code)
            self.status.setStyleSheet("")
            self.status.setText(
                "Invite code copied. Keep Sync open until they join. "
                "They appear under Storage servers when ready."
            )
        else:
            self.status.setStyleSheet("")
            self.status.setText(
                "Wait for them to Join (+ Offer if storing for you). "
                "They appear under Storage servers when ready."
            )

    def show_existing(self, code: str, url: str) -> None:
        """Paint a code this window already created. Does not start Tahoe."""
        if code:
            self.code_edit.setText(code)
            self.code_edit.setCursorPosition(0)
            self._paint_qr(code)
        if url:
            self.join_link.setText(url)
            self.join_link.setCursorPosition(0)
            self.join_link.setToolTip(url)

    def _paint_qr(self, payload: str) -> None:
        try:
            from .invite import qr_png

            pix = self.window.QtGui.QPixmap()
            if not pix.loadFromData(qr_png(payload)) or pix.isNull():
                raise RuntimeError("empty qr")
            self.qr.setText("")
            self.qr.setPixmap(
                pix.scaled(160, 160, self.window.QtCore.Qt.KeepAspectRatio)
            )
        except Exception:
            self.qr.setText("QR unavailable")


class InviteShareDialog:
    """Folders / More entry for the same short-code share card."""

    def __init__(self, parent, window: "MainWindow", qt) -> None:
        QtWidgets = qt
        self.dlg = QtWidgets.QDialog(parent)
        self.dlg.setWindowTitle("Share invite")
        self.dlg.setObjectName("inviteShareDialog")
        self.dlg.setModal(True)
        v = QtWidgets.QVBoxLayout(self.dlg)
        v.setContentsMargins(24, 20, 24, 20)
        self.panel = InviteSharePanel(
            v,
            window,
            qt,
            {
                "intro": "inviteDialogIntro",
                "qr": "inviteDialogQr",
                "code": "inviteDialogCode",
                "copy": "inviteDialogCopy",
                "advanced": "inviteDialogAdvanced",
                "link": "inviteDialogLink",
                "status": "inviteDialogStatus",
            },
        )
        brow = QtWidgets.QHBoxLayout()
        brow.addStretch(1)
        done = QtWidgets.QPushButton("Done")
        done.setObjectName("inviteDialogDone")
        done.setAutoDefault(False)
        done.clicked.connect(self.dlg.accept)
        brow.addWidget(done)
        v.addLayout(brow)
        self.panel.present()


class AddStorageServerDialog:
    """Add storage: invite someone to Offer disk, or paste a storage furl."""

    def __init__(self, parent, window: "MainWindow", qt) -> None:
        QtWidgets = qt
        self.QtWidgets = QtWidgets
        self.window = window
        self.dlg = QtWidgets.QDialog(parent)
        self.dlg.setWindowTitle("Add storage server")
        self.dlg.setObjectName("addStorageDialog")
        self.dlg.setModal(True)
        v = QtWidgets.QVBoxLayout(self.dlg)
        prompt = QtWidgets.QLabel("How do you want to add storage?")
        prompt.setObjectName("addStoragePrompt")
        v.addWidget(prompt)

        self.invite_radio = QtWidgets.QRadioButton("Invite someone to Offer disk")
        self.invite_radio.setObjectName("addPathInvite")
        self.invite_radio.setChecked(True)
        v.addWidget(self.invite_radio)
        invite_hint = QtWidgets.QLabel(
            "Share a short code or QR so their computer can store shares."
        )
        invite_hint.setWordWrap(True)
        invite_hint.setObjectName("addInviteHint")
        v.addWidget(invite_hint)
        self.invite_panel = InviteSharePanel(
            v,
            window,
            qt,
            {
                "intro": "addInviteIntro",
                "qr": "addInviteQr",
                "code": "addInviteCode",
                "copy": "copyInviteButton",
                "advanced": "addShowJoinLink",
                "link": "addInviteJoinLink",
                "status": "addInviteStatus",
            },
        )
        self.copy_invite_btn = self.invite_panel.copy_btn
        self.invite_status = self.invite_panel.status
        self.invite_panel.present()

        self.paste_radio = QtWidgets.QRadioButton("Paste a server link")
        self.paste_radio.setObjectName("addPathPaste")
        v.addWidget(self.paste_radio)
        self.paste_hint = QtWidgets.QLabel(
            "Paste a storage server link (pb://…) from a host you trust."
        )
        self.paste_hint.setWordWrap(True)
        self.paste_hint.setObjectName("addPasteHint")
        v.addWidget(self.paste_hint)
        v.addWidget(QtWidgets.QLabel("Server link"))
        self.furl_edit = QtWidgets.QLineEdit()
        self.furl_edit.setObjectName("storageFurlEdit")
        self.furl_edit.setPlaceholderText("pb://…")
        v.addWidget(self.furl_edit)
        v.addWidget(QtWidgets.QLabel("Nickname (optional)"))
        self.nick_edit = QtWidgets.QLineEdit()
        self.nick_edit.setObjectName("storageNickEdit")
        self.nick_edit.setPlaceholderText("home-nas")
        v.addWidget(self.nick_edit)
        self.error = QtWidgets.QLabel("")
        self.error.setObjectName("addStorageError")
        self.error.setWordWrap(True)
        self.error.setStyleSheet("color: #8b1a1a;")
        v.addWidget(self.error)
        brow = QtWidgets.QHBoxLayout()
        cancel = QtWidgets.QPushButton("Cancel")
        cancel.setObjectName("addStorageCancel")
        cancel.setAutoDefault(False)
        cancel.clicked.connect(self.dlg.reject)
        self.add_btn = QtWidgets.QPushButton("Add server")
        self.add_btn.setObjectName("addServerButton")
        self.add_btn.setAutoDefault(False)
        self.add_btn.clicked.connect(self.on_add)
        brow.addWidget(cancel)
        brow.addStretch(1)
        brow.addWidget(self.add_btn)
        v.addLayout(brow)

    def on_copy_invite(self) -> None:
        self.invite_panel.on_copy()

    def on_add(self) -> None:
        self.error.setText("")
        furl = self.furl_edit.text()
        self.add_btn.setEnabled(False)
        self.QtWidgets.QApplication.processEvents()
        try:
            add_storage_server(
                self.window.home,
                self.window.tahoe.nodedir,
                furl,
                self.nick_edit.text(),
            )
            self.window.tahoe.reload_static_servers()
        except SyncError as exc:
            self.error.setText(exc.banner())
            self.add_btn.setText("Retry")
            self.add_btn.setEnabled(True)
            return
        except Exception as exc:
            self.window._log_exception("add-storage", exc)
            self.error.setText(unexpected_error(exc, "could not add this storage server.").banner())
            self.add_btn.setText("Retry")
            self.add_btn.setEnabled(True)
            return
        self.dlg.accept()


class DisconnectServerDialog:
    """Confirm Disconnect. Copy is local to this Sync home."""

    def __init__(self, parent, qt, name: str) -> None:
        QtWidgets = qt
        self.dlg = QtWidgets.QDialog(parent)
        self.dlg.setWindowTitle("Disconnect storage server?")
        self.dlg.setObjectName("disconnectServerDialog")
        self.dlg.setModal(True)
        v = QtWidgets.QVBoxLayout(self.dlg)
        self.copy = QtWidgets.QLabel(disconnect_copy(name))
        self.copy.setObjectName("disconnectCopy")
        self.copy.setWordWrap(True)
        v.addWidget(self.copy)
        brow = QtWidgets.QHBoxLayout()
        cancel = QtWidgets.QPushButton("Cancel")
        cancel.setObjectName("disconnectCancel")
        cancel.setAutoDefault(False)
        cancel.clicked.connect(self.dlg.reject)
        ok = QtWidgets.QPushButton("Disconnect")
        ok.setObjectName("confirmDisconnect")
        ok.setAutoDefault(False)
        ok.clicked.connect(self.dlg.accept)
        brow.addWidget(cancel)
        brow.addStretch(1)
        brow.addWidget(ok)
        v.addLayout(brow)


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
        self._joining = False
        self._credit_loaded = False
        self._invite_session = None

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
        intro = QtWidgets.QLabel("Paste a short code, join link, or text from a QR.")
        intro.setWordWrap(True)
        intro.setObjectName("joinIntro")
        v.addWidget(intro)
        threat_box = QtWidgets.QGroupBox("Please read before you join")
        threat_box.setObjectName("threatBlock")
        tb = QtWidgets.QVBoxLayout(threat_box)
        threat = QtWidgets.QLabel(THREAT_COPY)
        threat.setWordWrap(True)
        threat.setObjectName("threatCopy")
        tb.addWidget(threat)
        self.threat_ack = QtWidgets.QCheckBox(JOIN_THREAT_ACK)
        self.threat_ack.setObjectName("threatAck")
        self.threat_ack.toggled.connect(self._on_join_threat_toggled)
        tb.addWidget(self.threat_ack)
        v.addWidget(threat_box)
        invite_label = QtWidgets.QLabel("Invite")
        invite_label.setObjectName("inviteFieldLabel")
        v.addWidget(invite_label)
        self.invite_edit = QtWidgets.QLineEdit()
        self.invite_edit.setPlaceholderText("7-word-word or join link")
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
        self.join_btn.setEnabled(False)
        _style_primary(self.join_btn)
        self.join_btn.clicked.connect(self.on_join_invite)
        v.addWidget(self.join_btn)
        self.existing_btn = QtWidgets.QPushButton("Use existing Tahoe node")
        self.existing_btn.setObjectName("existingButton")
        self.existing_btn.setFlat(True)
        self.existing_btn.setAutoDefault(False)
        self.existing_btn.setEnabled(False)
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
        v.setContentsMargins(16, 12, 16, 16)
        v.setSpacing(10)
        chrome = QtWidgets.QHBoxLayout()
        chrome.setSpacing(8)
        self.status_chip = QtWidgets.QPushButton("Connecting…")
        self.status_chip.setObjectName("statusChip")
        self.status_chip.setFlat(True)
        self.status_chip.setAutoDefault(False)
        self.status_chip.setCursor(self.QtCore.Qt.PointingHandCursor)
        self.status_chip.setToolTip("Open Storage servers")
        self.status_chip.clicked.connect(self.open_storage_servers)
        self.back_btn = QtWidgets.QPushButton("Folders")
        self.back_btn.setObjectName("backToFolders")
        self.back_btn.setAutoDefault(False)
        self.back_btn.clicked.connect(lambda: self.show_place(self.folders_tab))
        chrome.addWidget(self.back_btn)
        self.servers_nav_btn = QtWidgets.QPushButton("Storage servers")
        self.servers_nav_btn.setObjectName("storageServersNav")
        self.servers_nav_btn.setFlat(True)
        self.servers_nav_btn.setAutoDefault(False)
        self.servers_nav_btn.clicked.connect(self.open_storage_servers)
        chrome.addWidget(self.servers_nav_btn)
        chrome.addStretch(1)
        chrome.addWidget(self.status_chip)
        self.more_btn = QtWidgets.QToolButton()
        self.more_btn.setText("More")
        self.more_btn.setObjectName("moreButton")
        self.more_btn.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        more = QtWidgets.QMenu(self.more_btn)
        more.setObjectName("moreMenu")
        self.invite_action = more.addAction("Invite…")
        self.invite_action.setObjectName("invitePlaceAction")
        self.invite_action.triggered.connect(self.open_invite_share)
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
        self.servers_tab = QtWidgets.QWidget()
        self.servers_tab.setObjectName("storageServersTab")
        self.credit_tab = QtWidgets.QWidget()
        self.credit_tab.setObjectName("creditTab")
        self.recovery_tab = QtWidgets.QWidget()
        self.recovery_tab.setObjectName("recoveryTab")
        self.settings_tab = QtWidgets.QWidget()
        self.places.addWidget(self.folders_tab)
        self.places.addWidget(self.servers_tab)
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
        _style_primary(self.add_btn)
        self.add_btn.clicked.connect(self.on_add_folder)
        head.addWidget(self.add_btn)
        fl.addLayout(head)
        host_row = QtWidgets.QHBoxLayout()
        self.hosts_line = QtWidgets.QLabel("Hosts: none connected yet")
        self.hosts_line.setObjectName("hostsLine")
        self.manage_servers_btn = QtWidgets.QPushButton("Manage storage servers")
        self.manage_servers_btn.setObjectName("manageServersButton")
        self.manage_servers_btn.setAutoDefault(False)
        self.manage_servers_btn.clicked.connect(self.open_storage_servers)
        host_row.addWidget(self.hosts_line)
        host_row.addWidget(self.manage_servers_btn)
        host_row.addStretch(1)
        fl.addLayout(host_row)
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
        invite_row = QtWidgets.QHBoxLayout()
        invite_row.setContentsMargins(0, 8, 0, 4)
        invite_note = QtWidgets.QLabel("Invite a friend to store files?")
        invite_note.setObjectName("shareInviteNote")
        self.share_invite_btn = QtWidgets.QPushButton("Share invite")
        self.share_invite_btn.setObjectName("shareInviteButton")
        self.share_invite_btn.setAutoDefault(False)
        self.share_invite_btn.clicked.connect(self.open_invite_share)
        invite_row.addWidget(invite_note)
        invite_row.addWidget(self.share_invite_btn)
        invite_row.addStretch(1)
        fl.addLayout(invite_row)
        fl.addWidget(self._build_recovery_nudge())

        self._build_servers_tab()
        self._build_credit_tab()
        self._build_recovery_tab()
        self._build_settings_tab()
        self._sync_gated_chrome()
        return page

    def _build_servers_tab(self) -> None:
        QtWidgets = self.QtWidgets
        sl = QtWidgets.QVBoxLayout(self.servers_tab)
        title = QtWidgets.QLabel("Storage servers")
        title.setObjectName("storageServersTitle")
        font = title.font()
        font.setPointSize(14)
        font.setBold(True)
        title.setFont(font)
        sl.addWidget(title)
        sub = QtWidgets.QLabel("Where your files' shares are stored.")
        sub.setObjectName("storageServersSubtitle")
        sub.setWordWrap(True)
        sl.addWidget(sub)
        self.add_storage_btn = QtWidgets.QPushButton("+ Add storage server")
        self.add_storage_btn.setObjectName("addStorageButton")
        self.add_storage_btn.setAutoDefault(False)
        _style_primary(self.add_storage_btn)
        self.add_storage_btn.clicked.connect(self.on_add_storage)
        sl.addWidget(self.add_storage_btn)
        self.servers_empty = QtWidgets.QLabel(
            "No storage servers connected yet.\n\n"
            "Add a computer that stores your files' shares."
        )
        self.servers_empty.setObjectName("serversEmpty")
        self.servers_empty.setWordWrap(True)
        self.servers_empty.hide()
        sl.addWidget(self.servers_empty)
        self.servers_used_title = QtWidgets.QLabel("Used by this Sync home")
        self.servers_used_title.setObjectName("serversUsedTitle")
        sl.addWidget(self.servers_used_title)
        self.servers_used_box = QtWidgets.QWidget()
        self.servers_used_box.setObjectName("serversUsed")
        self.servers_used_lay = QtWidgets.QVBoxLayout(self.servers_used_box)
        self.servers_used_lay.setContentsMargins(0, 0, 0, 0)
        sl.addWidget(self.servers_used_box)
        self.servers_avail_title = QtWidgets.QLabel("Available on friendnet (not used yet)")
        self.servers_avail_title.setObjectName("serversAvailableTitle")
        sl.addWidget(self.servers_avail_title)
        self.servers_avail_box = QtWidgets.QWidget()
        self.servers_avail_box.setObjectName("serversAvailable")
        self.servers_avail_lay = QtWidgets.QVBoxLayout(self.servers_avail_box)
        self.servers_avail_lay.setContentsMargins(0, 0, 0, 0)
        sl.addWidget(self.servers_avail_box)
        self.servers_error = QtWidgets.QLabel("")
        self.servers_error.setObjectName("serversError")
        self.servers_error.setWordWrap(True)
        self.servers_error.setStyleSheet("color: #8b1a1a;")
        sl.addWidget(self.servers_error)
        honesty = QtWidgets.QLabel(SERVERS_HONESTY)
        honesty.setObjectName("serversHonesty")
        honesty.setWordWrap(True)
        sl.addWidget(honesty)
        sl.addStretch(1)

    def _clear_layout(self, layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    def _add_server_row(self, layout, row: ServerRow) -> None:
        QtWidgets = self.QtWidgets
        wrap = QtWidgets.QWidget()
        wrap.setObjectName("serverRow")
        outer = QtWidgets.QVBoxLayout(wrap)
        outer.setContentsMargins(0, 4, 0, 4)
        top = QtWidgets.QHBoxLayout()
        name = QtWidgets.QLabel(row.name)
        name.setObjectName("serverName")
        status = QtWidgets.QLabel(row.status)
        status.setObjectName("serverStatus")
        source = QtWidgets.QLabel(row.source)
        source.setObjectName("serverSource")
        top.addWidget(name)
        top.addWidget(status)
        top.addWidget(source)
        top.addStretch(1)
        if row.section == "used":
            btn = QtWidgets.QPushButton("Disconnect")
            btn.setObjectName("disconnectServerButton")
            btn.setAutoDefault(False)
            btn.clicked.connect(
                lambda _checked=False, key=row.key, label=row.name: self.on_disconnect_storage(
                    key, label
                )
            )
        else:
            btn = QtWidgets.QPushButton("Add")
            btn.setObjectName("pinServerButton")
            btn.setAutoDefault(False)
            btn.clicked.connect(
                lambda _checked=False, key=row.key, label=row.name: self.on_use_available(
                    key, label
                )
            )
        top.addWidget(btn)
        outer.addLayout(top)
        if row.note:
            note = QtWidgets.QLabel(row.note)
            note.setObjectName("serverNote")
            note.setWordWrap(True)
            outer.addWidget(note)
        layout.addWidget(wrap)

    def _refresh_hosts_line(self, status: ConnectionStatus) -> None:
        n = int(status.servers_connected or 0)
        if n <= 0:
            match = re.search(r"(\d+)\s+storage", status.detail or "")
            n = int(match.group(1)) if match else 0
        if n <= 0:
            self.hosts_line.setText("Hosts: none connected yet")
        elif n == 1:
            self.hosts_line.setText("Hosts: 1 connected")
        else:
            self.hosts_line.setText("Hosts: %d connected" % n)

    def _refresh_servers(self, status: Optional[ConnectionStatus] = None) -> None:
        if not hasattr(self, "servers_used_lay"):
            return
        if status is None:
            status = self.tahoe.connection_status() if self._joined else ConnectionStatus(state="Offline")
        self._refresh_hosts_line(status)
        try:
            used, available = roster(self.home, list(status.announced_servers or []))
        except SyncError as exc:
            self.servers_error.setText(exc.banner())
            return
        self.servers_error.setText("")
        self._clear_layout(self.servers_used_lay)
        self._clear_layout(self.servers_avail_lay)
        for row in used:
            self._add_server_row(self.servers_used_lay, row)
        for row in available:
            self._add_server_row(self.servers_avail_lay, row)
        empty = not used and not available
        self.servers_empty.setVisible(empty)
        self.servers_used_title.setVisible(bool(used))
        self.servers_used_box.setVisible(bool(used))
        self.servers_avail_title.setVisible(bool(available))
        self.servers_avail_box.setVisible(bool(available))

    def open_storage_servers(self) -> None:
        """Folders → Storage servers. No-op before this home has joined."""
        if not self._joined or self.stack.currentWidget() is not self.main_page:
            return
        self.show_place(self.servers_tab)

    def on_add_storage(self) -> None:
        if not self._joined:
            return
        dlg = AddStorageServerDialog(self.win, self, self.QtWidgets)
        if dlg.dlg.exec_() == self.QtWidgets.QDialog.Accepted:
            self.refresh()

    def on_disconnect_storage(self, key: str, name: str) -> None:
        dlg = DisconnectServerDialog(self.win, self.QtWidgets, name)
        if dlg.dlg.exec_() != self.QtWidgets.QDialog.Accepted:
            return
        try:
            disconnect_server(self.home, self.tahoe.nodedir, key, name=name)
            self.tahoe.reload_static_servers()
        except SyncError as exc:
            self.servers_error.setText(exc.banner())
            return
        except Exception as exc:
            self._log_exception("disconnect-storage", exc)
            self.servers_error.setText(
                unexpected_error(exc, "could not disconnect this storage server.").banner()
            )
            return
        self.refresh()

    def on_use_available(self, key: str, name: str) -> None:
        try:
            use_available_server(self.home, self.tahoe.nodedir, key, name)
            self.tahoe.reload_static_servers()
        except SyncError as exc:
            self.servers_error.setText(exc.banner())
            return
        except Exception as exc:
            self._log_exception("use-available", exc)
            self.servers_error.setText(
                unexpected_error(exc, "could not add this storage server.").banner()
            )
            return
        self.refresh()

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

    def _build_recovery_nudge(self):
        """Dismissible export reminder. Does not block Add folder or the Offer slider."""
        QtWidgets = self.QtWidgets
        box = QtWidgets.QWidget()
        box.setObjectName("recoveryNudge")
        lay = QtWidgets.QHBoxLayout(box)
        lay.setContentsMargins(0, 4, 0, 0)
        note = QtWidgets.QLabel("No recovery key exported yet.")
        note.setObjectName("recoveryNudgeNote")
        note.setWordWrap(True)
        lay.addWidget(note, 1)
        export = QtWidgets.QPushButton("Export recovery key…")
        export.setObjectName("nudgeExport")
        export.setAutoDefault(False)
        export.clicked.connect(self.on_export_recovery)
        dismiss = QtWidgets.QPushButton("Dismiss")
        dismiss.setObjectName("nudgeDismiss")
        dismiss.setFlat(True)
        dismiss.setAutoDefault(False)
        dismiss.clicked.connect(self.on_dismiss_recovery_nudge)
        lay.addWidget(export)
        lay.addWidget(dismiss)
        self._refresh_recovery_nudge(box)
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
        self.export_key_btn.setDefault(True)
        self.export_key_btn.clicked.connect(self.on_export_recovery)
        self.import_key_btn2 = QtWidgets.QPushButton("Import recovery key…")
        self.import_key_btn2.setObjectName("importKeyButton2")
        self.import_key_btn2.setAutoDefault(False)
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

    def _refresh_recovery_nudge(self, box=None) -> None:
        widget = box if box is not None else self.win.findChild(self.QtWidgets.QWidget, "recoveryNudge")
        if widget is None:
            return
        show = self.recovery.last_export() is None and not self.recovery.nudge_dismissed()
        widget.setVisible(show)

    def on_dismiss_recovery_nudge(self) -> None:
        self.recovery.dismiss_export_nudge()
        self._refresh_recovery_nudge()

    def on_export_recovery(self) -> None:
        self.recovery_status.setStyleSheet("")
        self.recovery_status.setText("")
        dlg = ExportRecoveryDialog(self.win, self.recovery, self.QtWidgets)
        if dlg.dlg.exec_() == self.QtWidgets.QDialog.Accepted and dlg.written is not None:
            self.recovery_status.setText(
                "Recovery key written to %s. Move it somewhere safe and offline." % dlg.written
            )
            self._refresh_last_export()
            self._refresh_recovery_nudge()

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
        note += " Files will download from the friendnet into %s as this device (%s)." % (
            self.recovery.folder_root,
            result.author_name,
        )
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
            "Share a short code or the QR. They paste it on Join."
        )
        share_hint.setWordWrap(True)
        share_hint.setObjectName("shareHint")
        sb.addWidget(share_hint)
        self.share_panel = InviteSharePanel(
            sb,
            self,
            QtWidgets,
            {
                "intro": "settingsInviteIntro",
                "qr": "shareQr",
                "code": "shareCode",
                "copy": "copyShare",
                "advanced": "showJoinLink",
                "link": "shareUrl",
                "status": "shareStatus",
            },
        )
        self.share_code_edit = self.share_panel.code_edit
        self.share_url_edit = self.share_panel.join_link
        self.share_qr = self.share_panel.qr
        self.copy_share_btn = self.share_panel.copy_btn
        self.export_page_btn = QtWidgets.QPushButton("Export I2P page…")
        self.export_page_btn.setObjectName("exportInvitePage")
        self.export_page_btn.setFlat(True)
        self.export_page_btn.setAutoDefault(False)
        self.export_page_btn.clicked.connect(self.on_export_invite_page)
        sb.addWidget(self.export_page_btn)
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

    def ensure_invite_code(self) -> tuple[str, str]:
        """Live short code plus the advanced join link. Does not copy a raw furl."""
        from .invite import start_invite_code

        url = self.current_share_url()
        if not url:
            raise SyncError(
                "could not share an invite. No friendnet joined yet.",
                "join a friendnet first, then Invite.",
            )
        session = self._invite_session
        if session is not None and session.alive() and session.code:
            return session.code, url
        if session is not None:
            session.close()
            self._invite_session = None
        session = start_invite_code(self.tahoe.nodedir, tahoe_bin=self.tahoe.tahoe_bin)
        self._invite_session = session
        return session.code, url

    def _refresh_share(self) -> None:
        """Fill the collapsed join link. A short code is created on Copy / Share."""
        url = self.current_share_url()
        self.share_url_edit.setText(url)
        self.share_url_edit.setCursorPosition(0)
        self.share_url_edit.setToolTip(url)
        self.copy_share_btn.setEnabled(True)
        self.export_page_btn.setEnabled(bool(url))
        session = self._invite_session
        code = session.code if session is not None and session.alive() else ""
        if code:
            self.share_panel.show_existing(code, url)
        else:
            self.share_code_edit.clear()
            self.share_qr.clear()
            self.share_qr.setText("")

    def on_copy_share_url(self) -> None:
        self.share_panel.on_copy()

    def open_invite_share(self) -> None:
        if not self._joined or self.stack.currentWidget() is not self.main_page:
            return
        dlg = InviteShareDialog(self.win, self, self.QtWidgets)
        dlg.dlg.exec_()

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
        session = getattr(self, "_invite_session", None)
        if session is not None:
            session.close()
            self._invite_session = None
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

    def _on_join_threat_toggled(self, checked: bool) -> None:
        if self._joining:
            return
        self.join_btn.setEnabled(checked)
        self.existing_btn.setEnabled(checked)

    def _join_refused_without_ack(self) -> bool:
        if self.threat_ack.isChecked():
            return False
        self.show_join_error(SyncError(JOIN_ACK_MSG, JOIN_ACK_NEXT))
        return True

    def _join_busy(self, busy: bool, text: str = "") -> None:
        self._joining = busy
        allowed = (not busy) and self.threat_ack.isChecked()
        self.join_btn.setEnabled(allowed)
        self.existing_btn.setEnabled(allowed)
        self.threat_ack.setEnabled(not busy)
        self.import_key_btn.setEnabled(not busy)
        self.details_btn.setEnabled(not busy)
        self.invite_edit.setEnabled(not busy)
        self.offer_storage_cb.setEnabled(not busy)
        self.join_progress.setText(text)
        self.QtWidgets.QApplication.processEvents()

    def on_join_invite(self) -> None:
        self.clear_errors()
        if self._join_refused_without_ack():
            return
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
        if self._join_refused_without_ack():
            return
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
        self._refresh_servers(status)
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

    def _style_place_nav(self, widget) -> None:
        """Folders and Storage servers are the two primary places. Credit stays in More."""
        on_folders = widget is self.folders_tab
        on_servers = widget is self.servers_tab
        self.back_btn.setVisible(True)
        folder_font = self.back_btn.font()
        folder_font.setBold(on_folders)
        self.back_btn.setFont(folder_font)
        self.back_btn.setFlat(not on_folders)
        server_font = self.servers_nav_btn.font()
        server_font.setBold(on_servers)
        self.servers_nav_btn.setFont(server_font)
        self.servers_nav_btn.setFlat(not on_servers)

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
        self._style_place_nav(widget)
        if not self._joined:
            return
        if widget is self.credit_tab:
            self.load_credit()
        elif widget is self.servers_tab:
            self._refresh_servers()
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
        """Join existing friendnet, quote → pay → redeem, show the updated balance."""
        self.clear_errors()
        status = self.tahoe.join_existing()
        self._enter_main(status.state, status.detail)
        before = self.credit.remaining_tokens()
        self.open_credit_place()
        snap = self.credit.complete_topup(int(XMR_TIERS.get(tier, XMR_TIERS["medium"])))
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
