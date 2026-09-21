"""S3: WalletRpcChain against a JSON-RPC stand-in, plus SQLite backup/restore.

No monerod. The live wallet-rpc adapter is the only piece that needs block time;
this file proves the mapping and the restore drill in CI.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from leasegrid_zkap.crypto import generate_signing_key
from leasegrid_zkap.issuer import IssuerState
from leasegrid_zkap.payment import PricePolicy, Transfer, VoucherStore

PRICE = 6 * 10**9
VID = "9f3a0b1c2d3e4f50"


class FakeWallet:
    """In-memory monero-wallet-rpc: create_address / get_transfers / get_height."""

    def __init__(self) -> None:
        self.next_index = 1
        self.labels: dict[int, str] = {}
        self.addresses: dict[int, str] = {}
        self.transfers: dict[int, list[dict]] = {}
        self.pool: dict[int, list[dict]] = {}
        self.height_value = 2_000
        self.calls: list[tuple[str, dict]] = []
        self.error: str | None = None

    def call(self, method: str, params: dict | None = None) -> dict:
        params = dict(params or {})
        self.calls.append((method, params))
        if self.error:
            raise RuntimeError(self.error)
        if method == "create_address":
            idx = self.next_index
            self.next_index += 1
            addr = "4mock%08d%s" % (idx, (params.get("label") or "")[-16:])
            self.addresses[idx] = addr
            self.labels[idx] = str(params.get("label") or "")
            self.transfers.setdefault(idx, [])
            self.pool.setdefault(idx, [])
            return {"address": addr, "address_index": idx}
        if method == "get_transfers":
            indices = [int(i) for i in params.get("subaddr_indices") or []]
            out: dict[str, list] = {"in": [], "pool": []}
            for idx in indices:
                out["in"].extend(self.transfers.get(idx, []))
                out["pool"].extend(self.pool.get(idx, []))
            return out
        if method == "get_height":
            return {"height": self.height_value}
        raise RuntimeError("unknown method %s" % method)

    def pay(self, index: int, amount: int, *, confirmed: bool = False, confirmations: int = 0) -> None:
        row = {
            "amount": int(amount),
            "confirmations": int(confirmations),
            "subaddr_index": {"major": 0, "minor": int(index)},
        }
        if confirmed or confirmations:
            row["confirmations"] = confirmations or 1
            self.transfers.setdefault(index, []).append(row)
        else:
            self.pool.setdefault(index, []).append(row)

    def mine(self, blocks: int = 1) -> None:
        self.height_value += blocks
        for idx, lst in list(self.pool.items()):
            for tx in lst:
                row = dict(tx)
                row["confirmations"] = blocks
                self.transfers.setdefault(idx, []).append(row)
            self.pool[idx] = []


class _RpcHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        body = json.loads(raw.decode("utf-8") or "{}")
        method = str(body.get("method") or "")
        params = body.get("params") or {}
        backend: FakeWallet = self.server.backend  # type: ignore[attr-defined]
        try:
            result = backend.call(method, params)
            payload = {"jsonrpc": "2.0", "id": body.get("id", "0"), "result": result}
        except Exception as exc:
            payload = {
                "jsonrpc": "2.0",
                "id": body.get("id", "0"),
                "error": {"code": -1, "message": str(exc)},
            }
        out = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *_args) -> None:
        return


def _serve(backend: FakeWallet) -> tuple[str, ThreadingHTTPServer]:
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _RpcHandler)
    httpd.backend = backend  # type: ignore[attr-defined]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    host, port = httpd.server_address[:2]
    return "http://%s:%d/json_rpc" % (host, port), httpd


@pytest.fixture
def policy() -> PricePolicy:
    return PricePolicy(price_piconero=PRICE)


def test_new_address_labels_with_vid():
    from leasegrid_zkap.payment.chain_walletrpc import WalletRpcChain

    wallet = FakeWallet()
    chain = WalletRpcChain(rpc=wallet.call)
    addr, index = chain.new_address(bytes.fromhex(VID))
    assert index == 1
    assert VID in addr or wallet.labels[index] == "leasegrid:%s" % VID
    assert wallet.labels[index] == "leasegrid:%s" % VID
    assert wallet.calls[0][0] == "create_address"
    assert wallet.calls[0][1]["account_index"] == 0


def test_received_maps_pool_as_zero_conf_and_in_as_depth():
    from leasegrid_zkap.payment.chain_walletrpc import WalletRpcChain

    wallet = FakeWallet()
    chain = WalletRpcChain(rpc=wallet.call)
    _, index = chain.new_address(bytes.fromhex(VID))
    wallet.pay(index, 10**10, confirmed=False)
    wallet.pay(index, 2 * 10**10, confirmed=True, confirmations=3)
    got = chain.received(index)
    assert Transfer(10**10, 0) in got
    assert Transfer(2 * 10**10, 3) in got


def test_received_ignores_other_subaddresses():
    from leasegrid_zkap.payment.chain_walletrpc import WalletRpcChain

    wallet = FakeWallet()
    chain = WalletRpcChain(rpc=wallet.call)
    chain.new_address(bytes.fromhex(VID))
    chain.new_address(bytes.fromhex("aabbccddeeff0011"))
    wallet.pay(1, 10**10, confirmed=True, confirmations=2)
    wallet.pay(2, 9 * 10**10, confirmed=True, confirmations=8)
    only_one = chain.received(1)
    assert only_one == [Transfer(10**10, 2)]


def test_height_from_rpc():
    from leasegrid_zkap.payment.chain_walletrpc import WalletRpcChain

    wallet = FakeWallet()
    wallet.height_value = 3_141_592
    chain = WalletRpcChain(rpc=wallet.call)
    assert chain.height() == 3_141_592


def test_rpc_error_is_wallet_rpc_error():
    from leasegrid_zkap.payment.chain_walletrpc import WalletRpcChain, WalletRpcError

    wallet = FakeWallet()
    wallet.error = "busy"
    chain = WalletRpcChain(rpc=wallet.call)
    with pytest.raises(WalletRpcError):
        chain.height()


def test_http_jsonrpc_roundtrip():
    from leasegrid_zkap.payment.chain_walletrpc import WalletRpcChain

    wallet = FakeWallet()
    url, httpd = _serve(wallet)
    try:
        chain = WalletRpcChain(url)
        addr, index = chain.new_address(bytes.fromhex(VID))
        assert index == 1
        assert addr.startswith("4mock")
        wallet.pay(index, PRICE, confirmed=True, confirmations=2)
        got = chain.received(index)
        assert got == [Transfer(PRICE, 2)]
        assert chain.height() == 2_000
    finally:
        httpd.shutdown()


def test_create_quote_and_poll_via_wallet_rpc(policy: PricePolicy):
    from leasegrid_zkap.payment.chain_walletrpc import WalletRpcChain

    wallet = FakeWallet()
    chain = WalletRpcChain(rpc=wallet.call)
    store = VoucherStore()
    v = store.create_quote(
        vid=VID,
        tokens=2,
        policy=policy,
        chain=chain,
        epoch=0,
        scheme="ristretto-v0",
    )
    assert v.address == wallet.addresses[v.subaddr_index]
    assert v.state == "quoted"
    wallet.pay(v.subaddr_index, 2 * PRICE, confirmed=False)
    store.poll(chain, policy)
    assert store.get(VID).state == "seen"
    wallet.mine(2)
    store.poll(chain, policy)
    assert store.get(VID).state == "payable"
    assert store.get(VID).tokens_owed == 2


def test_issuer_reports_chain_kind_wallet_rpc():
    from leasegrid_zkap.payment.chain_walletrpc import WalletRpcChain

    chain = WalletRpcChain(rpc=FakeWallet().call)
    state = IssuerState(generate_signing_key(), chain=chain, faucet=False)
    assert state.chain_kind == "wallet-rpc"
    assert state.keys()["chain"] == "wallet-rpc"


def test_cli_accepts_wallet_rpc_and_requires_url(monkeypatch):
    from leasegrid_zkap.cli import _issuer_chain, build_parser

    monkeypatch.delenv("LEASEGRID_WALLET_RPC", raising=False)
    p = build_parser()
    args = p.parse_args(
        ["issuer", "--chain", "wallet-rpc", "--wallet-rpc-url", "http://127.0.0.1:18083/json_rpc"]
    )
    assert args.chain == "wallet-rpc"
    chain = _issuer_chain(args)
    from leasegrid_zkap.payment.chain_walletrpc import WalletRpcChain

    assert isinstance(chain, WalletRpcChain)
    missing = p.parse_args(["issuer", "--chain", "wallet-rpc"])
    with pytest.raises(SystemExit):
        _issuer_chain(missing)


def test_backup_and_restore_preserves_vouchers(tmp_path: Path, policy: PricePolicy):
    from leasegrid_zkap.payment.backup import BackupError, backup_sqlite, restore_sqlite
    from leasegrid_zkap.payment import FakeChain

    db = tmp_path / "issuer.sqlite"
    store = VoucherStore(db)
    v = store.create_quote(
        vid=VID,
        tokens=3,
        policy=policy,
        chain=FakeChain(),
        epoch=0,
        scheme="ristretto-v0",
    )
    store.close()
    bak = tmp_path / "nightly" / "issuer.sqlite"
    backup_sqlite(db, bak)
    assert bak.is_file()
    dest = tmp_path / "restored.sqlite"
    restore_sqlite(bak, dest)
    again = VoucherStore(dest)
    got = again.get(VID)
    assert got is not None
    assert got.address == v.address
    assert got.subaddr_index == v.subaddr_index
    assert got.tokens_quoted == 3
    again.close()
    with pytest.raises(BackupError):
        restore_sqlite(bak, dest)
    restore_sqlite(bak, dest, force=True)
