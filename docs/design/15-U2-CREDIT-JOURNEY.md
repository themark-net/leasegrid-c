# U2 — Credit journey (Leasegrid Sync)

**Status:** Design DoD 2026-09-19 PT  
**Cite:** `docs/09-ui-track.md` U2 · U0 wireframes §3 Credit · tip ≥ `3452a87` (U1 SHIP) · CEO/PM U2 RELEASE 2026-09-19  
**Product:** Native **Leasegrid Sync** (buyer). Credit becomes a **real place** (not U1 stub).

---

## North star (one sentence)

A buyer already on friendnet (U1) opens **Credit**, sees remaining capacity in plain language, tops up via the **lab faucet**, and watches the balance update — without mainnet XMR and without lying that upload size equals credit 1:1.

---

## Preconditions (from U1)

| Must already work | Notes |
|-------------------|-------|
| Native Sync window | Leasegrid Sync title; Gridsync-class |
| Join friendnet | Invite or saved grid; in-window FAIL |
| Folders / Magic Folder | At least one folder path works in dogfood |
| Tray / window persist | Not CLI-only |
| No WUI product path | Preserve; Credit must not open WUI |
| Credit / Settings | U1 left Credit deferred — U2 replaces stub with real place |

---

## Happy path (Credit → faucet → balance updates)

| Step | Place | Buyer does | System does | Exit |
|------|-------|------------|-------------|------|
| 0 | Folders (or tray) | Opens Sync; already joined | Status chip Connected / Syncing | Ready |
| 1 | Chrome | Clicks **Credit** | Navigates to Credit place; starts balance load | Loading or balance card |
| 2 | Credit | Sees remaining capacity | Shows plain-language GiB·share-months + denomination note | Balance visible |
| 3 | Credit | Clicks **Top up** | Opens Top up dialog (lab faucet stub) | Dialog open |
| 4 | Top up | Picks amount tier; **Request faucet credit** | Calls lab issuer/faucet; redeems for this grid identity | Loading… |
| 5 | Credit | Returns to Credit (or dialog closes) | Refreshes balance; Recent row for faucet top-up | **Balance updated** (exit criterion) |
| 6 | Folders (optional) | Adds folder if previously blocked | Allocate shares with new credit | Folder row or FAIL |

**Steady state:** Credit tab always shows last-known balance; Refresh (explicit or on place enter) either updates or FAIL + next. Tray menu may include **Credit** (optional).

---

## Journey map (ASCII)

```
  [U1 Folders / tray]
         │
         ▼
  ┌─────────────────────┐
  │ Open Credit place   │── load FAIL ──► in-window FAIL + Retry / check issuer
  └──────────┬──────────┘
             │ PASS
             ▼
  ┌─────────────────────┐
  │ Balance visible     │◄── zero credit empty state + Top up CTA
  │ (plain language)    │
  └──────────┬──────────┘
             │ Top up
             ▼
  ┌─────────────────────┐
  │ Lab faucet dialog   │── issuer/faucet FAIL ──► FAIL + Retry; balance unchanged
  └──────────┬──────────┘
             │ PASS redeem
             ▼
  ┌─────────────────────┐
  │ Balance updates     │  ◄══ U2 exit: balance visible after faucet
  │ Recent: faucet row  │
  └─────────────────────┘

  Folders side-door (zero credit):
  Add folder ── FAIL no credit ──► [ Open Credit ] ←primary ──► Top up path above
```

---

## Operate-or-FAIL (Credit controls)

| Control | PASS | FAIL (in-window) | Next |
|---------|------|------------------|------|
| Open Credit / load balance | Balance card (incl. zero) | Issuer unreachable / auth / parse error | Retry; check network; ask operator if lab down |
| Refresh balance | Numbers update; timestamp | Same as load FAIL | Retry; leave last-known with stale hint **or** clear FAIL state — never silent blank |
| Top up → Request faucet | Redeem OK; balance increases; Recent row | Faucet down / issuer reject / network / timeout | Retry; Close; balance **unchanged** |
| Amount tier select | Selection only | N/A | — |
| Cancel Top up | Dialog closes; no redeem | N/A | Balance unchanged |
| Folders → Add folder (no credit) | — | FAIL not enough credit | **Open Credit** primary |
| Expansion surprise (add/sync) | REVIEW dialog with estimate | N/A (judgment) | Top up or Cancel add |
| Paste opaque ZKAP / foreign wallet | Reject copy only | Soft reject — no convert | Stay on Leasegrid Sync credit |

**Rule:** No silent no-op. No “check the terminal.” No localhost board URL. No “see ADR.” No claim of XMR payment success in U2.

---

## FAIL paths (buyer-visible)

### F1 — Issuer / balance load down

```
FAIL — could not load credit balance.
Issuer unreachable or returned an error. Last known balance may be stale.
Next: Retry; check network; if lab is down, ask your friendnet operator.
[ Retry ]←primary
```

### F2 — Faucet / issuer redeem FAIL

```
FAIL — top-up did not complete.
Faucet or issuer rejected the request (or network error).
Next: Retry; if lab is down, ask your operator. Balance unchanged.
[ Retry ]←primary   [ Close ]
```

### F3 — Zero credit (empty, not necessarily FAIL)

```
Credit remaining: none.
Sync may pause when leases cannot renew. Folders cannot allocate new shares until you top up.
[ Top up ]←primary
```

### F4 — Folders add blocked → Credit

```
FAIL — folder not added.
Not enough storage credit to allocate shares.
Next: Credit → Top up, then Add folder again.
[ Open Credit ]←primary   [ Cancel ]
```

### F5 — Expansion surprise (needs judgment)

```
REVIEW — this folder needs more credit than the raw size.
Share expansion is expected. Estimated need: ~3.2× upload size.
Uploading 1 GiB uses more than 1 GiB of credit — shares span nodes.
[ Top up ]←primary   [ Cancel add ]
```

### F6 — Opaque foreign wallet (reject, not convert)

```
This screen shows Leasegrid Sync credit only.
Pasting an opaque ZKAP wallet from another tool will not convert here.
[ Close ]
```

---

## Denomination honesty (journey copy lock)

| Say | Do not say |
|-----|------------|
| “About **N GiB** kept for ~**30 days** on this friendnet” | “N GiB free disk” as if local free space |
| “Prepaid share-capacity” / “encrypted shares expand across nodes” | “1 GiB upload = 1 GiB credit” |
| “1 credit unit ≈ 1 GiB-share × 30 days on **one** node” (short note OK) | Raw ZKAP blob dumps as the primary number |
| “Lab faucet until Monero (XMR) mint is ready” | “Pay with XMR” as a live U2 control |

---

## Out of this journey (explicit)

- AppImage / `.deb` install path (U3)  
- Recovery export HITL (U4)  
- XMR payment / mint redeem (U5 / gate 0c)  
- First-run threat checkbox polish (U4)  
- Operator issuer dashboards  

---

## One-liner

> **U2 journey:** Credit place → plain-language balance → lab faucet Top up → balance updates; zero-credit Folders deep-link to Credit; FAIL stays in-window; no mainnet XMR.
