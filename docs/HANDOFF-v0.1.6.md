# Handoff — Leasegrid Sync v0.1.6

Branch: `build/v0.1.6-batch`
Base: `ef174345aede2ef686a890cac1cd7edb75e4cae3` (v0.1.4, `origin/main`)
Version bump: `fcb994d`. Tip: the commit that adds this file.
Rebase onto v0.1.5 when it lands. Expected conflicts: version/notes files only.

## Tests

Baseline: 406 passed, 1 xfailed, 4 warnings, 39.71s. Failing tests: none.
Final ci-local: PASS, 433 passed, 1 xfailed, 4 warnings, 41.06s.

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
ci-local from a linked worktree no longer retargets another venv. Rebase onto v0.1.5 before review.
