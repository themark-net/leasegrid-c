# Leasegrid Sync — friends and family

Leasegrid Sync is the desktop window. One friend invites you; you join, add a folder, and put a file in it. You do not need Python.
Current build: [v0.1.6](https://github.com/themark-net/leasegrid-c/releases/tag/v0.1.6). Newest build: [latest release](https://github.com/themark-net/leasegrid-c/releases/latest). **More → Settings** shows `Leasegrid Sync (buyer) · version 0.1.6`. The installers are unsigned.

## Install

| OS | Download | One-liner |
|----|----------|-----------|
| Linux x86_64 (glibc 2.35+: Ubuntu 22.04+, Debian 12+, Fedora 36+) | [`Leasegrid_Sync-0.1.6-x86_64.AppImage`](https://github.com/themark-net/leasegrid-c/releases/download/v0.1.6/Leasegrid_Sync-0.1.6-x86_64.AppImage) | `chmod +x` it and run it. Needs FUSE (`libfuse2`); no FUSE: add `--appimage-extract-and-run`. |
| macOS (Intel; Apple Silicon through Rosetta 2) | [`Leasegrid_Sync-0.1.6-macos-x86_64.dmg`](https://github.com/themark-net/leasegrid-c/releases/download/v0.1.6/Leasegrid_Sync-0.1.6-macos-x86_64.dmg) | Drag to Applications, then **Open Anyway** (steps below). |
| Windows 10/11 x64 | [`Leasegrid_Sync-0.1.6-win64-setup.exe`](https://github.com/themark-net/leasegrid-c/releases/download/v0.1.6/Leasegrid_Sync-0.1.6-win64-setup.exe) | On SmartScreen: **More info → Run anyway**. |
| Windows x64, no setup | [`Leasegrid_Sync-0.1.6-win64.zip`](https://github.com/themark-net/leasegrid-c/releases/download/v0.1.6/Leasegrid_Sync-0.1.6-win64.zip) | Unzip and start `leasegrid-sync.exe`. `leasegrid-sync-cli.exe` is the console program, not the window. |

**Checksums:** compare your download with the matching `SHA256SUMS-linux-x86_64`, `SHA256SUMS-macos-x86_64` or `SHA256SUMS-win64` asset on [the release](https://github.com/themark-net/leasegrid-c/releases/tag/v0.1.6) before you run it.

<details>
<summary>macOS: “unidentified developer” — Open Anyway steps</summary>

1. Open the `.dmg` and drag **Leasegrid Sync** onto **Applications**.
2. Double-click **Leasegrid Sync** in Applications. Gatekeeper blocks it (the app is ad-hoc signed, not notarized).
3. Open **System Settings → Privacy & Security** and click **Open Anyway**. It shows for about an hour after the block. Enter your login password.

On macOS 14 and earlier, Control-click the app → **Open** → **Open** instead. Control-click no longer bypasses Gatekeeper on macOS 15.
</details>

Then: open **Join a friendnet**, paste the short code your friend copied with **Copy code**, tick **I understand the four points above.**, click **Join friendnet**, and **Add folder** on **Folders**.

## What's new in v0.1.6

- A second launch says **Leasegrid Sync is already running. Use the open window.**
- Closing the window while an invite is open asks first. **Keep open** is the default.
- Details: [v0.1.6 release notes](https://github.com/themark-net/leasegrid-c/blob/main/docs/release-notes/v0.1.6.md) (and [v0.1.5](https://github.com/themark-net/leasegrid-c/blob/main/docs/release-notes/v0.1.5.md) before it).

## Known issues

- **Add folder HTTP 500** ([#30](https://github.com/themark-net/leasegrid-c/issues/30), open, parked): the row never says **Up to date**. Say so in your bug report and mention #30.
- **Unsigned installers:** Gatekeeper and SmartScreen warn. On Windows 11, Smart App Control can block the app with no **Run anyway**.
- **Old v0.1.0 install?** It shows **Copy link** instead of **Copy code**. The [full guide](https://github.com/themark-net/leasegrid-c/blob/main/docs/TESTER-GUIDE.md#join-with-an-invite) covers both screens.

## Full guide

Step-by-step install per OS, joining, adding a folder, and what the status chip means: [`docs/TESTER-GUIDE.md`](https://github.com/themark-net/leasegrid-c/blob/main/docs/TESTER-GUIDE.md).

If a launch, invite, log, or folder step goes wrong: [If something goes wrong](https://github.com/themark-net/leasegrid-c/blob/main/docs/TESTER-GUIDE.md#if-something-goes-wrong).

## Report a bug

Open an issue: <https://github.com/themark-net/leasegrid-c/issues/new>. Include your OS, the About line from **More → Settings**, the clicks in order with the exact FAIL line, the chip text and folder Status, and the `logs` folder (`sync-ui.log`, `tahoe.log`, `magic-folder.log`):

| OS | Logs |
|----|------|
| Linux | `~/.local/share/leasegrid-sync/logs/` (or `$XDG_DATA_HOME/leasegrid-sync/logs/`) |
| Mac | `~/Library/Application Support/leasegrid-sync/logs/` |
| Windows | `%LOCALAPPDATA%\leasegrid-sync\logs\` (or `%APPDATA%\leasegrid-sync\logs\` if `%LOCALAPPDATA%` is not set) |

If you set `LEASEGRID_SYNC_HOME`, the logs are in its `logs` folder instead, on every OS.

Leave out invite codes, join links, anything that starts with `pb://`, recovery keys, and `credit-wallet.json`. Crop screenshots that show those.
