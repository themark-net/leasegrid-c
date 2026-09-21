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
    assert "--client-only" in text
    assert "--invite-url" in text
    assert "--export-invite-page" in text
    assert "i2p" in text.lower()


def test_exit_test_paid_join_is_client_only():
    """Gated installer proof: the paying home must not offer disk (or a lab node sees spent=0)."""
    from pathlib import Path

    text = (Path(__file__).resolve().parents[1] / "packaging" / "exit-test.sh").read_text(encoding="utf-8")
    assert 'client --join "$FURL" --client-only' in text
    assert "same invite offers disk" in text
    assert 'OUT="$T/offer.out" client --join "$FURL"' in text


def test_status_uses_nodedir(tmp_path, capsys):
    nodedir = tmp_path / "tahoe"
    nodedir.mkdir()
    (nodedir / "tahoe.cfg").write_text("[node]\n", encoding="utf-8")
    code = main(["--status", "--nodedir", str(nodedir)])
    out = capsys.readouterr().out
    assert code == 1
    assert "FAIL" in out or "Offline" in out or str(nodedir) in out


def test_invite_url_and_export_page(tmp_path, monkeypatch, capsys):
    nodedir = tmp_path / "tahoe"
    nodedir.mkdir()
    furl = "pb://hashhashhash@127.0.0.1:45001/swissnumswiss"
    (nodedir / "tahoe.cfg").write_text(
        "[node]\n[client]\nintroducer.furl = %s\nshares.needed = 2\n"
        "shares.happy = 3\nshares.total = 3\n" % furl,
        encoding="utf-8",
    )
    monkeypatch.setenv("LEASEGRID_JOIN_ORIGIN", "http://alice.i2p/join")
    code = main(["--invite-url", "--nodedir", str(nodedir)])
    out = capsys.readouterr().out.strip()
    assert code == 0
    assert out.startswith("http://alice.i2p/join#")
    assert furl not in out.split("#", 1)[0]
    page = tmp_path / "join.html"
    code = main(["--export-invite-page", str(page), "--nodedir", str(nodedir)])
    capsys.readouterr()
    assert code == 0
    html = page.read_text(encoding="utf-8")
    assert "alice.i2p/join#" in html
    assert "<svg" in html.lower()
    assert "cdn." not in html.lower()


def test_invite_url_fails_closed_when_not_joined(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("LEASEGRID_SYNC_HOME", str(tmp_path / "home"))
    code = main(["--invite-url", "--nodedir", str(tmp_path / "missing")])
    err = capsys.readouterr().err
    assert code == 1
    assert "No friendnet joined" in err
    assert not (tmp_path / "missing").exists()


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
    assert "--ack-threat" in text and "--ack-loss" in text and "--ack-store" in text
    monkeypatch.setenv("LEASEGRID_SYNC_HOME", str(tmp_path / "home"))
    code = main(
        [
            "--export-recovery",
            str(tmp_path / "k"),
            "--ack-threat",
            "--ack-loss",
            "--ack-store",
            "--nodedir",
            str(tmp_path / "tahoe"),
        ]
    )
    err = capsys.readouterr().err
    assert code == 1
    assert "No friendnet joined yet" in err
    assert not (tmp_path / "k").exists()


def test_export_without_dual_ack_writes_nothing(tmp_path, monkeypatch, capsys):
    """No silent one-click dump. Missing threat or either export ACK FAILs before a file exists."""
    monkeypatch.setenv("LEASEGRID_SYNC_HOME", str(tmp_path / "home"))
    key = tmp_path / "k.leasegrid-recovery"
    code = main(["--export-recovery", str(key), "--nodedir", str(tmp_path / "tahoe")])
    err = capsys.readouterr().err
    assert code == 1
    assert "FAIL" in err
    assert "one-click" in err or "acknowledg" in err
    assert not key.exists()
    code = main(
        ["--export-recovery", str(key), "--ack-threat", "--nodedir", str(tmp_path / "tahoe")]
    )
    err = capsys.readouterr().err
    assert code == 1
    assert not key.exists()
    assert "ack-loss" in err or "acknowledg" in err


def test_export_acks_from_env_still_fail_closed_when_not_joined(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("LEASEGRID_SYNC_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("LEASEGRID_RECOVERY_ACK_THREAT", "1")
    monkeypatch.setenv("LEASEGRID_RECOVERY_ACK_LOSS", "1")
    monkeypatch.setenv("LEASEGRID_RECOVERY_ACK_STORE", "1")
    key = tmp_path / "k.leasegrid-recovery"
    code = main(["--export-recovery", str(key), "--nodedir", str(tmp_path / "tahoe")])
    err = capsys.readouterr().err
    assert code == 1
    assert "No friendnet joined yet" in err
    assert not key.exists()


def test_restore_without_threat_ack_fails_closed(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("LEASEGRID_SYNC_HOME", str(tmp_path / "home"))
    key = tmp_path / "k.leasegrid-recovery"
    key.write_text("{}", encoding="utf-8")
    code = main(["--restore-recovery", str(key), "--nodedir", str(tmp_path / "tahoe")])
    err = capsys.readouterr().err
    assert code == 1
    assert "FAIL" in err
    assert "threat" in err.lower() or "acknowledg" in err.lower()


def test_credit_status_fail_closed(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("LEASEGRID_SYNC_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("LEASEGRID_ISSUER_URL", "http://127.0.0.1:1")
    code = main(["--credit-status"])
    err = capsys.readouterr().err
    assert code == 1
    assert "FAIL" in err
    assert "could not load credit balance" in err


def test_credit_status_collects_pending_xmr_topup(tmp_path, monkeypatch, capsys):
    """Exit-test path: quote + fake pay, then --credit-status collects the batch."""
    from leasegrid_zkap.client import http_json
    from leasegrid_zkap.crypto import generate_signing_key
    from leasegrid_zkap.issuer import start_issuer
    from leasegrid_zkap.payment import FakeChain, PricePolicy
    from leasegrid_zkap.payment.topup import TopUpClient

    price = 6 * 10**9
    home = tmp_path / "home"
    home.mkdir()
    state, httpd = start_issuer(
        generate_signing_key(), "127.0.0.1:0", chain=FakeChain(), policy=PricePolicy(price_piconero=price), faucet=False
    )
    try:
        monkeypatch.setenv("LEASEGRID_SYNC_HOME", str(home))
        monkeypatch.setenv("LEASEGRID_ISSUER_URL", state.listen)
        tc = TopUpClient(state.listen, home / "credit-wallet.json")
        q = tc.quote(4)
        http_json(state.listen + "/v0/fake/pay", "POST", {"vid": q["vid"], "amount_piconero": 4 * price, "mine": 2})
        code = main(["--credit-status"])
        out = capsys.readouterr().out
        assert code == 0
        assert out.startswith("4\t")
    finally:
        httpd.shutdown()
