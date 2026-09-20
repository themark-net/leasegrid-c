"""Client mint + spend helpers. Wallet JSON lives off-git."""

from __future__ import annotations

import contextlib
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


@contextlib.contextmanager
def wallet_lock(path: str | os.PathLike):
    """Cross-process exclusive lock on a wallet file (Sync tops up while Tahoe spends).

    Uses a lock on ``<wallet>.lock`` beside the wallet so the wallet itself can be
    replaced atomically: flock on POSIX, msvcrt byte-range locking on Windows.
    """
    lock_path = Path(path).expanduser().with_name(Path(path).name + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(lock_path), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        _lock_fd(fd)
        yield
    finally:
        try:
            _unlock_fd(fd)
        finally:
            os.close(fd)


if os.name == "nt":  # pragma: no cover - exercised on the Windows CI runner
    import msvcrt

    def _lock_fd(fd: int) -> None:
        # LK_LOCK retries for ~10 s then raises; spin so a long faucet redeem
        # on the other side does not turn into an error here.
        while True:
            try:
                msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
                return
            except OSError:
                continue

    def _unlock_fd(fd: int) -> None:
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)

else:
    import fcntl

    def _lock_fd(fd: int) -> None:
        fcntl.flock(fd, fcntl.LOCK_EX)

    def _unlock_fd(fd: int) -> None:
        fcntl.flock(fd, fcntl.LOCK_UN)


def save_wallet(path: str | os.PathLike, wallet: dict) -> None:
    path = Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(wallet, f, indent=2, sort_keys=True)
        f.write("\n")
    os.replace(tmp, path)


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
