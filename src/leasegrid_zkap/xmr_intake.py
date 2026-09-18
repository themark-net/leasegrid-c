"""XMR intake: simulated view-key scan, or wallet-rpc (never mainnet)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from hashlib import sha256
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .constants import (
    ALLOWED_XMR_NETWORKS,
    BANNED_XMR_RPC_PORTS,
    CONFIRMATIONS_REQUIRED_CHAIN,
    CONFIRMATIONS_REQUIRED_SIMULATED,
    DEFAULT_XMR_NETWORK,
    VID_LEN,
)
from .errors import MainnetBanned
from .xmr_addr import encode_integrated, payment_id_of


@dataclass
class Incoming:
    txid: str
    amount_piconero: int
    payment_id: bytes
    confirmations: int
    height: int = 0


def _port_of(url: str) -> int | None:
    p = urlparse(url)
    if p.port:
        return p.port
    if p.scheme == "https":
        return 443
    if p.scheme == "http":
        return 80
    return None


def refuse_mainnet_url(url: str) -> None:
    """Fail closed before any socket. :18081/:18083 are nimo mainnet."""
    if not url or not str(url).strip():
        raise MainnetBanned("empty XMR RPC URL")
    raw = str(url).strip()
    lower = raw.lower()
    if "mainnet" in lower:
        raise MainnetBanned("URL mentions mainnet: refused")
    port = _port_of(raw)
    if port in BANNED_XMR_RPC_PORTS:
        raise MainnetBanned(
            "refusing %s (port %s is nimo mainnet monerod; see GATE0C_NETWORK_CONSTRAINT.md)"
            % (raw, port)
        )


class SimulatedIntake:
    """In-process payments. No daemon. Label every operator path SIMULATED."""

    mode = "SIMULATED"

    def __init__(
        self,
        *,
        network: str = DEFAULT_XMR_NETWORK,
        spend_pub: bytes | None = None,
        view_pub: bytes | None = None,
        confirmations_required: int = CONFIRMATIONS_REQUIRED_SIMULATED,
    ):
        if network == "mainnet":
            raise MainnetBanned("simulated intake will not use mainnet address bytes")
        if network not in ALLOWED_XMR_NETWORKS and network not in ("stagenet", "testnet"):
            raise MainnetBanned("network %r is not allowed" % network)
        self.network = network
        self.spend_pub = spend_pub or os.urandom(32)
        self.view_pub = view_pub or os.urandom(32)
        self.confirmations_required = confirmations_required
        self._payments: list[Incoming] = []

    def make_integrated(self, vid: bytes) -> str:
        if len(vid) != VID_LEN:
            raise ValueError("vid must be %d bytes" % VID_LEN)
        return encode_integrated(self.spend_pub, self.view_pub, vid, network=self.network)

    def inject(
        self,
        vid: bytes,
        amount_piconero: int,
        confirmations: int | None = None,
        txid: str | None = None,
    ) -> Incoming:
        if len(vid) != VID_LEN:
            raise ValueError("vid must be %d bytes" % VID_LEN)
        conf = self.confirmations_required if confirmations is None else int(confirmations)
        if not txid:
            txid = "sim-" + sha256(vid + str(amount_piconero).encode() + os.urandom(8)).hexdigest()
        rec = Incoming(
            txid=txid,
            amount_piconero=int(amount_piconero),
            payment_id=vid,
            confirmations=conf,
            height=1,
        )
        self._payments.append(rec)
        return rec

    def inject_address(
        self,
        integrated_address: str,
        amount_piconero: int,
        confirmations: int | None = None,
    ) -> Incoming:
        vid = payment_id_of(integrated_address)
        return self.inject(vid, amount_piconero, confirmations=confirmations)

    def scan(self, min_confirmations: int | None = None) -> list[Incoming]:
        need = self.confirmations_required if min_confirmations is None else min_confirmations
        return [p for p in self._payments if p.confirmations >= need]


class WalletRpcIntake:
    """monero-wallet-rpc JSON-RPC. Stagenet / local-dev only."""

    mode = "wallet-rpc"

    def __init__(
        self,
        url: str,
        *,
        network: str = DEFAULT_XMR_NETWORK,
        confirmations_required: int = CONFIRMATIONS_REQUIRED_CHAIN,
        timeout: float = 15.0,
    ):
        refuse_mainnet_url(url)
        if network == "mainnet":
            raise MainnetBanned("WalletRpcIntake refuses mainnet")
        self.url = url.rstrip("/")
        if not self.url.endswith("json_rpc"):
            self.url = self.url + "/json_rpc"
        refuse_mainnet_url(self.url)
        self.network = network
        self.confirmations_required = confirmations_required
        self.timeout = timeout
        # Probe nettype without ever hitting banned ports (already refused).
        self._assert_wallet_nettype()

    def _rpc(self, method: str, params: dict | None = None) -> dict:
        refuse_mainnet_url(self.url)
        payload = json.dumps(
            {"jsonrpc": "2.0", "id": "0", "method": method, "params": params or {}}
        ).encode("utf-8")
        req = Request(
            self.url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(req, timeout=self.timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        if body.get("error"):
            raise RuntimeError("wallet-rpc %s: %s" % (method, body["error"]))
        return body.get("result") or {}

    def _assert_wallet_nettype(self) -> None:
        # wallet-rpc 0.18+: get_address works; some builds expose nettype via
        # get_info if running as daemon. Prefer get_address + optional get_info.
        try:
            info = self._rpc("get_info")
        except Exception:
            info = {}
        net = str(info.get("nettype") or info.get("net_type") or self.network).lower()
        if net in ("mainnet", "main"):
            raise MainnetBanned("wallet-rpc nettype is mainnet; refused")
        if net and net not in ALLOWED_XMR_NETWORKS and net != self.network:
            # Unknown nettype: keep configured network if it is allowed.
            if self.network not in ALLOWED_XMR_NETWORKS:
                raise MainnetBanned("wallet-rpc nettype %r refused" % net)

    def make_integrated(self, vid: bytes) -> str:
        if len(vid) != VID_LEN:
            raise ValueError("vid must be %d bytes" % VID_LEN)
        out = self._rpc("make_integrated_address", {"payment_id": vid.hex()})
        addr = out.get("integrated_address") or out.get("integratedAddress")
        if not addr:
            raise RuntimeError("make_integrated_address returned no address")
        got = payment_id_of(addr)
        if got != vid:
            raise RuntimeError("wallet integrated address payment id != vid")
        return addr

    def scan(self, min_confirmations: int | None = None) -> list[Incoming]:
        need = self.confirmations_required if min_confirmations is None else min_confirmations
        result = self._rpc("get_transfers", {"in": True, "pool": True})
        rows = []
        for key in ("in", "pool"):
            for item in result.get(key) or []:
                pid_hex = str(item.get("payment_id") or "").replace(" ", "")
                if len(pid_hex) != 16:
                    continue
                try:
                    pid = bytes.fromhex(pid_hex)
                except ValueError:
                    continue
                conf = int(item.get("confirmations") or 0)
                if key == "pool":
                    conf = 0
                if conf < need:
                    continue
                rows.append(
                    Incoming(
                        txid=str(item.get("txid") or item.get("tx_hash") or ""),
                        amount_piconero=int(item.get("amount") or 0),
                        payment_id=pid,
                        confirmations=conf,
                        height=int(item.get("height") or 0),
                    )
                )
        return rows

    def inject(self, *args, **kwargs):
        raise RuntimeError("inject is SIMULATED-only")


def make_intake(kind: str, *, xmr_rpc: str = "", network: str = DEFAULT_XMR_NETWORK):
    kind = (kind or "simulated").strip().lower()
    if kind in ("simulated", "sim", "none", ""):
        return SimulatedIntake(network=network)
    if kind in ("rpc", "wallet-rpc", "wallet_rpc"):
        if not xmr_rpc:
            raise MainnetBanned("wallet-rpc intake needs --xmr-rpc (not :18081)")
        refuse_mainnet_url(xmr_rpc)
        return WalletRpcIntake(xmr_rpc, network=network)
    raise ValueError("unknown intake %r (simulated|rpc)" % kind)
