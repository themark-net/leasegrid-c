# Leasegrid Sync — friends and family

This is the tester page for **Leasegrid Sync**, the desktop window. You do not need Python. One friend invites you. You join, add a folder, and put a file in it.

The only published build is [Leasegrid Sync v0.1.0 (friends & family)](https://github.com/themark-net/leasegrid-c/releases/tag/v0.1.0), commit `639163a`. **v0.1.1 is not released.** Do not look for a v0.1.1 download. More → Settings shows `Leasegrid Sync (buyer) · version 0.1.0` on that build.

The installers are unsigned. Details and the CI runners that produce them are in [`docs/ops/installers.md`](ops/installers.md).

| Your computer | Download | Runs on |
|---------------|----------|---------|
| Linux x86_64 | `Leasegrid_Sync-0.1.0-x86_64.AppImage` | glibc 2.35 or newer (Ubuntu 22.04+, Debian 12+, Fedora 36+). No `.deb`. |
| Mac | `Leasegrid_Sync-0.1.0-macos-x86_64.dmg` | Intel Macs. Apple Silicon only through Rosetta 2. |
| Windows 10/11 x64 | `Leasegrid_Sync-0.1.0-win64-setup.exe` | Same bits are in `Leasegrid_Sync-0.1.0-win64.zip` if you would rather not run the setup. |

The v0.1.0 release text prints a SHA-256 for the AppImage. Compare it before you run that file.

## Linux

```bash
chmod +x Leasegrid_Sync-0.1.0-x86_64.AppImage
./Leasegrid_Sync-0.1.0-x86_64.AppImage
```

The AppImage needs FUSE. On Ubuntu that package is `libfuse2`. With no FUSE, the documented fallback is:

```bash
./Leasegrid_Sync-0.1.0-x86_64.AppImage --appimage-extract-and-run
```

## Mac (Gatekeeper)

The disk image is ad-hoc signed only. It is not notarized. Gatekeeper reports an unidentified developer.

1. Open `Leasegrid_Sync-0.1.0-macos-x86_64.dmg`.
2. Drag **Leasegrid Sync** onto **Applications**.
3. On macOS 15 and newer, open **System Settings → Privacy & Security** and click **Open Anyway** for Leasegrid Sync. Control-click → **Open** no longer bypasses Gatekeeper on macOS 15 or newer.
4. On macOS 14 and earlier, Control-click **Leasegrid Sync** in Applications and choose **Open**, then **Open** again. If it is still blocked, use **System Settings → Privacy & Security → Open Anyway**.

From the folder that contains the app, this removes the download quarantine flag:

```bash
xattr -d com.apple.quarantine "Leasegrid Sync.app"
```

On Apple Silicon, macOS asks to install Rosetta if this Intel app has not run there before.

## Windows (SmartScreen)

The setup and the programs inside it are unsigned. SmartScreen warns that the publisher is unknown.

1. Start `Leasegrid_Sync-0.1.0-win64-setup.exe`.
2. On **Windows protected your PC**, click **More info**, then **Run anyway**.
3. Finish setup and start **Leasegrid Sync**.

Zip instead of setup: unzip `Leasegrid_Sync-0.1.0-win64.zip` and start `leasegrid-sync.exe`. The same SmartScreen dialog can appear on that file. `leasegrid-sync-cli.exe` is the console program, not the window.

## Join with an invite

A fresh install opens **Join a friendnet**. Nothing is shared until you join.

**If your window has a Short code field and a Copy code button,** you are on the current app (source commit `83b3e66`, issue [#32](https://github.com/themark-net/leasegrid-c/issues/32)). That screen is not in the v0.1.0 download. There is no newer installer.

1. The person already on the friendnet opens **Share invite** on Folders, **More → Invite…**, or **Settings → Invite others**. The card shows a QR, a **Short code** such as `7-word-word`, and **Copy code**.
2. They leave Leasegrid Sync open until you have joined. Closing the window quits. **Copy code** copies the short code.
3. You paste that code into **Invite**. A phone camera that reads the QR produces the same text. Paste it. The window has no camera button.
4. Check **I understand the four points above.** **Join friendnet** stays off until you do.
5. **Offer disk on this device** starts checked. Uncheck it when this computer should only keep folders.
6. Click **Join friendnet**. The first join can take a minute. The window then shows **Folders**.

The full join link stays under **Show full join link (advanced)**.

**If your window says Copy link,** you have the v0.1.0 download. The inviter uses **Settings → Invite others → Copy link** (the QR under that button is the same link) or **Storage servers → Add → Invite someone to Offer disk → Create invite / Copy invite**. Paste the link, a short code like `7-word-word`, or the text from a QR into **Invite**, check the four points, and click **Join friendnet**.

## Add a folder

1. On **Folders**, click **Add folder**.
2. Choose a local folder you can read and write. The dialog title is **Choose a local folder to sync**.
3. Wait through **Adding folder… first time can take a minute.**
4. The row shows Name, Status, and Local path. Put a small text file in that folder.

**Up to date** means the folder has files Magic Folder can see. **Idle** with **empty** means the folder was added and has no files yet.

## What “Connected” means

Connected means this app reached the friendnet introducer. It does not mean a folder is synced.

The chip at the top right does not print the word Connected:

| Chip | Meaning |
|------|---------|
| Online — N computers storing files | Introducer is up, and N storage computers answered. |
| Online — connected to the friendnet | Introducer is up, and the storage count is 0. |
| Connecting… | Not confirmed yet. |
| Offline | Tahoe is up and the introducer is not. |
| Can't reach the friendnet | The check failed. |

**Storage servers** uses the word **Connected** on a computer whose Tahoe connection is up. Click the chip to open that list. Folder Status (**Up to date**, **Idle**, **Conflict**, **FAIL**) is a different column.

## Known issue: Add folder HTTP 500 ([#30](https://github.com/themark-net/leasegrid-c/issues/30))

[#30](https://github.com/themark-net/leasegrid-c/issues/30) is open and parked. It does not mean the AppImage failed to start.

On an AppImage built for glibc 2.35 or newer (Ubuntu 22.04+, Debian 12+, Fedora 36+), unpaid Join reached Connected (introducer up) between the hosts plant and maximum, and the storage count settled from 3 to 0. **Add folder** then returned Magic Folder HTTP 500 on five tries for `mvp-hello.txt`. The folder never reached **Up to date**, and file-status did not list the file. The same class of error later cleared when both homes were on plant. It did not clear on maximum.

If you see HTTP 500 on Add folder, and the row never says **Up to date**, say that in the bug report and mention #30. A grid that charges for storage can also refuse an upload until **More → Credit** has a balance. That banner points at Credit. #30 was an unpaid join.

## Report a bug

Open an issue: <https://github.com/themark-net/leasegrid-c/issues/new>

Include:

- Operating system (Windows 11, macOS and whether it is Apple Silicon, Ubuntu version, and so on).
- The About line from **More → Settings** (`version 0.1.0` or whatever it shows).
- The clicks, in order, and the exact FAIL line.
- The chip text, and the folder Status if you added a folder.
- The `logs` folder from the Sync home. Useful files there are `sync-ui.log`, `tahoe.log`, and `magic-folder.log`.

| OS | Logs |
|----|------|
| Linux | `~/.local/share/leasegrid-sync/logs/` (or `$XDG_DATA_HOME/leasegrid-sync/logs/`) |
| Mac | `~/Library/Application Support/leasegrid-sync/logs/` |
| Windows | `%LOCALAPPDATA%\leasegrid-sync\logs\` |

Leave out invite codes, join links, anything that starts with `pb://`, recovery keys, and `credit-wallet.json`. Crop screenshots that show those.
