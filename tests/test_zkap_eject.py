"""Gate 0d (code, not a dated PASS): probe → silent eject → stop paying that nodeid.

No slash, no PoRep, no bond. Repair is reconstruct onto remaining live nodes
(docs/08-lab.md 0d, docs/00-decision.md).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from leasegrid_zkap.client import save_wallet
from leasegrid_zkap.crypto import (
    client_tokens,
    generate_signing_key,
    issuer_info,
    sign_blinded,
    unblind_batch,
    wallet_record,
)
from leasegrid_zkap.gate import LeaseGate
from leasegrid_zkap.spentset import SpentSet
from leasegrid_zkap.storage_http import start_storage_http

NODEID_A = "node-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
NODEID_B = "node-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
SI = bytes(range(16))
SI2 = bytes(range(16, 32))


def _mint_wallet(key, count: int) -> dict:
    tokens, blinded = client_tokens(count)
    issued = sign_blinded(key, [b.encode_base64() for b in blinded])
    unblinded = unblind_batch(
        tokens, blinded, issued["signed-tokens"], issued["proof"], issued["public-key"]
    )
    return {
        "issuer-pubkey-id": issued["issuer-pubkey-id"],
        "public-key": issued["public-key"],
        "token-epoch": issued["token-epoch"],
        "denomination": issued["denomination"],
        "tokens": [wallet_record(u) for u in unblinded],
    }


def _tokens_left(path: Path) -> int:
    return len(json.loads(path.read_text())["tokens"])


@pytest.fixture
def two_nodes(tmp_path: Path):
    key = generate_signing_key()
    pkid = issuer_info(key)["issuer-pubkey-id"]
    gate_a = LeaseGate(key, nodeid=NODEID_A, spent=SpentSet(str(tmp_path / "spent-a.json")))
    gate_b = LeaseGate(key, nodeid=NODEID_B, spent=SpentSet(str(tmp_path / "spent-b.json")))
    url_a, httpd_a = start_storage_http(gate_a, "127.0.0.1:0")
    url_b, httpd_b = start_storage_http(gate_b, "127.0.0.1:0")
    yield {
        "key": key,
        "pkid": pkid,
        "a": {"gate": gate_a, "url": url_a, "httpd": httpd_a},
        "b": {"gate": gate_b, "url": url_b, "httpd": httpd_b},
    }
    httpd_a.shutdown()
    httpd_b.shutdown()


def test_failed_probe_ejects_and_stop_paying_does_not_spend(two_nodes, tmp_path: Path):
    from leasegrid_zkap.eject import Ejected, EjectSet
    from leasegrid_zkap.spender import WalletSpender

    wallet = tmp_path / "credit-wallet.json"
    save_wallet(wallet, _mint_wallet(two_nodes["key"], 4))
    ejected_path = tmp_path / "ejected.json"
    probes = {"b": False}

    def probe(url: str) -> bool:
        if url.rstrip("/") == two_nodes["b"]["url"].rstrip("/"):
            return probes["b"]
        return True

    s = EjectSet(ejected_path, miss_limit=1, probe=probe)
    assert s.consider(NODEID_B, two_nodes["b"]["url"]) is True
    assert s.is_ejected(NODEID_B)
    assert not s.is_ejected(NODEID_A)
    log = s.events()
    assert log and log[-1]["action"] == "eject"
    assert log[-1]["nodeid"] == NODEID_B
    assert "slash" not in json.dumps(log).lower()
    assert "porep" not in json.dumps(log).lower()
    assert "bond" not in json.dumps(log).lower()

    sp = WalletSpender(wallet, eject=s)
    sp.ensure_grant_sync(two_nodes["a"]["url"], NODEID_A, two_nodes["pkid"], SI, 64)
    assert _tokens_left(wallet) == 3
    with pytest.raises(Ejected):
        sp.ensure_grant_sync(two_nodes["b"]["url"], NODEID_B, two_nodes["pkid"], SI, 64)
    assert _tokens_left(wallet) == 3
    assert len(two_nodes["b"]["gate"].spent) == 0


def test_cached_grant_on_ejected_node_is_not_reused(two_nodes, tmp_path: Path):
    from leasegrid_zkap.eject import Ejected, EjectSet
    from leasegrid_zkap.spender import WalletSpender

    wallet = tmp_path / "w.json"
    save_wallet(wallet, _mint_wallet(two_nodes["key"], 2))
    s = EjectSet(tmp_path / "ejected.json")
    sp = WalletSpender(wallet, eject=s)
    sp.ensure_grant_sync(two_nodes["b"]["url"], NODEID_B, two_nodes["pkid"], SI, 64)
    assert _tokens_left(wallet) == 1
    s.eject(NODEID_B, reason="operator")
    with pytest.raises(Ejected):
        sp.ensure_grant_sync(two_nodes["b"]["url"], NODEID_B, two_nodes["pkid"], SI, 64)
    assert _tokens_left(wallet) == 1


def test_admit_restores_paying(two_nodes, tmp_path: Path):
    from leasegrid_zkap.eject import EjectSet
    from leasegrid_zkap.spender import WalletSpender

    wallet = tmp_path / "w.json"
    save_wallet(wallet, _mint_wallet(two_nodes["key"], 2))
    s = EjectSet(tmp_path / "ejected.json")
    s.eject(NODEID_B, reason="probe")
    s.admit(NODEID_B)
    assert not s.is_ejected(NODEID_B)
    sp = WalletSpender(wallet, eject=s)
    sp.ensure_grant_sync(two_nodes["b"]["url"], NODEID_B, two_nodes["pkid"], SI2, 64)
    assert _tokens_left(wallet) == 1
    two_nodes["b"]["gate"].require_allocate(SI2, 64, [0])


def test_repair_log_is_eject_plus_reconstruct_only(tmp_path: Path):
    from leasegrid_zkap.eject import EjectSet

    s = EjectSet(tmp_path / "ejected.json")
    s.eject(NODEID_B, reason="unreachable")
    s.record_repair(
        ejected=NODEID_B,
        method="reconstruct",
        before_connected=3,
        after_connected=2,
    )
    blob = json.dumps(s.events())
    assert "reconstruct" in blob
    assert "slash" not in blob.lower()
    assert s.nodeids() == [NODEID_B]


def test_plugin_client_skips_forwarding_to_ejected_node(two_nodes, tmp_path: Path):
    pytest.importorskip("allmydata")
    from leasegrid_zkap.eject import Ejected, EjectSet
    from leasegrid_zkap.plugin import plugin
    from test_zkap_spender import _FakeRref, _wait

    wallet = tmp_path / "credit-wallet.json"
    save_wallet(wallet, _mint_wallet(two_nodes["key"], 2))
    ejected_path = tmp_path / "ejected.json"
    EjectSet(ejected_path).eject(NODEID_B, reason="probe")
    rref = _FakeRref()
    ann = {
        "name": "leasegrid-zkap-v0",
        "issuer-pubkey-id": two_nodes["pkid"],
        "spend-url": two_nodes["b"]["url"],
        "nodeid": NODEID_B,
    }
    client = plugin.get_storage_client(
        {"wallet-path": str(wallet), "eject-set-path": str(ejected_path)},
        ann,
        lambda: rref,
    )
    client.spender.threaded = False
    with pytest.raises(Ejected):
        _wait(client.allocate_buckets(SI, b"r" * 32, b"c" * 32, {0}, 64, None))
    assert rref.calls == []
    assert _tokens_left(wallet) == 2


def test_check_0d_local_prints_gate_line(capsys):
    from leasegrid_zkap.check_0d import run_local

    code = run_local()
    out = capsys.readouterr().out
    assert "0d.3" in out
    assert "0d.5" in out
    assert code == 0
    assert "GATE 0d: PASS" in out
    assert "slash" not in out.lower() or "no slash" in out.lower()
