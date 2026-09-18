"""Lab issuer HTTP: faucet (0b) + paid vid redeem (0c). Settlement still refuses R."""

from __future__ import annotations

import os
import threading
import time
import uuid
from http.server import ThreadingHTTPServer

from challenge_bypass_ristretto import SigningKey

from .constants import (
    CONFIRMATIONS_REQUIRED_SIMULATED,
    DEFAULT_QUOTE_TOKENS,
    DENOMINATION,
    PICONERO_PER_TOKEN,
    QUOTE_TTL_SECONDS,
    VID_LEN,
)
from .crypto import CryptoError, issuer_info, sign_blinded
from .httpjson import make_handler, parse_listen, serve_background
from .xmr_addr import payment_id_of
from .xmr_intake import SimulatedIntake

# Settlement must not see request binding. Names are matched case-insensitively.
_R_KEYS = frozenset(
    {
        "r",
        "mac",
        "request_binding",
        "request-binding",
        "storage_index",
        "storage-index",
        "w",
        "signature",
        "verification-signature",
    }
)


class Voucher:
    """Issuer-private (docs/02-objects.md §2.2). Not published as a whole."""

    def __init__(
        self,
        vid: bytes,
        integrated_address: str,
        amount_piconero: int,
        tokens_owed: int,
        expires: float,
    ):
        self.vid = vid
        self.integrated_address = integrated_address
        self.amount_piconero = int(amount_piconero)
        self.tokens_owed = int(tokens_owed)
        self.tokens_issued = 0
        self.confirmations = 0
        self.xmr_txid = None
        self.paid_amount = 0
        self.spent = False
        self.paid = False
        self.underpaid = False
        self.quote_id = uuid.uuid4().hex
        self.expires = expires
        self.created = time.time()

    @property
    def vid_hex(self) -> str:
        return self.vid.hex()

    def public(self) -> dict:
        return {
            "vid": self.vid_hex,
            "integrated-address": self.integrated_address,
            "amount_piconero": self.amount_piconero,
            "tokens_owed": self.tokens_owed,
            "tokens_issued": self.tokens_issued,
            "confirmations": self.confirmations,
            "spent": self.spent,
            "paid": self.paid,
            "underpaid": self.underpaid,
            "quote-id": self.quote_id,
            "expires": int(self.expires),
        }


class IssuerState:
    def __init__(self, signing_key: SigningKey, intake=None):
        self.key = signing_key
        self.info = issuer_info(signing_key)
        self.lock = threading.Lock()
        self.settled_t: list[str] = []
        self.settlement_rejected_r = 0
        self.issue_count = 0
        self.paid_issue_count = 0
        self.faucet_issue_count = 0
        self.last_settlement_keys: list[str] = []
        self.intake = intake or SimulatedIntake()
        self.vouchers: dict[str, Voucher] = {}

    def stats(self) -> dict:
        with self.lock:
            return {
                **self.info,
                "issued-batches": self.issue_count,
                "faucet-batches": self.faucet_issue_count,
                "paid-batches": self.paid_issue_count,
                "settled-preimages": len(self.settled_t),
                "settlement-rejected-r": self.settlement_rejected_r,
                "last-settlement-keys": list(self.last_settlement_keys),
                "denomination": DENOMINATION,
                "intake-mode": self.intake.mode,
                "xmr-network": getattr(self.intake, "network", "stagenet"),
                "confirmations-required": int(
                    getattr(
                        self.intake,
                        "confirmations_required",
                        CONFIRMATIONS_REQUIRED_SIMULATED,
                    )
                ),
                "piconero-per-token": PICONERO_PER_TOKEN,
                "open-vouchers": sum(1 for v in self.vouchers.values() if not v.spent),
            }

    def _parse_vid(self, value) -> bytes:
        if value is None:
            raise ValueError("vid required")
        if isinstance(value, bytes):
            raw = value
        else:
            s = str(value).strip().lower()
            if s.startswith("0x"):
                s = s[2:]
            if len(s) != VID_LEN * 2:
                raise ValueError("vid must be %d hex bytes" % VID_LEN)
            try:
                raw = bytes.fromhex(s)
            except ValueError as e:
                raise ValueError("vid must be hex") from e
        if len(raw) != VID_LEN:
            raise ValueError("vid must be %d bytes" % VID_LEN)
        return raw

    def quote(self, tokens: int | None = None, amount_piconero: int | None = None) -> Voucher:
        if tokens is None and amount_piconero is None:
            tokens = DEFAULT_QUOTE_TOKENS
        if tokens is not None:
            tokens = int(tokens)
            if tokens < 1:
                raise ValueError("tokens must be >= 1")
            amount = tokens * PICONERO_PER_TOKEN
        else:
            amount = int(amount_piconero)
            tokens = amount // PICONERO_PER_TOKEN
            if tokens < 1:
                raise ValueError("amount_piconero underpays one token")
            amount = tokens * PICONERO_PER_TOKEN
        vid = os.urandom(VID_LEN)
        addr = self.intake.make_integrated(vid)
        v = Voucher(
            vid=vid,
            integrated_address=addr,
            amount_piconero=amount,
            tokens_owed=tokens,
            expires=time.time() + QUOTE_TTL_SECONDS,
        )
        with self.lock:
            while v.vid_hex in self.vouchers:
                vid = os.urandom(VID_LEN)
                addr = self.intake.make_integrated(vid)
                v = Voucher(
                    vid=vid,
                    integrated_address=addr,
                    amount_piconero=amount,
                    tokens_owed=tokens,
                    expires=time.time() + QUOTE_TTL_SECONDS,
                )
            self.vouchers[v.vid_hex] = v
        return v

    def scan_and_match(self) -> list[dict]:
        incoming = self.intake.scan()
        matched = []
        with self.lock:
            for pay in incoming:
                vid_hex = pay.payment_id.hex()
                v = self.vouchers.get(vid_hex)
                if v is None:
                    continue
                v.confirmations = pay.confirmations
                v.xmr_txid = pay.txid
                v.paid_amount = pay.amount_piconero
                if pay.amount_piconero < v.amount_piconero:
                    v.underpaid = True
                    v.paid = False
                else:
                    v.underpaid = False
                    v.paid = True
                matched.append(
                    {
                        "vid": vid_hex,
                        "amount_piconero": pay.amount_piconero,
                        "confirmations": pay.confirmations,
                        "paid": v.paid,
                        "underpaid": v.underpaid,
                    }
                )
        return matched

    def simulate_pay(self, vid: bytes, amount_piconero: int, confirmations: int | None = None) -> dict:
        if getattr(self.intake, "mode", "") != "SIMULATED":
            raise RuntimeError("simulate-pay only works for SIMULATED intake")
        rec = self.intake.inject(vid, amount_piconero, confirmations=confirmations)
        matched = self.scan_and_match()
        hit = [m for m in matched if m["vid"] == vid.hex()]
        return {
            "ok": True,
            "intake-mode": "SIMULATED",
            "txid-kind": "simulated",
            "matched": hit,
            "confirmations": rec.confirmations,
        }

    def _voucher_for_issue(self, vid: bytes) -> tuple[Voucher | None, str | None]:
        v = self.vouchers.get(vid.hex())
        if v is None:
            return None, "unknown vid"
        if time.time() > v.expires and not v.paid:
            return v, "quote expired"
        if v.spent:
            return v, "voucher already spent for issuance"
        if v.underpaid and not v.paid:
            return v, "underpay"
        if not v.paid:
            return v, "not paid"
        return v, None


def _keys_of(body: dict) -> list[str]:
    return [str(k) for k in body.keys()]


def _contains_r(body: dict) -> bool:
    for k in body.keys():
        if str(k).lower() in _R_KEYS or str(k) == "R":
            return True
        if str(k).lower() == "tokens" and isinstance(body[k], list):
            for item in body[k]:
                if isinstance(item, dict) and _contains_r(item):
                    return True
    return False


def build_issuer_handler(state: IssuerState):
    def info(body, headers):
        return 200, state.stats()

    def health(body, headers):
        return 200, {
            "ok": True,
            "issuer-pubkey-id": state.info["issuer-pubkey-id"],
            "intake-mode": state.intake.mode,
        }

    def quote(body, headers):
        body = body or {}
        tokens = body.get("tokens")
        amount = body.get("amount_piconero") or body.get("amount")
        try:
            v = state.quote(
                tokens=int(tokens) if tokens is not None else None,
                amount_piconero=int(amount) if amount is not None else None,
            )
        except (TypeError, ValueError) as e:
            return 400, {"error": str(e)}
        out = v.public()
        out["network"] = getattr(state.intake, "network", "stagenet")
        out["intake-mode"] = state.intake.mode
        out["confirmations-required"] = int(
            getattr(state.intake, "confirmations_required", CONFIRMATIONS_REQUIRED_SIMULATED)
        )
        out["piconero-per-token"] = PICONERO_PER_TOKEN
        out["denomination"] = DENOMINATION
        return 200, out

    def voucher_status(body, headers):
        if not body or "vid" not in body:
            return 400, {"error": "vid required"}
        try:
            vid = state._parse_vid(body["vid"])
        except ValueError as e:
            return 400, {"error": str(e)}
        state.scan_and_match()
        with state.lock:
            v = state.vouchers.get(vid.hex())
        if v is None:
            return 404, {"error": "unknown vid"}
        out = v.public()
        out["intake-mode"] = state.intake.mode
        return 200, out

    def intake_scan(body, headers):
        matched = state.scan_and_match()
        return 200, {"matched": matched, "intake-mode": state.intake.mode}

    def intake_simulate(body, headers):
        if state.intake.mode != "SIMULATED":
            return 403, {"error": "simulate-pay is SIMULATED-only"}
        if not body or "vid" not in body:
            return 400, {"error": "vid required"}
        try:
            vid = state._parse_vid(body["vid"])
        except ValueError as e:
            return 400, {"error": str(e)}
        amount = body.get("amount_piconero") or body.get("amount")
        if amount is None:
            return 400, {"error": "amount_piconero required"}
        conf = body.get("confirmations")
        try:
            out = state.simulate_pay(
                vid,
                int(amount),
                confirmations=int(conf) if conf is not None else None,
            )
        except (TypeError, ValueError, RuntimeError) as e:
            return 400, {"error": str(e)}
        return 200, out

    def issue(body, headers):
        if not body or "blinded-tokens" not in body:
            return 400, {"error": "blinded-tokens required"}
        blinded = body["blinded-tokens"]
        if not isinstance(blinded, list) or not blinded:
            return 400, {"error": "blinded-tokens must be a non-empty list"}
        vid_raw = body.get("vid")
        if vid_raw:
            try:
                vid = state._parse_vid(vid_raw)
            except ValueError as e:
                return 400, {"error": str(e)}
            state.scan_and_match()
            with state.lock:
                voucher, err = state._voucher_for_issue(vid)
                if err:
                    return 403, {"error": err, "issued": False}
                if len(blinded) != voucher.tokens_owed:
                    return 400, {
                        "error": "blinded-tokens count must equal tokens_owed",
                        "tokens_owed": voucher.tokens_owed,
                    }
                try:
                    embedded = payment_id_of(voucher.integrated_address)
                except Exception:
                    embedded = b""
                if embedded != vid:
                    return 500, {"error": "integrated address does not embed vid"}
                try:
                    out = sign_blinded(state.key, blinded)
                except (CryptoError, Exception) as e:
                    return 400, {"error": "sign failed", "class": type(e).__name__}
                voucher.tokens_issued = len(blinded)
                voucher.spent = True
                state.issue_count += 1
                state.paid_issue_count += 1
            out["vid"] = vid.hex()
            out["tokens_owed"] = voucher.tokens_owed
            out["intake-mode"] = state.intake.mode
            return 200, out

        # Gate 0b faucet: no vid, no chain. Paid path above is 0c.
        try:
            out = sign_blinded(state.key, blinded)
        except (CryptoError, Exception) as e:
            return 400, {"error": "sign failed", "class": type(e).__name__}
        with state.lock:
            state.issue_count += 1
            state.faucet_issue_count += 1
        out["faucet"] = True
        return 200, out

    def settlement(body, headers):
        if not body:
            return 400, {"error": "JSON object required"}
        keys = _keys_of(body)
        with state.lock:
            state.last_settlement_keys = keys
        if _contains_r(body):
            with state.lock:
                state.settlement_rejected_r += 1
            return 400, {
                "error": "issuer must not receive R",
                "invariant": "settlement sends spent t only",
            }
        preimages = body.get("spent-preimages") or body.get("spent_preimages")
        if not isinstance(preimages, list):
            return 400, {"error": "spent-preimages (list of t) required"}
        for p in preimages:
            if not isinstance(p, str):
                return 400, {"error": "each spent preimage must be a base64 string"}
        with state.lock:
            for p in preimages:
                if p not in state.settled_t:
                    state.settled_t.append(p)
        return 200, {"ok": True, "accepted": len(preimages), "stored-r": False}

    routes = {
        ("GET", "/v0/info"): info,
        ("GET", "/health"): health,
        ("POST", "/v0/quote"): quote,
        ("POST", "/v0/voucher/status"): voucher_status,
        ("POST", "/v0/intake/scan"): intake_scan,
        ("POST", "/v0/intake/simulate"): intake_simulate,
        ("POST", "/v0/issue"): issue,
        ("POST", "/v0/faucet/issue"): issue,
        ("POST", "/v0/settlement"): settlement,
    }
    return make_handler(routes, name="IssuerHandler")


def start_issuer(signing_key: SigningKey, listen: str, intake=None) -> tuple[IssuerState, ThreadingHTTPServer]:
    host, port = parse_listen(listen)
    state = IssuerState(signing_key, intake=intake)
    handler = build_issuer_handler(state)
    httpd, _ = serve_background(host, port, handler)
    state.listen = "http://%s:%d" % (host, httpd.server_address[1])  # type: ignore[attr-defined]
    return state, httpd
