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
