"""Voucher store + state machine (docs/07-payment.md §2).

One SQLite file, one writer. Voucher rows are never deleted: a subaddress
stays mapped to its voucher forever, so a payment that arrives years late is
still credited. Money-losing states are impossible by construction:

  * every piconero on an issuer address belongs to exactly one voucher
  * a voucher issues at most once (all-or-nothing batch, cached by batch hash)
  * a paid voucher can always be re-asked for its cached batch until purge
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from dataclasses import dataclass, replace
from hashlib import sha256
from pathlib import Path
from typing import Callable, Iterable, Optional

from .chain import ChainWatcher, Transfer
from .policy import PricePolicy

STATES = (
    "quoted",  # subaddress allocated, nothing seen
    "seen",  # unconfirmed transfer(s) only
    "confirming",  # some depth, below the required confirmations
    "payable",  # confirmed ≥ 1 token; batch not yet issued
    "issued",  # terminal: batch signed and cached
    "underpaid",  # confirmed but < 1 token; more to the same address tops it up
    "expired_unpaid",  # cosmetic: quote window passed, nothing seen (still creditable)
)

OPEN_STATES = ("quoted", "seen", "confirming", "payable", "underpaid", "expired_unpaid")


class StoreError(Exception):
    pass


class DuplicateVid(StoreError):
    pass


@dataclass(frozen=True)
class Voucher:
    vid: str
    subaddr_index: int
    address: str
    scheme: str
    epoch: int
    tokens_quoted: int
    price_piconero: int
    amount_due: int
    quote_expires: float
    grace_until: float
    confirmations_required: int
    created: float
    updated: float
    state: str = "quoted"
    amount_seen: int = 0
    amount_confirmed: int = 0
    confirmations: int = 0  # depth of the shallowest transfer that counts toward amount_seen
    first_confirmed_at: Optional[float] = None
    effective_price: Optional[int] = None
    tokens_owed: int = 0
    tokens_issued: int = 0
    batch_hash: Optional[str] = None
    signed_batch: Optional[dict] = None

    def public(self) -> dict:
        """What /v0/voucher/{vid} returns. No chain internals, no batch."""
        return {
            "vid": self.vid,
            "state": self.state,
            "address": self.address,
            "scheme": self.scheme,
            "epoch": self.epoch,
            "tokens_quoted": self.tokens_quoted,
            "price_piconero": self.price_piconero,
            "amount_due": self.amount_due,
            "amount_seen": self.amount_seen,
            "amount_confirmed": self.amount_confirmed,
            "confirmations": self.confirmations,
            "confirmations_required": self.confirmations_required,
            "effective_price": self.effective_price,
            "tokens_owed": self.tokens_owed,
            "tokens_issued": self.tokens_issued,
            "quote_expires": self.quote_expires,
            "grace_until": self.grace_until,
        }


def batch_hash(blinded_b64: Iterable[str]) -> str:
    h = sha256()
    for b in blinded_b64:
        h.update(b.encode("ascii"))
        h.update(b"\n")
    return h.hexdigest()


def advance(
    v: Voucher,
    transfers: list[Transfer],
    policy: PricePolicy,
    now: float,
) -> Voucher:
    """Pure transition: fold a chain observation into a voucher.

    Never regresses `issued`. Never lowers tokens_owed on an unissued voucher
    except when the chain itself reports less (a reorg), which is why the
    required depth exists.
    """
    seen = sum(t.amount_piconero for t in transfers)
    if seen == 0:
        if v.state == "issued":
            return v
        # Nothing on chain (or a reorg took the unconfirmed tx back): unpaid.
        state = "expired_unpaid" if now > v.quote_expires else "quoted"
        if state == v.state and v.amount_seen == 0:
            return v
        return replace(
            v,
            state=state,
            amount_seen=0,
            amount_confirmed=0,
            confirmations=0,
            tokens_owed=0,
            first_confirmed_at=None,
            effective_price=None,
            updated=now,
        )

    required = policy.confirmations_required(seen)
    confirmed = sum(t.amount_piconero for t in transfers if t.confirmations >= required)
    depth = min(t.confirmations for t in transfers)
    out = replace(
        v,
        amount_seen=seen,
        amount_confirmed=confirmed,
        confirmations=depth,
        confirmations_required=required,
        updated=now,
    )
    if v.state == "issued":
        return out
    if confirmed == 0:
        state = "seen" if max(t.confirmations for t in transfers) == 0 else "confirming"
        return replace(out, state=state)

    first = v.first_confirmed_at if v.first_confirmed_at is not None else now
    price = (
        v.effective_price
        if v.effective_price is not None
        else policy.effective_price(v.price_piconero, first, v.grace_until)
    )
    owed = PricePolicy.tokens_owed(confirmed, price)
    return replace(
        out,
        first_confirmed_at=first,
        effective_price=price,
        tokens_owed=owed,
        state="payable" if owed >= 1 else "underpaid",
    )


_SCHEMA = """
CREATE TABLE IF NOT EXISTS voucher (
  vid TEXT PRIMARY KEY,
  subaddr_index INTEGER NOT NULL UNIQUE,
  address TEXT NOT NULL,
  scheme TEXT NOT NULL,
  epoch INTEGER NOT NULL,
  tokens_quoted INTEGER NOT NULL,
  price_piconero INTEGER NOT NULL,
  amount_due INTEGER NOT NULL,
  quote_expires REAL NOT NULL,
  grace_until REAL NOT NULL,
  confirmations_required INTEGER NOT NULL,
  created REAL NOT NULL,
  updated REAL NOT NULL,
  state TEXT NOT NULL,
  amount_seen INTEGER NOT NULL DEFAULT 0,
  amount_confirmed INTEGER NOT NULL DEFAULT 0,
  confirmations INTEGER NOT NULL DEFAULT 0,
  first_confirmed_at REAL,
  effective_price INTEGER,
  tokens_owed INTEGER NOT NULL DEFAULT 0,
  tokens_issued INTEGER NOT NULL DEFAULT 0,
  batch_hash TEXT,
  signed_batch TEXT
);
CREATE INDEX IF NOT EXISTS voucher_state ON voucher(state);
CREATE TABLE IF NOT EXISTS settlement (
  t TEXT PRIMARY KEY,
  nodeid TEXT NOT NULL,
  epoch INTEGER NOT NULL,
  settled_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS settlement_node ON settlement(nodeid, epoch);
CREATE TABLE IF NOT EXISTS conflict (
  t TEXT NOT NULL,
  nodeid TEXT NOT NULL,
  first_nodeid TEXT NOT NULL,
  at REAL NOT NULL
);
"""

_COLS = [
    "vid",
    "subaddr_index",
    "address",
    "scheme",
    "epoch",
    "tokens_quoted",
    "price_piconero",
    "amount_due",
    "quote_expires",
    "grace_until",
    "confirmations_required",
    "created",
    "updated",
    "state",
    "amount_seen",
    "amount_confirmed",
    "confirmations",
    "first_confirmed_at",
    "effective_price",
    "tokens_owed",
    "tokens_issued",
    "batch_hash",
    "signed_batch",
]


def _row_to_voucher(row: sqlite3.Row) -> Voucher:
    d = {k: row[k] for k in _COLS}
    if d["signed_batch"] is not None:
        d["signed_batch"] = json.loads(d["signed_batch"])
    return Voucher(**d)


SignFn = Callable[[list[str]], dict]


class VoucherStore:
    """SQLite-backed voucher store. Thread-safe via one process-wide lock."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = ":memory:" if path is None else str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._db = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self._db.row_factory = sqlite3.Row
        if self.path != ":memory:":
            self._db.execute("PRAGMA journal_mode=WAL")
        self._db.executescript(_SCHEMA)

    def close(self) -> None:
        with self._lock:
            self._db.close()

    # -- quotes -----------------------------------------------------------

    def create_quote(
        self,
        *,
        vid: str,
        tokens: int,
        policy: PricePolicy,
        chain: ChainWatcher,
        epoch: int,
        scheme: str,
        now: Optional[float] = None,
    ) -> Voucher:
        now = time.time() if now is None else now
        vid = vid.lower()
        if len(vid) != 16 or any(c not in "0123456789abcdef" for c in vid):
            raise StoreError("vid must be 8 bytes as 16 hex chars")
        amount_due = policy.amount_due(tokens)
        with self._lock:
            if self.get(vid) is not None:
                raise DuplicateVid(vid)
            address, index = chain.new_address(bytes.fromhex(vid))
            v = Voucher(
                vid=vid,
                subaddr_index=index,
                address=address,
                scheme=scheme,
                epoch=epoch,
                tokens_quoted=tokens,
                price_piconero=policy.price_piconero,
                amount_due=amount_due,
                quote_expires=now + policy.quote_ttl,
                grace_until=now + policy.quote_ttl + policy.grace,
                confirmations_required=policy.confirmations_required(amount_due),
                created=now,
                updated=now,
            )
            self._insert(v)
            return v

    def _insert(self, v: Voucher) -> None:
        vals = [getattr(v, c) for c in _COLS]
        vals[_COLS.index("signed_batch")] = (
            json.dumps(v.signed_batch) if v.signed_batch is not None else None
        )
        self._db.execute(
            "INSERT INTO voucher (%s) VALUES (%s)" % (",".join(_COLS), ",".join("?" * len(_COLS))),
            vals,
        )

    def _save(self, v: Voucher) -> None:
        cols = [c for c in _COLS if c != "vid"]
        vals = [getattr(v, c) for c in cols]
        vals[cols.index("signed_batch")] = (
            json.dumps(v.signed_batch) if v.signed_batch is not None else None
        )
        self._db.execute(
            "UPDATE voucher SET %s WHERE vid = ?" % ",".join("%s = ?" % c for c in cols),
            vals + [v.vid],
        )

    def get(self, vid: str) -> Optional[Voucher]:
        with self._lock:
            row = self._db.execute("SELECT * FROM voucher WHERE vid = ?", (vid.lower(),)).fetchone()
            return _row_to_voucher(row) if row else None

    def open_vouchers(self) -> list[Voucher]:
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM voucher WHERE state IN (%s) ORDER BY created"
                % ",".join("?" * len(OPEN_STATES)),
                OPEN_STATES,
            ).fetchall()
            return [_row_to_voucher(r) for r in rows]

    # -- chain observation ------------------------------------------------

    def observe(self, vid: str, transfers: list[Transfer], policy: PricePolicy, now: Optional[float] = None) -> Voucher:
        now = time.time() if now is None else now
        with self._lock:
            v = self.get(vid)
            if v is None:
                raise StoreError("unknown vid")
            nv = advance(v, transfers, policy, now)
            if nv != v:
                self._save(nv)
            return nv

    def poll(self, chain: ChainWatcher, policy: PricePolicy, now: Optional[float] = None) -> int:
        """Refresh every open voucher from the chain. Returns vouchers whose state changed."""
        now = time.time() if now is None else now
        changed = 0
        for v in self.open_vouchers():
            nv = self.observe(v.vid, chain.received(v.subaddr_index), policy, now)
            if nv.state != v.state or nv.tokens_owed != v.tokens_owed:
                changed += 1
        return changed

    # -- redeem -----------------------------------------------------------

    def redeem(
        self,
        vid: str,
        blinded_b64: list[str],
        sign_fn: SignFn,
        *,
        issuing_open: bool = True,
        now: Optional[float] = None,
    ) -> tuple[int, dict]:
        """Idempotent all-or-nothing issuance. Returns (http_status, body).

        200 batch (fresh or cached)   402 not payable yet (body = voucher.public())
        404 unknown vid               409 different batch already issued for this vid
        400 batch size != tokens_owed 410 epoch closed for issuing
        """
        now = time.time() if now is None else now
        bh = batch_hash(blinded_b64)
        with self._lock:
            v = self.get(vid)
            if v is None:
                return 404, {"error": "unknown vid"}
            if v.state == "issued":
                if v.batch_hash == bh and v.signed_batch is not None:
                    return 200, dict(v.signed_batch, cached=True)
                return 409, {"error": "a different batch was already issued for this vid", **v.public()}
            if v.state != "payable":
                return 402, {"error": "voucher not payable yet", **v.public()}
            if not issuing_open:
                return 410, {"error": "epoch closed for issuing; request a new quote", **v.public()}
            if len(blinded_b64) != v.tokens_owed:
                return 400, {
                    "error": "batch size must equal tokens_owed",
                    "tokens_owed": v.tokens_owed,
                    "got": len(blinded_b64),
                }
            signed = sign_fn(blinded_b64)
            nv = replace(
                v,
                state="issued",
                tokens_issued=v.tokens_owed,
                batch_hash=bh,
                signed_batch=signed,
                updated=now,
            )
            self._save(nv)
            return 200, dict(signed, cached=False)

    # -- settlement -------------------------------------------------------

    def settle(self, nodeid: str, epoch: int, preimages: list[str], now: Optional[float] = None) -> dict:
        """Record spent t values for a node. First node to settle a t owns it."""
        now = time.time() if now is None else now
        accepted = duplicates = conflicts = 0
        with self._lock:
            for t in preimages:
                row = self._db.execute("SELECT nodeid FROM settlement WHERE t = ?", (t,)).fetchone()
                if row is None:
                    self._db.execute(
                        "INSERT INTO settlement (t, nodeid, epoch, settled_at) VALUES (?,?,?,?)",
                        (t, nodeid, epoch, now),
                    )
                    accepted += 1
                elif row["nodeid"] == nodeid:
                    duplicates += 1
                else:
                    self._db.execute(
                        "INSERT INTO conflict (t, nodeid, first_nodeid, at) VALUES (?,?,?,?)",
                        (t, nodeid, row["nodeid"], now),
                    )
                    conflicts += 1
        return {"accepted": accepted, "duplicates": duplicates, "conflicts": conflicts}

    def node_ledger(self, nodeid: str) -> dict:
        with self._lock:
            rows = self._db.execute(
                "SELECT epoch, COUNT(*) AS n FROM settlement WHERE nodeid = ? GROUP BY epoch",
                (nodeid,),
            ).fetchall()
            return {str(r["epoch"]): r["n"] for r in rows}

    # -- ledger (solvency-lite) -------------------------------------------

    def ledger(self) -> dict:
        """Per-epoch totals operators can check. No per-payment data."""
        with self._lock:
            out: dict[str, dict] = {}
            for r in self._db.execute(
                "SELECT epoch, COUNT(*) AS quotes, "
                "SUM(amount_confirmed) AS xmr, SUM(tokens_quoted) AS quoted, "
                "SUM(tokens_issued) AS issued FROM voucher GROUP BY epoch"
            ).fetchall():
                out[str(r["epoch"])] = {
                    "quotes": r["quotes"],
                    "xmr_received_piconero": int(r["xmr"] or 0),
                    "tokens_quoted": int(r["quoted"] or 0),
                    "tokens_issued": int(r["issued"] or 0),
                    "tokens_settled": 0,
                }
            for r in self._db.execute(
                "SELECT epoch, COUNT(*) AS n FROM settlement GROUP BY epoch"
            ).fetchall():
                out.setdefault(str(r["epoch"]), _empty_epoch())["tokens_settled"] = r["n"]
            conflicts = self._db.execute("SELECT COUNT(*) AS n FROM conflict").fetchone()["n"]
            return {"epochs": out, "settlement_conflicts": int(conflicts)}


def _empty_epoch() -> dict:
    return {
        "quotes": 0,
        "xmr_received_piconero": 0,
        "tokens_quoted": 0,
        "tokens_issued": 0,
        "tokens_settled": 0,
    }
