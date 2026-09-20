"""Issuer HTTP: quote → voucher → redeem (docs/07-payment.md §5), settlement
that refuses R (gate 0b.5), optional faucet (lab), optional fake chain (dev grid).

The issuer signs prepaid receipts (ZKAPs) for real XMR it has seen arrive.
It never sees R, storage indexes, or where a token is spent.
"""

from __future__ import annotations

import os
import sys
import threading
from http.server import ThreadingHTTPServer
from typing import Optional
from urllib.parse import quote as urlquote

from challenge_bypass_ristretto import SigningKey

from .constants import DENOMINATION, TOKEN_EPOCH_V0
from .crypto import CryptoError, issuer_info, sign_blinded
from .httpjson import make_handler, parse_listen, serve_background
from .payment import ChainWatcher, FakeChain, PricePolicy, VoucherStore
from .payment.chain_walletrpc import WalletRpcChain
from .payment.store import DuplicateVid, StoreError

SCHEME_V0 = "ristretto-v0"
DEFAULT_PRICE_PICONERO = 6 * 10**9  # 0.006 XMR per GiB-share-month; operator-set
MAX_OPEN_QUOTES = 10_000

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
    def __init__(
        self,
        signing_key: SigningKey,
        *,
        chain: Optional[ChainWatcher] = None,
        policy: Optional[PricePolicy] = None,
        store: Optional[VoucherStore] = None,
        faucet: bool = True,
    ):
        self.key = signing_key
        self.info = issuer_info(signing_key)
        self.lock = threading.Lock()
        self.settled_t: list[str] = []
        self.settlement_rejected_r = 0
        self.issue_count = 0
        self.last_settlement_keys: list[str] = []
        self.chain = chain
        self.policy = policy or PricePolicy(price_piconero=DEFAULT_PRICE_PICONERO)
        self.store = store or VoucherStore()
        self.faucet = faucet
        self.listen = ""

    @property
    def chain_kind(self) -> str:
        if self.chain is None:
            return "none"
        if isinstance(self.chain, FakeChain):
            return "fake"
        if isinstance(self.chain, WalletRpcChain):
            return "wallet-rpc"
        return type(self.chain).__name__

    def stats(self) -> dict:
        with self.lock:
            return {
                **self.info,
                "issued-batches": self.issue_count,
                "settled-preimages": len(self.settled_t),
                "settlement-rejected-r": self.settlement_rejected_r,
                "last-settlement-keys": list(self.last_settlement_keys),
                "denomination": DENOMINATION,
                "faucet": self.faucet,
                "chain": self.chain_kind,
                "scheme": SCHEME_V0,
                "price_piconero": self.policy.price_piconero,
            }

    def keys(self) -> dict:
        return {
            "current": TOKEN_EPOCH_V0,
            "epochs": [
                {
                    "epoch": TOKEN_EPOCH_V0,
                    "scheme": SCHEME_V0,
                    "public-key": self.info["public-key"],
                    "issuer-pubkey-id": self.info["issuer-pubkey-id"],
                    "issue_until": None,
                    "accept_until": None,
                }
            ],
            "denomination": DENOMINATION,
            "price_piconero": self.policy.price_piconero,
            "quote_ttl": self.policy.quote_ttl,
            "grace": self.policy.grace,
            "max_tokens_per_quote": self.policy.max_tokens_per_quote,
            "chain": self.chain_kind,
        }

    def sign(self, blinded: list[str]) -> dict:
        out = sign_blinded(self.key, blinded)
        with self.lock:
            self.issue_count += 1
        return out

    def refresh(self, vid: str):
        """Pull this voucher's transfers from the chain now (no waiting on the poller)."""
        v = self.store.get(vid)
        if v is None or self.chain is None:
            return v
        if v.state == "issued":
            return v
        return self.store.observe(vid, self.chain.received(v.subaddr_index), self.policy)

    def poll_forever(self, interval: float, stop: threading.Event) -> None:
        while not stop.wait(interval):
            if self.chain is None:
                continue
            try:
                self.store.poll(self.chain, self.policy)
            except Exception as e:  # keep polling; a bad RPC answer must not kill the issuer
                print("issuer: poll failed: %s: %s" % (type(e).__name__, e), file=sys.stderr)


def pay_uri(address: str, amount_piconero: int, vid: str) -> str:
    return "monero:%s?tx_amount=%s&tx_description=%s" % (
        address,
        PricePolicy.format_xmr(amount_piconero),
        urlquote("leasegrid %s" % vid),
    )


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


def _blinded_list(body: dict):
    blinded = body.get("blinded-tokens")
    if not isinstance(blinded, list) or not blinded:
        return None
    if not all(isinstance(b, str) for b in blinded):
        return None
    return blinded


def build_issuer_handler(state: IssuerState):
    def info(body, headers):
        return 200, state.stats()

    def health(body, headers):
        return 200, {"ok": True, "issuer-pubkey-id": state.info["issuer-pubkey-id"]}

    def keys(body, headers):
        return 200, state.keys()

    # -- faucet (lab only) ------------------------------------------------

    def faucet_issue(body, headers):
        if not state.faucet:
            return 404, {"error": "faucet disabled on this issuer"}
        if not body or "blinded-tokens" not in body:
            return 400, {"error": "blinded-tokens required"}
        blinded = _blinded_list(body)
        if blinded is None:
            return 400, {"error": "blinded-tokens must be a non-empty list of strings"}
        try:
            out = state.sign(blinded)
        except (CryptoError, Exception) as e:
            return 400, {"error": "sign failed", "class": type(e).__name__}
        return 200, out

    # -- payment: quote → voucher → redeem ---------------------------------

    def quote(body, headers):
        if state.chain is None:
            return 503, {"error": "no payment chain configured on this issuer"}
        if not body:
            return 400, {"error": "JSON object required"}
        tokens = body.get("tokens")
        if not isinstance(tokens, int) or isinstance(tokens, bool):
            return 400, {"error": "tokens (integer) required"}
        if tokens < 1 or tokens > state.policy.max_tokens_per_quote:
            return 400, {"error": "tokens must be 1..%d" % state.policy.max_tokens_per_quote}
        scheme = body.get("scheme", SCHEME_V0)
        if scheme != SCHEME_V0:
            return 400, {"error": "unsupported scheme", "supported": [SCHEME_V0]}
        vid = body.get("vid")
        if vid is None:
            vid = os.urandom(8).hex()
        elif not isinstance(vid, str):
            return 400, {"error": "vid must be 16 hex chars"}
        if len(state.store.open_vouchers()) >= MAX_OPEN_QUOTES:
            return 429, {"error": "too many open quotes; try again later"}
        try:
            v = state.store.create_quote(
                vid=vid,
                tokens=tokens,
                policy=state.policy,
                chain=state.chain,
                epoch=TOKEN_EPOCH_V0,
                scheme=scheme,
            )
        except DuplicateVid:
            return 409, {"error": "vid already quoted", "vid": vid.lower()}
        except StoreError as e:
            return 400, {"error": str(e)}
        out = v.public()
        out["amount_piconero"] = v.amount_due
        out["amount_xmr"] = PricePolicy.format_xmr(v.amount_due)
        out["pay_uri"] = pay_uri(v.address, v.amount_due, v.vid)
        out["denomination"] = DENOMINATION
        return 200, out

    def voucher(body, headers):
        vid = (headers.get("x-path-tail") or "").strip("/").lower()
        if not vid:
            return 400, {"error": "vid required"}
        v = state.refresh(vid)
        if v is None:
            return 404, {"error": "unknown vid"}
        return 200, v.public()

    def redeem(body, headers):
        if not body:
            return 400, {"error": "JSON object required"}
        vid = body.get("vid")
        if not isinstance(vid, str):
            return 400, {"error": "vid required"}
        blinded = _blinded_list(body)
        if blinded is None:
            return 400, {"error": "blinded-tokens must be a non-empty list of strings"}
        state.refresh(vid)
        try:
            return state.store.redeem(vid, blinded, state.sign)
        except (CryptoError, Exception) as e:
            return 400, {"error": "sign failed", "class": type(e).__name__}

    def ledger(body, headers):
        return 200, state.store.ledger()

    # -- fake chain (dev grid / tests only) --------------------------------

    def fake_pay(body, headers):
        chain = state.chain
        if not isinstance(chain, FakeChain):
            return 404, {"error": "not a fake chain"}
        if not body:
            return 400, {"error": "JSON object required"}
        amount = body.get("amount_piconero")
        if amount is None and body.get("xmr") is not None:
            amount = int(round(float(body["xmr"]) * 10**12))
        if not isinstance(amount, int) or amount <= 0:
            return 400, {"error": "amount_piconero (positive int) or xmr required"}
        address = body.get("address")
        vid = body.get("vid")
        if address is None and isinstance(vid, str):
            v = state.store.get(vid)
            if v is None:
                return 404, {"error": "unknown vid"}
            address = v.address
        if not isinstance(address, str):
            return 400, {"error": "address or vid required"}
        try:
            index = chain.pay(address, amount)
        except KeyError:
            return 404, {"error": "unknown address"}
        blocks = body.get("mine", 0)
        if isinstance(blocks, int) and blocks > 0:
            chain.mine(blocks)
        return 200, {"ok": True, "index": index, "height": chain.height()}

    def fake_mine(body, headers):
        chain = state.chain
        if not isinstance(chain, FakeChain):
            return 404, {"error": "not a fake chain"}
        blocks = (body or {}).get("blocks", 1)
        if not isinstance(blocks, int) or blocks < 1:
            return 400, {"error": "blocks must be a positive int"}
        return 200, {"ok": True, "height": chain.mine(blocks)}

    # -- settlement (unchanged invariant: spent t only, never R) --------------

    def settlement(body, headers):
        if not body:
            return 400, {"error": "JSON object required"}
        keys_ = _keys_of(body)
        with state.lock:
            state.last_settlement_keys = keys_
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
        out = {"ok": True, "accepted": len(preimages), "stored-r": False}
        nodeid = body.get("nodeid")
        if isinstance(nodeid, str) and nodeid:
            epoch = body.get("epoch", TOKEN_EPOCH_V0)
            if not isinstance(epoch, int):
                return 400, {"error": "epoch must be an int"}
            out["ledger"] = state.store.settle(nodeid, epoch, preimages)
        return 200, out

    routes = {
        ("GET", "/v0/info"): info,
        ("GET", "/health"): health,
        ("GET", "/v0/keys"): keys,
        ("POST", "/v0/issue"): faucet_issue,
        ("POST", "/v0/faucet/issue"): faucet_issue,
        ("POST", "/v0/quote"): quote,
        ("GET", "/v0/voucher/"): voucher,
        ("POST", "/v0/redeem"): redeem,
        ("GET", "/v0/ledger"): ledger,
        ("POST", "/v0/fake/pay"): fake_pay,
        ("POST", "/v0/fake/mine"): fake_mine,
        ("POST", "/v0/settlement"): settlement,
    }
    return make_handler(routes, name="IssuerHandler")


def start_issuer(
    signing_key: SigningKey,
    listen: str,
    *,
    chain: Optional[ChainWatcher] = None,
    policy: Optional[PricePolicy] = None,
    store: Optional[VoucherStore] = None,
    faucet: bool = True,
    poll_interval: float = 0.0,
) -> tuple[IssuerState, ThreadingHTTPServer]:
    host, port = parse_listen(listen)
    state = IssuerState(signing_key, chain=chain, policy=policy, store=store, faucet=faucet)
    handler = build_issuer_handler(state)
    httpd, _ = serve_background(host, port, handler)
    state.listen = "http://%s:%d" % (host, httpd.server_address[1])
    if chain is not None and poll_interval > 0:
        stop = threading.Event()
        t = threading.Thread(
            target=state.poll_forever, args=(poll_interval, stop), name="issuer-poll", daemon=True
        )
        t.start()
        state.poll_stop = stop  # type: ignore[attr-defined]
    if isinstance(chain, FakeChain):
        print(
            "issuer: *** FAKE CHAIN *** payments are simulated via /v0/fake/pay; "
            "credit issued here is worth nothing. Lab use only.",
            file=sys.stderr,
            flush=True,
        )
    return state, httpd

