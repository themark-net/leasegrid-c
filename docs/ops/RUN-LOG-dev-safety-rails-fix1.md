# Run log — dev safety rails fix1

Worktree: `/tmp/lg-dev-safety-rails`
Branch: `build/dev-safety-rails`
Head at start: `2f60f4a` (fast-forward already current)
PR: https://github.com/themark-net/leasegrid-c/pull/75
Started: 2026-10-18T07:10:21Z
Wall clock: stop around 08:25Z (75 minutes)
Interpreter: `PYTHON=$PWD/.venv/bin/python bash scripts/ci-local.sh`

Windows evidence: Actions run 39105640143, job `test (windows-2022)` 117610761630. `3 failed, 560 passed, 32 skipped, 5 xfailed`. The other `windows` job passed. This host cannot run Windows.

## Plan

Overview: Make the three Windows-only failures green without weakening POSIX checks. prove-red must match `\n` patterns against CRLF working trees and still restore the original bytes. The unreaped-leader respawn test must keep `client._proc.pid == new_pid` on POSIX and accept the Windows `.bat` launcher pid. Then ci-local, push, and poll the public check-runs API.

Phases:

- prove-red crlf | scripts/prove-red.py, tests/test_prove_red.py | CRLF temp repo with an LF pattern exits 0 and restores bytes; existing prove-red tests stay green | none | lead
- win32 launcher pid | tests/test_sync_backend.py | POSIX assertion unchanged; Windows holds the launcher or the worker; Linux run of this test stays green | none | lead
- verify | (no extra product files) | ci-local green; `scripts/prove-red.py docs/ops/prove-red-dev-safety-rails.py` all RED | both fixes | lead
- handoff | docs/ops/HANDOFF-dev-safety-rails.md, /tmp/pr-dev-safety-rails.md | counts, causes, receipt, check-run conclusions or "still running" | verify | lead

The two fix phases share this clone and the commit/push gate, so the lead implements both. No second checkout.

Risks:

- A CRLF normalize that rewrites the mutant with `Path.write_text` would double-convert on Windows. Write bytes. Restore the captured original bytes in `finally`.
- Guessing the Windows parent pid wrong cannot be checked here. The worker records its pid and its parent; the assertion accepts either, and POSIX stays equality with the worker.
- prove-red refuses dirty targets. Run the official receipt only when `backend.py`, `app.py`, and the skill file are clean.
- Do not signal any process this run did not start.

## Progress

- prove-red crlf: DONE | tests: `tests/test_prove_red.py` 6 passed; CRLF pattern `return 1\n` was not a literal match (`old literal match False`) and `_mutant_bytes` rewrites to CRLF `return 2` | files: scripts/prove-red.py, tests/test_prove_red.py | err: none
- win32 launcher pid: DONE | tests: `test_start_respawns_an_unreaped_exited_leader` passed on Linux; POSIX still asserts `client._proc.pid == new_pid` | files: tests/test_sync_backend.py | err: none
- verify: DONE locally | tests: `PYTHON=$PWD/.venv/bin/python bash scripts/ci-local.sh` → ruff clean, semgrep 8/8 and 0 findings, pytest 595 passed, 5 xfailed, 4 warnings in 138.50s. prove-red exit 0, all six RED, `git diff` clean on targets | files: 0 product | err: none
