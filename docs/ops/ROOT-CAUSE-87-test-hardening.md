# Root cause, #87 test hardening

Follow-ups from #86 ([`ops/ROOT-CAUSE-86-xos-pytest.md`](ROOT-CAUSE-86-xos-pytest.md)). Written before the fix. The red-to-green section records the runs.

Code items only. The docs-policy item stays with the CEO. Version strings, changelog, tester pages, release notes, installer workflows, and `docs/PENDING-HANDOFF.md` are not part of this change.

## 1. Loopback skip on Linux (reviewer mutant M3)

Problem: `tests/test_storage_listen.py` skips `test_loopback_storage_override_listens_on_that_address_only` whenever `_can_bind_loopback_alias()` is false. A probe hardcoded to `return False` skips the test on every OS, including Linux, where `lo` has `127.0.0.0/8` and the bind works. The skip is silent in CI because pytest is invoked as `python -m pytest -q` (item 5).

Hypothesis: the #86 probe is the right check on macOS (`lo0` has only `127.0.0.1` unless an alias is added; this repo does not add one). It is the wrong check as a blanket skip. On Linux a failed probe is a real failure of the listen test, not a missing address.

Evidence, before any edit, on this Linux host: `socket.bind(("127.0.0.2", 0))` succeeds. Forcing `_can_bind_loopback_alias` to return False makes the current skip expression `not _can_bind_loopback_alias()` True, so the test would be skipped. `sys.platform` is `linux`.

Chosen fix: test. `loopback_listen_skip_reason(platform)` returns a reason only when the probe fails and the platform does not start with `linux`. Linux returns None, so the listen test runs and fails if `127.0.0.2` cannot be bound. darwin and win32 still skip, with the same reason as #86. The decorator calls that helper. Two tests lock it: on Linux the real probe is True and the collected skip condition is False; with the probe monkeypatched to False, Linux is not skipped and darwin (and win32) is skipped with a reason that names `127.0.0.2` and the alias.

Kind: test fix.

## 2. Lock file permission on Windows

Problem: `test_lock_file_mode_000_names_the_next_step` is skipped on win32. `chmod(0)` only sets the read-only attribute, so `_lock_path_problem` does not see mode 000 and the launch takes the already-running path (#86 W2). An ACL that actually denies read has the same hole: `st_mode` on Windows does not carry the DACL.

Hypothesis: a small product check is correct and keeps POSIX behaviour. Mode 000 stays the check it is (root can read a mode-000 file, so PermissionError alone would miss it). A `PermissionError` from opening the lock for read is the same user-facing problem: "could not read its lock file", with the same next step. A live second instance is not that case. Qt's Windows `QLockFile` opens the lock with `FILE_SHARE_READ`, so a reader still succeeds while the other process holds it, and the existing tryLock path still says already running. `_other_host_lock_is_young` swallows `OSError` and returns False, so a read error there does not name the next step. The check belongs in `_lock_path_problem`, before that call, and only for `PermissionError`.

Evidence: `_lock_path_problem` (`src/leasegrid_sync/app.py`) stats the path, returns the directory sentence, and returns the unreadable sentence only when `(st_mode & 0o777) == 0`. It does not mention `PermissionError`. Python's `os.chmod` on Windows sets only the read-only flag. Python's `PermissionError` is the `OSError` subclass for `EACCES` / `EPERM` (filesystem permissions). On Windows, `OSError.winerror` holds the native code and `errno` is the POSIX approximation, so `isinstance(exc, PermissionError)` is the check that already matches an access denial.

Not chosen: treating `QLockFile.LockFailedError` as a permission problem. Qt maps `ERROR_ACCESS_DENIED` on an existing file to `LockFailedError`, which this app already uses for "already running". Reclassifying that would mis-report a second instance. Not chosen: an xfail. The read check is the same sentence mode 000 already promises.

Chosen fix: product, plus tests. After the mode-000 return, open the regular file and read one byte. `PermissionError` returns the same `_LOCK_UNREADABLE` pair. Mode 000 still returns before open. `FileNotFoundError` returns None: `QLockFile` may unlink a stale lock between stat and open, and that path is usable. Tests: a Linux (every OS) launch with `builtins.open` of that lock raising `PermissionError` expects the next-step copy; a direct call with `st_mode` forced to `S_IFREG` (mode 000) expects that copy and expects open not to be called; a win32 test denies `(R)` with `icacls` and expects the same copy. `icacls /reset` runs in `finally`. An explicit deny outranks an inherited allow, so `/inheritance:r` is not used. `test_six_callers_never_double_hold` is the race check.

Kind: product fix plus test.

## 3. Download permission on Windows

Problem: `test_download_permission_denied_does_not_say_network` is skipped on win32. `chmod(0o555)` on a directory does not stop Windows creating a file in it (#86 W4). The phone is Android, which is POSIX. The copy is not checked on Windows.

Hypothesis: `leasegrid_read.dispatch` already maps `PermissionError` from `open(dest, "wb")` to "would not allow" / "check storage permission". No product change. Windows needs a denial that really raises `PermissionError`: `icacls <dir> /deny %USERNAME%:(OI)(CI)(W)`. `(OI)(CI)(W)` applies write denial to the directory (creating `dest` needs that) and to children. The chmod test stays the POSIX proof.

Evidence: `dispatch` catches `OSError` and uses `_permission_copy` only for `PermissionError`. The chmod test is the only check of "would not allow" for download, and it skips on win32. There is no monkeypatched `PermissionError` test, so a Windows run never executes that branch.

Chosen fix: test. A win32 test denies `(OI)(CI)(W)` on the destination directory, restores with `icacls /reset` in `finally`, and asserts the same copy as the chmod test (not network, not free space, file not created). A platform-independent test monkeypatches `leasegrid_read.open` so a write of that dest raises `PermissionError` and asserts the same copy. That runs on every OS, including Windows if `icacls` is not what fails.

Kind: test fix. No product change.

## 4. Put permission on Windows

Problem: `test_put_permission_denied_does_not_say_pick_it_again` is skipped on win32. `chmod(0)` does not deny the owner read, so `_put` reads the bytes and the fake server fails as a network error (#86 W5).

Hypothesis: same as item 3. `_put` already turns `PermissionError` from `open(path, "rb")` into the "would not allow" `WriteFail`, and does not say "pick it again". `icacls <file> /deny %USERNAME%:(R)` is the denial that raises `PermissionError` on read. No product change.

Evidence: `_put` checks `isinstance(exc, PermissionError)` after `open`. The chmod test is the only check, and it skips on win32.

Chosen fix: test. A win32 test denies `(R)` on the source file and asserts the permission copy. A platform-independent test monkeypatches `open` of that path in read mode to raise `PermissionError` and asserts the same copy.

Kind: test fix. No product change.

## 5. CI skip reasons

Problem: `.github/workflows/ci.yml` runs `python -m pytest -q`. Skipped tests do not print their reasons, so a silent skip (item 1) is invisible in the log.

Hypothesis: `-rs` prints the skip reason for each skipped test and does not change pass/fail.

Chosen fix: that one line becomes `python -m pytest -q -rs`. No other workflow edit.

Kind: CI flag.

## Red to green

Loopback, before the Linux clause. The helper skipped whenever the probe returned False, which is the #86 expression. `test_failed_loopback_probe_skips_only_off_linux` with the probe monkeypatched to False:

```
AssertionError: Linux must not skip when the probe fails ('127.0.0.2 is not assigned on this host (macOS lo0 has only 127.0.0.1 unless an alias is added); refusing to add that alias')
assert '127.0.0.2 is not assigned on this host (macOS lo0 has only 127.0.0.1 unless an alias is added); refusing to add that alias' is None
```

`test_linux_loopback_probe_succeeds_and_the_listen_test_is_not_skipped` passed in that same run: on this host the real probe is True and the collected skip condition is False. After the Linux clause, both meta-tests pass. A failed probe on Linux is not a skip, so the listen test would run and fail.

Lock, before the open check. `test_lock_file_permission_error_names_the_next_step` (`builtins.open` of the lock raises PermissionError) got exit code 0:

```
assert code == 1
E   assert 0 == 1
```

That is the already-running path. `_lock_path_problem` did not see a mode of 000, and `_other_host_lock_is_young` swallows the read error. After the open check, the same test passes: exit code 1, "could not read its lock file", "Next:", and not "already running". `test_mode_000_is_unreadable_without_opening` passed before and after: mode 000 still returns without calling open. `test_lock_file_mode_000_names_the_next_step` still passes.

The first open check also failed `test_six_callers_never_double_hold` on the aged kind. Six processes stat a stale empty lock, one unlinks it, and another's open raised `FileNotFoundError(2, 'No such file or directory')`. That worker exited, so the round never finished. Catching `FileNotFoundError` and treating the path as usable fixes that race. Fifteen aged rounds then had one winner each.

Download and put needed no product change. On Linux the chmod tests still pass. The new monkeypatched PermissionError tests pass. The three `icacls` tests skip on this host with their reasons (`-rs`). Windows CI is what runs them.

Targeted run after the permission copy landed: 10 passed, 3 skipped (the three icacls tests). After the `FileNotFoundError` catch, `test_six_callers_never_double_hold` passed with the three lock copy tests (4 passed). Full Linux suite: 706 passed, 4 skipped, 5 xfailed, 182s. Ruff on `src tests scripts packaging` and on `android/pytests/test_dispatch_copy.py` is clean. The dash check on added lines is empty.
