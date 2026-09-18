"""leasegrid-zkap CLI: issuer, storage-gate, faucet, spend, settle, check-0b."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .constants import (
    DEFAULT_ISSUER_KEY,
    DEFAULT_LEASE_SECONDS,
    DEFAULT_SHARE_BYTES,
    DEFAULT_SPENT_SET,
    DEFAULT_WALLET,
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
    key = load_signing_key(_key_path(args.key_file))
    from .issuer import start_issuer

    state, httpd = start_issuer(key, args.listen)
    print("issuer listening %s" % state.listen, flush=True)
    print("issuer-pubkey-id %s" % state.info["issuer-pubkey-id"], flush=True)
    print("invariant: settlement sends spent t only; R is rejected", flush=True)
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


def cmd_check(args) -> int:
    from .check_0b import main as check_main

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

    iss = sub.add_parser("issuer", help="run lab issuer + faucet")
    iss.add_argument("--key-file", default=DEFAULT_ISSUER_KEY)
    iss.add_argument("--listen", default="127.0.0.1:8700")
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

    c = sub.add_parser("check-0b", help="print PASS/FAIL for 0b.1–0b.5")
    c.add_argument("--live", action="store_true")
    c.add_argument("--issuer", default="")
    c.add_argument("--storage", default="")
    c.add_argument("--nodeid", default="")
    c.set_defaults(func=cmd_check)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
