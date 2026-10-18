# Run log — dev safety rails fix2

Worktree: `/home/mark/DEVELOP/leasegrid-c/tmp/pr75-fix2`
Branch: `bot/pr75-fix2` (do not push)
Head at start: `5d2101f` (matches `origin/build/dev-safety-rails` and `origin/main` is `78a691a`)
Started: 2026-10-18T07:52:52Z
Wall clock: stop around 10:22Z
Interpreter: `PYTHON=$PWD/.venv/bin/python bash scripts/ci-local.sh`
Ruff in this venv: 0.17.1

## Baseline

`PYTHON=$PWD/.venv/bin/python bash scripts/ci-local.sh` at `5d2101f`: ruff clean, semgrep 8/8 and 0 findings, pytest 595 passed, 5 xfailed, 4 warnings in 138.94s. Exit 0.

## Items

- A B1 signals: DONE | ci-local 597 passed, 5 xfailed, 4 warnings in 138.60s | files: src/leasegrid_sync/app.py, tests/test_sync_already_running.py
  RED: revert app.py signal change → `test_already_running_second_launch_exits_0_on_sigterm[SIGINT]` rc -6 with KeyboardInterrupt traceback; `[SIGHUP]` rc -1 (SIGTERM row still passed)
  GREEN: the same test, SIGTERM/SIGINT/SIGHUP, rc 0, no Traceback, first app alive, lock bytes unchanged
- B B2 false RED: pending
- C reap assert: pending
- D SS2 poll advice: pending
- E ST3 box stays up: pending
- F prove-red signal restore: pending
- G ruff pin: pending
- H semgrep path comments: pending
- I changelog: pending
- J handoff: pending
