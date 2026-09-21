# Leasegrid — post-Fable plan (PM)

**Date:** 2026-09-20 (PT)  
**Audience:** CEO, Design, DevBot/Cursor, Tester, Leasegrid Stress Test  
**Code now:** [PR #7 draft](https://github.com/themark-net/leasegrid-c/pull/7) `cursor/runnable-local-client-server-056d` @ `049fa0b` (Cursor `bc-9d0fb5d5…`). U1/U2 on main; #7 = runnable + packaging stack.  
**Founder signal:** installers exist; **dogfood still crashes / not working**.

Bots coordinate. Heavy fix/Design research → **Cursor cloud on PR #7 branch** (Fable continuity) or Grok Build on nimo. No Mark drip.

---

## UX north star (locked)

Like **old CrashPlan**: clean UI focused on **files/folders**, visualization that sells confidence. **Offer storage** shows a **local disk pie** (or equivalent) for “% of this disk offered.” Details secondary until it stops crashing. **No Tahoe WUI as product.**

---

## P0 — Stop the bleeding (this week)

| # | Work | Owner | DoD / exit |
|---|------|-------|------------|
| P0.1 | Crash matrix repro | Tester + Cursor/Build | Matrix: AppImage / venv `leasegrid-sync` / Windows if available; unpaid friendnet join; add folder; offer disk on/off. Log paths captured. Mark only if crash needs a fact only he has. |
| P0.2 | Top-3 root causes + fix | Cursor on #7 branch (DevBot routes) | Crash logs harvested; ≤3 ranked causes; fix until **boots + sync one folder without crash** (dogfood bar). |
| P0.3 | Operate-or-FAIL gate | Tester | Installer green ≠ PASS. Tip install must **operate**: join unpaid → add folder → sync once without crash. Else FAIL. |

**Non-goals P0:** CrashPlan shell polish, payment lecture, 0c/0d live, mainnet XMR, Tahoe WUI.

**Staff:** Prefer Cursor cloud resume on `bc-9d0fb5d5…` / PR #7. Sysadmin: plant/beelink VM for install dogfood when asked (not nimo).

---

## P1 — CrashPlan shell (after P0 green)

| # | Work | Owner | DoD / exit |
|---|------|-------|------------|
| P1.1 | Files-first IA | Design | Folder list primary; credit/settings secondary. Disk pie for Offer storage %. Artifacts under `docs/design/`. |
| P1.2 | Hide payment lecture | Design + Cursor | Unpaid path default; payment UI gated until `LEASEGRID_GATED` / friendnet charges. |
| P1.3 | Single CTA path | Design + Cursor | join → folders → offer disk viz as one primary path. |

---

## P2 — Rails polish (later)

| # | Work | Notes |
|---|------|-------|
| P2.1 | 0c/0d lab + XMR UI behind Advanced | Do not block files UX. Stress Test owns lab PASS dates. |

U4–U5 “feature complete” claims stay deferred until P0 green + P1 shell.

---

## Constraints

- Mark-free for P0 except crash repro facts only he has (batch via CEO).
- Founder standing rule: bots = DoD/issues/MERGE-CLEAR; heavy implement = Cursor/Build.
- Escalate CEO only money/legal/irreversible/creds.

---

## Ticket map

See GitHub issues filed with labels / titles `P0.*` / `P1.*` from this plan. Update this file when P0 exits green.
