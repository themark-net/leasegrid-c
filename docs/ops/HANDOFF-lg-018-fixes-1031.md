# Handoff: lg-018-fixes-1031 (2026-10-31)

Lane for the v0.1.8 known-fix list. Branch `bot/lg-018-fixes-1031`. Base `origin/main` @ `7ce0785` (v0.1.9). No release, no tag, no version bump, no PR, no merge.

Run log: [`RUN-LOG-lg-018-fixes-1031.md`](RUN-LOG-lg-018-fixes-1031.md). Decisions: [`AUTONOMOUS-DECISIONS-lg-018-fixes-1031.md`](AUTONOMOUS-DECISIONS-lg-018-fixes-1031.md).

Exit: lane empty. The sourced rows are fixed, parked, or need signing keys. The deferred rows that had a written behavior are fixed or were already on origin/main. What is left needs a design, Windows, or Mark.

Resume 2026-10-31 20:23 PT: the same lists were read again (HANDOFF-v0.1.8 Reviewer B1, v0.1.8 and v0.1.9 Known issues, HANDOFF-v0.1.9, and the v0.1.7 "Deferred to v0.1.8" list). No new row is code or docs, autonomous, and specified. `nice -n 19 .venv/bin/python -m pytest tests/test_tester_pages.py tests/test_sync_early_signal.py tests/test_sync_already_running.py tests/test_sync_signal_quit.py tests/test_sync_instance_lock.py` returned 48 passed in 84.30s. Pregate not run: host busy. `pgrep -f 'Runner[.]Worker'` was not empty, and the heavy lock was held.

## Item table

| Item | Source | Status at origin/main | Fix SHA | Test |
| --- | --- | --- | --- | --- |
| B1 (b): signal exit is Linux and macOS, and the notes say "instead of being killed by the signal" | HANDOFF-v0.1.8 Reviewer B1 | fixed in CHANGELOG 0.1.8 and `docs/release-notes/v0.1.8.md`. Current tester pages link those notes | none | already on main |
| B1 (a): re-handing the invite already in the Join field drops the older pending replacement; a replacement still needs Yes, then Join friendnet | HANDOFF-v0.1.8 Reviewer B1 | fixed in CHANGELOG 0.1.8 | none | already on main |
| Add folder can return Magic Folder HTTP 500 | v0.1.8 Known issues, issue #30 | parked. Not changed | none | record only |
| Unsigned installers; Gatekeeper, SmartScreen, and Smart App Control | v0.1.8 Known issues (repeated in v0.1.9) | still open | none | skipped: needs signing keys and Mark |
| v0.1.9 rows #77, #78, #80 | HANDOFF-v0.1.9 | not this lane. They are Android follow-ups of v0.1.9 | none | not taken |
| Caveat guard misses "Coming soon", "available shortly after release", "may not work until CI publishes them" | HANDOFF-v0.1.7 v0.1.8 candidates, from the v0.1.5 follow-up | open | `ac488a1` | `tests/test_tester_pages.py` (22 passed) |
| Signal in the first ~0.1 s of startup | HANDOFF-v0.1.7 deferred to v0.1.8 | open. The quit handler was installed only at the Qt loop | `73e92d9` | `tests/test_sync_early_signal.py` |
| Cross-host lock taken after 2 s instead of 30 s | HANDOFF-v0.1.7 deferred to v0.1.8 | fixed. `setStaleLockTime(2000)` already covers it. Probe: a 5-second-old other-host lock was taken in 0.001 s | none | existing `test_foreign_host_lock_older_than_stale_time_is_recovered`. No new test |
| Lock path is a directory or mode 000 | HANDOFF-v0.1.7 deferred to v0.1.8 | open. Both shapes returned already-running in about 0.1 s and never recovered | `acee332` | `test_old_empty_lock_directory_is_replaced`, `test_old_mode_000_lock_is_replaced_and_a_young_one_is_not` |
| Second `--join` while an invite is being typed | HANDOFF-v0.1.7 v0.1.8 candidates | fixed in v0.1.7. Yes/No, default No, typed text kept | none | `test_handed_invite_keeps_typed_text_unless_the_user_says_yes` |

## Skipped, and why

- Issue #30: the drop-in says parked. Record only.
- Unsigned installers: signing keys and Mark. The known-issue sentence stays.
- Windows pipe-owner check (`GetNamedPipeServerProcessId`): this host cannot run that API. The v0.1.7 design says the lock plus the user-only pipe ACL is the defense.
- Log-filter floors, other separators, percent-encoded and JSON-escaped base64, secrets split across a wrapped line: the short-fragment note says a lower floor eats ordinary words. See the OQ draft below.
- Underscore-joined lowercase+digit fragments: `test_digit_underscore_tokens_leak_no_worse_than_base` pins the current leak count (46/300 on this seed). Closing it needs a new redaction rule. OQ below.
- Base32-last ordering: the v0.1.5 handoff records it as an equivalent mutant, not a leak.
- Adopting an orphaned Tahoe, size-based rotation of daemon logs while the daemon is running, and a further cross-user check: no written behavior. OQ below.

## How the changes fail, and how they recover

Caveat guard (`ac488a1`, test-only). A tester page can grow a "links are not ready yet" sentence that avoids the old keywords ("Coming soon", "available shortly after release", "may not work until CI publishes them") and the guard stays green. The new patterns make `caveat_hits` non-empty for those sentences, so `test_tester_page_has_no_resolve_once_tagged_caveat` fails if a live page uses them. Before the patterns, the three new cases failed and the old seven passed. After, 22 passed. The live README, TESTERS page, and tester guide do not use the phrases. A wording that avoids these words can still pass. The guard comment says so.

Early signal (`73e92d9`, runtime). SIGTERM before `_install_signal_quit` killed the process with exit -15 and left `.leasegrid-sync.lock`, so the next launch said already running. The process now sets a flag, drops the lock, and returns 0 without writing the Qt-loop ready file. RED before the handler: `test_signal_during_early_startup_exits_0_and_drops_the_lock` saw exit -15. GREEN after: that test passed in 0.20 s. Regression: `tests/test_sync_already_running.py`, `tests/test_sync_signal_quit.py`, and `tests/test_sync_instance_lock.py` together, 23 passed in 88 s. Windows is skipped: SIGTERM there is TerminateProcess and cannot run a handler.

Unusable lock path (`acee332`, runtime). A directory, or a mode 000 file, at `.leasegrid-sync.lock` made every launch say already running. Past the same 2 s gate as a PID-less lock, an empty directory we own, or a mode 000 file we own, is removed and the launch proceeds. A non-empty directory is left, and the launch still refuses. A young mode 000 file is left, so a starter that is still writing is not deleted. A path owned by someone else is left. RED before the clear: both new tests failed because `_run_modes` was not called. GREEN after: those two tests plus the fresh-empty, aged-empty, and foreign-host tests, 5 passed. Mode 000 is skipped on Windows, where that mode does not hide a file from its owner.

## Test evidence

- `nice -n 19 .venv/bin/python -m pytest tests/test_tester_pages.py`: 22 passed.
- `nice -n 19 .venv/bin/python -m pytest tests/test_sync_early_signal.py`: 1 passed. Before the handler: 1 failed, exit -15.
- `nice -n 19 .venv/bin/python -m pytest tests/test_sync_already_running.py tests/test_sync_signal_quit.py tests/test_sync_instance_lock.py`: 23 passed.
- `nice -n 19 .venv/bin/python -m pytest` on the two new lock tests plus three neighbors: 5 passed. Before the clear: 2 failed, `_run_modes` call count 0.
- `ruff check` on the touched Python files: passed.
- Pregate not run: host busy. `pgrep -f 'Runner[.]Worker'` was not empty, so `scripts/ci-local.sh` was not started.

## OQ drafts (not filed)

1. Log filter: which shapes below the current floors (base32 under 20, hex under 32, mixed-case under 32, base64url under 40), which separators besides "-" and space, and percent-encoded or JSON-escaped `\/` base64, should be redacted without eating module names and paths? The short-fragment xfail is the current decision.
2. Digit and underscore tokens: is a leak bound (this seed, 46 of 300) acceptable, or is there a rule that redacts secret-like fragments without blanking long snake_case names? Widening the snake_case protector to digits was already measured as worse.
3. Orphan Tahoe: after a crash, should the next launch adopt the leftover `tahoe run`, or stop it and start a new one?
4. Daemon logs while the process is running: `rotate_log` renames the file at start. A running daemon keeps the old inode. Rotation while it runs needs the daemon to reopen the log. Who signals it?
5. Cross-user: the socket directory and socket already refuse a wrong uid. What other path should refuse a different user, and what should the window say?

## Cross-lane requests

None. No file outside this worktree was edited.

## Gate

- `ac488a1` is test-only: pregate plus Reviewer. Pregate did not run (host busy).
- `73e92d9` and `acee332` are runtime: Tester plus Reviewer.

## Next step

Review `73e92d9` and `acee332` with Tester and Reviewer. Review `ac488a1` with Reviewer after a pregate, once `Runner.Worker` is idle. Do not merge this branch from here. Do not start issue #30, installer signing, or the OQ drafts above without a written behavior.
