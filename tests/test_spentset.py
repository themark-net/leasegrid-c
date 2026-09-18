"""Spent-set replay rules (docs/02-objects.md §2.7)."""

from leasegrid_zkap.spentset import ReplayError, SpentRecord, SpentSet


def _rec(t: str, r_b64: str) -> SpentRecord:
    return SpentRecord(
        t=t,
        r_b64=r_b64,
        storage_index_hex="00" * 16,
        lease_seconds=60,
        share_bytes=64,
        token_epoch=0,
        issuer_pubkey_id="pk",
        nodeid="n",
    )


def test_first_spend_ok():
    s = SpentSet()
    s.remember(_rec("t1", "RAAA"))
    assert len(s) == 1


def test_idempotent_same_r():
    s = SpentSet()
    s.remember(_rec("t1", "RAAA"))
    again = s.remember(_rec("t1", "RAAA"))
    assert again.r_b64 == "RAAA"
    assert len(s) == 1


def test_replay_different_r_fails():
    s = SpentSet()
    s.remember(_rec("t1", "RAAA"))
    try:
        s.remember(_rec("t1", "RBBB"))
        raise AssertionError("expected ReplayError")
    except ReplayError:
        pass
