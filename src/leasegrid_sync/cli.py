"""leasegrid-sync CLI. Native window; never opens Tahoe WUI."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import APP_NAME, __version__
from .backend import SyncError, TahoeClient, default_nodedir
from .credit import CreditCtl, format_remaining
from .recovery import EXPORT_ACK_MSG, EXPORT_ACK_NEXT, THREAT_ACK_MSG, THREAT_ACK_NEXT


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
    p.add_argument(
        "--join",
        metavar="INVITE",
        default=None,
        help="Headless: join from a link (http://….i2p/join#… or leasegrid:join#…), a short "
        "`tahoe invite` code (7-word-word), or a pb:// introducer furl. Creates and starts "
        "a Tahoe node (client+storage) if needed; pass --client-only to skip offering disk.",
    )
    p.add_argument(
        "--client-only",
        action="store_true",
        help="Join without offering storage (tahoe create-node --no-storage). "
        "Default unpaid join is the same process as offering disk.",
    )
    p.add_argument(
        "--invite-url",
        action="store_true",
        help="Print the shareable join URL for this nodedir (I2P page fragment) and exit.",
    )
    p.add_argument(
        "--export-invite-page",
        metavar="PATH",
        default=None,
        help="Write a self-contained HTML invite page (QR + link) to PATH and exit. "
        "Host that file on your I2P eepsite.",
    )
    p.add_argument(
        "--ack-threat",
        action="store_true",
        help="Acknowledge the friendnet threat copy. Required before --export-recovery "
        "or --restore-recovery. Same as LEASEGRID_RECOVERY_ACK_THREAT=1.",
    )
    p.add_argument(
        "--ack-loss",
        action="store_true",
        help="Acknowledge that losing the recovery key and this device can mean total loss. "
        "Required before --export-recovery. Same as LEASEGRID_RECOVERY_ACK_LOSS=1.",
    )
    p.add_argument(
        "--ack-store",
        action="store_true",
        help="Acknowledge the recovery key will be stored offline. "
        "Required before --export-recovery. Same as LEASEGRID_RECOVERY_ACK_STORE=1.",
    )
    p.add_argument(
        "--export-recovery",
        metavar="PATH",
        default=None,
        help="Write a recovery key for the joined friendnet to PATH and exit (no window). "
        "Requires --ack-threat, --ack-loss, and --ack-store. "
        "Passphrase from LEASEGRID_RECOVERY_PASSPHRASE (empty = plaintext).",
    )
    p.add_argument(
        "--restore-recovery",
        metavar="PATH",
        default=None,
        help="Restore folders from a recovery key on this device and exit (no window). "
        "Requires --ack-threat. Passphrase from LEASEGRID_RECOVERY_PASSPHRASE. "
        "Folders land in LEASEGRID_RESTORE_ROOT (default ~/Leasegrid).",
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
    if args.invite_url or args.export_invite_page:
        return _invite_share_headless(args, nodedir)
    if args.export_recovery or args.restore_recovery:
        return _recovery_headless(args, nodedir)
    if args.join and not (args.dogfood_folder or args.credit_dogfood or args.screenshot):
        return _join_headless(args, nodedir)
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
        invite=args.join,
        offer_storage=not args.client_only,
    )


def _invite_share_headless(args, nodedir: Path) -> int:
    from .invite import invite_page_html, share_url_for_nodedir

    try:
        url = share_url_for_nodedir(nodedir)
    except SyncError as exc:
        print(exc.banner(), file=sys.stderr)
        return 1
    if args.export_invite_page:
        path = Path(args.export_invite_page).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(invite_page_html(url), encoding="utf-8")
        print("invite-page path=%s" % path)
    if args.invite_url:
        print(url)
    return 0


def _join_headless(args, nodedir: Path) -> int:
    from .backend import default_home

    tahoe = TahoeClient(nodedir=nodedir, home=default_home())
    try:
        st = tahoe.join_invite(args.join.strip(), offer_storage=not args.client_only)
    except SyncError as exc:
        print(exc.banner(), file=sys.stderr)
        tahoe.stop()
        return 1
    print("%s\t%s\t%s" % (st.state, st.detail, tahoe.nodedir))
    tahoe.stop()
    return 0 if st.state == "Connected" else 1


def _env_ack(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def _recovery_headless(args, nodedir: Path) -> int:
    from .backend import MagicFolderCtl, default_home
    from .recovery import RecoveryCtl

    if args.export_recovery:
        threat = args.ack_threat or _env_ack("LEASEGRID_RECOVERY_ACK_THREAT")
        loss = args.ack_loss or _env_ack("LEASEGRID_RECOVERY_ACK_LOSS")
        store = args.ack_store or _env_ack("LEASEGRID_RECOVERY_ACK_STORE")
        if not (threat and loss and store):
            print(SyncError(EXPORT_ACK_MSG, EXPORT_ACK_NEXT).banner(), file=sys.stderr)
            return 1
    elif not (args.ack_threat or _env_ack("LEASEGRID_RECOVERY_ACK_THREAT")):
        print(SyncError(THREAT_ACK_MSG, THREAT_ACK_NEXT).banner(), file=sys.stderr)
        return 1

    home = default_home()
    tahoe = TahoeClient(nodedir=nodedir, home=home)
    mf = MagicFolderCtl(config_dir=home / "magic-folder", nodedir=tahoe.nodedir)
    credit = CreditCtl(home=home, issuer_url=args.issuer)
    root = os.environ.get("LEASEGRID_RESTORE_ROOT")
    ctl = RecoveryCtl(home, tahoe, mf, credit, folder_root=Path(root).expanduser() if root else None)
    passphrase = os.environ.get("LEASEGRID_RECOVERY_PASSPHRASE", "")
    try:
        if args.export_recovery:
            bundle = ctl.export(Path(args.export_recovery).expanduser(), passphrase)
            print(
                "recovery-export path=%s folders=%d wallet=%s credit-seed=%s encrypted=%s"
                % (
                    args.export_recovery,
                    len(bundle.folders),
                    "yes" if bundle.wallet else "no",
                    "yes" if bundle.credit_seed else "no",
                    "yes" if passphrase else "NO",
                )
            )
            return 0
        result = ctl.restore(
            Path(args.restore_recovery).expanduser(),
            passphrase,
            progress=lambda text: print(text, file=sys.stderr),
        )
        credit = str(result.credit_recovered)
        if result.credit_recover_error:
            credit += " error=%s" % result.credit_recover_error
        print(
            "recovery-restore folders=%s skipped=%s wallet=%s credit=%s author=%s grid=%s"
            % (
                ",".join(result.folders) or "-",
                ",".join(result.skipped) or "-",
                "restored" if result.wallet_restored else "kept",
                credit,
                result.author_name,
                result.grid,
            )
        )
        # Leave the daemons running long enough for a first download pass when asked.
        linger = float(os.environ.get("LEASEGRID_RESTORE_LINGER", "0") or 0)
        if linger > 0:
            import time

            time.sleep(linger)
        return 0
    except SyncError as exc:
        print(exc.banner(), file=sys.stderr)
        return 1
    finally:
        mf.stop()
        tahoe.stop()


if __name__ == "__main__":
    raise SystemExit(main())
