# Handoff — dev safety rails

Branch `build/dev-safety-rails`. Implementation head `a80979c` (this file's parent). Compare: https://github.com/themark-net/leasegrid-c/compare/main...build/dev-safety-rails?expand=1

| Item | Status | Commit | ci-local | Mutations |
| --- | --- | --- | --- | --- |
| 1 semgrep + ruff | DONE | `a12f48a` | 581 passed, 5 xfailed | semgrep test, stale lock, S103, fixture: RED |
| 2 systems-safety | DONE | `44a29fb` | 584 passed, 5 xfailed | drop SS3, rename skill, undocumented SS9: RED |
| 3 prove-red | DONE | `57e70cb` | 589 passed, 5 xfailed | no restore, survivor exits 0, dirty check dropped: RED |
| 4 survivors | DONE | `a80979c` | 594 passed, 5 xfailed | r9n, n1i, l5n, latest-wins, sigterm: RED |

Final ci-local at `a80979c`: ruff clean, semgrep 8/8 and 0 findings, pytest 594 passed, 5 xfailed, 4 warnings in 143.32s.

Triage (nothing left as "Found by the new gate"): B904 ×3 fixed with `raise ... from err`. SIM115 noqa on daemon logs that must stay open. Listed S rules: 0 hits. Semgrep suppressed on the capped AF_UNIX client path and on getpgid/getpgrp/killpg/SIGKILL (Windows returns first; killpg only while our unreaped leader still pins the group). S377 omitted; ruff 0.17.1 has no such rule.

R9n needed no `backend.py` change: `start()` already reaps a non-running leader and spawns. App changes: latest hand clears an older pending invite; SIGTERM on the already-running box exits 0.

Prove-red receipt (exit 0, `git diff` clean after):

```
name                      result
skill-ss3-section         RED
r9n-zombie-as-running     RED
n1i-yes-joins             RED
l5n-drop-second-trylock   RED
latest-wins-keep-pending  RED
sigterm-no-handler        RED
```

Grok listed `systems-safety` in this session after the skill file existed (path `.grok/skills/systems-safety/SKILL.md`). A second process was not started. No PR opened. ci-local is Linux only and is not "CI green".

## Fix round 1 (Windows CI on PR #75)

PR #75 at `2f60f4a`: every check passed except `test (windows-2022)` (3 failed, 560 passed). Fix commit `22879c0`, no product code changed.

| Failure | Cause | Fix |
| --- | --- | --- |
| `test_prove_red.py::test_caught_mutant_is_red_and_restores`, `::test_surviving_mutant_exits_1` (PATTERN MISSING) | Windows writes `\r\n`, so the `\n` pattern was not a literal match | `scripts/prove-red.py` normalizes newlines only while matching, writes the mutant as bytes, restores the original bytes; new CRLF test |
| `test_sync_backend.py::test_start_respawns_an_unreaped_exited_leader` (pid mismatch) | CreateProcess can't exec a `.bat`, so `Popen.pid` is `cmd.exe`, not the worker | fake tahoe records worker pid and parent; win32 accepts either (still not the leader); POSIX keeps `client._proc.pid == new_pid` |

ci-local at `22879c0`: ruff clean, semgrep 8/8 and 0 findings, pytest 595 passed, 5 xfailed, 4 warnings in 138.50s. prove-red after the fix: exit 0, all six cases RED, `git diff` clean on targets.

GitHub checks on `22879c0`: `test (windows-2022)` success, and all other test jobs success. The `macos` packaging job failed in `hdiutil: create failed - Resource busy` (runner DMG step, not touched by this round; the same job passed at `2f60f4a`). The checks on this handoff commit are the fresh run.
