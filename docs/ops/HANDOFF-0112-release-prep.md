# Handoff: v0.1.12 release prep (after the 530dd52 gate FAIL)

Branch `bot/0112-release-prep` off `main` `530dd52`. Tester and Reviewer FAIL on [#88](https://github.com/themark-net/leasegrid-c/issues/88). Root cause: `docs/ops/ROOT-CAUSE-0112-gate.md`.

## What changed

1. **Release prep before the gate:** version 0.1.12 in `pyproject.toml` and `src/leasegrid_sync/__init__.py`; `docs/release-notes/v0.1.12.md` (says there is no Android APK, Android is in source only); CHANGELOG `0.1.12` with #87, #77 and #88 (the Unreleased lines moved in); README, TESTERS and TESTER-GUIDE point at v0.1.12 like the v0.1.11 prep did. No tag, no release.
2. **#87 retry and order tests:** `tests/test_sync_lock_retry_order.py` (10 tests). Mutant table below.
3. **B2:** `_lock_path_problem` leaves any stat error to tryLock. `_lock_read_state` returns readable, missing or denied; a lock that goes missing during the reads gets one more tryLock instead of "already running".
4. **MainActivity deny wiring:** routing moved to `AppModel.onScanResult`, tested by `AppModelFlowTest.aScannerResultRoutesARefusalACancelAndAScan`. The permission check line stays in the Activity (emulator check). A Robolectric Activity test was not cheap (see root cause, section 4).
5. **PENDING-HANDOFF:** the private checkout and virtualenv paths on lines 7 and 353 are gone.
6. **Reviewer F items:** F2 zxing core pinned at 3.4.1 in `android/app/build.gradle.kts`; F3 `android/THIRD_PARTY_NOTICES.md`; F4 `AppModelFlowTest.aScanOfExactlyTheCapIsAcceptedAndOneMoreIsRefused` (4096 accepted, 4097 refused); F8 the `_raise_permission_on_lock_read` docstring no longer says `_lock_path_problem` opens the file. F1 is the CHANGELOG entry. F5 and F6 are the device check (And). F7 is the docs policy (CEO).
7. `docs/ops/HANDOFF-87-test-hardening.md` line 8 now states the real order.

## Mutant table

Each mutant was applied by hand to `src/leasegrid_sync/app.py`, `tests/test_sync_lock_retry_order.py` was run, and the file was restored.

| # | Mutant | Red tests |
|---|--------|-----------|
| M1 | tries 3 to 1 | denial clears on third read; 80 ms delete; stays denied after three reads; rival just deleted; vanishes during reads (5 failed) |
| M2 | sleep 50 ms to 0 | 80 ms delete; stays denied after three reads (2 failed) |
| M3 | probe moved before tryLock | read runs only after tryLock failed; stale lock taken with reads always denied; stale lock taken with stat and reads denied; and 4 more (7 failed) |
| M4 | PID guard dropped | rival wrote its PID by the second tryLock (1 failed) |
| M5 | missing treated as unreadable | rival just deleted; missing lock; vanishes during reads (3 failed) |
| M6 | unreadable ignores the PID (probe verdict before the PID check) | rival wrote its PID by the second tryLock (1 failed) |
| M7 | B2: stat error before tryLock mapped to unreadable | stale lock taken with stat and reads denied (1 failed) |
| M8 | B2: no retry when the lock vanished during the reads | vanishes during reads is taken, not already running (1 failed) |

With no mutant, all 10 pass.

## How to verify

CI at the final SHA on ubuntu, windows-2022, macos-15-intel, semgrep and Android Slice A, then the Installers workflow at that SHA builds `Leasegrid_Sync-0.1.12-*`. Then Tester and Reviewer gate that SHA. And rechecks the refused camera path on the emulator.

## Remaining

- Gate at the final SHA, then tag `v0.1.12` and let Installers publish (no APK asset, keep prior releases, no marketing).
- Emulator recheck of the camera refusal (And).
