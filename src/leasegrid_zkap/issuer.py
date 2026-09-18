"""Lab issuer HTTP: faucet issue + settlement that refuses R (gate 0b.1 / 0b.5)."""

from __future__ import annotations

import threading
from http.server import ThreadingHTTPServer

from challenge_bypass_ristretto import SigningKey

from .constants import DENOMINATION
from .crypto import CryptoError, issuer_info, sign_blinded
from .httpjson import make_handler, parse_listen, serve_background

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


class IssuerState:
    def __init__(self, signing_key: SigningKey):
        self.key = signing_key
        self.info = issuer_info(signing_key)
        self.lock = threading.Lock()
        self.settled_t: list[str] = []
        self.settlement_rejected_r = 0
        self.issue_count = 0
        self.last_settlement_keys: list[str] = []

    def stats(self) -> dict:
        with self.lock:
            return {
                **self.info,
                "issued-batches": self.issue_count,
                "settled-preimages": len(self.settled_t),
                "settlement-rejected-r": self.settlement_rejected_r,
                "last-settlement-keys": list(self.last_settlement_keys),
                "denomination": DENOMINATION,
            }


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
        return 200, {"ok": True, "issuer-pubkey-id": state.info["issuer-pubkey-id"]}

    def issue(body, headers):
        if not body or "blinded-tokens" not in body:
            return 400, {"error": "blinded-tokens required"}
        blinded = body["blinded-tokens"]
        if not isinstance(blinded, list) or not blinded:
            return 400, {"error": "blinded-tokens must be a non-empty list"}
        try:
            out = sign_blinded(state.key, blinded)
        except (CryptoError, Exception) as e:
            return 400, {"error": "sign failed", "class": type(e).__name__}
        with state.lock:
            state.issue_count += 1
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
        ("POST", "/v0/issue"): issue,
        ("POST", "/v0/faucet/issue"): issue,
        ("POST", "/v0/settlement"): settlement,
    }
    return make_handler(routes, name="IssuerHandler")


def start_issuer(signing_key: SigningKey, listen: str) -> tuple[IssuerState, ThreadingHTTPServer]:
    host, port = parse_listen(listen)
    state = IssuerState(signing_key)
    handler = build_issuer_handler(state)
    httpd, _ = serve_background(host, port, handler)
    state.listen = "http://%s:%d" % (host, httpd.server_address[1])  # type: ignore[attr-defined]
    return state, httpd
