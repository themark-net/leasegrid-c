# Run log — Leasegrid Sync v0.1.7 batch

Worktree: `/home/mark/DEVELOP/leasegrid-c/tmp/v017-batch`
Branch: `build/v0.1.7-batch` (no upstream)
Base: `b4e9b70485ff20bdd9089e558cb0ff71702d280b` (`origin/main`, tag v0.1.6)
Drop-in: `f96dcd51c534222a40938ace45ac232ec2faac4b`
Started: 2026-10-17
Interpreter: `.venv/bin/python` (3.14.4)

Remote check: `origin/main` is still `b4e9b70`. No other remote branch holds this batch. Ahead 1 (the drop-in commit), behind 0.

## Plan

Overview: Twelve ordered Sync fixes and docs on one branch. Each item gets a failure-mode test, a red-without-fix proof, a full ci-local, one commit, and a push. Then a 0.1.7 bump, release notes, and handoff. No PR.

Phases:

- baseline | docs/ops/RUN-LOG-v0.1.7-batch.md, docs/ops/AUTONOMOUS-DECISIONS-v0.1.7.md | ci-local recorded | none | lead
- item 1 signals | src/leasegrid_sync/app.py, tests | SIGTERM/SIGINT/SIGHUP quit, stub reaped, lock gone | baseline | lead
- item 2 process group | src/leasegrid_sync/backend.py, tests | grandchild gone after stop | item 1 if stop path shared | lead
- item 3 daemon log rotate | backend.py, app.py rotate helper, TESTER-GUIDE | rotate before start; failure still starts | baseline | lead
- item 4 join handoff | app.py QLocalServer, cli | second --join fills the field, exits 0, no auto-join | item 1 lock path | lead
- item 5 empty lock | app.py lock | empty/garbage lock relaunches; live PID refused | item 4 | lead
- item 6 mask username | app.py helper, settings, bug report, banners | ~ form shown; disk paths unchanged | baseline | lead
- item 7 geometry | app.py geometry, tests | version pin, un-maximize size, no drift, assertion mutants | baseline | lead
- item 8 scrub | scrub_bug_report, is_wormhole_code | table of codes; any() mutant RED | baseline | lead
- item 9 tester strings | tests/test_tester_trouble.py | guide contains imported dialog strings | baseline | lead
- item 10 log filter | packaging/tahoe-log-filter.sh, tests | snake_case identifier survives; leak tests green | baseline | lead
- item 11 doc drift | friends-and-family-releases, HANDOFF note | docs only | baseline | lead
- item 12 design doc | docs/design/ | short UI doc linked from README | baseline | lead
- finish | version, release notes, HANDOFF-v0.1.7.md | ci-local green, pushed | all items | lead

Items share `src/leasegrid_sync` and `tests` and must land as ordered commits on this branch. Sibling worktrees are forbidden. The lead implements them one at a time. The project-map agent writes only `.project-map/`.

Risks:

- Qt offscreen cannot always maximize. Skip only that part and log why. Also check drift under `xvfb-run -a` with `QT_QPA_PLATFORM=xcb`.
- Signal and process-group tests spawn real processes. Reap them. Never signal a group this process did not create.
- Never log or print an invite. Tests use a fake code.
- A red baseline is recorded and the suite must not go below it.
- Windows: SIGINT and SIGBREAK only; group kill may need a logged skip if it cannot be exercised.

## Baseline

Command: `PYTHON=$PWD/.venv/bin/python bash scripts/ci-local.sh`
Result: PASS
Counts: 517 passed, 5 xfailed, 4 warnings in 44.34s
Failing tests: none
Log: `/tmp/v017-baseline.log`

Item 1 ci-local: PASS, 520 passed, 5 xfailed, 4 warnings in 74.61s.
Item 2 ci-local: PASS, 521 passed, 5 xfailed, 4 warnings in 75.79s.
Item 3 ci-local: PASS, 525 passed, 5 xfailed, 4 warnings in 76.82s.
Item 4 ci-local: PASS, 528 passed, 5 xfailed, 4 warnings in 77.34s.
Item 5 ci-local: PASS, 531 passed, 5 xfailed, 4 warnings in 77.11s.
Item 6 ci-local: PASS, 532 passed, 5 xfailed, 4 warnings in 77.57s.
Item 7 ci-local: PASS, 536 passed, 5 xfailed, 4 warnings in 77.19s.
Item 8 ci-local: PASS, 541 passed, 5 xfailed, 4 warnings in 77.13s.
Item 7 xcb: `xvfb-run -a` with `QT_QPA_PLATFORM=xcb` passed test_unmaximize_restores_the_normal_size and test_three_maximize_cycles_keep_the_normal_position (2 passed in 0.17s). The normal position did not drift.

## Items

| # | Status | Commit | Tests | RED without fix |
|---|--------|--------|-------|-----------------|
| 1 | DONE | 1ca7a9b | test_signal_quits_and_reaps_the_stub[SIGTERM,SIGINT,SIGHUP] | RED: no handler installed → test_signal_quits_and_reaps_the_stub[SIGTERM] at tests/test_sync_signal_quit.py:195 (returncode -15) |
| 2 | DONE | 2e03456 | test_stop_kills_daemon_and_grandchild | RED: kill only the leader → test_stop_kills_daemon_and_grandchild at tests/test_sync_process_group.py:156 |
| 3 | DONE | 9cb063e | test_daemon_log_rotates_when_the_daemon_starts[tahoe,magic-folder], test_daemon_starts_when_log_rotation_fails[tahoe,magic-folder] | RED: skip the rotate call → test_daemon_log_rotates_when_the_daemon_starts at tests/test_sync_daemon_log.py:142 |
| 4 | DONE | af14629 | test_second_launch_fills_the_open_join_field, test_stale_socket_keeps_the_already_running_message, test_already_joined_window_drops_the_handed_invite | RED: don't send → test_second_launch_fills_the_open_join_field at tests/test_sync_join_handoff.py:185 |
| 5 | DONE | fa6b8f2 | test_fresh_empty_lock_relaunches_at_once, test_fresh_garbage_lock_relaunches_at_once, test_six_concurrent_starts_open_one_window, test_second_instance_on_the_same_home_starts_no_window | RED: no removal → test_fresh_empty_lock_relaunches_at_once at tests/test_sync_instance_lock.py:209 |
| 6 | DONE | 24783e4 | test_shown_paths_hide_the_account_name | RED: helper returns the path unchanged → test_shown_paths_hide_the_account_name at tests/test_sync_settings_actions.py:64 |
| 7 | DONE | ca070ce | test_other_geometry_version_opens_at_the_default, test_unmaximize_restores_the_normal_size, test_three_maximize_cycles_keep_the_normal_position, test_fitter_alone_rejects_an_oversized_record, test_guard_resets_a_size_the_fitter_let_through | RED: drop version check → test_other_geometry_version_opens_at_the_default at tests/test_sync_window_geometry.py:98; save geometry() → test_unmaximize_restores_the_normal_size at :144; fitter off → test_fitter_alone_rejects_an_oversized_record at :489; guard off → test_guard_resets_a_size_the_fitter_let_through at :520 |
| 8 | DONE | (this commit) | test_scrub_bug_report_code_boundaries | RED: any() → test_scrub_bug_report_code_boundaries[7-guitarist-side-True] at tests/test_sync_settings_actions.py:143 |
| 9 | pending | | | |
| 10 | pending | | | |
| 11 | pending | | | |
| 12 | pending | | | |
