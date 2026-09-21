# Leasegrid Sync — U2 Design DoD (Credit panel → lab faucet)

**Status:** U2 Design DoD ready — 2026-09-19 PT  
**Owner:** Design Bot (executor staged on box)  
**Date:** 2026-09-19 PT  
**Product lock:** CEO / founder RELEASE 2026-09-19 + `docs/09-ui-track.md`  
**Cite tip:** ≥ `3452a87` (U1 SHIP) — Design DoD assumes U1 Folders/Magic Folder/tray/join intact  
**Canonical source (box staging):** `/workspace/leasegrid-u2-src/` → `09-ui-track.md`, U0 wireframes §3 Credit, U0 non-goals, U0 DevBot handoff  
**Install target (nimo):** `/home/mark/DEVELOP/leasegrid-c/docs/design/`  
**Brand (provisional):** **Leasegrid Sync** (buyer)

---

## Design index (UI track)

| Slice | Status | Exit |
|-------|--------|------|
| **U0** | Design DoD done (wireframes 1–5) | Founder ACK / product lock |
| **U1** | **SHIP** @ tip ≥ `3452a87` | Gridsync-class Sync boots; one Magic Folder syncs; no WUI |
| **U2** | **Design DoD ready** (this package) | Implement: Credit panel ↔ lab issuer/faucet; **balance visible after faucet** |
| **U3** | Deferred until U2 SHIP | Linux AppImage and/or `.deb` |
| **U4** | **Design DoD ready** (`30`–`34`) | Threat HITL + recovery key export/import; non-expert walkthrough PASS @ `4e1e6bd` |
| **U5** | Deferred | Swap faucet for XMR when gate 0c PASS |

**U2 one-liner:** Credit becomes a real place in Leasegrid Sync — remaining GiB-share-months in plain language, Top up via lab faucet, balance updates after redeem; no mainnet XMR; denomination honesty (expansion is real); operate-or-FAIL.

**U4 one-liner:** Recovery-copy UX on the CrashPlan shell — first-run threat HITL, dual-ACK recovery key export, import-on-new-device restore to Folders — without Tahoe WUI or a payment lecture. Canonical handoff: [34-U4-DEVBOT-HANDOFF.md](34-U4-DEVBOT-HANDOFF.md). Cite issue #15 · tip `4e1e6bd`. U0–P1 bodies (`10`–`29`) are not rewritten by this package.

---

## Artifact index

| File | Contents |
|------|----------|
| [15-U2-CREDIT-JOURNEY.md](15-U2-CREDIT-JOURNEY.md) | Happy path open Credit → balance → Top up faucet → update; FAIL paths; Folders→Credit on zero credit |
| [16-U2-IA-CREDIT-PANEL.md](16-U2-IA-CREDIT-PANEL.md) | Credit as primary place; balance model; faucet vs XMR later; optional chrome chip |
| [17-U2-WIREFRAMES.md](17-U2-WIREFRAMES.md) | ASCII refine of U0 §3 Credit + top-up stub + empty/loading/error/needs-judgment; Folders zero-credit deep link; Settings still stub |
| [18-U2-NON-GOALS.md](18-U2-NON-GOALS.md) | Explicit rejects for U2 Design / implement |
| [19-U2-DEVBOT-HANDOFF.md](19-U2-DEVBOT-HANDOFF.md) | Tight DoD: wire Credit panel to lab issuer/faucet; tests; tip ≥ `3452a87`; defer U3–U5 |
| [../09-ui-track-U2-POINTER.md](../09-ui-track-U2-POINTER.md) | One-line pointer beside `09-ui-track.md` |
| [30-U4-RECOVERY-JOURNEY.md](30-U4-RECOVERY-JOURNEY.md) | Threat → join → export; import → Folders restore; FAIL paths |
| [31-U4-IA-RECOVERY.md](31-U4-IA-RECOVERY.md) | IA: Folders primary; Recovery under More; CTA ranks; copy layers |
| [32-U4-WIREFRAMES.md](32-U4-WIREFRAMES.md) | ASCII: threat Join; Recovery place; export gate; import; FAIL |
| [33-U4-NON-GOALS.md](33-U4-NON-GOALS.md) | WUI; reset-password; payment lecture; AppImage/U5 claims; do not rewrite `10`–`29` |
| [34-U4-DEVBOT-HANDOFF.md](34-U4-DEVBOT-HANDOFF.md) | Tight DoD + tests; cite #15 + tip `4e1e6bd`; operate-or-FAIL |
| [../09-ui-track-U4-POINTER.md](../09-ui-track-U4-POINTER.md) | One-line pointer beside `09-ui-track.md` |
| [10-U0-BUYER-JOURNEY.md](10-U0-BUYER-JOURNEY.md) | Prior U0 (still in tree) |
| [11-U0-IA-NATIVE-SYNC.md](11-U0-IA-NATIVE-SYNC.md) | Prior U0 |
| [12-U0-WIREFRAMES.md](12-U0-WIREFRAMES.md) | Prior U0 (Credit baseline §3) |
| [13-U0-NON-GOALS.md](13-U0-NON-GOALS.md) | Prior U0 |
| [14-U0-DEVBOT-HANDOFF.md](14-U0-DEVBOT-HANDOFF.md) | Prior U1 implement handoff |

---

## U2 scope (binding)

1. **Credit panel** in native Leasegrid Sync (Gridsync-class) — remaining GiB-share-months in plain language.  
2. **Denomination honesty:** 1 token ≈ 1 GiB-share × 30 days on **one** node; expansion is real — UI must **not** claim 1 GiB upload = 1 GiB credit 1:1.  
3. **Top up via lab faucet** (issuer/faucet stub) — balance updates after successful redeem. **No mainnet XMR** (that’s U5).  
4. **Operate-or-FAIL** — refresh balance / Top up / faucet redeem either work or FAIL + next **in-window**.  
5. **Preserve U1:** Folders / Magic Folder sync, join, tray, no WUI. Credit becomes a **real place** (not U1 stub).  
6. Opaque ZKAP wallets do **not** convert in Credit UI.  
7. Product copy only — no ADR dumps.

---

## Binding constraints

| Lock | Rule |
|------|------|
| Tip | Implement against repo tip ≥ `3452a87` (U1 SHIP) |
| Product | Native Sync only; no WUI; no Electron default |
| Credit place | Primary nav place (tab/sidebar) — real, not Settings stub |
| Balance | Plain-language GiB·share-months; refresh works or FAIL |
| Faucet | Lab issuer/faucet redeem; balance visible after success |
| Denomination | Expansion honesty on Credit home + expansion surprise REVIEW |
| Opaque ZKAPs | No convert / paste-wallet import in Credit |
| XMR | Label “later when mint rails PASS” only — no U5 flow in U2 |
| Folders bridge | Add-folder blocked on zero credit → **Open Credit** primary |
| Chrome | Buyer copy only; no localhost boards; no ADR theology |
| Sequencing | U3 AppImage/.deb **after** U2 SHIP; U4–U5 deferred |

---

## Exit criterion (UI track)

Per `docs/09-ui-track.md` **U2:**

> Credit panel wired to lab issuer/faucet (no mainnet XMR required) → **Balance visible after faucet**.

Design DoD exit: this package ready for DevBot implement handoff (`19`). Implement exit: dogfood shows non-zero (or updated) balance after faucet redeem in Sync Credit place.

---

## Success check (U2 Design PASS)

- [x] Design index: U0–U1 done; **U2 Design DoD ready**; tip ≥ `3452a87`  
- [x] Credit journey with happy path + FAIL + Folders→Credit  
- [x] IA: Credit primary place; balance model; faucet vs XMR later  
- [x] Wireframes refine U0 §3 + Folders zero-credit deep link + Settings stub note  
- [x] Non-goals explicit (AppImage, recovery HITL, XMR, WUI, Electron, opaque convert)  
- [x] DevBot handoff: tight DoD, tests, defer U3–U5  
- [x] Package staged under `/workspace/leasegrid-u2-out/` for parent nimo install  
- [x] No implement / no git commit / no Mark contact from this executor  

---

## Explicit non-goals (summary)

AppImage / `.deb` (U3) · recovery HITL (U4) · XMR top-up (U5) · WUI · Electron · waiting on 0c · opaque ZKAP convert · ADR dumps.

See [18-U2-NON-GOALS.md](18-U2-NON-GOALS.md).
