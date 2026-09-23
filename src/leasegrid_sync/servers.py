"""Storage servers this Sync home uses (buyer roster, not Tahoe WUI).

Pins live in ``<home>/servers.json``. Pasted storage furls are also written to
``<nodedir>/private/servers.yaml`` so Tahoe can connect without the introducer.
Disconnect forgets that local pin only — the friendnet may announce the server again.
"""

from __future__ import annotations

import hashlib
import json
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .backend import SyncError

ADD_FAIL = (
    "could not add this storage server. Link looks wrong or the server is unreachable."
)
ADD_FAIL_NEXT = "Check the link and Retry."
UNREACHABLE = "could not add this storage server. The server is unreachable."
UNREACHABLE_NEXT = "Retry / check the host."
SEEN_AGAIN_NOTE = (
    "You disconnected this server earlier. Not used until you Add."
)
SERVERS_HONESTY = (
    "Disconnect removes a server from this home only. "
    "It does not eject it from the friendnet for everyone."
)
STATIC_MARKER = "# leasegrid-sync storage pins"


@dataclass
class ServerRow:
    key: str
    name: str
    status: str
    source: str
    section: str  # used | available
    furl: str = ""
    note: str = ""


def disconnect_copy(name: str) -> str:
    """Honest local-only Disconnect. No forever-remove claim."""
    who = name.strip() or "this storage server"
    return (
        'Disconnect "%s" from this Sync home?\n\n'
        "This will:\n"
        "• Stop preferring it for new files on this home\n"
        "• Forget it from your local server list\n\n"
        "This will not:\n"
        "• Remove it from the friendnet for everyone\n"
        "• Delete shares already stored on that computer\n\n"
        "If the friendnet announces it again, it may show under "
        "Available — you can Disconnect again or leave unused."
    ) % who


def servers_path(home: Path) -> Path:
    return Path(home) / "servers.json"


def _empty_book() -> dict:
    return {"version": 1, "pins": [], "forgotten": [], "archive": []}


def load_book(home: Path) -> dict:
    path = servers_path(home)
    if not path.is_file():
        return _empty_book()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SyncError(
            "could not read storage servers. The local server list is unreadable.",
            "Retry.",
        ) from exc
    if not isinstance(data, dict):
        raise SyncError(
            "could not read storage servers. The local server list is unreadable.",
            "Retry.",
        )
    pins = [p for p in (data.get("pins") or []) if isinstance(p, dict)]
    forgotten = [str(t) for t in (data.get("forgotten") or []) if str(t).strip()]
    archive = [p for p in (data.get("archive") or []) if isinstance(p, dict)]
    return {"version": 1, "pins": pins, "forgotten": forgotten, "archive": archive}


def save_book(home: Path, book: dict) -> None:
    path = servers_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "pins": list(book.get("pins") or []),
        "forgotten": list(book.get("forgotten") or []),
        "archive": list(book.get("archive") or []),
    }
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def _fail_bad() -> SyncError:
    return SyncError(ADD_FAIL, ADD_FAIL_NEXT)


def parse_storage_furl(raw: str) -> tuple[str, list[tuple[str, int]], str]:
    """Return ``(tubid, [(host, port), ...], swissnum)`` or raise SyncError."""
    text = (raw or "").strip()
    if not text or not text.startswith("pb://") or any(ch.isspace() for ch in text):
        raise _fail_bad()
    body = text[5:]
    at = body.find("@")
    slash = body.rfind("/")
    if at <= 0 or slash <= at + 1 or slash == len(body) - 1:
        raise _fail_bad()
    tubid = body[:at]
    swiss = body[slash + 1 :].split("#", 1)[0]
    if not tubid or not swiss or len(tubid) < 4:
        raise _fail_bad()
    hints: list[tuple[str, int]] = []
    for hint in body[at + 1 : slash].split(","):
        hint = hint.strip()
        if hint.startswith("tcp:"):
            hint = hint[4:]
        if hint.startswith("["):
            end = hint.find("]")
            if end < 0 or ":" not in hint[end:]:
                continue
            host = hint[1:end]
            port_s = hint[end + 1 :].lstrip(":")
        else:
            if ":" not in hint:
                continue
            host, port_s = hint.rsplit(":", 1)
        try:
            port = int(port_s)
        except ValueError:
            continue
        if not host or not (1 <= port <= 65535):
            continue
        hints.append((host, port))
    if not hints:
        raise _fail_bad()
    return tubid, hints, swiss


def probe_storage_furl(raw: str, timeout: float = 2.0) -> None:
    """TCP-check the furl. Malformed links fail before any connect."""
    _tubid, hints, _swiss = parse_storage_furl(raw)
    for host, port in hints:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return
        except OSError:
            continue
    raise SyncError(UNREACHABLE, UNREACHABLE_NEXT)


def _pin_key(furl: str) -> str:
    digest = hashlib.sha256(furl.encode("utf-8")).hexdigest()[:20]
    return "pin-" + digest


def _source_label(source: str) -> str:
    if source == "invite":
        return "Via invite/Offer"
    if source == "added":
        return "Added by you"
    return "Announced"


def _drop_tokens(forgotten: list[str], tokens: list[str]) -> list[str]:
    ban = {t.lower() for t in tokens if t}
    return [t for t in forgotten if t.lower() not in ban]


def _remember(forgotten: list[str], tokens: list[str]) -> None:
    have = {t.lower() for t in forgotten}
    for token in tokens:
        if token and token.lower() not in have:
            forgotten.append(token)
            have.add(token.lower())


def write_static_servers(nodedir: Path, pins: list[dict]) -> None:
    """Rewrite Sync-owned ``private/servers.yaml``. Leave a hand-written file alone."""
    nodedir = Path(nodedir)
    if not (nodedir / "tahoe.cfg").is_file():
        return
    path = nodedir / "private" / "servers.yaml"
    if path.is_file():
        existing = path.read_text(encoding="utf-8")
        if existing.strip() and not existing.startswith(STATIC_MARKER):
            return
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [STATIC_MARKER, "storage:"]
    wrote = False
    for pin in pins:
        furl = str(pin.get("furl") or "")
        if not furl.startswith("pb://"):
            continue
        wrote = True
        lines.append("  %s:" % pin.get("key"))
        lines.append("    ann:")
        lines.append("      nickname: %s" % json.dumps(str(pin.get("name") or "storage")))
        lines.append("      anonymous-storage-FURL: %s" % json.dumps(furl))
    if not wrote:
        lines = [STATIC_MARKER, "storage: {}"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def add_storage_server(
    home: Path,
    nodedir: Path,
    furl: str,
    nickname: str = "",
    timeout: float = 2.0,
) -> ServerRow:
    """Validate, probe, remember, and prefer this storage furl on this home."""
    text = (furl or "").strip()
    tubid, hints, _swiss = parse_storage_furl(text)
    probe_storage_furl(text, timeout=timeout)
    name = " ".join((nickname or "").split()) or hints[0][0]
    if len(name) > 80:
        name = name[:80]
    key = _pin_key(text)
    book = load_book(home)
    book["forgotten"] = _drop_tokens(
        book["forgotten"], [key, name, tubid, text]
    )
    book["archive"] = [
        item
        for item in book["archive"]
        if item.get("key") != key and item.get("furl") != text
    ]
    pin = {
        "key": key,
        "name": name,
        "furl": text,
        "tubid": tubid,
        "source": "added",
    }
    replaced = False
    pins: list[dict] = []
    for item in book["pins"]:
        if item.get("key") == key or item.get("furl") == text:
            pins.append(pin)
            replaced = True
        else:
            pins.append(item)
    if not replaced:
        pins.append(pin)
    book["pins"] = pins
    save_book(home, book)
    write_static_servers(nodedir, pins)
    return ServerRow(
        key=key,
        name=name,
        status="Connecting",
        source="Added by you",
        section="used",
        furl=text,
    )


def disconnect_server(home: Path, nodedir: Path, key: str, name: str = "") -> None:
    """Forget ``key`` from this home's used set. Does not edit the friendnet."""
    book = load_book(home)
    kept: list[dict] = []
    removed: list[dict] = []
    for pin in book["pins"]:
        if pin.get("key") == key:
            removed.append(pin)
        else:
            kept.append(pin)
    book["pins"] = kept
    tokens = [key, name]
    for pin in removed:
        tokens.extend(
            [str(pin.get("key") or ""), str(pin.get("name") or ""), str(pin.get("tubid") or "")]
        )
        book["archive"].append(pin)
    _remember(book["forgotten"], tokens)
    save_book(home, book)
    write_static_servers(nodedir, kept)


def use_available_server(home: Path, nodedir: Path, key: str, name: str) -> ServerRow:
    """Pin an announced / seen-again server so this home uses it again."""
    book = load_book(home)
    display = (name or "").strip() or "Storage server"
    restored = None
    kept_arch: list[dict] = []
    for item in book["archive"]:
        same = item.get("key") == key or (
            display and str(item.get("name") or "").lower() == display.lower()
        )
        if restored is None and same:
            restored = item
        else:
            kept_arch.append(item)
    book["archive"] = kept_arch
    tokens = [key, display]
    if restored:
        tokens.extend(
            [
                str(restored.get("key") or ""),
                str(restored.get("name") or ""),
                str(restored.get("tubid") or ""),
                str(restored.get("furl") or ""),
            ]
        )
    book["forgotten"] = _drop_tokens(book["forgotten"], tokens)
    if restored:
        pin = dict(restored)
        pin["name"] = display or pin.get("name") or "Storage server"
        pin["source"] = pin.get("source") or "added"
    else:
        pin = {"key": key, "name": display, "furl": "", "tubid": "", "source": "added"}
    pins = [p for p in book["pins"] if p.get("key") != pin.get("key")]
    pins.append(pin)
    book["pins"] = pins
    save_book(home, book)
    write_static_servers(nodedir, pins)
    return ServerRow(
        key=str(pin.get("key") or key),
        name=str(pin.get("name") or display),
        status="Connecting",
        source=_source_label(str(pin.get("source") or "added")),
        section="used",
        furl=str(pin.get("furl") or ""),
    )


def _announced_key(srv: dict, index: int) -> str:
    nodeid = str(srv.get("nodeid") or "").strip()
    if nodeid:
        return nodeid
    nick = str(srv.get("nickname") or "").strip().lower()
    if nick:
        return "nick:" + nick
    return "announced-%d" % index


def _display_name(srv: dict, index: int) -> str:
    nick = str(srv.get("nickname") or "").strip()
    if nick:
        return nick
    nodeid = str(srv.get("nodeid") or "").strip()
    if nodeid:
        return nodeid[:12]
    return "Storage server %d" % (index + 1)


def _connected(status: str) -> bool:
    return (status or "").strip().lower().startswith("connected")


def _status_word(status: str) -> str:
    low = (status or "").strip().lower()
    if low.startswith("connected"):
        return "Connected"
    if "connecting" in low:
        return "Connecting"
    return "Offline"


def _forgotten_hit(forgotten: list[str], tokens: list[str]) -> bool:
    ban = {t.lower() for t in forgotten if t}
    return any(t and t.lower() in ban for t in tokens)


def _matches(pin: dict, srv: dict, index: int) -> bool:
    key = _announced_key(srv, index)
    if pin.get("key") and pin.get("key") == key:
        return True
    nodeid = str(srv.get("nodeid") or "")
    if pin.get("nodeid") and pin.get("nodeid") == nodeid:
        return True
    pname = str(pin.get("name") or "").strip().lower()
    sname = str(srv.get("nickname") or "").strip().lower()
    if pname and sname and pname == sname:
        return True
    tubid = str(pin.get("tubid") or "").lower()
    if tubid and nodeid and tubid in nodeid.lower():
        return True
    return False


def roster(
    home: Path, announced: Optional[list[dict]] = None
) -> tuple[list[ServerRow], list[ServerRow]]:
    """Merge local pins with introducer-announced servers.

    Used = pins, plus connected servers this home has not disconnected.
    Available = announced servers not in that set, including ones seen again
    after Disconnect.
    """
    book = load_book(home)
    rows_in = [s for s in (announced or []) if isinstance(s, dict)]
    used: list[ServerRow] = []
    available: list[ServerRow] = []
    consumed: set[int] = set()

    for pin in book["pins"]:
        match_i = None
        for i, srv in enumerate(rows_in):
            if i in consumed:
                continue
            if _matches(pin, srv, i):
                match_i = i
                break
        if match_i is not None:
            consumed.add(match_i)
            status = _status_word(str(rows_in[match_i].get("connection_status") or ""))
        elif pin.get("furl"):
            status = "Connecting"
        else:
            status = "Offline"
        used.append(
            ServerRow(
                key=str(pin.get("key") or ""),
                name=str(pin.get("name") or "Storage server"),
                status=status,
                source=_source_label(str(pin.get("source") or "added")),
                section="used",
                furl=str(pin.get("furl") or ""),
            )
        )

    for i, srv in enumerate(rows_in):
        if i in consumed:
            continue
        key = _announced_key(srv, i)
        name = _display_name(srv, i)
        nodeid = str(srv.get("nodeid") or "")
        tokens = [key, name, nodeid]
        if _forgotten_hit(book["forgotten"], tokens):
            available.append(
                ServerRow(
                    key=key,
                    name=name,
                    status="Available",
                    source="Seen again",
                    section="available",
                    note=SEEN_AGAIN_NOTE,
                )
            )
            continue
        if _connected(str(srv.get("connection_status") or "")):
            used.append(
                ServerRow(
                    key=key,
                    name=name,
                    status="Connected",
                    source="Announced",
                    section="used",
                )
            )
        else:
            available.append(
                ServerRow(
                    key=key,
                    name=name,
                    status="Available",
                    source="Announced",
                    section="available",
                )
            )
    used.sort(key=lambda row: row.name.lower())
    available.sort(key=lambda row: row.name.lower())
    return used, available
