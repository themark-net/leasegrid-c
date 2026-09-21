"""Issuer HTTP: quote → voucher → redeem (docs/07-payment.md §5), settlement
that refuses R (gate 0b.5), optional faucet (lab), optional fake chain (dev grid).

The issuer signs prepaid receipts (ZKAPs) for real XMR it has seen arrive.
It never sees R, storage indexes, or where a token is spent.
"""

from __future__ import annotations

import os
import sys
import threading
import time
from http.server import ThreadingHTTPServer
from typing import Optional
from urllib.parse import quote as urlquote

from challenge_bypass_ristretto import SigningKey

from .constants import DENOMINATION, TOKEN_EPOCH_V0
from .crypto import CryptoError, generate_signing_key, issuer_info, sign_blinded
from .httpjson import make_handler, parse_listen, serve_background
from .payment import ChainWatcher, FakeChain, PricePolicy, VoucherStore
from .payment.chain_walletrpc import WalletRpcChain
from .payment.store import DuplicateVid, StoreError

SCHEME_V0 = "ristretto-v0"
SCHEME_RSA = "rsa-bssa-v1"
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
        rsa_key=None,
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
        self.rsa_key = rsa_key
        self._epoch_keys: dict[int, SigningKey] = {}
        self._seed_epochs()

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
            out = {
                **self.info,
                "issued-batches": self.issue_count,
                "settled-preimages": len(self.settled_t),
                "settlement-rejected-r": self.settlement_rejected_r,
                "last-settlement-keys": list(self.last_settlement_keys),
                "denomination": DENOMINATION,
                "faucet": self.faucet,
                "chain": self.chain_kind,
                "scheme": SCHEME_V0,
                "supported-schemes": [SCHEME_V0] + ([SCHEME_RSA] if self.rsa_key is not None else []),
                "price_piconero": self.policy.price_piconero,
            }
        if self.rsa_key is not None:
            from .rsa_bssa import rsa_pubkey_id, rsa_public_spki_b64

            pk = self.rsa_key.public_key()
            out["rsa-public-key"] = rsa_public_spki_b64(pk)
            out["rsa-issuer-pubkey-id"] = rsa_pubkey_id(pk)
        return out

    def _key_b64(self, key: SigningKey) -> str:
        v = key.encode_base64()
        return v.decode("ascii") if isinstance(v, bytes) else str(v)

    def _seed_epochs(self) -> None:
        rows = self.store.list_epochs()
        if not rows:
            info = issuer_info(self.key)
            self.store.seed_epoch(
                TOKEN_EPOCH_V0,
                scheme=SCHEME_V0,
                public_key=info["public-key"],
                issuer_pubkey_id=info["issuer-pubkey-id"],
                signing_key=self._key_b64(self.key),
            )
            self._epoch_keys[TOKEN_EPOCH_V0] = self.key
            return
        for row in rows:
            raw = row.get("signing_key")
            if raw:
                from challenge_bypass_ristretto import SigningKey as SK

                blob = raw.encode("ascii") if isinstance(raw, str) else raw
                self._epoch_keys[int(row["epoch"])] = SK.decode_base64(blob)
        if TOKEN_EPOCH_V0 not in self._epoch_keys:
            self._epoch_keys[TOKEN_EPOCH_V0] = self.key

    def epoch_keys(self) -> dict[int, SigningKey]:
        return dict(self._epoch_keys)

    def keys(self) -> dict:
        now = time.time()
        cur = self.store.current_issuing(now)
        epochs = []
        for e in self.store.list_epochs():
            epochs.append(
                {
                    "epoch": int(e["epoch"]),
                    "scheme": e["scheme"],
                    "public-key": e["public_key"],
                    "issuer-pubkey-id": e["issuer_pubkey_id"],
                    "valid_from": e.get("valid_from"),
                    "issue_until": e.get("issue_until"),
                    "accept_until": e.get("accept_until"),
                }
            )
        return {
            "current": int(cur["epoch"]) if cur else TOKEN_EPOCH_V0,
            "epochs": epochs,
            "denomination": DENOMINATION,
            "price_piconero": self.policy.price_piconero,
            "quote_ttl": self.policy.quote_ttl,
            "grace": self.policy.grace,
            "max_tokens_per_quote": self.policy.max_tokens_per_quote,
            "chain": self.chain_kind,
        }

    def rotate(self, now: Optional[float] = None) -> dict:
        """Close the current issue window and open the next epoch with a new key."""
        now = time.time() if now is None else now
        cur = self.store.current_issuing(now)
        if cur is not None:
            self.store.close_issue(int(cur["epoch"]), now)
            next_id = int(cur["epoch"]) + 1
        else:
            have = [int(e["epoch"]) for e in self.store.list_epochs()]
            next_id = (max(have) + 1) if have else 1
        new_key = generate_signing_key()
        info = issuer_info(new_key)
        row = self.store.insert_epoch(
            next_id,
            scheme=SCHEME_V0,
            public_key=info["public-key"],
            issuer_pubkey_id=info["issuer-pubkey-id"],
            signing_key=self._key_b64(new_key),
            valid_from=now,
            issue_until=None,
            accept_until=now + 490 * 24 * 3600,
        )
        self._epoch_keys[next_id] = new_key
        return row

    def burn(self, epoch: int, now: Optional[float] = None) -> dict:
        """Compromise: stop accepting the epoch and open a new one if needed."""
        now = time.time() if now is None else now
        self.store.close_issue(int(epoch), now)
        self.store.set_accept_until(int(epoch), now)
        if self.store.current_issuing(now) is None:
            self.rotate(now)
        row = self.store.get_epoch(int(epoch))
        if row is None:
            raise ValueError("unknown epoch %s" % epoch)
        return row

    def sign(self, blinded: list[str], epoch: Optional[int] = None, scheme: str = SCHEME_V0) -> dict:
        now = time.time()
        if epoch is None:
            cur = self.store.current_issuing(now)
            epoch = int(cur["epoch"]) if cur else TOKEN_EPOCH_V0
        key = self._epoch_keys.get(int(epoch), self.key)
        if scheme == SCHEME_RSA:
            out = self._sign_rsa(blinded, int(epoch))
        else:
            out = sign_blinded(key, blinded)
            out["token-epoch"] = int(epoch)
        with self.lock:
            self.issue_count += 1
        return out

    def _sign_rsa(self, blinded_b64: list[str], epoch: int) -> dict:
        if self.rsa_key is None:
            raise CryptoError("rsa-bssa-v1 issuer key is not configured")
        from base64 import b64decode, b64encode

        from .rsa_bssa import blind_sign, rsa_pubkey_id, rsa_public_spki_b64

        pk = self.rsa_key.public_key()
        sigs = []
        for b in blinded_b64:
            raw = b64decode(b)
            sigs.append(b64encode(blind_sign(self.rsa_key, raw)).decode("ascii"))
        return {
            "signed-tokens": sigs,
            "public-key": rsa_public_spki_b64(pk),
            "issuer-pubkey-id": rsa_pubkey_id(pk),
            "token-epoch": int(epoch),
            "scheme": SCHEME_RSA,
            "denomination": DENOMINATION,
        }

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
        if scheme == SCHEME_RSA:
            if state.rsa_key is None:
                return 400, {"error": "unsupported scheme", "supported": [SCHEME_V0]}
        elif scheme != SCHEME_V0:
            supported = [SCHEME_V0] + ([SCHEME_RSA] if state.rsa_key is not None else [])
            return 400, {"error": "unsupported scheme", "supported": supported}
        vid = body.get("vid")
        if vid is None:
            vid = os.urandom(8).hex()
        elif not isinstance(vid, str):
            return 400, {"error": "vid must be 16 hex chars"}
        if len(state.store.open_vouchers()) >= MAX_OPEN_QUOTES:
            return 429, {"error": "too many open quotes; try again later"}
        issuing = state.store.current_issuing()
        if issuing is None:
            return 410, {"error": "no epoch is open for issuing"}
        try:
            v = state.store.create_quote(
                vid=vid,
                tokens=tokens,
                policy=state.policy,
                chain=state.chain,
                epoch=int(issuing["epoch"]),
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
        if scheme == SCHEME_RSA and state.rsa_key is not None:
            from .rsa_bssa import rsa_pubkey_id, rsa_public_spki_b64

            pk = state.rsa_key.public_key()
            out["public-key"] = rsa_public_spki_b64(pk)
            out["issuer-pubkey-id"] = rsa_pubkey_id(pk)
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
        v = state.store.get(vid)
        epoch = int(v.epoch) if v is not None else TOKEN_EPOCH_V0
        scheme = v.scheme if v is not None else SCHEME_V0
        try:
            return state.store.redeem(
                vid,
                blinded,
                lambda b: state.sign(b, epoch, scheme),
                issuing_open=state.store.is_issuing(epoch),
            )
        except (CryptoError, Exception) as e:
            return 400, {"error": "sign failed", "class": type(e).__name__}

    def exchange(body, headers):
        if not body:
            return 400, {"error": "JSON object required"}
        epoch_old = body.get("epoch_old")
        if not isinstance(epoch_old, int) or isinstance(epoch_old, bool):
            return 400, {"error": "epoch_old (int) required"}
        tokens = body.get("tokens")
        blinded = body.get("blinded-tokens") or body.get("blinded_new")
        if not isinstance(tokens, list) or not isinstance(blinded, list):
            return 400, {"error": "tokens and blinded-tokens must be lists"}
        if not tokens or len(tokens) != len(blinded):
            return 400, {"error": "tokens and blinded-tokens must be the same non-empty length"}
        for b in blinded:
            if not isinstance(b, str):
                return 400, {"error": "blinded-tokens must be strings"}
        now = time.time()
        ep = state.store.get_epoch(epoch_old)
        if ep is None:
            return 404, {"error": "unknown epoch"}
        until = ep.get("accept_until")
        if until is None or float(until) > now:
            return 409, {"error": "epoch is not burnt; exchange is only for a burnt epoch"}
        old_key = state._epoch_keys.get(int(epoch_old))
        ts: list[str] = []
        from challenge_bypass_ristretto import TokenPreimage

        for rec in tokens:
            if not isinstance(rec, dict) or not isinstance(rec.get("t"), str):
                return 400, {"error": "each token needs t"}
            t = rec["t"]
            if state.store.is_settled(t):
                return 409, {"error": "token already settled"}
            if state.store.is_exchanged(t):
                return 409, {"error": "token already exchanged"}
            if old_key is not None:
                try:
                    pre = TokenPreimage.decode_base64(
                        t.encode("ascii") if isinstance(t, str) else t
                    )
                    unb = old_key.rederive_unblinded_token(pre)
                    if rec.get("W"):
                        w = unb.encode_base64()
                        w = w.decode("ascii") if isinstance(w, bytes) else str(w)
                        if w != rec["W"]:
                            return 400, {"error": "W does not match t"}
                except Exception:
                    return 400, {"error": "token did not rederive under the burnt epoch"}
            ts.append(t)
        led = state.store.ledger()
        row = led["epochs"].get(str(epoch_old), {})
        remaining = (
            int(row.get("tokens_issued") or 0)
            - int(row.get("tokens_settled") or 0)
            - int(row.get("tokens_exchanged") or 0)
        )
        if len(ts) > remaining:
            return 409, {"error": "exchange exceeds remaining issuance"}
        cur = state.store.current_issuing(now)
        if cur is None:
            return 503, {"error": "no issuing epoch"}
        signed = state.sign(blinded, int(cur["epoch"]))
        state.store.record_exchanges(ts, epoch_old, int(cur["epoch"]), now)
        return 200, signed

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
        ("POST", "/v0/exchange"): exchange,
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
    rsa_key=None,
) -> tuple[IssuerState, ThreadingHTTPServer]:
    host, port = parse_listen(listen)
    state = IssuerState(
        signing_key, chain=chain, policy=policy, store=store, faucet=faucet, rsa_key=rsa_key
    )
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

