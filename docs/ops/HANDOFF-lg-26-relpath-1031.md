# Handoff: lg-26-relpath-1031

Branch `bot/lg-26-relpath-1031`. Implementation `e6238ca`. This handoff is the commit after that. Compare: https://github.com/themark-net/leasegrid-c/compare/main...bot/lg-26-relpath-1031

Exit: lane empty at 2026-11-01T06:09:42Z. Wall cap was 2026-11-01T10:45:55Z. Host at exit: MemAvailable about 62 GiB, load about 2.7 on 32 cores. `pgrep -x Runner.Worker` was 0.

## Done

| Item | SHA | Tests | Result |
| --- | --- | --- | --- |
| #26 relative EXTRA_RECOVERY_FILE | `e6238ca` | `nice -n 19 ./gradlew --no-daemon :app:testDebugUnitTest --tests net.themark.leasegrid.sync.RecoveryExtraTest --tests net.themark.leasegrid.sync.InviteTest --tests net.themark.leasegrid.sync.RecoveryCodecTest` | pass. 5 + 10 + 4 tests, 0 failures, BUILD SUCCESSFUL in 6s |

Files: `DogfoodIntents.kt`, `MainActivity.kt`, `RecoveryExtraTest.kt`, `docs/ops/p4-android-dogfood.md`, `docs/ops/AUTONOMOUS-DECISIONS-lg-26-relpath-1031.md`.

Decision: a relative extra whose canonical path stays inside the app files dir loads, same as an absolute path. A relative path that leaves that dir (`../` or a symlink) is refused up front with a plain sentence. Rejecting every relative path would leave import confirm disabled (`conf_enabled=None`).

## How it fails and how it recovers

- Fail: a relative name is not joined onto the app files dir. The first frame has no bytes, so import confirm stays unset (`conf_enabled=None`). Recover: `loadRecoveryExtra` resolves the name inside the app files dir and returns the same bytes as the absolute path, before `setContent`.
- Fail: `../` or a symlink leaves the app files dir and the outside bytes come back. Recover: the load is rejected, bytes stay null, the banner is a plain sentence with no exception text, and Retry opens the recovery picker instead of reading that path again.
- Fail: a missing file inside the app files dir used to post the retry on `window.decorView` before `setContent`. Recover: the miss still opens Import, retries on `Handler(Looper.getMainLooper())` up to 5 times, then the plain miss sentence.
- An absolute path outside the app files dir still loads. That is the documented absolute-path pass.
- A recovery URI that cannot be read used to append the exception class name. It now uses the same plain miss sentence.

## RED receipt

`scripts/prove-red.py` only runs pytest, so this receipt is two one-line mutants of `locateRecovery`, each a second Gradle run, then the original bytes restored. Source sha256 after restore: `5a723a47b553356c59da0f20cc22ed4eeb4f949d43b2b3552068c633277d4513`.

| Mutant | Test | Result |
| --- | --- | --- |
| Relative path returns `File(trimmed)` and ignores the app files dir | `relativeNameInTheAppFilesDirLoadsTheSameBytesAsTheAbsolutePath` | FAILED, AssertionError at RecoveryExtraTest.kt:31 |
| Canonical file is returned with no inside-base check | `relativePathThatLeavesTheAppFilesDirDoesNotReturnThoseBytes` | FAILED, AssertionError at RecoveryExtraTest.kt:98 |
| Original function restored | RecoveryExtraTest and InviteTest | BUILD SUCCESSFUL in 6s |

Not CI green. `gh` is not logged in, and this lane opened no pull request.

## Skipped

- `tests/test_android_slice_a.py` and any other pytest: `pgrep -f 'Runner[.]Worker'` matches another lane's flock command line (pid 3024123). No real `Runner.Worker` (`pgrep -x` count 0). The slice A strings were read, not executed: `MainActivity.kt` still has `postDelayed`, `beginRecoveryImport`, `deliveryKey`, and `EXTRA_INVITE`, and it does not set `acknowledged = true`.
- Gradle under `flock`: the heavy lock is held by pid 2605611, which sleeps while `pgrep -f Runner.Worker` matches pid 3024123. Those pids are not this lane's and were not signaled. One niced targeted Gradle ran without the lock. See the decisions file.
- `readAddedFile` still appends the exception class name. That is the add-file picker, not `EXTRA_RECOVERY_FILE`.
- `Invite.kt` (lane lg-78-invite-1031), `AppModel.kt` busy/retry, and `SyncApp.kt` copy (lane lg-80-appmodel-1031) were not edited.
- `docs/PENDING-HANDOFF.md` still says #26 is untouched as of 2026-10-09. Left it so a shared status file is not raced.
- No phone, no emulator, no Robolectric. The intent-extra boundary is the JVM loader. No browser surface.
- No issue comment, no release, no tag, no merge. `scripts/pregate.sh` was not run.

## Cross-lane requests

None. `origin/bot/lg-78-invite-1031`, `origin/bot/lg-80-appmodel-1031`, `origin/bot/lg-77-design-1031`, and `origin/bot/lg-018-fixes-1031` do not touch `DogfoodIntents.kt`, `MainActivity.kt`, `RecoveryExtraTest.kt`, or `docs/ops/p4-android-dogfood.md`.

## Gate

Tester plus Reviewer. This is a runtime change. The operator runs pregate. This lane does not.

## Next step

Review `e6238ca` on `bot/lg-26-relpath-1031`. Dogfood: seed a file in the app files dir and pass that file name as `EXTRA_RECOVERY_FILE`. Import confirm should enable on the first frame. Pass `../` and confirm the plain sentence, with confirm left off. Do not merge from this lane.
