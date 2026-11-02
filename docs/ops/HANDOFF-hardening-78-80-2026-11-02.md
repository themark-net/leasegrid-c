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
| #80 F2 zero-width marks | `fa1a5c7`, Tester S2 `56c8fe9` | U+200B, U+200C, U+200D, U+2060 and U+FEFF are dropped anywhere in the paste, so a marked link still joins. Marks only: "Paste the join link first." |
| #80 F4 busy ticket | `ea9b803` | A cancelled grid job clears busy only if it is still the current job. |
| #80 Retry once | `df11bea` | A second Retry tap does not run the action again. |
| #80 bad recovery file | `608a679` | A damaged recovery file shows the import card, with Retry. |
| #80 friendnet copy | `113878a` | Phone strings say shared folder. Chips: "Not in the shared folder yet" and "In the shared folder". |
| #80 FlowHost pins and SyncApp guard | `d1dc8c7` | Cleared invite text, a null learn, or a dropped Retry action fails the pin. The guard reads every SyncApp.kt literal. |
| #80 generic grid Retry | `e213a26` | The card says "could not complete that." Retry runs the block once. |
| #80 download next line | `4f0c011` (Kotlin catch), `370bb84` (Python dispatch) | The next line is "check network / free space; Retry." with no class name, both when the grid call throws (Kotlin) and when `leasegrid_read.dispatch` returns its `OSError` fallback (Python). The last-resort message is "could not complete that." The class goes to the log. |
| #80 em dash and en dash | `58c64ee` | The guard flags U+2014 and U+2013. Remaining threat lines and the fail title use a colon. |
| #80 split Introducer (K3c) | `58c64ee` | "Intro" + "ducer" and "intro-\nducer" fail the guard. |
| Design 61 scope and PM sentence | `58c64ee` | The Tests line names the same files as the guard scope. The cancel-import sentence is in the note. |
| Import cancel lock | `550907e`, Tester T1 `65ce6e9` | Cancel and the back arrow on the import screen call `cancelImport()`: the running import stops, nothing is saved, and the screen goes to Welcome. A later import still saves. |
| Reviewer B1 dashes in docs | `f34d3da` | No added line in the branch diff has U+2014 or U+2013. Quoted old strings write the dash as `U+2014`. |
| Reviewer B2 Retry through AppModel | `ea6acea` | `AppModelRetryTest` builds the real `AppModel` (internal `AppSeams` constructor, fake grid). A failed folder load or download shows the card and its Retry. Two taps run the grid call once. |
| Reviewer follow-up 1 busy | `a72ed33` | Cancel clears busy at once. Busy clears after an error. |
| Tester root causes and decisions | `bb640f3` | `ROOT-CAUSE-hardening-78-80.md` section "Tester pass on 2be4d7e"; 14 lines in `AUTONOMOUS-DECISIONS-2026-11-02.md`. |
| Tester B3 `lg_tahoe.py:404` | `46c51ec` | A failed share fetch shows "check network / free space; Retry." with nothing after it. The last error goes to the log. |
| Tester S2, S4 | `56c8fe9` | Invisible marks anywhere are dropped. `pb://@host/swiss` is "That join link is incomplete." `pb://tubid/swiss` and `pb://tubid@/swiss` ask for the address. |
| Tester S1, S3 | `cdeba16` | A recovery file over 1 MiB, nested deeper than 32, or with scrypt n, r, p over the caps (n a power of two up to 2^20, r up to 32, p up to 16, 128*r*n up to 64 MiB) shows the import card. The recovery furl goes through the same `validateFurl` as a pasted link. Shares need 1 <= needed <= happy <= total <= 256. An added file over 64 MB shows "pick a file under 64 MB." |
| Tester T1, B3 call sites, S5 | `65ce6e9` | Import Cancel stops the import. A bridge that throws at folder load, download, add or remove shows a card with no class name, no `pb://`, no `Errno`. `MainActivity` file reads log the class and keep a plain next line. `GridFailTest` (constant tests) is deleted. |
| Tester U8, E5 to E12, S5 pins | `b962390` | The copy guard also reads `AppModel.kt` and `MainActivity.kt`, and sees through `\u` escapes, invisible marks, Cyrillic look-alikes, string templates, `+`, `.plus`, `append`, and char runs. FlowHost pins match whole lines. |

## Red-first evidence

Python, against `git show 7ce07856:tests/test_android_invite_copy.py` loaded from `/tmp/lg-red-78-80/`. `/usr/bin/python3` has no pytest. The red run used `/home/mark/tahoe-venv/bin/pytest /tmp/lg-red-78-80/test_red_expectations.py` (that venv was not modified). 2 failed:

- `test_em_dash_and_en_dash_are_banned`: `AssertionError: assert [] == ['trust U+2014 unpaid']`
- `test_split_introducer_is_caught_by_the_new_scan`: `AssertionError: "Intro" + "ducer"` then `assert []` from `old._banned(['Intro', 'ducer'])`

The per-literal scan also misses `"intro-" + "ducer"`, `"INTRO" + "DUCER"`, `"intro " + " ducer"`, and `"intro-\nducer"`. En dash fails the same way as the em dash; the first assertion stopped the test.

Green on this branch: `.venv/bin/python -m pytest tests/test_android_invite_copy.py -q` → `15 passed in 0.02s`.

Kotlin cannot compile on nimo (no Android SDK), so Kotlin ran on the box; counts are in "Box verification" below. Each test below goes red if the named production file is restored from `7ce07856`. `GridRun.kt` and `RetryOnce.kt` do not exist on that base. Restoring `AppModel.kt` from `7ce07856` is the same behavior: `finally` always clears busy, and `retryFail` does not clear the action. The new test classes then fail to compile until those types are deleted, which is the red state.

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
| `RecoveryCodecTest.badRecoveryFileFailsClosed` | `RecoveryCodec.kt` (`bundle` jsonObject, `shares` jsonArray) |
| `FolderWriteTest.pendingStaysNotOnFriendnetUntilAcknowledge` | `FolderWrite.kt` `PENDING` / `LANDED` |
| `AppModelFlowTest` (9 tests; replaced `GridFailTest`, deleted by Tester S5) | mutants in "Tester fixes" below |
| `AppModelRetryTest` (4 tests) | mutants K15 and K16, see "Reviewer fixes" below |

Already green on `7ce07856` (behavior shipped in `4ab71a0`, not a red fix): `SessionFlowTest.aCancelledJoinPaintsNothing` and `SessionFlowTest.aCancelledImportSavesNothingAndALaterImportSaves`. `InviteCopyTest.aHundredKilobyteJoinLinkStillParses` is also green on the base: that paste does not match the short-code regex, so it does not overflow. It stays so a long real link still parses after the length cap.

## Tests and counts

- At the earlier pin 2be4d7e: `.venv/bin/python -m pytest tests/test_android_invite_copy.py -q` → **15 passed**, 0 failed, 0 skipped, 0 xfailed, 0.02s. `/usr/bin/python3 -m pytest` cannot run: `No module named pytest`. The venv is the one `scripts/ci-local.sh` uses on this linked worktree.
- At the earlier pin 2be4d7e: `scripts/ci-local.sh` (detached, log was `tmp/ci-local.log`, deleted after the count was copied here) → **PASS**. Pytest: **619 passed, 5 xfailed, 0 failed, 0 skipped**, 4 warnings, 143.20s. Ruff passed. Semgrep scan: 0 findings. Gradle was not run.

## How it fails and how it recovers

- Long paste. Before: `StackOverflowError` in the short-code regex. After: `GARBAGE_MSG`, no Next line. Replace the field and tap Retry. learn() runs for the corrected link. A real short code still shows `WORMHOLE_MSG`. A ~100 KB well-formed join link still parses.
- Cancelled join. learn() rethrows `CancellationException`. SessionFlow does not call show(), so the failure card is not painted over a newer attempt. The newer join can save.
- Dirty link. The banner is `MALFORMED_MSG`. learn() is not called. Replace the field and tap Retry. The corrected link joins.
- Paste marks. U+200B, U+200C, U+200D, U+2060 and U+FEFF are dropped anywhere in the paste (`stripPaste`, Invite.kt), including a mark percent-encoded onto either end, so a marked link still joins. Marks only: `EMPTY_MSG`. Retry with the real link calls learn().
- Busy. An older finally no longer clears busy under a newer job. The current job still clears busy when it finishes. Cancel clears busy immediately.
- Retry. The action is taken out of the slot before it runs. A second tap does nothing. A new failure can arm a new action.
- Recovery file. A bundle that is not an object, or shares that are not an array, is `ImportFail` with the import message and a Retry next line. The file is not imported.
- Copy. A friendnet chip or a friendnet sentence in SyncApp fails `FolderWriteTest` or the SyncApp guard. An em dash or en dash in a guarded literal fails the same guard.
- Generic grid failure. The class name is logged, not shown. Retry runs the block once. A second tap does not.
- Download. The next line does not name the class, whether the grid call throws (Kotlin catch) or Python `dispatch` returns its `OSError` fallback. Python logs `dispatch <op> failed: <Class>` with no payload. Retry still starts the same download, once per tap.
- Introducer. A split of the word across `+`, a line break, case, or whitespace fails the guard. The JSON key `introducer_furl` is still allowed.
- Import cancel. Cancellation during learn() saves nothing. The user can import again. If the computer cannot be reached, the save is kept and the screen shows "Saved on this phone. Couldn't reach your computer to finish."

## Follow-up issues to file

Do not implement these on this branch. They are product or design forks, or they were outside the listed items.

Title: Python learn next line names the exception class

Body: `lg_intro.py:177` and `:194` put `type(exc).__name__` on the learn next line. `AppModel.learn()` only logs that result and never shows it, so it is not on screen today. If a later change shows learn's copy, drop the class there first.

Title: Android import-saved banner: decide whether "Saved on this phone." stands alone

Body: `Invite.IMPORT_SAVED_MSG` is "Saved on this phone. Couldn't reach your computer to finish." Design 61 records that an unreachable import keeps the save and that this matches "Saved on this phone...". A shorter banner that is only "Saved on this phone." was not adopted. If Design wants that shorter line, it is a copy change. The unreachable path must still say the finish step did not complete, or the phone will look fully joined when it is not.

Title: Join-failure Next line gives paste advice for every learn() failure

Body: `JOIN_FAILED_NEXT` tells the user to copy the join link again after any failed learn(), including a timeout when the link was already accepted. Refresh and import use `REFRESH_FAILED_NEXT`, which does not say paste. This branch did not change `JOIN_FAILED_NEXT`. The phone cannot tell a rejected link from an unreachable computer (one ReadFail). A separate line needs a Design call.

Title: Design packs 55-59 still say friendnet and use an em dash in FAIL

Body: Phone chips are "Not in the shared folder yet" and "In the shared folder". The phone fail title is "FAIL:". `docs/design/55` through `59`, and tester pages that quote them, still say "On friendnet", "Not on friendnet yet", and "FAIL U+2014". Align those packs with the phone, or record that they keep the older wording. This branch did not edit them.

Title: Android copy guard cannot follow a word split across variables or built at run time

Body: `tests/test_android_invite_copy.py` normalizes each file (escapes, invisible marks, Cyrillic look-alikes, templates, `+`, `.plus`, `append`, char runs) before it looks for "introducer", "friendnet" or a dash. `val a = "Intro"; val b = "ducer"; "$a$b"` and text built from data at run time still pass (Tester E5). Catching that needs data flow (a compiler plugin or a device string dump). Decision line in `AUTONOMOUS-DECISIONS-2026-11-02.md`.

Title: Tester mutant bodies for the 2be4d7e pass are not in the repo

Body: The Tester FAIL named mutants (N4b, H78b/d/e, F1e, F1i, F4b, F4c, K9, A5, A6, A8, A9, C3, C4, R2 to R4, F4e, F4f) but not their diffs. This branch killed its own version of each (table in "Tester fixes" below). Tester should re-run the original bodies on `b962390` or later and file any survivor.

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
| `AppModel.kt` from `7ce07856` | 3: `GridFailTest.downloadFailureDoesNotNameTheExceptionClass`, `.oneRetryRerunsTheBlockAndASecondTapDoesNot`, `RetryOnceTest.appModelPullsTheRetryBeforeItRuns` (these three read source text; Reviewer B2 deleted the last two and the source read in the first) |
| `GridRun.kt` finally clears busy unconditionally (base behavior) | 1: `GridRunTest.cancelledJobDoesNotClearBusyWhileANewerJobRuns` ("older finally cleared busy while the newer job was still running") |
| `RetryOnce.pull` does not clear the slot (base behavior) | 3: `RetryOnceTest.aSecondTapDoesNotRunTheActionAgain`, `.aNewFailureCanBeRetriedAfterTheFirstTap`, `GridFailTest.oneRetryRerunsTheBlockAndASecondTapDoesNot` |

Not red by a file restore: `GridFailTest.unexpectedCardDoesNotNameTheExceptionClass` tests `unexpectedGridCard()` in the new `GridRun.kt` (the base had the class-name text inline in `runGrid`, which `D` covers). `SessionFlowTest.aCancelledJoinPaintsNothing` and `.aCancelledImportSavesNothingAndALaterImportSaves` lock behavior already shipped in `4ab71a0`.

nimo `scripts/ci-local.sh` re-run on `1250037`: **619 passed, 5 xfailed, 0 failed**, ci-local PASS.

## Reviewer fixes (second pass, 2026-11-02)

Reviewer FAIL on `2be4d7e`: B1 dashes in docs, B2 tautological Retry tests (K15 and K16 survived), B3 false class-name claim. Root causes are in `docs/ops/ROOT-CAUSE-hardening-78-80.md` under "Reviewer B1", "Reviewer B2", "Reviewer B3", and "Reviewer follow-up 1".

| Blocker | Commit | Files |
| --- | --- | --- |
| B1 | `f34d3da` | This file (lines 37, 99), `ROOT-CAUSE-hardening-78-80.md` (lines 65, 97): the quoted em dash is written as `U+2014`. `git diff 7ce07856` has no added line with U+2014 or U+2013. |
| B3 | `370bb84` | `android/app/src/main/python/leasegrid_read.py`: the `OSError` and last-resort fallbacks return plain copy and log the class. New `android/pytests/test_dispatch_copy.py` (3 tests). |
| B2 | `ea6acea` | `AppModel.kt`: internal `AppSeams` constructor; `AppModel(app)` passes today's values. New `AppModelRetryTest.kt` (4 tests). Deleted `GridFailTest.oneRetryRerunsTheBlockAndASecondTapDoesNot`, `RetryOnceTest.appModelPullsTheRetryBeforeItRuns`, and the source read in `GridFailTest.downloadFailureDoesNotNameTheExceptionClass`. |
| Follow-up 1 | `a72ed33` | `GridRunTest.kt`: 2 tests. |

Red-first, Python (nimo, `.venv/bin/python -m pytest android/pytests/test_dispatch_copy.py`, before the `leasegrid_read.py` change): 2 failed, 1 passed.

- `test_a_download_that_cannot_be_written_does_not_name_the_class`: `assert 'check networ...otFoundError)' == 'check networ...space; Retry.'`
- `test_an_unexpected_failure_does_not_name_the_class`: `assert 'could not co...t. ValueError' == 'could not complete that.'`
- `test_the_log_line_keeps_only_the_class_not_the_payload` was green before the fix (nothing was logged). It guards the new log line against a furl or the payload.

After the fix: 3 passed.

Red-first, Kotlin (box, mutants applied by hand on top of the B2 tree, then reverted with `git checkout`):

| Mutant | Red tests (65 run) |
| --- | --- |
| K15: `retryFail` calls `retries.arm(action)` after `pull` | 3: `AppModelRetryTest.aFolderLoadThatThrowsShowsTheCardAndADoubleTapRetriesOnce` ("a second Retry tap ran the folder load again expected:<2> but was:<3>"), `.aDownloadThatFailsShowsTheCardAndADoubleTapRetriesOnce` (2 vs 3), `.aDownloadWhoseGridCallThrowsDoesNotNameTheClassAndRetriesOnce` (2 vs 3) |
| K16: the `runGrid` onError `show(...)` line removed | 2: `AppModelRetryTest.aFolderLoadThatThrowsShowsTheCardAndADoubleTapRetriesOnce` ("a grid failure showed no fail card, so there is no Retry"), `.dismissThenRetryDoesNothing` |
| K9: `GridRun.cancel` does not call `setBusy(false)` | 1: `GridRunTest.cancelClearsBusyWhileTheJobIsStillRunning` ("cancel left the spinner on") |
| none (reverted) | 0 of 65 |

`GridRunTest.busyClearsAfterAnErrorAndTheErrorReachesTheHandler` locks behavior that was already correct; no mutant in this pass targets it.

Counts at `50e888f` (code identical to this commit; this commit only adds these lines):

- Box Gradle (JDK 17, SDK 34), `./gradlew --no-daemon :app:testDebugUnitTest :app:assembleDebug`: BUILD SUCCESSFUL, **65 tests, 0 failures, 0 errors, 0 skipped** (was 61: minus 2 deleted source-text tests, plus 4 `AppModelRetryTest`, plus 2 `GridRunTest`). Debug APK assembled.
- nimo `.venv/bin/python -m pytest tests/test_android_invite_copy.py android/pytests/test_dispatch_copy.py -q`: **18 passed** (15 + 3).
- nimo `scripts/ci-local.sh`: **619 passed, 5 xfailed, 0 failed**, ci-local PASS. `android/pytests` is outside its `testpaths`, so the 3 new tests are counted only in the line above.

## Tester fixes (third pass, 2026-11-02)

Tester FAIL on `2be4d7e`. Root causes: `docs/ops/ROOT-CAUSE-hardening-78-80.md` section "Tester pass on 2be4d7e". Commits `bb640f3`, `46c51ec`, `56c8fe9`, `cdeba16`, `65ce6e9`, `b962390` (rows in "Done").

Red-first:

- Python B3 (box pytest, `android/pytests/test_dispatch_copy.py`, before the `lg_tahoe.py` change): 1 failed, 3 passed. `test_fetch_share_keeps_the_server_error_off_the_next_line` saw the last error in parentheses on the next line. After: 4 passed.
- Python guard: `test_guard_sees_through_hidden_spellings` has 14 samples (escapes, zero-width, soft hyphen, Cyrillic, template, `.plus`, `append`, char run, and others). Each passed the old guard. After: 18 passed in `tests/test_android_invite_copy.py`.
- Kotlin S1 depth: `RecoveryCodecTest.deeplyNestedJson...` on the old codec threw `StackOverflowError`. The other new Kotlin tests went red through the mutants below.

Mutants, each applied by hand on the box on top of this branch, run, then reverted (`tmp/mut2.py`, not committed). The Tester mutant bodies were not in the repo, so these are this branch's rebuilt versions of each name. In this table only E5 survives, but that is not Tester's result: Tester's own 75-mutant run at `e6039095` killed 66, with 9 survivors (E5, N4b, H78e, F4b, F4e, F4f, A5, C3, C4), tracked in [#85](https://github.com/themark-net/leasegrid-c/issues/85). Rebuilt mutants:

| Mutant | What it changes | Result | Killed by |
| --- | --- | --- | --- |
| T1 old | import Cancel only goes to Welcome | killed | `AppModelFlowTest` cancel import |
| A5 | `cancelDownload` does not call `gridRun.cancel()` | killed | `AppModelFlowTest` cancelDownload |
| A6 | `cancelDownload` does not return to Folders | killed | `AppModelFlowTest` cancelDownload |
| R2 | `RetryOnce.pull` does not clear the slot | killed | 6 tests |
| R3 | `retryFail` re-arms after pull | killed | 4 tests |
| R4 | `dismissFail` does not disarm | killed | `dismissThenRetryDoesNothing` |
| F4e | `GridRun` onError call removed | killed | 4 tests |
| F4f | `runGrid` show removed | killed | 3 tests |
| F4b | finally does not clear busy | killed | 7 tests |
| F4c | finally clears busy without the ticket check | killed | `GridRunTest` stale ticket |
| K9 | `cancel` does not `setBusy(false)` | killed | 3 tests |
| N4b | learn delegation returns null | killed | 2 tests |
| N4d | learned servers not saved | killed | 2 tests |
| J1c | invite text getter returns "" | killed | 2 tests |
| M4c | show with an empty Retry | killed | 1 test |
| GCls | class name back in `unexpectedGridCard` | killed | 2 tests |
| H78b, H78d, H78e | Invite length, regex and trim changes | killed | 1 test each |
| F1e, F1i | `validateFurl` control-char and short-swiss checks | killed | 2 tests each |
| S2 old | marks stripped only at the ends | killed | 1 test |
| S3 old | recovery furl skips `validateFurl` | killed | 1 test |
| S4 old | empty tub id or missing location accepted | killed | 2 tests |
| S1 depth, scrypt, size, read | whole cap check removed (individual scrypt bounds untested, follow-up) | killed | 1, 1, 1, 2 tests |
| C3, C3b, C4 | shares size check, shares order check, folders check removed | killed | 1 test each |
| A8 | "friendnet" in an `AppModel.kt` banner | killed by the new guard (1 failed, 17 passed); survived the old guard (15 passed) | `test_appmodel_and_mainactivity_pass_banned_word_guard` |
| A9 | em dash in an `AppModel.kt` banner | killed by the new guard (1 failed, 17 passed); survived the old guard | same |
| E5 | "Intro" and "ducer" in two variables | not killed | follow-up above; needs data flow |

Counts at `b962390`:

- Box Gradle (JDK 17, SDK 34), `:app:testDebugUnitTest :app:assembleDebug`: BUILD SUCCESSFUL, **86 tests, 0 failures, 0 errors, 0 skipped** (InviteCopyTest 21, SessionFlowTest 13, RecoveryCodecTest 11, InviteTest 10, AppModelFlowTest 9, FolderWriteTest 7, AppModelRetryTest 4, GridRunTest 4, BoundedReadTest 3, RetryOnceTest 2, SessionStoreTest 2). Debug APK assembled.
- nimo `.venv/bin/python -m pytest tests/test_android_invite_copy.py android/pytests -q`: **30 passed, 2 skipped** (the 2 skips are the live-grid tests).
- nimo `scripts/ci-local.sh`: **622 passed, 5 xfailed, 0 failed**, 139.90s, ci-local PASS (was 619; plus the 3 new guard tests). `android/pytests` is outside its `testpaths`.

## Gate

Tester and Reviewer. Runtime changes are in `Invite.kt`, `AppModel.kt`, `GridRun.kt`, `RetryOnce.kt`, `RecoveryCodec.kt`, `SyncApp.kt`, and `FolderWrite.kt`. Kotlin unit tests ran on the box (86/0 failures after the Tester pass, red-first tables above). `MainActivity.kt`, `BoundedRead.kt`, `lg_tahoe.py` and `leasegrid_read.py` also changed. Python ci-local passed, counts above.

## Next

Tester and Reviewer on `build/hardening-78-80`. Implementation by Grok Build headless on nimo (Hermes `-z` produced no response three times; see decisions). Do not merge until Tester and Reviewer pass.
