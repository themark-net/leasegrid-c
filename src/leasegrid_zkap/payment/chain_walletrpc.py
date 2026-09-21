"""WalletRpcChain: ChainWatcher over monero-wallet-rpc (docs/07-payment.md §10).

View-only wallet. The only RPC methods used are create_address, get_transfers
(in + pool, filtered by subaddr_indices), and get_height. Tests inject `rpc`
so CI never needs monerod.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Optional
from urllib.error import HTTPError, URLError
from urllib.request import (
    HTTPBasicAuthHandler,
    HTTPDigestAuthHandler,
    HTTPPasswordMgrWithDefaultRealm,
    Request,
    build_opener,
)

from .chain import Transfer

RpcFn = Callable[[str, dict], dict]


class WalletRpcError(Exception):
    pass


def _normalize_rpc_url(url: str) -> str:
    u = url.rstrip("/")
    if u and not u.endswith("/json_rpc"):
        u = u + "/json_rpc"
    return u


def _minor(tx: dict) -> Optional[int]:
    idx = tx.get("subaddr_index")
    if isinstance(idx, dict) and idx.get("minor") is not None:
        return int(idx["minor"])
    if isinstance(idx, int):
        return idx
    return None


class WalletRpcChain:
    def __init__(
        self,
        url: str = "",
        *,
        account_index: int = 0,
        user: Optional[str] = None,
        password: Optional[str] = None,
        timeout: float = 15.0,
        rpc: Optional[RpcFn] = None,
    ) -> None:
        self.url = _normalize_rpc_url(url)
        self.account_index = int(account_index)
        self.user = user or None
        self.password = password or ""
        self.timeout = timeout
        self._rpc_fn = rpc
        if self._rpc_fn is None and not self.url:
            raise WalletRpcError("wallet-rpc URL is required")

    def new_address(self, vid: bytes) -> tuple[str, int]:
        r = self._rpc(
            "create_address",
            {"account_index": self.account_index, "label": "leasegrid:%s" % vid.hex()},
        )
        try:
            return str(r["address"]), int(r["address_index"])
        except (KeyError, TypeError, ValueError) as exc:
            raise WalletRpcError("create_address: bad result %r" % r) from exc

    def received(self, index: int) -> list[Transfer]:
        r = self._rpc(
            "get_transfers",
            {
                "in": True,
                "pool": True,
                "account_index": self.account_index,
                "subaddr_indices": [int(index)],
            },
        )
        out: list[Transfer] = []
        for tx in r.get("pool") or []:
            if not isinstance(tx, dict):
                continue
            minor = _minor(tx)
            if minor is not None and minor != int(index):
                continue
            out.append(Transfer(int(tx["amount"]), 0))
        for tx in r.get("in") or []:
            if not isinstance(tx, dict):
                continue
            minor = _minor(tx)
            if minor is not None and minor != int(index):
                continue
            out.append(Transfer(int(tx["amount"]), int(tx.get("confirmations") or 0)))
        return out

    def height(self) -> int:
        r = self._rpc("get_height")
        try:
            return int(r["height"])
        except (KeyError, TypeError, ValueError) as exc:
            raise WalletRpcError("get_height: bad result %r" % r) from exc

    def _rpc(self, method: str, params: Optional[dict] = None) -> dict:
        params = dict(params or {})
        if self._rpc_fn is not None:
            try:
                result = self._rpc_fn(method, params)
            except WalletRpcError:
                raise
            except Exception as exc:
                raise WalletRpcError("%s: %s" % (method, exc)) from exc
            if not isinstance(result, dict):
                raise WalletRpcError("%s: expected object, got %r" % (method, result))
            return result
        return self._http_rpc(method, params)

    def _http_rpc(self, method: str, params: dict) -> dict:
        payload = {"jsonrpc": "2.0", "id": "0", "method": method, "params": params}
        raw = json.dumps(payload).encode("utf-8")
        req = Request(
            self.url,
            data=raw,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        try:
            opener = self._opener()
            with opener.open(req, timeout=self.timeout) as resp:
                body = resp.read()
        except HTTPError as exc:
            err = exc.read().decode("utf-8", "replace")
            raise WalletRpcError("%s -> %s %s" % (method, exc.code, err)) from exc
        except URLError as exc:
            raise WalletRpcError("unreachable %s: %s" % (self.url, exc.reason)) from exc
        except OSError as exc:
            raise WalletRpcError("%s failed: %s" % (method, exc)) from exc
        try:
            parsed: Any = json.loads(body.decode("utf-8") or "{}")
        except (UnicodeDecodeError, ValueError) as exc:
            raise WalletRpcError("%s returned non-JSON" % method) from exc
        if not isinstance(parsed, dict):
            raise WalletRpcError("%s: bad JSON-RPC envelope" % method)
        if parsed.get("error"):
            err = parsed["error"]
            if isinstance(err, dict):
                raise WalletRpcError("%s: %s" % (method, err.get("message") or err))
            raise WalletRpcError("%s: %s" % (method, err))
        result = parsed.get("result")
        if not isinstance(result, dict):
            raise WalletRpcError("%s: missing result" % method)
        return result

    def _opener(self):
        if not self.user:
            return build_opener()
        pm = HTTPPasswordMgrWithDefaultRealm()
        pm.add_password(None, self.url, self.user, self.password)
        return build_opener(HTTPDigestAuthHandler(pm), HTTPBasicAuthHandler(pm))
