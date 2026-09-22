"""Slice A grid entry point called from the Kotlin UI (and from host tests)."""

from __future__ import annotations

import json
from typing import Any

from lg_intro import learn_servers
from lg_tahoe import ReadFail, StorageServer, download_file, list_folder_view


def dispatch(op: str, payload: str) -> str:
    """JSON in, JSON out. Never raises across the Kotlin boundary."""
    try:
        data = json.loads(payload or "{}")
        if not isinstance(data, dict):
            raise ReadFail("could not complete that. The request was unreadable.", "Retry.")
        if op == "learn":
            result = learn_servers(str(data.get("furl") or ""), float(data.get("timeout") or 25))
        elif op == "list":
            servers = _servers(data)
            children = list_folder_view(str(data.get("cap") or ""), servers)
            result = {
                "ok": True,
                "children": [
                    {"name": c.name, "kind": c.kind, "cap": c.cap, "size": c.size}
                    for c in children
                ],
            }
        elif op == "download":
            servers = _servers(data)
            dest = str(data.get("dest") or "")
            blob = download_file(str(data.get("cap") or ""), servers)
            if not dest:
                raise ReadFail(
                    "could not download this file. No place to write it on this phone.",
                    "Retry.",
                )
            with open(dest, "wb") as handle:
                handle.write(blob)
            result = {"ok": True, "size": len(blob), "path": dest}
        else:
            raise ReadFail("could not complete that. Unknown action.", "Retry.")
        return json.dumps(result)
    except ReadFail as exc:
        return json.dumps({"ok": False, "message": exc.message, "next": exc.next_hint})
    except OSError as exc:
        return json.dumps(
            {
                "ok": False,
                "message": "could not download this file. Network error or not enough free space.",
                "next": "check network / free space; Retry. (%s)" % exc.__class__.__name__,
            }
        )
    except Exception as exc:  # last-resort operate-or-FAIL, still in-app
        return json.dumps(
            {
                "ok": False,
                "message": "could not complete that. %s" % exc.__class__.__name__,
                "next": "Retry. If it repeats, check the network and the invite.",
            }
        )


def _servers(data: dict[str, Any]) -> list[StorageServer]:
    rows = data.get("servers") or []
    out: list[StorageServer] = []
    if not isinstance(rows, list):
        return out
    for row in rows:
        if isinstance(row, dict) and str(row.get("furl") or "").startswith("pb://"):
            out.append(StorageServer(furl=str(row["furl"]), nickname=str(row.get("nickname") or "")))
    return out
