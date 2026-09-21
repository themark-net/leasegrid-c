# Leasegrid — post-Fable plan (PM)

**Date:** 2026-09-20 (PT)  
**Audience:** CEO, Design, DevBot/Cursor, Tester, Leasegrid Stress Test  
**Code now:** [PR #7 draft](https://github.com/themark-net/leasegrid-c/pull/7) `cursor/runnable-local-client-server-056d` @ `049fa0b` (Cursor `bc-9d0fb5d5…`). U1/U2 on main; #7 = runnable + packaging stack.  
**Founder signal:** installers exist; **dogfood still crashes / not working**.

Bots coordinate. Heavy fix → **Cursor on PR #7** (Fable continuity) or Grok Build on nimo. No Mark drip.

**Doc tip:** `f06ef01` · https://github.com/themark-net/leasegrid-c/blob/main/docs/10-post-fable-plan.md

---

## UX north star (locked)

Like **old CrashPlan**: files/folders first; Offer storage = local disk pie (% offered). Details secondary until stable. **No Tahoe WUI as product.**

---

## P0 — Stop the bleeding (this week)

| # | Issue | Work | Owner | Exit |
|---|-------|------|-------|------|
| P0.1 | [#8](https://github.com/themark-net/leasegrid-c/issues/8) | Crash matrix | Tester + Cursor | AppImage / venv / Windows; join; add folder; offer on/off |
| P0.2 | [#10](https://github.com/themark-net/leasegrid-c/issues/10) | Top-3 crash fix | Cursor on #7 | Boots + sync one folder without crash |
| P0.3 | [#9](https://github.com/themark-net/leasegrid-c/issues/9) | Operate-or-FAIL | Tester | Tip install operate path PASS |

Non-goals P0: CrashPlan polish, payment lecture, live 0c/0d, mainnet XMR, Tahoe WUI.

---

## P1 — CrashPlan shell (after P0 green)

| Issue | Work |
|-------|------|
| [#11](https://github.com/themark-net/leasegrid-c/issues/11) | Files-first shell: folder list primary; Offer = local disk pie (used/free/offered, % of this disk); single CTA join → folders → offer viz; payment lecture hidden until `LEASEGRID_GATED` |

P0 is green @ `c308b958`. Design PASS: nimo `docs/design/` README + 25–29 (`29-P1-DEVBOT-HANDOFF.md`); plan tip `f06ef01`. AppImage stays [#12](https://github.com/themark-net/leasegrid-c/issues/12).

---

## P2 — Rails polish (later)

0c/0d + XMR UI behind Advanced. Stress Test owns lab dates.

---

## Constraints

Mark-free P0 except crash facts only he has (CEO batch). Escalate CEO only money/legal/irreversible/creds.
