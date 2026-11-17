# Handoff: #77 Android Invite, scan the desktop QR

Branch `bot/77-qr-scan` off `main` `45e32da`. Issue [#77](https://github.com/themark-net/leasegrid-c/issues/77).

## Why this issue

Open product issues checked on 2026-11-17: #77, #81, #85 (#84 is closed). #30, #33 and #26 are out of scope. #87 has only the docs-policy item left, and that is with the CEO.

- #77 is the one open item that changes what a person can do. Short-code redeem is already on `main` (820c2712, d8372a53, c913ff5e) and shipped in v0.1.11. The other half of the issue, scanning the desktop share card's QR so nobody types or pastes, is not built.
- #81 is a Design copy call ("Saved on this phone." alone or not). It is not an engineering slice.
- #85 is a hardening list. Most of its boxes already landed without being ticked: the Import BackHandler, the storage deadline (`STORAGE_DEADLINE_S`), the list and remove copy, the class names only in logs, and the scrypt bound pins. What is left is test pins, not user-facing behaviour. It is a good audit-and-tick chore for later.

## Plan (written before code)

1. Invite screen gets a **Scan QR** button next to the field. Tapping it opens a camera scanner. The scanned text goes into the same field and through the same `Invite` checks as a paste, so a join link or a short code from the desktop QR joins exactly as typed text does. Nothing joins until the person taps Join (same as paste).
2. Scanner: `com.journeyapps:zxing-android-embedded` (Apache-2.0, ZXing). It does not need Google Play Services, so it works on de-Googled phones. It asks for the camera permission only when Scan is tapped.
3. Fail and recover copy: cancel leaves the field as it was. Permission refused says the camera was not allowed and to paste the link or type the short code instead. A QR that is not a Leasegrid join link or short code gets the existing "That isn't a join link." style copy, and the field keeps the old text.
4. Tests (JVM, behaviour of the model, not the camera): scanned join link and scanned short code land in the field and enable Join like a paste; garbage, empty, and oversized scans are refused with the copy and keep the field; cancel and permission refused do not change the field or start a join; the copy guard still passes. A wiring test checks the Scan button calls the scan path.
5. CI: `ci` and `Android Slice A` run on `feat/**` pushes, so the branch commit is pushed as `feat/77-qr-scan` first and must be green on ubuntu, windows-2022, macos-15-intel, semgrep and the debug APK job before `main` is fast-forwarded.

## Not in this slice

- A device check of scan to join (CI has no camera or emulator). Needed before #77 can close, together with the next F&F release.
- No release, tag or version bump. No change to the installers workflow. The next F&F release goes through Tester and Reviewer, and the #87 lock-path change must be flagged to them then.

## What changed

Invite on the phone has a Scan QR button under the field. It opens the ZXing capture screen (`com.journeyapps:zxing-android-embedded:4.3.0`). A result goes through `Invite.acceptScan`, then into `inviteText`. Join still waits for the tap.

The desktop share card QR is the short code (`InviteSharePanel._paint_qr(code)`). The invite page QR is the http join URL (`invite_page_html` calls `qr_svg` on that URL). A raw `pb://` address and a `leasegrid:` link are accepted too, because paste already accepts them. Whitespace, invisible paste marks, and a trailing sentence mark are stripped before the check. A scan longer than 4096 characters is refused. That is the desktop handoff bound. A typed paste is not capped, so the long join-link paste still parses.

Cancel leaves the field and any banner. A refused camera says the camera was not allowed, and the next line says to paste the join link or type the short code. A scan that is not a short code or a join link keeps the old field and shows the same banner a paste of that text would (empty field, web page, or "That isn't a join link.").

Camera hardware is optional (`uses-feature` `android.hardware.camera` `required=false`). The capture activity is `fullSensor` so `setOrientationLocked(false)` is not stuck in the library's landscape lock. Hardware acceleration stays on.

## How to verify

This machine has no Android SDK, so Gradle was not run. After a push on a `feat/**` branch (the plan name is `feat/77-qr-scan`; this worktree stays `bot/77-qr-scan` and was not pushed):

- CI job `test` on ubuntu-latest, windows-2022, and macos-15-intel, plus CI job `semgrep`.
- Android Slice A job `debug APK`: `./gradlew :app:testDebugUnitTest :app:assembleDebug` from `android/`.

Local, before that push: `QT_QPA_PLATFORM=offscreen PYTHONPATH=src pytest -q -rs`, ruff, and a dash check on the diff against `45e32da`. `tests/test_android_invite_copy.py` pins the new strings, the Scan QR button, the launcher, the optional camera feature, and the dependency line.

On a device: desktop Share invite, phone Invite, Scan QR, the short code lands in the field, tick the four points, Join. Scan the invite page QR the same way and the join link lands in the field. Back out of the camera and the field stays. Deny the camera and the paste or type line shows. Join does not run until the Join tap.

## Remaining slices

- A device check of scan to join, then #77 can close. CI has no camera.
- Scan on the Import screen is out of scope.
- No release, tag, or version bump here. The next F&F release goes through Tester and Reviewer. Flag the #87 lock-path change to them then.

## Design note

Library: `zxing-android-embedded` 4.3.0, Apache-2.0, ZXing, no Google Play Services, so a de-Googled phone can scan. The library merges the CAMERA permission and `CaptureActivity`, and asks for the camera when Scan QR is tapped. Camera hardware is not required, so a phone with no camera can still install. The library's capture activity is landscape. This manifest sets `fullSensor` with `tools:replace` so the unlocked orientation extra can follow the phone. Hardware acceleration is set on the application because the scanner uses a texture view. `tools:overrideLibrary` is not used: minSdk is 26 and the library's floor is 19.

Fail and recover: cancel is a null result and changes nothing. A missing-camera extra shows `SCAN_DENIED_MSG` / `SCAN_DENIED_NEXT` and does not join; Retry on that card does not join either. Any other result is cleaned (invisible marks, trim, quotes or brackets, trailing `. , ; : ! ?` and closing marks) and must be something `Invite.parse` accepts. If it is, the field is replaced and the old banner is cleared. If it is not, the field stays and the banner is the one parse already uses for that text. An empty scan says to enter a code or paste the link. A web address says it is the web page, not a join link. Other garbage, including a scan over 4096 characters, says "That isn't a join link." The 4096 cap is only on the scan. A typed paste of a long join link still parses.
