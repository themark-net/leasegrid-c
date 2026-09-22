# P4 Android Slice A — emulator dogfood (And)

**Product:** Leasegrid Sync, read-first APK.  
**Issue:** [#23](https://github.com/themark-net/leasegrid-c/issues/23)  
**Handoff:** [docs/design/39-P4-ANDROID-A-DEVBOT-HANDOFF.md](../design/39-P4-ANDROID-A-DEVBOT-HANDOFF.md)  
**Base:** main ≥ `7837ef8`  
**Application id:** `net.themark.leasegrid.sync`  
**minSdk:** 26 · **target/compile:** 34 · **ABIs:** `arm64-v8a`, `x86_64`

This note is for **And**. It does not claim Play Store, iOS, Slice B write/sync, or U5/mainnet.

## APK

| | |
|---|---|
| Debug APK | `android/app/build/outputs/apk/debug/app-debug.apk` |
| CI artifact | `leasegrid-sync-android-slice-a-debug.apk` |
| Install | `adb install -r android/app/build/outputs/apk/debug/app-debug.apk` |

Local rebuild (JDK 17+, Android SDK 34, NDK 26):

```bash
cd android
# local.properties: sdk.dir=/path/to/android-sdk
./gradlew :app:testDebugUnitTest :app:assembleDebug
```

## Emulator

API 34 or newer image (x86_64 is fine). Launch **Leasegrid Sync**. The product UI is Jetpack Compose. There is no Tahoe web UI and no browser chrome.

Loopback friendnets (`127.0.0.1` / `localhost` in an invite or storage furl) are also tried as `10.0.2.2`, the emulator’s alias for the host. A grid running on the dogfood machine is reachable that way. A physical phone cannot use that alias; use a LAN address in the invite.

## Path A — join

1. Read the four threat points.
2. Leave the box unchecked and confirm **Join friendnet** stays disabled.
3. Check **I understand the four points above.**
4. Paste a `pb://` introducer furl or a full `leasegrid:join#…` / `http(s)://…#v=1&i=pb://…` link. A wormhole short code (`7-word-word`) fails in-app and asks for the full link. This phone does not offer storage.
5. Join. You land on **Folders** with status **Online · unpaid** when the introducer answered. A join by itself has no folder caps, so the list can be empty until you import a recovery key. That empty state is the home, not a half-created node.

## Path B — import U4 recovery

1. From Welcome, **Import recovery key instead…** (or About → Import).
2. Pick a `*.leasegrid-recovery` file exported by desktop Sync (format v1, same file `recovery.py` writes).
3. Enter the passphrase if the file is encrypted. Empty passphrase is valid for a plaintext key.
4. Import. Folder names come from the bundle. Wrong passphrase or a corrupt file shows **FAIL** and **Next** on the phone and does not write `session.json`.
5. Open a folder, tap a file, wait for **Open with…**, and hand it to a system viewer.

## FAIL

Airplane mode (or a dead introducer) on download or refresh shows **FAIL — …** and **Next: …** with **Retry** and **Dismiss**. There is no “Open Tahoe WUI” action.

## Out of this build

No upload, no Magic Folder sync, no Offer pie, no Credit gate, no recovery export (that stays on desktop Sync), no second recovery format.

## What to report

PASS or FAIL, emulator image (API level), APK path, git SHA, issue #23. Do not include a Mark drip, Play Store claim, or Slice B / U5 claim.
