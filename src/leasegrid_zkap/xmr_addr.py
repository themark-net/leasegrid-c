"""Monero integrated addresses: 8-byte payment ID is the voucher id (`vid`)."""

from __future__ import annotations

from .keccak import keccak256

ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
ENCODED_BLOCK_SIZES = (0, 2, 3, 5, 6, 7, 9, 10, 11)
FULL_BLOCK = 8
FULL_ENCODED = 11

# Cryptonote network bytes. Lab code never encodes mainnet.
NETBYTES = {
    "stagenet": {"standard": 24, "integrated": 25, "subaddress": 36},
    "testnet": {"standard": 53, "integrated": 54, "subaddress": 63},
}
NETBYTE_TO_NET = {
    24: ("stagenet", "standard"),
    25: ("stagenet", "integrated"),
    36: ("stagenet", "subaddress"),
    53: ("testnet", "standard"),
    54: ("testnet", "integrated"),
    63: ("testnet", "subaddress"),
    18: ("mainnet", "standard"),
    19: ("mainnet", "integrated"),
    42: ("mainnet", "subaddress"),
}

VID_LEN = 8
PUB_LEN = 32


class AddressError(ValueError):
    pass


def _encode_block(block: bytes) -> str:
    size = len(block)
    if size < 1 or size > FULL_BLOCK:
        raise AddressError("bad block size %d" % size)
    enc_size = ENCODED_BLOCK_SIZES[size]
    num = int.from_bytes(block, "big")
    out = ["1"] * enc_size
    i = enc_size - 1
    while num > 0 and i >= 0:
        num, rem = divmod(num, 58)
        out[i] = ALPHABET[rem]
        i -= 1
    return "".join(out)


def _decode_block(enc: str) -> bytes:
    size = len(enc)
    dec_size = None
    for i, es in enumerate(ENCODED_BLOCK_SIZES):
        if es == size:
            dec_size = i
            break
    if dec_size is None:
        raise AddressError("invalid encoded block length %d" % size)
    num = 0
    for ch in enc:
        digit = ALPHABET.find(ch)
        if digit < 0:
            raise AddressError("invalid base58 character")
        num = num * 58 + digit
    if dec_size < FULL_BLOCK and num >= (1 << (8 * dec_size)):
        raise AddressError("base58 block overflow")
    return num.to_bytes(dec_size, "big")


def xmr_base58_encode(raw: bytes) -> str:
    full, rem = divmod(len(raw), FULL_BLOCK)
    parts = [_encode_block(raw[i * FULL_BLOCK : (i + 1) * FULL_BLOCK]) for i in range(full)]
    if rem:
        parts.append(_encode_block(raw[full * FULL_BLOCK :]))
    return "".join(parts)


def xmr_base58_decode(enc: str) -> bytes:
    full, rem = divmod(len(enc), FULL_ENCODED)
    dec_rem = None
    if rem:
        for i, es in enumerate(ENCODED_BLOCK_SIZES):
            if es == rem:
                dec_rem = i
                break
        if dec_rem is None:
            raise AddressError("invalid address length")
    parts = [
        _decode_block(enc[i * FULL_ENCODED : (i + 1) * FULL_ENCODED]) for i in range(full)
    ]
    if rem:
        parts.append(_decode_block(enc[full * FULL_ENCODED :]))
    return b"".join(parts)


def encode_integrated(
    spend_pub: bytes,
    view_pub: bytes,
    payment_id: bytes,
    *,
    network: str = "stagenet",
) -> str:
    if network == "mainnet":
        raise AddressError("refusing to encode a mainnet address")
    if network not in NETBYTES:
        raise AddressError("unknown network %r" % network)
    if len(spend_pub) != PUB_LEN or len(view_pub) != PUB_LEN:
        raise AddressError("spend/view public keys must be 32 bytes")
    if len(payment_id) != VID_LEN:
        raise AddressError("payment id / vid must be %d bytes" % VID_LEN)
    prefix = NETBYTES[network]["integrated"]
    payload = bytes([prefix]) + spend_pub + view_pub + payment_id
    checksum = keccak256(payload)[:4]
    return xmr_base58_encode(payload + checksum)


def decode_address(addr: str) -> dict:
    raw = xmr_base58_decode(addr.strip())
    if len(raw) < 5:
        raise AddressError("address too short")
    payload, checksum = raw[:-4], raw[-4:]
    if keccak256(payload)[:4] != checksum:
        raise AddressError("bad checksum")
    netbyte = payload[0]
    info = NETBYTE_TO_NET.get(netbyte)
    if info is None:
        raise AddressError("unknown network byte %d" % netbyte)
    network, kind = info
    if kind == "integrated":
        if len(payload) != 1 + PUB_LEN + PUB_LEN + VID_LEN:
            raise AddressError("integrated address has wrong payload length")
        spend = payload[1:33]
        view = payload[33:65]
        pid = payload[65:73]
    elif kind in ("standard", "subaddress"):
        if len(payload) != 1 + PUB_LEN + PUB_LEN:
            raise AddressError("standard address has wrong payload length")
        spend = payload[1:33]
        view = payload[33:65]
        pid = b""
    else:
        raise AddressError("unhandled address kind")
    return {
        "network": network,
        "kind": kind,
        "spend_pub": spend,
        "view_pub": view,
        "payment_id": pid,
        "netbyte": netbyte,
    }


def payment_id_of(addr: str) -> bytes:
    parsed = decode_address(addr)
    if parsed["kind"] != "integrated":
        raise AddressError("not an integrated address")
    return parsed["payment_id"]
