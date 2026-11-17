# Handoff: #88 QR scan polish

Branch `bot/88-qr-polish` off `main` `c283d2d`. Issue [#88](https://github.com/themark-net/leasegrid-c/issues/88), found in the #77 device check.

## Root cause

- (a) The scanner library asks for the camera itself after it opens. When the person taps "Don't allow", the library shows its own "camera encountered a problem" dialog and only then returns to us, so our paste guidance came second.
- (b) The fail card always drew a Retry button. A banner with no action (bad scan, refused camera, an unreadable picked file) still showed it, and tapping it only cleared the card, like Dismiss.

## What changed

- `MainActivity.kt`: Scan QR now checks the CAMERA permission first. If it is missing, our activity asks (`ActivityResultContracts.RequestPermission`). Allowed opens the scanner. Refused goes straight to `onScanDenied()`, so the scanner and its dialog never open. The old `MISSING_CAMERA_PERMISSION` check stays as a fallback.
- `AppModel.kt`: `onScanTapped` and `onCameraAnswer` hold that decision so JVM tests can see it. New `canRetry` is true only while a real Retry action is armed. Two unreadable file banners that armed an empty `{ }` Retry now arm none.
- `RetryOnce.kt`: `armed` is Compose state, true only while an action waits.
- `SyncApp.kt`: the fail card shows Retry only when `model.canRetry`. Dismiss always shows. Real retries (join with the field as it is now, learn, grid, import) keep Retry.
- `AndroidManifest.xml`: CAMERA declared in our manifest (the library merged it before).

## Tests

- `AppModelFlowTest`: `aBadScanAndARefusedCameraOfferDismissButNoRetry`, `aJoinParseFailStillOffersARealRetryWithTheFieldAsItIsNow`, `scanAsksForTheCameraFirstAndARefusalNeverOpensTheScanner`.
- `RetryOnceTest.armedIsTrueOnlyWhileARealActionWaits`.
- `SyncAppWiringTest.theFailCardOffersRetryOnlyWhenThereIsSomethingToRetry` and new lines in `scanQrButtonOnInviteCallsTheScanner`.
- `tests/test_android_invite_copy.py::test_scan_asks_for_the_camera_first_and_the_fail_card_hides_retry_without_an_action` failed on `main` before the change and passes after.

## How to verify

CI on `feat/88-qr-polish` then `main`: ubuntu, windows-2022, macos-15-intel, semgrep, Android Slice A debug APK. On a device or emulator: Invite, Scan QR, Don't allow shows only our camera card with Dismiss and no Retry; a non invite QR shows the banner with Dismiss only; a bad paste then Join still offers Retry.

## Remaining

- An emulator recheck of the refused camera path if PM wants one.
- No release, tag or version bump. Ships with the next F&F release through Tester and Reviewer, together with #77 and the #87 lock path change.
