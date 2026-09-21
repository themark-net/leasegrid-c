"""Gate 0d PASS/FAIL harness. Probe → silent eject → stop paying. No slash."""

from __future__ import annotations

import os
import tempfile

from .client import save_wallet
from .crypto import (
    client_tokens,
    generate_signing_key,
    issuer_info,
    sign_blinded,
    unblind_batch,
    wallet_record,
)
from .eject import Ejected, EjectSet
from .gate import LeaseGate
from .spender import WalletSpender
from .spentset import SpentSet
from .storage_http import start_storage_http


def _ok(step: str, msg: str) -> None:
    print("PASS  %s  %s" % (step, msg), flush=True)


def _fail(step: str, msg: str) -> None:
    print("FAIL  %s  %s" % (step, msg), flush=True)


def _mint(key, count: int) -> dict:
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


def run_local() -> int:
    failed: list[str] = []
    tmp = tempfile.TemporaryDirectory(prefix="leasegrid-0d-")
    key = generate_signing_key()
    pkid = issuer_info(key)["issuer-pubkey-id"]
    node_a, node_b = "node-a", "node-b"
    gate_a = LeaseGate(key, nodeid=node_a, spent=SpentSet(os.path.join(tmp.name, "sa.json")))
    gate_b = LeaseGate(key, nodeid=node_b, spent=SpentSet(os.path.join(tmp.name, "sb.json")))
    url_a, httpd_a = start_storage_http(gate_a, "127.0.0.1:0")
    url_b, httpd_b = start_storage_http(gate_b, "127.0.0.1:0")
    wallet_path = os.path.join(tmp.name, "credit-wallet.json")
    save_wallet(wallet_path, _mint(key, 6))
    eject_path = os.path.join(tmp.name, "ejected.json")
    si1 = b"\x11" * 16
    si2 = b"\x22" * 16
    try:
        sp = WalletSpender(wallet_path)
        sp.ensure_grant_sync(url_a, node_a, pkid, si1, 64)
        sp.ensure_grant_sync(url_b, node_b, pkid, si1, 64)
        gate_a.require_allocate(si1, 64, [0])
        gate_b.require_allocate(si1, 64, [0])
        _ok("0d.1", "shares on %s and %s (storage_index=%s)" % (node_a, node_b, si1.hex()[:8]))

        httpd_b.shutdown()
        _ok("0d.2", "%s unreachable (spend HTTP stopped)" % node_b)

        s = EjectSet(eject_path, miss_limit=1, probe=lambda url: url.rstrip("/") != url_b.rstrip("/"))
        if not s.consider(node_b, url_b) or not s.is_ejected(node_b):
            _fail("0d.3", "probe did not eject %s" % node_b)
            failed.append("0d.3")
        else:
            payer = WalletSpender(wallet_path, eject=s)
            before = len(json_tokens(wallet_path))
            refused = False
            try:
                payer.ensure_grant_sync(url_b, node_b, pkid, si2, 64)
            except Ejected:
                refused = True
            after = len(json_tokens(wallet_path))
            if refused and after == before:
                _ok("0d.3", "ejected %s; no new payment (tokens still %d)" % (node_b, after))
            else:
                _fail("0d.3", "still paying ejected node (refused=%s tokens %s→%s)" % (refused, before, after))
                failed.append("0d.3")

        payer = WalletSpender(wallet_path, eject=s)
        payer.ensure_grant_sync(url_a, node_a, pkid, si2, 64)
        gate_a.require_allocate(si2, 64, [0])
        s.record_repair(ejected=node_b, method="reconstruct", before_connected=2, after_connected=1)
        _ok("0d.4", "reconstructed onto %s; happy-set 2→1" % node_a)

        blob = str(s.events()).lower()
        if "slash" in blob or "porep" in blob or "bond" in blob:
            _fail("0d.5", "eject/repair log mentioned slash/PoRep/bond")
            failed.append("0d.5")
        else:
            _ok("0d.5", "logs show eject + repair only (no slash)")
    except Exception as exc:
        _fail("0d", "%s: %s" % (type(exc).__name__, exc))
        failed.append("0d")
    finally:
        try:
            httpd_a.shutdown()
        except Exception:
            pass
        try:
            httpd_b.shutdown()
        except Exception:
            pass
        tmp.cleanup()

    if failed:
        print("GATE 0d: FAIL  %s" % ",".join(failed), flush=True)
        return 1
    print("GATE 0d: PASS", flush=True)
    return 0


def json_tokens(path: str) -> list:
    import json

    return json.loads(open(path, encoding="utf-8").read()).get("tokens") or []


def main(argv: list[str] | None = None) -> int:
    return run_local()


if __name__ == "__main__":
    raise SystemExit(main())
