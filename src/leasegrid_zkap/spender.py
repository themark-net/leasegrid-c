"""Client-side spend-before-write for the Tahoe storage plugin.

Runs inside the *Tahoe client* process (via ``plugin.get_storage_client``), so it
must not block the reactor: the wallet + HTTP work happens in a thread under one
lock, and the storage client gets a Deferred.

One token buys one lease grant for (storage node, storage index) per the v0
denomination (1 token = 1 GiB-share x 30 days on one node). Grants are cached
locally so retries, extra shares and every later mutable write of the same
storage index do not spend again -- the node's LeaseGate also finds the
existing grant, so the cache is an optimisation, not the source of truth.
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Callable, Optional

from .client import ClientError, http_json, load_wallet, save_wallet, wallet_lock
from .constants import DEFAULT_LEASE_SECONDS, DEFAULT_SHARE_BYTES, TOKEN_EPOCH_V0
from .crypto import load_unblinded, mac_k_r
from .r_bind import encode_r


class NoCredit(Exception):
    """Wallet missing or empty: the write is refused client-side, nothing was spent."""


class WrongIssuer(Exception):
    """Wallet tokens were minted by a different issuer than this node accepts."""


class SpendRefused(Exception):
    """The storage node rejected the pass (bad MAC, replay, wrong epoch)."""


def _short(value: str, n: int = 8) -> str:
    return value[:n]


_SHARED: dict[str, "WalletSpender"] = {}
_SHARED_LOCK = threading.Lock()


class WalletSpender:
    @classmethod
    def shared(cls, wallet_path: str | os.PathLike, **kwargs) -> "WalletSpender":
        """One spender per wallet path per process.

        Tahoe builds one storage client per node; if each had its own spender the
        three would read-modify-write the same wallet and grants files and stale
        saves would resurrect spent tokens (observed: 15 node-side spends for 7
        wallet tokens). Sharing puts every spend in the process behind one lock.
        """
        key = str(Path(wallet_path).expanduser())
        with _SHARED_LOCK:
            sp = _SHARED.get(key)
            if sp is None:
                sp = cls(wallet_path, **kwargs)
                _SHARED[key] = sp
            return sp

    def __init__(
        self,
        wallet_path: str | os.PathLike,
        grants_path: Optional[str | os.PathLike] = None,
        recent_path: Optional[str | os.PathLike] = None,
        *,
        lease_seconds: int = DEFAULT_LEASE_SECONDS,
        share_bytes: int = DEFAULT_SHARE_BYTES,
        http: Callable[..., dict] = http_json,
    ) -> None:
        self.wallet_path = Path(wallet_path).expanduser()
        self.grants_path = (
            Path(grants_path).expanduser()
            if grants_path
            else self.wallet_path.with_name("credit-grants.json")
        )
        self.recent_path = Path(recent_path).expanduser() if recent_path else None
        self.lease_seconds = int(lease_seconds)
        self.share_bytes = int(share_bytes)
        self._http = http
        self._lock = threading.Lock()
        self._last_refusal_note = 0.0

    # -- grants cache --------------------------------------------------------

    def _load_grants(self) -> dict[str, dict[str, Any]]:
        if not self.grants_path.is_file():
            return {}
        try:
            data = json.loads(self.grants_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def _save_grants(self, grants: dict) -> None:
        self.grants_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.grants_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(grants, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(tmp, self.grants_path)

    def grant_for(self, nodeid: str, storage_index: bytes) -> Optional[dict]:
        return self._load_grants().get(nodeid, {}).get(storage_index.hex())

    def grants_count(self) -> int:
        return sum(len(v) for v in self._load_grants().values() if isinstance(v, dict))

    # -- recent events (same file/shape the Sync Credit place reads) ---------

    def _append_recent(self, title: str, tokens: int) -> None:
        if self.recent_path is None:
            return
        events: list[dict[str, Any]] = []
        if self.recent_path.is_file():
            try:
                data = json.loads(self.recent_path.read_text(encoding="utf-8"))
                if isinstance(data, dict) and isinstance(data.get("events"), list):
                    events = list(data["events"])
            except (OSError, json.JSONDecodeError):
                events = []
        events.insert(0, {"title": title, "tokens": int(tokens), "ts": time.time()})
        self.recent_path.parent.mkdir(parents=True, exist_ok=True)
        self.recent_path.write_text(
            json.dumps({"events": events[:20]}, indent=2) + "\n", encoding="utf-8"
        )

    def _note_refusal(self, title: str) -> None:
        now = time.time()
        if now - self._last_refusal_note < 60:
            return
        self._last_refusal_note = now
        self._append_recent(title, 0)

    # -- the spend -----------------------------------------------------------

    def ensure_grant_sync(
        self,
        spend_url: str,
        nodeid: str,
        issuer_pubkey_id: str,
        storage_index: bytes,
        need_bytes: int = 0,
    ) -> dict:
        """Return a grant for (nodeid, storage_index), spending one token if needed."""
        si_hex = storage_index.hex()
        with self._lock, wallet_lock(self.wallet_path):
            grants = self._load_grants()
            cached = grants.get(nodeid, {}).get(si_hex)
            if cached and int(need_bytes) <= int(cached.get("share_bytes", self.share_bytes)):
                return cached
            if int(need_bytes) > self.share_bytes:
                self._note_refusal("Upload refused: one write larger than a token covers")
                raise NoCredit(
                    "leasegrid-zkap-v0: %d bytes exceeds one token (%d bytes) for storage_index=%s"
                    % (need_bytes, self.share_bytes, si_hex)
                )
            if not self.wallet_path.is_file():
                self._note_refusal("Upload refused: no credit on this device")
                raise NoCredit("leasegrid-zkap-v0: no wallet at %s" % self.wallet_path)
            wallet = load_wallet(self.wallet_path)
            if str(wallet.get("issuer-pubkey-id") or "") != str(issuer_pubkey_id):
                self._note_refusal("Upload refused: credit is for a different issuer")
                raise WrongIssuer(
                    "leasegrid-zkap-v0: wallet issuer %s, node wants %s"
                    % (_short(str(wallet.get("issuer-pubkey-id") or "?")), _short(issuer_pubkey_id))
                )
            tokens = wallet.get("tokens") or []
            if not tokens:
                self._note_refusal("Upload refused: out of credit")
                raise NoCredit("leasegrid-zkap-v0: wallet empty; top up in the Credit place")

            rec = tokens.pop(0)
            r = encode_r(
                nodeid=nodeid,
                storage_index=storage_index,
                lease_seconds=self.lease_seconds,
                share_bytes=self.share_bytes,
                token_epoch=int(wallet.get("token-epoch", TOKEN_EPOCH_V0)),
                issuer_pubkey_id=issuer_pubkey_id,
            )
            mac = mac_k_r(load_unblinded(rec), r)
            from base64 import b64encode

            body = {
                "t": rec["t"],
                "R": b64encode(r).decode("ascii"),
                "mac": mac.decode("ascii") if isinstance(mac, bytes) else str(mac),
            }
            try:
                out = self._http(spend_url.rstrip("/") + "/v0/spend", "POST", body)
            except ClientError as exc:
                text = str(exc)
                if " 403 " in text:
                    # The node will never accept this pass; park it instead of retrying forever.
                    wallet.setdefault("rejected", []).append({"t": rec["t"], "why": text[-200:]})
                    save_wallet(self.wallet_path, wallet)
                    self._append_recent("Pass rejected by %s" % _short(nodeid), -1)
                    raise SpendRefused(text) from exc
                tokens.insert(0, rec)  # network trouble: the token is still ours
                raise
            save_wallet(self.wallet_path, wallet)
            grant = {
                "t": rec["t"],
                "share_bytes": self.share_bytes,
                "lease_seconds": self.lease_seconds,
                "ts": time.time(),
                "idempotent": bool(out.get("idempotent")),
            }
            grants.setdefault(nodeid, {})[si_hex] = grant
            self._save_grants(grants)
            self._append_recent("Lease on %s · %s" % (_short(nodeid), _short(si_hex)), -1)
            return grant

    # Tests flip this off to drive Deferreds without a running reactor.
    threaded = True

    def ensure_grant(self, *args, **kwargs):
        """Deferred flavour for use inside the Tahoe reactor."""
        if not self.threaded:
            from twisted.internet.defer import maybeDeferred

            return maybeDeferred(self.ensure_grant_sync, *args, **kwargs)
        from twisted.internet.threads import deferToThread

        return deferToThread(self.ensure_grant_sync, *args, **kwargs)
