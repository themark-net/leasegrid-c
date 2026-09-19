"""leasegrid-sync CLI. Native window; never opens Tahoe WUI."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import APP_NAME, __version__
from .backend import SyncError, TahoeClient, default_nodedir
from .credit import CreditCtl, format_remaining


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="leasegrid-sync",
        description="%s — native Magic Folder client (Gridsync wrap). Not the Tahoe web UI."
        % APP_NAME,
    )
    p.add_argument("--version", action="version", version="%s %s" % (APP_NAME, __version__))
    p.add_argument(
        "--nodedir",
        default=None,
        help="Tahoe client node directory (default: LEASEGRID_TAHOE_NODEDIR or ~/.tahoe)",
    )
    p.add_argument(
        "--screenshot",
        default=None,
        help="Write a PNG of the window then exit (lab evidence).",
    )
    p.add_argument(
        "--dogfood-folder",
        default=None,
        help="Join existing node, add this folder, write a probe file, wait for status.",
    )
    p.add_argument(
        "--offscreen",
        action="store_true",
        help="Set QT_QPA_PLATFORM=offscreen (CI / no display).",
    )
    p.add_argument(
        "--status",
        action="store_true",
        help="Print Tahoe connection status and exit (no window).",
    )
    p.add_argument(
        "--issuer",
        default=None,
        help="Lab issuer URL (default: LEASEGRID_ISSUER_URL or http://127.0.0.1:8700).",
    )
    p.add_argument(
        "--credit-status",
        action="store_true",
        help="Print credit balance from lab issuer/wallet and exit (no window).",
    )
    p.add_argument(
        "--credit-dogfood",
        action="store_true",
        help="Join existing node, redeem lab faucet, screenshot Credit, exit.",
    )
    p.add_argument(
        "--credit-tier",
        default="medium",
        choices=("small", "medium", "large"),
        help="Faucet amount tier for --credit-dogfood (default: medium).",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.offscreen:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
    nodedir = Path(args.nodedir).expanduser() if args.nodedir else default_nodedir()
    if args.status:
        client = TahoeClient(nodedir=nodedir)
        st = client.connection_status()
        print("%s\t%s\t%s" % (st.state, st.detail, nodedir))
        return 0 if st.state in ("Connected", "Connecting") else 1
    if args.credit_status:
        ctl = CreditCtl(issuer_url=args.issuer)
        try:
            snap = ctl.load_balance()
        except SyncError as exc:
            print(exc.banner(), file=sys.stderr)
            return 1
        print("%d\t%s" % (snap.balance.tokens, format_remaining(snap.balance.tokens).split("\n")[0]))
        return 0
    try:
        from .app import run_app
    except ImportError as exc:
        print(
            "PyQt is required for %s. Install with: pip install 'leasegrid-zkap-lab[sync]'\n"
            "(%s)" % (APP_NAME, exc),
            file=sys.stderr,
        )
        return 2
    screenshot = Path(args.screenshot).expanduser() if args.screenshot else None
    dogfood = Path(args.dogfood_folder).expanduser() if args.dogfood_folder else None
    return run_app(
        nodedir=nodedir,
        screenshot=screenshot,
        dogfood_folder=dogfood,
        issuer_url=args.issuer,
        credit_dogfood=args.credit_dogfood,
        credit_tier=args.credit_tier,
    )


if __name__ == "__main__":
    raise SystemExit(main())
