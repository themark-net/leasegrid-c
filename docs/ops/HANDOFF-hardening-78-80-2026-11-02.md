# Handoff hardening #78 and #80

Branch: `build/hardening-78-80`
Base: `origin/main` @ `7ce0785691b925c4b2f0ef06f7cd3c7d2796386a`
Worktree: `~/DEVELOP/leasegrid-c/tmp/hardening-78-80`
Date: 2026-11-02
Not a release. Pushed to `build/hardening-78-80` and `feat/hardening-78-80` (CI). No PR. No merge. Issues cited: #78 and #80 only.

Product changes from `bot/lg-78-invite-1031` (`97ee7e6`, `be0a398`, `a9b1b38`) and `bot/lg-80-appmodel-1031` (`f401a80`, `724982c`, `c64c043`, `9b7bbed`, `1a12026`, `d065a2c`, `642a416`) are on this branch. Lane drop-ins, run logs, lane handoffs, lane decision files, and `.gitignore` edits were not taken.

## Done

| Item | Commit | What the user sees |
| --- | --- | --- |
| Root cause notes, before the fixes | `9b62187` | `docs/ops/ROOT-CAUSE-hardening-78-80.md` |
| #78 long paste | `f4d8e58` | A ~100 KB near-miss shows "That isn't a join link." It does not throw. |
| #78 Retry after that paste | `550907e` | Retry, after the field is replaced, joins the corrected link. |
| #78 cancel ghost banner | base `4ab71a0`; test `550907e` | A cancelled join does not paint "Couldn't reach your computer." A later join still saves. |
| #80 F1 dirty or short link | `db08dcc` | NUL, U+FFFD, a `+` that becomes a space, a newline, or a swissnum under 8 characters shows "That join link is incomplete." learn() is not called. |
| #80 F2 zero-width marks | `fa1a5c7` | Leading or trailing U+200B or U+FEFF still joins. Marks only: "Paste the join link first." |
| #80 F4 busy ticket | `ea9b803` | A cancelled grid job clears busy only if it is still the current job. |
| #80 Retry once | `df11bea` | A second Retry tap does not run the action again. |
| #80 bad recovery file | `608a679` | A damaged recovery file shows the import card, with Retry. |
| #80 friendnet copy | `113878a` | Phone strings say shared folder. Chips: "Not in the shared folder yet" and "In the shared folder". |
| #80 FlowHost pins and SyncApp guard | `d1dc8c7` | Cleared invite text, a null learn, or a dropped Retry action fails the pin. The guard reads every SyncApp.kt literal. |
| #80 generic grid Retry | `e213a26` | The card says "could not complete that." Retry runs the block once. |
| #80 download next line | `4f0c011` | The next line is "check network / free space; Retry." The class name is not on it. |
| #80 em dash and en dash | `58c64ee` | The guard flags U+2014 and U+2013. Remaining threat lines and the fail title use a colon. |
| #80 split Introducer (K3c) | `58c64ee` | "Intro" + "ducer" and "intro-\nducer" fail the guard. |
| Design 61 scope and PM sentence | `58c64ee` | The Tests line names the same files as the guard scope. The cancel-import sentence is in the note. |
| Import cancel lock | `550907e` | Cancelling learn() during import saves nothing. A later import still saves. |

## Red-first evidence

Python, against `git show 7ce07856:tests/test_android_invite_copy.py` loaded from `/tmp/lg-red-78-80/`. `/usr/bin/python3` has no pytest. The red run used `/home/mark/tahoe-venv/bin/pytest /tmp/lg-red-78-80/test_red_expectations.py` (that venv was not modified). 2 failed:

- `test_em_dash_and_en_dash_are_banned`: `AssertionError: assert [] == ['trust U+2014 unpaid']`
- `test_split_introducer_is_caught_by_the_new_scan`: `AssertionError: "Intro" + "ducer"` then `assert []` from `old._banned(['Intro', 'ducer'])`

The per-literal scan also misses `"intro-" + "ducer"`, `"INTRO" + "DUCER"`, `"intro " + " ducer"`, and `"intro-\nducer"`. En dash fails the same way as the em dash; the first assertion stopped the test.

Green on this branch: `.venv/bin/python -m pytest tests/test_android_invite_copy.py -q` → `15 passed in 0.02s`.

Kotlin was not compiled here (no Android SDK, no Gradle). Each test below goes red if the named production file is restored from `7ce07856`. `GridRun.kt` and `RetryOnce.kt` do not exist on that base. Restoring `AppModel.kt` from `7ce07856` is the same behavior: `finally` always clears busy, and `retryFail` does not clear the action. The new test classes then fail to compile until those types are deleted, which is the red state.

| Test | Production file restored from `7ce07856` |
| --- | --- |
| `InviteCopyTest.aHundredKilobytePasteDoesNotOverflowAndStaysAPlainError` | `Invite.kt` (regex at the old line 12) |
| `SessionFlowTest.retryAfterAHundredKilobytePasteJoinsTheCorrectedLink` | `Invite.kt` |
| `InviteCopyTest.dirtyFurlsAreIncompleteAndACleanLinkStillJoins` | `Invite.kt` `validateFurl` |
| `SessionFlowTest.retryAfterAMalformedPasteJoinsTheCorrectedLink` | `Invite.kt` |
| `InviteCopyTest.invisiblePasteMarksStillParseAndAMarksOnlyPasteAsksForTheLink` | `Invite.kt` `parse` / `validateFurl` trim |
| `SessionFlowTest.aMarkedPasteJoinsAndAMarksOnlyPasteRecoversOnRetry` | `Invite.kt` |
| `GridRunTest.cancelledJobDoesNotClearBusyWhileANewerJobRuns` | `AppModel.kt` `runGrid` finally, or delete the ticket check in `GridRun.kt` |
| `RetryOnceTest.aSecondTapDoesNotRunTheActionAgain` | `AppModel.kt` `retryFail` (the field stays set) |
| `RetryOnceTest.appModelPullsTheRetryBeforeItRuns` | `AppModel.kt` |
| `RecoveryCodecTest.badRecoveryFileFailsClosed` | `RecoveryCodec.kt` (`bundle` jsonObject, `shares` jsonArray) |
| `FolderWriteTest.pendingStaysNotOnFriendnetUntilAcknowledge` | `FolderWrite.kt` `PENDING` / `LANDED` |
| `GridFailTest.unexpectedCardDoesNotNameTheExceptionClass` | `AppModel.kt` `runGrid` card text |
| `GridFailTest.oneRetryRerunsTheBlockAndASecondTapDoesNot` | `AppModel.kt` `runGrid` Retry lambda |
| `GridFailTest.downloadFailureDoesNotNameTheExceptionClass` | `AppModel.kt` download next line |

Already green on `7ce07856` (behavior shipped in `4ab71a0`, not a red fix): `SessionFlowTest.aCancelledJoinPaintsNothing` and `SessionFlowTest.aCancelledImportSavesNothingAndALaterImportSaves`. `InviteCopyTest.aHundredKilobyteJoinLinkStillParses` is also green on the base: that paste does not match the short-code regex, so it does not overflow. It stays so a long real link still parses after the length cap.

## Tests and counts

- `.venv/bin/python -m pytest tests/test_android_invite_copy.py -q` → **15 passed**, 0 failed, 0 skipped, 0 xfailed, 0.02s. `/usr/bin/python3 -m pytest` cannot run: `No module named pytest`. The venv is the one `scripts/ci-local.sh` uses on this linked worktree.
- `scripts/ci-local.sh` (detached, log was `tmp/ci-local.log`, deleted after the count was copied here) → **PASS**. Pytest: **619 passed, 5 xfailed, 0 failed, 0 skipped**, 4 warnings, 143.20s. Ruff passed. Semgrep scan: 0 findings. Gradle was not run.

## How it fails and how it recovers

- Long paste. Before: `StackOverflowError` in the short-code regex. After: `GARBAGE_MSG`, no Next line. Replace the field and tap Retry. learn() runs for the corrected link. A real short code still shows `WORMHOLE_MSG`. A ~100 KB well-formed join link still parses.
- Cancelled join. learn() rethrows `CancellationException`. SessionFlow does not call show(), so the failure card is not painted over a newer attempt. The newer join can save.
- Dirty link. The banner is `MALFORMED_MSG`. learn() is not called. Replace the field and tap Retry. The corrected link joins.
- Paste marks. Leading and trailing U+200B and U+FEFF are stripped, including a mark percent-encoded onto either end. A mark in the middle stays. Marks only: `EMPTY_MSG`. Retry with the real link calls learn().
- Busy. An older finally no longer clears busy under a newer job. The current job still clears busy when it finishes. Cancel clears busy immediately.
- Retry. The action is taken out of the slot before it runs. A second tap does nothing. A new failure can arm a new action.
- Recovery file. A bundle that is not an object, or shares that are not an array, is `ImportFail` with the import message and a Retry next line. The file is not imported.
- Copy. A friendnet chip or a friendnet sentence in SyncApp fails `FolderWriteTest` or the SyncApp guard. An em dash or en dash in a guarded literal fails the same guard.
- Generic grid failure. The class name is logged, not shown. Retry runs the block once. A second tap does not.
- Download. The next line does not name the class. Retry still starts the same download.
- Introducer. A split of the word across `+`, a line break, case, or whitespace fails the guard. The JSON key `introducer_furl` is still allowed.
- Import cancel. Cancellation during learn() saves nothing. The user can import again. If the computer cannot be reached, the save is kept and the screen shows "Saved on this phone. Couldn't reach your computer to finish."

## Follow-up issues to file

Do not implement these on this branch. They are product or design forks, or they were outside the listed items.

Title: Android import-saved banner: decide whether "Saved on this phone." stands alone

Body: `Invite.IMPORT_SAVED_MSG` is "Saved on this phone. Couldn't reach your computer to finish." Design 61 records that an unreachable import keeps the save and that this matches "Saved on this phone...". A shorter banner that is only "Saved on this phone." was not adopted. If Design wants that shorter line, it is a copy change. The unreachable path must still say the finish step did not complete, or the phone will look fully joined when it is not.

Title: Join-failure Next line gives paste advice for every learn() failure

Body: `JOIN_FAILED_NEXT` tells the user to copy the join link again after any failed learn(), including a timeout when the link was already accepted. Refresh and import use `REFRESH_FAILED_NEXT`, which does not say paste. This branch did not change `JOIN_FAILED_NEXT`. The phone cannot tell a rejected link from an unreachable computer (one ReadFail). A separate line needs a Design call.

Title: Design packs 55-59 still say friendnet and use an em dash in FAIL

Body: Phone chips are "Not in the shared folder yet" and "In the shared folder". The phone fail title is "FAIL:". `docs/design/55` through `59`, and tester pages that quote them, still say "On friendnet", "Not on friendnet yet", and "FAIL U+2014". Align those packs with the phone, or record that they keep the older wording. This branch did not edit them.

Title: Android file-read failures still append the exception class

Body: `MainActivity.readAddedFile` and `readRecovery` put `exc.javaClass.simpleName` on the Next line. Download and the generic grid card no longer do this (#80). Log the class and keep the plain next line. Left out of this branch because it was not one of the listed #78 or #80 items.

## Box verification (Gradle, 2026-11-02)

Run on the box (JDK 17, Android SDK 34) from a clone at `1250037`, via `android/./gradlew --no-daemon :app:compileDebugKotlin :app:testDebugUnitTest :app:assembleDebug`.

- Base `7ce07856`: BUILD SUCCESSFUL, **44 tests, 0 failures**.
- This branch: BUILD SUCCESSFUL, **61 tests, 0 failures, 0 errors, 0 skipped**; debug APK assembled.

Kotlin red-first, each run with only the named change on top of this branch, then restored:

| Change | Red tests (61 run) |
| --- | --- |
| `Invite.kt` from `7ce07856` | 6: `InviteCopyTest.aHundredKilobytePasteDoesNotOverflowAndStaysAPlainError` (StackOverflowError), `.dirtyFurlsAreIncompleteAndACleanLinkStillJoins`, `.invisiblePasteMarksStillParseAndAMarksOnlyPasteAsksForTheLink` ("That isn't a join link" for U+200B), `SessionFlowTest.retryAfterAHundredKilobytePasteJoinsTheCorrectedLink`, `.retryAfterAMalformedPasteJoinsTheCorrectedLink`, `.aMarkedPasteJoinsAndAMarksOnlyPasteRecoversOnRetry` |
| `RecoveryCodec.kt` from `7ce07856` | 1: `RecoveryCodecTest.badRecoveryFileFailsClosed` (raw "is not a JsonObject") |
| `FolderWrite.kt` from `7ce07856` | 2: `FolderWriteTest.pendingStaysNotOnFriendnetUntilAcknowledge`, `.silenceShowsExistingFailAndDoesNotSayOnFriendnet` ("Not on friendnet yet") |
| `AppModel.kt` from `7ce07856` | 3: `GridFailTest.downloadFailureDoesNotNameTheExceptionClass`, `.oneRetryRerunsTheBlockAndASecondTapDoesNot`, `RetryOnceTest.appModelPullsTheRetryBeforeItRuns` |
| `GridRun.kt` finally clears busy unconditionally (base behavior) | 1: `GridRunTest.cancelledJobDoesNotClearBusyWhileANewerJobRuns` ("older finally cleared busy while the newer job was still running") |
| `RetryOnce.pull` does not clear the slot (base behavior) | 3: `RetryOnceTest.aSecondTapDoesNotRunTheActionAgain`, `.aNewFailureCanBeRetriedAfterTheFirstTap`, `GridFailTest.oneRetryRerunsTheBlockAndASecondTapDoesNot` |

Not red by a file restore: `GridFailTest.unexpectedCardDoesNotNameTheExceptionClass` tests `unexpectedGridCard()` in the new `GridRun.kt` (the base had the class-name text inline in `runGrid`, which `D` covers). `SessionFlowTest.aCancelledJoinPaintsNothing` and `.aCancelledImportSavesNothingAndALaterImportSaves` lock behavior already shipped in `4ab71a0`.

nimo `scripts/ci-local.sh` re-run on `1250037`: **619 passed, 5 xfailed, 0 failed**, ci-local PASS.

## Gate

Tester and Reviewer. Runtime changes are in `Invite.kt`, `AppModel.kt`, `GridRun.kt`, `RetryOnce.kt`, `RecoveryCodec.kt`, `SyncApp.kt`, and `FolderWrite.kt`. Kotlin unit tests ran on the box (61/0 failures, red-first table above). Python ci-local passed, counts above.

## Next

Tester and Reviewer on `build/hardening-78-80`. Implementation by Grok Build headless on nimo (Hermes `-z` produced no response three times; see decisions). Do not merge until Tester and Reviewer pass.
