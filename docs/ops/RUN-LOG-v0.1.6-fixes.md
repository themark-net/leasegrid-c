# Run log — v0.1.6 fix round (Tester FAIL @ bd7b09e)

Worktree: `/home/mark/DEVELOP/leasegrid-c/tmp/v016-fixes`
Branch: `build/v0.1.6-batch` (PR #73). Start HEAD `3caa6bf` (drop-in on `bd7b09e`).
Base: `86a28c8` (v0.1.5). Interpreter: this tree's `.venv` (Python 3.14; PyQt5 abi3 wheel installs).

## Plan

Overview: Fix the two Tester blockers (lock wedge, off-screen restore) and the listed follow-ups, one commit per item, on this branch only. The lead implements in order because the items share `app.py` and this drop-in forbids any other worktree.

Phases:

- baseline | docs/ops/RUN-LOG-v0.1.6-fixes.md | ci-local recorded | none | lead
- 1 B1 lock | app.py, tests/test_sync_instance_lock.py | empty/garbage/foreign locks recover; live holder refused; real two-process app test; RED proofs | baseline | lead
- 2 B2 geometry | app.py, tests/test_sync_window_geometry.py | y=-650 and left-of-screen title bar stays on screen; on-screen round-trip; RED proof | 1 | lead
- 3 quit stops daemons | app.py (read), tests/test_sync_stop_reap.py | quit() leaves stub Tahoe and Magic Folder children gone; mutant 2e RED | 2 | lead
- 4 rotation shrink | tests/test_sync_ui_log.py | live file smaller than the limit, old bytes in .1 once; copy-instead-of-move RED | 3 | lead
- 5 tray quit prompt | app.py, tests/test_sync_close_invite.py | tray Quit with a live invite + Keep open stays up; no invite quits | 4 | lead
- 6 open folder is_dir | app.py, tests/test_sync_open_folder.py | a regular file never reaches openUrl | 5 | lead
- 7 geometry file | app.py, tests/test_sync_window_geometry.py | 100k-deep JSON falls back; failed replace leaves the good file | 6 | lead
- 8 bug-report scrub | app.py, tests/test_sync_settings_actions.py | planted pb://, wormhole codes, and join links do not survive; log and env plants absent | 7 | lead
- 9 docs | HANDOFF, AUTONOMOUS-DECISIONS, tester pages if behavior changed | stale 468 and the What's-new decision line corrected | 8 | lead
- handoff | docs/HANDOFF-v0.1.6.md, this log | final ci-local counts, table, v0.1.7 list, push | 9 | lead

Risks:

- Shared `app.py` — one item at a time, no parallel editors.
- Mutation proofs must be restored before commit.
- A 35 s live-lock wait is too slow — refuse as soon as the holder is alive and the file is younger than Qt's default stale time.
- Python 3.14 venv — PyQt5 has an abi3 wheel; if sync extra fails, log it and do not retarget another venv.
- Windows CI — no bash-WSL assumption; skip a case only with a reason.

## Baseline

state: DONE | tests: PYTHON=$PWD/.venv/bin/python bash scripts/ci-local.sh → 469 passed, 5 xfailed, 4 warnings in 43.12s, ci-local PASS | files: run log + one decision line | err: none

Failing tests: none. Qt stale time probed at 30000 ms. An empty, garbage, or other-host lock older than that is taken; the same files with stale time 0 are not. A live same-host holder is refused even after the file mtime is moved 120 s into the past. unlock() removes the lock file.

## Items

1. B1 lock | DONE | ci-local: 473 passed, 5 xfailed, 4 warnings in 43.16s | files: app.py, tests/test_sync_instance_lock.py, AUTONOMOUS-DECISIONS, this log | err: none
   Tests: test_empty_lock_older_than_stale_time_is_recovered, test_garbage_lock_older_than_stale_time_is_recovered, test_foreign_host_lock_older_than_stale_time_is_recovered, test_live_app_refuses_a_second_launch_and_releases_on_quit
   RED without fix: test_live_app_refuses_a_second_launch_and_releases_on_quit at tests/test_sync_instance_lock.py:330 (deleted `_INSTANCE_LOCK = lock`; the lock file was already gone while the first window was up)
   RED without fix: test_empty_lock_older_than_stale_time_is_recovered, test_garbage_lock_older_than_stale_time_is_recovered, test_foreign_host_lock_older_than_stale_time_is_recovered at tests/test_sync_instance_lock.py:209 (`setStaleLockTime(0)` put back)

2. B2 geometry | DONE | ci-local: 475 passed, 5 xfailed, 4 warnings in 42.54s | files: app.py, tests/test_sync_window_geometry.py, AUTONOMOUS-DECISIONS, this log | err: none
   Tests: test_title_bar_above_the_screen_stays_on_screen, test_title_bar_left_of_the_screen_stays_on_screen, test_geometry_round_trips_across_two_windows
   RED without fix: test_title_bar_above_the_screen_stays_on_screen at tests/test_sync_window_geometry.py:104 and test_title_bar_left_of_the_screen_stays_on_screen at tests/test_sync_window_geometry.py:117 (unconditional move() put back)
