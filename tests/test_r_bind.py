"""Request binding R encode/decode (docs/02-objects.md)."""

from leasegrid_zkap.constants import DOMAIN
from leasegrid_zkap.r_bind import RError, decode_r, encode_r


def test_encode_decode_roundtrip():
    si = b"\xab" * 16
    r = encode_r(
        nodeid="lab-node",
        storage_index=si,
        lease_seconds=2592000,
        share_bytes=1073741824,
        issuer_pubkey_id="abc123",
    )
    d = decode_r(r)
    assert d["domain"] == DOMAIN
    assert d["nodeid"] == "lab-node"
    assert d["storage_index"] == si
    assert d["lease_seconds"] == 2592000
    assert d["share_bytes"] == 1073741824
    assert d["issuer_pubkey_id"] == "abc123"


def test_domain_is_leasegrid_v0():
    r = encode_r(
        nodeid="n",
        storage_index=b"\x00" * 16,
        lease_seconds=1,
        share_bytes=1,
        issuer_pubkey_id="pk",
    )
    assert decode_r(r)["domain"] == "leasegrid-v0"


def test_truncated_r_raises():
    try:
        decode_r(b"\x00\x01")
        raise AssertionError("expected RError")
    except RError:
        pass
