"""Gate 0c PASS/FAIL harness. Prints one line per step. No stub success.

Default intake is SIMULATED (no chain). Never talks to :18081/:18083.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import traceback

from .check_0b import _try_tahoe_backend
from .client import (
    ClientError,
    http_json,
    quote_tokens,
    redeem_vid,
    simulate_pay,
    spend_token,
)
from .constants import (
    BANNED_XMR_RPC_PORTS,
    DEFAULT_LEASE_SECONDS,
    DEFAULT_SHARE_BYTES,
    DENOMINATION,
    PICONERO_PER_TOKEN,
    VID_LEN,
)
from .crypto import generate_signing_key, load_signing_key, save_signing_key
from .errors import MainnetBanned, ZKAPRequired
from .gate import LeaseGate
from .issuer import start_issuer
from .keccak import keccak256
from .spentset import SpentSet
from .storage_http import start_storage_http
from .xmr_addr import decode_address, payment_id_of
from .xmr_intake import refuse_mainnet_url


def _ok(step: str, msg: str) -> None:
    print("PASS  %s  %s" % (step, msg), flush=True)


def _fail(step: str, msg: str) -> None:
    print("FAIL  %s  %s" % (step, msg), flush=True)


def _ban_mainnet_ports() -> str | None:
    for port in sorted(BANNED_XMR_RPC_PORTS):
        url = "http://127.0.0.1:%d/json_rpc" % port
        try:
            refuse_mainnet_url(url)
            return "did not refuse %s" % url
        except MainnetBanned:
            pass
    try:
        refuse_mainnet_url("http://127.0.0.1:18081")
        return "did not refuse :18081"
    except MainnetBanned:
        return None


def run_local() -> int:
    failed = []
    tmp = tempfile.TemporaryDirectory(prefix="leasegrid-0c-")
    key_path = os.path.join(tmp.name, "issuer.signing.key")
    spent_path = os.path.join(tmp.name, "spent.json")
    storedir = os.path.join(tmp.name, "store")
    os.makedirs(storedir, exist_ok=True)

    empty = keccak256(b"").hex()
    if empty != "c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470":
        print("FAIL  keccak256 empty vector mismatch", flush=True)
        tmp.cleanup()
        return 1

    ban_err = _ban_mainnet_ports()
    if ban_err:
        print("FAIL  mainnet ban: %s" % ban_err, flush=True)
        tmp.cleanup()
        return 1

    key = generate_signing_key()
    save_signing_key(key_path, key)
    key = load_signing_key(key_path)
    nodeid = "lab-storage-0c"

    backend, backend_note = _try_tahoe_backend(storedir)
    gate = LeaseGate(key, nodeid=nodeid, spent=SpentSet(spent_path), backend=backend)
    if backend is not None:
        from .gate import install_on_storage_server

        install_on_storage_server(backend, gate)

    issuer_state, issuer_httpd = start_issuer(key, "127.0.0.1:0")
    storage_url, storage_httpd = start_storage_http(gate, "127.0.0.1:0")
    issuer_url = issuer_state.listen
    wallet = {"tokens": [], "issuer-pubkey-id": ""}

    try:
        info = http_json(issuer_url + "/v0/info")
        q = {}
        if info.get("intake-mode") != "SIMULATED":
            _fail("0c.1", "issuer intake-mode is %r, expected SIMULATED" % info.get("intake-mode"))
            failed.append("0c.1")
        elif info.get("xmr-network") not in ("stagenet", "testnet"):
            _fail("0c.1", "xmr-network %r not stagenet/testnet" % info.get("xmr-network"))
            failed.append("0c.1")
        else:
            try:
                q = quote_tokens(issuer_url, tokens=2)
                vid = q["vid"]
                addr = q["integrated-address"]
                if len(bytes.fromhex(vid)) != VID_LEN:
                    raise ClientError("vid is not 8 bytes")
                parsed = decode_address(addr)
                if parsed["kind"] != "integrated":
                    raise ClientError("quote did not return an integrated address")
                if parsed["network"] != "stagenet":
                    raise ClientError("address network is %s, expected stagenet" % parsed["network"])
                if payment_id_of(addr) != bytes.fromhex(vid):
                    raise ClientError("integrated address payment id != vid")
                if parsed["payment_id"] == b"\x00" * VID_LEN and vid != "00" * VID_LEN:
                    raise ClientError("payment id empty")
                # ZKAPs must not fit in the 8-byte memo.
                if q.get("tokens_owed") != 2:
                    raise ClientError("tokens_owed %r" % q.get("tokens_owed"))
                if q.get("amount_piconero") != 2 * PICONERO_PER_TOKEN:
                    raise ClientError("amount mismatch")
                _ok(
                    "0c.1",
                    "vid 8 bytes embedded in %s integrated address (%d chars); intake=%s"
                    % (parsed["network"], len(addr), info.get("intake-mode")),
                )
            except Exception as e:
                _fail("0c.1", "%s" % e)
                traceback.print_exc()
                failed.append("0c.1")
                q = {"vid": "", "integrated-address": "", "amount_piconero": 0, "tokens_owed": 0}

        # 0c.2 simulated pay + view-key scan match
        try:
            if not q.get("vid"):
                raise ClientError("no quote")
            pay = simulate_pay(issuer_url, q["vid"], q["amount_piconero"])
            if pay.get("intake-mode") != "SIMULATED":
                raise ClientError("simulate-pay not labeled SIMULATED")
            hits = pay.get("matched") or []
            if not hits or hits[0].get("vid") != q["vid"] or not hits[0].get("paid"):
                raise ClientError("scan did not match vid: %r" % pay)
            st = http_json(
                issuer_url + "/v0/voucher/status",
                "POST",
                {"vid": q["vid"]},
            )
            if not st.get("paid") or st.get("confirmations", 0) < 1:
                raise ClientError("voucher not paid after scan: %r" % st)
            _ok(
                "0c.2",
                "SIMULATED payment confirmed; view-key scan matched vid; confirmations=%s"
                % st.get("confirmations"),
            )
        except Exception as e:
            _fail("0c.2", "%s" % e)
            traceback.print_exc()
            failed.append("0c.2")

        # 0c.3 paid issue + DLEQ + voucher spent
        try:
            wallet = redeem_vid(issuer_url, q["vid"])
            n = len(wallet.get("tokens") or [])
            if n != 2 or wallet.get("denomination") != DENOMINATION:
                raise ClientError("redeem returned %s tokens denom=%r" % (n, wallet.get("denomination")))
            if wallet.get("intake-mode") != "SIMULATED":
                raise ClientError("paid issue not labeled SIMULATED")
            st = http_json(issuer_url + "/v0/voucher/status", "POST", {"vid": q["vid"]})
            if not st.get("spent") or st.get("tokens_issued") != 2:
                raise ClientError("voucher not marked spent: %r" % st)
            try:
                redeem_vid(issuer_url, q["vid"])
                raise ClientError("second redeem of spent voucher succeeded")
            except ClientError as e:
                if "second redeem" in str(e):
                    raise
                if "403" not in str(e) and "spent" not in str(e).lower():
                    raise ClientError("expected spent reject, got: %s" % e)
            _ok(
                "0c.3",
                "issued %s tokens; DLEQ verified; voucher spent; pubkey-id=%s"
                % (n, wallet.get("issuer-pubkey-id")),
            )
        except Exception as e:
            _fail("0c.3", "%s" % e)
            traceback.print_exc()
            failed.append("0c.3")
            wallet = {"tokens": [], "issuer-pubkey-id": info.get("issuer-pubkey-id")}

        # 0c.4 wrong vid / mismatch / underpay → no tokens
        try:
            q_wrong = quote_tokens(issuer_url, tokens=2)
            try:
                redeem_vid(issuer_url, q_wrong["vid"])
                raise ClientError("unpaid vid issued tokens")
            except ClientError as e:
                if "unpaid vid issued" in str(e):
                    raise
                if "403" not in str(e) and "not paid" not in str(e).lower():
                    raise ClientError("expected unpaid reject, got: %s" % e)

            q_mis = quote_tokens(issuer_url, tokens=2)
            other_vid = os.urandom(VID_LEN).hex()
            simulate_pay(issuer_url, other_vid, q_mis["amount_piconero"])
            try:
                redeem_vid(issuer_url, q_mis["vid"])
                raise ClientError("vid mismatch issued tokens")
            except ClientError as e:
                if "vid mismatch issued" in str(e):
                    raise
                if "403" not in str(e) and "not paid" not in str(e).lower():
                    raise ClientError("expected mismatch reject, got: %s" % e)

            q_under = quote_tokens(issuer_url, tokens=2)
            simulate_pay(issuer_url, q_under["vid"], int(q_under["amount_piconero"]) - 1)
            try:
                redeem_vid(issuer_url, q_under["vid"])
                raise ClientError("underpay issued tokens")
            except ClientError as e:
                if "underpay issued" in str(e):
                    raise
                if "403" not in str(e) and "underpay" not in str(e).lower():
                    raise ClientError("expected underpay reject, got: %s" % e)

            bogus = os.urandom(VID_LEN).hex()
            try:
                redeem_vid(issuer_url, bogus, count=2)
                raise ClientError("unknown vid issued tokens")
            except ClientError as e:
                if "unknown vid issued" in str(e):
                    raise
                if "403" not in str(e) and "unknown" not in str(e).lower():
                    raise ClientError("expected unknown vid reject, got: %s" % e)

            _ok(
                "0c.4",
                "unpaid, vid mismatch, underpay, unknown vid all refused",
            )
        except Exception as e:
            _fail("0c.4", "%s" % e)
            traceback.print_exc()
            failed.append("0c.4")

        # 0c.5 spend paid tokens on lease; unpaid still fails
        try:
            if not wallet.get("tokens"):
                raise ClientError("no paid tokens to spend")
            si = os.urandom(16)
            try:
                gate.lab_allocate(si, [0], 64)
                raise ClientError("anonymous allocate succeeded")
            except ZKAPRequired:
                pass
            except ClientError:
                raise
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
            renew = http_json(
                storage_url + "/v0/lab/renew",
                "POST",
                {"storage_index": si.hex()},
            )
            if not renew.get("ok"):
                raise ClientError("renew failed: %r" % renew)
            other_si = os.urandom(16)
            try:
                http_json(
                    storage_url + "/v0/lab/allocate",
                    "POST",
                    {"storage_index": other_si.hex(), "sharenums": [0], "allocated_size": 64},
                )
                raise ClientError("unpaid other SI allocate succeeded")
            except ClientError as e:
                if "unpaid other SI" in str(e):
                    raise
                if "403" not in str(e):
                    raise ClientError("expected unpaid 403, got: %s" % e)
            _ok(
                "0c.5",
                "paid allocate+renew ok; unpaid still refused (backend=%s, %s)"
                % (alloc.get("backend"), backend_note),
            )
        except Exception as e:
            _fail("0c.5", "%s" % e)
            traceback.print_exc()
            failed.append("0c.5")

    finally:
        issuer_httpd.shutdown()
        storage_httpd.shutdown()
        tmp.cleanup()

    if failed:
        print("GATE 0c: FAIL  (%s)  intake=SIMULATED" % ", ".join(failed), flush=True)
        return 1
    print("GATE 0c: PASS  intake=SIMULATED  network=stagenet-format (no chain)", flush=True)
    return 0


def run_live(issuer_url: str, storage_url: str, nodeid: str | None) -> int:
    failed = []
    ban_err = _ban_mainnet_ports()
    if ban_err:
        print("FAIL  mainnet ban: %s" % ban_err, flush=True)
        return 1
    try:
        info = http_json(issuer_url.rstrip("/") + "/v0/info")
    except Exception as e:
        _fail("0c.1", "issuer unreachable: %s" % e)
        print("GATE 0c: FAIL  (issuer unreachable)", flush=True)
        return 1
    mode = info.get("intake-mode") or "unknown"
    if mode not in ("SIMULATED", "wallet-rpc"):
        _fail("0c.1", "unknown intake-mode %r" % mode)
        failed.append("0c.1")

    wallet = {"tokens": [], "issuer-pubkey-id": info.get("issuer-pubkey-id")}
    q = {}
    try:
        q = quote_tokens(issuer_url, tokens=2)
        vid = q["vid"]
        addr = q["integrated-address"]
        if payment_id_of(addr) != bytes.fromhex(vid):
            raise ClientError("address does not embed vid")
        if decode_address(addr)["kind"] != "integrated":
            raise ClientError("not integrated")
        _ok("0c.1", "quote vid embedded; intake=%s network=%s" % (mode, info.get("xmr-network")))
    except Exception as e:
        _fail("0c.1", "%s" % e)
        failed.append("0c.1")

    try:
        if mode != "SIMULATED":
            raise ClientError("live wallet-rpc pay is operator-driven; this harness only auto-pays SIMULATED")
        pay = simulate_pay(issuer_url, q["vid"], q["amount_piconero"])
        if not (pay.get("matched") or []):
            raise ClientError("no match: %r" % pay)
        _ok("0c.2", "SIMULATED pay matched vid")
    except Exception as e:
        _fail("0c.2", "%s" % e)
        failed.append("0c.2")

    try:
        wallet = redeem_vid(issuer_url, q["vid"])
        st = http_json(issuer_url.rstrip("/") + "/v0/voucher/status", "POST", {"vid": q["vid"]})
        if not st.get("spent"):
            raise ClientError("voucher not spent")
        _ok("0c.3", "issued %s tokens; voucher spent" % len(wallet["tokens"]))
    except Exception as e:
        _fail("0c.3", "%s" % e)
        failed.append("0c.3")

    try:
        q2 = quote_tokens(issuer_url, tokens=2)
        try:
            redeem_vid(issuer_url, q2["vid"])
            raise ClientError("unpaid issued")
        except ClientError as e:
            if "unpaid issued" in str(e):
                raise
        q3 = quote_tokens(issuer_url, tokens=2)
        simulate_pay(issuer_url, q3["vid"], int(q3["amount_piconero"]) - 1)
        try:
            redeem_vid(issuer_url, q3["vid"])
            raise ClientError("underpay issued")
        except ClientError as e:
            if "underpay issued" in str(e):
                raise
        _ok("0c.4", "unpaid and underpay refused")
    except Exception as e:
        _fail("0c.4", "%s" % e)
        failed.append("0c.4")

    try:
        st = http_json(storage_url.rstrip("/") + "/v0/info")
        nodeid = nodeid or st.get("nodeid")
        si = os.urandom(16)
        try:
            http_json(
                storage_url.rstrip("/") + "/v0/lab/allocate",
                "POST",
                {"storage_index": si.hex(), "sharenums": [0], "allocated_size": 64},
            )
            raise ClientError("anonymous allocate succeeded")
        except ClientError as e:
            if "anonymous allocate succeeded" in str(e):
                raise
            if "403" not in str(e):
                raise
        spend_token(
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
        if not alloc.get("allocated") and not alloc.get("already-have"):
            raise ClientError("paid allocate empty")
        _ok("0c.5", "live paid allocate ok; unpaid refused")
    except Exception as e:
        _fail("0c.5", "%s" % e)
        failed.append("0c.5")

    if failed:
        print("GATE 0c: FAIL  (%s)  intake=%s" % (", ".join(failed), mode), flush=True)
        return 1
    print("GATE 0c: PASS  intake=%s" % mode, flush=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Leasegrid gate 0c PASS/FAIL checks")
    p.add_argument("--live", action="store_true")
    p.add_argument("--issuer", default="")
    p.add_argument("--storage", default="")
    p.add_argument("--nodeid", default="")
    args = p.parse_args(argv)
    if args.live:
        if not args.issuer or not args.storage:
            print("FAIL  --live requires --issuer and --storage", flush=True)
            return 2
        return run_live(args.issuer, args.storage, args.nodeid or None)
    return run_local()


if __name__ == "__main__":
    sys.exit(main())
