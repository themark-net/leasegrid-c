# U0 — Non-goals (explicit rejects)

**Status:** Design DoD 2026-09-19 PT  
**Cite:** `docs/09-ui-track.md` Explicit rejects · `docs/03-roadmap.md` · `docs/00-decision.md` · CEO U0 RELEASE 2026-09-19

U0 Design scopes **what we will not ship / not pretend** in the buyer Sync MVP. Implementers treat this as a hard reject list.

---

## Product-shape rejects

| Reject | Why |
|--------|-----|
| **Shipping Tahoe WUI / localhost web as the product** | Founder/CEO product lock; `09-ui-track.md` forbid |
| **“Web-only MVP then native later”** | Native + installer is the product; web is optional alt only |
| **Waiting for full Phase 0 (0c/0d) before any UI work** | UI track parallel; faucet until XMR rails |
| **Electron as default without a Gridsync-blocker writeup** | Stack default = Gridsync (PyQt) wrap/fork |
| **Leasegrid Node buyer chrome in U0** | Operator package is Phase 2; mention only |

---

## Surface / feature rejects (buyer MVP)

| Reject | Why |
|--------|-----|
| Full Tahoe capability / directory **browse** | Dropbox/Magic Folder metaphor only |
| **Mobile** app | Phase 4 table-stakes later |
| **Sharing** UX beyond invite codes | Caps-as-sharing is not MVP |
| **WUI embed** inside Sync | Same as shipping WUI-as-product |
| Opaque **ZKAP wallet convert** from foreign tools | Credit UI is Leasegrid balance only |
| **Mainnet XMR top-up** before gate 0c PASS | Faucet stub through U2–U4; U5 swaps when rails PASS |
| In-app **ADR / corner-C theology dumps** | Docs live in git; product chrome = buyer copy |
| **Localhost board URLs** / lab dashboards in chrome | Operator/lab tooling ≠ Sync |
| Fake **PoRep / SLA** claims in UI copy | Corner C: stop feeding dead nodes; no public proofs |
| **Slash / bond** UX as required to store a byte | Optional B-lite is later / ignorable (`00-decision.md`) |

---

## Process rejects (this Design Bot pass)

| Reject | Why |
|--------|-----|
| Implement product / Gridsync code in U0 Design | Design DoD only; code starts at U1 |
| Git commit from Design executor | Parent/PM owns commit if any |
| Contact Mark from this executor | Mark-needed items stay on parent / PM list |
| MachineId / nimo writes from box-only executor | Stage on box; parent CopyFromBox + INSTALL |
| Expanding U1 handoff into U2–U5 full build | Handoff is **U1 spike only** |

---

## Still in scope (do not “non-goal” these)

- Native Sync window + tray  
- Five surfaces wireframed in U0  
- Honest threat + Tor vs sync design flag  
- Credit plain-language denomination  
- Recovery scary gate  
- Operate-or-FAIL  
- Linux AppImage / .deb path (U3; designed toward, not coded here)

---

## One-liner for PRs

> If it is a WUI, a web-only MVP, an Electron default without a blocker writeup, a Tahoe browser, or mainnet XMR before 0c — it is out. Ship Sync.
