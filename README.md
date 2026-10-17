# Leasegrid

Monero-prepaid Tahoe-LAFS friendnet with bearer storage credits and silent eject.
**Leasegrid Sync** is the desktop app: join a friend's grid, add a folder, and it syncs. Current friends-and-family build: [v0.1.2](https://github.com/themark-net/leasegrid-c/releases/tag/v0.1.2) (unsigned).

## Install Leasegrid Sync

| OS | Download | One-liner |
|----|----------|-----------|
| Linux x86_64 (glibc 2.35+) | [`Leasegrid_Sync-0.1.2-x86_64.AppImage`](https://github.com/themark-net/leasegrid-c/releases/download/v0.1.2/Leasegrid_Sync-0.1.2-x86_64.AppImage) | `chmod +x` it and run it (needs FUSE). |
| macOS (Intel; Apple Silicon through Rosetta 2) | [`Leasegrid_Sync-0.1.2-macos-x86_64.dmg`](https://github.com/themark-net/leasegrid-c/releases/download/v0.1.2/Leasegrid_Sync-0.1.2-macos-x86_64.dmg) | Drag to Applications, then **Open Anyway** (below). |
| Windows 10/11 x64 | [`Leasegrid_Sync-0.1.2-win64-setup.exe`](https://github.com/themark-net/leasegrid-c/releases/download/v0.1.2/Leasegrid_Sync-0.1.2-win64-setup.exe) or [`.zip`](https://github.com/themark-net/leasegrid-c/releases/download/v0.1.2/Leasegrid_Sync-0.1.2-win64.zip) | SmartScreen: **More info → Run anyway**. From the zip, start `leasegrid-sync.exe`; `leasegrid-sync-cli.exe` is the console program, not the window. |

**Checksums:** compare your download with the matching `SHA256SUMS-*` asset on [the release](https://github.com/themark-net/leasegrid-c/releases/tag/v0.1.2).

<details>
<summary>macOS: “unidentified developer” — Open Anyway steps</summary>

1. Open the `.dmg` and drag **Leasegrid Sync** onto **Applications**.
2. Double-click **Leasegrid Sync** in Applications. Gatekeeper blocks it (the app is ad-hoc signed, not notarized).
3. Open **System Settings → Privacy & Security** and click **Open Anyway**. It shows for about an hour after the block. Enter your login password.

On macOS 14 and earlier, Control-click the app → **Open** → **Open** instead. Control-click no longer bypasses Gatekeeper on macOS 15.
</details>

Tester page (join, add a folder, report a bug): [`docs/TESTERS.md`](https://github.com/themark-net/leasegrid-c/blob/main/docs/TESTERS.md) · full guide: [`docs/TESTER-GUIDE.md`](https://github.com/themark-net/leasegrid-c/blob/main/docs/TESTER-GUIDE.md).

## What's new in v0.1.2

- Same app as v0.1.1; the release page and installer CI changed.
- Release text comes from [`docs/release-notes/`](https://github.com/themark-net/leasegrid-c/tree/main/docs/release-notes), with `SHA256SUMS-*` files per platform.
- Details: [v0.1.2 release notes](https://github.com/themark-net/leasegrid-c/blob/main/docs/release-notes/v0.1.2.md).

## Known issues

- Add folder can return Magic Folder HTTP 500 ([#30](https://github.com/themark-net/leasegrid-c/issues/30), open, parked).
- Unsigned installers: Gatekeeper and SmartScreen warn before the first launch.

## About this repository

An **architecture specification** plus lab code, not a token, not an L1, and not a Tahoe fork: stock Tahoe-LAFS storage, XMR → issuer → ZKAP payment, and client repair instead of slashing.
Full overview (status by milestone, reading order, two rails, non-goals, terms): [`docs/OVERVIEW.md`](https://github.com/themark-net/leasegrid-c/blob/main/docs/OVERVIEW.md).

## Run it locally

```bash
python3 -m venv .venv && .venv/bin/pip install -U pip && .venv/bin/pip install -e ".[sync,tahoe]"
scripts/dev-grid.sh                      # shell 1: introducer + 3 storage + issuer; prints an invite furl
LEASEGRID_ISSUER_URL=http://127.0.0.1:8700 .venv/bin/leasegrid-sync   # shell 2: paste the furl → Join
scripts/dev-grid.sh --invite             # optional shell 3: a short one-time code (7-word-word) instead of the furl
```

Details: [`docs/ops/dev-grid.md`](https://github.com/themark-net/leasegrid-c/blob/main/docs/ops/dev-grid.md) · [`docs/OVERVIEW.md`](https://github.com/themark-net/leasegrid-c/blob/main/docs/OVERVIEW.md#run-it-locally-client--server-one-machine).

## License

Specification text: Apache-2.0. A future Tahoe plugin would follow Tahoe-LAFS license terms and is out of scope here.
