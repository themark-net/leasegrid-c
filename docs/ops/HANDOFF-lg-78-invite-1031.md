# Handoff lg-78-invite-1031

Branch: `bot/lg-78-invite-1031`
Base: `origin/main` @ `7ce0785691b925c4b2f0ef06f7cd3c7d2796386a`
Worktree: `~/DEVELOP/leasegrid-c/tmp/lg-78-invite-1031`
Exit: lane empty. Not a release. No PR. No merge. No issue comment.

## Done

| Item | SHA | What the user sees |
|---|---|---|
| #78 long paste | `97ee7e6` | A ~100 KB near-miss returns "That isn't a join link." It does not throw. |
| #78 cancel ghost | `4782d8a` (record only) | Already on origin/main. A cancelled join does not paint "Couldn't reach your computer." |
| #80 F1 dirty link | `be0a398` | A NUL, a replacement character, a space from `+`, a newline, or a swissnum under 8 characters returns "That join link is incomplete." |
| #80 F2 paste marks | `a9b1b38` | A leading or trailing U+200B or U+FEFF still joins. A paste of only those marks says "Paste the join link first." |

Run-log rows: `4782d8a`, `ca0ed9d`, `716ae58`, plus this handoff commit. Decisions: `docs/ops/AUTONOMOUS-DECISIONS-lg-78-invite-1031.md`.

## How it fails and how it recovers

- Long paste. Before: `InviteCopyTest.aHundredKilobytePasteDoesNotOverflowAndStaysAPlainError` threw `StackOverflowError` in `Pattern.java`. After: the same paste returns `GARBAGE_MSG` with no Next line. A real short code still returns `WORMHOLE_MSG`. A ~100 KB well-formed join link still parses shares `[2, 3, 3]`.
- Ghost banner. Not re-edited. `AppModel.learn` rethrows `CancellationException`. Keyboard Done uses the same busy check as the Join button. `SessionFlowTest.aCancelledJoinPaintsNothing` and `tests/test_android_invite_copy.py` `test_learn_rethrows_cancellation_and_done_matches_join_button` pass on this tree.
- Dirty link. Before: `dirtyFurlsAreIncompleteAndACleanLinkStillJoins` threw `IllegalStateException` because parse accepted the link, and `retryAfterAMalformedPasteJoinsTheCorrectedLink` had a null banner. After: each dirty case is `MALFORMED_MSG`, learn is not called, and Retry after the field is replaced with the good link calls learn and clears the banner. Gradle: InviteCopyTest 15 tests, SessionFlowTest 10 tests, 0 failures (`be0a398`).
- Paste marks. Before: code point 8203 (U+200B) in front of a good link raised "That isn't a join link." and learn was not called. After: the marked link joins, including a mark percent-encoded onto either end of the address. A marks-only paste is `EMPTY_MSG` and does not call learn. Retry with the real link calls learn. Direct JUnit after the fix: 27 tests, 0 failures, 0.056s.

`stripPaste` replaces `trim()` in `parse` and in `validateFurl`. It strips both ends. A mark in the middle stays. Swissnum minimum is 8 so the `swissnumswiss` fixture (length 13) still joins.

## Tests

- Gradle, #78 green: `:app:testDebugUnitTest --tests InviteCopyTest`, 14 tests, 0 failures, the 100 KB case in 0.004s (`97ee7e6`).
- Gradle, #80 F1 green: `:app:testDebugUnitTest --tests InviteCopyTest --tests SessionFlowTest`. InviteCopyTest 15, SessionFlowTest 10, 0 failures (`be0a398`).
- #80 F2 red and green were direct JUnit (kotlinc 1.9.24 plus junit 4.13.2, niced, not Gradle). Red: 27 tests, 2 failures (the two new ones). Green: 27 tests, 0 failures.
- `python3` called the 12 functions in `tests/test_android_invite_copy.py` after F2. 0 failures. pytest is not installed here. `prove-red.py` is pytest-only, so the Kotlin red receipt is the test failure, not that script.
- Gradle suite not run: heavy lock deadlocked by a foreign sleep loop since 05:48Z. This lane queued `:app:testDebugUnitTest` from 06:00Z to 08:47Z. The log stayed empty. This lane stopped its own waiters at 08:47Z and did not signal the holder. When that loop's `pgrep -f Runner.Worker` goes quiet it runs a pregate before it drops the lock, so a later waiter still waits through that pregate.
- pregate not run: heavy lock held by that foreign sleep loop. `Runner.Worker` was not running at 08:47Z.

## Skipped

- #80 F4, retryFail double tap, FlowHost delegation tests, bad recovery file, legacy "friendnet" copy, the SyncApp banned-word extension, the dash guard in `tests/test_android_invite_copy.py`, and the design 61 wording. Lane `lg-80-appmodel-1031` owns `AppModel.kt`, `SyncApp.kt`, `FolderWrite.kt`, and that design note. This lane did not edit those files.
- The recovery-import cancel sentence from the #80 comment. It is not Invite.kt paste parsing.
- No further Invite.kt item. The listed paste bugs are pushed. No local model.

## Cross-lane

- lg-80 must not edit `Invite.kt`. This lane did not edit `AppModel.kt` or `SyncApp.kt`.
- The heavy lock holder is another lane's `while pgrep -f Runner.Worker; do sleep 60; done` inside `flock`. That pattern matches a second flock command waiting on the same lock (its command line contains the text `Runner.Worker`). Neither side finishes. Do not signal them from this lane.

## Gate

Tester plus Reviewer. Runtime change in `Invite.kt`. Tip to review is this handoff commit on `bot/lg-78-invite-1031`. Product commits are `97ee7e6`, `be0a398`, and `a9b1b38`.

## Next

Tester and Reviewer on this branch. Re-run `./gradlew :app:testDebugUnitTest` under the heavy lock once that lock is free. Do not merge from this lane.
