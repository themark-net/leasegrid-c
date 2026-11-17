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
