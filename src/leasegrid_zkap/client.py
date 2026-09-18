"""Client mint + spend helpers. Wallet JSON lives off-git."""

from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .constants import (
    DEFAULT_LEASE_SECONDS,
    DEFAULT_SHARE_BYTES,
    DENOMINATION,
    TOKEN_EPOCH_V0,
)
from .crypto import client_tokens, load_unblinded, mac_k_r, unblind_batch, wallet_record
from .r_bind import encode_r


class ClientError(Exception):
    pass


def http_json(url: str, method: str = "GET", body: dict | None = None, timeout: float = 15.0) -> dict:
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        raw = json.dumps(body).encode("utf-8")
        data = raw
        headers["Content-Type"] = "application/json"
    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=timeout) as resp:
            payload = resp.read()
    except HTTPError as e:
        err_body = e.read().decode("utf-8", "replace")
        raise ClientError("%s %s -> %s %s" % (method, url, e.code, err_body)) from e
    except URLError as e:
        raise ClientError("unreachable %s: %s" % (url, e.reason)) from e
    if not payload:
        return {}
    return json.loads(payload.decode("utf-8"))


def quote_tokens(issuer_url: str, tokens: int = 2) -> dict:
    return http_json(
        issuer_url.rstrip("/") + "/v0/quote",
        "POST",
        {"tokens": int(tokens)},
    )


def simulate_pay(issuer_url: str, vid: str, amount_piconero: int, confirmations: int | None = None) -> dict:
    body = {"vid": vid, "amount_piconero": int(amount_piconero)}
    if confirmations is not None:
        body["confirmations"] = int(confirmations)
    return http_json(issuer_url.rstrip("/") + "/v0/intake/simulate", "POST", body)


def scan_intake(issuer_url: str) -> dict:
    return http_json(issuer_url.rstrip("/") + "/v0/intake/scan", "POST", {})


def voucher_status(issuer_url: str, vid: str) -> dict:
    return http_json(
        issuer_url.rstrip("/") + "/v0/voucher/status",
        "POST",
        {"vid": vid},
    )


def redeem_vid(issuer_url: str, vid: str, count: int | None = None) -> dict:
    """Paid mint: blinded issue for a paid voucher. Fails if unpaid/underpay."""
    if count is None:
        st = voucher_status(issuer_url, vid)
        count = int(st.get("tokens_owed") or 0)
        if count < 1:
            raise ClientError("voucher tokens_owed < 1")
    tokens, blinded = client_tokens(count)
    blinded_b64 = []
    for b in blinded:
        v = b.encode_base64()
        blinded_b64.append(v.decode("ascii") if isinstance(v, bytes) else str(v))
    issued = http_json(
        issuer_url.rstrip("/") + "/v0/issue",
        "POST",
        {"vid": vid, "blinded-tokens": blinded_b64},
    )
    unblinded = unblind_batch(
        tokens,
        blinded,
        issued["signed-tokens"],
        issued["proof"],
        issued["public-key"],
    )
    recs = [wallet_record(u) for u in unblinded]
    return {
        "issuer-pubkey-id": issued["issuer-pubkey-id"],
        "public-key": issued["public-key"],
        "token-epoch": issued.get("token-epoch", TOKEN_EPOCH_V0),
        "denomination": issued.get("denomination", DENOMINATION),
        "tokens": recs,
        "vid": issued.get("vid", vid),
        "intake-mode": issued.get("intake-mode"),
        "faucet": False,
    }


def faucet_mint(issuer_url: str, count: int = 8) -> dict:
    tokens, blinded = client_tokens(count)
    blinded_b64 = []
    for b in blinded:
        v = b.encode_base64()
        blinded_b64.append(v.decode("ascii") if isinstance(v, bytes) else str(v))
    issued = http_json(
        issuer_url.rstrip("/") + "/v0/issue",
        "POST",
        {"blinded-tokens": blinded_b64},
    )
    unblinded = unblind_batch(
        tokens,
        blinded,
        issued["signed-tokens"],
        issued["proof"],
        issued["public-key"],
    )
    recs = [wallet_record(u) for u in unblinded]
    return {
        "issuer-pubkey-id": issued["issuer-pubkey-id"],
        "public-key": issued["public-key"],
        "token-epoch": issued.get("token-epoch", TOKEN_EPOCH_V0),
        "denomination": issued.get("denomination", DENOMINATION),
        "tokens": recs,
    }


def save_wallet(path: str | os.PathLike, wallet: dict) -> None:
    path = Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(wallet, f, indent=2, sort_keys=True)
        f.write("\n")


def load_wallet(path: str | os.PathLike) -> dict:
    return json.loads(Path(path).expanduser().read_text(encoding="utf-8"))


def pop_token(wallet: dict) -> dict:
    tokens = wallet.get("tokens") or []
    if not tokens:
        raise ClientError("wallet empty")
    rec = tokens.pop(0)
    return rec


def spend_token(
    storage_url: str,
    wallet: dict,
    *,
    nodeid: str,
    storage_index: bytes,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
    share_bytes: int = DEFAULT_SHARE_BYTES,
    keep_token: bool = False,
) -> dict:
    rec = wallet["tokens"][0] if keep_token else pop_token(wallet)
    unblinded = load_unblinded(rec)
    r = encode_r(
        nodeid=nodeid,
        storage_index=storage_index,
        lease_seconds=lease_seconds,
        share_bytes=share_bytes,
        token_epoch=int(wallet.get("token-epoch", TOKEN_EPOCH_V0)),
        issuer_pubkey_id=wallet["issuer-pubkey-id"],
    )
    mac = mac_k_r(unblinded, r)
    from base64 import b64encode

    body = {
        "t": rec["t"],
        "R": b64encode(r).decode("ascii"),
        "mac": mac.decode("ascii") if isinstance(mac, bytes) else str(mac),
    }
    out = http_json(storage_url.rstrip("/") + "/v0/spend", "POST", body)
    out["_t"] = rec["t"]
    out["_R"] = body["R"]
    out["_mac"] = body["mac"]
    return out


def settle_spent(issuer_url: str, preimages: list[str], extra: dict | None = None) -> dict:
    body = {"spent-preimages": preimages}
    if extra:
        body.update(extra)
    return http_json(issuer_url.rstrip("/") + "/v0/settlement", "POST", body)
