# U4 — Non-goals (Recovery Design)

**Status:** Design DoD 2026-09-21 PT  
**Cite:** issue [#15](https://github.com/themark-net/leasegrid-c/issues/15) · tip `4e1e6bd`

---

## Hard rejects for U4 Design / implement

| Non-goal | Why |
|----------|-----|
| **Tahoe WUI as product UI** | Founder lock — Sync is native. |
| **“Reset password” UX** | False promise; capability loss is total. |
| **Rootcap / furl paste as the buyer restore path** | Recovery key file is the path; raw caps are not product chrome. |
| **Payment / XMR lecture to export or import** | P1 unpaid default; Credit stays gated. |
| **Making Recovery the post-join primary surface** | CrashPlan shell: Folders + Offer pie stay primary. |
| **Skipping first-run threat HITL** | U4 exit requires non-expert threat walkthrough. |
| **Claiming AppImage (#12) done** | Deferred; not a U4 Design exit. |
| **U5 / mainnet XMR polish** | Explicitly out of #15. |
| **Registrar / DNS / Node operator UI** | Buyer Sync only. |
| **Rewriting U0–P1 design bodies (`10`–`29`)** | U4 adds `30`–`34` only. |
| **Mark drip / SendToUser / git commit from Design** | Parent/PM owns commit & Mark contact. |
| **Inventing Phase letters** | Use U4 / issue #15. |
| **Silent export “success” without write verify** | Operate-or-FAIL; read-back before success copy. |

---

## Stretch (optional, not Design exit)

| Item | Note |
|------|------|
| Per-folder local path picker after import (U0 4f) | Default `~/Leasegrid/<name>` OK for U4 exit if documented |
| Printed QR / paper backup | Nice; file-on-USB is enough |
| Forced export before Add folder | Nudge OK; hard block is stretch |
| macOS Keychain / secret-service auto store | Out of U4 Design |

---

## In-scope reminder

U4 **does** include: first-run threat HITL; Recovery place under More; dual-ACK export gate; optional passphrase + plaintext warning; import from Join and Recovery; restore → Folders with operate-or-FAIL; CrashPlan / unpaid locks preserved; DevBot handoff citing #15 + tip `4e1e6bd`.
