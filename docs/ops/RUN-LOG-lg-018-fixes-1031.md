# Run log: lg-018-fixes-1031

Worktree: `~/DEVELOP/leasegrid-c/tmp/lg-018-fixes-1031`
Branch: `bot/lg-018-fixes-1031`
Base: `origin/main` @ `7ce0785` (v0.1.9, "Release v0.1.9")
Drop-in commit: `5c99573`
Started: 2026-10-31T18:32:00-0700
Deadline: 2026-11-01T02:12:00-0700 (8 hours from start, minus 20 minutes to write the handoff). Sunday 2026-11-01 18:00 PT is later, so the 8 hour cap wins.
Host at start: MemAvailable about 66 GiB, 32 cores, load about 4. Under the pause line.

## LOOP EXIT CARD

```text
LOOP EXIT CARD
Goal: each v0.1.8 known-fix item is fixed on this branch, or recorded as already on origin/main, parked, or skipped with a reason. A code change gets a behavior test, one commit, and a push.
1 Goal met: the handoff item table covers every sourced row, and each new test was red without the fix and green with it.
2 Turn cap: one commit per item. Stop the item after two identical failures.
3 Budget cap: cloud Grok only. No local model. No full suite unless the pregate rule allows it.
4 Wall clock: 2026-11-01T02:12:00-0700 for new items. Handoff after that.
5 No progress: the same failure twice with no new information, or 3 items in a row skipped.
6 Human interrupt: user stop. Do not ask questions.
7 Error threshold: two identical failures on one item, then skip that item.
8 External event: origin/main already has the fix. Record it and do not redo it.
Loop type: goal
Human gate: no merge, no PR, no tag, no release.
```

## Plan

Overview: Collect the v0.1.8 known-fix list, mark what v0.1.9 already closed, and fix only the leftovers that are code or docs, autonomous, and do not need signing keys, a phone, Mark, or an ADR. One commit and one push per fix. Then write the handoff.

Phases:

- exits | docs/ops/RUN-LOG-lg-018-fixes-1031.md | this card is in the log before code changes | none | lead
- inventory | handoff, release notes, later handoffs, HANDOFF-v0.1.7 deferred list | each row is fixed, parked, skip, or open | exits | lead
- fixes | only files the open row needs | targeted tests green, commit, push | inventory | lead
- handoff | docs/ops/HANDOFF-lg-018-fixes-1031.md and this log | final state line, commit, push | fixes | lead

The lead implements the fixes. Items share this worktree and land one at a time. The project-map agent writes only `.project-map/`.

Risks:

- A sourced row that is already on origin/main gets a record, not a second copy.
- Issue #30 stays parked. Unsigned installers need signing keys.
- A deferred row that needs a new redaction rule, a Windows API, or a product choice is an OQ in the handoff, not code.
- Host pressure: MemAvailable under 16 GiB, or load over 64 for 5 minutes, means pause 10 minutes and stop if it persists.
- A test that is already red on the base is recorded and that area is skipped.

## Inventory (against origin/main 7ce0785)

| Item | Source | Status at origin/main |
| --- | --- | --- |
| B1 (b) signal wording: Linux and macOS, "instead of being killed by the signal" | HANDOFF-v0.1.8 Reviewer B1 | fixed in CHANGELOG 0.1.8 and docs/release-notes/v0.1.8.md. Current tester pages link those notes. |
| B1 (a) re-handing the invite already in the Join field drops the older pending replacement; Yes then Join friendnet | HANDOFF-v0.1.8 Reviewer B1 | fixed in CHANGELOG 0.1.8 |
| Add folder Magic Folder HTTP 500 | v0.1.8 Known issues, issue #30 | parked. Record only. |
| Unsigned installers, Gatekeeper, SmartScreen, Smart App Control | v0.1.8 Known issues | open, skipped: needs signing keys and Mark. v0.1.9 notes repeat it. |
| v0.1.9 follow-ups #77, #78, #80 | HANDOFF-v0.1.9 | not this lane. They are Android follow-ups of v0.1.9, not v0.1.8 known fixes. |

Continuation queue (named "Deferred to v0.1.8" / "v0.1.8 candidates" in docs/HANDOFF-v0.1.7.md). v0.1.8 did not ship them. Taken only when the fix is specified and does not need an ADR:

- Caveat guard misses "Coming soon", "available shortly after release", "may not work until CI publishes them". Open. Test-only guard.
- Signal in the first ~0.1 s of startup, before the quit handler is installed. Open. Code.
- Cross-host lock taken after 2 s instead of 30 s. Probe. Fix only if a few-second-old foreign lock still waits.
- Lock path that is a directory or mode 000. Probe. Fix only if it hangs or crashes.
- Second `--join` while an invite is being typed. Already shipped in v0.1.7 (Yes/No, default No). Record fixed after a code check.
- Windows pipe-owner check. Skip: Windows API, design says the client cannot read the pipe owner.
- Underscore-joined lowercase+digit fragments, other log-filter floors and separators, base32-last order. Skip: written design limits, or the leak count is the current contract. OQ.
- Orphan Tahoe adopt, runtime daemon-log rotation, cross-user check. Skip: need a design. OQ.

## Progress

- exits: DONE | tests: not run | files: this log | err: none
- caveat guard missed rewordings | ac488a1 | pytest tests/test_tester_pages.py: 22 passed. RED before the patterns: 3 failed (Coming soon, shortly after release, may not work until CI publishes), 7 passed | result: pass
- signal in the first moment of startup | 73e92d9 | pytest tests/test_sync_early_signal.py: 1 passed. RED before the handler: exit -15. Then pytest tests/test_sync_already_running.py tests/test_sync_signal_quit.py tests/test_sync_instance_lock.py: 23 passed | result: pass
- lock path is a directory or mode 000 | acee332 | pytest the two new tests plus fresh-empty, aged-empty, and foreign-host: 5 passed. RED before the clear: _run_modes call_count 0 on both new tests | result: pass
- foreign-host lock at 2s | none | probe tmp/probe-lock.py: foreign-5s ok=True 0.001s | result: already fixed on origin/main
- state: lane empty | tests: targeted modules above, pregate not run: host busy | files: app.py, test_tester_pages.py, test_sync_early_signal.py, test_sync_instance_lock.py, this log, the decisions file, the handoff | err: none
- resume 2026-10-31T20:23-0700 | none | pytest tests/test_tester_pages.py tests/test_sync_early_signal.py tests/test_sync_already_running.py tests/test_sync_signal_quit.py tests/test_sync_instance_lock.py: 48 passed in 84.30s | result: lane still empty. No new sourced row is code or docs and specified.
- state: lane empty | tests: 48 passed in 84.30s, pregate not run: host busy | files: this log, the handoff, the decisions file | err: none
