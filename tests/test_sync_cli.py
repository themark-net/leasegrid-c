"""CLI help/status do not require a display; --help never mentions WUI as CTA."""

from __future__ import annotations

from leasegrid_sync.cli import build_parser, main


def test_help_describes_native_not_wui():
    p = build_parser()
    text = p.format_help() + " " + (p.description or "")
    assert "Leasegrid Sync" in text
    assert "Magic Folder" in text
    assert "Open web UI" not in text
    assert "native" in text.lower()


def test_status_uses_nodedir(tmp_path, capsys):
    nodedir = tmp_path / "tahoe"
    nodedir.mkdir()
    (nodedir / "tahoe.cfg").write_text("[node]\n", encoding="utf-8")
    code = main(["--status", "--nodedir", str(nodedir)])
    out = capsys.readouterr().out
    assert code == 1
    assert "FAIL" in out or "Offline" in out or str(nodedir) in out
