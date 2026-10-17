# Handoff — Leasegrid Sync v0.1.7

Branch: `build/v0.1.7-batch` (no upstream). Base: `b4e9b70` (`origin/main`, tag v0.1.6).
Head: the commit that writes the fix round 2 section (`v0.1.7: handoff after fix round 2`). Round 1's handoff commit remains in the history below.
Batch head was `fbeb6f1` (`v0.1.7: handoff`), parent `f8a3271` (version bump). The drop-in on top of that was `3d64b06`.
Batch baseline: 517 passed, 5 xfailed, 4 warnings in 44.34s. Batch final: 542 passed, 5 xfailed, 4 warnings in 77.59s.
Fix round 1 final is in the section below.
None skipped. Decisions: [`docs/ops/AUTONOMOUS-DECISIONS-v0.1.7.md`](ops/AUTONOMOUS-DECISIONS-v0.1.7.md). Run logs: [`docs/ops/RUN-LOG-v0.1.7-batch.md`](ops/RUN-LOG-v0.1.7-batch.md), [`docs/ops/RUN-LOG-v0.1.7-fixes.md`](ops/RUN-LOG-v0.1.7-fixes.md), [`docs/ops/RUN-LOG-v0.1.7-fixes2.md`](ops/RUN-LOG-v0.1.7-fixes2.md).

## Fix round 1 after Reviewer FAIL @ fbeb6f1

Reviewer FAIL on PR #74 at `fbeb6f1`. None skipped.

- **B1.** `--join` checks the home lock before any connect. The listener uses a 0700 directory (`<Sync home>/run` when the path is under 100 bytes, else `$XDG_RUNTIME_DIR/leasegrid-sync`, else `$TMPDIR/leasegrid-sync-<uid>`). The client refuses a symlink, the wrong uid, a mode with group or other bits, or a path that is not our socket. `176274f`.
- **(a)** An empty lock with no readable PID waits 100 ms. The file is removed only if the PID is still unreadable, so a starter mid-write keeps the lock. `ceac025`. Fix round 2 stops that removal: a PID-less lock younger than 2s is left in place.
- **(b)** `LEASEGRID_TEST_INVITE_DUMP`, `LEASEGRID_TEST_JOIN_READY`, and `LEASEGRID_TEST_SIGNAL_READY` do nothing unless a test driver sets `app._TEST_HOOKS`. An env var alone writes no invite dump. `789e53c`.

Windows has no portable way to read the pipe owner from the client. The defense there is the lock gate plus `QLocalServer.UserAccessOption` before `listen`. This handoff did not describe a `/tmp` socket or a send-then-lock order. The endpoint above replaces that.

| Mutant | Test | Result |
|--------|------|--------|
| send before the lock check (the old order) | test_old_path_squatter_receives_nothing_when_the_lock_is_free | RED |
| drop the lock gate | test_free_lock_does_not_connect | RED |
| skip the mode check | test_shared_directory_receives_nothing | RED |
| stat instead of lstat | test_symlinked_directory_receives_nothing | RED |
| skip the uid check | test_wrong_owner_receives_nothing | RED |
| skip S_ISSOCK | test_non_socket_receives_nothing | RED |
| no fallback | test_long_home_still_hands_off | RED |
| the option is removed | test_join_server_is_user_only | RED |
| no retry | test_empty_lock_mid_write_is_not_taken | RED |
| the gate is removed | test_real_entry_does_not_dump_an_invite_from_the_env | RED |

Fix round 1 counts: 555 passed, 5 xfailed, 4 warnings. Item 1 ci-local 552 passed in 80.83s. Item 2: 553 passed in 80.48s. Item 3: 555 passed in 81.53s. Final ci-local: PASS, 555 passed, 5 xfailed, 4 warnings in 81.24s.

| # | Status | Commit | Tests | RED |
|---|--------|--------|-------|-----|
| 1 | DONE | 1ca7a9b | test_signal_quits_and_reaps_the_stub | no handler → tests/test_sync_signal_quit.py:195 |
| 2 | DONE | 2e03456 | test_stop_kills_daemon_and_grandchild | kill only the leader → tests/test_sync_process_group.py:156 |
| 3 | DONE | 9cb063e | daemon log rotates, and starts when rotation fails | skip rotate → tests/test_sync_daemon_log.py:142 |
| 4 | DONE | af14629 | second --join fills the field; stale socket; already joined drops it | don't send → tests/test_sync_join_handoff.py:185 |
| 5 | DONE | fa6b8f2 | empty lock, garbage lock, six starts, live holder | no removal → tests/test_sync_instance_lock.py:209 |
| 6 | DONE | 24783e4 | test_shown_paths_hide_the_account_name | identity helper → tests/test_sync_settings_actions.py:64 |
| 7 | DONE | ca070ce | version, un-maximize, three cycles, fitter, guard | tests/test_sync_window_geometry.py:98, :144, :489, :520 |
| 8 | DONE | caae73d | test_scrub_bug_report_code_boundaries | any() → tests/test_sync_settings_actions.py:143 |
| 9 | DONE | 0aa58b3 | test_trouble_section_names_shipped_recovery_in_at_most_eight_lines | change ALREADY_RUNNING → tests/test_tester_trouble.py:39 |
| 10 | DONE | 9e81896 | test_long_snake_case_name_survives_on_an_allowlisted_line | old `{40,}` rule → tests/test_tahoe_log_filter.py:206 |
| 11 | DONE | fcd3d87 | docs only | no behavior mutation |
| 12 | DONE | a946f80 | docs/design/60-DESKTOP-UI-V016.md | no behavior mutation |

Not verified: no Android SDK (versionName left at `0.4.0-slice-b`); Qt offscreen, plus one xvfb `QT_QPA_PLATFORM=xcb` check on the two maximize tests (2 passed, 0.17s); no real Windows or macOS GUI.

## Fix round 2 after Tester FAIL @ fbeb6f1

Tester FAIL on PR #74 at `fbeb6f1`. Items 1–10 are DONE. None skipped. CI: see PR checks.

- **T1.** Already in `c595ea5`: Windows CTRL_BREAK (the old rc=21), the bug-report `~` assertion on Windows, the macOS stub `getfqdn` stall, and the `_lock_writer_grace` hook.
- **T2.** The log filter is `sed -E` again. Long snake_case is kept by a SOH protect/restore around the v0.1.6 rule. No awk remains. `3de2c1e`.
- **T3.** A PID-less lock younger than 2s is refused and is not unlinked. Qt takes an older one inside `tryLock` (`staleLockTime` 2000 ms). A crash mid-write blocks the next launch for that 2s threshold, not about 30s. 1000 local trials, 6 workers: 0 double holders on empty, garbage, none, and aged locks. `88012ca`.
- **T4.** `reap_child` does not signal a process group after the leader has been reaped. `31f3689`.
- **T5.** The notes say `tahoe.log` and `magic-folder.log` rotate when the daemon starts. They do not say those files rotate the same way as `sync-ui.log`. `7e54cd3`.
- **Follow-up.** The join server keeps at most 8 pending sockets, aborts the rest, and drops an idle socket after 2s. `569a1db`.
- **Follow-up.** An oversized `--join` is not sent. A held home shows already-running and exits 1. A free home prints "That invite is too long." and exits 1. `2d38c20`.
- **Follow-up.** A handed invite does not replace typed text unless the user answers Yes. The default is No. Neither invite is logged. `97ee8c1`.
- **Follow-up.** Banners mask the home path, including through a symlinked home. Windows and macOS ignore letter case. A path that leaves home with `..` stays unchanged. An empty path is `""`. `18daa94`.
- **Follow-up.** Signal and process-group tests SIGKILL only the stub pids they recorded, including a grandchild. `fa36bb1`.

| Mutant | Test | Result |
|--------|------|--------|
| awk `{40,}` under mawk 1.3.4 20200120 | test_v015_shapes_never_leak[base64url-unpadded] | RED (181/200). Local mawk 20260129 honors intervals and stays green |
| drop setStaleLockTime and the young-age return, then removeStaleLockFile | test_fresh_empty_lock_is_refused | RED (window opened) |
| drop the poll() returns before the group signal | test_reaped_leader_does_not_signal_a_reused_pid | RED (victim -15) |
| restore "the same way sync-ui.log does" | test_daemon_logs_rotate_when_the_daemon_starts | RED |
| no join cap and no socket cleanup | test_join_flood_leaves_the_app_alive_for_a_later_handoff | RED (109 sockets still open; this Qt did not crash) |
| return "free" for an oversized invite | test_oversized_join_with_a_held_lock_says_already_running | RED (join was attempted) |
| overwrite the Join field unconditionally | test_handed_invite_keeps_typed_text_unless_the_user_says_yes | RED ('B' == 'A') |
| display_path returns the input | test_display_path_table | RED |
| display_path does not resolve the home | test_display_path_table | RED (symlink target leaked fakeuser) |

Fix round 2 counts: item 1 was 557 passed; item 2, 559; item 3, 561; item 4, 562; item 5, 563; item 6, 565; item 7, 566; items 8 and 9, 568 passed, 5 xfailed. Closing ci-local: 568 passed, 5 xfailed, 4 warnings in 119.32s. CI: see PR checks.

## v0.1.8 candidates

- Log-filter separators other than `-` or space at 4 characters, and any separator every 5–7.
- Percent-encoded base64, and JSON-escaped `\/` base64.
- Secrets split across a line wrap into pieces under 20 characters.
- Lengths below each cutoff: base32 under 20, hex under 32, mixed-case under 32, base64url under 40.
- Caveat guard misses 6 of 10 rewordings ("Coming soon", "available shortly after release", "may not work until CI publishes them").
- Base32-last ordering stays a backstop (equivalent mutant, 0 leaks in the probes).
- A signal in the first ~0.1 s of startup.
- Adopting an orphaned Tahoe from a crashed session.
- A lock path that is a directory or has mode 000.
- Size-based rotation of `tahoe.log` and `magic-folder.log` while the daemon is running.
- A second `--join` that arrives while an invite is still being typed.
- The cross-user check.

## Suggested PR

Title: `v0.1.7: quit cleanly, hand off a second invite, and tighten logs`

Quit on SIGTERM, SIGINT, and SIGHUP, and stop a daemon's process group only while its leader is still unreaped.
`tahoe.log` and `magic-folder.log` rotate when the daemon starts. A second `--join` fills the open window and does not auto-join. An oversized invite is not sent.
A PID-less lock younger than 2s is refused. An older one is taken without waiting about 30 seconds. Shown paths hide the account name, including in banners.
Geometry save and restore share one origin. The bug-report scrub matches the invite shape the app accepts.
The tester guide quotes the app's dialog strings. The public log filter keeps long snake_case names.

Do not open this PR from the batch.
