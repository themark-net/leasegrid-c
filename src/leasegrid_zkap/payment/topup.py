"""Buyer side of the payment rail (docs/07-payment.md §5–§6).

quote → pay (out of band, any Monero wallet) → poll → redeem → tokens in the
wallet. Everything the client sends is derived from a 32-byte credit seed:

    vid_n        = HKDF(seed, "leasegrid/vid/v0"   || n)[:8]
    token_{vid,i}= HKDF(seed, "leasegrid/token/v0" || vid || i)  (64 B preimage)
    blind_{vid,i}= HKDF(seed, "leasegrid/blind/v0" || vid || i)  (scalar, wide-reduced)

so a restored client can replay every blinded batch it ever sent and get the
issuer's cached signatures back. The seed is what the recovery key carries.

State (seed, quote counter, pending vouchers) lives in one JSON file next to
the wallet; the write-ahead rule is "persist before you ask the issuer".
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Callable, Optional

from challenge_bypass_ristretto import RandomToken

from ..client import ClientError, http_json, load_wallet, save_wallet, wallet_lock
from ..constants import DENOMINATION, TOKEN_EPOCH_V0
from ..crypto import CryptoError, unblind_batch, wallet_record

INFO_VID = b"leasegrid/vid/v0"
INFO_TOKEN = b"leasegrid/token/v0"
INFO_BLIND = b"leasegrid/blind/v0"
RISTRETTO_L = 2**252 + 27742317777372353535851937790883648493
RECOVER_GAP = 20
STATE_VERSION = 1

HttpFn = Callable[..., dict]


class TopUpError(Exception):
    pass


class _RedeemNotReady(Exception):
    def __init__(self, body: dict) -> None:
        self.body = body


class _RedeemResize(Exception):
    def __init__(self, count: int) -> None:
        self.count = count


# -- derivation ----------------------------------------------------------------------


def hkdf_expand(prk: bytes, info: bytes, length: int) -> bytes:
    """RFC 5869 expand step (SHA-256). The seed is uniform, so it is the PRK."""
    out = b""
    prev = b""
    counter = 1
    while len(out) < length:
        prev = hmac.new(prk, prev + info + bytes([counter]), hashlib.sha256).digest()
        out += prev
        counter += 1
    return out[:length]


def derive_vid(seed: bytes, n: int) -> str:
    if n < 0 or n > 0xFFFFFFFF:
        raise ValueError("quote counter out of range")
    return hkdf_expand(seed, INFO_VID + n.to_bytes(4, "big"), 8).hex()


def derive_tokens(seed: bytes, vid: str, count: int) -> list[RandomToken]:
    vid_b = bytes.fromhex(vid)
    out = []
    for i in range(count):
        tag = vid_b + i.to_bytes(4, "big")
        preimage = hkdf_expand(seed, INFO_TOKEN + tag, 64)
        wide = int.from_bytes(hkdf_expand(seed, INFO_BLIND + tag, 64), "little")
        scalar = (wide % RISTRETTO_L).to_bytes(32, "little")
        out.append(RandomToken.decode_base64(base64.b64encode(preimage + scalar)))
    return out


def _b64(x) -> str:
    v = x.encode_base64()
    return v.decode("ascii") if isinstance(v, bytes) else str(v)


def _http_status(exc: ClientError) -> Optional[int]:
    m = re.search(r"-> (\d{3}) ", str(exc))
    return int(m.group(1)) if m else None


def _http_body(exc: ClientError) -> dict:
    text = str(exc)
    i = text.find("{")
    if i < 0:
        return {}
    try:
        return json.loads(text[i:])
    except json.JSONDecodeError:
        return {}


# -- state file ------------------------------------------------------------------------


class TopUpState:
    """<home>/credit-topup.json: seed, quote counter, pending vouchers."""

    def __init__(self, path: str | os.PathLike) -> None:
        self.path = Path(path).expanduser()
        self.seed: bytes = b""
        self.counter = 0
        self.pending: dict[str, dict[str, Any]] = {}
        self.history: list[dict[str, Any]] = []
        if self.path.is_file():
            self._load()
        else:
            self.seed = os.urandom(32)
            self.save()

    def _load(self) -> None:
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or "credit-seed" not in data:
            raise TopUpError("credit-topup.json is not a Leasegrid top-up state file")
        self.seed = bytes.fromhex(data["credit-seed"])
        if len(self.seed) != 32:
            raise TopUpError("credit seed must be 32 bytes")
        self.counter = int(data.get("quote-counter") or 0)
        self.pending = dict(data.get("pending") or {})
        self.history = list(data.get("history") or [])

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": STATE_VERSION,
            "credit-seed": self.seed.hex(),
            "quote-counter": self.counter,
            "pending": self.pending,
            "history": self.history[-50:],
        }
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, sort_keys=True)
                f.write("\n")
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
        os.replace(tmp, self.path)

    @classmethod
    def from_seed(cls, path: str | os.PathLike, seed: bytes, counter_hint: int = 0) -> "TopUpState":
        """Recovery: create the state file from a seed carried in the recovery key."""
        p = Path(path).expanduser()
        if p.is_file():
            raise TopUpError("refusing to overwrite existing %s" % p)
        st = cls.__new__(cls)
        st.path = p
        st.seed = bytes(seed)
        if len(st.seed) != 32:
            raise TopUpError("credit seed must be 32 bytes")
        st.counter = int(counter_hint)
        st.pending = {}
        st.history = []
        st.save()
        return st


# -- client ----------------------------------------------------------------------------


class TopUpClient:
    def __init__(
        self,
        issuer_url: str,
        wallet_path: str | os.PathLike,
        state_path: str | os.PathLike | None = None,
        http: HttpFn = http_json,
    ) -> None:
        self.issuer_url = issuer_url.rstrip("/")
        self.wallet_path = Path(wallet_path).expanduser()
        self.state_path = (
            Path(state_path).expanduser()
            if state_path is not None
            else self.wallet_path.with_name("credit-topup.json")
        )
        self.state = TopUpState(self.state_path)
        self._http = http

    # -- issuer calls --

    def keys(self) -> dict:
        return self._http(self.issuer_url + "/v0/keys")

    def status(self, vid: str) -> Optional[dict]:
        """Voucher view, or None if the issuer has never seen this vid."""
        try:
            return self._http(self.issuer_url + "/v0/voucher/" + vid)
        except ClientError as exc:
            if _http_status(exc) == 404:
                return None
            raise

    # -- quote --

    def quote(self, tokens: int, scheme: Optional[str] = None) -> dict:
        """Ask for a quote under the next seed-derived vid. Persist before asking."""
        if tokens < 1:
            raise TopUpError("tokens must be ≥ 1")
        n = self.state.counter
        vid = derive_vid(self.state.seed, n)
        self.state.pending[vid] = {
            "n": n,
            "tokens_quoted": int(tokens),
            "state": "quoting",
            "created": time.time(),
        }
        if scheme:
            self.state.pending[vid]["scheme"] = scheme
        self.state.counter = n + 1
        self.state.save()
        body: dict[str, Any] = {"tokens": int(tokens), "vid": vid}
        if scheme:
            body["scheme"] = scheme
        try:
            q = self._http(self.issuer_url + "/v0/quote", "POST", body)
        except ClientError as exc:
            if _http_status(exc) == 409:
                # A previous run got this far and lost the reply: adopt the issuer's row.
                q = self.status(vid)
                if q is None:
                    raise
            else:
                raise
        rec = self.state.pending[vid]
        rec.update(
            {
                "state": q.get("state", "quoted"),
                "scheme": q.get("scheme", scheme),
                "address": q.get("address"),
                "amount_piconero": q.get("amount_due") or q.get("amount_piconero"),
                "amount_xmr": q.get("amount_xmr"),
                "pay_uri": q.get("pay_uri"),
                "quote_expires": q.get("quote_expires"),
                "grace_until": q.get("grace_until"),
                "confirmations_required": q.get("confirmations_required"),
                "public-key": q.get("public-key"),
                "issuer-pubkey-id": q.get("issuer-pubkey-id"),
            }
        )
        self.state.save()
        return dict(q, vid=vid)

    # -- redeem --

    def redeem(self, vid: str, *, unverified: bool = False) -> dict:
        """Collect the batch for a payable/issued voucher into the wallet. Idempotent."""
        v = self.status(vid)
        if v is None:
            self.state.pending.pop(vid, None)
            self.state.save()
            raise TopUpError("issuer does not know voucher %s" % vid)
        state = v.get("state")
        if state not in ("payable", "issued"):
            if vid in self.state.pending:
                self.state.pending[vid].update(
                    state=state,
                    amount_seen=v.get("amount_seen"),
                    confirmations=v.get("confirmations"),
                )
                self.state.save()
            return {"vid": vid, "state": state, "tokens_added": 0, "voucher": v}
        count = int(v["tokens_issued"] if state == "issued" else v["tokens_owed"])
        if count < 1:
            raise TopUpError("voucher %s owes no tokens" % vid)
        scheme = v.get("scheme") or (self.state.pending.get(vid) or {}).get("scheme")
        try:
            if scheme == "rsa-bssa-v1":
                issued, recs = self._redeem_rsa(vid, v, count)
            else:
                issued, recs = self._redeem_ristretto(vid, count)
        except _RedeemNotReady as exc:
            return {
                "vid": vid,
                "state": exc.body.get("state", "unknown"),
                "tokens_added": 0,
                "voucher": exc.body,
            }
        count = len(recs)
        if unverified:
            for r in recs:
                r["unverified"] = True
        added = self._merge_into_wallet(recs, issued)
        self.state.pending.pop(vid, None)
        self.state.history.append(
            {"vid": vid, "tokens": count, "added": added, "cached": bool(issued.get("cached")), "ts": time.time()}
        )
        self.state.save()
        return {
            "vid": vid,
            "state": "issued",
            "tokens_added": added,
            "tokens": count,
            "cached": bool(issued.get("cached")),
            "issuer-pubkey-id": issued.get("issuer-pubkey-id"),
        }

    def _post_redeem(self, vid: str, blinded_b64: list[str], count: int) -> dict:
        try:
            return self._http(
                self.issuer_url + "/v0/redeem", "POST", {"vid": vid, "blinded-tokens": blinded_b64}
            )
        except ClientError as exc:
            code = _http_status(exc)
            body = _http_body(exc)
            if code == 402:
                raise _RedeemNotReady(body)
            if code == 409:
                raise TopUpError(
                    "issuer already issued a different batch for %s; this seed cannot reproduce it" % vid
                ) from exc
            if code == 400 and isinstance(body.get("tokens_owed"), int) and body["tokens_owed"] != count:
                raise _RedeemResize(int(body["tokens_owed"])) from exc
            raise

    def _redeem_ristretto(self, vid: str, count: int) -> tuple[dict, list[dict]]:
        for _attempt in range(2):
            tokens = derive_tokens(self.state.seed, vid, count)
            blinded = [t.blind() for t in tokens]
            blinded_b64 = [_b64(b) for b in blinded]
            try:
                issued = self._post_redeem(vid, blinded_b64, count)
                break
            except _RedeemResize as exc:
                count = exc.count
                continue
        else:
            raise TopUpError("voucher %s: batch size kept changing" % vid)
        try:
            unblinded = unblind_batch(
                tokens, blinded, issued["signed-tokens"], issued["proof"], issued["public-key"]
            )
        except (CryptoError, KeyError) as exc:
            raise TopUpError("issuer batch for %s did not verify: %s" % (vid, exc)) from exc
        return issued, [wallet_record(u) for u in unblinded]

    def _redeem_rsa(self, vid: str, voucher: dict, count: int) -> tuple[dict, list[dict]]:
        from base64 import b64decode, b64encode

        from ..rsa_bssa import (
            BssaError,
            blind,
            derive_tok_keypair,
            finalize,
            load_rsa_public_spki,
            token_id,
            token_message,
        )

        pk_b64 = (
            voucher.get("public-key")
            or (self.state.pending.get(vid) or {}).get("public-key")
            or self._http(self.issuer_url + "/v0/info").get("rsa-public-key")
        )
        if not pk_b64:
            raise TopUpError("issuer did not publish an rsa-bssa-v1 public key")
        pk = load_rsa_public_spki(str(pk_b64))
        for _attempt in range(2):
            prepared = []
            blinded_b64 = []
            for i in range(count):
                t = token_id(self.state.seed, vid, i)
                _tok_sk, tok_pk = derive_tok_keypair(self.state.seed, vid, i)
                msg = token_message(t, tok_pk)
                blinded, inv = blind(pk, msg)
                prepared.append((t, tok_pk, msg, inv))
                blinded_b64.append(b64encode(blinded).decode("ascii"))
            try:
                issued = self._post_redeem(vid, blinded_b64, count)
                break
            except _RedeemResize as exc:
                count = exc.count
                continue
        else:
            raise TopUpError("voucher %s: batch size kept changing" % vid)
        try:
            issued_pk = load_rsa_public_spki(issued["public-key"])
            recs = []
            for i, (t, tok_pk, msg, inv) in enumerate(prepared):
                sigma = finalize(issued_pk, msg, b64decode(issued["signed-tokens"][i]), inv)
                recs.append(
                    {
                        "scheme": "rsa-bssa-v1",
                        "t": b64encode(t).decode("ascii"),
                        "pk_tok": b64encode(tok_pk).decode("ascii"),
                        "sigma": b64encode(sigma).decode("ascii"),
                    }
                )
        except (BssaError, KeyError, ValueError, IndexError) as exc:
            raise TopUpError("issuer rsa batch for %s did not verify: %s" % (vid, exc)) from exc
        return issued, recs

    def _merge_into_wallet(self, recs: list[dict], issued: dict) -> int:
        with wallet_lock(self.wallet_path):
            wallet: dict = {}
            if self.wallet_path.is_file():
                wallet = load_wallet(self.wallet_path)
            wid = str(wallet.get("issuer-pubkey-id") or "")
            iid = str(issued.get("issuer-pubkey-id") or "")
            if wid and iid and wid != iid:
                raise TopUpError("wallet belongs to issuer %s, batch is from %s" % (wid[:8], iid[:8]))
            have = {r.get("t") for r in wallet.get("tokens") or []}
            have |= {r.get("t") for r in wallet.get("rejected") or []}
            wallet.setdefault("tokens", [])
            wallet["issuer-pubkey-id"] = iid or wid
            wallet["public-key"] = issued.get("public-key", wallet.get("public-key"))
            wallet["token-epoch"] = issued.get("token-epoch", wallet.get("token-epoch", TOKEN_EPOCH_V0))
            wallet["denomination"] = issued.get("denomination", wallet.get("denomination", DENOMINATION))
            added = 0
            for r in recs:
                if r["t"] in have:
                    continue
                wallet["tokens"].append(r)
                added += 1
            save_wallet(self.wallet_path, wallet)
            return added

    # -- resume / recover --

    def resume(self) -> list[dict]:
        """Finish every pending voucher that is payable or issued; refresh the rest."""
        out = []
        for vid in list(self.state.pending.keys()):
            try:
                out.append(self.redeem(vid))
            except TopUpError as exc:
                out.append({"vid": vid, "state": "error", "tokens_added": 0, "error": str(exc)})
        return out

    def recover(self, gap: int = RECOVER_GAP, limit: int = 100_000) -> dict:
        """Walk vid_0, vid_1, … at the issuer; re-collect every batch this seed ever bought.

        Recovered tokens are marked unverified: some may have been spent by the
        lost device, and the node's spent-set is where that is discovered.
        """
        found = 0
        added = 0
        unknown_run = 0
        n = 0
        last_known = -1
        results = []
        while unknown_run < gap and n < limit:
            vid = derive_vid(self.state.seed, n)
            v = self.status(vid)
            if v is None:
                unknown_run += 1
            else:
                unknown_run = 0
                found += 1
                last_known = n
                if v.get("state") in ("payable", "issued"):
                    r = self.redeem(vid, unverified=True)
                    added += int(r.get("tokens_added", 0))
                    results.append(r)
                elif v.get("state") != "expired_unpaid":
                    self.state.pending.setdefault(vid, {"n": n, "tokens_quoted": v.get("tokens_quoted")})
                    self.state.pending[vid].update(state=v.get("state"), address=v.get("address"))
                    results.append({"vid": vid, "state": v.get("state"), "tokens_added": 0})
            n += 1
        if last_known + 1 > self.state.counter:
            self.state.counter = last_known + 1
        self.state.save()
        return {"vouchers_found": found, "tokens_added": added, "next_counter": self.state.counter, "results": results}
