"""leasegrid-zkap CLI: issuer, storage-gate, faucet, quote/redeem (0c), spend, settle, checks."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .constants import (
    DEFAULT_ISSUER_KEY,
    DEFAULT_LEASE_SECONDS,
    DEFAULT_QUOTE_TOKENS,
    DEFAULT_SHARE_BYTES,
    DEFAULT_SPENT_SET,
    DEFAULT_WALLET,
    DEFAULT_XMR_NETWORK,
    DENOMINATION,
)
from .crypto import generate_signing_key, issuer_info, load_signing_key, save_signing_key
from .gate import LeaseGate, parse_storage_index
from .spentset import SpentSet


def _key_path(p: str | None) -> str:
    return os.path.expanduser(p or os.environ.get("LEASEGRID_ISSUER_KEY") or DEFAULT_ISSUER_KEY)


def cmd_keygen(args) -> int:
    path = _key_path(args.key_file)
    if os.path.exists(path) and not args.force:
        print("refusing to overwrite %s (pass --force)" % path, file=sys.stderr)
        return 2
    if os.path.exists(path) and args.force:
        os.remove(path)
    key = generate_signing_key()
    save_signing_key(path, key)
    info = issuer_info(key)
    print("wrote %s" % path)
    print("issuer-pubkey-id %s" % info["issuer-pubkey-id"])
    print("denomination %s" % DENOMINATION)
    return 0


def cmd_info(args) -> int:
    key = load_signing_key(_key_path(args.key_file))
    print(json.dumps(issuer_info(key), indent=2, sort_keys=True))
    return 0


def cmd_issuer(args) -> int:
    from .errors import MainnetBanned
    from .issuer import start_issuer
    from .xmr_intake import make_intake, refuse_mainnet_url

    try:
        if getattr(args, "xmr_rpc", ""):
            refuse_mainnet_url(args.xmr_rpc)
        intake = make_intake(
            getattr(args, "intake", "simulated") or "simulated",
            xmr_rpc=getattr(args, "xmr_rpc", "") or "",
            network=getattr(args, "xmr_network", "") or DEFAULT_XMR_NETWORK,
        )
    except MainnetBanned as e:
        print("FAIL  %s" % e, file=sys.stderr)
        return 2
    key = load_signing_key(_key_path(args.key_file))
    state, httpd = start_issuer(key, args.listen, intake=intake)
    print("issuer listening %s" % state.listen, flush=True)
    print("issuer-pubkey-id %s" % state.info["issuer-pubkey-id"], flush=True)
    print("intake-mode %s network %s" % (state.intake.mode, getattr(state.intake, "network", "")), flush=True)
    print("invariant: settlement sends spent t only; R is rejected", flush=True)
    if state.intake.mode == "SIMULATED":
        print("XMR intake is SIMULATED (no chain; no :18081)", flush=True)
    try:
        while True:
            import time

            time.sleep(3600)
    except KeyboardInterrupt:
        httpd.shutdown()
    return 0


def cmd_storage_gate(args) -> int:
    key = load_signing_key(_key_path(args.key_file))
    nodeid = args.nodeid
    if not nodeid and args.node_dir:
        p = Path(args.node_dir).expanduser() / "my_nodeid"
        nodeid = p.read_text(encoding="utf-8").strip()
    if not nodeid:
        print("need --nodeid or --node-dir with my_nodeid", file=sys.stderr)
        return 2
    spent = SpentSet(args.spent_set or DEFAULT_SPENT_SET)
    backend = None
    if args.wrap_tahoe_dir:
        from allmydata.storage.server import StorageServer
        from .gate import install_on_storage_server

        raw_id = b"\x00" * 20
        backend = StorageServer(os.path.expanduser(args.wrap_tahoe_dir), raw_id)
        gate = LeaseGate(key, nodeid=nodeid, spent=spent, backend=backend)
        install_on_storage_server(backend, gate)
    else:
        gate = LeaseGate(key, nodeid=nodeid, spent=spent)
    from .storage_http import start_storage_http

    url, httpd = start_storage_http(gate, args.listen)
    print("storage-gate listening %s" % url, flush=True)
    print("nodeid %s" % nodeid, flush=True)
    print("issuer-pubkey-id %s" % gate.issuer_pubkey_id, flush=True)
    try:
        import time

        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        httpd.shutdown()
    return 0


def cmd_faucet(args) -> int:
    from .client import faucet_mint, save_wallet

    wallet = faucet_mint(args.issuer, count=args.count)
    save_wallet(args.out, wallet)
    print("wrote %s (%s tokens)" % (args.out, len(wallet["tokens"])))
    print("issuer-pubkey-id %s" % wallet["issuer-pubkey-id"])
    print("denomination %s" % wallet["denomination"])
    return 0


def cmd_spend(args) -> int:
    from .client import load_wallet, save_wallet, spend_token

    wallet = load_wallet(args.wallet)
    si = parse_storage_index(args.storage_index)
    out = spend_token(
        args.storage,
        wallet,
        nodeid=args.nodeid,
        storage_index=si,
        lease_seconds=args.lease_seconds,
        share_bytes=args.share_bytes,
    )
    save_wallet(args.wallet, wallet)
    public = {k: v for k, v in out.items() if not k.startswith("_")}
    print(json.dumps(public, indent=2, sort_keys=True))
    return 0


def cmd_settle(args) -> int:
    from .client import http_json, settle_spent

    if args.from_storage:
        bundle = http_json(args.from_storage.rstrip("/") + "/v0/settlement-bundle")
        pre = bundle["spent-preimages"]
    else:
        pre = json.loads(Path(args.preimages).read_text(encoding="utf-8"))
        if isinstance(pre, dict):
            pre = pre.get("spent-preimages") or pre.get("spent")
    extra = None
    if args.include_r:
        print("refusing --include-r: issuer must not receive R", file=sys.stderr)
        return 2
    out = settle_spent(args.issuer, pre, extra=extra)
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0


def cmd_quote(args) -> int:
    from .client import quote_tokens

    out = quote_tokens(args.issuer, tokens=args.tokens)
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0


def cmd_simulate_pay(args) -> int:
    from .client import simulate_pay, voucher_status

    amount = args.amount_piconero
    if amount is None:
        st = voucher_status(args.issuer, args.vid)
        amount = st["amount_piconero"]
    out = simulate_pay(args.issuer, args.vid, amount, confirmations=args.confirmations)
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0


def cmd_redeem(args) -> int:
    from .client import redeem_vid, save_wallet

    wallet = redeem_vid(args.issuer, args.vid, count=args.count)
    save_wallet(args.out, wallet)
    print("wrote %s (%s tokens)" % (args.out, len(wallet["tokens"])))
    print("issuer-pubkey-id %s" % wallet["issuer-pubkey-id"])
    print("vid %s" % wallet.get("vid"))
    print("intake-mode %s" % wallet.get("intake-mode"))
    return 0


def cmd_check(args) -> int:
    from .check_0b import main as check_main

    argv = []
    if args.live:
        argv += ["--live", "--issuer", args.issuer, "--storage", args.storage]
        if args.nodeid:
            argv += ["--nodeid", args.nodeid]
    return check_main(argv)


def cmd_check_0c(args) -> int:
    from .check_0c import main as check_main

    argv = []
    if args.live:
        argv += ["--live", "--issuer", args.issuer, "--storage", args.storage]
        if args.nodeid:
            argv += ["--nodeid", args.nodeid]
    return check_main(argv)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="leasegrid-zkap")
    sub = p.add_subparsers(dest="cmd", required=True)

    k = sub.add_parser("keygen", help="create issuer signing key (off-git path)")
    k.add_argument("--key-file", default=DEFAULT_ISSUER_KEY)
    k.add_argument("--force", action="store_true")
    k.set_defaults(func=cmd_keygen)

    i = sub.add_parser("info", help="print issuer pubkey id")
    i.add_argument("--key-file", default=DEFAULT_ISSUER_KEY)
    i.set_defaults(func=cmd_info)

    iss = sub.add_parser("issuer", help="run lab issuer + faucet + 0c quote/redeem")
    iss.add_argument("--key-file", default=DEFAULT_ISSUER_KEY)
    iss.add_argument("--listen", default="127.0.0.1:8700")
    iss.add_argument("--intake", default="simulated", help="simulated (default) or rpc")
    iss.add_argument("--xmr-rpc", default="", help="wallet-rpc URL; :18081/:18083 refused")
    iss.add_argument("--xmr-network", default=DEFAULT_XMR_NETWORK)
    iss.set_defaults(func=cmd_issuer)

    sg = sub.add_parser("storage-gate", help="run storage spend HTTP (optional Tahoe wrap)")
    sg.add_argument("--key-file", default=DEFAULT_ISSUER_KEY)
    sg.add_argument("--listen", default="127.0.0.1:8701")
    sg.add_argument("--nodeid", default="")
    sg.add_argument("--node-dir", default="")
    sg.add_argument("--spent-set", default=DEFAULT_SPENT_SET)
    sg.add_argument("--wrap-tahoe-dir", default="", help="optional Tahoe StorageServer storedir")
    sg.set_defaults(func=cmd_storage_gate)

    f = sub.add_parser("faucet", help="blinded faucet mint into a wallet JSON")
    f.add_argument("--issuer", required=True)
    f.add_argument("--out", default=DEFAULT_WALLET)
    f.add_argument("--count", type=int, default=8)
    f.set_defaults(func=cmd_faucet)

    s = sub.add_parser("spend", help="spend one token bound to R")
    s.add_argument("--storage", required=True)
    s.add_argument("--wallet", default=DEFAULT_WALLET)
    s.add_argument("--nodeid", required=True)
    s.add_argument("--storage-index", required=True, help="16-byte SI as hex")
    s.add_argument("--lease-seconds", type=int, default=DEFAULT_LEASE_SECONDS)
    s.add_argument("--share-bytes", type=int, default=DEFAULT_SHARE_BYTES)
    s.set_defaults(func=cmd_spend)

    t = sub.add_parser("settle", help="send spent t only to issuer")
    t.add_argument("--issuer", required=True)
    t.add_argument("--from-storage", default="")
    t.add_argument("--preimages", default="")
    t.add_argument("--include-r", action="store_true", help="forbidden; always refused")
    t.set_defaults(func=cmd_settle)

    q = sub.add_parser("quote", help="allocate vid + integrated address (0c.1)")
    q.add_argument("--issuer", required=True)
    q.add_argument("--tokens", type=int, default=DEFAULT_QUOTE_TOKENS)
    q.set_defaults(func=cmd_quote)

    sp = sub.add_parser("simulate-pay", help="SIMULATED XMR intake for a vid (no chain)")
    sp.add_argument("--issuer", required=True)
    sp.add_argument("--vid", required=True)
    sp.add_argument("--amount-piconero", type=int, default=None)
    sp.add_argument("--confirmations", type=int, default=None)
    sp.set_defaults(func=cmd_simulate_pay)

    rdm = sub.add_parser("redeem", help="paid issue for a paid vid (0c.3)")
    rdm.add_argument("--issuer", required=True)
    rdm.add_argument("--vid", required=True)
    rdm.add_argument("--out", default=DEFAULT_WALLET)
    rdm.add_argument("--count", type=int, default=None)
    rdm.set_defaults(func=cmd_redeem)

    c = sub.add_parser("check-0b", help="print PASS/FAIL for 0b.1–0b.5")
    c.add_argument("--live", action="store_true")
    c.add_argument("--issuer", default="")
    c.add_argument("--storage", default="")
    c.add_argument("--nodeid", default="")
    c.set_defaults(func=cmd_check)

    c3 = sub.add_parser("check-0c", help="print PASS/FAIL for 0c.1–0c.5 (SIMULATED default)")
    c3.add_argument("--live", action="store_true")
    c3.add_argument("--issuer", default="")
    c3.add_argument("--storage", default="")
    c3.add_argument("--nodeid", default="")
    c3.set_defaults(func=cmd_check_0c)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
