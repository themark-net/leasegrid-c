"""lg_fec matches zfec for the share counts Leasegrid grids actually use."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

zfec = pytest.importorskip("zfec")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "android/app/src/main/python"))

from lg_fec import decode_blocks, encode_blocks  # noqa: E402


def test_systematic_matches_zfec():
    cases = [(1, 1), (1, 3), (2, 3), (2, 5), (3, 10), (7, 10)]
    payload = b"Leasegrid phone read path shares must match zfec."
    for k, n in cases:
        size = 16
        blocks = []
        for i in range(k):
            chunk = (payload + bytes([i])) * 4
            blocks.append(chunk[:size])
        ref = zfec.Encoder(k, n).encode(blocks)
        ours = encode_blocks(k, n, blocks)
        assert ours == ref, (k, n)
        picks = [list(range(k))]
        if k > 1:
            picks.append(list(range(n - k, n)))
        for ids in picks:
            ids = ids[:k]
            if len(set(ids)) < k:
                continue
            got = decode_blocks(k, n, [(i, ours[i]) for i in ids])
            assert got == blocks, (k, n, ids)
