# Run log — v0.1.7 fix round 2

Slug: v0.1.7-fixes2. Worktree: `/home/mark/DEVELOP/leasegrid-c/tmp/v017-fixes`. Branch: `build/v0.1.7-batch`. Started at `9c099d5` (drop-in on `c595ea5`). Tester FAIL on PR #74 at `fbeb6f1`.

Overview: Fix Tester blockers T2–T5 and the listed follow-ups. Each item is fix, tests, mutation, ci-local, one commit, then a fast-forward push. The lead does the items in order in this worktree.

Phases:
- 1 log-filter | packaging/tahoe-log-filter.sh, tests/test_tahoe_log_filter.py | full filter tests pass under mawk and gawk shims; diff vs b4e9b70 is sed-only | none | general
- 2 empty-lock age | src/leasegrid_sync/app.py, tests/test_sync_instance_lock.py | 0 double holders in a ≥200-round race and in 1000 local trials | 1 | general
- 3 reap stale pgid | src/leasegrid_sync/backend.py, tests/test_sync_stop_reap.py, tests/test_sync_process_group.py | no signal after the leader is reaped; unrelated pgid survives | 1 | general
- 4 rotation wording | docs/release-notes/v0.1.7.md, README.md, docs/TESTERS.md, docs/TESTER-GUIDE.md, tests | notes say rotate when the daemon starts, not the same way as sync-ui.log | none | general
- 5 join flood | src/leasegrid_sync/app.py, tests/test_sync_join_handoff.py | 400 connections, process stays alive, a later handoff works | 2 | general
- 6 oversized join | src/leasegrid_sync/app.py, tests | held lock shows already-running; free lock rejects without joining | 5 | general
- 7 invite overwrite | src/leasegrid_sync/app.py, tests | default keeps typed text; Yes uses the handed invite | 6 | general
- 8 path masking | src/leasegrid_sync/app.py, tests | banner, symlink, case, escape, empty path | 7 | general
- 9 stub reap | tests/test_sync_signal_quit.py | recorded stub PIDs are dead after the module | none | general
- 10 handoff | docs/HANDOFF-v0.1.7.md, docs/ops/RUN-LOG-v0.1.7-fixes2.md | v0.1.8 candidates listed; final ci-local; push | 1–9 | general

Risks:
- Shared app.py and one fast-forward branch. Mitigation: one item at a time in this worktree, no sibling worktree.
- mawk `{40,}` is not portable. Mitigation: no awk left in the filter; prove it with PATH shims.
- A young empty lock used to relaunch at once. Mitigation: refuse under 2s, and say the crash-mid-write wait is that threshold instead of 30s.
- ci-local is about 80s. Mitigation: run the item's tests first, then one ci-local per item.

Exits: goal, 6 attempts or 3 identical failures, ~3 hours or 40 minutes without a commit, STOP file, or under 2 GB free. Resume at the first item that is not DONE or SKIPPED.

- state: DONE | tests: PYTHON=.venv/bin/python bash scripts/ci-local.sh → 557 passed, 5 xfailed, 4 warnings in 81.14s | files: packaging/tahoe-log-filter.sh, tests/test_tahoe_log_filter.py | err: none
  RED: awk `{40,}` under mawk 1.3.4 20200120 → test_v015_shapes_never_leak[base64url-unpadded] (181/200). Local /usr/bin/mawk is 1.3.4 20260129, which honors intervals, so that binary stays green. Diff vs b4e9b70 is the sed-only snake_case keep. Full file also passed with PATH shims for /usr/bin/mawk and /usr/bin/gawk.

## 2 empty-lock age

- state: DONE | tests: PYTHON=.venv/bin/python bash scripts/ci-local.sh → 559 passed, 5 xfailed, 4 warnings in 120.25s | files: src/leasegrid_sync/app.py, tests/test_sync_instance_lock.py | err: none
  1000 trials × 6 workers: empty >1 holder=0 (0 holders=1000); garbage >1=0 (0 holders=1000); none >1=0 (0 holders=0); aged (mtime now-5) >1=0 (0 holders=0). No "Could not remove our own lock file".
  RED: drop setStaleLockTime and the young-age return, then removeStaleLockFile → test_fresh_empty_lock_is_refused (AssertionError: window). Removing only the Python age return stays green, because staleLockTime 2000 ms already refuses a young file.

## 3 reap stale pgid

- state: DONE | tests: PYTHON=.venv/bin/python bash scripts/ci-local.sh → 561 passed, 5 xfailed, 4 warnings in 120.91s | files: src/leasegrid_sync/backend.py, tests/test_sync_process_group.py | err: none
  RED: drop the poll() liveness returns before the group signal → test_reaped_leader_does_not_signal_a_reused_pid (victim returncode -15).

## 4 rotation wording

- state: DONE | tests: PYTHON=.venv/bin/python bash scripts/ci-local.sh → 562 passed, 5 xfailed, 4 warnings in 118.49s | files: docs/release-notes/v0.1.7.md, README.md, docs/TESTERS.md, docs/TESTER-GUIDE.md, tests/test_release_notes.py | err: none
  Size-based rotation while a daemon is running is not in this fix. It is a v0.1.8 candidate.
  RED: restore "the same way sync-ui.log does" → test_daemon_logs_rotate_when_the_daemon_starts (AssertionError: notes).

## 5 join flood

- state: DONE | tests: PYTHON=.venv/bin/python bash scripts/ci-local.sh → 563 passed, 5 xfailed, 4 warnings in 119.77s | files: src/leasegrid_sync/app.py, tests/test_sync_join_flood.py | err: none
  RED: no cap and no cleanup → test_join_flood_leaves_the_app_alive_for_a_later_handoff (AssertionError: 109 <= 8). A sequential connect-and-close did not crash, so the test holds the sockets open and counts how many stay connected.

## 6 oversized join

- state: DONE | tests: PYTHON=.venv/bin/python bash scripts/ci-local.sh → 565 passed, 5 xfailed, 4 warnings in 119.11s | files: src/leasegrid_sync/app.py, src/leasegrid_sync/cli.py, tests/test_sync_join_oversize.py | err: none
  RED: return "free" for an empty or oversized invite → test_oversized_join_with_a_held_lock_says_already_running and test_oversized_join_with_a_free_lock_is_rejected (AssertionError: join was attempted).

## 7 handed invite

- state: DONE | tests: PYTHON=.venv/bin/python bash scripts/ci-local.sh → 566 passed, 5 xfailed, 4 warnings in 121.29s | files: src/leasegrid_sync/app.py, tests/test_sync_handed_invite.py | err: none
  RED: overwrite the Join field unconditionally → test_handed_invite_keeps_typed_text_unless_the_user_says_yes (assert 'B' == 'A').

## 8 path masking

- state: DONE | tests: PYTHON=.venv/bin/python bash scripts/ci-local.sh → 568 passed, 5 xfailed, 4 warnings in 121.62s | files: src/leasegrid_sync/app.py, src/leasegrid_sync/backend.py, tests/test_sync_display_path.py, tests/test_sync_settings_actions.py | err: none
  RED: identity helper → test_display_path_table (link-home == '~'). RED: no resolve() → test_display_path_table (real/fakeuser/logs/tahoe.log == '~/logs/tahoe.log').

## 9 stub reap

- state: DONE | tests: PYTHON=.venv/bin/python bash scripts/ci-local.sh → 568 passed, 5 xfailed, 4 warnings in 122.98s | files: tests/test_sync_signal_quit.py, tests/test_sync_process_group.py | err: none
  The drop-in names no mutant. The module fixture asserts every recorded stub pid is dead after the file. The signal stub now writes a grandchild pid, and finally SIGKILLs only the pids in those files.
