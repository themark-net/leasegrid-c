"""U2 credit: denomination, faucet redeem, FAIL, no 1:1 lie, no opaque convert."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from leasegrid_sync.backend import SyncError
from leasegrid_sync.credit import (
    DENOMINATION_NOTE,
    LAB_NOTE,
    OPAQUE_REJECT,
    TIER_TOKENS,
    XMR_LATER,
    CreditCtl,
    credit_gate,
    estimate_share_tokens,
    format_remaining,
    is_leasegrid_wallet,
    merge_wallets,
)
from leasegrid_zkap.client import faucet_mint
from leasegrid_zkap.constants import DENOMINATION
from leasegrid_zkap.crypto import generate_signing_key
from leasegrid_zkap.issuer import start_issuer


@pytest.fixture
def issuer():
    key = generate_signing_key()
    state, httpd = start_issuer(key, "127.0.0.1:0")
    try:
        yield state
    finally:
        httpd.shutdown()


def test_format_remaining_zero_is_explicit():
    text = format_remaining(0)
    assert "none" in text.lower()
    assert "top up" in text.lower()


def test_format_remaining_plain_language():
    text = format_remaining(48)
    assert "About 48 GiB" in text
    assert "30 days" in text
    assert "friendnet" in text
    assert "disk free" not in text.lower()


def test_denomination_honesty_rejects_one_to_one():
    blob = DENOMINATION_NOTE + "\n" + format_remaining(12) + "\n" + LAB_NOTE
    assert "1 GiB-share" in blob or "one node" in blob
    assert "expand" in blob.lower()
    assert "1 GiB upload = 1 GiB credit" not in blob
    assert "1:1" not in blob


def test_xmr_is_later_label_only():
    assert "XMR" in XMR_LATER
    assert "not available" in XMR_LATER.lower()


def test_credit_gate():
    assert credit_gate(0, 0) == "zero"
    assert credit_gate(0, 5) == "zero"
    assert credit_gate(10, 4) == "ok"
    assert credit_gate(10, 11) == "review"


def test_estimate_share_tokens_expansion_not_one_to_one():
    one_gib = 2**30
    need = estimate_share_tokens(one_gib)
    assert need >= 3
    assert need != 1


def test_opaque_wallet_rejected():
    assert not is_leasegrid_wallet({"vouchers": ["abc"], "tokens": []})
    assert not is_leasegrid_wallet("not-json")
    good = {
        "issuer-pubkey-id": "aa",
        "tokens": [{"t": "t", "W": "w"}],
        "denomination": DENOMINATION,
    }
    assert is_leasegrid_wallet(good)


def test_merge_rejects_foreign_issuer():
    a = {"issuer-pubkey-id": "one", "tokens": [{"t": "t1", "W": "w1"}]}
    b = {"issuer-pubkey-id": "two", "tokens": [{"t": "t2", "W": "w2"}]}
    with pytest.raises(SyncError) as exc:
        merge_wallets(a, b)
    assert "different issuer" in exc.value.banner().lower() or "opaque" in exc.value.banner().lower()


def test_reject_opaque_import(tmp_path: Path):
    ctl = CreditCtl(home=tmp_path, issuer_url="http://127.0.0.1:9")
    with pytest.raises(SyncError) as exc:
        ctl.reject_opaque_import('{"vouchers":[]}')
    assert OPAQUE_REJECT.split(".")[0] in exc.value.banner()


def test_load_balance_issuer_down(tmp_path: Path):
    ctl = CreditCtl(home=tmp_path, issuer_url="http://127.0.0.1:1")
    with pytest.raises(SyncError) as exc:
        ctl.load_balance()
    text = exc.value.banner()
    assert "FAIL" in text
    assert "could not load credit balance" in text
    assert "Next:" in text
    assert "Retry" in text


def test_load_balance_zero_when_no_wallet(tmp_path: Path, issuer):
    ctl = CreditCtl(home=tmp_path, issuer_url=issuer.listen)
    snap = ctl.load_balance()
    assert snap.balance.tokens == 0
    assert "none" in snap.remaining_text.lower()
    assert snap.balance.issuer_pubkey_id == issuer.info["issuer-pubkey-id"]


def test_opaque_wallet_file_fails_load(tmp_path: Path, issuer):
    wallet = tmp_path / "credit-wallet.json"
    wallet.write_text(json.dumps({"vouchers": ["foreign-zkap"], "tokens": []}), encoding="utf-8")
    ctl = CreditCtl(home=tmp_path, issuer_url=issuer.listen, wallet_path=wallet)
    with pytest.raises(SyncError) as exc:
        ctl.load_balance()
    assert "will not convert" in exc.value.banner().lower() or "opaque" in exc.value.banner().lower()


def test_redeem_faucet_updates_balance(tmp_path: Path, issuer):
    ctl = CreditCtl(home=tmp_path, issuer_url=issuer.listen)
    before = ctl.load_balance()
    assert before.balance.tokens == 0
    snap = ctl.redeem_faucet(count=2)
    assert snap.balance.tokens == 2
    assert "About 2 GiB" in snap.remaining_text
    assert snap.recent
    assert snap.recent[0].title == "Faucet top-up"
    again = ctl.load_balance()
    assert again.balance.tokens == 2
    second = ctl.redeem_faucet(count=2)
    assert second.balance.tokens == 4


def test_redeem_uses_real_issue_endpoint(tmp_path: Path, issuer):
    ctl = CreditCtl(home=tmp_path, issuer_url=issuer.listen, mint_fn=faucet_mint)
    snap = ctl.redeem_faucet(count=1)
    assert snap.balance.tokens == 1
    wallet = json.loads((tmp_path / "credit-wallet.json").read_text(encoding="utf-8"))
    assert wallet["issuer-pubkey-id"] == issuer.info["issuer-pubkey-id"]
    assert wallet["tokens"][0]["t"]
    assert wallet["tokens"][0]["W"]


def test_redeem_fail_leaves_balance_unchanged(tmp_path: Path, issuer):
    def boom(url, count):
        raise RuntimeError("faucet down")

    ctl = CreditCtl(home=tmp_path, issuer_url=issuer.listen, mint_fn=boom)
    with pytest.raises(SyncError) as exc:
        ctl.redeem_faucet(count=2)
    assert "top-up did not complete" in exc.value.banner()
    assert "Balance unchanged" in exc.value.banner()
    assert ctl.remaining_tokens() == 0
    assert not (tmp_path / "credit-wallet.json").is_file()


def test_tier_sizes():
    assert TIER_TOKENS["small"] == 10
    assert TIER_TOKENS["medium"] == 50
    assert TIER_TOKENS["large"] == 100
