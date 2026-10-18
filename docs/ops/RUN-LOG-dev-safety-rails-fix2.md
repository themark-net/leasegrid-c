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
- B B2 false RED: DONE | ci-local 602 passed, 5 xfailed, 4 warnings in 140.34s | files: scripts/prove-red.py, tests/test_prove_red.py, AGENTS.md, .grok/skills/systems-safety/SKILL.md, .github/pull_request_template.md
  RED: `_run_case` returned RED for any non-zero pytest exit and skipped the clean baseline → tests 1–5 failed (each printed RED and prove-red exited 0): typo node id, `-k zzz`, import break, missing fixture, always-failing baseline
  GREEN: `test_typo_node_id_is_setup_error` (baseline rc=4), `test_no_tests_collected_is_setup_error` (baseline rc=5), `test_import_break_is_setup_error` (rc=2), `test_missing_fixture_is_setup_error` (baseline rc=1), `test_always_failing_baseline_is_setup_error` (baseline rc=1), `test_caught_mutant_is_red_and_restores` (RED, exit 0). Overall exit 2 on setup errors.
  Receipt (`scripts/prove-red.py docs/ops/prove-red-dev-safety-rails.py`) exit 0, `git diff` clean on backend.py and app.py:

```
name                      result
skill-ss3-section         RED
r9n-zombie-as-running     RED
n1i-yes-joins             RED
l5n-drop-second-trylock   RED
latest-wins-keep-pending  RED
sigterm-no-handler        RED
```
- C reap assert: DONE | ci-local 602 passed, 5 xfailed, 4 warnings in 140.27s | files: tests/test_sync_backend.py
  RED: `start()` skipped `reap_child` on the non-running leader → `test_start_respawns_an_unreaped_exited_leader` (`start() left the old leader unreaped`, `returncode is None`)
  GREEN: `test_start_respawns_an_unreaped_exited_leader`
- D SS2 poll advice: DONE | ci-local 603 passed, 5 xfailed, 4 warnings in 144.24s | files: .grok/skills/systems-safety/SKILL.md, AGENTS.md, tools/semgrep/leasegrid-systems.yml, tests/test_systems_rules_doc.py. Left docs/build-dropins/dev-safety-rails.md historical.
  RED: restored the old SS2 sentence (`Popen.poll()` is `None` immediately before the signal) → `test_ss2_does_not_recommend_poll_before_the_signal` (`immediately before` is back)
  GREEN: `test_ss2_does_not_recommend_poll_before_the_signal` and the other systems-rules doc tests
- E ST3 box stays up: pending
- F prove-red signal restore: pending
- G ruff pin: pending
- H semgrep path comments: pending
- I changelog: pending
- J handoff: pending
