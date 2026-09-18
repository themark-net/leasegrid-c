"""Canonical request binding R (docs/02-objects.md §2.4)."""

from __future__ import annotations

from .constants import DOMAIN, TOKEN_EPOCH_V0


class RError(ValueError):
    """R is malformed or fields disagree with the operation."""


def _put(parts: list[bytes], field: bytes) -> None:
    if len(field) > 65535:
        raise RError("R field longer than 65535 bytes")
    parts.append(len(field).to_bytes(2, "big"))
    parts.append(field)


def encode_r(
    *,
    nodeid: str | bytes,
    storage_index: bytes,
    lease_seconds: int,
    share_bytes: int,
    token_epoch: int = TOKEN_EPOCH_V0,
    issuer_pubkey_id: str | bytes,
    domain: str = DOMAIN,
) -> bytes:
    """
    R = domain || nodeid || storage_index || lease_seconds || share_bytes
        || token_epoch || issuer_pubkey_id

    Length-prefixed fields (uint16 BE + bytes). nodeid and issuer_pubkey_id
    are ASCII (Tahoe my_nodeid string; hex pubkey id). storage_index is raw.
    """
    if not isinstance(storage_index, (bytes, bytearray)):
        raise RError("storage_index must be bytes")
    if lease_seconds < 0 or share_bytes < 0 or token_epoch < 0:
        raise RError("numeric R fields must be >= 0")
    nodeid_b = nodeid.encode("ascii") if isinstance(nodeid, str) else nodeid
    pk_b = (
        issuer_pubkey_id.encode("ascii")
        if isinstance(issuer_pubkey_id, str)
        else issuer_pubkey_id
    )
    parts: list[bytes] = []
    _put(parts, domain.encode("ascii"))
    _put(parts, nodeid_b)
    _put(parts, bytes(storage_index))
    _put(parts, str(int(lease_seconds)).encode("ascii"))
    _put(parts, str(int(share_bytes)).encode("ascii"))
    _put(parts, str(int(token_epoch)).encode("ascii"))
    _put(parts, pk_b)
    return b"".join(parts)


def decode_r(r: bytes) -> dict:
    fields = []
    i = 0
    while i < len(r):
        if i + 2 > len(r):
            raise RError("truncated R length")
        n = int.from_bytes(r[i : i + 2], "big")
        i += 2
        if i + n > len(r):
            raise RError("truncated R field")
        fields.append(r[i : i + n])
        i += n
    if len(fields) != 7:
        raise RError("R must have 7 fields, got %d" % len(fields))
    domain, nodeid, storage_index, lease_s, share_s, epoch_s, pk = fields
    try:
        return {
            "domain": domain.decode("ascii"),
            "nodeid": nodeid.decode("ascii"),
            "storage_index": bytes(storage_index),
            "lease_seconds": int(lease_s.decode("ascii")),
            "share_bytes": int(share_s.decode("ascii")),
            "token_epoch": int(epoch_s.decode("ascii")),
            "issuer_pubkey_id": pk.decode("ascii"),
        }
    except (UnicodeDecodeError, ValueError) as e:
        raise RError("R field decode failed") from e
