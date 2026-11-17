# Handoff: #85 recovery picker next line pins

Branch `bot/85-picker-pins` off `main` `afb33b3`. Issue [#85](https://github.com/themark-net/leasegrid-c/issues/85), last box.

## What changed

Three source pins in `tests/test_android_invite_copy.py`, one per recovery picker failure in `android/app/src/main/java/net/themark/leasegrid/sync/MainActivity.kt`:

- `test_recovery_picker_no_file_chosen_says_what_to_pick_and_retries_the_picker`: the empty picker result in `pickRecovery` shows "No file was chosen." with "choose a *.leasegrid-recovery file; Retry.", goes to Import first, and Retry reopens the picker.
- `test_recovery_handoff_load_failure_uses_the_loader_copy_or_the_path_next_line`: `readRecoveryFile` uses the loader banner and next, else "check the path and storage permission; Retry."; a rejected file reopens the picker.
- `test_recovery_read_failure_shows_the_path_next_line_and_logs_only_the_class`: `readRecovery` shows the path next line on a thrown read, the import card on TooLarge, and the exception class only in `Log.w`.

Each test also checks that no exception class or message reaches a `reportFail` call and that the block passes the banned word scan.

## How it was checked

Each test failed on a hand mutation of its site (next line replaced, class name put on the next line) and passed on the real file. Full pytest and ruff ran locally. CI: branch `feat/85-picker-pins` first, then `main`.

## #85 decisions

- E5 (a banned word split across variables) is closed as won't fix by PM: the existing copy guards cover the realistic cases. Reopen if a split string banned word ever ships.
- No app code changed. No release, tag or version bump.
