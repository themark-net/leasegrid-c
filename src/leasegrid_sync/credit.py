"""Lab issuer/faucet credit for Leasegrid Sync.

Buyer-facing remaining capacity (GiB·share-months). Tokens live in a local
wallet bound to this friendnet issuer. Not a 1:1 upload=credit meter.
"""

from __future__ import annotations

import json
import math
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from leasegrid_zkap.client import (
    ClientError,
    faucet_mint,
    http_json,
    load_wallet,
    save_wallet,
    wallet_lock,
)
from leasegrid_zkap.constants import DENOMINATION, GIB

from .backend import SyncError, default_home

DEFAULT_ISSUER_URL = "http://127.0.0.1:8700"
EXPAND_FACTOR = 3.2  # shares span nodes; upload size is not credit 1:1
TIER_TOKENS = {"small": 10, "medium": 50, "large": 200}

PLAIN_ZERO = (
    "Credit remaining: none.\n"
    "Sync may pause when leases cannot renew.\n"
    "New folders cannot allocate shares until you top up."
)

DENOMINATION_NOTE = (
    "Plain meaning: prepaid share-capacity, not a simple “disk free” meter. "
    "Encrypted shares expand across nodes — uploading 1 GiB uses more than "
    "1 GiB of credit.\n"
    "(1 credit ≈ 1 GiB-share × 30 days on one node.)"
)

LAB_NOTE = (
    "Top up quotes XMR for this friendnet. A lab faucet is still in the dialog "
    "for unpaid grids. Opaque ZKAP wallets from other apps do not convert."
)

OPAQUE_REJECT = (
    "This screen shows Leasegrid Sync credit only. "
    "Pasting an opaque ZKAP wallet from another tool will not convert here."
)

XMR_LATER = (
    "Pay the quoted XMR exactly. Credits appear after confirmations, never at zero-conf."
)
XMR_TIERS = TIER_TOKENS

LOAD_FAIL_MSG = "could not load credit balance. Issuer unreachable or returned an error."
LOAD_FAIL_NEXT = "Retry; check network; if lab is down, ask your friendnet operator."
REDEEM_FAIL_MSG = (
    "top-up did not complete. Faucet or issuer rejected the request (or network error)."
)
REDEEM_FAIL_NEXT = "Retry; if lab is down, ask your operator. Balance unchanged."
ZERO_FOLDER_MSG = "folder not added. Not enough storage credit to allocate shares."
ZERO_FOLDER_NEXT = "Credit → Top up, then Add folder again."
REVIEW_HEAD = "REVIEW — this folder needs more credit than the raw size."


def format_xmr_amount(piconero: Any) -> str:
    from leasegrid_zkap.payment.policy import PricePolicy

    try:
        n = int(piconero)
    except (TypeError, ValueError):
        return ""
    return PricePolicy.format_xmr(n)


def underpaid_copy(voucher: dict[str, Any], quoted_piconero: Any = None) -> str:
    """Buyer line for a live /v0/voucher row (piconero ints, no amount_xmr_*)."""
    seen = voucher.get("amount_seen")
    if seen is None:
        seen = voucher.get("amount_confirmed") or 0
    due = voucher.get("amount_due")
    if due is None:
        due = quoted_piconero or 0
    try:
        seen_n = int(seen)
    except (TypeError, ValueError):
        seen_n = 0
    try:
        due_n = int(due)
    except (TypeError, ValueError):
        due_n = 0
    rest = max(0, due_n - seen_n)
    return (
        "Underpaid. Received %s XMR; send at least %s more to the same address, "
        "or leave it — nothing is lost."
        % (format_xmr_amount(seen_n), format_xmr_amount(rest))
    )


MintFn = Callable[[str, int], dict]


@dataclass
class CreditBalance:
    tokens: int
    issuer_pubkey_id: str = ""
    denomination: str = DENOMINATION
    stale: bool = False


@dataclass
class RecentRow:
    title: str
    delta: str
    when: str


@dataclass
class CreditSnapshot:
    balance: CreditBalance
    remaining_text: str
    recent: list[RecentRow] = field(default_factory=list)


def default_issuer_url() -> str:
    return (os.environ.get("LEASEGRID_ISSUER_URL") or DEFAULT_ISSUER_URL).rstrip("/")


def format_remaining(tokens: int) -> str:
    if tokens <= 0:
        return PLAIN_ZERO
    return "About %d GiB kept for ~30 days on this friendnet" % tokens


def format_delta(tokens: int) -> str:
    sign = "+" if tokens >= 0 else ""
    return "%s%d GiB·mo" % (sign, tokens)


def credit_enforced() -> bool:
    """True when this grid charges for writes (``LEASEGRID_GATED=1``).

    Unpaid friendnets use the same join/offer path with no Credit required to
    add a folder. Payment complexity stays behind this flag.
    """
    return os.environ.get("LEASEGRID_GATED", "").strip().lower() in ("1", "true", "yes", "on")


def credit_gate(remaining: int, need: int) -> str:
    """Return 'ok', 'zero', or 'review' for add-folder vs remaining tokens."""
    if remaining <= 0:
        return "zero"
    if need > remaining:
        return "review"
    return "ok"


def folder_size_bytes(path: Path) -> int:
    total = 0
    root = Path(path)
    if not root.is_dir():
        return 0
    for item in root.rglob("*"):
        try:
            if item.is_file():
                total += item.stat().st_size
        except OSError:
            continue
    return total


def estimate_share_tokens(nbytes: int, expansion: float = EXPAND_FACTOR) -> int:
    if nbytes <= 0:
        return 0
    need = (nbytes / float(GIB)) * expansion
    return max(1, int(math.ceil(need)))


def is_leasegrid_wallet(data: Any) -> bool:
    if not isinstance(data, dict):
        return False
    tokens = data.get("tokens")
    if not isinstance(tokens, list):
        return False
    if "issuer-pubkey-id" not in data:
        return False
    # Foreign opaque shapes (PrivateStorage vouchers, raw blobs).
    foreign = ("unblinded-tokens", "vouchers", "zkaps", "passes")
    if any(k in data for k in foreign) and not tokens:
        return False
    for rec in tokens:
        if rec is None:
            return False
        if not isinstance(rec, dict) or "t" not in rec or "W" not in rec:
            return False
    return True


def opaque_reject_error() -> SyncError:
    return SyncError(OPAQUE_REJECT, "Stay on Leasegrid Sync credit. Close.")


def merge_wallets(existing: Optional[dict], minted: dict) -> dict:
    if not is_leasegrid_wallet(minted):
        raise opaque_reject_error()
    if not existing:
        return dict(minted)
    if not is_leasegrid_wallet(existing):
        raise opaque_reject_error()
    old_id = existing.get("issuer-pubkey-id")
    new_id = minted.get("issuer-pubkey-id")
    if old_id and new_id and old_id != new_id:
        raise SyncError(
            "could not add faucet credit. This wallet belongs to a different issuer.",
            "use this friendnet's Credit place; opaque wallets do not convert.",
        )
    out = dict(minted)
    out["tokens"] = list(existing.get("tokens") or []) + list(minted.get("tokens") or [])
    return out


def _when_label(ts: float, now: Optional[float] = None) -> str:
    now = now if now is not None else time.time()
    local = datetime.fromtimestamp(ts, tz=timezone.utc).date()
    today = datetime.fromtimestamp(now, tz=timezone.utc).date()
    delta = (today - local).days
    if delta <= 0:
        return "today"
    if delta == 1:
        return "yesterday"
    return local.isoformat()


class CreditCtl:
    def __init__(
        self,
        home: Optional[Path] = None,
        issuer_url: Optional[str] = None,
        wallet_path: Optional[Path] = None,
        mint_fn: Optional[MintFn] = None,
    ) -> None:
        self.home = Path(home) if home else default_home()
        self.home.mkdir(parents=True, exist_ok=True)
        env_wallet = os.environ.get("LEASEGRID_WALLET")
        if wallet_path is not None:
            self.wallet_path = Path(wallet_path)
        elif env_wallet:
            self.wallet_path = Path(env_wallet).expanduser()
        else:
            self.wallet_path = self.home / "credit-wallet.json"
        self.recent_path = self.home / "credit-recent.json"
        self.topup_state_path = self.wallet_path.with_name("credit-topup.json")
        self.issuer_url = (issuer_url or default_issuer_url()).rstrip("/")
        self._mint = mint_fn or (lambda url, count: faucet_mint(url, count=count))

    def ping_issuer(self) -> dict[str, Any]:
        try:
            info = http_json(self.issuer_url + "/v0/info", timeout=5.0)
        except ClientError as exc:
            raise SyncError(LOAD_FAIL_MSG, LOAD_FAIL_NEXT) from exc
        except (ValueError, json.JSONDecodeError) as exc:
            raise SyncError(LOAD_FAIL_MSG, LOAD_FAIL_NEXT) from exc
        if not isinstance(info, dict) or "issuer-pubkey-id" not in info:
            raise SyncError(LOAD_FAIL_MSG, LOAD_FAIL_NEXT)
        return info

    def _read_wallet(self) -> Optional[dict]:
        if not self.wallet_path.is_file():
            return None
        try:
            data = load_wallet(self.wallet_path)
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise opaque_reject_error() from exc
        if not is_leasegrid_wallet(data):
            raise opaque_reject_error()
        return data

    def remaining_tokens(self) -> int:
        try:
            wallet = self._read_wallet()
        except SyncError:
            return 0
        if not wallet:
            return 0
        return len(wallet.get("tokens") or [])

    def recent_rows(self) -> list[RecentRow]:
        if not self.recent_path.is_file():
            return []
        try:
            data = json.loads(self.recent_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        items = data.get("events") if isinstance(data, dict) else None
        if not isinstance(items, list):
            return []
        rows = []
        for item in items[:8]:
            if not isinstance(item, dict):
                continue
            ts = float(item.get("ts") or 0)
            tokens = int(item.get("tokens") or 0)
            rows.append(
                RecentRow(
                    title=str(item.get("title") or "Faucet top-up"),
                    delta=format_delta(tokens),
                    when=_when_label(ts) if ts else "",
                )
            )
        return rows

    def recent_refusal(self, within_seconds: float = 120.0) -> Optional[str]:
        """Newest 'Upload refused…' / 'Pass rejected…' event the Tahoe-side spender wrote, if fresh.

        The spender (leasegrid_zkap.spender) runs inside the Tahoe client; this file is
        how the window learns that writes are being refused for lack of credit.
        """
        if not self.recent_path.is_file():
            return None
        try:
            data = json.loads(self.recent_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        items = data.get("events") if isinstance(data, dict) else None
        if not isinstance(items, list) or not items:
            return None
        newest = items[0] if isinstance(items[0], dict) else {}
        title = str(newest.get("title") or "")
        ts = float(newest.get("ts") or 0)
        if not (title.startswith("Upload refused") or title.startswith("Pass rejected")):
            return None
        if time.time() - ts > within_seconds:
            return None
        return title

    def _append_recent(self, title: str, tokens: int) -> None:
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
            json.dumps({"events": events[:20]}, indent=2) + "\n",
            encoding="utf-8",
        )

    def _topup_client(self):
        from leasegrid_zkap.payment.topup import TopUpClient

        return TopUpClient(self.issuer_url, self.wallet_path, self.topup_state_path)

    def quote_topup(self, tokens: int) -> dict:
        try:
            return self._topup_client().quote(int(tokens))
        except SyncError:
            raise
        except Exception as exc:
            raise SyncError(
                "REVIEW — Your grid's issuer did not answer. Payments already sent are safe; retry later.",
                "Retry later. Do not send more XMR until Credit shows the quote again.",
            ) from exc

    def poll_topup(self, vid: str) -> dict:
        try:
            r = self._topup_client().redeem(str(vid))
        except SyncError:
            raise
        except Exception as exc:
            raise SyncError(
                "REVIEW — Your grid's issuer did not answer. Payments already sent are safe; retry later.",
                "Retry later.",
            ) from exc
        n = int(r.get("tokens_added") or 0)
        if n:
            self._append_recent("XMR top-up", n)
        return r

    def pending_topups(self) -> list[dict[str, Any]]:
        if not self.topup_state_path.is_file():
            return []
        try:
            from leasegrid_zkap.payment.topup import TopUpState

            st = TopUpState(self.topup_state_path)
            out = []
            for vid, rec in st.pending.items():
                row = dict(rec)
                row["vid"] = vid
                out.append(row)
            return out
        except Exception:
            return []

    def resume_pending_topups(self) -> int:
        """Finish XMR top-ups the issuer has confirmed since we last looked. Never raises.

        Pending vouchers live in credit-topup.json (07-payment.md §5.2); a crash
        between paying and collecting, or a restore from a recovery key, leaves
        rows there. Opening Credit is when they get collected.
        """
        if not self.topup_state_path.is_file():
            return 0
        try:
            from leasegrid_zkap.payment.topup import TopUpClient

            tc = TopUpClient(self.issuer_url, self.wallet_path, self.topup_state_path)
            if not tc.state.pending:
                return 0
            added = 0
            for r in tc.resume():
                n = int(r.get("tokens_added") or 0)
                if n:
                    added += n
                    self._append_recent("XMR top-up", n)
            return added
        except Exception:
            return 0

    def load_balance(self) -> CreditSnapshot:
        info = self.ping_issuer()
        self.resume_pending_topups()
        wallet = self._read_wallet()
        pubkey = str(info.get("issuer-pubkey-id") or "")
        tokens = 0
        denom = str(info.get("denomination") or DENOMINATION)
        if wallet:
            wid = str(wallet.get("issuer-pubkey-id") or "")
            if wid and pubkey and wid != pubkey:
                raise SyncError(
                    "could not load credit balance. Wallet is for a different issuer.",
                    "Top up on this friendnet; opaque wallets do not convert.",
                )
            tokens = len(wallet.get("tokens") or [])
            denom = str(wallet.get("denomination") or denom)
            pubkey = wid or pubkey
        return CreditSnapshot(
            balance=CreditBalance(tokens=tokens, issuer_pubkey_id=pubkey, denomination=denom),
            remaining_text=format_remaining(tokens),
            recent=self.recent_rows(),
        )

    def redeem_faucet(self, tier: str = "medium", count: Optional[int] = None) -> CreditSnapshot:
        if count is None:
            if tier not in TIER_TOKENS:
                raise SyncError(
                    REDEEM_FAIL_MSG,
                    REDEEM_FAIL_NEXT,
                )
            count = TIER_TOKENS[tier]
        if count <= 0:
            raise SyncError(REDEEM_FAIL_MSG, REDEEM_FAIL_NEXT)
        info = self.ping_issuer()
        existing = None
        try:
            minted = self._mint(self.issuer_url, int(count))
        except SyncError:
            raise
        except Exception as exc:
            raise SyncError(REDEEM_FAIL_MSG, REDEEM_FAIL_NEXT) from exc
        if not is_leasegrid_wallet(minted):
            raise opaque_reject_error()
        minted_id = str(minted.get("issuer-pubkey-id") or "")
        live_id = str(info.get("issuer-pubkey-id") or "")
        if minted_id and live_id and minted_id != live_id:
            raise SyncError(REDEEM_FAIL_MSG, REDEEM_FAIL_NEXT)
        # Read-merge-write under the wallet lock: the Tahoe client may be spending
        # from this same file right now.
        with wallet_lock(self.wallet_path):
            try:
                existing = self._read_wallet()
            except SyncError as exc:
                if OPAQUE_REJECT in exc.message:
                    raise
                existing = None
            merged = merge_wallets(existing, minted)
            save_wallet(self.wallet_path, merged)
        self._append_recent("Faucet top-up", int(count))
        tokens = len(merged.get("tokens") or [])
        return CreditSnapshot(
            balance=CreditBalance(
                tokens=tokens,
                issuer_pubkey_id=str(merged.get("issuer-pubkey-id") or live_id),
                denomination=str(merged.get("denomination") or DENOMINATION),
            ),
            remaining_text=format_remaining(tokens),
            recent=self.recent_rows(),
        )

    def estimate_tokens(self, path: Path) -> int:
        return estimate_share_tokens(folder_size_bytes(path))

    def reject_opaque_import(self, _blob: str = "") -> None:
        raise opaque_reject_error()
