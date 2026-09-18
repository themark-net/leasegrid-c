"""Per-issuer-epoch spent-set held by the storage node (docs/02-objects.md §2.7)."""

from __future__ import annotations

import json
import os
import threading
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class SpentRecord:
    t: str
    r_b64: str
    storage_index_hex: str
    lease_seconds: int
    share_bytes: int
    token_epoch: int
    issuer_pubkey_id: str
    nodeid: str


class ReplayError(Exception):
    """Same t presented against a different R."""


class SpentSet:
    def __init__(self, path: str | os.PathLike | None = None):
        self.path = Path(path).expanduser() if path else None
        self._lock = threading.Lock()
        self._by_t: dict[str, SpentRecord] = {}
        if self.path and self.path.exists():
            self._load()

    def _load(self) -> None:
        data = json.loads(self.path.read_text(encoding="utf-8"))
        for row in data.get("spent", []):
            rec = SpentRecord(**row)
            self._by_t[rec.t] = rec

    def _flush(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        payload = {"spent": [asdict(v) for v in self._by_t.values()]}
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(tmp, self.path)

    def lookup(self, t: str) -> SpentRecord | None:
        with self._lock:
            return self._by_t.get(t)

    def remember(self, rec: SpentRecord) -> SpentRecord:
        """
        First spend records the row. Same t + same R is idempotent success.
        Same t + different R raises ReplayError.
        """
        with self._lock:
            existing = self._by_t.get(rec.t)
            if existing is None:
                self._by_t[rec.t] = rec
                self._flush()
                return rec
            if existing.r_b64 != rec.r_b64:
                raise ReplayError("replay of t against a different R")
            return existing

    def preimages(self) -> list[str]:
        with self._lock:
            return list(self._by_t.keys())

    def __len__(self) -> int:
        with self._lock:
            return len(self._by_t)
