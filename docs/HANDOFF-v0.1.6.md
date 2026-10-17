# Handoff — Leasegrid Sync v0.1.6

Branch: `build/v0.1.6-batch`
Base: `86a28c8217855f6f16387c08041c08674b50434d` (v0.1.5, `origin/main`). Built on v0.1.4 `ef17434`, then rebased.
Commit SHAs in the item table are from before the rebase; match commits by subject (`v0.1.6 item N`).
Rebase conflicts: TESTER-GUIDE bug-report list (kept both), version/asset links (took 0.1.6), README/TESTERS What's new (v0.1.6 bullets plus v0.1.5's #30 correction, which `test_tester_pages` requires). Release notes now point back at v0.1.5 @ `86a28c8`.

## Tests

Baseline: 406 passed, 1 xfailed, 4 warnings, 39.71s. Failing tests: none.
Final ci-local before rebase: PASS, 433 passed, 1 xfailed.
After rebase onto v0.1.5: ci-local at bd7b09e was 469 passed, 5 xfailed (this line previously said 468). Fix round: 484 passed, 5 xfailed.

## Items

| # | Status | Commit | Tests | RED without fix |
|---|--------|--------|-------|-----------------|
| 1 | DONE | 7a12515 | test_linked_worktree_uses_its_own_venv, test_explicit_python_is_honored_in_a_worktree, test_main_checkout_still_prefers_shared_venv | test_linked_worktree_uses_its_own_venv at tests/test_ci_local_worktree.py:79 |
| 2 | DONE | 0792361 | test_stop_reaps_child_that_ignores_sigterm, test_stop_is_safe_when_the_child_already_exited | test_stop_reaps_child_that_ignores_sigterm at tests/test_sync_stop_reap.py:59 |
| 3 | DONE | a4c4b2e | test_log_rotates_when_over_one_mebibyte_and_keeps_one_backup, test_rotation_failure_still_appends_and_does_not_raise | test_log_rotates_when_over_one_mebibyte_and_keeps_one_backup at tests/test_sync_ui_log.py:32 |
| 4 | DONE | d9045e1 | test_second_instance_on_the_same_home_starts_no_window, test_a_different_sync_home_is_not_blocked, test_stale_lock_from_a_killed_process_is_recovered, test_status_cli_is_not_blocked_by_the_home_lock | test_second_instance_on_the_same_home_starts_no_window at tests/test_sync_instance_lock.py:80 |
| 5 | DONE | 9e17bbb | test_keep_open_ignores_close_and_leaves_the_invite, test_quit_accepts_close_and_closes_the_invite, test_close_without_a_live_invite_quits_without_a_dialog | test_keep_open_ignores_close_and_leaves_the_invite at tests/test_sync_close_invite.py:77 |
| 6 | DONE | c0237f7 | test_open_logs_button_opens_the_real_logs_directory, test_open_logs_failure_shows_the_path_without_exception_text | test_open_logs_button_opens_the_real_logs_directory at tests/test_sync_settings_actions.py:45 |
| 7 | DONE | 35e7488 | test_copy_bug_report_has_about_line_and_no_secrets | test_copy_bug_report_has_about_line_and_no_secrets at tests/test_sync_settings_actions.py:96 |
| 8 | DONE | 5820ee7 | test_double_click_opens_an_existing_folder, test_context_menu_open_folder_uses_the_same_path, test_missing_folder_shows_a_banner_and_does_not_crash | test_missing_folder_shows_a_banner_and_does_not_crash at tests/test_sync_open_folder.py:89 |
| 9 | DONE | 774ddcf | test_current_release_notes_match_the_template_shape, test_placeholder_and_sixth_bullet_are_rejected | test_placeholder_and_sixth_bullet_are_rejected at tests/test_release_notes.py:81 |
| 10 | DONE | ea39bd1 | test_trouble_section_names_shipped_recovery_in_at_most_eight_lines | test_trouble_section_names_shipped_recovery_in_at_most_eight_lines at tests/test_tester_trouble.py:21 |
| 11 | DONE | 75bda50 | test_geometry_round_trips_across_two_windows, test_offscreen_geometry_falls_back_to_the_default_size, test_corrupt_geometry_file_uses_the_default_size | test_geometry_round_trips_across_two_windows at tests/test_sync_window_geometry.py:40 |

## Decisions

[`docs/ops/AUTONOMOUS-DECISIONS-v0.1.6.md`](ops/AUTONOMOUS-DECISIONS-v0.1.6.md)

## Not verified

- No Android SDK. Android `versionName` was left unchanged.
- Qt ran offscreen only (`QT_QPA_PLATFORM=offscreen`).
- No live two-machine friendnet test.

## Suggested PR

Title: Leasegrid Sync v0.1.6: one window, invite close, logs, and folder open

One Sync window per home. Closing during an invite asks first.
Settings can open the logs folder and copy a bug report with no invite or join link.
Double-click a folder to open it. The window remembers its size and place.
Quit reaps Tahoe and Magic Folder, and sync-ui.log rotates past 1 MiB.
ci-local from a linked worktree no longer retargets another venv. Rebased onto v0.1.5.

## Fix round after Tester FAIL @ bd7b09e

Tester failed PR #73 at `bd7b09e`. Reviewer passed. Items 1–9 are DONE. None skipped.
Final ci-local: 484 passed, 5 xfailed. GHA at `9230bd5`: ubuntu/macOS test green; windows-2022 475 passed, 9 skipped, 5 xfailed.
Windows CI fix (`9230bd5`): the two item-2 tests asserted width 700/500, but the layout's minimum width on windows-2022 is 863 px, so Qt clamped the size before saving. They now compare with the width actually saved. No skip; the on-screen rule applies on Windows. The unconditional-`move()` mutation is still RED.
Corrected geometry claim: a saved frame that cannot be decoded, is out of range, or raises while it is applied (including a one-bit sign flip of frame-left) leaves the default size. The window still opens. "Any parse failure keeps the default" was false for that flip: QRect raised OverflowError and the process never started.
Head is the commit that last edits this file (`v0.1.6 fixes: handoff counts after Windows CI fix`).

| # | Status | Commit | Tests | RED without fix |
|---|--------|--------|-------|-----------------|
| 1 | DONE | e6f6ec4 | test_empty_lock_older_than_stale_time_is_recovered, test_garbage_lock_older_than_stale_time_is_recovered, test_foreign_host_lock_older_than_stale_time_is_recovered, test_live_app_refuses_a_second_launch_and_releases_on_quit | tests/test_sync_instance_lock.py:330 (drop `_INSTANCE_LOCK = lock`); :209 (`setStaleLockTime(0)` restored) |
| 2 | DONE | a4f02ab | test_title_bar_above_the_screen_stays_on_screen, test_title_bar_left_of_the_screen_stays_on_screen | tests/test_sync_window_geometry.py:104 and :117 (unconditional `move()` restored) |
| 3 | DONE | 295bd98 | test_quit_stops_tahoe_and_magic_folder | tests/test_sync_stop_reap.py:89 (`shutdown()` never calls `stop()`) |
| 4 | DONE | 162f6ff | test_rotation_leaves_a_short_live_file_and_the_old_bytes_once | tests/test_sync_ui_log.py:64 (copy instead of `os.replace`) |
| 5 | DONE | 09bac50 | test_tray_quit_keep_open_leaves_the_invite_running, test_tray_quit_with_no_invite_quits | tests/test_sync_close_invite.py:125 (tray Quit connected straight to `quit()`) |
| 6 | DONE | f80cbd0 | test_a_file_path_never_reaches_open_url | tests/test_sync_open_folder.py:91 (`exists()` instead of `is_dir()`) |
| 7 | DONE | 84975c9 | test_deeply_nested_geometry_file_uses_the_default_size, test_failed_geometry_replace_keeps_the_previous_file | tests/test_sync_window_geometry.py:127 (`RecursionError` escapes) and :154 (direct write) |
| 8 | DONE | 4fac7da | test_scrub_bug_report_removes_each_secret_shape, test_bug_report_omits_secrets_planted_in_logs_and_env | tests/test_sync_settings_actions.py:93 and :126 (scrub returns the text unchanged) |
| 9 | DONE | 1613d0d | docs only; test_trouble_section_names_shipped_recovery_in_at_most_eight_lines still passes | no behavior mutation |

### v0.1.7 follow-ups

- Signal handlers (SIGTERM, SIGINT, SIGHUP call quit) and a process-group kill of daemon grandchildren.
- Rotate `tahoe.log` and `magic-folder.log`.
- The `--join <invite>` second-launch case.
- A design doc for the v0.1.6 UI additions.
- Import `ALREADY_RUNNING` and `INVITE_CLOSE_QUESTION` into the tester-guide test (10c/10d).
- 11e is closed: Tester at `8a70dd3` shows that skipping the frame pre-check is RED (`35c3b90`).
- Qt treats a fresh lock from another host as stale after about 30 seconds, so a shared Sync home can refuse a launch for that long.
- A live lock held by another host is taken over after about 30 seconds.

## Fix round 2 after Tester FAIL @ 3455c8f

Tester failed PR #73 at `3455c8f`. Reviewer had passed. B1 and B2 stayed fixed. B3 and B4 are fixed. Items 1–6 are DONE. None skipped.
Final ci-local: 496 passed, 5 xfailed, 4 warnings in 43.72s.
Corrected B3 claim: a saved geometry that cannot be decoded, is out of range, or raises while it is applied leaves the default size, and the window still opens. The check covers the whole saved file: a version-2 record of x, y, width, height, and maximized, including a one-bit sign flip of frame-left and a frame of `(0, 0, 2^31-1, 2^31-1)`. An old geometry blob is ignored. A missing file is not an error and is not logged. The old sentence "Any parse failure keeps the default" was false for the sign flip: `QRect` raised `OverflowError` and the process never started.
Last behavior commit: `1e4cf0b`. Head is the commit that last edits this file (`v0.1.6 fix2: handoff`).

| # | Status | Commit | Tests | RED without fix |
|---|--------|--------|-------|-----------------|
| 1 | DONE | cd99d36 | test_saved_frame_rejects_a_sign_flipped_left, test_sign_flipped_frame_opens_at_the_default_size, test_max_int_frame_opens_at_the_default_size, test_sign_flipped_geometry_launches_the_real_app, test_partial_geometry_restore_keeps_the_default_size | :267 drop range check (window tests stayed green). :301 drop the outer try (corrupt JSON and deep nesting too) |
| 2 | DONE | 6a79024 | test_bug_report_omits_secrets_planted_in_logs_and_env | :165 for 7c', 7d', 7f', 7g', 7e', and 7h'. 7e' also test_copy_bug_report_has_about_line_and_no_secrets at :236 |
| 3 | DONE | 977c56b | test_title_bar_partly_off_the_left_edge_stays_on_screen | :160 (`contains` → `intersects`; the fully-off cases stayed green) |
| 4 | DONE | 35c3b90 | the three title-bar tests, width 1000 | :126, :140, :159 (skip restore, `920 == 1000`). :121 if the request is the 920 default |
| 5 | DONE | 8fae733 | test_failed_geometry_replace_keeps_the_previous_file | :197 (no `tmp.unlink()`) |
| 6 | DONE | 1e4cf0b | test_scrub_bug_report_code_boundaries | :86 and :84 (old whitespace regex). :86 (drop `IGNORECASE`, caps only) |

## Fix round 3 after Tester FAIL @ 8a70dd3 (B5)

Tester failed PR #73 at `8a70dd3` on B5. Reviewer had passed. A saved window is a version-2 record, and `restoreGeometry` is not called. Items 1–3 are DONE. None skipped.
Final ci-local: 517 passed, 5 xfailed (516 + the fitter-alone test added after the Build run).
Independent check by Grok Bot after the run: own fuzz, 1424 cases (every bit and 0x00/0xFF byte of a real old blob, every bit of a record, per-field extremes and type swaps, NaN/Infinity, maximized, 16777215 both sides, 100k nesting), one subprocess per 60 cases. Offscreen: 1424/1424 ok, 0 crashes, 0 exceptions, 0 title-bar misses, largest 924x951 (= the no-file default). xcb (xvfb-run, 1920x1080): 1424/1424 ok, largest 920x826. Bit 470 and 0xFF at byte 54 open at the default on both.
Mutations re-run by Grok Bot, each RED: each of x / y / width / height range, maximized-bool, bool-as-int, float, guard off (with the fitter keeping the size), old blob fed back to `restoreGeometry` (pytest dies), fitter off (with the guard off), scrub wordlist off, scrub dot boundary off.
Fuzz, 1534 cases (old-blob bit flips plus record extremes), in subprocess chunks: offscreen 0 crashes, 0 title-bar misses, 0 larger than the no-file control (920×947), 0 sides ≥ 10000. xcb under `xvfb-run -a` at 1920×1080: 0 crashes, 0 title-bar misses, 0 larger than the screen union, 0 sides ≥ 10000.
Last behavior commit: `747c824`. Head is the commit that last edits this file (`v0.1.6 fix3: handoff`).

| # | Status | Commit | Tests | RED without fix |
|---|--------|--------|-------|-----------------|
| 1 | DONE | 0a987e8 | test_corrupt_old_blob_launches_the_real_app, test_window_record_rejects_one_bad_field, test_oversized_record_uses_the_default_size, test_guard_resets_a_size_the_fitter_let_through | drop each of the bool, int, x, y, width, height, and maximized checks (its own case). `restoreGeometry` on an old blob: BEFORE_SHOW height 16777215, and the in-process test SIGSEGV. Drop the guard while the fitter is bypassed: SIGSEGV. The oversized-record tests stayed green on the fitter alone. |
| 2 | DONE | 747c824 | test_scrub_bug_report_code_boundaries | drop the wordlist: `404-not-found`, `1-way-sync`, `3-day-trip`, `500-from-server-side`. Drop the dot: `v0.1.6-guitarist-revenge`. `v0.1.6-rc-final` stayed green on each single drop. |
| 3 | DONE | 03397d7 | docs/HANDOFF-v0.1.6.md (the 11e line and the B3 claim) | docs only; no behavior mutation |
