"""Read Tahoe-LAFS caps (CHK, LIT, SDMF directories) over the HTTP storage API.

Same capability strings desktop Leasegrid Sync stores in a U4 recovery key.
No Tahoe web UI. Slice A never uploads.
"""

from __future__ import annotations

import base64
import hashlib
import json
import socket
import ssl
import struct
from dataclasses import dataclass
from typing import Callable, Optional
from urllib.parse import unquote

from lg_fec import decode_blocks

UEB_TAG = b"allmydata_uri_extension_v1"
CIPHERTEXT_TAG = b"allmydata_crypttext_v1"
MUTABLE_READKEY_TAG = b"allmydata_mutable_writekey_to_readkey_v1"
MUTABLE_DATAKEY_TAG = b"allmydata_mutable_readkey_to_datakey_v1"
MUTABLE_STORAGEINDEX_TAG = b"allmydata_mutable_readkey_to_storage_index_v1"
MUTABLE_PUBKEY_TAG = b"allmydata_mutable_pubkey_to_fingerprint_v1"

HEADER_V1 = struct.Struct(">9L")  # 36 bytes
MUTABLE_HEADER = struct.Struct(">BQ32s16sBBQQLLLLQQ")


class ReadFail(Exception):
    def __init__(self, message: str, next_hint: str) -> None:
        super().__init__(message)
        self.message = message
        self.next_hint = next_hint


def _netstring(data: bytes) -> bytes:
    return b"%d:%s," % (len(data), data)


def _tagged_hash(tag: bytes, val: bytes, truncate: Optional[int] = None) -> bytes:
    h1 = hashlib.sha256(_netstring(tag) + val).digest()
    out = hashlib.sha256(h1).digest()
    return out if truncate is None else out[:truncate]


def _tagged_pair(tag: bytes, a: bytes, b: bytes, truncate: Optional[int] = None) -> bytes:
    h1 = hashlib.sha256(_netstring(tag) + _netstring(a) + _netstring(b)).digest()
    out = hashlib.sha256(h1).digest()
    return out if truncate is None else out[:truncate]


def b2a(data: bytes) -> str:
    return base64.b32encode(data).rstrip(b"=").decode("ascii").lower()


def a2b(text: str) -> bytes:
    cs = text.strip().encode("ascii").upper()
    while (len(cs) * 5) % 8 != 0:
        cs += b"="
    return base64.b32decode(cs)


def _split_netstrings(data: bytes, count: int, position: int = 0) -> tuple[list[bytes], int]:
    out: list[bytes] = []
    while len(out) < count:
        if position >= len(data):
            raise ReadFail(
                "could not read this folder. The directory bytes were cut short.",
                "Retry. If it repeats, the share may be corrupt.",
            )
        colon = data.index(b":", position)
        length = int(data[position:colon])
        start = colon + 1
        blob = data[start : start + length]
        if len(blob) != length or data[start + length : start + length + 1] != b",":
            raise ReadFail(
                "could not read this folder. The directory bytes were not a valid directory.",
                "Retry.",
            )
        out.append(blob)
        position = start + length + 1
    return out, position


def _aes_ctr(key: bytes, data: bytes) -> bytes:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    decryptor = Cipher(algorithms.AES(key), modes.CTR(b"\x00" * 16)).decryptor()
    return decryptor.update(data) + decryptor.finalize()


@dataclass
class StorageServer:
    furl: str
    nickname: str = ""

    def hints(self) -> tuple[str, list[tuple[str, int]], str]:
        return parse_storage_furl(self.furl)


def parse_storage_furl(furl: str) -> tuple[str, list[tuple[str, int]], str]:
    """Return (tubid, [(host, port), ...], swissnum) from a pb:// furl."""
    text = (furl or "").strip()
    if not text.startswith("pb://") or "/" not in text[5:]:
        raise ReadFail(
            "could not download this file. A storage server address was unreadable.",
            "Refresh folders, then Retry.",
        )
    body = text[5:]
    at = body.find("@")
    slash = body.rfind("/")
    if at < 0 or slash < at:
        raise ReadFail(
            "could not download this file. A storage server address was unreadable.",
            "Refresh folders, then Retry.",
        )
    tubid = body[:at][:32]
    hints_s = body[at + 1 : slash]
    swiss = body[slash + 1 :]
    # Fragment is not part of the swissnum (NURLs use #v=1).
    swiss = swiss.split("#", 1)[0]
    hosts: list[tuple[str, int]] = []
    for hint in hints_s.split(","):
        hint = unquote(hint).strip()
        if hint.startswith("tcp:"):
            hint = hint[4:]
        if hint.startswith("["):
            end = hint.find("]")
            host = hint[1:end]
            port_s = hint[end + 1 :].lstrip(":")
        else:
            if ":" not in hint:
                continue
            host, port_s = hint.rsplit(":", 1)
        try:
            hosts.append((host, int(port_s)))
        except ValueError:
            continue
    if not hosts or not swiss:
        raise ReadFail(
            "could not download this file. A storage server address was unreadable.",
            "Refresh folders, then Retry.",
        )
    return tubid, hosts, swiss


def _host_candidates(host: str) -> list[str]:
    loop = {"127.0.0.1", "localhost", "::1"}
    if host in loop:
        return [host, "10.0.2.2"]
    if host == "10.0.2.2":
        return [host, "127.0.0.1"]
    return [host]


def _cert_tubid(der: bytes) -> str:
    return b2a(hashlib.sha1(der).digest())


def _http_get(host: str, port: int, tubid: str, path: str, swiss: str, timeout: float) -> bytes:
    auth = base64.b64encode(swiss.encode("ascii")).decode("ascii")
    # Open-ended Range is rejected (416) by Tahoe 1.20. The whole share is the read.
    request = (
        "GET %s HTTP/1.1\r\n"
        "Host: %s\r\n"
        "Authorization: Tahoe-LAFS %s\r\n"
        "Accept: application/octet-stream\r\n"
        "Connection: close\r\n\r\n" % (path, host, auth)
    ).encode("ascii")
    last: Optional[Exception] = None
    for use_host in _host_candidates(host):
        try:
            raw = socket.create_connection((use_host, port), timeout=timeout)
        except OSError as exc:
            last = exc
            continue
        try:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            ssock = ctx.wrap_socket(raw, server_hostname=use_host)
            der = ssock.getpeercert(binary_form=True)
            if der and _cert_tubid(der) != tubid.lower():
                ssock.close()
                last = ReadFail(
                    "could not download this file. Storage server identity did not match.",
                    "Refresh folders, then Retry.",
                )
                continue
            ssock.sendall(request)
            chunks = []
            while True:
                block = ssock.recv(65536)
                if not block:
                    break
                chunks.append(block)
            ssock.close()
            # A real HTTP answer means this host is the server. Do not fall
            # through to the emulator alias after a protocol response.
            return _http_body(b"".join(chunks))
        except ReadFail:
            raise
        except (OSError, ssl.SSLError) as exc:
            last = exc
            try:
                raw.close()
            except OSError:
                pass
    if isinstance(last, ReadFail):
        raise last
    raise ReadFail(
        "could not download this file. Network error or not enough free space.",
        "check network / free space; Retry.",
    )


def _http_body(raw: bytes) -> bytes:
    head, _, rest = raw.partition(b"\r\n\r\n")
    if not head:
        raise ReadFail(
            "could not download this file. The storage server returned nothing.",
            "check network; Retry.",
        )
    line = head.split(b"\r\n", 1)[0]
    parts = line.split(b" ")
    code = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    if code in (401, 403):
        raise ReadFail(
            "could not download this file. The storage server refused the read.",
            "Refresh folders, then Retry.",
        )
    if code == 404:
        raise ReadFail(
            "could not download this file. This share is not on that server.",
            "Retry.",
        )
    if code not in (200, 206):
        raise ReadFail(
            "could not download this file. The storage server returned an error.",
            "check network; Retry.",
        )
    headers = {}
    for row in head.split(b"\r\n")[1:]:
        if b":" in row:
            k, v = row.split(b":", 1)
            headers[k.strip().lower()] = v.strip()
    if headers.get(b"transfer-encoding", b"").lower() == b"chunked":
        return _unchunk(rest)
    length = headers.get(b"content-length")
    if length and length.isdigit():
        return rest[: int(length)]
    return rest


def _unchunk(data: bytes) -> bytes:
    out = bytearray()
    pos = 0
    while pos < len(data):
        line_end = data.find(b"\r\n", pos)
        if line_end < 0:
            break
        size = int(data[pos:line_end].split(b";", 1)[0], 16)
        if size == 0:
            break
        start = line_end + 2
        out += data[start : start + size]
        pos = start + size + 2
    return bytes(out)


def fetch_share(
    servers: list[StorageServer],
    kind: str,
    storage_index: bytes,
    sharenum: int,
    timeout: float = 20.0,
) -> bytes:
    si = b2a(storage_index)
    path = "/storage/v1/%s/%s/%d" % (kind, si, sharenum)
    errors: list[str] = []
    for server in servers:
        try:
            tubid, hosts, swiss = server.hints()
        except ReadFail as exc:
            errors.append(exc.message)
            continue
        for host, port in hosts:
            try:
                return _http_get(host, port, tubid, path, swiss, timeout)
            except ReadFail as exc:
                errors.append(exc.message)
    hint = errors[-1] if errors else "no storage servers"
    raise ReadFail(
        "could not download this file. Network error or not enough free space.",
        "check network / free space; Retry. (%s)" % hint,
    )


@dataclass
class Child:
    name: str
    kind: str  # file | dir
    cap: str
    size: int = 0


def _parse_chk_body(body: str) -> tuple[bytes, bytes, int, int, int]:
    parts = body.split(":")
    if len(parts) != 5:
        raise ReadFail(
            "could not download this file. The capability is not a readable file.",
            "Retry.",
        )
    key, ueb, needed, total, size = parts
    return a2b(key), a2b(ueb), int(needed), int(total), int(size)


def read_chk(body: str, servers: list[StorageServer], progress: Optional[Callable[[int], None]] = None) -> bytes:
    key, ueb_hash, needed, total, size = _parse_chk_body(body)
    si = _tagged_hash(b"allmydata_immutable_key_to_storage_index_v1", key, 16)
    shares: list[tuple[int, bytes]] = []
    errors: list[str] = []
    for num in range(total):
        try:
            blob = fetch_share(servers, "immutable", si, num)
        except ReadFail as exc:
            errors.append(exc.message)
            continue
        shares.append((num, blob))
        if progress:
            progress(min(70, int(40 * len(shares) / max(needed, 1))))
        if len(shares) >= needed:
            break
    if len(shares) < needed:
        raise ReadFail(
            "could not download this file. Network error or not enough free space.",
            "check network / free space; Retry.",
        )
    plain = _decode_chk_shares(key, ueb_hash, needed, total, size, shares)
    if progress:
        progress(100)
    return plain


def _decode_chk_shares(
    key: bytes,
    ueb_hash: bytes,
    needed: int,
    total: int,
    size: int,
    shares: list[tuple[int, bytes]],
) -> bytes:
    parsed = []
    ueb = b""
    for num, blob in shares:
        if len(blob) < 36:
            continue
        version = struct.unpack(">L", blob[:4])[0]
        if version != 1:
            continue
        fields = HEADER_V1.unpack(blob[:36])
        block_size, data_size = fields[1], fields[2]
        off_data = fields[3]
        off_ueb = fields[8]
        if off_ueb + 4 > len(blob):
            continue
        ueb_len = struct.unpack(">L", blob[off_ueb : off_ueb + 4])[0]
        ueb_bytes = blob[off_ueb + 4 : off_ueb + 4 + ueb_len]
        digest = _tagged_hash(UEB_TAG, ueb_bytes)
        if digest != ueb_hash:
            continue
        block = blob[off_data : off_data + data_size]
        if block_size and len(block) > block_size:
            # One-segment files store a single block of data_size.
            block = block[:data_size]
        parsed.append((num, block))
        ueb = ueb_bytes
    if len(parsed) < needed or not ueb:
        raise ReadFail(
            "could not download this file. The shares did not match this capability.",
            "Retry.",
        )
    info = _unpack_ueb(ueb)
    segment_size = int(info.get("segment_size") or 0)
    num_segments = int(info.get("num_segments") or 1)
    if segment_size <= 0 or num_segments <= 0:
        raise ReadFail(
            "could not download this file. The capability extension was unreadable.",
            "Retry.",
        )
    block_size = segment_size // needed
    tail = size % segment_size or segment_size
    padded_tail = tail + ((needed - (tail % needed)) % needed)
    tail_block = padded_tail // needed
    # Slice each share into per-segment blocks.
    per_seg: list[list[tuple[int, bytes]]] = [[] for _ in range(num_segments)]
    for num, data in parsed[:needed]:
        pos = 0
        for seg in range(num_segments):
            blen = tail_block if seg == num_segments - 1 else block_size
            per_seg[seg].append((num, data[pos : pos + blen]))
            pos += blen
    crypt_parts = []
    for seg, parts in enumerate(per_seg):
        blocks = decode_blocks(needed, total, parts)
        segment = b"".join(blocks)
        use = tail if seg == num_segments - 1 else segment_size
        crypt_parts.append(segment[:use])
    crypt = b"".join(crypt_parts)[:size]
    expect = info.get("crypttext_hash")
    if expect is not None and _tagged_hash(CIPHERTEXT_TAG, crypt) != expect:
        raise ReadFail(
            "could not download this file. The bytes failed an integrity check.",
            "Retry.",
        )
    return _aes_ctr(key, crypt)


def _unpack_ueb(data: bytes) -> dict[str, bytes]:
    """URI extension: ``key:`` + netstring(value), keys sorted, not a pair of netstrings."""
    out: dict[str, bytes] = {}
    while data:
        colon = data.index(b":")
        key = data[:colon].decode("utf-8")
        data = data[colon + 1 :]
        colon = data.index(b":")
        length = int(data[:colon])
        data = data[colon + 1 :]
        value = data[:length]
        if data[length : length + 1] != b",":
            raise ReadFail(
                "could not download this file. The capability extension was unreadable.",
                "Retry.",
            )
        data = data[length + 1 :]
        out[key] = value
    for intkey in ("size", "segment_size", "num_segments", "needed_shares", "total_shares"):
        if intkey in out:
            out[intkey] = int(out[intkey])  # type: ignore[assignment]
    return out


def _readkey_from_dir_cap(cap: str) -> tuple[bytes, bytes]:
    """Return (readkey, fingerprint) for a DIR2 / DIR2-RO / SSK cap."""
    if cap.startswith("URI:DIR2-RO:"):
        body = cap[len("URI:DIR2-RO:") :]
    elif cap.startswith("URI:SSK-RO:"):
        body = cap[len("URI:SSK-RO:") :]
    elif cap.startswith("URI:DIR2:"):
        body = cap[len("URI:DIR2:") :]
        write_b32, fp_b32 = body.split(":", 1)
        writekey = a2b(write_b32)
        readkey = _tagged_hash(MUTABLE_READKEY_TAG, writekey, 16)
        return readkey, a2b(fp_b32)
    elif cap.startswith("URI:SSK:"):
        body = cap[len("URI:SSK:") :]
        write_b32, fp_b32 = body.split(":", 1)
        writekey = a2b(write_b32)
        readkey = _tagged_hash(MUTABLE_READKEY_TAG, writekey, 16)
        return readkey, a2b(fp_b32)
    else:
        raise ReadFail(
            "could not load folders. This capability is not a folder this phone can read.",
            "Retry.",
        )
    read_b32, fp_b32 = body.split(":", 1)
    return a2b(read_b32), a2b(fp_b32)


def read_sdmf(cap: str, servers: list[StorageServer]) -> bytes:
    readkey, fingerprint = _readkey_from_dir_cap(cap)
    si = _tagged_hash(MUTABLE_STORAGEINDEX_TAG, readkey, 16)
    # k and N live in the share; try the first handful of share numbers.
    got: list[tuple[int, bytes]] = []
    for num in range(16):
        try:
            blob = fetch_share(servers, "mutable", si, num)
        except ReadFail:
            continue
        if len(blob) >= MUTABLE_HEADER.size:
            got.append((num, blob))
        if len(got) >= 3:
            # May still need more; decode will say.
            break
    if not got:
        raise ReadFail(
            "could not load folders. Network error talking to storage.",
            "check network; Retry.",
        )
    return _decode_sdmf(readkey, fingerprint, got)


def _decode_sdmf(readkey: bytes, fingerprint: bytes, shares: list[tuple[int, bytes]]) -> bytes:
    parsed = []
    k = n = segsize = datalen = 0
    salt = b""
    for num, blob in shares:
        if len(blob) < MUTABLE_HEADER.size:
            continue
        fields = MUTABLE_HEADER.unpack_from(blob, 0)
        version = fields[0]
        if version != 0:
            continue
        salt = fields[3]
        k, n = fields[4], fields[5]
        segsize, datalen = fields[6], fields[7]
        off_sig, off_hash, off_block, off_data, off_priv, eof = fields[8:]
        pubkey = blob[MUTABLE_HEADER.size : off_sig]
        fp = _tagged_hash(MUTABLE_PUBKEY_TAG, pubkey)
        if fp != fingerprint:
            continue
        block = blob[off_data:off_priv]
        parsed.append((num, block))
    if not parsed or k <= 0:
        raise ReadFail(
            "could not load folders. The folder shares did not match this capability.",
            "Retry.",
        )
    if len(parsed) < k:
        raise ReadFail(
            "could not load folders. Not enough shares are reachable.",
            "check network; Retry.",
        )
    tail = datalen % segsize or segsize if segsize else datalen
    if not segsize:
        tail = datalen
    padded = tail + ((k - (tail % k)) % k) if k else tail
    blocks = decode_blocks(k, n, [(num, block[: padded // k]) for num, block in parsed[:k]])
    segment = b"".join(blocks)[:tail]
    # SDMF is a single segment; datalen is the plaintext/crypttext length.
    segment = segment[:datalen] if datalen else segment
    key = _tagged_pair(MUTABLE_DATAKEY_TAG, salt, readkey, 16)
    return _aes_ctr(key, segment)


def _normalize_cap(raw: bytes) -> str:
    text = raw.rstrip(b" ").decode("utf-8", errors="replace")
    for prefix in ("imm.", "ro."):
        if text.startswith(prefix):
            text = text[len(prefix) :]
            break
    if text and not text.startswith("URI:") and ":" in text:
        text = "URI:" + text
    return text


def unpack_directory(data: bytes) -> list[Child]:
    if data == b"":
        return []
    children: list[Child] = []
    pos = 0
    while pos < len(data):
        (entry,), pos = _split_netstrings(data, 1, pos)
        fields, _ = _split_netstrings(entry, 4, 0)
        name = fields[0].decode("utf-8")
        ro = _normalize_cap(fields[1])
        meta = {}
        try:
            meta = json.loads(fields[3].decode("utf-8") or "{}")
        except json.JSONDecodeError:
            meta = {}
        size = 0
        if isinstance(meta, dict):
            tahoe = meta.get("tahoe") if isinstance(meta.get("tahoe"), dict) else {}
            if isinstance(tahoe, dict) and isinstance(tahoe.get("size"), int):
                size = tahoe["size"]
        kind = "dir" if ro.startswith("URI:DIR2") else "file"
        if ro.startswith("URI:CHK:"):
            try:
                size = int(ro.rsplit(":", 1)[-1])
            except ValueError:
                pass
        if ro.startswith("URI:LIT:"):
            try:
                size = len(a2b(ro[len("URI:LIT:") :]))
            except Exception:
                size = 0
        children.append(Child(name=name, kind=kind, cap=ro, size=size))
    return children


def read_literal(body: str) -> bytes:
    return a2b(body)


def download_file(cap: str, servers: list[StorageServer], progress: Optional[Callable[[int], None]] = None) -> bytes:
    cap = cap.strip()
    if cap.startswith("URI:LIT:"):
        data = read_literal(cap[len("URI:LIT:") :])
        if progress:
            progress(100)
        return data
    if cap.startswith("URI:CHK:"):
        return read_chk(cap[len("URI:CHK:") :], servers, progress)
    if cap.startswith("URI:DIR2-CHK:"):
        return read_chk(cap[len("URI:DIR2-CHK:") :], servers, progress)
    if cap.startswith("URI:DIR2-LIT:"):
        return read_literal(cap[len("URI:DIR2-LIT:") :])
    if cap.startswith("URI:SSK") or cap.startswith("URI:DIR2"):
        return read_sdmf(cap, servers)
    raise ReadFail(
        "could not download this file. This phone cannot read that capability.",
        "Retry.",
    )


def list_directory(cap: str, servers: list[StorageServer]) -> list[Child]:
    data = download_file(cap, servers)
    # Immutable CHK directory bytes are a packed directory, not a file the
    # operator named. Mutable DIR2 plaintext is the same packing.
    if cap.startswith("URI:DIR2") or cap.startswith("URI:SSK"):
        return unpack_directory(data)
    raise ReadFail(
        "could not load folders. That is a file, not a folder.",
        "Open it with Download.",
    )


def list_folder_view(cap: str, servers: list[StorageServer]) -> list[Child]:
    """Buyer-facing listing.

    Magic Folder collectives are directories of participant directories, and a
    snapshot directory holds the bytes under a child named ``content``. Flatten
    one level of participant dirs, and present snapshot dirs as files.
    """
    children = list_directory(cap, servers)
    files = [c for c in children if c.kind == "file"]
    dirs = [c for c in children if c.kind == "dir"]
    if files:
        return _snapshots_as_files(files, dirs, servers)
    flattened: list[Child] = []
    for entry in dirs:
        try:
            inner = list_directory(entry.cap, servers)
        except ReadFail:
            flattened.append(entry)
            continue
        inner_files = [c for c in inner if c.kind == "file"]
        inner_dirs = [c for c in inner if c.kind == "dir"]
        if _looks_like_snapshot(inner):
            content = _content_child(inner)
            if content is not None:
                flattened.append(Child(entry.name, "file", content.cap, content.size))
                continue
        if inner_files or not inner_dirs:
            flattened.extend(_snapshots_as_files(inner_files, inner_dirs, servers))
        else:
            flattened.append(entry)
    return flattened or dirs


def _looks_like_snapshot(children: list[Child]) -> bool:
    names = {c.name for c in children}
    return "content" in names and "metadata" in names


def _content_child(children: list[Child]) -> Optional[Child]:
    for child in children:
        if child.name == "content" and child.kind == "file":
            return child
    return None


def _snapshots_as_files(files: list[Child], dirs: list[Child], servers: list[StorageServer]) -> list[Child]:
    out = list(files)
    for entry in dirs:
        try:
            inner = list_directory(entry.cap, servers)
        except ReadFail:
            out.append(entry)
            continue
        if _looks_like_snapshot(inner):
            content = _content_child(inner)
            if content is not None:
                out.append(Child(entry.name.rstrip("/"), "file", content.cap, content.size))
                continue
        out.append(entry)
    return out
