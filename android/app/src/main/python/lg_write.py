"""Put and remove a file in a folder the phone already has.

A writable folder is ``URI:DIR2:`` (not a read-only or immutable cap). The
chip may say On friendnet only after a read-back of the same bytes. A
Magic Folder collective stores the bytes as a signed snapshot in a
participant directory the desktop downloader polls. A raw CHK on the
collective root is not downloaded.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import struct
import time
from dataclasses import dataclass
from typing import Any, Optional

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, padding, rsa
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)

from lg_cbor import dumps, loads
from lg_fec import encode_blocks
from lg_tahoe import (
    ReadFail,
    StorageServer,
    _aes_ctr,
    _tagged_hash,
    _tagged_pair,
    a2b,
    b2a,
    download_file,
    http_storage,
    list_folder_view,
    read_sdmf,
)

UEB_TAG = b"allmydata_uri_extension_v1"
BLOCK_TAG = b"allmydata_encoded_subshare_v1"
CIPHERTEXT_TAG = b"allmydata_crypttext_v1"
CIPHERTEXT_SEGMENT_TAG = b"allmydata_crypttext_segment_v1"
STORAGE_INDEX_TAG = b"allmydata_immutable_key_to_storage_index_v1"
MUTABLE_WRITEKEY_TAG = b"allmydata_mutable_privkey_to_writekey_v1"
MUTABLE_WRITE_ENABLER_MASTER_TAG = b"allmydata_mutable_writekey_to_write_enabler_master_v1"
MUTABLE_WRITE_ENABLER_TAG = b"allmydata_mutable_write_enabler_master_and_nodeid_to_write_enabler_v1"
MUTABLE_PUBKEY_TAG = b"allmydata_mutable_pubkey_to_fingerprint_v1"
MUTABLE_READKEY_TAG = b"allmydata_mutable_writekey_to_readkey_v1"
MUTABLE_DATAKEY_TAG = b"allmydata_mutable_readkey_to_datakey_v1"
MUTABLE_STORAGEINDEX_TAG = b"allmydata_mutable_readkey_to_storage_index_v1"
DIRNODE_CHILD_WRITECAP_TAG = b"allmydata_mutable_writekey_and_salt_to_dirnode_child_capkey_v1"
DIRNODE_CHILD_SALT_TAG = b"allmydata_dirnode_child_rwcap_to_salt_v1"
EMPTY_LEAF_TAG = b"Merkle tree empty leaf"
PAIR_TAG = b"Merkle tree internal node"

ADD_FAIL = "could not add this file."
ADD_NEXT = "check network; Retry."
REMOVE_FAIL = "could not remove this file."
REMOVE_NEXT = "Retry."
READ_FAIL = "could not read this file."
READ_NEXT = "pick it again."
SPACE_FAIL = "not enough free space."
SPACE_NEXT = "free space; Retry."
RO_FAIL = "could not add this file."
RO_NEXT = "Adding files is not available in this folder."

PREFIX = struct.Struct(">BQ32s16s")
SIGNED = struct.Struct(">BQ32s16sBBQQ")
MUTABLE = struct.Struct(">BQ32s16sBBQQLLLLQQ")
PSS = padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=32)


class WriteFail(Exception):
    def __init__(self, message: str, next_hint: str) -> None:
        super().__init__(message)
        self.message = message
        self.next_hint = next_hint


def directory_writable(cap: str) -> bool:
    """True only for a mutable directory write cap.

    ``URI:DIR2-RO:``, ``URI:DIR2-CHK:``, and ``URI:DIR2-LIT:`` all contain a
    hyphen and cannot accept a new child.
    """
    text = (cap or "").strip()
    return text.startswith("URI:DIR2:") and not text.startswith("URI:DIR2-")


def keep_both_name(name: str, taken: set[str]) -> str:
    """Distinct visible name. ``beach.jpg`` becomes ``beach (phone).jpg``."""
    if "." in name[1:]:
        stem, ext = name.rsplit(".", 1)
        ext = "." + ext
    else:
        stem, ext = name, ""
    candidate = "%s (phone)%s" % (stem, ext)
    number = 2
    while candidate in taken:
        candidate = "%s (phone %d)%s" % (stem, number, ext)
        number += 1
        if number > 50:
            raise WriteFail(ADD_FAIL, "Choose a different file; Retry.")
    return candidate


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _netstring(data: bytes) -> bytes:
    return b"%d:%s," % (len(data), data)


def _split_netstrings(data: bytes, count: int, position: int = 0) -> tuple[list[bytes], int]:
    out: list[bytes] = []
    while len(out) < count:
        if position >= len(data):
            raise WriteFail(ADD_FAIL, "Retry. The folder bytes were cut short.")
        colon = data.index(b":", position)
        length = int(data[position:colon])
        start = colon + 1
        blob = data[start : start + length]
        if len(blob) != length or data[start + length : start + length + 1] != b",":
            raise WriteFail(ADD_FAIL, "Retry. The folder bytes were not a directory.")
        out.append(blob)
        position = start + length + 1
    return out, position


def _next_multiple(n: int, k: int) -> int:
    if k <= 0:
        raise WriteFail(ADD_FAIL, "Retry.")
    if n % k == 0:
        return n
    return n + k - (n % k)


def _div_ceil(n: int, d: int) -> int:
    return (n + d - 1) // d


def _roundup_pow2(n: int) -> int:
    ans = 1
    while ans < n:
        ans *= 2
    return ans


def _empty_leaf(i: int) -> bytes:
    return _tagged_hash(EMPTY_LEAF_TAG, b"%d" % i)


def _pair(a: bytes, b: bytes) -> bytes:
    return _tagged_pair(PAIR_TAG, a, b)


class _HashTree:
    def __init__(self, leaves: list[bytes]) -> None:
        end = _roundup_pow2(len(leaves) if leaves else 1)
        self.first_leaf = end - 1
        row: list[Optional[bytes]] = list(leaves) + [None] * (end - len(leaves))
        for i in range(len(leaves), end):
            row[i] = _empty_leaf(i)
        rows: list[list[bytes]] = [row]  # type: ignore[list-item]
        while len(rows[-1]) != 1:
            last = rows[-1]
            rows.append([_pair(last[2 * i], last[2 * i + 1]) for i in range(len(last) // 2)])
        rows.reverse()
        self.nodes: list[bytes] = []
        for one in rows:
            self.nodes.extend(one)

    def __getitem__(self, index: int) -> bytes:
        return self.nodes[index]

    def needed(self, leafnum: int, include_leaf: bool = False) -> list[int]:
        here = self.first_leaf + leafnum
        found: set[int] = set()
        while here != 0:
            parent = (here - 1) // 2
            left = 2 * parent + 1
            sib = left + 1 if here == left else left
            found.add(sib)
            here = parent
        if include_leaf:
            found.add(self.first_leaf + leafnum)
        return sorted(found)


def _pack_extension(data: dict[str, Any]) -> bytes:
    pieces = []
    for key in sorted(data.keys()):
        value = data[key]
        if isinstance(value, int):
            value = b"%d" % value
        if isinstance(key, str):
            key_b = key.encode("utf-8")
        else:
            key_b = key
        pieces.append(key_b + b":" + _netstring(value))
    return b"".join(pieces)


def _tahoe_hmac(key: bytes, data: bytes) -> bytes:
    ikey = bytes(b ^ 0x36 for b in key)
    okey = bytes(b ^ 0x5C for b in key)
    inner = hashlib.sha256(ikey + data).digest()
    return hashlib.sha256(okey + inner).digest()


def encrypt_rw_uri(writekey: bytes, rw_uri: bytes) -> bytes:
    salt = _tagged_hash(DIRNODE_CHILD_SALT_TAG, rw_uri, 16)
    key = _tagged_pair(DIRNODE_CHILD_WRITECAP_TAG, salt, writekey, 16)
    crypt = _aes_ctr(key, rw_uri)
    return salt + crypt + _tahoe_hmac(key, salt + crypt)


def decrypt_rw_uri(writekey: bytes, blob: bytes) -> bytes:
    if len(blob) < 48:
        return b""
    salt, crypt, mac = blob[:16], blob[16:-32], blob[-32:]
    key = _tagged_pair(DIRNODE_CHILD_WRITECAP_TAG, salt, writekey, 16)
    if _tahoe_hmac(key, salt + crypt) != mac:
        return b""
    return _aes_ctr(key, crypt)


@dataclass
class DirEntry:
    name: str
    ro: str
    rw: bytes
    meta: dict[str, Any]
    raw: bytes = b""
    dirty: bool = False


def _pack_entry(entry: DirEntry) -> bytes:
    meta = json.dumps(entry.meta, sort_keys=True, separators=(",", ":")).encode("utf-8")
    inner = b"".join(
        [
            _netstring(entry.name.encode("utf-8")),
            _netstring(entry.ro.encode("utf-8")),
            _netstring(entry.rw),
            _netstring(meta),
        ]
    )
    return _netstring(inner)


def unpack_entries(data: bytes) -> list[DirEntry]:
    if not data:
        return []
    entries: list[DirEntry] = []
    pos = 0
    while pos < len(data):
        start = pos
        (inner,), pos = _split_netstrings(data, 1, pos)
        raw = data[start:pos]
        fields, _ = _split_netstrings(inner, 4, 0)
        name = fields[0].decode("utf-8")
        ro = fields[1].decode("utf-8")
        try:
            meta = json.loads(fields[3].decode("utf-8") or "{}")
        except json.JSONDecodeError:
            meta = {}
        if not isinstance(meta, dict):
            meta = {}
        entries.append(DirEntry(name=name, ro=ro, rw=fields[2], meta=meta, raw=raw))
    return entries


def pack_entries(entries: list[DirEntry]) -> bytes:
    ordered = sorted(entries, key=lambda entry: entry.name)
    parts = []
    for entry in ordered:
        if entry.raw and not entry.dirty:
            parts.append(entry.raw)
        else:
            parts.append(_pack_entry(entry))
    return b"".join(parts)


def _basename(name: str) -> str:
    cleaned = (name or "").replace("\\", "/").split("/")[-1].replace("\x00", "").strip()
    if not cleaned or cleaned in (".", ".."):
        raise WriteFail(READ_FAIL, READ_NEXT)
    return cleaned[:180]


def encode_chk(data: bytes, needed: int, total: int) -> tuple[str, list[bytes]]:
    """Return ``(URI:CHK:…, shares)`` readable by Tahoe and by ``read_chk``."""
    if needed < 1 or total < needed or total > 256:
        raise WriteFail(ADD_FAIL, "Retry.")
    if not data:
        return "URI:LIT:", []
    key = os.urandom(16)
    crypt = _aes_ctr(key, data)
    segsize = _next_multiple(min(128 * 1024, len(data)), needed)
    num_segments = _div_ceil(len(data), segsize)
    main_block = segsize // needed
    segments: list[bytes] = []
    offset = 0
    for seg in range(num_segments):
        if seg == num_segments - 1:
            segments.append(crypt[offset:])
        else:
            segments.append(crypt[offset : offset + segsize])
            offset += segsize
    tail = segments[-1]
    padded_tail = _next_multiple(len(tail), needed)
    tail_block = padded_tail // needed
    share_rows: list[list[bytes]] = [[] for _ in range(total)]
    segment_hashes = []
    for seg, segment in enumerate(segments):
        segment_hashes.append(_tagged_hash(CIPHERTEXT_SEGMENT_TAG, segment))
        is_tail = seg == num_segments - 1
        width = padded_tail if is_tail else segsize
        block = tail_block if is_tail else main_block
        padded = segment + b"\x00" * (width - len(segment))
        pieces = [padded[i * block : (i + 1) * block] for i in range(needed)]
        encoded = encode_blocks(needed, total, pieces)
        for num, blob in enumerate(encoded):
            share_rows[num].append(blob)
    crypt_hash = _tagged_hash(CIPHERTEXT_TAG, crypt)
    crypt_tree = _HashTree(segment_hashes)
    block_roots = []
    block_trees: list[list[bytes]] = []
    for blocks in share_rows:
        tree = _HashTree([_tagged_hash(BLOCK_TAG, block) for block in blocks])
        block_roots.append(tree[0])
        block_trees.append(list(tree.nodes))
    share_tree = _HashTree(block_roots)
    needed_count = len(share_tree.needed(0, include_leaf=True))
    ueb_body = {
        "codec_name": b"crs",
        "codec_params": b"%d-%d-%d" % (segsize, needed, total),
        "size": len(data),
        "segment_size": segsize,
        "num_segments": num_segments,
        "needed_shares": needed,
        "total_shares": total,
        "tail_codec_params": b"%d-%d-%d" % (padded_tail, needed, total),
        "crypttext_hash": crypt_hash,
        "crypttext_root_hash": crypt_tree[0],
        "share_root_hash": share_tree[0],
    }
    ueb = _pack_extension(ueb_body)
    ueb_hash = _tagged_hash(UEB_TAG, ueb)
    effective = _roundup_pow2(num_segments)
    segment_hash_size = (2 * effective - 1) * 32
    data_size = (num_segments - 1) * main_block + tail_block
    share_hash_size = needed_count * (2 + 32)
    uri_at = 0x24 + data_size + segment_hash_size * 3 + share_hash_size
    shares: list[bytes] = []
    for num in range(total):
        header = struct.pack(
            ">LLLLLLLLL",
            1,
            main_block,
            data_size,
            0x24,
            0x24 + data_size,
            0x24 + data_size + segment_hash_size,
            0x24 + data_size + 2 * segment_hash_size,
            0x24 + data_size + 3 * segment_hash_size,
            uri_at,
        )
        assert len(header) == 0x24
        packed_blocks = b"".join(share_rows[num])
        assert len(packed_blocks) == data_size
        crypt_bytes = b"".join(crypt_tree.nodes)
        block_bytes = b"".join(block_trees[num])
        if len(crypt_bytes) != segment_hash_size or len(block_bytes) != segment_hash_size:
            raise WriteFail(ADD_FAIL, "Retry.")
        chain = b"".join(
            struct.pack(">H32s", idx, share_tree[idx])
            for idx in share_tree.needed(num, include_leaf=True)
        )
        if len(chain) != share_hash_size:
            raise WriteFail(ADD_FAIL, "Retry.")
        blob = b"".join(
            [
                header,
                packed_blocks,
                b"\x00" * segment_hash_size,
                crypt_bytes,
                block_bytes,
                chain,
                struct.pack(">L", len(ueb)),
                ueb,
            ]
        )
        shares.append(blob)
    cap = "URI:CHK:%s:%s:%d:%d:%d" % (b2a(key), b2a(ueb_hash), needed, total, len(data))
    return cap, shares


def _storage_index_immutable(key: bytes) -> bytes:
    return _tagged_hash(STORAGE_INDEX_TAG, key, 16)


def _key_from_chk(cap: str) -> bytes:
    body = cap[len("URI:CHK:") :]
    return a2b(body.split(":", 1)[0])


def _auth(kind: str, secret: bytes) -> tuple[str, str]:
    return ("X-Tahoe-Authorization", "%s %s" % (kind, _b64(secret)))


def _server_exchange(
    server: StorageServer,
    method: str,
    path: str,
    body: bytes = b"",
    headers: Optional[list[tuple[str, str]]] = None,
    message: str = ADD_FAIL,
    nxt: str = ADD_NEXT,
) -> tuple[int, bytes]:
    try:
        tubid, hosts, swiss = server.hints()
    except ReadFail as exc:
        raise WriteFail(message, exc.next_hint) from exc
    last: Optional[WriteFail] = None
    for host, port in hosts:
        try:
            return http_storage(
                host,
                port,
                tubid,
                method,
                path,
                swiss,
                body,
                headers,
                fail_message=message,
                fail_next=nxt,
            )
        except ReadFail as exc:
            last = WriteFail(message, exc.next_hint)
    if last:
        raise last
    raise WriteFail(message, nxt)


def upload_immutable(
    data: bytes,
    needed: int,
    total: int,
    servers: list[StorageServer],
) -> str:
    if not data:
        return "URI:LIT:"
    cap, shares = encode_chk(data, needed, total)
    if cap.startswith("URI:LIT:"):
        return cap
    si = b2a(_storage_index_immutable(_key_from_chk(cap)))
    upload_secret = os.urandom(32)
    renew = os.urandom(32)
    cancel = os.urandom(32)
    if not servers:
        raise WriteFail(ADD_FAIL, ADD_NEXT)
    placed = 0
    for num, share in enumerate(shares):
        server = servers[num % len(servers)]
        if _upload_share(server, si, num, share, upload_secret, renew, cancel):
            placed += 1
    if placed < needed:
        raise WriteFail(ADD_FAIL, ADD_NEXT)
    return cap


def _as_set(value: Any) -> set[int]:
    if isinstance(value, set):
        return {int(item) for item in value}
    if isinstance(value, list):
        return {int(item) for item in value}
    return set()


def _upload_share(
    server: StorageServer,
    si: str,
    num: int,
    share: bytes,
    upload_secret: bytes,
    renew: bytes,
    cancel: bytes,
) -> bool:
    try:
        code, body = _server_exchange(
            server,
            "POST",
            "/storage/v1/immutable/" + si,
            dumps({"share-numbers": {num}, "allocated-size": len(share)}),
            [
                ("Content-Type", "application/cbor"),
                _auth("upload-secret", upload_secret),
                _auth("lease-renew-secret", renew),
                _auth("lease-cancel-secret", cancel),
            ],
        )
    except WriteFail:
        return False
    if code != 200:
        return False
    try:
        decoded = loads(body)
    except Exception:
        return False
    if not isinstance(decoded, dict):
        return False
    if num in _as_set(decoded.get("already-have")):
        return True
    if num not in _as_set(decoded.get("allocated")):
        return False
    end = len(share)
    try:
        code, _body = _server_exchange(
            server,
            "PATCH",
            "/storage/v1/immutable/%s/%d" % (si, num),
            share,
            [
                ("Content-Range", "bytes 0-%d/%d" % (end - 1, end)),
                _auth("upload-secret", upload_secret),
            ],
        )
    except WriteFail:
        return False
    return code in (200, 201)


def _parse_write_cap(cap: str) -> tuple[bytes, bytes]:
    if not directory_writable(cap):
        raise WriteFail(RO_FAIL, RO_NEXT)
    body = cap[len("URI:DIR2:") :]
    write_b32, fp_b32 = body.split(":", 1)
    return a2b(write_b32), a2b(fp_b32)


def readonly_dir_cap(cap: str) -> str:
    writekey, fp = _parse_write_cap(cap)
    readkey = _tagged_hash(MUTABLE_READKEY_TAG, writekey, 16)
    return "URI:DIR2-RO:%s:%s" % (b2a(readkey), b2a(fp))


def _readkey(writekey: bytes) -> bytes:
    return _tagged_hash(MUTABLE_READKEY_TAG, writekey, 16)


def _fetch_share(server: StorageServer, kind: str, si: bytes, num: int) -> Optional[bytes]:
    path = "/storage/v1/%s/%s/%d" % (kind, b2a(si), num)
    try:
        code, body = _server_exchange(server, "GET", path)
    except WriteFail:
        return None
    if code == 404:
        return None
    if code not in (200, 206) or not body:
        return None
    return body


def _announced_total(blob: bytes) -> Optional[int]:
    """Share count from an SDMF header. None when the header is not usable."""
    if len(blob) < MUTABLE.size:
        return None
    try:
        total = int(MUTABLE.unpack_from(blob, 0)[5])
    except struct.error:
        return None
    if total < 1 or total > 256:
        return None
    return total


def _locate(servers: list[StorageServer], kind: str, si: bytes, total: int) -> dict[int, tuple[StorageServer, bytes]]:
    """Find shares ``0 .. n-1``.

    ``n`` comes from the first share header. Callers used to pass
    ``max(total, 16)`` and then probe share numbers the header says do
    not exist. Each miss can sit on the storage socket timeout, so a
    put never reaches read-back and the row never fails closed.
    """
    found: dict[int, tuple[StorageServer, bytes]] = {}
    limit = max(int(total), 1)
    num = 0
    while num < limit:
        for server in servers:
            blob = _fetch_share(server, kind, si, num)
            if not blob:
                continue
            found[num] = (server, blob)
            if kind == "mutable":
                announced = _announced_total(blob)
                if announced is not None:
                    limit = announced
            break
        num += 1
    return found


def _new_mutable_keys() -> tuple[Any, bytes, bytes, bytes, bytes, bytes]:
    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv_der = priv.private_bytes(Encoding.DER, PrivateFormat.PKCS8, NoEncryption())
    pub_der = priv.public_key().public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)
    writekey = _tagged_hash(MUTABLE_WRITEKEY_TAG, priv_der, 16)
    encpriv = _aes_ctr(writekey, priv_der)
    fingerprint = _tagged_hash(MUTABLE_PUBKEY_TAG, pub_der)
    return priv, priv_der, pub_der, writekey, encpriv, fingerprint


def _load_priv(writekey: bytes, encpriv: bytes) -> Any:
    priv_der = _aes_ctr(writekey, encpriv)
    if _tagged_hash(MUTABLE_WRITEKEY_TAG, priv_der, 16) != writekey:
        raise WriteFail(ADD_FAIL, "Retry. This folder key did not match.")
    return serialization.load_der_private_key(priv_der, password=None)


def _build_sdmf_shares(
    plaintext: bytes,
    needed: int,
    total: int,
    seqnum: int,
    salt: bytes,
    readkey: bytes,
    priv: Any,
    pub_der: bytes,
    encpriv: bytes,
) -> list[bytes]:
    datalen = len(plaintext)
    if datalen == 0:
        segsize = 0
        share_blocks = [b""] * total
        block_roots = []
        block_trees = []
        empty = _HashTree([])
        for _ in range(total):
            block_roots.append(empty[0])
            block_trees.append(b"".join(empty.nodes))
    else:
        segsize = _next_multiple(datalen, needed)
        padded = plaintext + b"\x00" * (segsize - datalen)
        datakey = _tagged_pair(MUTABLE_DATAKEY_TAG, salt, readkey, 16)
        crypt = _aes_ctr(datakey, padded)
        piece = segsize // needed
        pieces = [crypt[i * piece : (i + 1) * piece] for i in range(needed)]
        share_blocks = encode_blocks(needed, total, pieces)
        block_roots = []
        block_trees = []
        for block in share_blocks:
            tree = _HashTree([_tagged_hash(BLOCK_TAG, block)])
            block_roots.append(tree[0])
            block_trees.append(b"".join(tree.nodes))
    share_tree = _HashTree(block_roots)
    root = share_tree[0]
    prefix = SIGNED.pack(0, seqnum, root, salt, needed, total, segsize, datalen)
    signature = priv.sign(prefix, PSS, hashes.SHA256())
    shares = []
    header_len = MUTABLE.size
    for num in range(total):
        chain = b"".join(
            struct.pack(">H32s", idx, share_tree[idx]) for idx in share_tree.needed(num, True)
        )
        block_bytes = block_trees[num]
        data = share_blocks[num]
        off_sig = header_len + len(pub_der)
        off_hash = off_sig + len(signature)
        off_block = off_hash + len(chain)
        off_data = off_block + len(block_bytes)
        off_priv = off_data + len(data)
        eof = off_priv + len(encpriv)
        header = MUTABLE.pack(
            0,
            seqnum,
            root,
            salt,
            needed,
            total,
            segsize,
            datalen,
            off_sig,
            off_hash,
            off_block,
            off_data,
            off_priv,
            eof,
        )
        shares.append(b"".join([header, pub_der, signature, chain, block_bytes, data, encpriv]))
    return shares


def _write_enabler(writekey: bytes, peerid: bytes) -> bytes:
    if len(peerid) != 20:
        raise WriteFail(ADD_FAIL, "Refresh folders, then Retry.")
    master = _tagged_hash(MUTABLE_WRITE_ENABLER_MASTER_TAG, writekey)
    return _tagged_pair(MUTABLE_WRITE_ENABLER_TAG, master, peerid)


def _push_mutable(
    servers: list[StorageServer],
    writekey: bytes,
    readkey: bytes,
    shares: list[bytes],
    old: dict[int, tuple[StorageServer, bytes]],
    needed: int,
) -> None:
    si = _tagged_hash(MUTABLE_STORAGEINDEX_TAG, readkey, 16)
    si_s = b2a(si)
    renew = _tagged_hash(b"leasegrid_phone_lease_renew_v1", writekey)
    cancel = _tagged_hash(b"leasegrid_phone_lease_cancel_v1", writekey)
    placed = 0
    for num, blob in enumerate(shares):
        server = old[num][0] if num in old else servers[num % len(servers)]
        prefix = old[num][1][: PREFIX.size] if num in old else None
        if _push_one_mutable(server, si_s, num, blob, writekey, renew, cancel, prefix):
            placed += 1
    if placed < needed:
        raise WriteFail(ADD_FAIL, ADD_NEXT)


def _push_one_mutable(
    server: StorageServer,
    si: str,
    num: int,
    blob: bytes,
    writekey: bytes,
    renew: bytes,
    cancel: bytes,
    old_prefix: Optional[bytes],
) -> bool:
    try:
        tubid, _hosts, _swiss = server.hints()
        peerid = a2b(tubid)
        enabler = _write_enabler(writekey, peerid)
    except (ReadFail, WriteFail):
        return False
    if old_prefix is None:
        test = [{"offset": 0, "size": 1, "specimen": b""}]
    else:
        test = [{"offset": 0, "size": len(old_prefix), "specimen": old_prefix}]
    message = {
        "test-write-vectors": {
            num: {
                "test": test,
                "write": [{"offset": 0, "data": blob}],
                "new-length": len(blob),
            }
        },
        "read-vector": [{"offset": 0, "size": PREFIX.size}],
    }
    try:
        code, body = _server_exchange(
            server,
            "POST",
            "/storage/v1/mutable/%s/read-test-write" % si,
            dumps(message),
            [
                ("Content-Type", "application/cbor"),
                _auth("write-enabler", enabler),
                _auth("lease-renew-secret", renew),
                _auth("lease-cancel-secret", cancel),
            ],
        )
    except WriteFail:
        return False
    if code != 200:
        return False
    try:
        decoded = loads(body)
    except Exception:
        return False
    return isinstance(decoded, dict) and decoded.get("success") is True


def _publish_new_directory(plaintext: bytes, needed: int, total: int, servers: list[StorageServer]) -> str:
    priv, _priv_der, pub_der, writekey, encpriv, fingerprint = _new_mutable_keys()
    readkey = _readkey(writekey)
    salt = os.urandom(16) if plaintext else b"\x00" * 16
    shares = _build_sdmf_shares(plaintext, needed, total, 1, salt, readkey, priv, pub_der, encpriv)
    _push_mutable(servers, writekey, readkey, shares, {}, needed)
    return "URI:DIR2:%s:%s" % (b2a(writekey), b2a(fingerprint))


def _rewrite_directory(
    cap: str,
    servers: list[StorageServer],
    needed: int,
    total: int,
    plaintext: bytes,
    message: str = ADD_FAIL,
    nxt: str = ADD_NEXT,
) -> None:
    writekey, fingerprint = _parse_write_cap(cap)
    readkey = _readkey(writekey)
    si = _tagged_hash(MUTABLE_STORAGEINDEX_TAG, readkey, 16)
    # Learn k/n from an existing share when the folder was created elsewhere.
    # Do not scan past that n. Missing higher share numbers are not a
    # reason to wait out another socket timeout before read-back.
    located = _locate(servers, "mutable", si, max(int(total), 1))
    if not located:
        raise WriteFail(message, nxt)
    sample = next(iter(located.values()))[1]
    if len(sample) < MUTABLE.size:
        raise WriteFail(message, nxt)
    fields = MUTABLE.unpack_from(sample, 0)
    seqnum, k, n = fields[1], fields[4], fields[5]
    off_sig, _off_hash, _off_block, _off_data, off_priv, eof = fields[8:]
    pub_der = sample[MUTABLE.size : off_sig]
    encpriv = sample[off_priv:eof]
    if _tagged_hash(MUTABLE_PUBKEY_TAG, pub_der) != fingerprint:
        raise WriteFail(message, nxt)
    priv = _load_priv(writekey, encpriv)
    salt = os.urandom(16) if plaintext else b"\x00" * 16
    shares = _build_sdmf_shares(plaintext, k, n, int(seqnum) + 1, salt, readkey, priv, pub_der, encpriv)
    # Only test shares that actually exist. Extra encoded shares fill gaps.
    old = {num: item for num, item in located.items() if num < n}
    try:
        _push_mutable(servers, writekey, readkey, shares, old, k)
    except WriteFail as exc:
        raise WriteFail(message, nxt) from exc


def _load_entries(cap: str, servers: list[StorageServer]) -> list[DirEntry]:
    try:
        data = read_sdmf(cap, servers) if directory_writable(cap) or cap.startswith("URI:DIR2") else download_file(cap, servers)
    except ReadFail as exc:
        raise WriteFail(exc.message, exc.next_hint) from exc
    return unpack_entries(data)


def _is_mutable_dir(ro: str) -> bool:
    if ro.startswith("URI:DIR2-CHK:") or ro.startswith("URI:DIR2-LIT:"):
        return False
    return ro.startswith("URI:DIR2") or ro.startswith("URI:SSK")


def _participant_entries(entries: list[DirEntry]) -> list[DirEntry]:
    """Mutable directories linked in a collective. ``@metadata`` is not one."""
    return [
        entry
        for entry in entries
        if entry.name != "@metadata" and _is_mutable_dir(entry.ro)
    ]


def _is_collective(entries: list[DirEntry]) -> bool:
    """A Magic Folder collective, including one that has ``@metadata``.

    The desktop Photos collective is ``@metadata`` (an immutable file) plus
    the read-only participant directories. Requiring every child to be a
    mutable directory missed ``@metadata``, so the add stored a raw CHK on
    the collective root. Magic Folder does not download that.
    """
    if not _participant_entries(entries):
        return False
    if any(entry.name == "@metadata" for entry in entries):
        return True
    return all(_is_mutable_dir(entry.ro) for entry in entries)


def _without_root_files(entries: list[DirEntry]) -> list[DirEntry]:
    """Drop children that are not ``@metadata`` and not a participant.

    The downloader treats every other collective child as a participant.
    Listing a raw CHK there raises, and the poll stops, so those children
    also hide a snapshot that was linked correctly.
    """
    return [
        entry
        for entry in entries
        if entry.name == "@metadata" or _is_mutable_dir(entry.ro)
    ]


def _writable_participant(entry: DirEntry, writekey: bytes) -> str:
    """Write cap stored on a participant this phone linked. Empty if absent."""
    if not entry.rw:
        return ""
    text = decrypt_rw_uri(writekey, entry.rw).decode("utf-8", "replace").strip()
    if directory_writable(text):
        return text
    return ""


def _participant_is_linked(entries: list[DirEntry], writekey: bytes, dmd: str) -> bool:
    read_only = readonly_dir_cap(dmd)
    for entry in entries:
        if entry.ro == read_only or _writable_participant(entry, writekey) == dmd:
            return True
    return False


def _file_entry(name: str, cap: str, size: int) -> DirEntry:
    now = time.time()
    return DirEntry(
        name=name,
        ro=cap,
        rw=b"",
        meta={"tahoe": {"linkcrtime": now, "linkmotime": now, "size": size}},
        dirty=True,
    )


def _dir_entry(name: str, write_cap: str, writekey: bytes) -> DirEntry:
    now = time.time()
    rw = encrypt_rw_uri(writekey, write_cap.encode("utf-8"))
    return DirEntry(
        name=name,
        ro=readonly_dir_cap(write_cap),
        rw=rw,
        meta={"tahoe": {"linkcrtime": now, "linkmotime": now}},
        dirty=True,
    )


def _upsert(entries: list[DirEntry], fresh: DirEntry) -> list[DirEntry]:
    kept = [entry for entry in entries if entry.name != fresh.name]
    kept.append(fresh)
    return kept


def _drop(entries: list[DirEntry], name: str) -> list[DirEntry]:
    return [entry for entry in entries if entry.name != name]


def _commit_entries(
    cap: str,
    servers: list[StorageServer],
    needed: int,
    total: int,
    entries: list[DirEntry],
    message: str = ADD_FAIL,
    nxt: str = ADD_NEXT,
) -> None:
    _rewrite_directory(cap, servers, needed, total, pack_entries(entries), message, nxt)


def _snapshot_cap(
    name: str,
    content_cap: str,
    seed: bytes,
    needed: int,
    total: int,
    servers: list[StorageServer],
) -> str:
    key = ed25519.Ed25519PrivateKey.from_private_bytes(seed)
    verify = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    verify_b64 = _b64(verify)
    now = int(time.time())
    meta_obj = {
        "author": {"name": "phone", "verify_key": verify_b64},
        "modification_time": now,
        "parents": [],
        "relpath": name,
        "snapshot_version": 1,
    }
    meta_bytes = json.dumps(meta_obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
    meta_cap = upload_immutable(meta_bytes, needed, total, servers)
    signed = (
        "magic-folder-snapshot-v1\n%s\n%s\n%s\n" % (content_cap, meta_cap, name)
    ).encode("utf-8")
    signature = _b64(key.sign(signed))
    content = DirEntry(
        name="content",
        ro=content_cap,
        rw=b"",
        meta={"ctime": now, "mtime": now},
        dirty=True,
    )
    metadata = DirEntry(
        name="metadata",
        ro=meta_cap,
        rw=b"",
        meta={"magic_folder": {"author_signature": signature}},
        dirty=True,
    )
    directory = pack_entries([content, metadata])
    chk = upload_immutable(directory, needed, total, servers)
    if chk.startswith("URI:LIT:"):
        return "URI:DIR2-LIT:" + chk[len("URI:LIT:") :]
    if not chk.startswith("URI:CHK:"):
        raise WriteFail(ADD_FAIL, ADD_NEXT)
    return "URI:DIR2-CHK:" + chk[len("URI:CHK:") :]


def _phone_dmd_name(entries: list[DirEntry]) -> str:
    taken = {entry.name for entry in entries}
    if "phone" not in taken:
        return "phone"
    number = 2
    while "phone-%d" % number in taken:
        number += 1
    return "phone-%d" % number


def _put_in_container(
    container: str,
    name: str,
    child: DirEntry,
    servers: list[StorageServer],
    needed: int,
    total: int,
) -> None:
    entries = _load_entries(container, servers)
    _commit_entries(container, servers, needed, total, _upsert(entries, child))


def _place_in_collective(
    dir_cap: str,
    name: str,
    data: bytes,
    content_cap: str,
    servers: list[StorageServer],
    needed: int,
    total: int,
    author_seed: bytes,
    phone_dmd: str,
    entries: list[DirEntry],
) -> dict[str, Any]:
    """Put a snapshot where Magic Folder's downloader will fetch it.

    The desktop's own participant is linked read-only, and the downloader
    skips that directory (it is "self"). This phone cannot write it. A
    participant this phone can write is polled, because its cap is not the
    desktop upload directory. Reuse that directory when it is already
    linked. Raw CHK children are removed in the same rewrite: they are not
    participants, and the poll aborts on them.
    """
    writekey, _fp = _parse_write_cap(dir_cap)
    seed = author_seed if len(author_seed) == 32 else os.urandom(32)
    snap = _snapshot_cap(name, content_cap, seed, needed, total, servers)
    dmd = phone_dmd if directory_writable(phone_dmd) else ""
    if not dmd:
        for entry in _participant_entries(entries):
            cap = _writable_participant(entry, writekey)
            if cap:
                dmd = cap
                break
    child = _file_entry(name, snap, len(data))
    if dmd:
        _put_in_container(dmd, name, child, servers, needed, total)
    else:
        dmd = _publish_new_directory(pack_entries([child]), needed, total, servers)
    loaded = _load_entries(dir_cap, servers)
    fresh = _without_root_files(loaded)
    changed = len(fresh) != len(loaded)
    if not _participant_is_linked(fresh, writekey, dmd):
        fresh = _upsert(fresh, _dir_entry(_phone_dmd_name(fresh), dmd, writekey))
        changed = True
    if changed:
        _commit_entries(dir_cap, servers, needed, total, fresh)
    if not _read_back(dir_cap, name, data, content_cap, servers):
        raise WriteFail(ADD_FAIL, ADD_NEXT)
    return _landed(name, content_cap, len(data), seed, dmd)


def put_file(
    dir_cap: str,
    name: str,
    data: bytes,
    servers: list[StorageServer],
    shares: tuple[int, int, int],
    replace: bool = False,
    author_seed: bytes = b"",
    phone_dmd: str = "",
) -> dict[str, Any]:
    """Upload ``data`` into ``dir_cap`` and return only after a read-back."""
    if not directory_writable(dir_cap):
        raise WriteFail(RO_FAIL, RO_NEXT)
    name = _basename(name)
    needed, _happy, total = shares
    if needed < 1 or total < needed:
        needed, total = 1, 1
    try:
        listed = list_folder_view(dir_cap, servers)
    except ReadFail as exc:
        raise WriteFail(ADD_FAIL, exc.next_hint) from exc
    already = [row for row in listed if row.name == name]
    if already and not replace:
        for row in already:
            try:
                if download_file(row.cap, servers) == data:
                    return _landed(name, row.cap, len(data), author_seed, phone_dmd)
            except ReadFail:
                continue
        raise WriteFail(
            "A file named %s is already in this folder." % name,
            "Choose Replace, Keep both, or Cancel.",
        )
    try:
        content_cap = upload_immutable(data, needed, total, servers)
    except WriteFail:
        raise
    except OSError as exc:
        raise WriteFail(SPACE_FAIL if exc.errno == 28 else ADD_FAIL, SPACE_NEXT if exc.errno == 28 else ADD_NEXT) from exc
    entries = _load_entries(dir_cap, servers)
    if _is_collective(entries):
        return _place_in_collective(
            dir_cap,
            name,
            data,
            content_cap,
            servers,
            needed,
            total,
            author_seed,
            phone_dmd,
            entries,
        )
    _commit_entries(
        dir_cap,
        servers,
        needed,
        total,
        _upsert(entries, _file_entry(name, content_cap, len(data))),
    )
    if not _read_back(dir_cap, name, data, content_cap, servers):
        raise WriteFail(ADD_FAIL, ADD_NEXT)
    return _landed(name, content_cap, len(data), author_seed, phone_dmd)


def _read_back(
    dir_cap: str,
    name: str,
    data: bytes,
    content_cap: str,
    servers: list[StorageServer],
) -> bool:
    try:
        listed = list_folder_view(dir_cap, servers)
    except ReadFail:
        return False
    for row in listed:
        if row.name != name:
            continue
        try:
            if download_file(row.cap, servers) == data:
                return True
        except ReadFail:
            continue
    return False


def _landed(name: str, cap: str, size: int, seed: bytes, dmd: str) -> dict[str, Any]:
    return {
        "ok": True,
        "name": name,
        "cap": cap,
        "size": size,
        "author_seed_b64": _b64(seed) if seed else "",
        "phone_dmd": dmd or "",
    }


def remove_file(
    dir_cap: str,
    name: str,
    servers: list[StorageServer],
    shares: tuple[int, int, int],
    phone_dmd: str = "",
) -> dict[str, Any]:
    if not directory_writable(dir_cap):
        raise WriteFail(REMOVE_FAIL, REMOVE_NEXT)
    name = _basename(name)
    needed, _happy, total = shares
    entries = _load_entries(dir_cap, servers)
    removed = False
    if any(entry.name == name for entry in entries):
        _commit_entries(
            dir_cap,
            servers,
            needed,
            total,
            _drop(entries, name),
            REMOVE_FAIL,
            REMOVE_NEXT,
        )
        removed = True
    if phone_dmd and directory_writable(phone_dmd):
        inner = _load_entries(phone_dmd, servers)
        if any(entry.name == name for entry in inner):
            _commit_entries(
                phone_dmd,
                servers,
                needed,
                total,
                _drop(inner, name),
                REMOVE_FAIL,
                REMOVE_NEXT,
            )
            removed = True
    if not removed:
        raise WriteFail(REMOVE_FAIL, REMOVE_NEXT)
    try:
        listed = list_folder_view(dir_cap, servers)
    except ReadFail as exc:
        raise WriteFail(REMOVE_FAIL, exc.next_hint) from exc
    if any(row.name == name for row in listed):
        raise WriteFail(REMOVE_FAIL, REMOVE_NEXT)
    return {"ok": True, "name": name}


def shares_tuple(raw: Any) -> tuple[int, int, int]:
    if isinstance(raw, list) and len(raw) == 3:
        try:
            return int(raw[0]), int(raw[1]), int(raw[2])
        except (TypeError, ValueError):
            pass
    return (2, 3, 3)
