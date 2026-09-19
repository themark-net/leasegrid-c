# U2 — Non-goals (explicit rejects)

**Status:** Design DoD 2026-09-19 PT  
**Cite:** `docs/09-ui-track.md` U2–U5 · U0 `13-U0-NON-GOALS.md` · tip ≥ `3452a87` · CEO/PM U2 RELEASE 2026-09-19

U2 Design scopes **what we will not ship / not pretend** while wiring Credit → lab faucet. Implementers treat this as a hard reject list.

---

## Out of U2 (deferred slices)

| Reject in U2 | Belongs to | Why |
|--------------|------------|-----|
| **AppImage / `.deb`** one-command installer polish | **U3** | After U2 SHIP |
| **Recovery key export** + first-run threat HITL (production-ready) | **U4** | Explicit defer |
| **XMR top-up** / mainnet Monero pay | **U5** | After gate 0c PASS; faucet until then |
| Waiting on **0c** mint rails to start Credit UI | — | UI track parallel; faucet dogfood |

---

## Product-shape rejects (carry forward)

| Reject | Why |
|--------|-----|
| **Tahoe WUI / localhost web as the product** | Founder/CEO product lock |
| **“Web-only MVP then native later”** | Native Sync is the product |
| **Electron as default** without Gridsync-blocker writeup | Stack = Gridsync-class PyQt wrap/fork |
| Opening **WUI** from Credit / Top up / FAIL next | Same as shipping WUI-as-product |
| **Leasegrid Node** buyer chrome | Operator Phase 2 |

---

## Credit-specific rejects

| Reject | Why |
|--------|-----|
| Opaque **ZKAP wallet convert** / paste-import from foreign tools | Credit UI = Leasegrid Sync balance only |
| Claiming **1 GiB upload = 1 GiB credit 1:1** | Expansion is real; denomination honesty |
| Presenting balance as **local free disk** without share-capacity framing | Misleading |
| **Live XMR** address / payment / proof fields in Top up | U5 only |
| Fake “XMR payment received” while still on faucet | Honesty |
| Raw **ZKAP blob dumps** as the primary buyer number | Plain language first |
| Issuer **admin / mint dashboards** in Sync chrome | Lab/operator tooling ≠ buyer |
| **Localhost board URLs** in Credit FAIL next | Forbidden |
| In-app **ADR / corner-C theology dumps** | Docs in git; chrome = buyer copy |
| Fake **PoRep / SLA / slash** claims in Credit copy | Corner C honesty |

---

## Process rejects (this Design Bot pass)

| Reject | Why |
|--------|-----|
| Implement Credit / faucet code in Design DoD | Design only; code = DevBot via `19` |
| Git commit from Design executor | Parent/PM owns commit if any |
| Contact Mark from this executor | Mark-needed stays on parent / PM list |
| MachineId / nimo writes from box-only executor | Stage on box; parent CopyFromBox + INSTALL |
| Expanding U2 handoff into U3–U5 full build | Handoff is **U2 Credit/faucet only** |
| Regressing U1 Folders / tray / join / no-WUI | Preserve U1 |

---

## Still in scope (do not “non-goal” these)

- Credit as primary place (real panel)  
- Plain-language GiB·share-months balance  
- Lab faucet Top up + balance update after redeem  
- Denomination honesty + expansion REVIEW  
- Operate-or-FAIL on load / refresh / redeem  
- Folders → Open Credit when add blocked on zero credit  
- Optional soft balance chip in chrome (not required for exit)  
- Preserve U1 Folders / Magic Folder / tray / join  

---

## One-liner for PRs

> If it is AppImage packaging, recovery HITL, live XMR, WUI, Electron-default, opaque ZKAP convert, or a 1:1 upload=credit lie — it is out of U2. Ship Credit → faucet → visible balance.
