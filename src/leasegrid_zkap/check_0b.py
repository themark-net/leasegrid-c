"""Gate 0b PASS/FAIL harness. Prints one line per step. No stub success."""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import traceback
from base64 import b64encode

from .client import ClientError, faucet_mint, http_json, settle_spent, spend_token
from .crypto import load_unblinded, mac_k_r
from .constants import DEFAULT_LEASE_SECONDS, DEFAULT_SHARE_BYTES, DENOMINATION, DOMAIN
from .crypto import generate_signing_key, load_signing_key, save_signing_key
from .errors import ZKAPRequired
from .gate import LeaseGate, install_on_storage_server
from .issuer import start_issuer
from .r_bind import encode_r
from .spentset import SpentSet
from .storage_http import start_storage_http


def _ok(step: str, msg: str) -> None:
    print("PASS  %s  %s" % (step, msg), flush=True)


def _fail(step: str, msg: str) -> None:
    print("FAIL  %s  %s" % (step, msg), flush=True)


def _try_tahoe_backend(storedir: str):
    try:
        from allmydata.storage.server import StorageServer
    except Exception as e:
        return None, "allmydata.storage.server unavailable: %s" % e
    nodeid = b"\x00" * 20
    ss = StorageServer(storedir, nodeid)
    return ss, "tahoe StorageServer 1.20 wrap"


def run_local() -> int:
    failed = []
    tmp = tempfile.TemporaryDirectory(prefix="leasegrid-0b-")
    key_path = os.path.join(tmp.name, "issuer.signing.key")
    spent_path = os.path.join(tmp.name, "spent.json")
    storedir = os.path.join(tmp.name, "store")
    os.makedirs(storedir, exist_ok=True)

    key = generate_signing_key()
    save_signing_key(key_path, key)
    key = load_signing_key(key_path)
    nodeid = "lab-storage-0"

    backend, backend_note = _try_tahoe_backend(storedir)
    gate = LeaseGate(key, nodeid=nodeid, spent=SpentSet(spent_path), backend=backend)
    if backend is not None:
        install_on_storage_server(backend, gate)

    issuer_state, issuer_httpd = start_issuer(key, "127.0.0.1:0")
    storage_url, storage_httpd = start_storage_http(gate, "127.0.0.1:0")
    issuer_url = issuer_state.listen

    try:
        # 0b.1
        info = http_json(issuer_url + "/v0/info")
        pkid = info.get("issuer-pubkey-id")
        if not pkid or info.get("domain") != DOMAIN:
            _fail("0b.1", "issuer info missing pubkey id or domain")
            failed.append("0b.1")
        else:
            _ok("0b.1", "issuer %s pubkey-id=%s" % (issuer_url, pkid))

        # 0b.2 anonymous allocate fails
        si = os.urandom(16)
        step2_ok = True
        try:
            gate.lab_allocate(si, [0], 64)
            _fail("0b.2", "anonymous allocate succeeded")
            failed.append("0b.2")
            step2_ok = False
        except ZKAPRequired:
            pass
        if step2_ok and backend is not None:
            try:
                backend.allocate_buckets(si, b"\x11" * 32, b"\x22" * 32, {0}, 64)
                _fail("0b.2", "wrapped Tahoe allocate_buckets allowed unpaid")
                failed.append("0b.2")
                step2_ok = False
            except ZKAPRequired:
                pass
        if step2_ok:
            try:
                http_json(
                    storage_url + "/v0/lab/allocate",
                    "POST",
                    {"storage_index": si.hex(), "sharenums": [0], "allocated_size": 64},
                )
                _fail("0b.2", "HTTP anonymous allocate succeeded")
                failed.append("0b.2")
                step2_ok = False
            except ClientError as e:
                if "403" not in str(e) and "refused" not in str(e):
                    _fail("0b.2", "unexpected error: %s" % e)
                    failed.append("0b.2")
                    step2_ok = False
        if step2_ok:
            if backend is None:
                _fail(
                    "0b.2",
                    "Tahoe StorageServer not importable; cannot claim plugin wrap",
                )
                failed.append("0b.2")
            else:
                _ok("0b.2", "anonymous allocate refused (%s)" % backend_note)

        # 0b.3 faucet mint
        wallet = faucet_mint(issuer_url, count=4)
        n = len(wallet.get("tokens") or [])
        if n != 4 or wallet.get("denomination") != DENOMINATION:
            _fail("0b.3", "mint returned %s tokens denom=%r" % (n, wallet.get("denomination")))
            failed.append("0b.3")
        else:
            _ok(
                "0b.3",
                "minted %s tokens; %s; pubkey-id=%s"
                % (n, DENOMINATION, wallet["issuer-pubkey-id"]),
            )

        # 0b.4 spend + allocate; replay different R; idempotent
        try:
            spent_rec = wallet["tokens"][0]
            first = spend_token(
                storage_url,
                wallet,
                nodeid=nodeid,
                storage_index=si,
                lease_seconds=DEFAULT_LEASE_SECONDS,
                share_bytes=DEFAULT_SHARE_BYTES,
            )
            alloc = http_json(
                storage_url + "/v0/lab/allocate",
                "POST",
                {"storage_index": si.hex(), "sharenums": [0], "allocated_size": 64},
            )
            if not alloc.get("allocated") and not alloc.get("already-have"):
                raise ClientError("allocate returned empty: %r" % alloc)
            again = http_json(
                storage_url + "/v0/spend",
                "POST",
                {"t": first["_t"], "R": first["_R"], "mac": first["_mac"]},
            )
            if not again.get("ok"):
                raise ClientError("idempotent spend not ok: %r" % again)
            alloc2 = http_json(
                storage_url + "/v0/lab/allocate",
                "POST",
                {"storage_index": si.hex(), "sharenums": [0], "allocated_size": 64},
            )
            if not alloc2.get("allocated") and not alloc2.get("already-have") and alloc2.get("ok") is False:
                raise ClientError("idempotent allocate failed: %r" % alloc2)

            # different R (different SI) with a *valid* MAC_K(R2) on the same t
            other_si = os.urandom(16)
            r2 = encode_r(
                nodeid=nodeid,
                storage_index=other_si,
                lease_seconds=DEFAULT_LEASE_SECONDS,
                share_bytes=DEFAULT_SHARE_BYTES,
                issuer_pubkey_id=wallet["issuer-pubkey-id"],
            )
            unblinded = load_unblinded(spent_rec)
            mac2 = mac_k_r(unblinded, r2)
            mac2_s = mac2.decode("ascii") if isinstance(mac2, bytes) else str(mac2)
            try:
                http_json(
                    storage_url + "/v0/spend",
                    "POST",
                    {
                        "t": first["_t"],
                        "R": b64encode(r2).decode("ascii"),
                        "mac": mac2_s,
                    },
                )
                raise ClientError("replay different R was accepted")
            except ClientError as e:
                if "replay different R was accepted" in str(e):
                    raise
                if "403" not in str(e) and "replay" not in str(e).lower():
                    raise ClientError("expected replay fail, got: %s" % e)

            _ok(
                "0b.4",
                "allocate ok; idempotent same R ok; different R refused (backend=%s)"
                % alloc.get("backend"),
            )
        except Exception as e:
            _fail("0b.4", "%s" % e)
            traceback.print_exc()
            failed.append("0b.4")

        # 0b.5 issuer does not receive R
        try:
            bundle = http_json(storage_url + "/v0/settlement-bundle")
            if "R" in bundle or "mac" in bundle or "storage_index" in bundle:
                raise ClientError("settlement bundle leaked R fields: %s" % list(bundle))
            pre = bundle.get("spent-preimages") or []
            if not pre:
                raise ClientError("no spent preimages to settle")
            good = settle_spent(issuer_url, pre)
            if good.get("stored-r") is not False:
                raise ClientError("issuer stored-r not false: %r" % good)
            try:
                settle_spent(issuer_url, pre, extra={"R": first["_R"]})
                raise ClientError("issuer accepted settlement with R")
            except ClientError as e:
                if "must not receive R" not in str(e) and "400" not in str(e):
                    raise ClientError("expected R reject, got: %s" % e)
            stats = http_json(issuer_url + "/v0/info")
            if int(stats.get("settlement-rejected-r") or 0) < 1:
                raise ClientError("issuer did not count rejected R")
            if "R" in (stats.get("last-settlement-keys") or []) and stats.get("settlement-rejected-r") < 1:
                raise ClientError("issuer kept R")
            _ok(
                "0b.5",
                "settlement t-only accepted; R rejected; pubkey-id=%s"
                % stats.get("issuer-pubkey-id"),
            )
        except Exception as e:
            _fail("0b.5", "%s" % e)
            traceback.print_exc()
            failed.append("0b.5")

    finally:
        issuer_httpd.shutdown()
        storage_httpd.shutdown()
        tmp.cleanup()

    if failed:
        print("GATE 0b: FAIL  (%s)" % ", ".join(failed), flush=True)
        return 1
    print("GATE 0b: PASS", flush=True)
    return 0


def run_live(issuer_url: str, storage_url: str, nodeid: str | None) -> int:
    failed = []
    try:
        info = http_json(issuer_url.rstrip("/") + "/v0/info")
        pkid = info.get("issuer-pubkey-id")
        if not pkid:
            _fail("0b.1", "no issuer-pubkey-id at %s" % issuer_url)
            failed.append("0b.1")
        else:
            _ok("0b.1", "issuer %s pubkey-id=%s" % (issuer_url, pkid))
    except Exception as e:
        _fail("0b.1", "%s" % e)
        print("GATE 0b: FAIL  (issuer unreachable)", flush=True)
        return 1

    st = http_json(storage_url.rstrip("/") + "/v0/info")
    nodeid = nodeid or st.get("nodeid")
    if not nodeid:
        _fail("0b.2", "storage nodeid unknown")
        failed.append("0b.2")
        print("GATE 0b: FAIL", flush=True)
        return 1

    si = os.urandom(16)
    try:
        http_json(
            storage_url.rstrip("/") + "/v0/lab/allocate",
            "POST",
            {"storage_index": si.hex(), "sharenums": [0], "allocated_size": 64},
        )
        _fail("0b.2", "anonymous allocate succeeded on live storage")
        failed.append("0b.2")
    except ClientError as e:
        if "403" in str(e):
            _ok("0b.2", "anonymous allocate refused at %s nodeid=%s" % (storage_url, nodeid))
        else:
            _fail("0b.2", "%s" % e)
            failed.append("0b.2")

    try:
        wallet = faucet_mint(issuer_url, count=4)
        _ok("0b.3", "minted %s tokens; %s" % (len(wallet["tokens"]), wallet.get("denomination")))
    except Exception as e:
        _fail("0b.3", "%s" % e)
        failed.append("0b.3")
        wallet = {"tokens": [], "issuer-pubkey-id": pkid}

    try:
        spent_rec = wallet["tokens"][0]
        first = spend_token(
            storage_url,
            wallet,
            nodeid=nodeid,
            storage_index=si,
            lease_seconds=DEFAULT_LEASE_SECONDS,
            share_bytes=DEFAULT_SHARE_BYTES,
        )
        alloc = http_json(
            storage_url.rstrip("/") + "/v0/lab/allocate",
            "POST",
            {"storage_index": si.hex(), "sharenums": [0], "allocated_size": 64},
        )
        http_json(
            storage_url.rstrip("/") + "/v0/spend",
            "POST",
            {"t": first["_t"], "R": first["_R"], "mac": first["_mac"]},
        )
        other_si = os.urandom(16)
        r2 = encode_r(
            nodeid=nodeid,
            storage_index=other_si,
            lease_seconds=DEFAULT_LEASE_SECONDS,
            share_bytes=DEFAULT_SHARE_BYTES,
            issuer_pubkey_id=wallet["issuer-pubkey-id"],
        )
        mac2 = mac_k_r(load_unblinded(spent_rec), r2)
        mac2_s = mac2.decode("ascii") if isinstance(mac2, bytes) else str(mac2)
        try:
            http_json(
                storage_url.rstrip("/") + "/v0/spend",
                "POST",
                {"t": first["_t"], "R": b64encode(r2).decode("ascii"), "mac": mac2_s},
            )
            raise ClientError("live replay different R accepted")
        except ClientError as e:
            if "live replay different R accepted" in str(e):
                raise
            if "403" not in str(e) and "replay" not in str(e).lower():
                raise
        _ok("0b.4", "live spend+allocate ok; replay different R refused; backend=%s" % alloc.get("backend"))
    except Exception as e:
        _fail("0b.4", "%s" % e)
        failed.append("0b.4")
        first = {"_R": ""}

    try:
        bundle = http_json(storage_url.rstrip("/") + "/v0/settlement-bundle")
        settle_spent(issuer_url, bundle["spent-preimages"])
        try:
            settle_spent(issuer_url, bundle["spent-preimages"], extra={"R": first.get("_R") or "AAAA"})
            raise ClientError("issuer accepted R")
        except ClientError as e:
            if "issuer accepted R" in str(e):
                raise
        stats = http_json(issuer_url.rstrip("/") + "/v0/info")
        if int(stats.get("settlement-rejected-r") or 0) < 1:
            raise ClientError("live issuer did not reject R")
        _ok("0b.5", "live settlement t-only; R rejected")
    except Exception as e:
        _fail("0b.5", "%s" % e)
        failed.append("0b.5")

    if failed:
        print("GATE 0b: FAIL  (%s)" % ", ".join(failed), flush=True)
        return 1
    print("GATE 0b: PASS", flush=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Leasegrid gate 0b PASS/FAIL checks")
    p.add_argument("--live", action="store_true", help="use --issuer and --storage URLs")
    p.add_argument("--issuer", default="", help="issuer base URL")
    p.add_argument("--storage", default="", help="storage-gate base URL")
    p.add_argument("--nodeid", default="", help="storage nodeid (my_nodeid string)")
    args = p.parse_args(argv)
    if args.live:
        if not args.issuer or not args.storage:
            print("FAIL  --live requires --issuer and --storage", flush=True)
            return 2
        return run_live(args.issuer, args.storage, args.nodeid or None)
    return run_local()


if __name__ == "__main__":
    sys.exit(main())
