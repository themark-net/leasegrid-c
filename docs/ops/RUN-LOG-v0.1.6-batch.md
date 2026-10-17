# Run log — Leasegrid Sync v0.1.6 batch

Worktree: `/home/mark/DEVELOP/leasegrid-c/tmp/v016-batch`
Branch: `build/v0.1.6-batch`
Base: `ef174345aede2ef686a890cac1cd7edb75e4cae3` (v0.1.4, `origin/main`)
Started: 2026-10-17T00:32:00-07:00
Interpreter: `.venv/bin/python` (3.14.4)

Do not edit `packaging/tahoe-log-filter.sh`, `tests/test_tahoe_log_filter.py`, or #30 wording. v0.1.5 lives on `origin/build/release-0.1.5` (`0dd01e2`) and will be the rebase target later.

## Plan

Overview: Eleven local Sync fixes on one branch, each with a failure-mode test and a red-without-fix proof, then a 0.1.6 bump, release notes, and handoff. No PR.

Phases:

- baseline | docs/ops/RUN-LOG-v0.1.6-batch.md, docs/ops/AUTONOMOUS-DECISIONS-v0.1.6.md | ci-local recorded | none | lead
- item 1 ci-local worktree | scripts/ci-local.sh, tests/test_ci_local_worktree.py, AGENTS.md | print-python worktree test | baseline | lead
- item 2 reap children | src/leasegrid_sync/backend.py, tests/test_sync_backend.py | real SIGTERM-ignoring child is reaped | baseline | lead
- item 3 log rotate | src/leasegrid_sync/app.py, tests, docs/TESTER-GUIDE.md | rotate, one backup, failure still appends | baseline | lead
- item 4 single instance | cli/app lock, tests | second home refused, other home ok, stale recovered | baseline | lead
- item 5 invite close | app.py _on_close, tests | Quit vs Keep open vs no session | item 4 if same close path | lead
- item 6 open logs | settings tab, tests | button opens logs path; failure shows path | baseline | lead
- item 7 bug report copy | settings tab, tests, TESTER-GUIDE | clipboard has no furl or invite | item 6 status label | lead
- item 8 open folder | folder table, tests | existing path opens; missing path banners | baseline | lead
- item 9 release notes test | tests/test_release_notes.py | green on v0.1.4; red on temp bad notes | baseline | lead
- item 10 tester section | docs/TESTER-GUIDE.md, docs/TESTERS.md | ≤8 bullets, tester page tests green | items 4–8 | lead
- item 11 geometry | app.py, tests | round-trip; corrupt ignored | baseline | lead
- finish | version, release notes, handoff | ci-local green, pushed | all items | lead

Risks:

- Red proof of item 1 must not `pip install` into `/home/mark/tahoe-venv` — the test blocks `pip install` with a bash DEBUG trap.
- v0.1.5 already edits README, TESTERS, TESTER-GUIDE, test_sync_ui.py, test_tester_pages.py — keep those hunks small.
- Qt offscreen only. No Android SDK. No live two-machine run.

## Baseline

Command: `PYTHON=$PWD/.venv/bin/python bash scripts/ci-local.sh`
Result: PASS
Counts: 406 passed, 1 xfailed, 4 warnings in 39.71s
Failing tests: none

## Items

| # | Status | Commit | Tests | RED without fix |
|---|--------|--------|-------|-----------------|
| 1 | DONE | 7a12515 | test_linked_worktree_uses_its_own_venv, test_explicit_python_is_honored_in_a_worktree, test_main_checkout_still_prefers_shared_venv | RED without fix: test_linked_worktree_uses_its_own_venv at tests/test_ci_local_worktree.py:79 (old script selected /home/mark/tahoe-venv and reached pip install) |
| 2 | DONE | 0792361 | test_stop_reaps_child_that_ignores_sigterm, test_stop_is_safe_when_the_child_already_exited | RED without fix: test_stop_reaps_child_that_ignores_sigterm at tests/test_sync_stop_reap.py:59 (TypeError: stop() got an unexpected keyword argument 'terminate_timeout') |
| 3 | DONE | a4c4b2e | test_log_rotates_when_over_one_mebibyte_and_keeps_one_backup, test_rotation_failure_still_appends_and_does_not_raise | RED without fix: test_log_rotates_when_over_one_mebibyte_and_keeps_one_backup at tests/test_sync_ui_log.py:32 (no sync-ui.log.1) |
| 4 | DONE | d9045e1 | test_second_instance_on_the_same_home_starts_no_window, test_a_different_sync_home_is_not_blocked, test_stale_lock_from_a_killed_process_is_recovered, test_status_cli_is_not_blocked_by_the_home_lock | RED without fix: test_second_instance_on_the_same_home_starts_no_window at tests/test_sync_instance_lock.py:80 (MainWindow was constructed) |
| 5 | DONE | 9e17bbb | test_keep_open_ignores_close_and_leaves_the_invite, test_quit_accepts_close_and_closes_the_invite, test_close_without_a_live_invite_quits_without_a_dialog | RED without fix: test_keep_open_ignores_close_and_leaves_the_invite at tests/test_sync_close_invite.py:77 (quit ran with no prompt) |
| 6 | DONE | c0237f7 | test_open_logs_button_opens_the_real_logs_directory, test_open_logs_failure_shows_the_path_without_exception_text | RED without fix: test_open_logs_button_opens_the_real_logs_directory at tests/test_sync_settings_actions.py:45 (logs directory was not created) |
| 7 | DONE | 35e7488 | test_copy_bug_report_has_about_line_and_no_secrets | RED without fix: test_copy_bug_report_has_about_line_and_no_secrets at tests/test_sync_settings_actions.py:96 (clipboard stayed STALE) |
| 8 | DONE | 5820ee7 | test_double_click_opens_an_existing_folder, test_context_menu_open_folder_uses_the_same_path, test_missing_folder_shows_a_banner_and_does_not_crash | RED without fix: test_missing_folder_shows_a_banner_and_does_not_crash at tests/test_sync_open_folder.py:89 (openUrl ran for a missing path) |
| 9 | DONE | (this commit) | test_current_release_notes_match_the_template_shape, test_placeholder_and_sixth_bullet_are_rejected | RED without fix: test_placeholder_and_sixth_bullet_are_rejected at tests/test_release_notes.py:81 (checker returned no problems) |
| 10 | pending | | | |
| 11 | pending | | | |

## Finish

Not started.
