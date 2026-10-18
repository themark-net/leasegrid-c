"""More → Settings: open the logs folder and copy a bug report."""

from __future__ import annotations

import platform
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

PyQt5 = pytest.importorskip("PyQt5")

from leasegrid_sync.app import (  # noqa: E402
    MainWindow,
    UI_LOG_NAME,
    about_line,
    display_path,
    scrub_bug_report,
)
from leasegrid_sync.backend import FolderRow, SyncError  # noqa: E402
from leasegrid_sync.invite import InviteCodeSession  # noqa: E402
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


def test_shown_paths_hide_the_account_name(tmp_path: Path, monkeypatch) -> None:
    """A planted account name stays off the Settings line, the report, and the banner."""
    fake = tmp_path / "Users" / "fakeuser"
    fake.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(fake))
    monkeypatch.setenv("USERPROFILE", str(fake))
    monkeypatch.setattr(Path, "home", lambda *_args, **_kwargs: fake)
    home = fake / "LeasegridSync"
    nodedir = tmp_path / "tahoe"
    nodedir.mkdir()
    (nodedir / "tahoe.cfg").write_text("[node]\n", encoding="utf-8")
    with patch(
        "leasegrid_sync.app.TahoeClient.join_existing",
        side_effect=SyncError("could not join this friendnet. No Tahoe.", "Retry."),
    ):
        window = MainWindow(nodedir=nodedir, home=home)
    try:
        with patch("PyQt5.QtGui.QDesktopServices.openUrl", return_value=False):
            window.on_open_logs()
        status = window.settings_status.text()
        assert "fakeuser" not in status
        assert "~" in status
        report = window.bug_report_text()
        assert "fakeuser" not in report
        assert "~" in report
        missing = fake / "Documents" / "gone"
        window.open_folder_path(str(missing))
        banner = window.folder_error.text()
        assert "fakeuser" not in banner
        assert "~" in banner
        assert "That folder is not on this computer any more:" in banner
        real_logs = window.home / "logs"
        assert real_logs.is_dir()
        assert "fakeuser" in str(real_logs)
        (real_logs / UI_LOG_NAME).write_text(str(real_logs) + "\n", encoding="utf-8")
        assert "fakeuser" in (real_logs / UI_LOG_NAME).read_text(encoding="utf-8")
    finally:
        _close(window)


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
        assert display_path(window.home / "logs") in text
        assert_no_raw_user_text(text)
        assert (window.home / "logs").is_dir()
    finally:
        _close(window)


@pytest.mark.parametrize(
    ("raw", "kept"),
    [
        ("7-guitarist-revenge", False),
        ("(7-guitarist-revenge)", False),
        ("code:7-GUITARIST-REVENGE.", False),
        ("7-guitarist-gazelle-passenger", False),
        ("7-guitarist-revenge.", False),
        ("code:7-guitarist-revenge", False),
        ("7-guitarist-revenge2", False),
        ("sentence.7-guitarist-revenge", False),
        # redacted by design: both words are PGP words, so a leading number is a code
        ("2-adult-tiger", False),
        ("see 12-03-2026 today", True),
        ("500-from-server-side", True),
        ("404-not-found", True),
        ("1-way-sync", True),
        ("3-day-trip", True),
        ("v0.1.6-rc-final", True),
        ("v0.1.6-guitarist-revenge", True),
        ("v1.2.7-guitarist-revenge", True),
        # any() would redact this: guitarist is a PGP word and side is not
        ("7-guitarist-side", True),
        ("Logs: /home/u/3-day-trip/logs", True),
    ],
)
def test_scrub_bug_report_code_boundaries(raw: str, kept: bool) -> None:
    out = scrub_bug_report(raw)
    if kept:
        assert out == raw
    else:
        assert out != raw
        assert "[redacted]" in out
        for word in ("guitarist", "revenge", "gazelle", "passenger"):
            if word in raw.lower():
                assert word not in out.lower()


def test_scrub_bug_report_removes_each_secret_shape() -> None:
    planted = "\n".join(
        [
            about_line(),
            platform.platform(),
            "pb://FAKE-TUBID@127.0.0.1:1/FAKE-SWISS",
            "7-guitarist-revenge",
            "leasegrid:join#v=1&i=pb://FAKE-TUBID@127.0.0.1:1/FAKE-LINK",
            "http://example.i2p/join#v=1&i=pb://FAKE-TUBID@127.0.0.1:1/FAKE-PAGE",
        ]
    )
    out = scrub_bug_report(planted)
    assert about_line() in out
    assert platform.platform() in out
    for secret in (
        "FAKE-TUBID",
        "FAKE-SWISS",
        "FAKE-LINK",
        "FAKE-PAGE",
        "7-guitarist-revenge",
        "pb://",
        "leasegrid:",
    ):
        assert secret not in out


# Real-shaped fakes the scrubber does not know: base32 swissnum, tub id,
# DIR2 and CHK caps, and 32 hex digits. An 8-character piece is still a leak.
_SWISS = "qpwoeirutyalskdjfhgmznxbcv234567"
_TUB = "mnbvcxzlkjhgfdsapoiuytrewq765432"
_DIR2 = "URI:DIR2:" + ("a" * 26) + ":" + ("b" * 52)
_CHK = "URI:CHK:" + ("c" * 26) + ":" + ("d" * 52) + ":1:1:9"
_HEX = "a1b2c3d4e5f60718293a4b5c6d7e8f90"


def _eight_char_pieces(secret: str) -> list[str]:
    return [secret[i : i + 8] for i in range(len(secret) - 7)]


def test_bug_report_omits_secrets_planted_in_logs_and_env(tmp_path: Path, monkeypatch) -> None:
    window = _window(tmp_path)
    logs = window.home / "logs"
    logs.mkdir(parents=True)
    (logs / UI_LOG_NAME).write_text(
        "\n".join(
            [
                "pb://FAKE-TUBID@127.0.0.1:1/FAKE-LOGSW",
                "7-log-secret",
                "leasegrid:join#v=1&i=pb://FAKE-TUBID@127.0.0.1:1/FAKE-LOGURL",
                _SWISS,
                _CHK,
                _HEX,
            ]
        ),
        encoding="utf-8",
    )
    (window.tahoe.nodedir / "tahoe.cfg").write_text(
        "[node]\ntubid = %s\n%s\n" % (_TUB, _DIR2),
        encoding="utf-8",
    )
    (window.home / "credit-wallet.json").write_text('{"seed":"%s"}\n' % _HEX, encoding="utf-8")
    monkeypatch.setenv("LEASEGRID_PLANTED_FURL", "pb://FAKE-TUBID@127.0.0.1:1/FAKE-ENVSW")
    monkeypatch.setenv("LEASEGRID_PLANTED_CODE", "4-env-planted")
    monkeypatch.setenv("LEASEGRID_PLANTED_HEX", _HEX)
    window.status_chip.setText("Online pb://FAKE-TUBID@127.0.0.1:1/FAKE-CHIP")
    window.share_url_edit.setText(_DIR2)
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    window._invite_session = InviteCodeSession(code=_SWISS, proc=proc)
    window._joined = True
    try:
        lines = window.bug_report_lines()
        assert lines == [
            about_line(),
            platform.platform(),
            "Chip: Online pb://FAKE-TUBID@127.0.0.1:1/FAKE-CHIP",
            "Joined: yes",
            "0 folders",
            "Logs: %s" % display_path(window.home / "logs"),
        ]
        raw = "\n".join(lines)
        text = window.bug_report_text()
        assert text == scrub_bug_report(raw)
        window.QtWidgets.QApplication.clipboard().setText("STALE")
        window.copy_bug_btn.click()
        clip = window.QtWidgets.QApplication.clipboard().text()
        assert clip == scrub_bug_report(raw)
        for secret in (
            "FAKE-LOGSW",
            "FAKE-LOGURL",
            "FAKE-ENVSW",
            "FAKE-CHIP",
            "7-log-secret",
            "4-env-planted",
            "pb://",
        ):
            assert secret not in clip
        for secret in (_SWISS, _TUB, _DIR2, _CHK, _HEX):
            for piece in _eight_char_pieces(secret):
                assert piece not in clip
    finally:
        if window._invite_session is not None:
            window._invite_session.close()
        _close(window)


def test_copy_bug_report_has_about_line_and_no_secrets(tmp_path: Path) -> None:
    window = _window(tmp_path)
    furl = "pb://FAKE-TUBID@127.0.0.1:1/FAKE-SWISS"
    (window.tahoe.nodedir / "tahoe.cfg").write_text(
        "[node]\nintroducer.furl = %s\n" % furl,
        encoding="utf-8",
    )
    (window.home / "credit-wallet.json").write_text('{"seed":"SECRET-WALLET"}\n', encoding="utf-8")
    window.share_url_edit.setText("http://example.i2p/join#invite-fragment")
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    window._invite_session = InviteCodeSession(code="7-planted-invite", proc=proc)
    window._joined = True
    window.status_chip.setText("Online — 1 computer storing files")
    window._render_rows(
        [FolderRow(name="secret-folder-name", path="/tmp/secret-folder-name", status="Up to date")]
    )
    button = window.settings_tab.findChild(window.QtWidgets.QPushButton, "copyBugReport")
    assert button is not None and button.text() == "Copy bug-report details"
    try:
        window.QtWidgets.QApplication.clipboard().setText("STALE")
        button.click()
        clip = window.QtWidgets.QApplication.clipboard().text()
        assert about_line() in clip
        assert platform.platform() in clip
        assert "Chip: Online — 1 computer storing files" in clip
        assert "Joined: yes" in clip
        assert "1 folder: Up to date" in clip
        assert "secret-folder-name" not in clip
        assert display_path(window.home / "logs") in clip
        assert_no_raw_user_text(clip)
        assert "pb://" not in clip
        assert "FAKE-SWISS" not in clip
        assert "7-planted-invite" not in clip
        assert "SECRET-WALLET" not in clip
        assert "invite-fragment" not in clip
        assert window.settings_status.text() == "Copied. Paste it into your bug report."
    finally:
        if window._invite_session is not None:
            window._invite_session.close()
        _close(window)
