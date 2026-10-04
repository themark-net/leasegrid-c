"""A phone add must land where an existing Magic Folder downloads it.

Magic Folder polls the collective, skips ``@metadata``, skips its own
participant, and downloads snapshot directories from every other
participant. A raw CHK on the collective root is not that, and it aborts
the poll. This test fails if ``put_file`` still writes one.
"""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "app/src/main/python"
sys.path.insert(0, str(ROOT))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey  # noqa: E402
from lg_cbor import dumps, loads  # noqa: E402
from lg_tahoe import ReadFail, StorageServer, b2a, download_file, list_folder_view  # noqa: E402
from lg_write import (  # noqa: E402
    DirEntry,
    _commit_entries,
    _dir_entry,
    _is_mutable_dir,
    _load_entries,
    _parse_write_cap,
    _publish_new_directory,
    pack_entries,
    put_file,
    readonly_dir_cap,
    unpack_entries,
)

PAYLOAD = b"phone-add-lands-in-a-watched-dmd\n"
assert len(PAYLOAD) == 33


class _Grid:
    """In-memory Tahoe HTTP storage. Enough for one-share put and read-back."""

    def __init__(self) -> None:
        self.imm: dict[tuple[str, int], bytes] = {}
        self.mut: dict[tuple[str, int], bytes] = {}

    def http_get(self, host, port, tubid, path, swiss, timeout):
        code, body = self._handle("GET", path, b"")
        if code == 404:
            raise ReadFail("missing share", "Retry.")
        if code not in (200, 206) or not body:
            raise ReadFail("storage error", "Retry.")
        return body

    def http_storage(
        self,
        host,
        port,
        tubid,
        method,
        path,
        swiss,
        body=b"",
        extra_headers=None,
        timeout=60.0,
        fail_message="",
        fail_next="",
    ):
        return self._handle(method, path, body)

    def _handle(self, method: str, path: str, body: bytes) -> tuple[int, bytes]:
        parts = [part for part in path.split("/") if part]
        if len(parts) < 4 or parts[0] != "storage" or parts[1] != "v1":
            return 404, b""
        kind, si = parts[2], parts[3]
        store = self.imm if kind == "immutable" else self.mut
        if method == "GET":
            blob = store.get((si, int(parts[4])))
            if blob is None:
                return 404, b""
            return 200, blob
        if kind == "immutable" and method == "POST":
            msg = loads(body)
            nums = msg.get("share-numbers") or set()
            return 200, dumps({"already-have": set(), "allocated": set(int(n) for n in nums)})
        if kind == "immutable" and method == "PATCH":
            store[(si, int(parts[4]))] = body
            return 200, b""
        if kind == "mutable" and method == "POST" and len(parts) >= 5 and parts[4] == "read-test-write":
            msg = loads(body)
            vectors = msg.get("test-write-vectors") or {}
            for key, spec in vectors.items():
                num = int(key)
                current = store.get((si, num), b"")
                for test in spec.get("test") or []:
                    off = int(test.get("offset") or 0)
                    size = int(test.get("size") or 0)
                    specimen = test.get("specimen") or b""
                    if isinstance(specimen, str):
                        specimen = specimen.encode("utf-8")
                    have = current[off : off + size] if current else b""
                    if have != specimen:
                        return 200, dumps({"success": False})
                buf = bytearray(current)
                for write in spec.get("write") or []:
                    off = int(write.get("offset") or 0)
                    data = write.get("data") or b""
                    if isinstance(data, str):
                        data = data.encode("utf-8")
                    end = off + len(data)
                    if len(buf) < end:
                        buf.extend(b"\x00" * (end - len(buf)))
                    buf[off:end] = data
                new_len = spec.get("new-length")
                if isinstance(new_len, int) and new_len >= 0:
                    if new_len < len(buf):
                        buf = buf[:new_len]
                    elif new_len > len(buf):
                        buf.extend(b"\x00" * (new_len - len(buf)))
                store[(si, num)] = bytes(buf)
            return 200, dumps({"success": True})
        return 400, b""


def _server() -> StorageServer:
    tub = b2a(b"\x11" * 20)
    return StorageServer("pb://%s@127.0.0.1:1/swissnum" % tub)


def _use(monkeypatch) -> tuple[_Grid, list[StorageServer]]:
    grid = _Grid()
    import lg_tahoe
    import lg_write

    monkeypatch.setattr(lg_tahoe, "_http_get", grid.http_get)
    monkeypatch.setattr(lg_write, "http_storage", grid.http_storage)
    return grid, [_server()]


def _lit(data: bytes) -> str:
    return "URI:LIT:" + b2a(data)


def _metadata() -> DirEntry:
    return DirEntry(
        name="@metadata",
        ro=_lit(b'{"version":1}'),
        rw=b"",
        meta={},
        dirty=True,
    )


def _snapshot_bytes(cap: str, servers: list[StorageServer]) -> tuple[str, bytes]:
    """Return ``(relpath, content)`` for one Magic Folder snapshot directory."""
    if not cap.startswith("URI:DIR2-CHK:"):
        raise AssertionError("snapshot is not an immutable directory")
    kids = {entry.name: entry for entry in unpack_entries(download_file(cap, servers))}
    if "content" not in kids or "metadata" not in kids:
        raise AssertionError("snapshot is missing content or metadata")
    meta = json.loads(download_file(kids["metadata"].ro, servers))
    signature = kids["metadata"].meta["magic_folder"]["author_signature"]
    relpath = meta["relpath"]
    signed = (
        "magic-folder-snapshot-v1\n%s\n%s\n%s\n" % (kids["content"].ro, kids["metadata"].ro, relpath)
    ).encode("utf-8")
    Ed25519PublicKey.from_public_bytes(base64.b64decode(meta["author"]["verify_key"])).verify(
        base64.b64decode(signature),
        signed,
    )
    if meta.get("snapshot_version") != 1:
        raise AssertionError("snapshot_version")
    return relpath, download_file(kids["content"].ro, servers)


def _downloaded(entries: list[DirEntry], self_ro: str, servers: list[StorageServer]) -> dict[str, bytes]:
    """What the running Photos Magic Folder would fetch.

    ``@metadata`` is skipped. The participant whose read cap is the desktop
    upload directory is self and is skipped. Any other non-directory child
    aborts the poll, which is why a raw CHK on the collective root never
    arrives in ``~/Leasegrid/Photos``.
    """
    found: dict[str, bytes] = {}
    for entry in entries:
        if entry.name == "@metadata":
            continue
        if not _is_mutable_dir(entry.ro):
            raise AssertionError("poll aborts on %s (%s)" % (entry.name, entry.ro.split(":")[1]))
        if entry.ro == self_ro:
            continue
        for child in _load_entries(entry.ro, servers):
            if child.name == "@metadata":
                continue
            relpath, content = _snapshot_bytes(child.ro, servers)
            found[relpath] = content
    return found


def test_plain_folder_still_stores_a_direct_file(monkeypatch):
    _grid, servers = _use(monkeypatch)
    folder = _publish_new_directory(b"", 1, 1, servers)
    landed = put_file(folder, "note.txt", b"abc", servers, (1, 1, 1))
    assert landed["ok"] is True
    kids = {entry.name: entry for entry in _load_entries(folder, servers)}
    assert kids["note.txt"].ro.startswith("URI:CHK:")
    assert download_file(kids["note.txt"].ro, servers) == b"abc"


def test_mixed_folder_is_not_treated_as_a_collective(monkeypatch):
    """A folder with a file and a subdirectory is not a Magic Folder collective."""
    _grid, servers = _use(monkeypatch)
    parent = _publish_new_directory(b"", 1, 1, servers)
    child = _publish_new_directory(b"", 1, 1, servers)
    writekey, _fp = _parse_write_cap(parent)
    _commit_entries(
        parent,
        servers,
        1,
        1,
        [
            DirEntry(name="already.txt", ro=_lit(b"old"), rw=b"", meta={}, dirty=True),
            _dir_entry("subdir", child, writekey),
        ],
    )
    put_file(parent, "another.txt", b"zzz", servers, (1, 1, 1))
    names = {entry.name: entry.ro for entry in _load_entries(parent, servers)}
    assert names["another.txt"].startswith("URI:CHK:")
    assert "phone" not in names


def test_phone_add_is_not_a_raw_chk_on_the_collective_root(monkeypatch):
    """Photos shape: ``@metadata`` + read-only ``mark`` (the desktop's own DMD).

    ``mark`` has no write cap in the collective, and Magic Folder will not
    download it. The add has to become a snapshot in some other participant
    directory. A CHK named like the file on the collective root fails this.
    """
    _grid, servers = _use(monkeypatch)
    mark = _publish_new_directory(pack_entries([_metadata()]), 1, 1, servers)
    mark_ro = readonly_dir_cap(mark)
    stray = DirEntry(
        name="lg44-live.txt",
        ro="URI:CHK:aaaaaaaaaaaaaaaaaaaaaaaa:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb:1:1:33",
        rw=b"",
        meta={"tahoe": {"size": 33}},
        dirty=True,
    )
    collective = _publish_new_directory(
        pack_entries(
            [
                _metadata(),
                DirEntry(name="mark", ro=mark_ro, rw=b"", meta={}, dirty=True),
                stray,
            ]
        ),
        1,
        1,
        servers,
    )
    landed = put_file(collective, "lg46-lab.txt", PAYLOAD, servers, (1, 1, 1))
    assert landed["ok"] is True
    entries = _load_entries(collective, servers)
    root = {entry.name: entry for entry in entries}
    assert "lg46-lab.txt" not in root
    assert "lg44-live.txt" not in root
    assert "@metadata" in root
    assert root["mark"].ro == mark_ro
    mark_names = [entry.name for entry in _load_entries(mark_ro, servers)]
    assert mark_names == ["@metadata"]
    others = [entry for entry in entries if entry.name not in ("@metadata", "mark")]
    assert len(others) == 1
    assert _is_mutable_dir(others[0].ro)
    downloaded = _downloaded(entries, mark_ro, servers)
    assert downloaded == {"lg46-lab.txt": PAYLOAD}
    visible = {row.name for row in list_folder_view(collective, servers)}
    assert "lg46-lab.txt" in visible
    assert "@metadata" not in visible
    assert "mark" not in visible

    again = put_file(
        collective,
        "second.txt",
        b"second file from the phone\n",
        servers,
        (1, 1, 1),
        phone_dmd=landed["phone_dmd"],
    )
    assert again["ok"] is True
    entries = _load_entries(collective, servers)
    others = [entry for entry in entries if entry.name not in ("@metadata", "mark")]
    assert len(others) == 1
    assert _downloaded(entries, mark_ro, servers)["second.txt"] == b"second file from the phone\n"

    # The linked participant is writable by this phone. A later add must
    # reuse it even when the app does not pass the cap back.
    third = put_file(collective, "third.txt", b"third\n", servers, (1, 1, 1))
    assert third["ok"] is True
    entries = _load_entries(collective, servers)
    others = [entry for entry in entries if entry.name not in ("@metadata", "mark")]
    assert len(others) == 1
    assert third["phone_dmd"] == landed["phone_dmd"]
