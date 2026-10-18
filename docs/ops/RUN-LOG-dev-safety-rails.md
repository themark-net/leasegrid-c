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

Baseline is the v0.1.7 suite plus the un-wired seed rules. Interpreter: CPython 3.14.4 in `.venv`. Sync and tahoe extras installed. No semgrep yet.
