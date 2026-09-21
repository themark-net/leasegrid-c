"""Silent eject: drop a dead nodeid from the usable set and stop paying it.

Corner C (docs/00-decision.md, docs/08-lab.md gate 0d): no slash, no PoRep,
no bond. Probe fails → eject. Repair is reconstruct onto remaining nodes.
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Callable, Optional
from urllib.error import URLError
from urllib.request import Request, urlopen

ProbeFn = Callable[[str], bool]


class Ejected(Exception):
    """This nodeid is silently ejected: do not pay it and do not write to it."""


def default_probe(url: str, timeout: float = 2.0) -> bool:
    """Cheap liveness: GET /health then the URL itself. 2xx is live."""
    base = url.rstrip("/")
    for target in (base + "/health", base):
        try:
            req = Request(target, method="GET", headers={"Accept": "application/json"})
            with urlopen(req, timeout=timeout) as resp:
                if 200 <= int(resp.status) < 300:
                    return True
        except (OSError, URLError, ValueError):
            continue
    return False


class EjectSet:
    def __init__(
        self,
        path: str | os.PathLike,
        *,
        miss_limit: int = 1,
        probe: Optional[ProbeFn] = None,
    ) -> None:
        self.path = Path(path).expanduser()
        self.miss_limit = int(miss_limit)
        self._probe = probe or default_probe
        self._lock = threading.Lock()
        self._data: dict = {"ejected": {}, "misses": {}, "events": []}
        if self.path.is_file():
            self._load()

    def _load(self) -> None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if isinstance(data, dict):
            self._data["ejected"] = dict(data.get("ejected") or {})
            self._data["misses"] = dict(data.get("misses") or {})
            self._data["events"] = list(data.get("events") or [])

    def _flush(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(self._data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(tmp, self.path)

    def _event(self, action: str, nodeid: str, **extra) -> None:
        rec = {"action": action, "nodeid": nodeid, "at": time.time()}
        rec.update(extra)
        self._data["events"].append(rec)
        self._flush()

    def is_ejected(self, nodeid: str) -> bool:
        with self._lock:
            return str(nodeid) in self._data["ejected"]

    def nodeids(self) -> list[str]:
        with self._lock:
            return sorted(self._data["ejected"])

    def events(self) -> list[dict]:
        with self._lock:
            return list(self._data["events"])

    def eject(self, nodeid: str, reason: str, probe_url: Optional[str] = None) -> None:
        nodeid = str(nodeid)
        with self._lock:
            if nodeid in self._data["ejected"]:
                return
            row = {"reason": str(reason), "at": time.time()}
            if probe_url:
                row["probe_url"] = probe_url
            self._data["ejected"][nodeid] = row
            self._event("eject", nodeid, reason=str(reason))

    def admit(self, nodeid: str) -> None:
        nodeid = str(nodeid)
        with self._lock:
            self._data["ejected"].pop(nodeid, None)
            self._data["misses"].pop(nodeid, None)
            self._event("admit", nodeid)

    def record_repair(
        self,
        *,
        ejected: str,
        method: str,
        before_connected: int,
        after_connected: int,
    ) -> None:
        if method.lower() in {"slash", "porep", "bond"}:
            raise ValueError("repair method cannot be slash/PoRep/bond")
        with self._lock:
            self._event(
                "repair",
                str(ejected),
                method=str(method),
                before_connected=int(before_connected),
                after_connected=int(after_connected),
            )

    def consider(self, nodeid: str, url: str) -> bool:
        """Probe ``url``. Eject after ``miss_limit`` failures. True if ejected."""
        if self.is_ejected(nodeid):
            return True
        ok = bool(self._probe(url))
        with self._lock:
            if ok:
                self._data["misses"][str(nodeid)] = 0
                self._flush()
                return False
            n = int(self._data["misses"].get(str(nodeid), 0)) + 1
            self._data["misses"][str(nodeid)] = n
            self._event("probe_fail", str(nodeid), url=url, misses=n)
            if n >= self.miss_limit:
                # eject() takes the lock; release first.
                pass
            else:
                return False
        if n >= self.miss_limit:
            self.eject(nodeid, reason="probe", probe_url=url)
            return True
        return False
