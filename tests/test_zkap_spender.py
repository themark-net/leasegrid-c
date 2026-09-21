"""Client-side spend-before-write: WalletSpender against a real LeaseGate, and the
Tahoe plugin's paying storage client against a fake remote reference."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from leasegrid_zkap.client import ClientError, save_wallet
from leasegrid_zkap.crypto import (
    client_tokens,
    generate_signing_key,
    issuer_info,
    sign_blinded,
    unblind_batch,
    wallet_record,
)
from leasegrid_zkap.gate import LeaseGate
from leasegrid_zkap.spender import NoCredit, SpendRefused, WalletSpender, WrongIssuer
from leasegrid_zkap.spentset import SpentSet
from leasegrid_zkap.storage_http import start_storage_http

NODEID = "node1aaaaaaaaaaaaaaaaaaaaaaaaaaaa"
SI = bytes(range(16))
SI2 = bytes(range(16, 32))


def _mint_wallet(key, count: int) -> dict:
    tokens, blinded = client_tokens(count)
    issued = sign_blinded(key, [b.encode_base64() for b in blinded])
    unblinded = unblind_batch(tokens, blinded, issued["signed-tokens"], issued["proof"],
                              issued["public-key"])
    return {
        "issuer-pubkey-id": issued["issuer-pubkey-id"],
        "public-key": issued["public-key"],
        "token-epoch": issued["token-epoch"],
        "denomination": issued["denomination"],
        "tokens": [wallet_record(u) for u in unblinded],
    }


@pytest.fixture
def node(tmp_path: Path):
    key = generate_signing_key()
    gate = LeaseGate(key, nodeid=NODEID, spent=SpentSet(str(tmp_path / "spent.json")))
    url, httpd = start_storage_http(gate, "tcp:0:interface=127.0.0.1")
    yield {"key": key, "gate": gate, "url": url, "pubkey_id": issuer_info(key)["issuer-pubkey-id"]}
    httpd.shutdown()


@pytest.fixture
def wallet_path(tmp_path: Path, node) -> Path:
    p = tmp_path / "home" / "credit-wallet.json"
    save_wallet(p, _mint_wallet(node["key"], 3))
    return p


def _tokens_left(path: Path) -> int:
    return len(json.loads(path.read_text())["tokens"])


def test_spend_once_per_node_and_storage_index(node, wallet_path: Path, tmp_path: Path):
    sp = WalletSpender(wallet_path, recent_path=tmp_path / "home" / "credit-recent.json")
    g1 = sp.ensure_grant_sync(node["url"], NODEID, node["pubkey_id"], SI, 64)
    assert _tokens_left(wallet_path) == 2
    # Same SI again (retry / more shares / mutable rewrite): cached, no spend.
    g2 = sp.ensure_grant_sync(node["url"], NODEID, node["pubkey_id"], SI, 4096)
    assert g2["t"] == g1["t"]
    assert _tokens_left(wallet_path) == 2
    # Different SI: spends.
    sp.ensure_grant_sync(node["url"], NODEID, node["pubkey_id"], SI2, 64)
    assert _tokens_left(wallet_path) == 1
    # Node now has grants for both -> its gate lets allocate through.
    node["gate"].require_allocate(SI, 64, [0])
    node["gate"].require_allocate(SI2, 64, [0])
    assert sp.grants_count() == 2
    recent = json.loads((tmp_path / "home" / "credit-recent.json").read_text())["events"]
    assert recent[0]["tokens"] == -1 and "Lease on" in recent[0]["title"]


def test_wallet_empty_is_no_credit_and_records_refusal(node, tmp_path: Path):
    p = tmp_path / "w.json"
    save_wallet(p, {"issuer-pubkey-id": node["pubkey_id"], "token-epoch": 0, "tokens": []})
    sp = WalletSpender(p, recent_path=tmp_path / "recent.json")
    with pytest.raises(NoCredit):
        sp.ensure_grant_sync(node["url"], NODEID, node["pubkey_id"], SI, 64)
    recent = json.loads((tmp_path / "recent.json").read_text())["events"]
    assert "out of credit" in recent[0]["title"]
    with pytest.raises(NoCredit):
        WalletSpender(tmp_path / "missing.json").ensure_grant_sync(
            node["url"], NODEID, node["pubkey_id"], SI, 64
        )


def test_wrong_issuer_refused_without_spending(node, tmp_path: Path):
    other = generate_signing_key()
    p = tmp_path / "w.json"
    save_wallet(p, _mint_wallet(other, 2))
    sp = WalletSpender(p)
    with pytest.raises(WrongIssuer):
        sp.ensure_grant_sync(node["url"], NODEID, node["pubkey_id"], SI, 64)
    assert _tokens_left(p) == 2


def test_network_error_puts_token_back(node, wallet_path: Path):
    def boom(url, method, body):
        raise ClientError("unreachable %s: connection refused" % url)

    sp = WalletSpender(wallet_path, http=boom)
    with pytest.raises(ClientError):
        sp.ensure_grant_sync("http://127.0.0.1:1", NODEID, node["pubkey_id"], SI, 64)
    assert _tokens_left(wallet_path) == 3
    assert sp.grants_count() == 0


def test_forged_wallet_is_rejected_and_parked(node, tmp_path: Path):
    """A wallet whose tokens the node's issuer never signed: 403, token parked, not retried."""
    forged_key = generate_signing_key()
    w = _mint_wallet(forged_key, 1)
    w["issuer-pubkey-id"] = node["pubkey_id"]  # lie about the issuer
    p = tmp_path / "w.json"
    save_wallet(p, w)
    sp = WalletSpender(p)
    with pytest.raises(SpendRefused):
        sp.ensure_grant_sync(node["url"], NODEID, node["pubkey_id"], SI, 64)
    data = json.loads(p.read_text())
    assert data["tokens"] == []
    assert len(data["rejected"]) == 1


def test_write_bigger_than_a_token_is_refused_client_side(node, wallet_path: Path):
    sp = WalletSpender(wallet_path)
    with pytest.raises(NoCredit):
        sp.ensure_grant_sync(node["url"], NODEID, node["pubkey_id"], SI, 2**31)
    assert _tokens_left(wallet_path) == 3


def test_shared_spender_keeps_exact_accounting_under_concurrency(node, tmp_path: Path):
    """Regression: per-node spenders raced on the wallet file (15 node spends for 7 tokens)."""
    import threading

    p = tmp_path / "home" / "credit-wallet.json"
    save_wallet(p, _mint_wallet(node["key"], 12))
    spenders = [WalletSpender.shared(p, recent_path=tmp_path / "home" / "recent.json") for _ in range(3)]
    assert spenders[0] is spenders[1] is spenders[2]
    sis = [bytes([i]) * 16 for i in range(9)]
    errors: list[BaseException] = []

    def work(sp, si):
        try:
            sp.ensure_grant_sync(node["url"], NODEID, node["pubkey_id"], si, 64)
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=work, args=(spenders[i % 3], si)) for i, si in enumerate(sis)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    assert _tokens_left(p) == 3
    assert spenders[0].grants_count() == 9
    assert len(node["gate"].spent) == 9  # every node-side spend is backed by exactly one token


# -- plugin client -----------------------------------------------------------


class _FakeRref:
    def __init__(self):
        self.calls = []

    def callRemote(self, name, *args, **kwargs):
        from twisted.internet.defer import succeed

        self.calls.append((name, args))
        return succeed({"remote": name})


def _wait(d):
    """Extract the result of an already-fired Deferred (spender runs unthreaded in tests)."""
    from twisted.python.failure import Failure

    out = {}
    d.addBoth(lambda r: out.setdefault("r", r))
    assert "r" in out, "Deferred did not fire synchronously"
    if isinstance(out["r"], Failure):
        out["r"].raiseException()
    return out["r"]


def test_plugin_client_pays_then_forwards_writes(node, wallet_path: Path, tmp_path: Path):
    pytest.importorskip("allmydata")
    from leasegrid_zkap.plugin import plugin

    rref = _FakeRref()
    ann = {
        "name": "leasegrid-zkap-v0",
        "storage-server-FURL": "pb://x@127.0.0.1:1/y",
        "issuer-pubkey-id": node["pubkey_id"],
        "spend-url": node["url"],
        "nodeid": NODEID,
    }
    cfg = {"wallet-path": str(wallet_path), "recent-path": str(tmp_path / "recent.json")}
    client = plugin.get_storage_client(cfg, ann, lambda: rref)
    client.spender.threaded = False

    from allmydata.interfaces import IStorageServer

    assert IStorageServer.providedBy(client)

    # reads are free
    _wait(client.get_buckets(SI))
    assert rref.calls[-1][0] == "get_buckets"
    assert _tokens_left(wallet_path) == 3

    # allocate pays first, then forwards
    _wait(client.allocate_buckets(SI, b"r" * 32, b"c" * 32, {0}, 64, None))
    assert rref.calls[-1][0] == "allocate_buckets"
    assert _tokens_left(wallet_path) == 2
    node["gate"].require_allocate(SI, 64, [0])  # node side has the grant

    # mutable write on a new SI pays again; same SI later does not
    tw = {0: ([], [(0, b"hello")], None)}
    _wait(client.slot_testv_and_readv_and_writev(SI2, (b"w", b"r", b"c"), tw, []))
    assert _tokens_left(wallet_path) == 1
    _wait(client.slot_testv_and_readv_and_writev(SI2, (b"w", b"r", b"c"), tw, []))
    assert _tokens_left(wallet_path) == 1
    assert rref.calls[-1][0] == "slot_testv_and_readv_and_writev"


def test_plugin_client_without_spend_url_fails_writes_clearly(node, wallet_path: Path):
    pytest.importorskip("allmydata")
    from leasegrid_zkap.plugin import plugin

    rref = _FakeRref()
    ann = {"name": "leasegrid-zkap-v0", "issuer-pubkey-id": node["pubkey_id"]}
    client = plugin.get_storage_client({"wallet-path": str(wallet_path)}, ann, lambda: rref)
    client.spender.threaded = False
    with pytest.raises(NoCredit):
        _wait(client.allocate_buckets(SI, b"r" * 32, b"c" * 32, {0}, 64, None))
    assert rref.calls == []
    assert _tokens_left(wallet_path) == 3


def test_plugin_server_announces_spend_url_and_nodeid(tmp_path: Path):
    pytest.importorskip("allmydata")
    from leasegrid_zkap.crypto import save_signing_key
    from leasegrid_zkap.plugin import plugin

    key = generate_signing_key()
    key_path = tmp_path / "issuer.key"
    save_signing_key(key_path, key)

    from allmydata.storage.server import StorageServer

    ss = StorageServer(str(tmp_path / "storage"), b"\x01" * 20)

    cfg = {
        "issuer-signing-key-file": str(key_path),
        "spend-listen": "tcp:0:interface=127.0.0.1",
        "spent-set-path": str(tmp_path / "spent.json"),
    }
    result = _wait(plugin.get_storage_server(cfg, lambda: ss))
    ann = result.announcement
    assert ann["spend-url"].startswith("http://127.0.0.1:")
    assert ann["nodeid"] and ann["issuer-pubkey-id"] == issuer_info(key)["issuer-pubkey-id"]


def test_wallet_lock_excludes_a_second_process(tmp_path: Path):
    """flock on POSIX, msvcrt on Windows: a second holder must wait for the first."""
    import subprocess
    import sys
    import time

    from leasegrid_zkap.client import wallet_lock

    wallet = tmp_path / "wallet.json"
    marker = tmp_path / "second-got-lock"
    child = (
        "import sys, pathlib; from leasegrid_zkap.client import wallet_lock\n"
        "with wallet_lock(sys.argv[1]):\n"
        "    pathlib.Path(sys.argv[2]).write_text('x')\n"
    )
    with wallet_lock(wallet):
        proc = subprocess.Popen([sys.executable, "-c", child, str(wallet), str(marker)])
        time.sleep(1.5)
        assert proc.poll() is None, "second process got the lock while the first held it"
        assert not marker.exists()
    assert proc.wait(timeout=20) == 0
    assert marker.exists()
    assert (tmp_path / "wallet.json.lock").exists()
