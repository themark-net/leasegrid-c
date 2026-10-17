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
        assert cased == _tilde("logs/tahoe.log"), cased
    else:
        # Linux paths are case-sensitive, so a different case stays visible.
        assert cased == folded


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
