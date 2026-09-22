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

## Operate from adb

UiAutomator matches **content-desc**, not Compose `testTag`. Each hook sets both to the same name on **one** node. The debug APK is debuggable. Do not `adb root` (that breaks package and storage on this emulator).

Probe `join_button` by content-desc. The node’s bounds must be non-zero — `[0,0][0,0]` is a failed probe. Its `enabled` attribute is the product gate:

| threat box | invite text | `join_button` enabled |
|---|---|---|
| unchecked | empty or filled | false |
| checked | blank | false |
| checked | non-blank | true (false while a join is already running) |

Do not treat a zero-size node as enabled. The Join control does not fire while that attribute is false.

| content-desc / testTag | Control |
|---|---|
| `threat_ack` | Threat checkbox. Join stays disabled until this is checked. |
| `invite_field` | Invite `OutlinedTextField`. After the box is checked it requests focus so `input text` can land. |
| `join_button` | Join friendnet. Enabled only when the box is checked and the invite is non-blank. |
| `import_recovery_button` | Opens the system document picker (`ACTION_OPEN_DOCUMENT`). |
| `import_screen` | Import place. Present only after a recovery file is chosen or seeded. |
| `passphrase_field` | Passphrase. On Import, with non-zero bounds, before confirm. |
| `import_confirm` | Import. Enabled only when a file was read. |

`adb shell input text` mangles `:` and `/`. Prefer the debug invite extra. It fills the field and does **not** check the threat box.

```bash
adb shell am start -n net.themark.leasegrid.sync/.MainActivity \
  --es net.themark.leasegrid.sync.EXTRA_INVITE 'pb://hashhashhash@10.0.2.2:45001/swissnumswiss'
# or a deep link (URL-encode the furl):
adb shell am start -n net.themark.leasegrid.sync/.MainActivity \
  -a android.intent.action.VIEW \
  -d 'leasegrid://dogfood?invite=pb%3A%2F%2Fhashhashhash%4010.0.2.2%3A45001%2Fswissnumswiss'
```

Then tap `threat_ack` (uiautomator content-desc). The invite field takes focus. **Join friendnet** enables. A wormhole short code still fails in-app and asks for the full link.

If you would rather type: check `threat_ack` first (focus moves to `invite_field`), then `adb shell input text` a furl that needs no colon escaping, or tap the field and paste. The field is a normal outlined text field, single line, URI keyboard.

## Path A — join

1. Read the four threat points.
2. Leave the box unchecked and confirm **Join friendnet** stays disabled.
3. Check **I understand the four points above.** The invite field takes focus.
4. Paste a `pb://` introducer furl or a full `leasegrid:join#…` / `http(s)://…#v=1&i=pb://…` link. A wormhole short code (`7-word-word`) fails in-app and asks for the full link. This phone does not offer storage.
5. Join. You land on **Folders** with status **Online · unpaid** when the introducer answered. A join by itself has no folder caps, so the list can be empty until you import a recovery key. That empty state is the home, not a half-created node.

## Path B — import U4 recovery

1. From Welcome, **Import recovery key instead…** (or About → Import). The picker is `ACTION_OPEN_DOCUMENT`.
2. Pick a `*.leasegrid-recovery` file exported by desktop Sync (format v1, same file `recovery.py` writes).
3. Enter the passphrase if the file is encrypted. Empty passphrase is valid for a plaintext key. `ok-pass` uses `correct horse` (`adb shell input text 'correct%s horse'` once `passphrase_field` is focused). `ok-plain` uses an empty passphrase.
4. Tap `import_confirm`. Folder names come from the bundle. Wrong passphrase or a corrupt file shows **FAIL** and **Next** on the phone and does not write `session.json`.
5. Open a folder, tap a file, wait for **Open with…**, and hand it to a system viewer.

Pixel Launcher and DocumentsUI ANRs on TCG+lavapipe are the emulator, not the import result. Skip the picker with `ACTION_VIEW` or the debug file extra. Pass `-t application/octet-stream` so the filter matches a `file://` URI that has no host. A read that fails (scoped storage on API 34 often returns EACCES for `/sdcard`) shows **FAIL** and **Retry** and does not write a session.

```bash
adb shell am start -n net.themark.leasegrid.sync/.MainActivity \
  -a android.intent.action.VIEW -t application/octet-stream \
  -d file:///sdcard/Download/leasegrid-dogfood/ok-plain.leasegrid-recovery

# If that FAIL is EACCES, copy into the debug app files dir (no adb root) and pass a filesDir-relative path.
# shell can read /sdcard; run-as writes as the app.
adb shell "cat /sdcard/Download/leasegrid-dogfood/ok-plain.leasegrid-recovery | run-as net.themark.leasegrid.sync sh -c 'cat > files/ok-plain.leasegrid-recovery'"
adb shell am start -n net.themark.leasegrid.sync/.MainActivity \
  --es net.themark.leasegrid.sync.EXTRA_RECOVERY_FILE ok-plain.leasegrid-recovery
```

An absolute path in `EXTRA_RECOVERY_FILE` is also accepted (`/data/user/0/net.themark.leasegrid.sync/files/…` or any other readable path). A path that is not absolute is resolved under the app files dir. Import does not run by itself.

Cold-start after a data wipe. Seed the file only after `pm clear`, then start. The extra opens Import before the first frame and retries the read if the file is not visible yet. A miss still shows Import with FAIL and Retry — not Welcome.

```bash
adb shell am force-stop net.themark.leasegrid.sync
adb shell pm clear net.themark.leasegrid.sync
# seed ok-pass.leasegrid-recovery into the app files dir, then:
adb shell am start -n net.themark.leasegrid.sync/.MainActivity \
  --es net.themark.leasegrid.sync.EXTRA_RECOVERY_FILE ok-pass.leasegrid-recovery
```

Wait for content-desc `import_screen` and `passphrase_field`. Welcome (`threat_ack`, `invite_field`, `join_button`) means the extra did not apply. `ok-pass` needs `correct horse` in `passphrase_field` (`adb shell input text 'correct%s horse'`), then `import_confirm`. `ok-plain` confirms with an empty passphrase. `corrupt` confirms and must show FAIL + Next without writing `session.json`. A file that cannot be read shows FAIL and Retry on Import and does not write a session. An introducer that does not answer is the environment; an empty Folders list after a successful import or join is OK.

## FAIL

Airplane mode (or a dead introducer) on download or refresh shows **FAIL — …** and **Next: …** with **Retry** and **Dismiss**. There is no “Open Tahoe WUI” action.

## Out of this build

No upload, no Magic Folder sync, no Offer pie, no Credit gate, no recovery export (that stays on desktop Sync), no second recovery format.

## What to report

PASS or FAIL, emulator image (API level), APK path, git SHA, issue #23. Do not include a Mark drip, Play Store claim, or Slice B / U5 claim.
