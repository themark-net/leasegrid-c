"""Shaky write-layout checks. They fail if a CHK we mint cannot be read back,
or if a read-only cap is treated as writable. No grid required.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "app/src/main/python"
sys.path.insert(0, str(ROOT))

from lg_tahoe import _decode_chk_shares, _parse_chk_body  # noqa: E402
from lg_write import (  # noqa: E402
    directory_writable,
    encode_chk,
    keep_both_name,
)


def test_chk_round_trip_matches_the_reader():
    blob = b"hello from the phone\n" + (b"y" * 300_000)
    for needed, total in ((1, 1), (2, 3)):
        cap, shares = encode_chk(blob, needed, total)
        key, ueb, k, n, size = _parse_chk_body(cap[len("URI:CHK:") :])
        assert (k, n, size) == (needed, total, len(blob))
        plain = _decode_chk_shares(key, ueb, needed, total, size, list(enumerate(shares))[:needed])
        assert plain == blob


def test_read_only_put_fails_closed(tmp_path: Path):
    import json

    from leasegrid_read import dispatch

    blob = tmp_path / "a.bin"
    blob.write_bytes(b"abc")
    raw = dispatch(
        "put",
        json.dumps(
            {
                "path": str(blob),
                "cap": "URI:DIR2-RO:aaaaaaaaaaaaaaaaaaaaaaaa:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                "name": "a.bin",
                "servers": [],
                "shares": [1, 1, 1],
            }
        ),
    )
    body = json.loads(raw)
    assert body["ok"] is False
    assert "On friendnet" not in raw
    assert "computer" not in raw.lower()


def test_keep_both_and_read_only_cap():
    assert keep_both_name("beach.jpg", {"beach.jpg"}) == "beach (phone).jpg"
    assert keep_both_name("beach.jpg", {"beach.jpg", "beach (phone).jpg"}) == "beach (phone 2).jpg"
    assert directory_writable("URI:DIR2:abc:def")
    assert not directory_writable("URI:DIR2-RO:abc:def")
    assert not directory_writable("URI:DIR2-CHK:abc:def:1:1:4")
