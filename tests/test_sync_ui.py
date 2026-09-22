"""Offscreen Qt smoke: window title, join FAIL in-window, no WUI CTA."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PyQt5 = pytest.importorskip("PyQt5")

from leasegrid_sync import APP_NAME  # noqa: E402
from leasegrid_sync.app import MainWindow, TopUpDialog  # noqa: E402
from leasegrid_sync.backend import ConnectionStatus, SyncError  # noqa: E402
from leasegrid_sync.credit import (  # noqa: E402
    CreditBalance,
    CreditSnapshot,
    OPAQUE_REJECT,
    format_remaining,
)


class FakeCredit:
    def __init__(self, tokens: int = 8) -> None:
        self.tokens = tokens
        self.fail_load = False
        self.fail_redeem = False
        self.fail_quote = False
        self.pubkey = "lab"
        self.refusal = None
        self.quote: dict | None = None
        self.poll: dict | None = None
        self.pending: list = []

    def remaining_tokens(self) -> int:
        return self.tokens

    def recent_refusal(self, within_seconds: float = 120.0):
        return self.refusal

    def load_balance(self) -> CreditSnapshot:
        if self.fail_load:
            raise SyncError(
                "could not load credit balance. Issuer unreachable or returned an error.",
                "Retry; check network; if lab is down, ask your friendnet operator.",
            )
        return CreditSnapshot(
            balance=CreditBalance(tokens=self.tokens, issuer_pubkey_id=self.pubkey),
            remaining_text=format_remaining(self.tokens),
            recent=[],
        )

    def redeem_faucet(self, tier: str = "medium", count=None) -> CreditSnapshot:
        if self.fail_redeem:
            raise SyncError(
                "top-up did not complete. Faucet or issuer rejected the request (or network error).",
                "Retry; if lab is down, ask your operator. Balance unchanged.",
            )
        add = {"small": 10, "medium": 50, "large": 200}.get(tier, count or 50)
        self.tokens += int(add)
        return CreditSnapshot(
            balance=CreditBalance(tokens=self.tokens, issuer_pubkey_id=self.pubkey),
            remaining_text=format_remaining(self.tokens),
            recent=[],
        )

    def estimate_tokens(self, path: Path) -> int:
        return 0

    def reject_opaque_import(self, _blob: str = "") -> None:
        raise SyncError(OPAQUE_REJECT, "Stay on Leasegrid Sync credit. Close.")

    def quote_topup(self, tokens: int) -> dict:
        if self.fail_quote:
            raise SyncError(
                "REVIEW — Your grid's issuer did not answer. Payments already sent are safe; retry later.",
                "Retry later.",
            )
        q = dict(self.quote or {})
        q.setdefault("tokens_quoted", tokens)
        self.pending.append(
            {
                "vid": q.get("vid"),
                "state": q.get("state") or "quoted",
                "tokens_quoted": q.get("tokens_quoted"),
                "amount_xmr": q.get("amount_xmr"),
            }
        )
        return q

    def poll_topup(self, vid: str) -> dict:
        return dict(self.poll or {"vid": vid, "state": "quoted", "tokens_added": 0})

    def pending_topups(self) -> list:
        return list(self.pending)


@pytest.fixture
def fake_credit() -> FakeCredit:
    return FakeCredit(tokens=8)


@pytest.fixture
def ui(tmp_path: Path, fake_credit: FakeCredit):
    home = tmp_path / "sync-home"
    nodedir = tmp_path / "tahoe"
    nodedir.mkdir()
    (nodedir / "tahoe.cfg").write_text("[node]\n", encoding="utf-8")
    with patch(
        "leasegrid_sync.app.TahoeClient.join_existing",
        side_effect=SyncError("could not join this friendnet. No Tahoe.", "Retry."),
    ):
        window = MainWindow(nodedir=nodedir, home=home, credit=fake_credit)
    yield window
    window.poll.stop()
    window.win.hide()
    if window.tray is not None:
        window.tray.hide()


def test_window_title_is_leasegrid_sync(ui: MainWindow):
    assert ui.win.windowTitle() == APP_NAME
    assert "Leasegrid Sync" in ui.win.windowTitle()


def _ack_join(ui: MainWindow) -> None:
    ui.threat_ack.setChecked(True)


def test_join_stays_disabled_until_threat_ack(ui: MainWindow):
    """First-run HITL: four points on Join; Join does not run until the box is checked."""
    block = ui.join_page.findChild(PyQt5.QtWidgets.QGroupBox, "threatBlock")
    assert block is not None
    copy = ui.join_page.findChild(PyQt5.QtWidgets.QLabel, "threatCopy")
    assert copy is not None
    text = copy.text()
    assert "1. Same invite" in text or "offering disk" in text.lower()
    assert "No storage proofs" in text or "not slashed" in text.lower()
    assert "I2P" in text or "LAN/WAN" in text
    assert "recovery key" in text.lower()
    assert "mainnet" not in text.lower()
    ack = ui.join_page.findChild(PyQt5.QtWidgets.QCheckBox, "threatAck")
    assert ack is not None
    assert not ack.isChecked()
    assert ack.text() == "I understand the four points above."
    assert not ui.join_btn.isEnabled()
    assert not ui.existing_btn.isEnabled()
    assert ui.import_key_btn.isEnabled()
    with patch.object(ui.tahoe, "join_invite") as join:
        ui.invite_edit.setText("pb://hashhashhash@127.0.0.1:45001/swissnumswiss")
        ui.on_join_invite()
    join.assert_not_called()
    assert "FAIL" in ui.join_error.text()
    assert "Next:" in ui.join_error.text()
    assert "web UI" not in ui.join_error.text().lower()
    ack.setChecked(True)
    assert ui.join_btn.isEnabled()
    ack.setChecked(False)
    assert not ui.join_btn.isEnabled()


def test_join_failure_is_in_window_not_silent(ui: MainWindow):
    _ack_join(ui)
    ui.invite_edit.setText("nope")
    ui.on_join_invite()
    text = ui.join_error.text()
    assert text
    assert "FAIL" in text
    assert "web UI" not in text.lower() or "does not use the Tahoe web UI" in text


def test_empty_invite_fail(ui: MainWindow):
    _ack_join(ui)
    ui.invite_edit.setText("")
    ui.on_join_invite()
    assert "FAIL" in ui.join_error.text()
    assert ui.join_btn.isEnabled()
    assert ui.invite_edit.isEnabled()


def test_join_invite_success_enters_main(ui: MainWindow):
    st = ConnectionStatus(state="Connected", detail="introducer up · 3 storage", introducer_ok=True)
    seen = {}

    def fake_join(invite, offer_storage=True):
        seen["progress"] = ui.join_progress.text()
        seen["disabled"] = not ui.join_btn.isEnabled()
        seen["offer_storage"] = offer_storage
        return st

    assert ui.join_btn.isDefault()
    assert ui.existing_btn.isFlat()
    assert ui.import_key_btn.isFlat()
    _ack_join(ui)
    ui.invite_edit.setText("pb://hashhashhash@127.0.0.1:45001/swissnumswiss")
    with patch.object(ui.tahoe, "join_invite", side_effect=fake_join):
        with patch.object(ui.tahoe, "connection_status", return_value=st):
            with patch.object(ui.mf, "list_folders", return_value=[]):
                ui.on_join_invite()
    # fixture nodedir already exists, so the copy is the "existing client" variant
    assert "Connecting" in seen["progress"]
    assert seen["disabled"]
    assert ui.stack.currentWidget() is ui.main_page
    assert "computers storing files" in ui.status_chip.text()
    assert "3" in ui.status_chip.text()
    assert "introducer" not in ui.status_chip.text().lower()
    assert ui.join_btn.isEnabled()
    assert ui.join_progress.text() == ""
    assert ui.join_error.text() == ""
    assert ui.places.currentWidget() is ui.folders_tab
    assert not ui.disk_pie.isHidden()
    assert "% of this disk" in ui.offer_percent.text()
    assert "Used" in ui.offer_legend.text() and "Offered" in ui.offer_legend.text()


def test_recovery_place_has_scary_copy_and_both_actions(ui: MainWindow):
    labels = ui.recovery_tab.findChildren(PyQt5.QtWidgets.QLabel)
    buttons = ui.recovery_tab.findChildren(PyQt5.QtWidgets.QPushButton)
    blob = " ".join(w.text() for w in labels)
    assert "TOTAL LOSS" in blob
    assert "Last export: never" in blob
    names = [b.text() for b in buttons]
    assert "Export recovery key…" in names
    assert "Import recovery key…" in names
    assert ui.export_key_btn.isDefault()
    assert ui.export_key_btn.isEnabled()
    assert ui.import_key_btn2.isEnabled()
    assert "not in this build" not in blob
    assert "xmr" not in blob.lower()
    assert "mainnet" not in blob.lower()


def test_import_from_recovery_lands_on_folders(ui: MainWindow):
    from leasegrid_sync.app import ImportRecoveryDialog
    from leasegrid_sync.recovery import RestoreResult

    res = RestoreResult(
        folders=["Photos"], skipped=[], wallet_restored=False, author_name="me@box-ab12",
        grid="introducer up · 3 storage",
    )
    st = ConnectionStatus(state="Connected", detail="introducer up · 3 storage", introducer_ok=True)

    real_init = ImportRecoveryDialog.__init__

    def init_with_result(self, *args, **kwargs):
        real_init(self, *args, **kwargs)
        self.result = res
        self.dlg.exec_ = lambda: ui.QtWidgets.QDialog.Accepted

    with patch.object(ImportRecoveryDialog, "__init__", init_with_result):
        with patch.object(ui.tahoe, "connection_status", return_value=st):
            with patch.object(ui.mf, "list_folders", return_value=[]):
                ui.on_import_recovery()
    assert ui.stack.currentWidget() is ui.main_page
    assert ui.places.currentWidget() is ui.folders_tab
    assert "Photos" in ui.folder_error.text()


def test_folders_nudge_is_dismissible_and_does_not_block_add(ui: MainWindow):
    _enter(ui)
    nudge = ui.folders_tab.findChild(PyQt5.QtWidgets.QWidget, "recoveryNudge")
    assert nudge is not None
    assert not nudge.isHidden()
    assert "No recovery key exported yet" in nudge.findChild(PyQt5.QtWidgets.QLabel).text()
    assert ui.add_btn.isEnabled()
    assert not ui.disk_pie.isHidden()
    ui.on_dismiss_recovery_nudge()
    assert nudge.isHidden()
    assert ui.add_btn.isEnabled()
    assert ui.recovery.nudge_dismissed()


def test_join_page_offers_import_recovery(ui: MainWindow):
    buttons = ui.join_page.findChildren(PyQt5.QtWidgets.QPushButton)
    assert any("Import recovery key" in b.text() for b in buttons)


def test_export_dialog_gate_requires_both_acks_and_matching_passphrase(ui: MainWindow, tmp_path):
    from leasegrid_sync.app import ExportRecoveryDialog

    dlg = ExportRecoveryDialog(ui.win, ui.recovery, ui.QtWidgets, default_dir=tmp_path)
    assert not dlg.write_btn.isEnabled()
    dlg.ack_loss.setChecked(True)
    assert not dlg.write_btn.isEnabled()
    dlg.ack_store.setChecked(True)
    assert dlg.write_btn.isEnabled()  # no passphrase is allowed (plaintext, with a note)
    assert not dlg.pass_note.isHidden()
    dlg.pass_edit.setText("abc")
    assert not dlg.write_btn.isEnabled()  # confirm mismatch
    dlg.confirm_edit.setText("abc")
    assert dlg.write_btn.isEnabled()
    assert dlg.path_edit.text().endswith(".leasegrid-recovery")


def test_export_dialog_fail_in_window(ui: MainWindow, tmp_path):
    from leasegrid_sync.app import ExportRecoveryDialog

    dlg = ExportRecoveryDialog(ui.win, ui.recovery, ui.QtWidgets, default_dir=tmp_path)
    dlg.ack_loss.setChecked(True)
    dlg.ack_store.setChecked(True)
    with patch.object(
        ui.recovery, "export", side_effect=SyncError("recovery key was not written.", "Retry.")
    ):
        dlg.on_write()
    assert "FAIL" in dlg.status.text()
    assert dlg.write_btn.text() == "Retry export"
    assert dlg.write_btn.isEnabled()
    assert dlg.written is None


def test_export_dialog_success(ui: MainWindow, tmp_path):
    from leasegrid_sync.app import ExportRecoveryDialog
    from leasegrid_sync.recovery import RecoveryBundle

    dlg = ExportRecoveryDialog(ui.win, ui.recovery, ui.QtWidgets, default_dir=tmp_path)
    dlg.ack_loss.setChecked(True)
    dlg.ack_store.setChecked(True)
    bundle = RecoveryBundle(introducer_furl="pb://x@h:1/s", shares=(2, 3, 3))
    with patch.object(ui.recovery, "export", return_value=bundle) as exp:
        dlg.on_write()
    assert exp.called
    assert dlg.written == Path(dlg.path_edit.text())


def test_import_dialog_missing_file_and_fail(ui: MainWindow, tmp_path):
    from leasegrid_sync.app import ImportRecoveryDialog

    dlg = ImportRecoveryDialog(ui.win, ui.recovery, ui.QtWidgets, path=tmp_path / "nope")
    dlg.on_import()
    assert "File not found" in dlg.status.text()
    key = tmp_path / "k.leasegrid-recovery"
    key.write_text("{}", encoding="utf-8")
    dlg.path_edit.setText(str(key))
    with patch.object(
        ui.recovery,
        "restore",
        side_effect=SyncError("could not import this recovery key.", "check passphrase."),
    ):
        dlg.on_import()
    assert "FAIL" in dlg.status.text()
    assert dlg.import_btn.text() == "Retry import"


def test_apply_restore_result_enters_main_with_note(ui: MainWindow):
    from leasegrid_sync.recovery import RestoreResult

    st = ConnectionStatus(state="Connected", detail="introducer up · 3 storage", introducer_ok=True)
    res = RestoreResult(
        folders=["Photos"], skipped=[], wallet_restored=True, author_name="me@box-ab12",
        grid="introducer up · 3 storage",
    )
    with patch.object(ui.tahoe, "connection_status", return_value=st):
        with patch.object(ui.mf, "list_folders", return_value=[]):
            ui.apply_restore_result(res)
    assert ui.stack.currentWidget() is ui.main_page
    assert ui.places.currentWidget() is ui.folders_tab
    assert "Restored 1 folder(s): Photos" in ui.folder_error.text()
    assert "Credit wallet restored" in ui.folder_error.text()


def test_join_page_explains_what_join_does(ui: MainWindow):
    labels = ui.join_page.findChildren(PyQt5.QtWidgets.QLabel)
    blob = " ".join(w.text() for w in labels)
    assert "1. Same invite" in blob
    assert "No storage proofs" in blob
    assert "Recovery" in blob
    assert "paste" in blob.lower() or "link" in blob.lower() or "code" in blob.lower()
    ph = ui.invite_edit.placeholderText().lower()
    assert "i2p" in ph or "join#" in ph
    assert "word-word" in ph or "7-" in ph
    cb = ui.join_page.findChild(PyQt5.QtWidgets.QCheckBox, "offerStorage")
    assert cb is not None
    assert cb.isChecked()
    assert "offer" in cb.text().lower()
    details = ui.join_page.findChild(PyQt5.QtWidgets.QPushButton, "joinDetails")
    assert details is not None


def test_join_page_threat_is_the_hitl_not_a_hidden_dialog(ui: MainWindow):
    intro = ui.join_page.findChild(PyQt5.QtWidgets.QLabel, "joinIntro")
    assert intro is not None
    assert len(intro.text()) < 120
    assert ui.join_page.findChild(PyQt5.QtWidgets.QLabel, "threatCopy") is not None
    assert not ui.join_btn.isEnabled()


def test_join_i2p_url_enters_main(ui: MainWindow):
    from leasegrid_sync.invite import format_join_url

    st = ConnectionStatus(state="Connected", detail="introducer up · 3 storage", introducer_ok=True)
    furl = "pb://hashhashhash@127.0.0.1:45001/swissnumswiss"
    url = format_join_url(furl, origin="http://alice.i2p/join")
    seen = {}

    def fake_join(invite, offer_storage=True):
        seen["invite"] = invite
        seen["offer_storage"] = offer_storage
        return st

    ui.invite_edit.setText(url)
    _ack_join(ui)
    with patch.object(ui.tahoe, "has_nodedir", return_value=False):
        with patch.object(ui.tahoe, "join_invite", side_effect=fake_join):
            with patch.object(ui.tahoe, "connection_status", return_value=st):
                with patch.object(ui.mf, "list_folders", return_value=[]):
                    ui.on_join_invite()
    assert seen["invite"] == url
    assert seen["offer_storage"] is True
    assert ui.stack.currentWidget() is ui.main_page


def test_settings_share_link_qr_and_copy(ui: MainWindow, monkeypatch):
    furl = "pb://hashhashhash@127.0.0.1:45001/swissnumswiss"
    (ui.tahoe.nodedir / "tahoe.cfg").write_text(
        "[node]\n[client]\nintroducer.furl = %s\nshares.needed = 2\n"
        "shares.happy = 3\nshares.total = 3\n" % furl,
        encoding="utf-8",
    )
    monkeypatch.setenv("LEASEGRID_JOIN_ORIGIN", "http://alice.i2p/join")
    st = ConnectionStatus(state="Connected", detail="introducer up", introducer_ok=True)
    with patch.object(ui.tahoe, "connection_status", return_value=st):
        with patch.object(ui.mf, "list_folders", return_value=[]):
            ui._enter_main("Connected", "introducer up")
    box = ui.settings_tab.findChild(PyQt5.QtWidgets.QGroupBox, "shareBox")
    assert box is not None
    url = ui.share_url_edit.text()
    assert url.startswith("http://alice.i2p/join#")
    assert furl not in url.split("#", 1)[0]
    assert ui.share_url_edit.cursorPosition() == 0
    pix = ui.share_qr.pixmap()
    assert pix is not None and not pix.isNull()
    ui.on_copy_share_url()
    assert ui.QtWidgets.QApplication.clipboard().text() == url
    assert ui.copy_share_btn.isEnabled()
    assert ui.export_page_btn.isEnabled()
    hint = " ".join(w.text() for w in box.findChildren(PyQt5.QtWidgets.QLabel))
    assert "i2p" in hint.lower()
    assert "qr" in hint.lower() or "QR" in hint


def test_join_invite_passes_offer_storage_default(ui: MainWindow):
    st = ConnectionStatus(state="Connected", detail="introducer up · 3 storage", introducer_ok=True)
    seen = {}

    def fake_join(invite, offer_storage=True):
        seen["offer_storage"] = offer_storage
        return st

    ui.invite_edit.setText("pb://hashhashhash@127.0.0.1:45001/swissnumswiss")
    _ack_join(ui)
    with patch.object(ui.tahoe, "has_nodedir", return_value=False):
        with patch.object(ui.tahoe, "join_invite", side_effect=fake_join):
            with patch.object(ui.tahoe, "connection_status", return_value=st):
                with patch.object(ui.mf, "list_folders", return_value=[]):
                    ui.on_join_invite()
    assert seen["offer_storage"] is True


def test_join_opt_out_passes_offer_storage_false(ui: MainWindow):
    st = ConnectionStatus(state="Connected", detail="introducer up · 3 storage", introducer_ok=True)
    seen = {}

    def fake_join(invite, offer_storage=True):
        seen["offer_storage"] = offer_storage
        return st

    ui.offer_storage_cb.setChecked(False)
    _ack_join(ui)
    ui.invite_edit.setText("pb://hashhashhash@127.0.0.1:45001/swissnumswiss")
    with patch.object(ui.tahoe, "has_nodedir", return_value=False):
        with patch.object(ui.tahoe, "join_invite", side_effect=fake_join):
            with patch.object(ui.tahoe, "connection_status", return_value=st):
                with patch.object(ui.mf, "list_folders", return_value=[]):
                    ui.on_join_invite()
    assert seen["offer_storage"] is False


def test_join_with_short_code_shows_code_progress(ui: MainWindow):
    st = ConnectionStatus(state="Connected", detail="introducer up · 3 storage", introducer_ok=True)
    seen = {}

    def fake_join(invite, offer_storage=True):
        seen["progress"] = ui.join_progress.text()
        seen["offer_storage"] = offer_storage
        return st

    _ack_join(ui)
    ui.invite_edit.setText(" 7-Guitarist-Revenge ")
    with patch.object(ui.tahoe, "has_nodedir", return_value=False):
        with patch.object(ui.tahoe, "join_invite", side_effect=fake_join):
            with patch.object(ui.tahoe, "connection_status", return_value=st):
                with patch.object(ui.mf, "list_folders", return_value=[]):
                    ui.on_join_invite()
    assert "code 7-guitarist-revenge" in seen["progress"]
    assert "inviter" in seen["progress"]
    assert ui.stack.currentWidget() is ui.main_page


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
    assert ui.places.currentWidget() is ui.folders_tab
    assert ui.back_btn.isHidden()
    assert ui.more_btn.text() == "More"
    assert ui.recovery_action.text() == "Recovery"
    assert ui.settings_action.text() == "Settings"
    assert not ui.credit_action.isVisible()
    assert ui.status_chip.text().startswith("Online")


def test_payment_lecture_hidden_until_gated(ui: MainWindow, monkeypatch):
    """Unpaid default. XMR / Credit copy stays off the window until LEASEGRID_GATED."""
    monkeypatch.delenv("LEASEGRID_GATED", raising=False)
    _enter(ui)
    note = ui.settings_tab.findChild(PyQt5.QtWidgets.QLabel, "settingsNote")
    text = note.text() if note is not None else ""
    assert "AppImage" in text
    assert "U3" not in text and "U4" not in text and "U5" not in text
    assert "xmr" not in text.lower()
    assert "top up" not in text.lower()
    lecture = ui.payment_lecture
    assert "XMR" in lecture.text()
    assert "Top up" in lecture.text()
    assert "after mint rails" not in lecture.text().lower()
    assert not lecture.isVisibleTo(ui.settings_tab)
    assert not ui.credit_action.isVisible()
    visible = " ".join(
        w.text() for w in ui.folders_tab.findChildren(PyQt5.QtWidgets.QLabel) if not w.isHidden()
    ).lower()
    assert "top up" not in visible
    assert "xmr" not in visible
    assert "% of this disk" in visible
    monkeypatch.setenv("LEASEGRID_GATED", "1")
    ui._sync_gated_chrome()
    assert lecture.isVisibleTo(ui.settings_tab)
    assert ui.credit_action.isVisible()


def test_connected_autoload_skips_join(tmp_path: Path):
    home = tmp_path / "home"
    nodedir = tmp_path / "tahoe"
    nodedir.mkdir()
    (nodedir / "tahoe.cfg").write_text("[node]\n", encoding="utf-8")
    st = ConnectionStatus(state="Connected", detail="lab", introducer_ok=True)
    fake = FakeCredit(tokens=8)
    with patch("leasegrid_sync.app.TahoeClient.join_existing", return_value=st):
        with patch("leasegrid_sync.app.MagicFolderCtl.list_folders", return_value=[]):
            window = MainWindow(nodedir=nodedir, home=home, credit=fake)
    try:
        assert window.stack.currentWidget() is window.main_page
        assert window.win.windowTitle() == APP_NAME
    finally:
        window.poll.stop()
        window.win.hide()
        if window.tray is not None:
            window.tray.hide()


def test_window_close_quits_instead_of_hiding_to_tray(ui: MainWindow):
    called = []

    def fake_quit():
        called.append(True)

    ev = ui.QtGui.QCloseEvent()
    with patch.object(ui, "quit", side_effect=fake_quit):
        ui._on_close(ev)
    assert called == [True]
    assert ev.isAccepted()


def test_refresh_non_sync_error_stays_in_window(ui: MainWindow):
    _enter(ui)
    with patch.object(ui.mf, "list_folders", side_effect=RuntimeError("boom")):
        ui.refresh()
    assert ui.folder_error.text().startswith("FAIL")
    assert "RuntimeError" in ui.folder_error.text()
    assert "boom" in ui.folder_error.text()
    assert (ui.home / "logs" / "sync-ui.log").is_file()


def test_add_folder_non_sync_error_stays_in_window(ui: MainWindow, tmp_path: Path):
    _enter(ui)
    with patch.object(
        ui.QtWidgets.QFileDialog, "getExistingDirectory", return_value=str(tmp_path)
    ), patch.object(ui.mf, "add_folder", side_effect=RuntimeError("native abort")):
        ui.on_add_folder()
    assert ui.folder_error.text().startswith("FAIL")
    assert "native abort" in ui.folder_error.text()
    assert "folder not added" in ui.folder_error.text().lower()


def test_status_chip_is_not_tahoe_jargon(ui: MainWindow):
    from leasegrid_sync.app import format_status_chip

    st = ConnectionStatus(
        state="Connected",
        detail="introducer up · 3 storage",
        introducer_ok=True,
        servers_connected=3,
    )
    text = format_status_chip(st)
    assert "introducer" not in text.lower()
    assert "3 computers storing files" in text
    assert format_status_chip(
        ConnectionStatus(state="Connected", detail="introducer up · 3 storage")
    ) == text


def test_offer_pie_shows_percent_of_this_disk(ui: MainWindow):
    from collections import namedtuple

    (ui.tahoe.nodedir / "tahoe.cfg").write_text(
        "[node]\n[storage]\nenabled = true\nreserved_space = 10%\n", encoding="utf-8"
    )
    usage = namedtuple("usage", "total used free")(1000, 400, 600)
    st = ConnectionStatus(state="Connected", detail="lab", introducer_ok=True)
    with patch("leasegrid_sync.backend.shutil.disk_usage", return_value=usage):
        with patch.object(ui.tahoe, "connection_status", return_value=st):
            with patch.object(ui.mf, "list_folders", return_value=[]):
                ui._enter_main("Connected", "lab")
    assert ui.places.currentWidget() is ui.folders_tab
    assert not ui.disk_pie.isHidden()
    # reserved 10% of 1000 = 100, kept = min(600, 100) = 100, offered = 500 → 50%
    assert ui.offer_percent.text() == "Offering 50% of this disk"
    legend = ui.offer_legend.text()
    assert legend.startswith("Used ")
    assert "Free " in legend
    assert "Offered " in legend
    assert ui.offer_slider.value() == 50
    assert "Open web UI" not in legend


def test_offer_pie_fail_stays_in_window(ui: MainWindow):
    with patch(
        "leasegrid_sync.app.read_disk_offer",
        side_effect=SyncError("could not read this disk. boom", "check that the disk is mounted; Retry."),
    ):
        _enter(ui)
    assert ui.places.currentWidget() is ui.folders_tab
    assert "FAIL" in ui.offer_status.text()
    assert "boom" in ui.offer_status.text()
    assert "Next:" in ui.offer_status.text()
    assert "% of this disk" in ui.offer_percent.text()
    assert "Used" in ui.offer_legend.text() and "Offered" in ui.offer_legend.text()


def test_offer_slider_sync_only_fails_in_window(ui: MainWindow):
    _enter(ui)
    ui.offer_slider.setValue(25)
    ui.on_offer_percent_chosen()
    assert "FAIL" in ui.offer_status.text()
    assert "sync-only" in ui.offer_status.text()
    assert "Offer disk" in ui.offer_status.text()
    assert ui.places.currentWidget() is ui.folders_tab


def test_offer_slider_saves_percent_of_this_disk(ui: MainWindow):
    from collections import namedtuple

    (ui.tahoe.nodedir / "tahoe.cfg").write_text(
        "[node]\n[storage]\nenabled = true\n", encoding="utf-8"
    )
    usage = namedtuple("usage", "total used free")(1000, 200, 800)
    with patch("leasegrid_sync.backend.shutil.disk_usage", return_value=usage):
        _enter(ui)
        ui.offer_slider.setValue(25)
        ui.on_offer_percent_chosen()
    assert "Saved" in ui.offer_status.text()
    assert ui.offer_percent.text() == "Offering 25% of this disk"
    cfg = (ui.tahoe.nodedir / "tahoe.cfg").read_text(encoding="utf-8")
    assert "enabled = true" in cfg
    assert "reserved_space = 550" in cfg  # free 800 − 25% of 1000
    assert "Used" in ui.offer_legend.text()
    assert "Free" in ui.offer_legend.text()
    assert "Offered" in ui.offer_legend.text()


def _enter(ui: MainWindow) -> None:
    ui.win.show()
    st = ConnectionStatus(state="Connected", detail="lab", introducer_ok=True)
    with patch.object(ui.tahoe, "connection_status", return_value=st):
        with patch.object(ui.mf, "list_folders", return_value=[]):
            ui._enter_main("Connected", "lab")


def test_gated_credit_is_secondary_place(ui: MainWindow, monkeypatch):
    monkeypatch.setenv("LEASEGRID_GATED", "1")
    _enter(ui)
    assert ui.places.currentWidget() is ui.folders_tab
    assert ui.credit_action.isVisible()
    assert ui.credit_action.text() == "Credit"
    ui.open_credit_place()
    assert ui.places.currentWidget() is ui.credit_tab
    assert not ui.back_btn.isHidden()
    assert not ui.credit_body.isHidden()
    assert ui.credit_topup_btn.text() == "Top up"
    assert "1 GiB upload = 1 GiB credit" not in ui.credit_remaining.text()
    denom = ui.credit_tab.findChild(PyQt5.QtWidgets.QLabel, "creditDenomination")
    assert denom is not None
    assert "expand" in denom.text().lower()
    lab = ui.credit_tab.findChild(PyQt5.QtWidgets.QLabel, "creditLabNote")
    assert lab is not None
    assert "faucet" in lab.text().lower()
    assert "opaque" in lab.text().lower()


def test_credit_zero_state(ui: MainWindow, fake_credit: FakeCredit):
    fake_credit.tokens = 0
    _enter(ui)
    ui.show_place(ui.credit_tab)
    text = ui.credit_remaining.text().lower()
    assert "none" in text
    assert not ui.credit_topup_btn.isHidden()
    assert not ui.credit_body.isHidden()


def test_credit_load_fail_retry(ui: MainWindow, fake_credit: FakeCredit):
    fake_credit.fail_load = True
    _enter(ui)
    ui.show_place(ui.credit_tab)
    assert not ui.credit_error.isHidden()
    assert "FAIL" in ui.credit_error.text()
    assert "Next:" in ui.credit_error.text()
    assert not ui.credit_retry_btn.isHidden()
    fake_credit.fail_load = False
    ui.credit_retry_btn.click()
    assert not ui.credit_body.isHidden()
    assert "About 8 GiB" in ui.credit_remaining.text()


def test_credit_tab_survives_non_sync_error(ui: MainWindow, fake_credit: FakeCredit):
    """A backend surprise (not SyncError) must become a FAIL banner, never reach Qt.

    PyQt5 aborts the process on any exception that escapes a slot; the Credit
    tab's currentChanged slot used to let anything but SyncError through.
    """
    _enter(ui)
    with patch.object(
        fake_credit, "load_balance", side_effect=RuntimeError("Remote end closed connection")
    ):
        ui.show_place(ui.credit_tab)
    assert not ui.credit_error.isHidden()
    text = ui.credit_error.text()
    assert text.startswith("FAIL")
    assert "RuntimeError" in text and "Remote end closed" in text
    assert "Next:" in text and "sync-ui.log" in text
    assert not ui.credit_retry_btn.isHidden()
    assert ui.credit_body.isHidden()
    log = ui.home / "logs" / "sync-ui.log"
    assert log.is_file()
    assert "RuntimeError: Remote end closed connection" in log.read_text(encoding="utf-8")
    ui.credit_retry_btn.click()
    assert not ui.credit_body.isHidden()
    assert "About 8 GiB" in ui.credit_remaining.text()


def test_excepthook_keeps_window_alive_and_shows_review(ui: MainWindow):
    from leasegrid_sync.app import install_excepthook

    _enter(ui)
    saved = sys.excepthook
    try:
        install_excepthook(ui)
        assert sys.excepthook is not saved
        try:
            raise ValueError("slot blew up")
        except ValueError as exc:
            sys.excepthook(type(exc), exc, exc.__traceback__)
        banner = ui.win.findChild(PyQt5.QtWidgets.QLabel, "unexpectedReview")
        assert banner is not None and not banner.isHidden()
        assert "ValueError" in banner.text()
        assert "slot blew up" in banner.text()
        assert "sync-ui.log" in banner.text()
        assert ui.status_chip.text().startswith("REVIEW")
        assert (ui.home / "logs" / "sync-ui.log").is_file()
        # a second failure reuses the same banner instead of stacking dialogs
        try:
            raise KeyError("again")
        except KeyError as exc:
            sys.excepthook(type(exc), exc, exc.__traceback__)
        banners = ui.win.findChildren(PyQt5.QtWidgets.QLabel, "unexpectedReview")
        assert len(banners) == 1
        assert "KeyError" in banners[0].text()
        banners[0].hide()
    finally:
        sys.excepthook = saved


def test_balance_updates_after_redeem(ui: MainWindow, fake_credit: FakeCredit):
    fake_credit.tokens = 0
    _enter(ui)
    ui.load_credit()
    assert "none" in ui.credit_remaining.text().lower()
    dlg = TopUpDialog(ui.win, ui.credit, ui.QtWidgets)
    dlg.radios["small"].setChecked(True)
    dlg.on_request()
    assert dlg.snapshot is not None
    assert dlg.snapshot.balance.tokens == 10
    ui.apply_credit_snapshot(dlg.snapshot, success_note="Top-up complete.\n" + dlg.snapshot.remaining_text)
    assert "About 10 GiB" in ui.credit_remaining.text()
    assert "Top-up complete" in ui.credit_success.text()


def test_redeem_fail_in_dialog(ui: MainWindow, fake_credit: FakeCredit):
    fake_credit.fail_redeem = True
    _enter(ui)
    dlg = TopUpDialog(ui.win, ui.credit, ui.QtWidgets)
    dlg.on_request()
    assert "FAIL" in dlg.status.text()
    assert "Next:" in dlg.status.text()
    assert dlg.request_btn.text() == "Retry"
    assert dlg.cancel_btn.text() == "Close"
    assert fake_credit.tokens == 8


def test_topup_continue_quotes_and_shows_pay(ui: MainWindow, fake_credit: FakeCredit):
    fake_credit.quote = {
        "vid": "aabbccddeeff0011",
        "address": "4fakeAddressForPay",
        "amount_xmr": "0.12",
        "amount_piconero": 120000000000,
        "pay_uri": "monero:4fakeAddressForPay?tx_amount=0.12",
        "quote_expires": 2000000000,
        "grace_until": 2000086400,
        "confirmations_required": 2,
        "tokens_quoted": 20,
        "state": "quoted",
    }
    dlg = TopUpDialog(ui.win, ui.credit, ui.QtWidgets)
    dlg.radios["medium"].setChecked(True)
    dlg.on_continue()
    assert dlg.page == "pay"
    assert "4fakeAddressForPay" in dlg.pay_address.text()
    assert "0.12" in dlg.pay_amount.text()
    assert "XMR" in dlg.pay_amount.text()
    blob = " ".join(w.text() for w in dlg.dlg.findChildren(PyQt5.QtWidgets.QLabel))
    assert "send exactly" in blob.lower()
    assert "24" in blob  # grace hours
    assert "Open web UI" not in blob
    assert "http://127.0.0.1" not in blob
    assert dlg.copy_address_btn.isEnabled()


def test_topup_poll_issued_accepts(ui: MainWindow, fake_credit: FakeCredit):
    fake_credit.quote = {
        "vid": "aabbccddeeff0011",
        "address": "4addr",
        "amount_xmr": "0.06",
        "tokens_quoted": 10,
        "state": "quoted",
        "quote_expires": 2000000000,
        "grace_until": 2000086400,
        "confirmations_required": 2,
    }
    fake_credit.poll = {"vid": "aabbccddeeff0011", "state": "issued", "tokens_added": 10}
    fake_credit.tokens = 18
    dlg = TopUpDialog(ui.win, ui.credit, ui.QtWidgets)
    dlg.radios["small"].setChecked(True)
    dlg.on_continue()
    dlg.on_poll()
    assert dlg.page == "done"
    assert dlg.snapshot is not None
    assert dlg.snapshot.balance.tokens == 18
    assert "+10" in dlg.status.text() or "10" in dlg.status.text()


def test_topup_issuer_unreachable_is_review(ui: MainWindow, fake_credit: FakeCredit):
    fake_credit.fail_quote = True
    dlg = TopUpDialog(ui.win, ui.credit, ui.QtWidgets)
    dlg.on_continue()
    assert dlg.page == "choose"
    assert "REVIEW" in dlg.status.text()
    assert "issuer" in dlg.status.text().lower()
    assert "localhost" not in dlg.status.text()
    assert "http://" not in dlg.status.text()


def test_topup_underpaid_keeps_same_address(ui: MainWindow, fake_credit: FakeCredit):
    fake_credit.quote = {
        "vid": "aabbccddeeff0011",
        "address": "4same",
        "amount_xmr": "0.12",
        "tokens_quoted": 20,
        "state": "quoted",
        "quote_expires": 2000000000,
        "grace_until": 2000086400,
        "confirmations_required": 2,
    }
    fake_credit.poll = {
        "vid": "aabbccddeeff0011",
        "state": "underpaid",
        "tokens_added": 0,
        # live /v0/voucher/{vid} shape: piconero ints, no amount_xmr_* aliases
        "voucher": {
            "amount_seen": 5 * 10**10,
            "amount_due": 12 * 10**10,
            "amount_confirmed": 0,
        },
    }
    dlg = TopUpDialog(ui.win, ui.credit, ui.QtWidgets)
    dlg.on_continue()
    dlg.on_poll()
    assert dlg.page == "pay"
    assert "4same" in dlg.pay_address.text()
    assert "underpaid" in dlg.status.text().lower()
    assert "0.05" in dlg.status.text()
    assert "0.07" in dlg.status.text()  # remaining due
    assert "50000000000" not in dlg.status.text()
    assert "nothing is lost" in dlg.status.text().lower()


def test_credit_panel_lists_pending_vouchers(ui: MainWindow, fake_credit: FakeCredit):
    fake_credit.pending = [{"vid": "aa", "state": "quoted", "tokens_quoted": 20, "amount_xmr": "0.12"}]
    _enter(ui)
    ui.load_credit()
    assert not ui.credit_pending.isHidden()
    assert "0.12" in ui.credit_pending.text() or "20" in ui.credit_pending.text()
    assert "quoted" in ui.credit_pending.text().lower() or "waiting" in ui.credit_pending.text().lower()


def test_topup_copy_amount_is_numeric_xmr(ui: MainWindow, fake_credit: FakeCredit):
    fake_credit.quote = {
        "vid": "aabbccddeeff0011",
        "address": "4fakeAddressForPay",
        "amount_xmr": "0.12",
        "tokens_quoted": 20,
        "state": "quoted",
    }
    dlg = TopUpDialog(ui.win, ui.credit, ui.QtWidgets)
    dlg.on_continue()
    dlg.on_copy_amount()
    clipped = ui.QtWidgets.QApplication.clipboard().text()
    assert clipped == "0.12"
    assert "XMR" not in clipped


def test_topup_close_stops_timer_and_lists_pending(ui: MainWindow, fake_credit: FakeCredit):
    fake_credit.quote = {
        "vid": "aabbccddeeff0011",
        "address": "4addr",
        "amount_xmr": "0.12",
        "tokens_quoted": 20,
        "state": "quoted",
    }
    _enter(ui)
    ui.load_credit()
    assert ui.credit_pending.isHidden()
    dlg = TopUpDialog(ui.win, ui.credit, ui.QtWidgets)
    dlg.on_continue()
    assert dlg._timer is not None and dlg._timer.isActive()
    dlg.dlg.reject()
    assert dlg._timer is None or not dlg._timer.isActive()
    ui._apply_topup_result(dlg, ui.QtWidgets.QDialog.Rejected)
    assert not ui.credit_pending.isHidden()
    assert "0.12" in ui.credit_pending.text() or "20" in ui.credit_pending.text()


def test_export_warn_mentions_credit_seed(ui: MainWindow):
    from leasegrid_sync.app import ExportRecoveryDialog
    from leasegrid_sync.recovery import EXPORT_WARN

    assert "credit seed" in EXPORT_WARN.lower()
    dlg = ExportRecoveryDialog(ui.win, ui.recovery, ui.QtWidgets, default_dir=ui.home)
    assert "credit seed" in dlg.dlg.findChild(PyQt5.QtWidgets.QLabel, "exportWarn").text().lower()


def test_refresh_surfaces_spender_refusal(ui: MainWindow, fake_credit: FakeCredit):
    """Wallet ran dry mid-sync: the Tahoe-side spender wrote an event; Folders says so."""
    _enter(ui)
    assert "paused" not in ui.folder_error.text()
    fake_credit.refusal = "Upload refused: out of credit"
    with patch.object(ui.mf, "list_folders", return_value=[]):
        ui.refresh()
    assert "FAIL" in ui.folder_error.text()
    assert "sync is paused" in ui.folder_error.text()
    assert "out of credit" in ui.folder_error.text()
    assert not ui.open_credit_btn.isHidden()


def test_add_folder_500_with_refusal_shows_credit_copy(ui: MainWindow, fake_credit: FakeCredit):
    _enter(ui)
    fake_credit.refusal = "Upload refused: no credit on this device"
    with patch.object(ui.QtWidgets.QFileDialog, "getExistingDirectory", return_value="/tmp"), \
         patch.object(ui.credit, "estimate_tokens", return_value=1, create=True), \
         patch.object(ui.mf, "add_folder", side_effect=SyncError(
             "folder not added. Error: Magic Folder HTTP API reported error 500", "Retry.")):
        ui.on_add_folder()
    assert "error 500" not in ui.folder_error.text()
    assert "no credit on this device" in ui.folder_error.text()
    assert not ui.open_credit_btn.isHidden()


def test_add_folder_zero_credit_open_credit(ui: MainWindow, fake_credit: FakeCredit, monkeypatch):
    monkeypatch.setenv("LEASEGRID_GATED", "1")
    fake_credit.tokens = 0
    _enter(ui)
    ui.on_add_folder()
    assert "FAIL" in ui.folder_error.text()
    assert "folder not added" in ui.folder_error.text()
    assert "Not enough storage credit" in ui.folder_error.text()
    assert not ui.open_credit_btn.isHidden()
    ui.open_credit_place()
    assert ui.places.currentWidget() is ui.credit_tab


def test_add_folder_ungated_zero_credit_does_not_block(ui: MainWindow, fake_credit: FakeCredit, monkeypatch):
    """Unpaid grids: join already offered disk; Add folder must not demand Credit first."""
    monkeypatch.delenv("LEASEGRID_GATED", raising=False)
    fake_credit.tokens = 0
    _enter(ui)
    with patch.object(ui.QtWidgets.QFileDialog, "getExistingDirectory", return_value="") as dlg:
        ui.on_add_folder()
    assert dlg.called
    assert "Not enough storage credit" not in ui.folder_error.text()
    assert ui.open_credit_btn.isHidden()


def test_no_wui_cta_on_credit(ui: MainWindow):
    labels = ui.win.findChildren(PyQt5.QtWidgets.QLabel)
    buttons = ui.win.findChildren(PyQt5.QtWidgets.QPushButton)
    blob = " ".join(w.text() for w in list(labels) + list(buttons)).lower()
    for needle in ("open web ui", "open tahoe wui", "use the web ui"):
        assert needle not in blob
    assert "credit" in blob
    assert "top up" in blob


def test_run_modes_runs_credit_then_folder_when_both_requested(ui: MainWindow, tmp_path: Path):
    """--credit-dogfood --dogfood-folder: top up, then the upload that spends it (CI paid path)."""
    from leasegrid_sync.app import _run_modes

    order = []
    folder = tmp_path / "sync"

    def credit(screenshot=None, tier="medium"):
        order.append("credit")
        return {"before": 0, "after": 50, "remaining": "About 50 GiB"}

    def one_folder(path, screenshot=None):
        order.append("folder")
        return {"folder": str(path), "probe": "p", "status": {"relpath": "p"}, "grid": "g"}

    with patch.object(ui, "dogfood_credit", side_effect=credit):
        with patch.object(ui, "dogfood_one_folder", side_effect=one_folder):
            assert _run_modes(ui, None, folder, True, "medium") == 0
            assert order == ["credit", "folder"]
            order.clear()
            assert _run_modes(ui, None, None, True, "medium") == 0
            assert order == ["credit"]
