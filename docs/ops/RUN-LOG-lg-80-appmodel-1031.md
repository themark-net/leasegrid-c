# Run log: lg-80-appmodel-1031

Slug: lg-80-appmodel-1031. Worktree: `/home/mark/DEVELOP/leasegrid-c/tmp/lg-80-appmodel-1031`. Branch: `bot/lg-80-appmodel-1031`. Base: `origin/main` @ `7ce0785`. Started `2026-11-01T01:55:50Z`. Drop-in commit `bee26e0`. Lead implements items in this worktree. No parallel implementers: the items share AppModel.kt, SyncApp.kt, and FolderWrite.kt.

## LOOP EXIT CARD

Goal (success criteria): issue #80 behaviors below are fixed or recorded skipped, each code change has a behavior or fail/recover test that went red first, Android unit tests were run niced under the heavy lock, and the handoff is pushed.
1 Goal met: named items done, no further gap that fits this lane, handoff written. Evaluator: Gradle unit tests plus the new assertions, not a vibe check.
2 Turn cap: 12 items. After the named scope, at most a few lane-local gaps, then treat the lane as empty. Do not invent architecture.
3 Budget cap: cloud Grok only. No local model. No paid deploy.
4 Wall clock: 8 hours from launch (`2026-11-01T09:55:50Z`) or Sunday 2026-11-01 18:00 PT (`2026-11-02T02:00:00Z`), whichever comes first. Stop starting items at `2026-11-01T09:35:50Z` so the handoff has 20 minutes.
5 No-progress: the same failure twice with no new information, or 3 items in a row skipped.
6 Human interrupt: user stop. No questions while the run is open. Conservative choice, one line in the decisions file.
7 Error threshold: 3 consecutive failed attempts on one item, then skip that item and continue. Two identical failures with no new information stop the run (exit 5).
8 External event: stop an item if `origin/main` already has it, or if the only fix is in `Invite.kt` (lane lg-78-invite-1031).
Loop type: goal
Human gate: no merge, no PR, no release. Push this branch only.

Host pressure exit: MemAvailable under 16 GiB, or load over 2x cores (64) for 5 minutes. Pause 10 minutes, then stop if it persists.
Red base exit: tests that fail on the base before the change are recorded and that area is skipped. The run does not stop.

Overview: Close the Android busy/retry race, pin the AppModel FlowHost one-line delegations, fail closed on a bad recovery file, and replace leftover "friendnet" phone copy so the banned-word guard can cover all of SyncApp.kt. Retry on the generic grid failure must rerun the job and must not show an exception class name.

Phases:
- F4 busy gate | ui/GridRun.kt, ui/AppModel.kt, ui/GridRunTest.kt | a cancelled job's finish does not clear busy while a newer job is running; the current job does clear it | none | general
- retryFail once | ui/GridRun.kt, ui/AppModel.kt, ui/GridRunTest.kt | a second Retry tap does not run the action again | F4 | general
- FlowHost pins | tests/test_android_invite_copy.py | each AppModel FlowHost one-liner is pinned so a swapped delegation fails | none | general
- bad recovery file | recovery/RecoveryCodec.kt, RecoveryCodecTest.kt | a damaged recovery file throws ImportFail, not a raw exception | none | general
- legacy copy | SyncApp.kt, FolderWrite.kt, AppModel.kt, FolderWriteTest.kt, design/61 | user-visible phone strings no longer say friendnet; chips still do not say "on your computer" | none | general
- generic Retry | ui/GridRun.kt or AppModel.kt, GridRunTest.kt | unexpected failure card has no class name and Retry runs the block again | F4 | general
- banned-word guard | tests/test_android_invite_copy.py, design/61 | the guard scans every SyncApp.kt string literal | legacy copy | general
- handoff | docs/ops/HANDOFF and this log | state line, SHAs, skips, fail/recover, gate | all | general

Risks:
- AppModel needs an Application, so the busy race is tested on GridRun, which AppModel calls. Mitigation: AppModel's runGrid, download, and remove paths go through that one launch.
- Design packs 55-59 still say "On friendnet". Mitigation: phone copy follows design 61's ban; the chip meaning stays "in the shared folder", never "on your computer". Decision logged.
- Gradle needs an Android SDK. Mitigation: install platforms;android-34 under this worktree's tmp/ only. Do not write into another project's SDK.
- Other lanes share the host. Mitigation: stay in this worktree; Gradle under the heavy flock; do not edit Invite.kt.

Check before every item: wall clock, MemAvailable, load.

## Items

F4 busy gate | f401a80 | :app:testDebugUnitTest --tests GridRunTest | red: older finally cleared busy while the newer job was still running (main=0 io=1); green: 2 tests, 0 failures
retryFail once | 724982c | :app:testDebugUnitTest --tests RetryOnceTest | red: a second tap ran the action again (pull did not clear); before the wire, retryFail invoked the stored field; green: 3 tests, 0 failures. Targeted Gradle outside the deadlocked heavy lock, decision logged.
bad recovery file | c64c043 | :app:testDebugUnitTest --tests RecoveryCodecTest | red: badRecoveryFileFailsClosed threw IllegalArgumentException "is not a JsonObject"; green: 5 tests, 0 failures
legacy copy | 9b7bbed | FolderWriteTest | red: chip was "On friendnet", expected "Not in the shared folder yet"; green: 7 tests, 0 failures
FlowHost pins | 1a12026 | tests/test_android_invite_copy.py test_appmodel_flowhost_delegates_exactly | red: inviteText = "" failed the pin; green: pass
banned-word guard | 1a12026 | tests/test_android_invite_copy.py test_syncapp_passes_banned_word_guard | red: Friendnet trust literal listed; green: pass
generic Retry | d065a2c | :app:testDebugUnitTest --tests GridFailTest | red: card was "could not complete that. IllegalStateException" and Retry did not call runGrid; green: 2 tests, 0 failures
download class name | 642a416 | GridFailTest.downloadFailureDoesNotNameTheExceptionClass and full :app:testDebugUnitTest | red: expected "Retry." but was "Retry. (IllegalStateException)"; green: 53 tests, 0 failures

state: lane empty | named items and the download class-name gap are pushed. Full Android unit tests 53 passed, 0 failed. Pregate not run: heavy lock held by another lane's sleep. No further gap in AppModel, SyncApp, or FolderWrite that fits without a new product choice.
