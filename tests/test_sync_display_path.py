"""Shown paths hide the account name, including through a symlinked home."""

from __future__ import annotations

import sys
from pathlib import Path

from unittest.mock import patch

from leasegrid_sync.app import MainWindow, display_path, mask_shown_paths
from leasegrid_sync.backend import SyncError


def _tilde(tail: str) -> str:
    if not tail or tail == ".":
        return "~"
    if sys.platform == "win32":
        return "~\\" + tail.replace("/", "\\")
    return "~/" + tail


def _home(tmp_path: Path, monkeypatch) -> tuple[Path, Path]:
    """A symlinked home whose leaf is a fake account name."""
    real = tmp_path / "real" / "fakeuser"
    real.mkdir(parents=True)
    link = tmp_path / "link-home"
    link.symlink_to(real, target_is_directory=True)
    monkeypatch.setenv("HOME", str(link))
    monkeypatch.setenv("USERPROFILE", str(link))
    monkeypatch.setattr(Path, "home", lambda *_args, **_kwargs: link)
    return link, real


def test_display_path_table(tmp_path: Path, monkeypatch) -> None:
    link, real = _home(tmp_path, monkeypatch)
    inside_link = str(link / "logs" / "tahoe.log")
    inside_real = str(real / "logs" / "tahoe.log")
    escape = str(link / ".." / "otheruser" / "x")
    outside = str(tmp_path / "srv" / "zeldaq")
    folded = inside_real.swapcase()
    rows = [
        ("", ""),
        (str(link), "~"),
        (inside_link, _tilde("logs/tahoe.log")),
        (inside_real, _tilde("logs/tahoe.log")),
        (outside, outside),
    ]
    for raw, expected in rows:
        assert display_path(raw) == expected, raw
    escaped = display_path(escape)
    assert not escaped.startswith("~"), escaped
    assert "otheruser" in escaped
    assert "fakeuser" not in escaped
    hint = "or a pb:// furl"
    assert mask_shown_paths(hint) == hint
    cased = display_path(folded)
    if sys.platform in ("win32", "darwin"):
        # The prefix is folded to match home; the tail keeps the typed case.
        assert cased.casefold() == _tilde("logs/tahoe.log").casefold(), cased
        assert cased.startswith("~"), cased
    else:
        # Linux paths are case-sensitive, so a different case stays visible.
        assert cased == folded


def test_display_path_collapses_dotdot_that_leaves_home(monkeypatch) -> None:
    """A path that steps out of home does not keep the account name."""
    if sys.platform == "win32":
        home = Path("C:/Users/u")
        raw = "C:/Users/u/../other/x"
        expected = "C:\\Users\\other\\x"
    else:
        home = Path("/home/u")
        raw = "/home/u/../other/x"
        expected = "/home/other/x"
    monkeypatch.setattr(Path, "home", lambda *_args, **_kwargs: home)
    assert display_path(raw) == expected
    assert "u" not in Path(display_path(raw)).parts
    assert display_path("pb://user@host/code") == "pb://user@host/code"
    assert display_path("other/../x") == "other/../x"


def test_join_banner_hides_the_account_name(tmp_path: Path, monkeypatch) -> None:
    link, real = _home(tmp_path, monkeypatch)
    log = real / "logs" / "tahoe.log"
    nodedir = tmp_path / "tahoe"
    nodedir.mkdir()
    (nodedir / "tahoe.cfg").write_text("[node]\n", encoding="utf-8")
    with patch(
        "leasegrid_sync.app.TahoeClient.join_existing",
        side_effect=SyncError("could not join this friendnet. No Tahoe.", "Retry."),
    ):
        window = MainWindow(nodedir=nodedir, home=link / "LeasegridSync")
    try:
        window.show_join_error(
            SyncError("Tahoe exited while starting. see %s; Retry." % log, "Retry.")
        )
        text = window.join_error.text()
        assert "fakeuser" not in text
        assert "~" in text
        assert "tahoe.log" in text
    finally:
        window.poll.stop()
        window.win.hide()
