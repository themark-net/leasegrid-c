# U2 — Information architecture (Credit panel)

**Status:** Design DoD 2026-09-19 PT  
**Cite:** `docs/09-ui-track.md` U2 · U0 IA places · tip ≥ `3452a87` · CEO/PM U2 RELEASE 2026-09-19  
**Product chrome:** Buyer copy only — no ADR dumps, no localhost board URLs, no Tahoe WUI embeds.

---

## Thesis

**Credit is a primary place** in Leasegrid Sync — same chrome weight as Folders / Recovery / Settings — not a Settings stub line and not a modal-only afterthought.

U1 shipped Folders + tray + join with Credit deferred. U2 **promotes Credit to a real place** wired to the lab issuer/faucet.

---

## Window chrome (U2 delta)

```
┌─ Leasegrid Sync — friendnet “lab” ───────────────[─][□][×]─┐
│  Folders   Credit   Recovery   Settings          Connected ✓│
│  (optional)  ≈48 GiB·mo                                      │
│═════════════════════════════════════════════════════════════│
│  (place body — Credit when selected)                        │
└─────────────────────────────────────────────────────────────┘
```

| Element | U2 rule |
|---------|---------|
| **Credit** tab/place | **Required.** Selecting it loads Credit home (balance). |
| Folders | Unchanged as home after first-run; preserve U1 |
| Recovery | Still stub / deferred polish until U4 — place may exist thin; do not fake export HITL as done |
| Settings | Still stub for U3–U5 items; may **remove** “Credit (U2)” from deferred list once Credit place ships |
| Status chip | Connection status (U1). **Optional:** small balance chip in chrome — see below |
| Tray | Keep U1 tray. Optional menu item **Credit** → opens Credit place |

**IA choice:** Same as U0 — top tabs of places (or Gridsync sidebar equivalent). Do not invent a third nav system for Credit alone.

---

## Credit place — structure

| Region | Role | Objects |
|--------|------|---------|
| **Balance card** | Primary | Plain-language remaining capacity; denomination honesty note |
| **Primary CTA** | Top up | Opens faucet Top-up dialog |
| **Secondary** | Refresh | Explicit refresh control and/or refresh on place enter |
| **Recent** | Optional stub list | Faucet top-up / lease renew rows if issuer provides; else hide section |
| **Lab note** | Honesty | Faucet until XMR; opaque wallets do not convert |

### Balance model (binding)

| Concept | Buyer-facing model |
|---------|-------------------|
| Unit | **GiB-share-months** (GiB·mo) — prepaid share-capacity |
| Denomination | 1 token ≈ 1 GiB-share × 30 days on **one** node |
| Expansion | Encrypted shares span nodes → upload size ≠ credit burn 1:1 |
| Display | Prefer “About **N GiB** kept for ~**30 days** on this friendnet” over raw token integers alone |
| Zero | Explicit empty state + Top up — not a blank panel |
| Stale | If refresh fails, show FAIL; optionally keep last-known with “could not refresh” — never invent numbers |

### What Credit is **not**

| Reject in Credit IA | Why |
|---------------------|-----|
| Raw ZKAP blob / wallet dump as primary UI | Opaque; not buyer language |
| Foreign ZKAP wallet import/convert | Explicit non-goal |
| Live XMR pay form | U5 after gate 0c |
| Issuer admin / mint dashboard | Operator/lab tooling |
| “Disk free” metaphor without expansion note | Lies about expansion |
| WUI / localhost board link | Forbidden product path |

---

## Faucet vs XMR later

| Now (U2) | Later (U5) |
|----------|------------|
| **Top up** → lab faucet / issuer stub dialog | Same entry point swaps to XMR payment when 0c PASS |
| Copy: “Lab faucet (stub)” + “Later: Monero (XMR)” | Copy: pay with XMR; faucet may remain lab-only |
| Success = balance increases after redeem | Success = mint confirms payment → credit |
| No mainnet XMR required for U2 exit | Phase 1 rails exit still needs 0c for real XMR |

**IA rule:** One **Top up** control. Do not ship parallel “Faucet” and “XMR” primary buttons in U2. XMR is a **label about the future**, not a second live flow.

---

## Optional chrome chip

| Option | Spec | Guidance |
|--------|------|----------|
| **A — No chip** | Balance only inside Credit place | Simplest; default if chrome crowded |
| **B — Soft chip** | Small `≈48 GiB·mo` or `Credit low` in title bar / status area; click → Credit | Nice for dogfood; must not replace Credit place |
| **C — Tray hint** | Tray tooltip includes balance when known | Optional; FAIL must not spam tray balloons |

**U2 Design recommendation:** Implement Credit place + Top up **first**. Chip **optional** — not an exit criterion. If chip ships, it is read-only + deep-link; operate-or-FAIL still lives on Credit refresh/Top up.

---

## Folders ↔ Credit bridge

| Trigger | IA behavior |
|---------|-------------|
| Add folder / allocate fails on zero or insufficient credit | FAIL banner with **[ Open Credit ]** primary |
| Expansion estimate exceeds remaining | REVIEW dialog → Top up or Cancel add |
| Sync pause from lease renew failure (if detectable in U2) | Folders status FAIL/paused + link to Credit (thin OK) |

Folders remains **home**. Credit is the **fix place** for capacity problems — one click from FAIL copy.

---

## Navigation rules (U2)

1. Credit is one click from chrome — no scavenger hunt.  
2. Top up is the only payment/redeem entry in U2 (faucet).  
3. Deep links from Folders FAIL land on Credit home (optionally auto-open Top up after Open Credit — optional polish; default = Credit home with Top up visible).  
4. Settings must not be the only path to balance.  
5. Operate-or-FAIL on load, refresh, and redeem.  
6. Preserve U1: Folders, join, tray, no WUI.

---

## Settings (U2 interaction)

Settings stays a **stub surface** for U3–U5. After Credit place ships:

- Remove or strike “Credit panel (U2)” from any deferred-feature list in Settings.  
- Keep AppImage/.deb (U3), recovery HITL (U4), XMR (U5) listed as deferred if Settings still shows the roadmap stub.  
- Do not bury live Top up under Settings.

---

## One-liner

> **U2 IA:** Credit is a primary place with plain-language balance and a single Top up → lab faucet path; optional chrome chip; Folders FAIL deep-links here; XMR waits for U5.
