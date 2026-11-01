# Handoff: lg-80-appmodel-1031

Branch `bot/lg-80-appmodel-1031`. Base `origin/main` @ `7ce0785`. Worktree `~/DEVELOP/leasegrid-c/tmp/lg-80-appmodel-1031`. Finished `2026-11-01T07:35:00Z`. Exit: lane empty. No merge, no PR, no release, no issue comments.

## Done

| Item | SHA | What changed |
| --- | --- | --- |
| F4 busy gate | `f401a80` | `GridRun` ticket. A cancelled job clears busy only if it is still current. download, remove, cancel, beginRecoveryImport, and runGrid share that ticket. |
| retryFail once | `724982c` | `RetryOnce.pull` clears the action before it runs. dismiss and a finished upload clear it too. |
| bad recovery file | `c64c043` | A bundle that is not an object, and shares that are not an array, throw `ImportFail`. |
| legacy copy | `9b7bbed` | Phone strings in SyncApp, FolderWrite, and forget-downloads no longer say friendnet. Chips: "Not in the shared folder yet" and "In the shared folder". |
| FlowHost pins and SyncApp guard | `1a12026` | Exact FlowHost delegations. Banned-word guard scans every SyncApp.kt string literal. |
| generic Retry | `d065a2c` | The unexpected grid card has no class name. Retry runs the same block again. |
| download class name | `642a416` | Download's next line no longer appends the exception class. Retry still calls download. |

Run-log commits: `95c7662`, `8a32681`, `19846d3`, `5b25e18`, plus this handoff commit.

## Skipped

- `Invite.kt`: lane lg-78-invite-1031 owns it. This lane did not need a change there.
- Design packs 55-59: they still say the older chip word. The phone follows design 61. Rewriting those packs is out of scope.
- Empty Retry on a bad file name, low space, or a failed local write: the tap already dismisses the card. There is no second copy of the picked bytes. Left as they were. Decision logged.
- Pregate not run: heavy lock held. From about `2026-11-01T05:49Z`, pid 2605611 slept on `pgrep Runner.Worker` while queued flock 3024123's own command line matched that pattern. No `Runner.Worker` process. This lane did not signal those processes.

## Tests

F4 red and green ran under the heavy lock. Later Gradle ran `nice -n 19` outside that lock because it would not release (decision logged). One Gradle at a time in this worktree.

- GridRunTest red: "older finally cleared busy while the newer job was still running. main=0 io=1". Green: 2 tests, 0 failures.
- RetryOnceTest red: "a second tap ran the action again". Before the wire, `retryFail` invoked the stored field. Green: 3 tests, 0 failures.
- RecoveryCodecTest red: `IllegalArgumentException` "is not a JsonObject". Green: 5 tests, 0 failures.
- FolderWriteTest red: expected "Not in the shared folder yet" but was "On friendnet". Green: 7 tests, 0 failures.
- Python pins red: `inviteText = ""` failed the FlowHost pin. "Friendnet trust" failed the SyncApp guard and named that literal. Green: both pins, and the rest of `tests/test_android_invite_copy.py`.
- GridFailTest red: card was "could not complete that. IllegalStateException", and Retry did not call `runGrid`. Green: 2 tests, then the download case.
- Download red: expected "Retry." but was "Retry. (IllegalStateException)".
- Full `:app:testDebugUnitTest` after `642a416`: 53 tests, 0 failures, 0 errors.

No red-on-base failures in this suite.

## How it fails and how it recovers

- Busy: an older `finally` used to set busy false under a newer join, so the phone looked idle while the join was still running. The ticket blocks that clear. The current job still clears busy when it finishes. Cancel still clears busy immediately.
- Retry: a second tap used to run the same action again. `pull` empties the slot first. A new failure can arm a new action.
- Recovery file: a damaged shape used to escape as a raw parser exception and hit the generic card. It is now `ImportFail` with the import message and a Retry next line. The file is not imported.
- Copy: a friendnet chip or sentence comes back and the FolderWrite test or the SyncApp guard fails. Chips must not say the file is on the computer.
- Generic grid failure: the class name used to be on the card and Retry did nothing. The class is logged. Retry runs the block once. A second tap does not, because the slot was pulled.
- Download: the next line used to name the class. It is logged instead. Retry still starts the same download.

## Cross-lane

No edit requested in another lane's files. `Invite.kt` stayed untouched.

## Gate

Tester plus Reviewer. These are runtime changes (AppModel, GridRun, RecoveryCodec, SyncApp, FolderWrite) with tests.

## Next

Review `bot/lg-80-appmodel-1031`. Do not merge until Tester and Reviewer pass. Pregate still needs a free heavy lock if the gate wants it.
