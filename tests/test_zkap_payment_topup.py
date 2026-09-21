"""S2: buyer side — seed-derived vids/tokens, write-ahead pending records,
crash resume, and recovery from the seed alone (07-payment.md §5.2, §5.3, §6)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from leasegrid_sync.credit import is_leasegrid_wallet
from leasegrid_zkap.client import ClientError, http_json, load_wallet
from leasegrid_zkap.crypto import generate_signing_key
from leasegrid_zkap.gate import LeaseGate
from leasegrid_zkap.issuer import start_issuer
from leasegrid_zkap.payment import FakeChain, PricePolicy, VoucherStore
from leasegrid_zkap.payment.topup import (
    TopUpClient,
    TopUpError,
    TopUpState,
    derive_tokens,
    derive_vid,
    hkdf_expand,
)
from leasegrid_zkap.spender import WalletSpender
from leasegrid_zkap.spentset import SpentSet
from leasegrid_zkap.storage_http import start_storage_http

PRICE = 6 * 10**9
NODEID = "node1aaaaaaaaaaaaaaaaaaaaaaaaaaaa"
SI = bytes(range(16))


@pytest.fixture
def issuer():
    key = generate_signing_key()
    chain = FakeChain()
    state, httpd = start_issuer(
        key, "127.0.0.1:0", chain=chain, policy=PricePolicy(price_piconero=PRICE), store=VoucherStore(), faucet=False
    )
    yield state, chain, key
    httpd.shutdown()


@pytest.fixture
def home(tmp_path: Path) -> Path:
    h = tmp_path / "home"
    h.mkdir()
    return h


def client(issuer, home: Path, **kw) -> TopUpClient:
    return TopUpClient(issuer[0].listen, home / "credit-wallet.json", **kw)


def pay_and_confirm(url: str, vid: str, amount: int, blocks: int = 2) -> None:
    http_json(url + "/v0/fake/pay", "POST", {"vid": vid, "amount_piconero": amount, "mine": blocks})


# -- derivation ---------------------------------------------------------------------


def test_hkdf_expand_is_rfc5869_shaped():
    prk = bytes(range(32))
    a = hkdf_expand(prk, b"x", 10)
    b = hkdf_expand(prk, b"x", 70)
    assert b[:10] == a and len(b) == 70
    assert hkdf_expand(prk, b"y", 10) != a


def test_vid_and_tokens_are_deterministic_and_distinct():
    seed = b"\x07" * 32
    assert derive_vid(seed, 0) == derive_vid(seed, 0)
    assert len(derive_vid(seed, 0)) == 16
    assert derive_vid(seed, 0) != derive_vid(seed, 1)
    assert derive_vid(b"\x08" * 32, 0) != derive_vid(seed, 0)
    vid = derive_vid(seed, 3)
    a = [t.blind().encode_base64() for t in derive_tokens(seed, vid, 5)]
    b = [t.blind().encode_base64() for t in derive_tokens(seed, vid, 5)]
    assert a == b
    assert len(set(a)) == 5
    # a prefix of a longer batch is the same tokens (batch size can grow before redeem)
    c = [t.blind().encode_base64() for t in derive_tokens(seed, vid, 8)]
    assert c[:5] == a
    other = [t.blind().encode_base64() for t in derive_tokens(seed, derive_vid(seed, 4), 5)]
    assert not set(a) & set(other)
    with pytest.raises(ValueError):
        derive_vid(seed, -1)


# -- state file -----------------------------------------------------------------------


def test_state_file_created_with_seed_and_0600(home: Path):
    st = TopUpState(home / "credit-topup.json")
    assert len(st.seed) == 32 and st.counter == 0 and st.pending == {}
    data = json.loads((home / "credit-topup.json").read_text())
    assert data["credit-seed"] == st.seed.hex()
    import os

    if os.name != "nt":
        assert (home / "credit-topup.json").stat().st_mode & 0o777 == 0o600
    again = TopUpState(home / "credit-topup.json")
    assert again.seed == st.seed
    with pytest.raises(TopUpError):
        TopUpState.from_seed(home / "credit-topup.json", b"\x01" * 32)
    (home / "bad.json").write_text("{}")
    with pytest.raises(TopUpError):
        TopUpState(home / "bad.json")


# -- lifecycle ------------------------------------------------------------------------


def test_quote_persists_before_asking_then_pay_then_redeem(issuer, home: Path):
    state, chain, _ = issuer
    tc = client(issuer, home)
    q = tc.quote(20)
    assert q["vid"] == derive_vid(tc.state.seed, 0)
    assert q["amount_piconero"] == 20 * PRICE
    st = json.loads((home / "credit-topup.json").read_text())
    assert st["quote-counter"] == 1
    assert st["pending"][q["vid"]]["address"] == q["address"]
    assert st["pending"][q["vid"]]["state"] == "quoted"

    r = tc.redeem(q["vid"])
    assert r["state"] == "quoted" and r["tokens_added"] == 0
    assert not (home / "credit-wallet.json").exists()

    pay_and_confirm(state.listen, q["vid"], 20 * PRICE)
    r = tc.redeem(q["vid"])
    assert r["state"] == "issued" and r["tokens_added"] == 20 and r["cached"] is False
    wallet = load_wallet(home / "credit-wallet.json")
    assert is_leasegrid_wallet(wallet)
    assert len(wallet["tokens"]) == 20
    assert wallet["issuer-pubkey-id"] == state.info["issuer-pubkey-id"]
    assert not any(t.get("unverified") for t in wallet["tokens"])
    assert tc.state.pending == {}
    assert tc.state.history[-1]["tokens"] == 20

    # redeeming again is a no-op on the wallet (cached batch, same t values)
    r = tc.redeem(q["vid"])
    assert r["tokens_added"] == 0 and r["cached"] is True
    assert len(load_wallet(home / "credit-wallet.json")["tokens"]) == 20
    assert state.issue_count == 1


def test_second_quote_uses_next_counter_and_topups_accumulate(issuer, home: Path):
    state, _, _ = issuer
    tc = client(issuer, home)
    q1 = tc.quote(2)
    q2 = tc.quote(3)
    assert q2["vid"] == derive_vid(tc.state.seed, 1) and q1["vid"] != q2["vid"]
    pay_and_confirm(state.listen, q1["vid"], 2 * PRICE)
    pay_and_confirm(state.listen, q2["vid"], 3 * PRICE)
    res = tc.resume()
    assert sorted(r["tokens_added"] for r in res) == [2, 3]
    assert len(load_wallet(home / "credit-wallet.json")["tokens"]) == 5
    assert tc.state.pending == {}


def test_crash_between_pay_and_collect_resumes_from_state_file(issuer, home: Path):
    state, _, _ = issuer
    tc = client(issuer, home)
    q = tc.quote(4)
    pay_and_confirm(state.listen, q["vid"], 4 * PRICE)
    del tc  # "crash"
    tc2 = client(issuer, home)
    assert q["vid"] in tc2.state.pending
    res = tc2.resume()
    assert len(res) == 1 and res[0]["tokens_added"] == 4
    assert len(load_wallet(home / "credit-wallet.json")["tokens"]) == 4


def test_lost_redeem_reply_is_recovered_from_cached_batch(issuer, home: Path):
    state, _, _ = issuer
    calls = {"redeem": 0}

    def flaky(url, method="GET", body=None, timeout=15.0):
        out = http_json(url, method, body, timeout)
        if url.endswith("/v0/redeem"):
            calls["redeem"] += 1
            if calls["redeem"] == 1:
                raise ClientError("POST %s failed: ConnectionResetError: reply lost" % url)
        return out

    tc = client(issuer, home, http=flaky)
    q = tc.quote(6)
    pay_and_confirm(state.listen, q["vid"], 6 * PRICE)
    with pytest.raises(ClientError):
        tc.redeem(q["vid"])  # issuer signed and cached; we never saw it
    assert state.issue_count == 1
    assert q["vid"] in tc.state.pending
    r = tc.redeem(q["vid"])
    assert r["tokens_added"] == 6 and r["cached"] is True
    assert state.issue_count == 1  # never signed twice


def test_batch_size_race_retries_with_issuer_count(issuer, home: Path):
    state, chain, _ = issuer
    tc = client(issuer, home)
    q = tc.quote(10)
    pay_and_confirm(state.listen, q["vid"], 10 * PRICE)
    seen = {"get": 0}
    real = tc._http

    def racy(url, method="GET", body=None, timeout=15.0):
        out = real(url, method, body, timeout)
        if method == "GET" and "/v0/voucher/" in url:
            seen["get"] += 1
            if seen["get"] == 1:
                # more confirmations land right after our GET
                chain.pay(q["address"], 10 * PRICE)
                chain.mine(2)
        return out

    tc._http = racy
    r = tc.redeem(q["vid"])
    assert r["tokens_added"] == 20 and r["tokens"] == 20


def test_quote_409_adopts_existing_voucher(issuer, home: Path):
    state, chain, _ = issuer
    tc = client(issuer, home)
    vid0 = derive_vid(tc.state.seed, 0)
    # A previous run's quote reached the issuer but the reply was lost before we persisted.
    state.store.create_quote(vid=vid0, tokens=7, policy=state.policy, chain=chain, epoch=0, scheme="ristretto-v0")
    q = tc.quote(7)
    assert q["vid"] == vid0 and q["tokens_quoted"] == 7
    assert tc.state.pending[vid0]["address"] == state.store.get(vid0).address


def test_issuer_mismatch_refuses_merge(issuer, home: Path, tmp_path: Path):
    state, _, _ = issuer
    tc = client(issuer, home)
    from leasegrid_zkap.client import save_wallet

    save_wallet(home / "credit-wallet.json", {"issuer-pubkey-id": "deadbeef", "tokens": []})
    q = tc.quote(1)
    pay_and_confirm(state.listen, q["vid"], PRICE)
    with pytest.raises(TopUpError):
        tc.redeem(q["vid"])


# -- recovery ---------------------------------------------------------------------------


def test_recover_from_seed_alone_rebuilds_wallet_marked_unverified(issuer, home: Path, tmp_path: Path):
    state, _, _ = issuer
    tc = client(issuer, home)
    seed = tc.state.seed
    q1 = tc.quote(3)
    q2 = tc.quote(2)
    q3 = tc.quote(5)  # never paid
    pay_and_confirm(state.listen, q1["vid"], 3 * PRICE)
    pay_and_confirm(state.listen, q2["vid"], 2 * PRICE)
    tc.resume()
    original = load_wallet(home / "credit-wallet.json")
    assert len(original["tokens"]) == 5

    # the laptop dies: nothing left but the seed from the recovery key
    new_home = tmp_path / "new-home"
    new_home.mkdir()
    TopUpState.from_seed(new_home / "credit-topup.json", seed)
    tc2 = TopUpClient(state.listen, new_home / "credit-wallet.json")
    out = tc2.recover(gap=5)
    assert out["vouchers_found"] == 3
    assert out["tokens_added"] == 5
    assert out["next_counter"] == 3  # continues past every vid the issuer knows
    recovered = load_wallet(new_home / "credit-wallet.json")
    assert sorted(t["t"] for t in recovered["tokens"]) == sorted(t["t"] for t in original["tokens"])
    assert all(t["unverified"] is True for t in recovered["tokens"])
    assert q3["vid"] in tc2.state.pending  # still waiting for payment on the new device
    assert state.issue_count == 2  # cached batches; nothing signed again
    # a fresh quote on the recovered device does not collide with the old ones
    q4 = tc2.quote(1)
    assert q4["vid"] == derive_vid(seed, 3)


def test_recover_stops_after_gap_of_unknown_vids(issuer, home: Path):
    tc = client(issuer, home)
    calls = []
    real = tc._http

    def counting(url, method="GET", body=None, timeout=15.0):
        calls.append(url)
        return real(url, method, body, timeout)

    tc._http = counting
    out = tc.recover(gap=3)
    assert out == {"vouchers_found": 0, "tokens_added": 0, "next_counter": 0, "results": []}
    assert len([c for c in calls if "/v0/voucher/" in c]) == 3


def test_spender_drops_unverified_token_already_spent_elsewhere(tmp_path: Path):
    """Recovered credit converges: a spent token is parked silently and the next one pays."""
    key = generate_signing_key()
    from leasegrid_zkap.crypto import issuer_info

    gate = LeaseGate(key, nodeid=NODEID, spent=SpentSet(str(tmp_path / "spent.json")))
    url, httpd = start_storage_http(gate, "tcp:0:interface=127.0.0.1")
    try:
        chain = FakeChain()
        istate, ihttpd = start_issuer(
            key, "127.0.0.1:0", chain=chain, policy=PricePolicy(price_piconero=PRICE), faucet=False
        )
        try:
            home = tmp_path / "home"
            home.mkdir()
            tc = TopUpClient(istate.listen, home / "credit-wallet.json")
            q = tc.quote(3)
            pay_and_confirm(istate.listen, q["vid"], 3 * PRICE)
            tc.redeem(q["vid"])
            # the old device spends token #1 on SI at this node
            old = WalletSpender(home / "credit-wallet.json", recent_path=home / "recent.json")
            spent_t = old.ensure_grant_sync(url, NODEID, issuer_info(key)["issuer-pubkey-id"], SI, 64)["t"]
            assert len(load_wallet(home / "credit-wallet.json")["tokens"]) == 2

            # new device recovers all three from the seed (does not know #1 is gone)
            new_home = tmp_path / "new"
            new_home.mkdir()
            TopUpState.from_seed(new_home / "credit-topup.json", tc.state.seed)
            tc2 = TopUpClient(istate.listen, new_home / "credit-wallet.json")
            assert tc2.recover(gap=2)["tokens_added"] == 3
            sp = WalletSpender(new_home / "credit-wallet.json", recent_path=new_home / "recent.json")
            other_si = bytes(range(16, 32))
            grant = sp.ensure_grant_sync(url, NODEID, issuer_info(key)["issuer-pubkey-id"], other_si, 64)
            assert grant["t"] and grant["t"] != spent_t
            w = load_wallet(new_home / "credit-wallet.json")
            assert len(w["tokens"]) == 1  # 3 recovered − 1 spent-elsewhere parked − 1 spent now
            assert len(w["rejected"]) == 1
            recent = json.loads((new_home / "recent.json").read_text())["events"]
            assert any("already spent elsewhere" in e["title"] for e in recent)
        finally:
            ihttpd.shutdown()
    finally:
        httpd.shutdown()


def test_cli_topup_json(issuer, home, capsys):
    from leasegrid_zkap.cli import main

    state = issuer[0]
    code = main(
        [
            "topup",
            "--issuer",
            state.listen,
            "--wallet",
            str(home / "credit-wallet.json"),
            "--tokens",
            "3",
            "--json",
        ]
    )
    assert code == 0
    q = json.loads(capsys.readouterr().out)
    assert q["tokens_quoted"] == 3
    assert q["amount_piconero"] == 3 * PRICE
    assert len(q["vid"]) == 16
    assert q["address"] and q["pay_uri"].startswith("monero:")
