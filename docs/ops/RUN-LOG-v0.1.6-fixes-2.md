# Run log — v0.1.6 fix round 2 (Tester FAIL @ 3455c8f)

Worktree: `/home/mark/DEVELOP/leasegrid-c/tmp/v016-fix2`
Branch: `build/v0.1.6-batch` (PR #73). Start HEAD `7e90ce9` (drop-in on Tester head `3455c8f`).
Base: `86a28c8` (v0.1.5). Interpreter: this tree's `.venv`.
Started: 2026-10-17. Wall clock cap: about 2.5 hours.

## Plan

Overview: Tester failed at `3455c8f` on B3 (a sign-flipped geometry frame crashes every launch) and B4 (the bug-report test stays green when the report dumps raw secrets). Fix those two, then the four follow-ups, one commit per item, on this branch only. The lead implements in order because every item edits `app.py` or the tests next to it, and this drop-in forbids any other worktree.

Phases:

- baseline | docs/ops/RUN-LOG-v0.1.6-fixes-2.md | ci-local recorded | none | lead
- 1 B3 geometry crash | app.py, tests/test_sync_window_geometry.py, HANDOFF comment | corrupt frame opens at the default size, in-process and in a real launch; range check and outer try each go RED alone | baseline | lead
- 2 B4 bug report | app.py, tests/test_sync_settings_actions.py | raw report is a 6-line allowlist; unknown secret shapes leave no 8-char fragment; 7c' 7d' 7f' 7g' RED; 7e' 7h' still RED | 1 | lead
- 3 partial title bar | app.py (read), tests/test_sync_window_geometry.py | x=-40 ends with the title grab inside availableGeometry; contains→intersects RED | 2 | lead
- 4 saved width | tests/test_sync_window_geometry.py | the three title-bar tests assert saved_width != 920 | 3 | lead
- 5 geometry tmp | app.py, tests/test_sync_window_geometry.py | a failed os.replace leaves no window-geometry.json.tmp | 4 | lead
- 6 scrub precision | app.py, tests/test_sync_settings_actions.py | punctuation and caps redacted; dates and 500-from-server-side kept | 5 | lead
- handoff | docs/HANDOFF-v0.1.6.md, this log | final ci-local counts, table, v0.1.7 lines, push | 6 | lead

Risks:

- Shared `app.py` — one item at a time, no parallel editors.
- Range check and the outer try can hide each other — one test calls `_saved_frame` (range check alone) and one feeds corrupt JSON or a partial restore (try alone).
- Mutation proofs are restored before any commit.
- Offscreen width — request 1000 px so the saved width is not the 920 default on windows-2022 (minimum 863).
- A missing geometry file is not logged — only a file that fails while restoring.

## Baseline

state: DONE | tests: PYTHON=$PWD/.venv/bin/python bash scripts/ci-local.sh → 484 passed, 5 xfailed, 4 warnings in 43.85s, ci-local PASS | files: run log + one decision line | err: none

Failing tests: none. Matches the Tester suite count at `3455c8f`.

## Items
