"""leasegrid-zkap CLI: issuer, storage-gate, faucet, topup/resume/recover, spend, settle, check-0b."""

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


def _issuer_chain(args):
    """Build the ChainWatcher for `issuer --chain`. Raises SystemExit(2) on bad config."""
    kind = getattr(args, "chain", "none")
    if kind == "none":
        return None
    if kind == "fake":
        from .payment import FakeChain

        return FakeChain()
    if kind == "wallet-rpc":
        url = (
            getattr(args, "wallet_rpc_url", "")
            or os.environ.get("LEASEGRID_WALLET_RPC")
            or ""
        )
        if not url:
            print("need --wallet-rpc-url or LEASEGRID_WALLET_RPC", file=sys.stderr)
            raise SystemExit(2)
        from .payment.chain_walletrpc import WalletRpcChain

        user = getattr(args, "wallet_rpc_user", "") or os.environ.get("LEASEGRID_WALLET_RPC_USER") or None
        password = (
            getattr(args, "wallet_rpc_password", "")
            or os.environ.get("LEASEGRID_WALLET_RPC_PASSWORD")
            or None
        )
        account = int(getattr(args, "wallet_rpc_account", 0) or 0)
        return WalletRpcChain(url, account_index=account, user=user, password=password)
    print("unsupported --chain %s" % kind, file=sys.stderr)
    raise SystemExit(2)


def cmd_issuer(args) -> int:
    key = load_signing_key(_key_path(args.key_file))
    from .issuer import start_issuer
    from .payment import PricePolicy, VoucherStore

    try:
        chain = _issuer_chain(args)
    except SystemExit:
        raise
    except Exception as exc:
        print("issuer chain: %s" % exc, file=sys.stderr)
        return 2
    price = int(round(float(args.price_xmr) * 10**12))
    policy = PricePolicy(
        price_piconero=price,
        quote_ttl=int(args.quote_ttl),
        grace=int(args.grace),
        confirmations_small=int(args.confirmations),
        confirmations_large=int(args.confirmations_large),
    )
    store = VoucherStore(os.path.expanduser(args.db)) if args.db else VoucherStore()
    rsa_key = None
    rsa_path = getattr(args, "rsa_key", "") or ""
    if rsa_path:
        from .rsa_bssa import load_or_create_rsa_pem

        rsa_key = load_or_create_rsa_pem(rsa_path)
    state, httpd = start_issuer(
        key,
        args.listen,
        chain=chain,
        policy=policy,
        store=store,
        faucet=bool(args.faucet),
        poll_interval=float(args.poll_interval),
        rsa_key=rsa_key,
    )
    print("issuer listening %s" % state.listen, flush=True)
    print("issuer-pubkey-id %s" % state.info["issuer-pubkey-id"], flush=True)
    print(
        "chain %s  faucet %s  price %s XMR/token  db %s  rsa-bssa-v1 %s"
        % (
            state.chain_kind,
            "on" if state.faucet else "off",
            args.price_xmr,
            args.db or "memory",
            "on" if rsa_key is not None else "off",
        ),
        flush=True,
    )
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


def _topup_client(args):
    from .payment.topup import TopUpClient

    return TopUpClient(args.issuer, args.wallet, args.state or None)


def cmd_topup(args) -> int:
    """Quote → print how to pay → (optionally) wait for confirmation and collect the batch."""
    import time

    tc = _topup_client(args)
    q = tc.quote(int(args.tokens))
    if args.json:
        print(json.dumps(q, sort_keys=True), flush=True)
    else:
        print("vid            %s" % q["vid"])
        print("pay exactly    %s XMR  (%d piconero)" % (q["amount_xmr"], q["amount_piconero"]))
        print("to address     %s" % q["address"])
        print("uri            %s" % q["pay_uri"])
        print("price window   until %s (quoted price honoured %ds more after that)"
              % (time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime(q["quote_expires"])),
                 int(q["grace_until"] - q["quote_expires"])))
        print("confirmations  %d" % q["confirmations_required"])
        print("denomination   %s" % q.get("denomination", DENOMINATION), flush=True)
    if not args.wait:
        if not args.json:
            print("then:          leasegrid-zkap resume --issuer %s --wallet %s" % (args.issuer, args.wallet))
        return 0
    deadline = time.time() + float(args.wait)
    last = ""
    while time.time() < deadline:
        r = tc.redeem(q["vid"])
        if r["state"] == "issued":
            print("issued         +%d tokens into %s%s"
                  % (r["tokens_added"], args.wallet, " (cached batch)" if r.get("cached") else ""))
            return 0
        v = r.get("voucher") or {}
        line = "waiting        state=%s seen=%s confirmations=%s/%s" % (
            r["state"], v.get("amount_seen"), v.get("confirmations"), v.get("confirmations_required"))
        if line != last:
            print(line, flush=True)
            last = line
        time.sleep(float(args.poll))
    print("timed out waiting; the voucher is saved. Run `leasegrid-zkap resume` later.", file=sys.stderr)
    return 3


def cmd_resume(args) -> int:
    tc = _topup_client(args)
    results = tc.resume()
    if not results:
        print("nothing pending")
        return 0
    for r in results:
        print("%s  %-14s +%d%s" % (r["vid"], r["state"], r.get("tokens_added", 0),
                                   ("  " + r["error"]) if r.get("error") else ""))
    return 0


def cmd_recover(args) -> int:
    from .payment.topup import TopUpState

    if args.seed:
        TopUpState.from_seed(args.state or Path(args.wallet).expanduser().with_name("credit-topup.json"),
                             bytes.fromhex(args.seed))
    tc = _topup_client(args)
    out = tc.recover(gap=int(args.gap))
    print("vouchers found %d" % out["vouchers_found"])
    print("tokens added   %d (unverified until first spend)" % out["tokens_added"])
    print("next counter   %d" % out["next_counter"])
    for r in out["results"]:
        print("  %s  %-14s +%d" % (r["vid"], r["state"], r.get("tokens_added", 0)))
    return 0


def cmd_voucher(args) -> int:
    tc = _topup_client(args)
    v = tc.status(args.vid)
    if v is None:
        print("issuer does not know vid %s" % args.vid, file=sys.stderr)
        return 1
    print(json.dumps(v, indent=2, sort_keys=True))
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

    iss = sub.add_parser("issuer", help="run issuer (quote/redeem; optional faucet; optional fake chain)")
    iss.add_argument("--key-file", default=DEFAULT_ISSUER_KEY)
    iss.add_argument("--listen", default="127.0.0.1:8700")
    iss.add_argument(
        "--chain",
        default="none",
        choices=["none", "fake", "wallet-rpc"],
        help="payment detector: none (quotes 503), fake (lab; /v0/fake/pay), wallet-rpc (monero-wallet-rpc)",
    )
    iss.add_argument(
        "--wallet-rpc-url",
        default="",
        help="monero-wallet-rpc JSON-RPC URL (or LEASEGRID_WALLET_RPC)",
    )
    iss.add_argument("--wallet-rpc-user", default="")
    iss.add_argument("--wallet-rpc-password", default="")
    iss.add_argument("--wallet-rpc-account", default="0", help="wallet account index (default 0)")
    iss.add_argument("--faucet", action="store_true", help="enable free /v0/issue (lab only)")
    iss.add_argument("--price-xmr", default="0.006", help="XMR per token (1 GiB-share-month)")
    iss.add_argument("--quote-ttl", default=str(30 * 60), help="seconds a quote is 'exact'")
    iss.add_argument("--grace", default=str(24 * 3600), help="seconds after expiry quoted price still holds")
    iss.add_argument("--confirmations", default="2", help="required depth below the large threshold")
    iss.add_argument("--confirmations-large", default="10")
    iss.add_argument("--db", default="", help="SQLite voucher store (default: in-memory)")
    iss.add_argument("--poll-interval", default="5", help="seconds between chain polls")
    iss.add_argument(
        "--rsa-key",
        default="",
        help="PEM RSA key enabling rsa-bssa-v1 quotes (created if the path does not exist)",
    )
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

    def _topup_args(sp):
        sp.add_argument("--issuer", required=True)
        sp.add_argument("--wallet", default=DEFAULT_WALLET)
        sp.add_argument("--state", default="", help="credit-topup.json (default: next to the wallet)")

    tu = sub.add_parser("topup", help="buy credit with XMR: quote, pay, collect")
    _topup_args(tu)
    tu.add_argument("--tokens", type=int, required=True, help="GiB-share-months to buy")
    tu.add_argument("--wait", default="", help="seconds to wait for payment + confirmations, then collect")
    tu.add_argument("--poll", default="2", help="seconds between checks while waiting")
    tu.add_argument("--json", action="store_true", help="print the quote as one JSON object (CI / scripts)")
    tu.set_defaults(func=cmd_topup)

    ru = sub.add_parser("resume", help="finish pending top-ups (after a crash or a slow payment)")
    _topup_args(ru)
    ru.set_defaults(func=cmd_resume)

    rc = sub.add_parser("recover", help="re-collect every batch this credit seed ever bought")
    _topup_args(rc)
    rc.add_argument("--seed", default="", help="32-byte credit seed as hex (from a recovery key) if no state file")
    rc.add_argument("--gap", default="20", help="stop after this many consecutive unknown vids")
    rc.set_defaults(func=cmd_recover)

    vo = sub.add_parser("voucher", help="show one voucher as the issuer sees it")
    _topup_args(vo)
    vo.add_argument("--vid", required=True)
    vo.set_defaults(func=cmd_voucher)

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
