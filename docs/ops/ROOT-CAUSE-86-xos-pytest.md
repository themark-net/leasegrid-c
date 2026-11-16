# Root cause, #86 cross-OS pytest

CI run 43796144756, job `test`, base `d3b5c5c`. Logs: `windows-2022-job133065286957` and `macos-15-intel-job133065287012`. Written before the fix. Sections update when a simulation changes the evidence.

## W1 leftover mutant is not restored

Symptom: `tests/test_prove_red.py::test_leftover_mutant_from_sigkill_is_restored` — `AssertionError: assert 'restored leftover mutant' in ''`. Stdout ends with `caught  RED`. Exit code of prove-red was 0 (the return-code assert did not fire).

Hypothesis: two line-ending bugs stack. On Windows, `Path.write_text` writes CRLF, and GitHub's git has `core.autocrlf=true`, so the blob is LF and the working tree is CRLF. The test injects the leftover with `original.replace(b"return 1\n", b"return 2\n")`, which does not match `return 1\r\n`, so the file stays clean. prove-red never enters leftover restore, runs the case itself, and prints RED with empty stderr. Under that, `_exact_leftover` compares `git show` bytes (LF blob, no autocrlf smudge) to the working tree. A real SIGKILL leftover is the CRLF mutant `_mutant_bytes` writes. Those bytes are not equal, so the next run would refuse the file as uncommitted instead of restoring it.

Evidence: `scripts/prove-red.py` `_mutant_bytes` already folds newlines when it applies a mutant, and says so. `_exact_leftover` still uses `current == mutant` on the raw `git show` blob. `tests/test_prove_red.py` line 227 uses the LF needle. `test_crlf_working_tree_matches_lf_pattern` only covers a clean CRLF run, not a leftover.

Chosen fix: product. Compare newline-normalized bytes, and write the restored blob back with the working tree's newline spelling so a CRLF checkout stays CRLF. Test: inject the leftover with the harness's own `_mutant_bytes`, and add a Linux test that commits CRLF under `core.autocrlf=true`.

Kind: product fix plus test.

## W2 mode-000 lock file

Symptom: `tests/test_sync_instance_lock.py::test_lock_file_mode_000_names_the_next_step` — `assert 0 == 1` at the exit code. `MainWindow` was not constructed (`_lock_failure` asserts that before returning).

Hypothesis: POSIX-only. `chmod(0)` on Windows only sets the read-only attribute. `stat.S_IMODE` still has the read bits, so `_lock_path_problem` does not see mode 000. The launch then takes the "already running" path (`acquire_instance_lock` returns false, `run_app` returns 0). The file was not unreadable.

Evidence: `src/leasegrid_sync/app.py` `_lock_path_problem` requires `(st_mode & 0o777) == 0`. Python's Windows `chmod` documents that only the read-only flag is stored. The product check is the right check on POSIX. Treating every read-only lock as mode 000 would mis-report a Windows QLockFile.

Chosen fix: `pytest.mark.skipif(sys.platform == "win32", reason="chmod(0) only sets the Windows read-only attribute; it does not create a mode-000 file or deny the owner read")`.

Kind: platform skip.

## W3 bad Tahoe folder path in the banner

Symptom: `tests/test_sync_ui.py::test_bad_tahoe_folder_names_a_plain_next_step` — `assert str(path) in text` failed. `str(path)` is `C:\Users\runneradmin\AppData\Local\Temp\pytest-of-runneradmin\pytest-0\test_bad_tahoe_folder_names_a_0\empty-tahoe`. The label is `FAIL <char> could not join this friendnet. No Tahoe client is configured at ~\AppData\Local\Temp\pytest-of-runneradmin...tahoe_folder_names_a_0\empty-tahoe.`

Hypothesis: the product is doing what `display_path` / `mask_shown_paths` promise. Windows pytest temp lives under the user profile, so the banner hides the account and shows `~\...`. Linux `/tmp` is outside `$HOME`, so `str(path)` is still in the text and the test passes. The `...` in the log is pytest's assertion ellipsis (the Next line is intact on both sides of it), not a product middle-elision. There is no elision helper. The `<char>` bytes in the log are UTF-8 U+FFFD (`EF BF BD`). The source banner is `FAIL — ` (U+2014, bytes `E2 80 94` in `SyncError.banner`). That is the em dash written to a cp1252 pipe (byte `0x97`) and decoded as invalid UTF-8 when the log was stored. The label still contains `FAIL`, and the same em dash is the product string on every OS. Not an encoding bug in the label.

Evidence: `d3b5c5c` keeps the folder in the sentence and sends it through `banner()` → `mask_shown_paths`. `display_path` documents `~\\…` on Windows. `tests/test_sync_display_path.py` locks the account-hiding behaviour. `app.py` has no middle-elision of paths.

Chosen fix: test. Assert `display_path(path)` (the form the banner promises) and the folder leaf. Do not change the em dash. Linux still requires the shown path, which outside `$HOME` is the absolute path.

Kind: test fix.

## W4 download into a mode-0555 directory

Symptom: `android/pytests/test_dispatch_copy.py::test_download_permission_denied_does_not_say_network` — `assert True is False` on `reply["ok"]`. The write succeeded.

Hypothesis: POSIX-only. `chmod(0o555)` on a directory does not stop Windows from creating a file in it. `leasegrid_read.dispatch` maps `PermissionError` to "would not allow". No `PermissionError` was raised, so the success path ran. The phone is Android, which is Linux permissions. The product check is the right one.

Chosen fix: skip on win32. Reason: chmod(0o555) does not deny creating a file on Windows; this test is the Android (POSIX) permission copy.

Kind: platform skip.

## W5 put of a mode-000 file

Symptom: `android/pytests/test_dispatch_copy.py::test_put_permission_denied_does_not_say_pick_it_again` — `{'ok': False, 'message': 'could not add this file.', 'next': 'check network; Retry.'}`. `would not allow` is absent. The log then shows `fetch_share` network warnings.

Hypothesis: POSIX-only. `chmod(0)` left the file readable, so `_put` read the bytes and the fake servers failed as a network error. The permission copy in `_put` / `_permission_copy` never ran. Same product check as W4.

Chosen fix: skip on win32. Reason: chmod(0) does not deny reading a file on Windows; this test is the Android (POSIX) permission copy.

Kind: platform skip.

## M1 loopback 127.0.0.2

Symptom: `tests/test_storage_listen.py::test_loopback_storage_override_listens_on_that_address_only` — `TimeoutError: timed out` on `sock.connect(("127.0.0.2", port))`. The assertions on `tub.location` and `tub.port` had already passed (`tcp:127.0.0.2` and `interface=127.0.0.2`).

Hypothesis: the config is right. macOS `lo0` has only `127.0.0.1` unless an alias is added. Nothing can accept a connection to `127.0.0.2`, so Tahoe's bind does not become reachable and the connect times out. This is not a product listen bug. windows-2022 did not fail this test (five failures, this is not one of them). Linux `lo` has `127.0.0.0/8`.

Chosen fix: capability probe. Skip when `socket.bind(("127.0.0.2", 0))` raises `OSError`. Reason names the missing loopback address and that we will not add an `ifconfig` alias. Hosts where the bind works, including Windows if it works there today, still run the test.

Kind: platform skip, probe not a blanket darwin skip.

`tests/test_live_grid.py` connects to `127.0.0.2` only inside the live journey, which did not fail on this run. Left as it is.

## M2 Magic Folder orphan never becomes ready

Symptom: `tests/test_sync_orphan.py::test_magic_folder_start_stops_our_orphan_only` — `SyncError: folder not added. Magic Folder daemon did not become ready.` Raised from `MagicFolderCtl.ensure_running` after the 20s loop. That branch runs only while `_leader_state(self._proc) == "running"` and `is_running()` stays false. The sibling `test_start_stops_our_tahoe_orphan_and_spares_another_nodedir` passed on the same macOS job (the failure dot is this test; the next test passed and the relative-path test skipped for lack of `/proc`).

Hypothesis: not `/var` vs `/private/var`, not a ps cmdline miss, and not a slow real daemon. The Tahoe orphan test uses the same sleeper, the same `stop_orphan_for_directory`, and the same kqueue leader check, and it stopped the orphan and reached a ready HTTP stub. The Magic Folder double is different: `_MF` constructs `ThreadingHTTPServer`, whose `server_bind` calls `socket.getfqdn("127.0.0.1")` before the stub writes `api_client_endpoint`. The Tahoe double overrides `server_bind` and sets `server_name` itself, so it never does that lookup. A blocked `getfqdn` leaves the child alive (so the loop does not say "stopped while starting") and never writes the endpoint (so `is_running` stays false) until the 20s budget ends. Real `magic-folder` does not go through this stub. Raising the timeout would not fix a lookup that has not returned.

Evidence to confirm on Linux: a `sitecustomize` that sleeps inside `socket.getfqdn` for `127.0.0.1` makes the current `_MF` miss its endpoint; the Tahoe-style `server_bind` writes the endpoint without calling it. macOS path match is already covered by the passing Tahoe orphan test on this runner (`tmp_path` was already `/private/var/folders/...`).

Chosen fix: test double. Give `_MF` the same `server_bind` override `_TAHOE` has. Regression: spawn the double with `getfqdn` blocked and require `api_client_endpoint` within 2s.

Kind: test fix. Not a product change.

## Red to green

W1, simulated on Linux with `core.autocrlf=true` before the fix. A CRLF working tree of `return 1` does not change under `replace(b"return 1\n", b"return 2\n")` (`changed False`). `git show` is LF. The harness mutant of the working tree is `return 2\r\n`; the mutant of the blob is `return 2\n`. Raw compare is false. Folded compare is true. Writing the LF blob back leaves `git status` dirty (` M mod.py`). Writing the blob with the checkout's CRLF spelling is clean, which is what `git checkout` itself writes. Pytest before the fix: `uncommitted changes in mod.py`, return code 2 (`test_crlf_leftover_mutant_is_restored`). After the fix that test passes, and `test_leftover_mutant_from_sigkill_is_restored` still passes. The Windows CI symptom (empty stderr, `caught RED`) is the step before this: the test's LF replace never created a leftover, so prove-red ran a normal RED case. The test now injects with `_mutant_bytes`, so a CRLF tree gets a real leftover and hits the restore path.

M2, before the stub change: `test_magic_folder_stub_writes_endpoint_without_reverse_dns` failed in 2.09s with `endpoint was not written while getfqdn was blocked`. `socket.getfqdn("127.0.0.1")` slept in the child's `sitecustomize`. After `_MF` overrides `server_bind` the same way `_TAHOE` does, the endpoint file appears inside the 2s budget and the orphan test still passes.

W3: `test_plain_screen_hides_a_folder_inside_the_account_home` puts the folder under a fake home. The banner contains `display_path` and does not contain `str(folder)`.

Semgrep: `tools/semgrep` is in the tree. The `semgrep` binary is not on PATH and not in the shared venv. It was not installed. Scan skipped.

## W3b round 2: the parked-node assertion in the same test

Symptom: after `2e4ce83` was fast-forwarded to main, CI run 43928997775 (job 133516051680, windows-2022) failed only `tests/test_sync_ui.py::test_bad_tahoe_folder_names_a_plain_next_step` at line 766: `assert str(parked) in parked_text`, with the label `A Tahoe node already exists at ~\AppData\Local\Temp\...`. ubuntu, macos-15-intel, debug APK and semgrep were green.

Hypothesis: same cause as W3, a second assertion the first fix missed. Round 1 changed `_assert_plain_screen`, but the parked-node block asserts `str(parked)` inline, and the banner masks the account home there too.

Red to green on Linux: run the test with `HOME=/tmp/lg86home` and `--basetemp=/tmp/lg86home/bt`, so pytest temp sits under the home the way Windows temp sits under the profile. Before: fails at line 766 with `~/bt/.../already-here` in the label. After asserting `display_path(parked)`: `tests/test_sync_ui.py` 92 passed with that HOME, and 92 passed with the normal HOME. The whole suite under the under-home simulation: 700 passed, 1 skipped, 5 xfailed. No other `str(path) in` banner assertion is left in `tests/test_sync_ui.py`.

Kind: test fix.
