# U2 → DevBot handoff — **Credit panel ↔ lab issuer/faucet**

**Status:** Design DoD 2026-09-19 PT  
**Implement against:** this `docs/design/` package (15–18) + `docs/09-ui-track.md` U2 + U0 §3 baseline  
**Cite tip:** repo tip ≥ `3452a87` (U1 SHIP) — do not regress Folders / join / tray / no-WUI  
**Do not:** implement U3–U5 in this slice; do not ship WUI; do not wait for Phase 0 0c PASS; do not contact Mark from Design.

---

## UI track map (from `docs/09-ui-track.md`)

| Slice | Deliverable | Exit |
|-------|-------------|------|
| **U0** | Product lock + Design wireframes screens 1–5 | Done |
| **U1** | Gridsync-class Sync; one Magic Folder syncs | **SHIP** @ tip ≥ `3452a87` |
| **U2** | Credit panel ↔ lab issuer/faucet | **Balance visible after faucet** |
| **U3** | Linux AppImage and/or `.deb` | After U2 SHIP |
| **U4** | Recovery key export + first-run threat HITL | Deferred |
| **U5** | Swap faucet for XMR when gate 0c PASS | Deferred |

**This handoff = U2 only.** U0/U1 are input. U3–U5 wait.

---

## U2 DoD (tight)

### Must prove

1. **Credit place:** Native Sync exposes **Credit** as a primary place (tab/sidebar) — not Settings-only stub text.  
2. **Balance visible:** After join (U1), Credit shows remaining capacity in **plain language** (GiB·share-months / “About N GiB kept for ~30 days…”). Zero credit is an explicit empty state.  
3. **Denomination honesty:** On-panel copy states expansion is real — must **not** claim 1 GiB upload = 1 GiB credit 1:1. Include short one-node × 30-day framing.  
4. **Top up → lab faucet:** Primary **Top up** opens faucet stub; **Request faucet credit** calls lab issuer/faucet for this friendnet identity.  
5. **Balance updates after redeem:** Successful faucet redeem → Credit shows **updated** balance (and optional Recent row). This is the **UI track exit criterion**.  
6. **Operate-or-FAIL:** Load balance / Refresh / faucet redeem either succeed or show in-window **FAIL — … / Next: …** with Retry (or Open Credit from Folders). No silent no-op.  
7. **Folders bridge:** Add-folder (or allocate) blocked on insufficient/zero credit → FAIL with **[ Open Credit ]** primary.  
8. **Preserve U1:** Folders / Magic Folder sync, join, tray, no WUI-as-product. Credit must not open Tahoe WUI.  
9. **Opaque ZKAP reject:** No convert/import path for foreign opaque wallets in Credit UI (copy reject OK).  
10. **No mainnet XMR:** No live XMR pay fields; “XMR later” label only.  
11. **Tests:** Automated and/or dogfood evidence — see checklist below.  
12. **Dogfood note:** Short nimo steps: how to open Credit, hit faucet, see balance — for PM/founder.

### Explicitly waits for U3–U5 (do not block U2)

| Item | Slice |
|------|-------|
| AppImage / `.deb` installer polish | **U3** |
| Recovery key export + first-run threat HITL | **U4** |
| XMR top-up replacing faucet | **U5** (after gate 0c) |
| Chrome balance chip | Optional — not exit criterion |
| Brand-final names | Mark confirm — provisional Leasegrid Sync OK |
| macOS / Windows | After Linux dogfood |

---

## Stack rules

| Do | Don't |
|----|-------|
| Extend U1 Gridsync-class Sync (PyQt wrap/fork) | Greenfield Electron/Tauri for Credit alone |
| Wire to **lab** issuer/faucet stub already used for friendnet dogfood | Require mainnet XMR / 0c PASS |
| Buyer strings from wireframes 17 / journey 15 | Paste `00-decision.md` / ADR dumps into chrome |
| Keep Folders primary home | Make Credit the only window / replace Folders |
| FAIL in-window | “Check the terminal” / localhost board URL as Next |

If lab issuer API shape is thin: implement the thinnest redeem+balance read that proves exit; document the stub contract in dogfood — do **not** fake a successful balance without a real redeem path.

---

## Suggested U2 build order

1. Add **Credit** place chrome (empty → loading → balance card skeleton)  
2. Balance read from lab issuer; plain-language formatter + denomination note  
3. Top up dialog → faucet redeem → refresh balance  
4. FAIL paths for load + redeem; Retry  
5. Folders add-folder insufficient credit → Open Credit  
6. Tests + dogfood note; strike Credit from Settings deferred list  

---

## Design references (read before coding)

| Doc | Use |
|-----|-----|
| [15-U2-CREDIT-JOURNEY.md](15-U2-CREDIT-JOURNEY.md) | Happy path + FAIL copy |
| [16-U2-IA-CREDIT-PANEL.md](16-U2-IA-CREDIT-PANEL.md) | Place weight; faucet vs XMR; optional chip |
| [17-U2-WIREFRAMES.md](17-U2-WIREFRAMES.md) | ASCII binding for Credit + Folders bridge |
| [18-U2-NON-GOALS.md](18-U2-NON-GOALS.md) | Hard rejects |
| U0 `12` §3 Credit | Baseline (U2 refines) |
| `docs/09-ui-track.md` | Sequencing authority |

---

## U2 exit checklist (DevBot reports PASS/FAIL)

- [ ] Tip ≥ `3452a87`; U1 Folders/join/tray/no-WUI still PASS  
- [ ] Credit primary place opens in Sync  
- [ ] Balance visible in plain language (incl. zero state)  
- [ ] Denomination / expansion honesty present (no 1:1 upload lie)  
- [ ] Top up → lab faucet redeem succeeds in dogfood  
- [ ] **Balance visible / updated after faucet** (exit criterion)  
- [ ] Load FAIL + redeem FAIL in-window with Next + Retry  
- [ ] Folders insufficient credit → Open Credit  
- [ ] No WUI CTA from Credit; no live XMR fields  
- [ ] No opaque ZKAP convert  
- [ ] Tests (unit/UI and/or scripted dogfood evidence)  
- [ ] Dogfood steps written for nimo  
- [ ] Explicit list of what was deferred to U3–U5  

**U2 FAIL examples:** Credit only mentioned in Settings stub; faucet button no-ops; balance never updates after “success”; opens WUI; requires mainnet XMR; claims 1:1 upload=credit; regresses Magic Folder sync; silent issuer errors.

---

## Mark-needed (not DevBot blockers for U2 start)

| Mark-needed | Org-can-do now |
|-------------|----------------|
| Brand name confirm | Provisional Leasegrid Sync |
| Friendnet / faucet lab access if not already on nimo | Wire to existing lab issuer stub from U1 dogfood |
| Recovery-key accept ceremony | U4 |
| 0c XMR rails | U5 |

---

## One-liner

> **U2:** Wire Leasegrid Sync **Credit** to lab issuer/faucet so balance is visible after Top up; denomination honesty; operate-or-FAIL; preserve U1; defer AppImage, recovery HITL, and XMR to U3–U5.
