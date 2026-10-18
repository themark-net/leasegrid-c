# Run log — dev safety rails

Worktree: `/tmp/lg-dev-safety-rails`
Branch: `build/dev-safety-rails`
Base after merge: `6219383` (`dev-safety-rails: merge main (v0.1.7)`), `origin/main` `78a691a` version `0.1.7`
Drop-in seed: `ec81d39`
Started: 2026-10-17
Interpreter: `.venv/bin/python` via `PYTHON=$PWD/.venv/bin/python bash scripts/ci-local.sh`

Precondition: `origin/main` `pyproject.toml` version is `0.1.7`. Proceed.

Remote check: no other remote branch implements this gate. `origin/build/dev-safety-rails` was the seed (`ec81d39`) only.

## Plan

Overview: Catch lock, PID, IPC, and secret-leak mistakes in CI before a Tester or Reviewer round. Wire the seed Semgrep rules and a stricter ruff select into ci-local and Actions, add a systems-safety skill plus an AGENTS.md rule block, add a proof-of-RED harness, then land behavioral tests (and the two allowed fixes) for the v0.1.7 mutation survivors. One commit per item on this branch. No PR.

Phases:

- merge main | (done) `6219383` | version on origin/main is 0.1.7 and history is merged, never rebased | none | lead
- baseline | docs/ops/RUN-LOG-dev-safety-rails.md | ci-local counts recorded, commit `dev-safety-rails: run log baseline` | merge | lead
- item 1 semgrep+ruff | pyproject.toml, scripts/ci-local.sh, .github/workflows/ci.yml, suppressions in src/scripts/packaging | semgrep --test and scan at 0 hits; ruff select in pyproject; five mutants RED then restored | baseline | lead
- item 2 systems-safety | .grok/skills/systems-safety/SKILL.md, AGENTS.md, CONTRIBUTING.md, tests/test_systems_rules_doc.py | consistency test green; three mutants RED | item 1 (standing rule cites the gate) | lead
- item 3 prove-red | scripts/prove-red.py, tests/test_prove_red.py, .github/pull_request_template.md, AGENTS.md, docs/ops/prove-red-dev-safety-rails.py | harness tests green on the temp git repo; three mutants RED; item 2 receipt | item 2 | lead
- item 4 survivors | backend.py, app.py, tests, docs/ops/prove-red-dev-safety-rails.py | R9n and latest-wins fixed; N1i, L5n, follow-up 3 tested; prove-red receipt | item 3 | lead
- finish | docs/ops/HANDOFF-dev-safety-rails.md, /tmp/pr-dev-safety-rails.md | ci-local counts, handoff pushed, PR body written, no PR opened | all items | lead

Items share this clone, AGENTS.md, and the ci-local gate. They land as ordered commits. The lead implements them. The project-map agent writes only `.project-map/`.

Risks:

- Semgrep 1.181.0 may lack a CPython 3.14 wheel. ci-local must fail closed unless `CI_LOCAL_SKIP_SEMGREP=1`. Mutations still have to run semgrep, so install it here if the wheel exists.
- New ruff/semgrep hits on v0.1.7 code are suppressed with a reason or logged, not fixed, except the item 4 bugs.
- A red baseline is recorded. The suite must not go below it.
- Signal and lock tests spawn real processes. Reap only processes this run starts.
- Wall clock is 2.5 hours from start. Finish the current commit, then handoff.

## Progress

- merge: DONE | tests: not run yet | files: merge of origin/main | err: none
- baseline: DONE | tests: `PYTHON=$PWD/.venv/bin/python bash scripts/ci-local.sh` → ruff all checks passed; pytest 581 passed, 5 xfailed, 4 warnings in 139.92s | files: run log + decisions | err: none
- item 1: DONE | tests: same command → ruff clean, semgrep 8/8 and 0 findings, pytest 581 passed, 5 xfailed, 4 warnings in 135.35s | files: pyproject, ci-local, ci.yml, three B904 sites, six nosemgrep/noqa | err: none

Baseline is the v0.1.7 suite plus the un-wired seed rules. Interpreter: CPython 3.14.4 in `.venv`. Sync and tahoe extras installed.

Item 1 triage (0 unsuppressed hits):

- Ruff B904 ×3 fixed with `raise ... from err` (`check_0b.py` replay and R-reject, `topup.py` 402). B905 did not fire at `target-version = py39`.
- Ruff SIM115 ×2 on daemon log handles and ×4 on devnull logs in `test_sync_process_group.py`: noqa, the handle has to stay open. Listed S rules: 0 hits in src/scripts/packaging. Test S hits ignored by `tests/**`.
- Semgrep 7 hits, all suppressed, none left as open bugs: `af-unix-path-length` on the client socket (path already capped in `join_endpoint`); `getpgid` / `getpgrp` / `killpg` / two `SIGKILL` sites (Windows returns before these; `killpg` only gets a pgid `_foreign_pgid` still owns).

RED:

- RED: delete `pattern-not-inside` `setSocketOptions` → `semgrep --test` exit 1, `qlocalserver-listen-without-user-access-option` incorrect line 36
- RED: `lock.setStaleLockTime(0)` in `acquire_instance_lock` → ci-local exit 1 at semgrep, `qlockfile-manual-stale-removal`
- RED: `os.chmod(path, 0o777)` in `src/leasegrid_sync/app.py` → ci-local exit 1 at ruff, `bad-file-permissions` (S103)
- RED: one `# ruleid: ipc-endpoint-in-shared-tmp` changed to `# ok:` → `semgrep --test` exit 1, incorrect line 16

`CI_LOCAL_SKIP_SEMGREP` was not used.

- item 2: DONE | tests: ci-local → 584 passed, 5 xfailed, 4 warnings in 137.78s; `tests/test_systems_rules_doc.py` 3 passed | files: skill, AGENTS.md, CONTRIBUTING.md, doc test | err: none

RED:

- RED: delete the SS3 section from the skill → `test_semgrep_ids_are_in_agents_and_the_skill` skill missing SS3
- RED: `name: systems-safety-renamed` → `test_skill_frontmatter_matches_its_folder`
- RED: rule message gains `SS9` → same id test, AGENTS.md missing SS9

Grok skill list: this session listed `systems-safety` after `SKILL.md` was written (description matches, path `.grok/skills/systems-safety/SKILL.md`). A second process was not started.

- item 3: DONE | tests: ci-local → 589 passed, 5 xfailed, 4 warnings in 139.02s; prove-red tests 5 passed | files: scripts/prove-red.py, tests/test_prove_red.py, PR template, AGENTS sentence, cases file | err: none

```
name               result
skill-ss3-section  RED
```

RED:

- RED: drop `path.write_bytes(original)` from the `finally` → `test_caught_mutant_is_red_and_restores` bytes differ (`return 2` left in the file)
- RED: survivor branch `return 0` → `test_surviving_mutant_exits_1` sees exit 0
- RED: `if False and _uncommitted` → `test_dirty_target_exits_2_and_is_unchanged` stderr is `git diff is not quiet`, not `uncommitted`
