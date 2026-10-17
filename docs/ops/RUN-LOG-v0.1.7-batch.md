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

## Items

| # | Status | Commit | Tests | RED without fix |
|---|--------|--------|-------|-----------------|
| 1 | DONE | (this commit) | test_signal_quits_and_reaps_the_stub[SIGTERM,SIGINT,SIGHUP] | RED: no handler installed → test_signal_quits_and_reaps_the_stub[SIGTERM] at tests/test_sync_signal_quit.py:195 (returncode -15) |
| 2 | pending | | | |
| 3 | pending | | | |
| 4 | pending | | | |
| 5 | pending | | | |
| 6 | pending | | | |
| 7 | pending | | | |
| 8 | pending | | | |
| 9 | pending | | | |
| 10 | pending | | | |
| 11 | pending | | | |
| 12 | pending | | | |
