# Run log — Leasegrid Sync v0.1.7 fix round 1

Worktree: `/home/mark/DEVELOP/leasegrid-c/tmp/v017-fixes`
Branch: `build/v0.1.7-batch` (no upstream)
Base: `fbeb6f1` (`v0.1.7: handoff`). Head at start: `3d64b06` (the drop-in; same commit on `origin/build/v0.1.7-batch`).
Started: 2026-10-17
Interpreter: `.venv/bin/python`
CI: `PYTHON=$PWD/.venv/bin/python bash scripts/ci-local.sh`
Baseline from `docs/HANDOFF-v0.1.7.md`: 542 passed, 5 xfailed, 4 warnings in 77.59s.

Remote check: `origin/build/v0.1.7-batch` is `3d64b06`. No other remote branch holds this B1 fix.

## Plan

Overview: Reviewer failed PR #74 at `fbeb6f1` because `--join` can hand an invite to a squatter on the world-shared socket, and because an empty lock can be stolen mid-write. Three ordered fixes on this worktree: a lock-gated private handoff, a short retry before taking an empty lock, and test hooks that stay inert unless the test driver arms them. Each item gets fail-path tests, a mutation check, ci-local, one commit, and a fast-forward push. Then the handoff. No PR.

Phases:

- item 1 B1 private handoff | src/leasegrid_sync/app.py, tests/test_sync_join_handoff.py, design handoff paragraph | squatter gets 0 bytes; happy-path two-process test still passes; ci-local green | none | lead
- item 2 empty-lock retry | src/leasegrid_sync/app.py, tests/test_sync_instance_lock.py | mid-write PID keeps the lock; empty, garbage, and 6-way stay green | item 1 | lead
- item 3 test-hook gate | src/leasegrid_sync/app.py, tests that arm LEASEGRID_TEST_* | env var alone writes no invite dump | item 2 | lead
- handoff | docs/HANDOFF-v0.1.7.md, docs/design/60-DESKTOP-UI-V016.md, this log | final ci-local, mutation table, push | items 1–3 | lead

Items share `src/leasegrid_sync/app.py`. The drop-in allows only this worktree and `/tmp`, so the lead implements them one at a time. The project-map agent writes only `.project-map/`.

Risks:

- AF_UNIX path cap. Prefer `<home>/run` then `$XDG_RUNTIME_DIR/leasegrid-sync`, then `$TMPDIR/leasegrid-sync-<uid>`, and keep the encoded path under 100 bytes.
- A private-dir check that chmods an existing directory would hide a squatter. Create mode 0700 only for a directory this process just made. An existing directory is lstat'd and refused when it is a symlink, the wrong uid, or group/other accessible.
- Mutation checks edit the tree. Restore before any commit. A mutated tree is never pushed.
- Real sockets and real lock files. Every test has a timeout. Reap processes this run starts.

## Items

| # | Status | Commit | Tests | RED without fix |
|---|--------|--------|-------|-----------------|
| 1 | DONE | 176274f | old-path squatter, free lock, mode 0755, symlink dir, wrong uid, file and fifo, long home, UserAccessOption; existing two-process handoff still passes | see below |
| 2 | DONE | ceac025 | test_empty_lock_mid_write_is_not_taken; empty, garbage, and six-start tests stay green | RED: no retry → test_empty_lock_mid_write_is_not_taken |
| 3 | DONE | 789e53c | test_real_entry_does_not_dump_an_invite_from_the_env, test_handed_invite_is_not_dumped_when_hooks_are_off; join and signal drivers set _TEST_HOOKS | RED: the gate is removed → test_real_entry_does_not_dump_an_invite_from_the_env |
| handoff | DONE | this commit | final ci-local 555 passed, 5 xfailed, 4 warnings in 81.24s | docs only |

state: DONE | tests: `PYTHON=$PWD/.venv/bin/python bash scripts/ci-local.sh` → 552 passed, 5 xfailed, 4 warnings in 80.83s | files: app.py, test_sync_join_handoff.py, test_sync_join_handoff_private.py | err: none

Item 1 ci-local: PASS, 552 passed, 5 xfailed, 4 warnings in 80.83s. Baseline was 542 passed, 5 xfailed. Ten new tests.

RED: send before the lock check (the old order) → test_old_path_squatter_receives_nothing_when_the_lock_is_free
RED: drop the lock gate → test_free_lock_does_not_connect
RED: skip the mode check → test_shared_directory_receives_nothing
RED: stat instead of lstat → test_symlinked_directory_receives_nothing
RED: skip the uid check → test_wrong_owner_receives_nothing
RED: skip S_ISSOCK → test_non_socket_receives_nothing
RED: no fallback → test_long_home_still_hands_off
RED: the option is removed → test_join_server_is_user_only

The client checks the lock before any connect. The socket lives in a 0700 directory (`<home>/run`, else `$XDG_RUNTIME_DIR/leasegrid-sync`, else `$TMPDIR/leasegrid-sync-<uid>`). A symlink, the wrong uid, mode `& 0o077 != 0`, or a non-socket is refused and the planted listener reads 0 bytes. Windows keeps the lock gate and sets `QLocalServer.UserAccessOption` before `listen`. The pipe owner is not checked from the client.

state: DONE | tests: `PYTHON=$PWD/.venv/bin/python bash scripts/ci-local.sh` → 553 passed, 5 xfailed, 4 warnings in 80.48s | files: app.py, tests/test_sync_instance_lock.py | err: none

Item 2 ci-local: PASS, 553 passed, 5 xfailed, 4 warnings in 80.48s.

RED: no retry → test_empty_lock_mid_write_is_not_taken (`assert True is False`)

When `tryLock(0)` fails and the PID is not readable, wait 100 ms and look again. Remove the file only if it is still unreadable. A helper that writes a live pid and hostname about 50 ms after creating an empty file keeps the lock.

state: DONE | tests: `PYTHON=$PWD/.venv/bin/python bash scripts/ci-local.sh` → 555 passed, 5 xfailed, 4 warnings in 81.53s | files: app.py, tests/test_sync_join_handoff.py, tests/test_sync_signal_quit.py | err: none

Item 3 ci-local: PASS, 555 passed, 5 xfailed, 4 warnings in 81.53s.

RED: the gate is removed → test_real_entry_does_not_dump_an_invite_from_the_env (dump file exists)
RED: the gate is removed → test_handed_invite_is_not_dumped_when_hooks_are_off (dump file exists)

`LEASEGRID_TEST_INVITE_DUMP`, `LEASEGRID_TEST_JOIN_READY`, and `LEASEGRID_TEST_SIGNAL_READY` are inert unless `app._TEST_HOOKS` is true. Only the test drivers set that flag before `main()`. The real `python -m leasegrid_sync` entry does not. An env var alone writes no dump file.

state: DONE | tests: `PYTHON=$PWD/.venv/bin/python bash scripts/ci-local.sh` → 555 passed, 5 xfailed, 4 warnings in 81.24s | files: docs/HANDOFF-v0.1.7.md, docs/design/60-DESKTOP-UI-V016.md, this log | err: none

Handoff section "Fix round 1 after Reviewer FAIL @ fbeb6f1" records B1, the empty-lock wait, the test-hook gate, the mutation table, and this ci-local. None skipped. No PR.
