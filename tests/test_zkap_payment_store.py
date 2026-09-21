"""S0: voucher state machine, price policy, idempotent redeem, settlement ledger.

No Monero, no HTTP. docs/07-payment.md §2–§5, §9.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from leasegrid_zkap.payment import (
    PICONERO,
    FakeChain,
    PricePolicy,
    Transfer,
    VoucherStore,
    advance,
)
from leasegrid_zkap.payment.store import DuplicateVid, StoreError, batch_hash

PRICE = 6 * 10**9  # 0.006 XMR per token
VID = "9f3a0b1c2d3e4f50"
T0 = 1_800_000_000.0


@pytest.fixture
def policy() -> PricePolicy:
    return PricePolicy(price_piconero=PRICE)


@pytest.fixture
def chain() -> FakeChain:
    return FakeChain()


@pytest.fixture
def store() -> VoucherStore:
    return VoucherStore()


def quote(store, policy, chain, tokens=20, vid=VID, now=T0):
    return store.create_quote(vid=vid, tokens=tokens, policy=policy, chain=chain, epoch=0, scheme="ristretto-v0", now=now)


def fake_sign(blinded: list[str]) -> dict:
    return {"signed-tokens": ["S" + b for b in blinded], "proof": "p", "public-key": "pk", "issuer-pubkey-id": "id"}


# -- policy ------------------------------------------------------------------


def test_policy_amounts_and_confirmations(policy: PricePolicy):
    assert policy.amount_due(20) == 20 * PRICE
    with pytest.raises(ValueError):
        policy.amount_due(0)
    with pytest.raises(ValueError):
        policy.amount_due(policy.max_tokens_per_quote + 1)
    assert policy.confirmations_required(PICONERO // 10) == 2
    assert policy.confirmations_required(PICONERO // 2) == 10
    assert policy.confirmations_required(3 * PICONERO) == 10


def test_policy_effective_price_grace_window(policy: PricePolicy):
    grace_until = T0 + 3600
    assert policy.effective_price(quoted_price=1, first_confirmed_at=T0 + 10, grace_until=grace_until) == 1
    assert policy.effective_price(quoted_price=1, first_confirmed_at=grace_until + 1, grace_until=grace_until) == PRICE


def test_tokens_owed_floors_and_never_negative():
    assert PricePolicy.tokens_owed(20 * PRICE, PRICE) == 20
    assert PricePolicy.tokens_owed(20 * PRICE + PRICE - 1, PRICE) == 20  # dust kept, said up front
    assert PricePolicy.tokens_owed(PRICE - 1, PRICE) == 0
    assert PricePolicy.tokens_owed(0, PRICE) == 0


def test_format_xmr():
    assert PricePolicy.format_xmr(PICONERO) == "1"
    assert PricePolicy.format_xmr(120 * 10**9) == "0.12"
    assert PricePolicy.format_xmr(0) == "0"
    assert PricePolicy.format_xmr(1) == "0.000000000001"


def test_policy_rejects_nonsense():
    with pytest.raises(ValueError):
        PricePolicy(price_piconero=0)
    with pytest.raises(ValueError):
        PricePolicy(price_piconero=1, confirmations_small=5, confirmations_large=2)


# -- quote ---------------------------------------------------------------------


def test_quote_allocates_fresh_subaddress_and_windows(store, policy, chain):
    v = quote(store, policy, chain)
    assert v.state == "quoted"
    assert v.amount_due == 20 * PRICE
    assert v.subaddr_index == 1 and v.address.startswith("FAKE00000001")
    assert v.quote_expires == T0 + policy.quote_ttl
    assert v.grace_until == v.quote_expires + policy.grace
    assert v.confirmations_required == 2
    v2 = quote(store, policy, chain, vid="0000000000000001")
    assert v2.subaddr_index == 2  # never reused


def test_quote_rejects_duplicate_and_bad_vid(store, policy, chain):
    quote(store, policy, chain)
    with pytest.raises(DuplicateVid):
        quote(store, policy, chain)
    with pytest.raises(StoreError):
        quote(store, policy, chain, vid="xyz")
    with pytest.raises(StoreError):
        quote(store, policy, chain, vid="00" * 9)


def test_quote_is_case_insensitive_on_vid(store, policy, chain):
    quote(store, policy, chain, vid=VID.upper())
    assert store.get(VID) is not None
    assert store.get(VID.upper()).vid == VID


# -- state machine (pure) -------------------------------------------------------


def test_quoted_to_seen_to_confirming_to_payable(store, policy, chain):
    v = quote(store, policy, chain)
    v = advance(v, [Transfer(20 * PRICE, 0)], policy, T0 + 60)
    assert (v.state, v.amount_seen, v.amount_confirmed, v.tokens_owed) == ("seen", 20 * PRICE, 0, 0)
    v = advance(v, [Transfer(20 * PRICE, 1)], policy, T0 + 180)
    assert (v.state, v.confirmations, v.confirmations_required) == ("confirming", 1, 2)
    v = advance(v, [Transfer(20 * PRICE, 2)], policy, T0 + 300)
    assert v.state == "payable"
    assert v.tokens_owed == 20
    assert v.effective_price == PRICE
    assert v.first_confirmed_at == T0 + 300


def test_large_amount_needs_ten_confirmations(store, policy, chain):
    v = quote(store, policy, chain, tokens=100)  # 0.6 XMR ≥ 0.5 threshold
    assert v.confirmations_required == 10
    v = advance(v, [Transfer(100 * PRICE, 2)], policy, T0 + 60)
    assert v.state == "confirming"
    v = advance(v, [Transfer(100 * PRICE, 10)], policy, T0 + 1200)
    assert v.state == "payable" and v.tokens_owed == 100


def test_overpay_floors_to_whole_tokens(store, policy, chain):
    v = quote(store, policy, chain)
    v = advance(v, [Transfer(20 * PRICE + PRICE // 2, 2)], policy, T0 + 60)
    assert v.state == "payable" and v.tokens_owed == 20


def test_underpaid_then_topped_up_on_same_address(store, policy, chain):
    v = quote(store, policy, chain)
    v = advance(v, [Transfer(PRICE // 2, 2)], policy, T0 + 60)
    assert v.state == "underpaid" and v.tokens_owed == 0
    v = advance(v, [Transfer(PRICE // 2, 5), Transfer(PRICE // 2, 2)], policy, T0 + 600)
    assert v.state == "payable" and v.tokens_owed == 1


def test_partial_confirmation_counts_only_deep_transfers(store, policy, chain):
    v = quote(store, policy, chain)
    v = advance(v, [Transfer(10 * PRICE, 3), Transfer(10 * PRICE, 0)], policy, T0 + 60)
    assert v.state == "payable"
    assert v.amount_seen == 20 * PRICE and v.amount_confirmed == 10 * PRICE
    assert v.tokens_owed == 10 and v.confirmations == 0
    v = advance(v, [Transfer(10 * PRICE, 5), Transfer(10 * PRICE, 2)], policy, T0 + 300)
    assert v.tokens_owed == 20


def test_expired_unpaid_is_cosmetic_and_still_credits(store, policy, chain):
    v = quote(store, policy, chain)
    v = advance(v, [], policy, T0 + policy.quote_ttl + 1)
    assert v.state == "expired_unpaid"
    late = T0 + policy.quote_ttl + 600  # inside grace
    v = advance(v, [Transfer(20 * PRICE, 2)], policy, late)
    assert v.state == "payable" and v.effective_price == PRICE and v.tokens_owed == 20


def test_late_payment_after_grace_uses_current_price(store, policy, chain):
    v = quote(store, policy, chain)
    today = PricePolicy(price_piconero=2 * PRICE)  # price doubled since the quote
    after_grace = v.grace_until + 1
    v = advance(v, [Transfer(20 * PRICE, 2)], today, after_grace)
    assert v.state == "payable"
    assert v.effective_price == 2 * PRICE
    assert v.tokens_owed == 10


def test_effective_price_is_locked_at_first_confirmation(store, policy, chain):
    v = quote(store, policy, chain)
    v = advance(v, [Transfer(10 * PRICE, 2)], policy, T0 + 60)
    later_policy = PricePolicy(price_piconero=3 * PRICE)
    v = advance(v, [Transfer(10 * PRICE, 9), Transfer(10 * PRICE, 2)], later_policy, T0 + 4000)
    assert v.effective_price == PRICE and v.tokens_owed == 20


def test_reorg_that_removes_unconfirmed_tx_resets_to_quoted(store, policy, chain):
    v = quote(store, policy, chain)
    v = advance(v, [Transfer(20 * PRICE, 0)], policy, T0 + 60)
    assert v.state == "seen"
    v = advance(v, [], policy, T0 + 120)
    assert v.state == "quoted" and v.amount_seen == 0


def test_issued_never_regresses(store, policy, chain):
    v = quote(store, policy, chain)
    store.observe(v.vid, [Transfer(20 * PRICE, 2)], policy, T0 + 60)
    code, body = store.redeem(v.vid, ["b%d" % i for i in range(20)], fake_sign, now=T0 + 90)
    assert code == 200
    v = store.observe(v.vid, [Transfer(20 * PRICE, 2), Transfer(5 * PRICE, 3)], policy, T0 + 900)
    assert v.state == "issued" and v.tokens_issued == 20
    assert v.amount_confirmed == 25 * PRICE  # recorded, not re-issued
    v = store.observe(v.vid, [], policy, T0 + 1000)
    assert v.state == "issued"


# -- store + chain ------------------------------------------------------------------


def test_poll_drives_vouchers_from_fake_chain(store, policy, chain):
    v = quote(store, policy, chain)
    other = quote(store, policy, chain, vid="0000000000000002", tokens=5)
    assert store.poll(chain, policy, now=T0 + 10) == 0
    chain.pay(v.address, 20 * PRICE)
    assert store.poll(chain, policy, now=T0 + 20) == 1
    assert store.get(v.vid).state == "seen"
    assert store.get(other.vid).state == "quoted"
    chain.mine(2)
    store.poll(chain, policy, now=T0 + 400)
    assert store.get(v.vid).state == "payable"
    assert store.get(v.vid).tokens_owed == 20
    assert [x.vid for x in store.open_vouchers()] == [v.vid, other.vid]


def test_fake_chain_rejects_unknown_address_and_zero(chain: FakeChain):
    with pytest.raises(KeyError):
        chain.pay("nope", 1)
    addr, idx = chain.new_address(b"\x00" * 8)
    with pytest.raises(ValueError):
        chain.pay(addr, 0)
    assert chain.index_of(addr) == idx
    assert chain.received(idx) == []
    h = chain.height()
    assert chain.mine(3) == h + 3


# -- redeem -----------------------------------------------------------------------


def test_redeem_codes_and_idempotency(store, policy, chain):
    v = quote(store, policy, chain)
    blinded = ["b%d" % i for i in range(20)]
    assert store.redeem("0000000000000099", blinded, fake_sign)[0] == 404
    code, body = store.redeem(v.vid, blinded, fake_sign)
    assert code == 402 and body["state"] == "quoted"
    store.observe(v.vid, [Transfer(20 * PRICE, 1)], policy, T0 + 60)
    code, body = store.redeem(v.vid, blinded, fake_sign)
    assert code == 402 and body["state"] == "confirming" and body["confirmations"] == 1
    store.observe(v.vid, [Transfer(20 * PRICE, 2)], policy, T0 + 120)
    code, body = store.redeem(v.vid, blinded[:5], fake_sign)
    assert code == 400 and body["tokens_owed"] == 20
    code, body = store.redeem(v.vid, blinded, fake_sign, issuing_open=False)
    assert code == 410
    calls = []

    def counting_sign(b):
        calls.append(list(b))
        return fake_sign(b)

    code, first = store.redeem(v.vid, blinded, counting_sign, now=T0 + 130)
    assert code == 200 and first["cached"] is False
    assert first["signed-tokens"] == ["S" + b for b in blinded]
    code, again = store.redeem(v.vid, blinded, counting_sign, now=T0 + 140)
    assert code == 200 and again["cached"] is True
    assert again["signed-tokens"] == first["signed-tokens"]
    assert len(calls) == 1  # signed exactly once
    code, body = store.redeem(v.vid, ["other%d" % i for i in range(20)], counting_sign)
    assert code == 409 and body["state"] == "issued"
    assert len(calls) == 1
    got = store.get(v.vid)
    assert got.state == "issued" and got.tokens_issued == 20 and got.batch_hash == batch_hash(blinded)


def test_redeem_public_view_hides_batch(store, policy, chain):
    v = quote(store, policy, chain)
    store.observe(v.vid, [Transfer(20 * PRICE, 2)], policy, T0 + 60)
    store.redeem(v.vid, ["b"] * 20, fake_sign)
    pub = store.get(v.vid).public()
    assert "signed_batch" not in pub and "batch_hash" not in pub and "subaddr_index" not in pub
    assert pub["state"] == "issued" and pub["tokens_issued"] == 20


# -- settlement + ledger ---------------------------------------------------------


def test_settlement_dedups_and_flags_conflicts(store):
    r = store.settle("node-a", 0, ["t1", "t2", "t3"])
    assert r == {"accepted": 3, "duplicates": 0, "conflicts": 0}
    r = store.settle("node-a", 0, ["t2", "t4"])
    assert r == {"accepted": 1, "duplicates": 1, "conflicts": 0}
    r = store.settle("node-b", 0, ["t1", "t5"])  # t1 already owned by node-a
    assert r == {"accepted": 1, "duplicates": 0, "conflicts": 1}
    assert store.node_ledger("node-a") == {"0": 4}
    assert store.node_ledger("node-b") == {"0": 1}


def test_ledger_totals(store, policy, chain):
    v = quote(store, policy, chain)
    store.observe(v.vid, [Transfer(20 * PRICE, 2)], policy, T0 + 60)
    store.redeem(v.vid, ["b"] * 20, fake_sign)
    quote(store, policy, chain, vid="0000000000000002", tokens=5)
    store.settle("node-a", 0, ["t1", "t2"])
    store.settle("node-b", 0, ["t1"])
    led = store.ledger()
    e = led["epochs"]["0"]
    assert e["quotes"] == 2
    assert e["xmr_received_piconero"] == 20 * PRICE
    assert e["tokens_quoted"] == 25
    assert e["tokens_issued"] == 20
    assert e["tokens_settled"] == 2
    assert led["settlement_conflicts"] == 1


def test_store_persists_across_reopen(tmp_path: Path, policy, chain):
    path = tmp_path / "issuer" / "vouchers.sqlite"
    s1 = VoucherStore(path)
    v = quote(s1, policy, chain)
    s1.observe(v.vid, [Transfer(20 * PRICE, 2)], policy, T0 + 60)
    code, body = s1.redeem(v.vid, ["b"] * 20, fake_sign)
    assert code == 200
    s1.close()
    s2 = VoucherStore(path)
    got = s2.get(v.vid)
    assert got is not None and got.state == "issued"
    code, again = s2.redeem(v.vid, ["b"] * 20, fake_sign)
    assert code == 200 and again["cached"] is True and again["signed-tokens"] == body["signed-tokens"]
    s2.close()
