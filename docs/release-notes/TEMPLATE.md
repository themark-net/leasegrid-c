<!--
Release-notes template for the next friends-and-family tag.
Copy this file to docs/release-notes/vX.Y.Z.md (the Installers workflow reads
docs/release-notes/<tag>.md as the GitHub release body via body_path), replace
X.Y.Z and every <placeholder>, and delete this comment. Keep the shape:
2-3 line summary, install table, What's new (5 bullets max), Known issues,
links out to the full guide. Every link absolute. Long detail belongs in
docs/TESTER-GUIDE.md or the previous release notes, not here.
See https://github.com/themark-net/leasegrid-c/blob/main/docs/ops/friends-and-family-releases.md
-->
# Leasegrid Sync vX.Y.Z

Friends-and-family build of Leasegrid Sync, the desktop folder-sync window. <One sentence: what changed for testers, or "the app is the same as vA.B.C".>
The installers are unsigned, so your OS will warn before the first launch.

## Install

| OS | Download | One-liner |
|----|----------|-----------|
| Linux x86_64 (glibc 2.35+: Ubuntu 22.04+, Debian 12+, Fedora 36+) | [`Leasegrid_Sync-X.Y.Z-x86_64.AppImage`](https://github.com/themark-net/leasegrid-c/releases/download/vX.Y.Z/Leasegrid_Sync-X.Y.Z-x86_64.AppImage) | `chmod +x` it and run it. Needs FUSE (`libfuse2` on Ubuntu). |
| macOS (Intel; Apple Silicon through Rosetta 2) | [`Leasegrid_Sync-X.Y.Z-macos-x86_64.dmg`](https://github.com/themark-net/leasegrid-c/releases/download/vX.Y.Z/Leasegrid_Sync-X.Y.Z-macos-x86_64.dmg) | Drag to Applications, then **Open Anyway** (steps below). |
| Windows 10/11 x64 | [`Leasegrid_Sync-X.Y.Z-win64-setup.exe`](https://github.com/themark-net/leasegrid-c/releases/download/vX.Y.Z/Leasegrid_Sync-X.Y.Z-win64-setup.exe) | On SmartScreen: **More info → Run anyway**. |
| Windows x64, no setup | [`Leasegrid_Sync-X.Y.Z-win64.zip`](https://github.com/themark-net/leasegrid-c/releases/download/vX.Y.Z/Leasegrid_Sync-X.Y.Z-win64.zip) | Unzip and start `leasegrid-sync.exe`. `leasegrid-sync-cli.exe` is the console program, not the window. |

**Checksums:** compare your download with the matching `SHA256SUMS-linux-x86_64`, `SHA256SUMS-macos-x86_64` or `SHA256SUMS-win64` asset on [this release](https://github.com/themark-net/leasegrid-c/releases/tag/vX.Y.Z) before you run it.

<details>
<summary>macOS: “unidentified developer” — Open Anyway steps</summary>

1. Open the `.dmg` and drag **Leasegrid Sync** onto **Applications**.
2. Double-click **Leasegrid Sync** in Applications. Gatekeeper blocks it (the app is ad-hoc signed, not notarized).
3. Open **System Settings → Privacy & Security** and click **Open Anyway**. It shows for about an hour after the block. Enter your login password.

On macOS 14 and earlier, Control-click the app → **Open** → **Open** instead. Control-click no longer bypasses Gatekeeper on macOS 15.
</details>

## What's new

- <change, one line> ([#NN](https://github.com/themark-net/leasegrid-c/pull/NN), `<sha>`)
- <up to 5 bullets; move anything longer to the guide or the PR>

## Known issues

- <issue, one line> ([#NN](https://github.com/themark-net/leasegrid-c/issues/NN))

## More

- **Full tester guide** (install, join with an invite, add a folder, what the status chip means, report a bug): [`docs/TESTER-GUIDE.md`](https://github.com/themark-net/leasegrid-c/blob/main/docs/TESTER-GUIDE.md)
- **Earlier changes:** [vA.B.C notes](https://github.com/themark-net/leasegrid-c/blob/main/docs/release-notes/vA.B.C.md). Previous build: [vA.B.C](https://github.com/themark-net/leasegrid-c/releases/tag/vA.B.C) at `<sha>`.
- **Report a bug:** [https://github.com/themark-net/leasegrid-c/issues/new](https://github.com/themark-net/leasegrid-c/issues/new). Leave out invite codes, join links and anything that starts with `pb://`.
