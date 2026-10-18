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
