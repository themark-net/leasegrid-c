"""Keccak-256 (pre-NIST). hashlib.sha3_256 is not this; Monero checksums need keccak."""

from __future__ import annotations

_MASK = (1 << 64) - 1
_RC = (
    0x0000000000000001,
    0x0000000000008082,
    0x800000000000808A,
    0x8000000080008000,
    0x000000000000808B,
    0x0000000080000001,
    0x8000000080008081,
    0x8000000000008009,
    0x000000000000008A,
    0x0000000000000088,
    0x0000000080008009,
    0x000000008000000A,
    0x000000008000808B,
    0x800000000000008B,
    0x8000000000008089,
    0x8000000000008003,
    0x8000000000008002,
    0x8000000000000080,
    0x000000000000800A,
    0x800000008000000A,
    0x8000000080008081,
    0x8000000000008080,
    0x0000000080000001,
    0x8000000080008008,
)
# r[x + 5*y] rotation offsets (FIPS 202 / Keccak).
_ROT = (
    0,
    1,
    62,
    28,
    27,
    36,
    44,
    6,
    55,
    20,
    3,
    10,
    43,
    25,
    39,
    41,
    45,
    15,
    21,
    8,
    18,
    2,
    61,
    56,
    14,
)


def _rotl64(x: int, n: int) -> int:
    n %= 64
    return ((x << n) | (x >> (64 - n))) & _MASK


def _keccak_f(st: list[int]) -> None:
    for rnd in range(24):
        c = [st[x] ^ st[x + 5] ^ st[x + 10] ^ st[x + 15] ^ st[x + 20] for x in range(5)]
        d = [c[(x - 1) % 5] ^ _rotl64(c[(x + 1) % 5], 1) for x in range(5)]
        for i in range(25):
            st[i] ^= d[i % 5]
        t = [0] * 25
        for x in range(5):
            for y in range(5):
                t[y + 5 * ((2 * x + 3 * y) % 5)] = _rotl64(st[x + 5 * y], _ROT[x + 5 * y])
        for y in range(5):
            for x in range(5):
                a = t[x + 5 * y]
                b = (~t[((x + 1) % 5) + 5 * y]) & _MASK
                c2 = t[((x + 2) % 5) + 5 * y]
                st[x + 5 * y] = (a ^ (b & c2)) & _MASK
        st[0] ^= _RC[rnd]


def keccak256(data: bytes) -> bytes:
    rate = 136
    st = [0] * 25
    i = 0
    n = len(data)
    while i + rate <= n:
        _absorb(st, data[i : i + rate])
        _keccak_f(st)
        i += rate
    padded = bytearray(rate)
    leftover = data[i:]
    padded[: len(leftover)] = leftover
    padded[len(leftover)] ^= 0x01
    padded[rate - 1] ^= 0x80
    _absorb(st, padded)
    _keccak_f(st)
    out = bytearray()
    for lane in st:
        out.extend(lane.to_bytes(8, "little"))
    return bytes(out[:32])


def _absorb(st: list[int], block: bytes) -> None:
    for j in range(0, len(block), 8):
        st[j // 8] ^= int.from_bytes(block[j : j + 8], "little")
