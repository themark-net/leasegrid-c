# Run log — v0.1.6 fix round 3 (Tester FAIL @ 8a70dd3, B5)

Worktree: `/home/mark/DEVELOP/leasegrid-c/tmp/v016-fix3`
Branch: `build/v0.1.6-batch` (PR #73). Start HEAD `29e9dee` (drop-in on Tester head `8a70dd3`).
Base: `86a28c8` (v0.1.5). Interpreter: this tree's `.venv`.
Started: 2026-10-17. Wall clock cap: about 2.5 hours.
Remote `origin/build/v0.1.6-batch` matched HEAD at start. No other branch holds this B5 fix.

## Plan

Overview: Tester failed at `8a70dd3` on B5. `restoreGeometry` still applies the unchecked tail of the geometry blob, and a bit flip there segfaults offscreen and opens a 16,777,215 px window on xcb. Store a plain JSON record, ignore old blobs, and stop calling `restoreGeometry`. Then stop the scrubber from eating ordinary `N-word-word` text, and correct the handoff.

Phases:

- baseline | docs/ops/RUN-LOG-v0.1.6-fixes-3.md | ci-local recorded (expect 496 passed, 5 xfailed) | none | lead
- 1 B5 geometry record | src/leasegrid_sync/app.py, tests/test_sync_window_geometry.py | old flipped blob launches at the default size; each record check goes RED alone; fuzz is 0 crashes on offscreen and xcb | baseline | lead
- 2 scrub wordlist | src/leasegrid_sync/pgp_words.py, app.py, tests/test_sync_settings_actions.py | the four false positives stay; real PGP codes are redacted; dropping the wordlist goes RED | 1 | lead
- 3 handoff accuracy | docs/HANDOFF-v0.1.6.md | 11e line matches Tester (RED); B3 claim covers the whole saved file | 2 | lead
- handoff | docs/HANDOFF-v0.1.6.md, this log | final ci-local, table, fuzz counts, push | 3 | lead

Risks:

- Shared `app.py` and one branch — one item at a time. No extra worktree (owner rule).
- A 1000 px window is wider than the ~800 px offscreen desktop — round-trip uses a size that fits, and an oversized record is clamped or replaced with the default before `resize`.
- Range checks can hide each other — each field has its own test that calls the validator.
- Mutation proofs are restored before any commit.
- `7-purple-sausage` is not in the PGP word list — boundary tests use real PGP words in those same positions.

## Baseline

state: DONE | tests: PYTHON=$PWD/.venv/bin/python bash scripts/ci-local.sh → 496 passed, 5 xfailed, 4 warnings in 42.99s, ci-local PASS | files: run log + one decision line | err: none

Failing tests: none. Head at the run was `29e9dee`. Started 2026-10-17T13:10:14Z.

## Items

### 1. B5 geometry record

state: DONE | tests: PYTHON=$PWD/.venv/bin/python bash scripts/ci-local.sh → 508 passed, 5 xfailed, 4 warnings in 43.25s, ci-local PASS | files: app.py, test_sync_window_geometry.py, decisions, this log | err: none

`_save_window_geometry` writes `{"version": 2, "x", "y", "width", "height", "maximized"}`. `_restore_window_geometry` never calls `restoreGeometry`. An old `{"geometry": "<base64>"}` file is ignored and rewritten as a record on quit. A bad version-2 field is logged once and the default size is kept. A size past the screen, the default, and the layout hint is replaced with the default size before `resize`. The guard does the same after apply and after `show`.

RED: drop the bool check in `_record_int` → `test_window_record_rejects_one_bad_field[bool-as-int]` (width `True` accepted). The other six field cases stayed green.
RED: drop the `isinstance(..., int)` check → `[float]` (`x=12.0` accepted). The bool case stayed green.
RED: drop the x range check → `[bad-x]`. RED: drop the y range check → `[bad-y]`. RED: drop the width check → `[bad-width]`. RED: drop the height check → `[bad-height]`. RED: drop the maximized bool check → `[maximized-int]`. Each of those left the other field cases green.
RED: put `restoreGeometry` back for an old blob → `test_corrupt_old_blob_launches_the_real_app` (`BEFORE_SHOW` height 16777215). The in-process old-blob test segfaulted (`rc=-11`) on the same mutant.
Drop the post-apply guard: `test_oversized_record_uses_the_default_size` and `test_oversized_height_uses_the_default_size` stayed green (the fitter already uses the default). `test_guard_resets_a_size_the_fitter_let_through` segfaulted (`rc=-11`) because `resize(16777215)` on the real window is what the guard was holding back.

Fuzz (`/tmp/geo_fuzz3.py`, Tester's old-blob cases plus record bit-flips and extremes), 1534 cases, chunks of 400:
- offscreen: 0 crashes, 0 title-bar misses, 0 windows larger than the no-file control (920×947), 0 sides ≥ 10000. 1533/1534 were larger than the 800×600 union because the join page itself is 920×947.
- xcb under `xvfb-run -a -s '-screen 0 1920x1080x24'`: 0 crashes, 0 title-bar misses, 0 larger than the 1920×1080 union, 0 sides ≥ 10000. Control window 920×826.

### 2. Scrub wordlist

(pending)

### 3. Handoff accuracy

(pending)
