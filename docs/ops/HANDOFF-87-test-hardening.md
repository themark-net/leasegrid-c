# Handoff, #87 test hardening

Branch `bot/87-test-hardening` off `origin/main` `0395215`. Local commit only. Not pushed, not tagged, not a release.

## What changed

- `tests/test_storage_listen.py`: the loopback listen test skips only when `loopback_listen_skip_reason` says so. Linux never skips. A probe that cannot bind `127.0.0.2` on Linux runs the listen test, so the test fails instead of disappearing. darwin and win32 still skip when the bind fails, with the same reason as #86 (no alias is added). `test_linux_loopback_probe_succeeds_and_the_listen_test_is_not_skipped` locks the real probe and the collected skip mark on Linux. `test_failed_loopback_probe_skips_only_off_linux` monkeypatches the probe: Linux is not skipped, darwin and win32 are, and the reason names `127.0.0.2` and the alias.
- `src/leasegrid_sync/app.py`: the real order in `acquire_instance_lock` is: `_lock_path_problem` stats the path (no open; a directory or a mode-000 file is refused, and since v0.1.12 any stat error is left to tryLock), then `_other_host_lock_is_young` (stat, and a text read only for a lock younger than 30 seconds), then `tryLock`, the writer grace, a second `tryLock`, the PID check, and only then `_lock_read_state`, which reports "could not read its lock file" only when three reads, 50 ms apart, all raise `PermissionError`. A lock that vanishes during those reads is tried once more. Round 1 opened the file before `tryLock`, which raced Qt's stale-lock delete on Windows: windows-2022 timed out at 89502ee (run 44138425560), see the root-cause note, section 6. `test_transient_permission_error_on_a_stale_lock_still_takes_it` fails the read only once, so it does not pin that order by itself. The order and the retries are pinned by `tests/test_sync_lock_retry_order.py` (v0.1.12, see `docs/ops/HANDOFF-0112-release-prep.md`).
- `tests/test_sync_instance_lock.py`: `test_lock_file_permission_error_names_the_next_step` monkeypatches `open` of the lock and expects that copy on every OS. `test_mode_000_is_unreadable_without_opening` forces mode 000 and expects open not to be called. `test_lock_file_windows_acl_deny_names_the_next_step` denies `(R)` with `icacls` and restores with `icacls /reset`. The chmod(0) test is unchanged and still skipped on win32.
- `android/pytests/test_dispatch_copy.py`: the chmod tests are unchanged. `test_download_permission_error_does_not_say_network` and `test_put_permission_error_does_not_say_pick_it_again` monkeypatch `PermissionError` so the "would not allow" copy runs on every OS. `test_download_windows_acl_deny_does_not_say_network` denies `(OI)(CI)(W)` on the destination directory. `test_put_windows_acl_deny_does_not_say_pick_it_again` denies `(R)` on the source file. Both restore with `icacls /reset`. No change to `leasegrid_read.dispatch`: it already mapped `PermissionError`.
- `.github/workflows/ci.yml`: the pytest line is `python -m pytest -q -rs`. Nothing else in that file.

Root cause: [`ops/ROOT-CAUSE-87-test-hardening.md`](ROOT-CAUSE-87-test-hardening.md). Decisions: [`ops/AUTONOMOUS-DECISIONS-2026-11-17.md`](AUTONOMOUS-DECISIONS-2026-11-17.md).

## How to verify

From this checkout, with a venv made for it. `leasegrid_sync.__file__` must resolve inside this checkout.

```bash
PYTHONPATH=src:. .venv/bin/python -c "import leasegrid_sync; print(leasegrid_sync.__file__)"
QT_QPA_PLATFORM=offscreen PYTHONPATH=src:. .venv/bin/python -m pytest -q
.venv/bin/python -m ruff check src tests scripts packaging
```

CI adds `-rs` so skip reasons are in the log. The import must print a path under this checkout.

## What only CI can confirm

nimo is Linux. These need a push before GitHub Actions can run them:

- windows-2022: the three `icacls` tests (lock read deny, download directory write deny, put file read deny). Python maps an access denial to `PermissionError`. If a runner token can still read or create the file, that test fails rather than skipping.
- windows-2022 and macos-15-intel: the monkeypatched permission copy (lock, download, put) and the loopback decision helper.
- macos-15-intel: `test_loopback_storage_override_listens_on_that_address_only` should skip when `127.0.0.2` is not assigned, and `-rs` should show the alias reason. It must not skip on ubuntu, where the probe succeeds.

Linux on this worktree: 706 passed, 4 skipped, 5 xfailed, 182s. The skips are the live-grid journey (`LEASEGRID_LIVE_GRID` unset) and the three `icacls` tests. Ruff on `src tests scripts packaging` is clean.

## What's left

The docs-policy item stays with the CEO. It was not edited. Version strings, changelog, tester pages, release notes, installer workflows, and `docs/PENDING-HANDOFF.md` were not touched. Not pushed. Not tagged. Not a release.
