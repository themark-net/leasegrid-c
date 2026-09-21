# Leasegrid — post-Fable plan (PM)

**Date:** 2026-09-20 (PT)  
**Audience:** CEO, Design, DevBot/Cursor, Tester, Leasegrid Stress Test  
**Code now:** [PR #7 draft](https://github.com/themark-net/leasegrid-c/pull/7) `cursor/runnable-local-client-server-056d` @ `049fa0b` (Cursor `bc-9d0fb5d5…`). U1/U2 on main; #7 = runnable + packaging stack.  
**Founder signal:** installers exist; **dogfood still crashes / not working**.

Bots coordinate. Heavy fix/Design research → **Cursor cloud on PR #7 branch** (Fable continuity) or Grok Build on nimo. No Mark drip.

**Plan commit:** `c406e1c` · file: this doc.

---

## UX north star (locked)

Like **old CrashPlan**: clean UI focused on **files/folders**, visualization that sells confidence. **Offer storage** shows a **local disk pie** (or equivalent) for “% of this disk offered.” Details secondary until it stops crashing. **No Tahoe WUI as product.**

---

## P0 — Stop the bleeding (this week)

| # | Issue | Work | Owner | Exit |
|---|-------|------|-------|------|
| P0.1 | [#8](https://github.com/themark-net/leasegrid-c/issues/8) | Crash matrix repro | Tester + Cursor | AppImage / venv / Windows; join; add folder; offer on/off; logs |
| P0.2 | [#10](https://github.com/themark-net/leasegrid-c/issues/10) | Top-3 crash fix | Cursor on #7 | Boots + sync one folder without crash |
| P0.3 | [#9](https://github.com/themark-net/leasegrid-c/issues/9) | Operate-or-FAIL | Tester | Tip install operate path PASS |

**Non-goals P0:** CrashPlan shell polish, payment lecture, 0c/0d live, mainnet XMR, Tahoe WUI.

**Staff:** Resume Cursor on `bc-9d0fb5d5…` / PR #7. Sysadmin: plant/beelink VM when asked (not nimo).

---

## P1 — CrashPlan shell (after P0 green)

| # | Issue | Work | Owner |
|---|-------|------|-------|
| P1 | [#11](https://github.com/themark-net/leasegrid-c/issues/11) (or next) | Files-first IA + disk pie + CTA path | Design → Cursor |

---

## P2 — Rails polish (later)

0c/0d lab + XMR UI behind Advanced. Stress Test owns lab dates. Do not block files UX.

---

## Constraints

- Mark-free for P0 except crash facts only he has (batch via CEO).
- Founder standing rule: bots = DoD/issues/MERGE-CLEAR; implement = Cursor/Build.
- Escalate CEO only money/legal/irreversible/creds.
