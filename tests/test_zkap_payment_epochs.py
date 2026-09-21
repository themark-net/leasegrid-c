"""S8: epoch rotation, burn + /v0/exchange, node key pull.

docs/07-payment.md §2.5, §8. No Monero.
"""

from __future__ import annotations

import pytest

from leasegrid_zkap.client import ClientError, http_json
from leasegrid_zkap.crypto import (
    client_tokens,
    generate_signing_key,
    issuer_info,
    mac_k_r,
    unblind_batch,
    wallet_record,
)
from leasegrid_zkap.gate import LeaseGate
from leasegrid_zkap.issuer import start_issuer
from leasegrid_zkap.payment import FakeChain, PricePolicy, VoucherStore
from leasegrid_zkap.r_bind import encode_r
from leasegrid_zkap.spentset import SpentSet

PRICE = 6 * 10**9
NODEID = "node-epoch-test"


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


def _buy(url, tokens=3):
    q = _post(url, "/v0/quote", {"tokens": tokens})
    _post(url, "/v0/fake/pay", {"vid": q["vid"], "amount_piconero": tokens * PRICE, "mine": 2})
    raw, blinded = client_tokens(tokens)
    blinded_b64 = [_b64(b) for b in blinded]
    issued = _post(url, "/v0/redeem", {"vid": q["vid"], "blinded-tokens": blinded_b64})
    unblinded = unblind_batch(raw, blinded, issued["signed-tokens"], issued["proof"], issued["public-key"])
    recs = [wallet_record(u) for u in unblinded]
    return q, issued, recs, unblinded


def test_keys_seed_epoch_zero_is_open(issuer):
    state, _, key = issuer
    keys = http_json(state.listen + "/v0/keys")
    assert keys["current"] == 0
    ep = keys["epochs"][0]
    assert ep["epoch"] == 0
    assert ep["scheme"] == "ristretto-v0"
    assert ep["issuer-pubkey-id"] == issuer_info(key)["issuer-pubkey-id"]
    assert ep.get("issue_until") in (None, 0) or ep["issue_until"] > 0


def test_rotate_closes_issue_and_quotes_new_epoch(issuer):
    state, _, key = issuer
    url = state.listen
    q0 = _post(url, "/v0/quote", {"tokens": 1})
    assert q0["epoch"] == 0
    new = state.rotate()
    assert new["epoch"] == 1
    keys = http_json(url + "/v0/keys")
    assert keys["current"] == 1
    old = [e for e in keys["epochs"] if e["epoch"] == 0][0]
    assert old["issue_until"] is not None
    q1 = _post(url, "/v0/quote", {"tokens": 1})
    assert q1["epoch"] == 1


def test_redeem_410_after_issue_window_closes(issuer):
    state, _, _ = issuer
    url = state.listen
    q = _post(url, "/v0/quote", {"tokens": 2})
    _post(url, "/v0/fake/pay", {"vid": q["vid"], "amount_piconero": 2 * PRICE, "mine": 2})
    state.rotate()
    _, blinded = client_tokens(2)
    code, msg = _post_status(url, "/v0/redeem", {"vid": q["vid"], "blinded-tokens": [_b64(b) for b in blinded]})
    assert code == 410
    assert "epoch closed" in msg.lower() or "new quote" in msg.lower()


def test_exchange_before_burn_is_refused(issuer):
    state, _, _ = issuer
    url = state.listen
    _, _, recs, _ = _buy(url, 2)
    _, blinded = client_tokens(2)
    code, msg = _post_status(
        url,
        "/v0/exchange",
        {"epoch_old": 0, "tokens": recs, "blinded-tokens": [_b64(b) for b in blinded]},
    )
    assert code == 409 or code == 400
    assert "burn" in msg.lower() or "accept" in msg.lower() or "not burnt" in msg.lower()


def test_burn_exchange_settled_rejected_and_ledger(issuer):
    state, _, key0 = issuer
    url = state.listen
    q, issued, recs, unblinded = _buy(url, 3)
    assert issued.get("token-epoch", 0) == 0
    _post(url, "/v0/settlement", {"nodeid": "n1", "epoch": 0, "spent-preimages": [recs[0]["t"]]})

    burnt = state.burn(0)
    assert burnt["accept_until"] is not None
    keys = http_json(url + "/v0/keys")
    assert keys["current"] == 1
    old = [e for e in keys["epochs"] if e["epoch"] == 0][0]
    assert old["accept_until"] is not None

    raw_new, blinded_new = client_tokens(2)
    code, msg = _post_status(
        url,
        "/v0/exchange",
        {
            "epoch_old": 0,
            "tokens": [recs[0]],
            "blinded-tokens": [_b64(b) for b in blinded_new[:1]],
        },
    )
    assert code == 409
    assert "settled" in msg.lower() or "spent" in msg.lower()

    batch = _post(
        url,
        "/v0/exchange",
        {
            "epoch_old": 0,
            "tokens": recs[1:],
            "blinded-tokens": [_b64(b) for b in blinded_new],
        },
    )
    assert len(batch["signed-tokens"]) == 2
    assert batch["token-epoch"] == 1
    fresh = unblind_batch(
        raw_new, blinded_new, batch["signed-tokens"], batch["proof"], batch["public-key"]
    )
    assert len(fresh) == 2

    led = http_json(url + "/v0/ledger")
    assert led["epochs"]["0"]["tokens_issued"] == 3
    assert led["epochs"]["0"]["tokens_settled"] == 1
    assert led["epochs"]["0"]["tokens_exchanged"] == 2

    # replay of the same t is refused
    raw2, blinded2 = client_tokens(2)
    code, _ = _post_status(
        url,
        "/v0/exchange",
        {"epoch_old": 0, "tokens": recs[1:], "blinded-tokens": [_b64(b) for b in blinded2]},
    )
    assert code == 409


def test_gate_pull_keys_drops_burnt_keeps_rotated(issuer, tmp_path):
    state, _, key0 = issuer
    url = state.listen
    _, _, recs0, unblinded0 = _buy(url, 1)
    state.rotate()
    _, issued1, recs1, unblinded1 = _buy(url, 1)
    assert issued1["token-epoch"] == 1

    keys = http_json(url + "/v0/keys")
    gate = LeaseGate(key0, nodeid=NODEID, spent=SpentSet(str(tmp_path / "spent.json")))
    gate.pull_keys(keys, signing_keys=state.epoch_keys())

    def _spend(unblinded, epoch, pubkey_id):
        r = encode_r(
            nodeid=NODEID,
            storage_index=b"\x11" * 16,
            lease_seconds=100,
            share_bytes=64,
            token_epoch=epoch,
            issuer_pubkey_id=pubkey_id,
        )
        rec = wallet_record(unblinded)
        return gate.spend(rec["t"], r, mac_k_r(unblinded, r).decode("ascii"))

    pk0 = issuer_info(key0)["issuer-pubkey-id"]
    pk1 = [e for e in keys["epochs"] if e["epoch"] == 1][0]["issuer-pubkey-id"]
    # After a planned rotate, both epochs are still accepted.
    assert _spend(unblinded0[0], 0, pk0)["ok"] is True
    assert _spend(unblinded1[0], 1, pk1)["ok"] is True

    state.burn(0)
    keys = http_json(url + "/v0/keys")
    gate.pull_keys(keys, signing_keys=state.epoch_keys())
    # unblinded0 was already spent; buy a leftover unused epoch-0 token? we only bought 1.
    # Burn drops epoch 0: a fresh R for epoch 0 is refused before spent-set replay.
    from leasegrid_zkap.errors import SpendError

    with pytest.raises(SpendError) as exc:
        r = encode_r(
            nodeid=NODEID,
            storage_index=b"\x22" * 16,
            lease_seconds=100,
            share_bytes=64,
            token_epoch=0,
            issuer_pubkey_id=pk0,
        )
        rec = wallet_record(unblinded0[0])
        gate.spend(rec["t"], r, mac_k_r(unblinded0[0], r).decode("ascii"))
    assert "epoch" in str(exc.value).lower()
