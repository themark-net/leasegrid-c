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
    assert "--credit-status" in text
    assert "--credit-dogfood" in text


def test_status_uses_nodedir(tmp_path, capsys):
    nodedir = tmp_path / "tahoe"
    nodedir.mkdir()
    (nodedir / "tahoe.cfg").write_text("[node]\n", encoding="utf-8")
    code = main(["--status", "--nodedir", str(nodedir)])
    out = capsys.readouterr().out
    assert code == 1
    assert "FAIL" in out or "Offline" in out or str(nodedir) in out


def test_join_headless_rejects_bad_invite_without_tahoe(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("LEASEGRID_SYNC_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("PATH", str(tmp_path / "empty-bin"))
    monkeypatch.delenv("LEASEGRID_TAHOE_BIN", raising=False)
    code = main(["--join", "not-a-furl", "--nodedir", str(tmp_path / "tahoe")])
    err = capsys.readouterr().err
    assert code == 1
    assert "FAIL" in err
    assert not (tmp_path / "tahoe").exists()


def test_recovery_flags_present_and_export_fails_closed_when_not_joined(tmp_path, monkeypatch, capsys):
    text = build_parser().format_help()
    assert "--export-recovery" in text and "--restore-recovery" in text and "--join" in text
    monkeypatch.setenv("LEASEGRID_SYNC_HOME", str(tmp_path / "home"))
    code = main(["--export-recovery", str(tmp_path / "k"), "--nodedir", str(tmp_path / "tahoe")])
    err = capsys.readouterr().err
    assert code == 1
    assert "No friendnet joined yet" in err
    assert not (tmp_path / "k").exists()


def test_credit_status_fail_closed(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("LEASEGRID_SYNC_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("LEASEGRID_ISSUER_URL", "http://127.0.0.1:1")
    code = main(["--credit-status"])
    err = capsys.readouterr().err
    assert code == 1
    assert "FAIL" in err
    assert "could not load credit balance" in err
