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
    credit_enforced,
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


def test_xmr_copy_does_not_claim_received_before_confirm():
    assert "XMR" in XMR_LATER
    assert "received" not in XMR_LATER.lower()
    assert "1:1" not in XMR_LATER


def test_credit_gate():
    assert credit_gate(0, 0) == "zero"
    assert credit_gate(0, 5) == "zero"
    assert credit_gate(10, 4) == "ok"
    assert credit_gate(10, 11) == "review"


def test_credit_enforced_reads_gated_env(monkeypatch):
    monkeypatch.delenv("LEASEGRID_GATED", raising=False)
    assert credit_enforced() is False
    monkeypatch.setenv("LEASEGRID_GATED", "1")
    assert credit_enforced() is True
    monkeypatch.setenv("LEASEGRID_GATED", "true")
    assert credit_enforced() is True
    monkeypatch.setenv("LEASEGRID_GATED", "0")
    assert credit_enforced() is False


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
    assert TIER_TOKENS["large"] == 200


def test_recent_refusal_reads_spender_events(tmp_path: Path):
    import time

    ctl = CreditCtl(home=tmp_path, issuer_url="http://127.0.0.1:1")
    assert ctl.recent_refusal() is None
    ctl.recent_path.write_text(json.dumps({"events": [
        {"title": "Upload refused: out of credit", "tokens": 0, "ts": time.time()},
        {"title": "Faucet top-up", "tokens": 10, "ts": time.time() - 100},
    ]}))
    assert ctl.recent_refusal() == "Upload refused: out of credit"
    # stale refusal is not a current problem
    ctl.recent_path.write_text(json.dumps({"events": [
        {"title": "Upload refused: out of credit", "tokens": 0, "ts": time.time() - 3600},
    ]}))
    assert ctl.recent_refusal() is None
    # newest event is a spend -> uploads are flowing
    ctl.recent_path.write_text(json.dumps({"events": [
        {"title": "Lease on abc · def", "tokens": -1, "ts": time.time()},
        {"title": "Upload refused: out of credit", "tokens": 0, "ts": time.time()},
    ]}))
    assert ctl.recent_refusal() is None


def _serve_bytes(payload: bytes):
    """One-shot TCP server: accept, send payload (maybe nothing), close."""
    import socket
    import threading

    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)

    def run():
        conn, _ = srv.accept()
        try:
            conn.recv(4096)
            if payload:
                conn.sendall(payload)
        finally:
            conn.close()
            srv.close()

    threading.Thread(target=run, daemon=True).start()
    return "http://127.0.0.1:%d" % srv.getsockname()[1]


def test_ping_issuer_wraps_non_http_service_as_sync_error(tmp_path: Path):
    """Issuer URL pointing at a non-HTTP port (RemoteDisconnected) is a FAIL, not a crash."""
    url = _serve_bytes(b"")
    ctl = CreditCtl(home=tmp_path, issuer_url=url)
    with pytest.raises(SyncError) as exc:
        ctl.ping_issuer()
    assert "could not load credit balance" in exc.value.message


def test_ping_issuer_wraps_non_json_body_as_sync_error(tmp_path: Path):
    url = _serve_bytes(b"HTTP/1.0 200 OK\r\nContent-Type: text/html\r\nContent-Length: 6\r\n\r\n<html>")
    ctl = CreditCtl(home=tmp_path, issuer_url=url)
    with pytest.raises(SyncError) as exc:
        ctl.ping_issuer()
    assert "could not load credit balance" in exc.value.message


def test_load_balance_collects_pending_xmr_topups(tmp_path: Path):
    """Crash after paying → open Credit → the confirmed voucher is collected (07-payment.md §5.2)."""
    from leasegrid_zkap.client import http_json
    from leasegrid_zkap.issuer import start_issuer as start_pay_issuer
    from leasegrid_zkap.payment import FakeChain, PricePolicy
    from leasegrid_zkap.payment.topup import TopUpClient

    PRICE = 6 * 10**9
    state, httpd = start_pay_issuer(
        generate_signing_key(), "127.0.0.1:0", chain=FakeChain(), policy=PricePolicy(price_piconero=PRICE), faucet=False
    )
    try:
        ctl = CreditCtl(home=tmp_path, issuer_url=state.listen)
        assert ctl.load_balance().balance.tokens == 0  # no state file yet: nothing to do
        tc = TopUpClient(state.listen, ctl.wallet_path, ctl.topup_state_path)
        q = tc.quote(3)
        assert ctl.load_balance().balance.tokens == 0  # quoted, unpaid
        http_json(state.listen + "/v0/fake/pay", "POST", {"vid": q["vid"], "amount_piconero": 3 * PRICE, "mine": 2})
        snap = ctl.load_balance()
        assert snap.balance.tokens == 3
        assert snap.recent and snap.recent[0].title == "XMR top-up" and snap.recent[0].delta == "+3 GiB·mo"
        assert ctl.load_balance().balance.tokens == 3  # idempotent
    finally:
        httpd.shutdown()


def test_quote_and_poll_topup_against_fake_issuer(tmp_path: Path):
    """CreditCtl methods the dialog calls, against a real FakeChain issuer."""
    from leasegrid_zkap.client import http_json
    from leasegrid_zkap.issuer import start_issuer as start_pay_issuer
    from leasegrid_zkap.payment import FakeChain, PricePolicy

    PRICE = 6 * 10**9
    state, httpd = start_pay_issuer(
        generate_signing_key(),
        "127.0.0.1:0",
        chain=FakeChain(),
        policy=PricePolicy(price_piconero=PRICE),
        faucet=False,
    )
    try:
        ctl = CreditCtl(home=tmp_path, issuer_url=state.listen)
        q = ctl.quote_topup(4)
        assert q["vid"] and q["address"] and q["amount_xmr"]
        assert ctl.pending_topups()
        idle = ctl.poll_topup(q["vid"])
        assert idle["state"] == "quoted"
        assert idle["tokens_added"] == 0
        http_json(
            state.listen + "/v0/fake/pay",
            "POST",
            {"vid": q["vid"], "amount_piconero": 4 * PRICE, "mine": 2},
        )
        issued = ctl.poll_topup(q["vid"])
        assert issued["state"] == "issued"
        assert issued["tokens_added"] == 4
        snap = ctl.load_balance()
        assert snap.balance.tokens == 4
        assert snap.recent and snap.recent[0].title == "XMR top-up"

        q2 = ctl.quote_topup(4)
        http_json(
            state.listen + "/v0/fake/pay",
            "POST",
            {"vid": q2["vid"], "amount_piconero": PRICE // 2, "mine": 2},
        )
        short = ctl.poll_topup(q2["vid"])
        assert short["state"] == "underpaid"
        assert int(short["voucher"]["amount_seen"]) == PRICE // 2
        from leasegrid_sync.credit import underpaid_copy

        text = underpaid_copy(short["voucher"])
        assert "0.003" in text
        assert str(PRICE // 2) not in text
        assert "nothing is lost" in text.lower()
    finally:
        httpd.shutdown()


def test_gated_xmr_topup_increases_balance_unpaid_allocate_fails(tmp_path: Path, monkeypatch):
    """U5: quote → pay → redeem on FakeChain. Unpaid allocate still fails.

    LEASEGRID_GATED=1 does not mint faucet credit. A quote with no payment
    leaves the wallet empty, and the storage gate refuses allocate until a
    spent ZKAP exists.
    """
    from leasegrid_zkap.client import ClientError, http_json
    from leasegrid_zkap.errors import ZKAPRequired
    from leasegrid_zkap.gate import LeaseGate
    from leasegrid_zkap.payment import FakeChain, PricePolicy
    from leasegrid_zkap.spender import WalletSpender
    from leasegrid_zkap.spentset import SpentSet
    from leasegrid_zkap.storage_http import start_storage_http

    monkeypatch.setenv("LEASEGRID_GATED", "1")
    assert credit_enforced() is True

    price = 6 * 10**9
    key = generate_signing_key()
    state, httpd = start_issuer(
        key,
        "127.0.0.1:0",
        chain=FakeChain(),
        policy=PricePolicy(price_piconero=price),
        faucet=False,
    )
    nodeid = "node1aaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    si = bytes(range(16))
    gate = LeaseGate(key, nodeid=nodeid, spent=SpentSet(str(tmp_path / "spent.json")))
    storage_url, storage_httpd = start_storage_http(gate, "tcp:0:interface=127.0.0.1")
    try:
        ctl = CreditCtl(home=tmp_path, issuer_url=state.listen)
        assert ctl.load_balance().balance.tokens == 0
        assert credit_gate(ctl.remaining_tokens(), 1) == "zero"
        with pytest.raises(ZKAPRequired):
            gate.lab_allocate(si, [0], 64)
        with pytest.raises(ClientError) as unpaid_http:
            http_json(
                storage_url + "/v0/lab/allocate",
                "POST",
                {"storage_index": si.hex(), "sharenums": [0], "allocated_size": 64},
            )
        assert "403" in str(unpaid_http.value)

        quote = ctl.quote_topup(2)
        assert ctl.poll_topup(quote["vid"])["state"] == "quoted"
        assert ctl.remaining_tokens() == 0
        with pytest.raises(ZKAPRequired):
            gate.lab_allocate(si, [0], 64)

        paid = ctl.pay_quote(quote)
        assert paid.get("ok") is True
        assert paid.get("skipped") is not True
        issued = ctl.poll_topup(quote["vid"])
        assert issued["state"] == "issued"
        assert issued["tokens_added"] == 2
        snap = ctl.load_balance()
        assert snap.balance.tokens == 2
        assert snap.recent and snap.recent[0].title == "XMR top-up"

        # Tokens in the wallet are not a grant. Allocate stays refused until spend.
        with pytest.raises(ZKAPRequired):
            gate.lab_allocate(si, [0], 64)
        WalletSpender(ctl.wallet_path, recent_path=tmp_path / "credit-recent.json").ensure_grant_sync(
            storage_url, nodeid, gate.issuer_pubkey_id, si, 64
        )
        alloc = gate.lab_allocate(si, [0], 64)
        assert 0 in alloc["allocated"] or 0 in alloc["already-have"]
        # Dogfood entry: same quote → pay → redeem, no faucet.
        dogfood = ctl.complete_topup(1)
        assert dogfood.balance.tokens == 2
        with pytest.raises(ClientError) as faucet:
            http_json(state.listen + "/v0/issue", "POST", {"blinded-tokens": ["not-a-token"]})
        assert "404" in str(faucet.value)
    finally:
        storage_httpd.shutdown()
        httpd.shutdown()


def test_pay_stagenet_refuses_mainnet_and_sends_exact_amount():
    from leasegrid_sync.credit import pay_stagenet_transfer

    stagenet = "5" + ("A" * 94)
    sub = "7" + ("B" * 94)
    mainnet = "4" + ("C" * 94)
    calls: list[str] = []

    def rpc_mainnet_wallet(method, params):
        calls.append(method)
        if method == "get_address":
            return {"address": mainnet}
        raise AssertionError("transfer must not run against a mainnet wallet")

    with pytest.raises(SyncError) as exc:
        pay_stagenet_transfer(sub, 12 * 10**9, rpc=rpc_mainnet_wallet)
    assert "mainnet" in exc.value.message.lower()
    assert "transfer" not in calls

    calls.clear()

    def rpc_mainnet_dest(method, params):
        calls.append(method)
        raise AssertionError("mainnet destination must not reach the wallet")

    with pytest.raises(SyncError) as exc:
        pay_stagenet_transfer(mainnet, 12 * 10**9, rpc=rpc_mainnet_dest)
    assert "mainnet" in exc.value.message.lower()
    assert calls == []

    seen = {}

    def rpc_ok(method, params):
        calls.append(method)
        if method == "get_address":
            return {"address": stagenet}
        if method == "transfer":
            seen["params"] = params
            return {"tx_hash": "ab" * 32, "amount": params["destinations"][0]["amount"]}
        raise AssertionError(method)

    out = pay_stagenet_transfer(sub, 12 * 10**9, rpc=rpc_ok)
    assert out["tx_hash"]
    assert seen["params"]["destinations"] == [{"amount": 12 * 10**9, "address": sub}]
    assert calls == ["get_address", "transfer"]
