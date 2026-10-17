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

### 1. B3 corrupted geometry

state: DONE | tests: PYTHON=$PWD/.venv/bin/python bash scripts/ci-local.sh → 489 passed, 5 xfailed, 4 warnings in 43.60s, ci-local PASS | files: app.py, test_sync_window_geometry.py, HANDOFF sentence, decisions | err: none

A sign-flipped real frame and a `(0, 0, 2^31-1, 2^31-1)` frame open at the default size. The same flipped file launches the real app (`WINDOW_SHOWN`, exit 0). A `restoreGeometry` that resizes and then raises is logged once and the default size is put back.

RED: drop range check → `test_saved_frame_rejects_a_sign_flipped_left` at tests/test_sync_window_geometry.py:244 (also `test_max_int_frame_opens_at_the_default_size` at :261). The window and real-launch tests stayed green: the outer try still caught `OverflowError`.
RED: drop outer try → `test_partial_geometry_restore_keeps_the_default_size` at tests/test_sync_window_geometry.py:278 (also `test_corrupt_geometry_file_uses_the_default_size` and `test_deeply_nested_geometry_file_uses_the_default_size`). The `_saved_frame` tests stayed green: the range check still returned None.

### 2. B4 bug report

state: DONE | tests: PYTHON=$PWD/.venv/bin/python bash scripts/ci-local.sh → 489 passed, 5 xfailed, 4 warnings in 42.98s, ci-local PASS | files: app.py, test_sync_settings_actions.py, decisions | err: none

`bug_report_lines()` is the six-line allowlist. `bug_report_text()` is `scrub` of that join. The planted test also puts a base32 swissnum, a tub id, `URI:DIR2`, `URI:CHK`, and 32 hex into the log, `tahoe.cfg`, env, the invite session, and the share field. No 8-character piece of those is in the copied text. No product leak: the builder still emits only those six lines.

RED: 7c' invite code appended → `test_bug_report_omits_secrets_planted_in_logs_and_env` at tests/test_sync_settings_actions.py:145
RED: 7d' tahoe.cfg dumped → same test at :145 (the copy test stays green; scrub still masks `pb://`)
RED: 7f' share URL appended → same test at :145 (the copy test stays green; scrub still masks the join link)
RED: 7g' tail of sync-ui.log appended → same test at :145
RED: 7e' wallet dumped → same test at :145, and `test_copy_bug_report_has_about_line_and_no_secrets` at :216
RED: 7h' env dumped → same test at :145

### 3. Partial title bar

state: DONE | tests: PYTHON=$PWD/.venv/bin/python bash scripts/ci-local.sh → 490 passed, 5 xfailed, 4 warnings in 43.41s, ci-local PASS | files: test_sync_window_geometry.py | err: none

A saved x of -40 ends with the 80×28 title grab inside `availableGeometry()`. The fully-off cases stayed green under the mutant.

RED: `contains` → `intersects` in `_title_bar_on_a_screen` → `test_title_bar_partly_off_the_left_edge_stays_on_screen` at tests/test_sync_window_geometry.py:156

### 4. Saved width

state: DONE | tests: PYTHON=$PWD/.venv/bin/python bash scripts/ci-local.sh → 490 passed, 5 xfailed, 4 warnings in 43.50s, ci-local PASS | files: test_sync_window_geometry.py, decisions | err: none

The three title-bar tests request 1000 px wide and assert `saved_width != DEFAULT_WINDOW_SIZE[0]`. On this offscreen desktop Qt saved 1000, which is not 920.

RED: skip restore (`saved = _saved_frame(blob)` → `return`) → the three tests at tests/test_sync_window_geometry.py:126, :140, and :159 (`assert 920 == 1000`).
RED: requesting 920 in the above-screen test → `test_title_bar_above_the_screen_stays_on_screen` at :121 (`assert 920 != 920`).

### 5. Geometry tmp

Pending.

### 6. Scrub precision

Pending.
