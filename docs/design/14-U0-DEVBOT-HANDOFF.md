# U0 → DevBot handoff — **U1 Gridsync spike only**

**Status:** Design DoD 2026-09-19 PT  
**Implement against:** this `docs/design/` package + `docs/09-ui-track.md`  
**Cite:** `docs/09-ui-track.md` sequencing U0–U5 · CEO U0 RELEASE 2026-09-19 · founder product lock  
**Do not:** implement U2–U5 in this spike; do not ship WUI; do not wait for Phase 0 0c/0d PASS to start.

---

## UI track map (from `docs/09-ui-track.md`)

| Slice | Deliverable | Exit |
|-------|-------------|------|
| **U0** | Product lock + Design Bot wireframes screens 1–5 | Founder ACK — **this package** |
| **U1** | Spike: Gridsync fork/wrap boots against existing friendnet; **one Magic Folder syncs** | Dogfood on nimo |
| **U2** | Credit panel ↔ lab issuer/faucet | Balance visible after faucet |
| **U3** | Linux installer (AppImage and/or .deb) | Fresh VM / second user install PASS |
| **U4** | Recovery key export + first-run threat copy | Non-expert walkthrough PASS |
| **U5** | Swap faucet for XMR top-up when gate 0c PASS | Phase 1 exit with rails |

**This handoff = U1 only.** U0 design is input. U2–U5 wait.

---

## U1 DoD (tight)

### Must prove

1. **Boot:** Gridsync fork **or** tight wrap launches as a native desktop window on Linux (lab/nimo).  
2. **Join:** App connects to an **existing friendnet** (invite or pre-seeded grid config — lab-acceptable).  
3. **One Magic Folder syncs:** Create or join **one** Magic Folder; local file change appears on a second participant **or** round-trips on the same grid with observable sync status.  
4. **No WUI product path:** Spike does not open Tahoe WUI as the buyer UI; no “use the web UI” primary CTA.  
5. **Tray or window persist:** Process can run as a desktop sync client (window and/or tray) — not a one-shot CLI demo only.  
6. **Operate-or-FAIL (minimal):** Join / add-folder failures show an in-window error (even crude) rather than silent no-op.  
7. **Dogfood note:** Short note on nimo: how to launch, which friendnet, which folder path — for PM/founder.

### Explicitly waits for U2–U5 (do not block U1)

| Item | Slice |
|------|-------|
| Credit panel + faucet redeem UI | **U2** |
| AppImage / .deb one-command installer polish | **U3** |
| Recovery key export + first-run threat HITL copy (production-ready) | **U4** |
| XMR top-up replacing faucet | **U5** (after gate 0c) |
| Settings Tor vs sync design-flag polish | U4/Settings polish — stub OK in U1 |
| Brand-final names | Mark confirm — provisional Leasegrid Sync OK |
| macOS / Windows | After Linux dogfood |

---

## Stack rules for the spike

| Do | Don't |
|----|-------|
| Prefer Gridsync (PyQt) fork/wrap + Magic Folder daemon | Greenfield Electron/Tauri without Gridsync-blocker writeup |
| Reuse Gridsync folder list / status mental model | Embed Tahoe WUI |
| Point at existing friendnet / lab introducer | Require Phase 0c XMR mint to demo sync |
| Keep buyer-facing strings free of ADR dumps | Paste `00-decision.md` into the UI |

If Gridsync is **unforkable** for later ZKAP credit: still finish U1 sync proof on Gridsync lineage if possible; write a short blocker note for credit integration — do **not** silently switch to WUI.

---

## Suggested U1 build order

1. Package or venv launch of Gridsync wrap with Leasegrid Sync title stub  
2. Connect to friendnet (invite or config drop)  
3. Add one Magic Folder; verify sync  
4. Minimal FAIL dialogs on join/add  
5. Dogfood README for nimo  

---

## Design references (read before coding)

| Doc | Use |
|-----|-----|
| [12-U0-WIREFRAMES.md](12-U0-WIREFRAMES.md) | Target IA/copy for later slices; U1 may be thinner |
| [11-U0-IA-NATIVE-SYNC.md](11-U0-IA-NATIVE-SYNC.md) | Places + tray; Folders primary |
| [10-U0-BUYER-JOURNEY.md](10-U0-BUYER-JOURNEY.md) | Happy path context |
| [13-U0-NON-GOALS.md](13-U0-NON-GOALS.md) | Hard rejects |
| `docs/09-ui-track.md` | Sequencing authority |

---

## U1 exit checklist (DevBot reports PASS/FAIL)

- [ ] Native window boots on Linux  
- [ ] Joins existing friendnet  
- [ ] One Magic Folder syncs (evidence: screenshot or log + path)  
- [ ] No WUI-as-product  
- [ ] Crude in-window FAIL on at least join failure  
- [ ] Dogfood steps written  
- [ ] Explicit list of what was deferred to U2–U5  

**U1 FAIL examples:** only CLI `tahoe magic-folder` with no app window; opens WUI as primary UI; cannot sync any folder; blocked on waiting for 0c.

---

## Mark-needed (not DevBot blockers for U1 start)

| Mark-needed | Org-can-do now |
|-------------|----------------|
| Friendnet invite for dogfood | Spike against lab grid already running |
| Brand name confirm | Use provisional Leasegrid Sync |
| Recovery-key accept ceremony later | U4 |

---

## One-liner

> **U1:** Gridsync-class Sync boots on friendnet and one Magic Folder syncs. Credit, installer, recovery HITL, and XMR wait for U2–U5 per `docs/09-ui-track.md`.
