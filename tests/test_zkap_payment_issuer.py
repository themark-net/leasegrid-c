"""S1: issuer HTTP lifecycle against a FakeChain — quote → pay → confirm → redeem
(idempotent) → tokens verify → settlement lands in the ledger. No faucet."""

from __future__ import annotations

import pytest

from leasegrid_zkap.client import ClientError, http_json
from leasegrid_zkap.crypto import (
    client_tokens,
    generate_signing_key,
    mac_k_r,
    unblind_batch,
    verify_mac,
    wallet_record,
)
from leasegrid_zkap.issuer import pay_uri, start_issuer
from leasegrid_zkap.payment import FakeChain, PricePolicy, VoucherStore

PRICE = 6 * 10**9


@pytest.fixture
def issuer():
    key = generate_signing_key()
    chain = FakeChain()
    state, httpd = start_issuer(
        key,
        "127.0.0.1:0",
        chain=chain,
        policy=PricePolicy(price_piconero=PRICE),
        store=VoucherStore(),
        faucet=False,
    )
    yield state, chain, key
    httpd.shutdown()


def _b64(x) -> str:
    v = x.encode_base64()
    return v.decode("ascii") if isinstance(v, bytes) else str(v)


def _post(url, path, body):
    return http_json(url + path, "POST", body)


def _post_status(url, path, body) -> tuple[int, str]:
    try:
        _post(url, path, body)
        return 200, ""
    except ClientError as e:
        msg = str(e)
        code = int(msg.split("-> ")[1].split(" ")[0])
        return code, msg


def test_keys_and_info_describe_payment_surface(issuer):
    state, chain, key = issuer
    keys = http_json(state.listen + "/v0/keys")
    assert keys["current"] == 0
    assert keys["epochs"][0]["scheme"] == "ristretto-v0"
    assert keys["epochs"][0]["issuer-pubkey-id"] == state.info["issuer-pubkey-id"]
    assert keys["price_piconero"] == PRICE and keys["chain"] == "fake"
    info = http_json(state.listen + "/v0/info")
    assert info["faucet"] is False and info["chain"] == "fake"


def test_faucet_is_off_unless_asked(issuer):
    state, _, _ = issuer
    _, blinded = client_tokens(2)
    code, msg = _post_status(state.listen, "/v0/issue", {"blinded-tokens": [_b64(b) for b in blinded]})
    assert code == 404 and "faucet disabled" in msg


def test_full_lifecycle_quote_pay_confirm_redeem(issuer):
    state, chain, key = issuer
    url = state.listen

    q = _post(url, "/v0/quote", {"tokens": 20})
    assert q["state"] == "quoted" and q["tokens_quoted"] == 20
    assert q["amount_piconero"] == 20 * PRICE and q["amount_xmr"] == "0.12"
    assert q["pay_uri"] == pay_uri(q["address"], 20 * PRICE, q["vid"])
    assert q["pay_uri"].startswith("monero:%s?tx_amount=0.12&tx_description=leasegrid%%20%s" % (q["address"], q["vid"]))
    assert q["confirmations_required"] == 2
    vid = q["vid"]

    tokens, blinded = client_tokens(20)
    blinded_b64 = [_b64(b) for b in blinded]

    code, msg = _post_status(url, "/v0/redeem", {"vid": vid, "blinded-tokens": blinded_b64})
    assert code == 402 and '"state": "quoted"' in msg

    # buyer pays exactly the quoted amount (0 conf)
    _post(url, "/v0/fake/pay", {"vid": vid, "amount_piconero": 20 * PRICE})
    v = http_json(url + "/v0/voucher/" + vid)
    assert v["state"] == "seen" and v["amount_seen"] == 20 * PRICE and v["amount_confirmed"] == 0
    code, msg = _post_status(url, "/v0/redeem", {"vid": vid, "blinded-tokens": blinded_b64})
    assert code == 402 and '"state": "seen"' in msg

    _post(url, "/v0/fake/mine", {"blocks": 1})
    v = http_json(url + "/v0/voucher/" + vid)
    assert v["state"] == "confirming" and v["confirmations"] == 1

    _post(url, "/v0/fake/mine", {"blocks": 1})
    v = http_json(url + "/v0/voucher/" + vid)
    assert v["state"] == "payable" and v["tokens_owed"] == 20 and v["effective_price"] == PRICE

    # wrong batch size is a 400 with the right number in it
    code, msg = _post_status(url, "/v0/redeem", {"vid": vid, "blinded-tokens": blinded_b64[:3]})
    assert code == 400 and '"tokens_owed": 20' in msg

    first = _post(url, "/v0/redeem", {"vid": vid, "blinded-tokens": blinded_b64})
    assert first["cached"] is False and len(first["signed-tokens"]) == 20
    again = _post(url, "/v0/redeem", {"vid": vid, "blinded-tokens": blinded_b64})
    assert again["cached"] is True and again["signed-tokens"] == first["signed-tokens"]
    assert state.issue_count == 1

    # unblind, DLEQ verifies, and every token passes the storage-side MAC check
    unblinded = unblind_batch(tokens, blinded, first["signed-tokens"], first["proof"], first["public-key"])
    assert len(unblinded) == 20
    r = b"leasegrid-v0|node|si|2592000|1073741824|0|" + state.info["issuer-pubkey-id"].encode()
    for u in unblinded:
        rec = wallet_record(u)
        verify_mac(key, rec["t"], r, mac_k_r(u, r))

    # a different batch for the same vid is refused; nothing more signed
    _, other = client_tokens(20)
    code, msg = _post_status(url, "/v0/redeem", {"vid": vid, "blinded-tokens": [_b64(b) for b in other]})
    assert code == 409
    assert state.issue_count == 1

    v = http_json(url + "/v0/voucher/" + vid)
    assert v["state"] == "issued" and v["tokens_issued"] == 20
    led = http_json(url + "/v0/ledger")
    assert led["epochs"]["0"]["tokens_issued"] == 20
    assert led["epochs"]["0"]["xmr_received_piconero"] == 20 * PRICE


def test_client_supplied_vid_and_duplicate(issuer):
    state, chain, _ = issuer
    url = state.listen
    q = _post(url, "/v0/quote", {"tokens": 1, "vid": "00112233AABBCCDD"})
    assert q["vid"] == "00112233aabbccdd"
    code, _ = _post_status(url, "/v0/quote", {"tokens": 1, "vid": "00112233aabbccdd"})
    assert code == 409
    code, _ = _post_status(url, "/v0/quote", {"tokens": 1, "vid": "zz"})
    assert code == 400
    code, _ = _post_status(url, "/v0/quote", {"tokens": 0})
    assert code == 400
    code, _ = _post_status(url, "/v0/quote", {"tokens": 1, "scheme": "rsa-bssa-v1"})
    assert code == 400
    code, _ = _post_status(url, "/v0/quote", {"tokens": "5"})
    assert code == 400


def test_underpay_then_top_up_same_address(issuer):
    state, chain, _ = issuer
    url = state.listen
    q = _post(url, "/v0/quote", {"tokens": 2})
    _post(url, "/v0/fake/pay", {"address": q["address"], "amount_piconero": PRICE // 2, "mine": 2})
    v = http_json(url + "/v0/voucher/" + q["vid"])
    assert v["state"] == "underpaid" and v["tokens_owed"] == 0
    _post(url, "/v0/fake/pay", {"address": q["address"], "xmr": "0.003", "mine": 2})
    v = http_json(url + "/v0/voucher/" + q["vid"])
    assert v["state"] == "payable" and v["tokens_owed"] == 1  # 0.003 + 0.003 = one 0.006 token


def test_unknown_vid_and_bad_fake_calls(issuer):
    state, chain, _ = issuer
    url = state.listen
    code, _ = _post_status(url, "/v0/redeem", {"vid": "0000000000000000", "blinded-tokens": ["x"]})
    assert code == 404
    try:
        http_json(url + "/v0/voucher/0000000000000000")
    except ClientError as e:
        assert "404" in str(e)
    else:
        raise AssertionError("expected 404")
    code, _ = _post_status(url, "/v0/fake/pay", {"address": "nope", "amount_piconero": 5})
    assert code == 404
    code, _ = _post_status(url, "/v0/fake/pay", {"vid": "0000000000000000", "amount_piconero": 5})
    assert code == 404
    code, _ = _post_status(url, "/v0/fake/mine", {"blocks": 0})
    assert code == 400


def test_settlement_with_nodeid_lands_in_ledger_and_still_refuses_r(issuer):
    state, _, _ = issuer
    url = state.listen
    out = _post(url, "/v0/settlement", {"nodeid": "node-a", "epoch": 0, "spent-preimages": ["t1", "t2"]})
    assert out["stored-r"] is False and out["ledger"] == {"accepted": 2, "duplicates": 0, "conflicts": 0}
    out = _post(url, "/v0/settlement", {"nodeid": "node-b", "epoch": 0, "spent-preimages": ["t1"]})
    assert out["ledger"]["conflicts"] == 1
    code, msg = _post_status(url, "/v0/settlement", {"nodeid": "node-a", "spent-preimages": ["t3"], "R": "x"})
    assert code == 400 and "must not receive R" in msg
    led = http_json(url + "/v0/ledger")
    assert led["epochs"]["0"]["tokens_settled"] == 2 and led["settlement_conflicts"] == 1
    # legacy body without nodeid still accepted (0b settle CLI)
    out = _post(url, "/v0/settlement", {"spent-preimages": ["t9"]})
    assert out["accepted"] == 1 and "ledger" not in out


def test_no_chain_means_quote_503_and_fake_404():
    key = generate_signing_key()
    state, httpd = start_issuer(key, "127.0.0.1:0", chain=None, faucet=True)
    try:
        code, msg = _post_status(state.listen, "/v0/quote", {"tokens": 1})
        assert code == 503
        code, _ = _post_status(state.listen, "/v0/fake/mine", {"blocks": 1})
        assert code == 404
        assert http_json(state.listen + "/v0/keys")["chain"] == "none"
        # faucet still works where enabled (0b lab compatibility)
        _, blinded = client_tokens(1)
        out = _post(state.listen, "/v0/issue", {"blinded-tokens": [_b64(b) for b in blinded]})
        assert len(out["signed-tokens"]) == 1
    finally:
        httpd.shutdown()


def test_poller_thread_advances_vouchers():
    import time

    key = generate_signing_key()
    chain = FakeChain()
    state, httpd = start_issuer(
        key, "127.0.0.1:0", chain=chain, policy=PricePolicy(price_piconero=PRICE), faucet=False, poll_interval=0.05
    )
    try:
        q = _post(state.listen, "/v0/quote", {"tokens": 1})
        chain.pay(q["address"], PRICE)
        chain.mine(2)
        deadline = time.time() + 5
        while time.time() < deadline and state.store.get(q["vid"]).state != "payable":
            time.sleep(0.05)
        assert state.store.get(q["vid"]).state == "payable"
    finally:
        state.poll_stop.set()
        httpd.shutdown()
