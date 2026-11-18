"""Design's two strings for #90 slice D (PM, 2026-11-17 11:14pm PT).

1. Folder refresh failure keeps "Couldn't refresh folders." The Next line
   names a control that really exists in the window: "Restart Sync" if there
   is such a button or menu item, else the folders view's Refresh button,
   else "quit and reopen Leasegrid Sync". No Retry, no issue number, and a
   repeated failure shows the same pair with no count or code.
2. User-visible invite hints and the --join help say "join link", never
   "pb://". pb:// stays in code, logs and tests.
"""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import patch

import pytest

from leasegrid_sync import backend as backend_mod
from leasegrid_sync.backend import SyncError, validate_introducer_furl
from leasegrid_sync.cli import build_parser, main
from tests.test_design_copy_90 import assert_clean
from tests.test_sync_backend import _mf_api_ready, _poison_http

REFRESH_MSG = "Couldn't refresh folders."
NEXT_RESTART = "Wait a minute, then Restart Sync."
NEXT_REFRESH = "Wait a minute, then click Refresh."
NEXT_REOPEN = "Wait a minute, then quit and reopen Leasegrid Sync."
JOIN_HELP = (
    "Join a shared folder with the full join link (in the app, Share invite, "
    "then tick Show full join link (advanced))."
)
JOIN_HELP_LINE = "--join LINK  " + JOIN_HELP
INVITE_BANNED = ("pb://", "furl")
ISSUE_NUMBER = re.compile(r"#\d+")
# Inputs that reach each of the three invite hints in validate_introducer_furl.
INVITE_INPUTS = ("", "   ", "https://example.com/", "http://leasegrid.i2p/", "pb:/nope", "word-word")


def assert_join_link_words(text: str) -> None:
    """Guard for invite hints and the --join help: no pb://, no furl, no issue number."""
    for word in INVITE_BANNED:
        assert word not in text.lower(), (word, text)
    assert not ISSUE_NUMBER.search(text), text


def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _join_action():
    parser = build_parser()
    return next(a for a in parser._actions if "--join" in a.option_strings)


def test_join_help_is_designs_line_exactly():
    action = _join_action()
    assert action.metavar == "LINK"
    assert action.help == JOIN_HELP
    assert_join_link_words(action.help)


def test_join_help_line_shows_in_cli_help(capsys):
    with pytest.raises(SystemExit):
        main(["--help"])
    out = capsys.readouterr().out
    assert _squash(JOIN_HELP_LINE) in _squash(out)


@pytest.mark.parametrize("text", INVITE_INPUTS)
def test_invite_hints_say_join_link_not_pb(text: str):
    with pytest.raises(SyncError) as exc:
        validate_introducer_furl(text)
    hint = exc.value.next_hint or ""
    assert "join link" in hint, hint
    assert_join_link_words(hint)
    assert "pb://" not in exc.value.banner()


def test_pb_guard_catches_pb_and_furl():
    for bad in ("Paste the pb:// address.", "or pb://…", "Invite furl", "see #90"):
        with pytest.raises(AssertionError):
            assert_join_link_words(bad)
    assert_join_link_words("Paste the full join link.")


def test_ui_labels_named_by_the_join_help_exist():
    """The help sends people to Share invite, then Show full join link (advanced)."""
    src = Path(backend_mod.__file__).with_name("app.py").read_text(encoding="utf-8")
    assert 'QPushButton("Share invite")' in src
    assert 'QCheckBox("Show full join link (advanced)")' in src


def _window_labels(tmp_path: Path):
    pytest.importorskip("PyQt5")
    from PyQt5 import QtWidgets

    from leasegrid_sync.app import MainWindow

    window = MainWindow(home=tmp_path / "home", autoload=False)
    try:
        window.poll.stop()
        everywhere = {b.text() for b in window.win.findChildren(QtWidgets.QAbstractButton)}
        everywhere |= {a.text() for a in window.win.findChildren(QtWidgets.QAction)}
        folders = {b.text() for b in window.folders_tab.findChildren(QtWidgets.QAbstractButton)}
        folders |= {a.text() for a in window.folders_tab.findChildren(QtWidgets.QAction)}
    finally:
        window.win.hide()
        if window.tray is not None:
            window.tray.hide()
    return window, everywhere, folders


def test_refresh_next_line_names_a_control_that_exists(tmp_path: Path):
    _, everywhere, folders = _window_labels(tmp_path)
    if "Restart Sync" in everywhere:
        expected = NEXT_RESTART
    elif "Refresh" in folders:
        expected = NEXT_REFRESH
    else:
        expected = NEXT_REOPEN
    assert backend_mod.REFRESH_FAIL_MSG == REFRESH_MSG
    assert backend_mod.REFRESH_FAIL_NEXT == expected
    assert_clean(backend_mod.REFRESH_FAIL_NEXT)
    assert "Share invite" in everywhere


def test_repeated_refresh_500_keeps_the_generic_pair(tmp_path: Path, monkeypatch):
    ctl = _mf_api_ready(tmp_path)

    def boom(req, timeout=10):
        raise _poison_http(500)

    monkeypatch.setattr(backend_mod.urllib.request, "urlopen", boom)
    seen = []
    with patch.object(ctl, "ensure_running", return_value=None):
        for _ in range(3):
            with pytest.raises(SyncError) as exc:
                ctl.list_folders()
            seen.append((exc.value.message, exc.value.next_hint, exc.value.banner()))
    assert len(set(seen)) == 1
    message, hint, banner = seen[0]
    assert (message, hint) == (REFRESH_MSG, backend_mod.REFRESH_FAIL_NEXT)
    assert not re.search(r"\d", banner), banner
    assert_clean(banner)


def test_repeated_refresh_failure_in_the_window_shows_no_count(tmp_path: Path, monkeypatch):
    window, _, _ = _window_labels(tmp_path)
    err = SyncError(backend_mod.REFRESH_FAIL_MSG, backend_mod.REFRESH_FAIL_NEXT, http_status=500)
    window._joined = True
    monkeypatch.setattr(window.tahoe, "connection_status", lambda: backend_mod.ConnectionStatus(
        state="Connected", detail="introducer up · 3 storage", introducer_ok=True, servers_connected=3))
    monkeypatch.setattr(window, "_refresh_servers", lambda status: None)
    monkeypatch.setattr(window, "_refresh_offer_viz", lambda: None)

    def fail():
        raise err

    monkeypatch.setattr(window.mf, "list_folders", fail)
    shown = []
    for _ in range(3):
        window.refresh()
        shown.append(window.folder_error.text())
    assert len(set(shown)) == 1, shown
    assert REFRESH_MSG in shown[0]
    assert backend_mod.REFRESH_FAIL_NEXT in shown[0]
    assert not re.search(r"\d", shown[0]), shown[0]
    assert_clean(shown[0])
