# U4 → DevBot handoff — **Recovery key + first-run threat HITL**

**Status:** Design DoD 2026-09-21 PT  
**Implement against:** this `docs/design/` package (`30`–`33`) + issue [#15](https://github.com/themark-net/leasegrid-c/issues/15)  
**Cite tip:** main @ **`4e1e6bd`** (P0+P1 CrashPlan shell)  
**PM RELEASE:** CEO/PM RELEASED U4 Design now (product previously deferred U4–U5)  
**Do not:** ship Tahoe WUI; payment lecture on unpaid path; rewrite U0–P1 docs; contact Mark; claim AppImage or U5/mainnet XMR done; invent Phase letters.

---

## Track map

| Slice | Work | Owner |
|-------|------|-------|
| P0 / P1 | CrashPlan shell on main @ `4e1e6bd` | Done / preserve |
| **U4** | Threat HITL + recovery export/import walkthrough | **Design → DevBot/Cursor** |
| U5 | Faucet → XMR when 0c PASS | Deferred |
| #12 | AppImage | Deferred |

**This handoff = U4 Design → implement only.**

---

## U4 DoD (tight) — mirrors issue #15

### Must prove

1. **Threat HITL:** First-run Join shows four-point threat copy; Join disabled until ACK. No skip on first install.  
2. **Recovery place:** Reachable under **More → Recovery** without demoting Folders primary chrome.  
3. **Export gate:** STOP copy + **two** ACKs + optional passphrase + plaintext warning when empty + path + Write. Write disabled until both ACKs.  
4. **Export success:** File written (`*.leasegrid-recovery`), mode safe, verified before success copy; operator told to store offline.  
5. **Import path:** From Join (**Import recovery key instead…**) and from Recovery; wrong passphrase / corrupt → FAIL + Next in-window; nothing half-created.  
6. **Restore:** New device rejoins as **new participant**; folders appear on Folders; files download from friendnet (dogfood or e2e).  
7. **CrashPlan locks:** Folders-first; Offer pie; unpaid default; payment/XMR behind gated friendnet / Advanced.  
8. **Operate-or-FAIL:** Export / import / join-from-import either work or FAIL + Next **in-window** (no WUI Next; no terminal-only Next).  
9. **Preserve:** U1 Magic Folder / join / tray / no-WUI; P1 shell.  
10. **Honesty:** Do not claim #12 AppImage or U5/mainnet done.  
11. **Artifacts:** Design under `docs/design/` (`30`–`34`); implement cites this handoff + #15 + tip `4e1e6bd`.

### Explicitly out of U4 implement

| Item | Where it lives |
|------|----------------|
| Tahoe WUI | Never product |
| AppImage operate | #12 |
| Mainnet XMR / U5 | Deferred |
| Registrar / DNS | Out |
| Rewriting `10`–`29` markdown | Forbidden |
| Per-folder path picker (4f) | Stretch — default restore root OK if documented |

---

## Stack rules

| Do | Don't |
|----|-------|
| Extend existing Sync (`src/leasegrid_sync/` recovery + app) | Greenfield Electron for Recovery |
| Keep Folders primary after join | Force Recovery as post-join home |
| Dual-ACK before Write | Single OK / easy dismiss of scary gate |
| FAIL banners in-window | “Open WUI” / “see terminal” as Next |
| Cite #15 + tip `4e1e6bd` in dogfood | Invent Phase letters |
| Align copy with `recovery.py` constants where shipped | Invent a second threat model |

**Note:** Tip already has substantial recovery + threat strings (`docs/ops/u4-recovery.md`, `recovery.py`). U4 implement is **walkthrough PASS + CrashPlan-shell fit** (More → Recovery, nudge, gates, FAIL copy) — not a greenfield crypto redesign unless gaps fail the DoD.

---

## Suggested build order

1. Confirm Join threat HITL (ACK gates Join) on CrashPlan join page.  
2. Confirm More → Recovery place + Export/Import entry points.  
3. Harden export gate (dual ACK, passphrase warning, write verify, FAIL copy).  
4. Harden import from Join + Recovery (FAIL copy; no partial home).  
5. Dogfood / e2e: device A export → device B import → files byte-check.  
6. Optional Folders nudge (dismissible).  
7. Tests + short dogfood note for PM (no Mark drip).

---

## Design references (read before coding)

| Doc | Use |
|-----|-----|
| [30-U4-RECOVERY-JOURNEY.md](30-U4-RECOVERY-JOURNEY.md) | Happy paths + FAIL |
| [31-U4-IA-RECOVERY.md](31-U4-IA-RECOVERY.md) | Places + CTA ranks |
| [32-U4-WIREFRAMES.md](32-U4-WIREFRAMES.md) | ASCII frames |
| [33-U4-NON-GOALS.md](33-U4-NON-GOALS.md) | Hard rejects |
| U0 `12` §1a / §4 | Baseline threat + Recovery frames |
| P1 `25`–`29` | Folders-first chrome locks |
| `docs/ops/u4-recovery.md` | Ops/format detail (if present on tip) |
| Issue [#15](https://github.com/themark-net/leasegrid-c/issues/15) | Binding Design DoD |
| Tip `4e1e6bd` | CrashPlan shell base |

---

## U4 exit checklist (DevBot reports PASS/FAIL)

- [ ] Tip / branch documented; cite `4e1e6bd` + issue #15  
- [ ] First-run threat HITL: Join blocked until ACK  
- [ ] More → Recovery reaches export/import  
- [ ] Export: dual ACK required; plaintext warning if no passphrase  
- [ ] Export success only after verified write; offline-store copy shown  
- [ ] Export FAIL paths in-window with Next + Retry  
- [ ] Import from Join and from Recovery  
- [ ] Import FAIL (bad passphrase / corrupt) in-window; no partial join  
- [ ] Restore dogfood: folders visible; files return from friendnet  
- [ ] Folders remains primary chrome; Offer pie intact  
- [ ] Unpaid default: no payment lecture on export/import  
- [ ] No Tahoe WUI affordance  
- [ ] Tests updated (UI + recovery)  
- [ ] Dogfood note for PM — **no** AppImage / U5 / mainnet claims  

---

## Operate-or-FAIL reminder

Every U4 control (threat ACK, Write, Import, Retry) either performs its action or shows buyer-visible **FAIL** with a concrete **Next** in-window. Silent failure is itself FAIL for this handoff.

---

## One-liner for PM

> **U4:** Ship recovery-copy UX — first-run threat HITL + dual-ACK recovery key export/import — so a non-expert passes the walkthrough on CrashPlan shell @ `4e1e6bd`, without WUI or payment lecture.
