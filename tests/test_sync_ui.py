"""Offscreen Qt smoke: window title, join FAIL in-window, no WUI CTA."""

from __future__ import annotations

import os
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
        self.pubkey = "lab"
        self.refusal = None

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
        add = {"small": 10, "medium": 50, "large": 100}.get(tier, count or 50)
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
    assert ui.join_btn.isEnabled()
    assert ui.invite_edit.isEnabled()


def test_join_invite_success_enters_main(ui: MainWindow):
    st = ConnectionStatus(state="Connected", detail="introducer up · 3 storage", introducer_ok=True)
    seen = {}

    def fake_join(invite):
        seen["progress"] = ui.join_progress.text()
        seen["disabled"] = not ui.join_btn.isEnabled()
        return st

    ui.invite_edit.setText("pb://hashhashhash@127.0.0.1:45001/swissnumswiss")
    with patch.object(ui.tahoe, "join_invite", side_effect=fake_join):
        with patch.object(ui.tahoe, "connection_status", return_value=st):
            with patch.object(ui.mf, "list_folders", return_value=[]):
                ui.on_join_invite()
    # fixture nodedir already exists, so the copy is the "existing client" variant
    assert "Connecting" in seen["progress"]
    assert seen["disabled"]
    assert ui.stack.currentWidget() is ui.main_page
    assert "3 storage" in ui.status_chip.text()
    assert ui.join_btn.isEnabled()
    assert ui.join_progress.text() == ""
    assert ui.join_error.text() == ""


def test_recovery_place_has_scary_copy_and_both_actions(ui: MainWindow):
    labels = ui.recovery_tab.findChildren(PyQt5.QtWidgets.QLabel)
    buttons = ui.recovery_tab.findChildren(PyQt5.QtWidgets.QPushButton)
    blob = " ".join(w.text() for w in labels)
    assert "TOTAL LOSS" in blob
    assert "Last export: never" in blob
    names = [b.text() for b in buttons]
    assert "Export recovery key…" in names
    assert "Import recovery key…" in names
    assert "not in this build" not in blob


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
    assert ui.tabs.currentWidget() is ui.folders_tab
    assert "Restored 1 folder(s): Photos" in ui.folder_error.text()
    assert "Credit wallet restored" in ui.folder_error.text()


def test_join_page_explains_what_join_does(ui: MainWindow):
    labels = ui.join_page.findChildren(PyQt5.QtWidgets.QLabel)
    blob = " ".join(w.text() for w in labels)
    assert "creates a Tahoe client" in blob
    assert "Nothing is uploaded until you add a folder" in blob
    assert "short code" in blob
    assert "7-word-word" in ui.invite_edit.placeholderText()


def test_join_with_short_code_shows_code_progress(ui: MainWindow):
    st = ConnectionStatus(state="Connected", detail="introducer up · 3 storage", introducer_ok=True)
    seen = {}

    def fake_join(invite):
        seen["progress"] = ui.join_progress.text()
        return st

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
    assert ui.tabs.tabText(0) == "Folders"
    assert ui.tabs.tabText(1) == "Credit"
    assert ui.tabs.tabText(2) == "Recovery"
    assert ui.tabs.tabText(3) == "Settings"
    assert ui.status_chip.text().startswith("Connected")


def test_settings_stub_defers_u5_not_credit(ui: MainWindow):
    note = ui.settings_tab.findChild(PyQt5.QtWidgets.QLabel, "settingsNote")
    text = note.text() if note is not None else ""
    assert "U5" in text and "AppImage" in text
    assert "U3" not in text and "U4" not in text  # both shipped; no stale "coming later"
    assert "Credit panel (U2)" not in text
    assert "Credit:" in text
    assert "open the Credit place" in text


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


def _enter(ui: MainWindow) -> None:
    ui.win.show()
    st = ConnectionStatus(state="Connected", detail="lab", introducer_ok=True)
    with patch.object(ui.tahoe, "connection_status", return_value=st):
        with patch.object(ui.mf, "list_folders", return_value=[]):
            ui._enter_main("Connected", "lab")


def test_credit_is_primary_place(ui: MainWindow):
    _enter(ui)
    assert ui.tabs.tabText(1) == "Credit"
    ui.tabs.setCurrentWidget(ui.credit_tab)
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
    ui.tabs.setCurrentWidget(ui.credit_tab)
    text = ui.credit_remaining.text().lower()
    assert "none" in text
    assert not ui.credit_topup_btn.isHidden()
    assert not ui.credit_body.isHidden()


def test_credit_load_fail_retry(ui: MainWindow, fake_credit: FakeCredit):
    fake_credit.fail_load = True
    _enter(ui)
    ui.tabs.setCurrentWidget(ui.credit_tab)
    assert not ui.credit_error.isHidden()
    assert "FAIL" in ui.credit_error.text()
    assert "Next:" in ui.credit_error.text()
    assert not ui.credit_retry_btn.isHidden()
    fake_credit.fail_load = False
    ui.credit_retry_btn.click()
    assert not ui.credit_body.isHidden()
    assert "About 8 GiB" in ui.credit_remaining.text()


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


def test_topup_dialog_has_no_xmr_fields(ui: MainWindow):
    dlg = TopUpDialog(ui.win, ui.credit, ui.QtWidgets)
    edits = dlg.dlg.findChildren(PyQt5.QtWidgets.QLineEdit)
    assert edits == []
    blob = " ".join(w.text() for w in dlg.dlg.findChildren(PyQt5.QtWidgets.QLabel))
    assert "XMR" in blob
    assert "not available" in blob.lower()
    assert "Request faucet credit" in dlg.request_btn.text()
    assert "Open web UI" not in blob
    assert "http://127.0.0.1" not in blob


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


def test_add_folder_zero_credit_open_credit(ui: MainWindow, fake_credit: FakeCredit):
    fake_credit.tokens = 0
    _enter(ui)
    ui.on_add_folder()
    assert "FAIL" in ui.folder_error.text()
    assert "folder not added" in ui.folder_error.text()
    assert "Not enough storage credit" in ui.folder_error.text()
    assert not ui.open_credit_btn.isHidden()
    ui.open_credit_place()
    assert ui.tabs.currentWidget() is ui.credit_tab


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
