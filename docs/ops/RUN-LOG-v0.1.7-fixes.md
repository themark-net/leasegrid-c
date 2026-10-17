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
| 1 | DONE | this commit | old-path squatter, free lock, mode 0755, symlink dir, wrong uid, file and fifo, long home, UserAccessOption; existing two-process handoff still passes | see below |
| 2 | pending | | | |
| 3 | pending | | | |
| handoff | pending | | | |

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
