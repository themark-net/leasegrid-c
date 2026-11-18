# Handoff: #89 follow-ups (private paths, camera permission line)

Branch `bot/89-scrub-perm` off `main` `6295015` (v0.1.12). Issue: [#89](https://github.com/themark-net/leasegrid-c/issues/89). No release, no tag. CHANGELOG lines are under Unreleased.

## (a) Private home paths

1. The four files Tester named had the real account home path: `GATE0B_REPORT.md` (3 lines), `U1_REPORT.md` (2), `U2_REPORT.md` (1), `deploy/zkap-lab/README.md` (3). They now say `~/` (for example `~/tahoe-venv/bin/leasegrid-zkap`, `~/.tahoe`). The meaning is the same: the same paths, relative to the user's home.
2. A repo grep found the same path in 22 more docs (`docs/build-dropins/*`, `docs/ops/RUN-LOG-*`, `docs/ops/HANDOFF-ff-0111-2026-10-14.md`, `docs/design/README.md` and others). Same change. One touched line also lost an em dash.
3. Code: `scripts/ci-local.sh` and `scripts/leasegrid-sync-nimo.sh` now use `"$HOME/tahoe-venv/..."`. On nimo that is the same path. `tests/test_ci_local_worktree.py` uses `os.path.expanduser("~/tahoe-venv/bin/python")` to match.
4. Left as they are: generic examples (`/home/u`, `/home/x`, `/home/you`, `/home/runner`, `C:/Users/u`) in tests and wireframes, and `$T/home/...` temp dirs in `packaging/exit-test.sh`.
5. Guard: `tests/test_no_private_home_paths.py` reads `git ls-files` and fails on `/home/<name>` or `/Users/<name>` at the start of a path in tracked text files, unless the name is a generic placeholder. Red first: before the scrub it failed with 79 hits in 29 files; after the scrub it passes. A second test pins the matcher (a real name is flagged; placeholders, `~/`, `$HOME`, `$T/home` are not).
6. Not touched: `docs/ops/HANDOFF-0112-release-prep.md` and `docs/ops/ROOT-CAUSE-0112-gate.md` stay where they are. The docs policy is with CEO under [#87](https://github.com/themark-net/leasegrid-c/issues/87).

## (b) MainActivity camera permission line

The instrumented-free option was cheap, so Robolectric was not tried.

1. New `android/app/src/main/java/net/themark/leasegrid/sync/ui/CameraGate.kt`: `PERMISSION` (`Manifest.permission.CAMERA`), `isGranted(checkResult)` (only `PERMISSION_GRANTED` is a yes) and `scanRefused(missingPermissionExtra)` (null or false is not a refusal).
2. `MainActivity.kt` now only passes Android values in: `CameraGate.isGranted(ContextCompat.checkSelfPermission(this, CameraGate.PERMISSION))`, `askCamera.launch(CameraGate.PERMISSION)` and `CameraGate.scanRefused(result.originalIntent?.hasExtra(...))`. The decisions after that were already in `AppModel.onScanTapped`, `onCameraAnswer` and `onScanResult` with JVM tests.
3. `CameraGateTest.kt` (JVM): the permission name, granted and denied results, the three refusal-flag cases, and a source pin that the Activity calls the gate and no longer names `PERMISSION_GRANTED` or `Manifest.permission.CAMERA` itself.
4. `SyncAppWiringTest.kt` and `tests/test_android_invite_copy.py` pin `CameraGate.PERMISSION` in the Scan QR opener instead of the inline `Manifest.permission.CAMERA`.

## Checks

Local (nimo): full pytest and ruff green. Android unit tests run only in CI (no Java on nimo). CI ids are in the #89 comment.
