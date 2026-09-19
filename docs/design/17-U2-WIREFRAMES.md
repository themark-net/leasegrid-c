# U2 — Wireframes (Credit panel + faucet)

**Status:** Design DoD 2026-09-19 PT  
**Cite:** U0 `12-U0-WIREFRAMES.md` §3 Credit (baseline) · `docs/09-ui-track.md` U2 · tip ≥ `3452a87` · CEO/PM U2 RELEASE 2026-09-19  
**Platform:** Native desktop (Gridsync-class). ASCII binding for IA/copy; pixels follow Qt.  
**Scope:** Refine Credit (+ Folders zero-credit deep link). First-run / Recovery / Settings polish stay U4 / stub — shown only where U2 touches them.

---

## Shared chrome (unchanged pattern)

```
┌─ Leasegrid Sync — friendnet “lab” ───────────────[─][□][×]─┐
│  Folders   Credit   Recovery   Settings          Connected ✓│
│═════════════════════════════════════════════════════════════│
│  (place body)                                               │
└─────────────────────────────────────────────────────────────┘
```

Status chip: `Connecting…` | `Connected ✓` | `Syncing…` | `Offline` | `FAIL`.  
Optional (not required): soft balance chip `≈48 GiB·mo` near status — click opens Credit.

---

# 3. Credit (U2 refine of U0 §3)

## 3a. Balance visible (plain language) — primary

```
┌─ Leasegrid Sync ──────────────────────────────── Connected ✓┐
│  Folders   Credit   Recovery   Settings                     │
│═════════════════════════════════════════════════════════════│
│  Credit                                    [ Refresh ]      │
│                                                             │
│  ┌─ Remaining ────────────────────────────────────────────┐ │
│  │  About **48 GiB** kept for ~**30 days**                │ │
│  │  on this friendnet                                     │ │
│  │                                                        │ │
│  │  Plain meaning: prepaid share-capacity, not a simple   │ │
│  │  “disk free” meter. Encrypted shares expand across     │ │
│  │  nodes — uploading 1 GiB uses more than 1 GiB of       │ │
│  │  credit.                                               │ │
│  │                                                        │ │
│  │  (1 credit ≈ 1 GiB-share × 30 days on one node.)       │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                             │
│  [ Top up ]←primary                                         │
│                                                             │
│  Lab note: Top up uses a faucet stub until XMR mint is      │
│  ready. Opaque ZKAP wallets from other apps do not convert. │
│                                                             │
│  Recent                                                     │
│  · Faucet top-up  +12 GiB·mo    today                       │
│  · Lease renew                 yesterday                    │
└─────────────────────────────────────────────────────────────┘
```

**Denomination lock:** 1 token ≈ 1 GiB-share × 30 days on **one** node. UI must not claim 1 GiB upload = 1 GiB credit 1:1.

## 3b. Empty / zero credit

```
┌─ Leasegrid Sync ──────────────────────────────── Connected ✓┐
│  Folders   Credit   Recovery   Settings                     │
│═════════════════════════════════════════════════════════════│
│  Credit                                    [ Refresh ]      │
│                                                             │
│  Credit remaining: **none**.                                │
│  Sync may pause when leases cannot renew.                   │
│  New folders cannot allocate shares until you top up.       │
│                                                             │
│  [ Top up ]←primary                                         │
│                                                             │
│  Lab note: Top up uses a faucet stub until XMR mint is      │
│  ready.                                                     │
└─────────────────────────────────────────────────────────────┘
```

## 3c. Top-up stub (lab faucet now → XMR later)

```
┌─ Top up ────────────────────────────────────────────────────┐
│  Lab faucet (stub)                                          │
│  Request prepaid credit for this friendnet.                 │
│                                                             │
│  Amount  ○ Small (≈ 10 GiB·mo)  ● Medium (≈ 50)  ○ Large    │
│                                                             │
│  Later: Top up with Monero (XMR) when mint rails PASS.      │
│  (XMR is not available in this build.)                      │
│                                                             │
│  [ Request faucet credit ]←primary   [ Cancel ]             │
└─────────────────────────────────────────────────────────────┘
```

**U2:** Only faucet request is live. No XMR address / amount / payment proof fields.

## 3d. Loading — balance / redeeming

```
│  Loading credit balance…                                    │
```

```
│  Requesting credit from faucet…                             │
│  [ Cancel ]                                                 │
```

## 3e. Error — balance load FAIL

```
│  FAIL — could not load credit balance.                      │
│  Issuer unreachable or returned an error.                   │
│  Next: Retry; check network; if lab is down, ask your       │
│        friendnet operator.                                  │
│  [ Retry ]←primary                                          │
```

## 3f. Error — faucet / issuer redeem FAIL

```
│  FAIL — top-up did not complete.                            │
│  Faucet or issuer rejected the request (or network error).  │
│  Next: Retry; if lab is down, ask your operator. Balance    │
│        unchanged.                                           │
│  [ Retry ]←primary   [ Close ]                              │
```

## 3g. Success — after faucet (exit criterion)

```
│  Top-up complete.                                           │
│  About **60 GiB** kept for ~**30 days** on this friendnet.  │
│  [ Done ]←primary                                           │
```

Or dialog closes and Credit home shows updated Remaining + Recent faucet row. Either pattern OK; **balance must be visible**.

## 3h. Needs judgment — denomination / surprise expansion

```
│  REVIEW — this folder needs more credit than the raw size.  │
│  Share expansion is expected. Estimated need: ~3.2× upload. │
│  Uploading 1 GiB uses more than 1 GiB of credit.            │
│  [ Top up ]←primary   [ Cancel add ]                        │
```

## 3i. Reject — opaque foreign wallet

```
│  This screen shows Leasegrid Sync credit only.              │
│  Pasting an opaque ZKAP wallet from another tool will not   │
│  convert here.                                              │
│  [ Close ]                                                  │
```

---

# 2. Folders — U2 touch (zero-credit bridge)

## 2d. Error — add folder FAIL (no credit) — refine U0

```
│  FAIL — folder not added.                                   │
│  Not enough storage credit to allocate shares.              │
│  Next: Credit → Top up, then Add folder again.              │
│  [ Open Credit ]←primary   [ Cancel ]                       │
```

**Open Credit** navigates to Credit place (3a or 3b). Do not open WUI. Do not open Settings.

## 2b. Populated — unchanged from U1/U0 (preserve)

Folders list, sync status, Add folder, tray — **preserve U1**. No Credit stub row inside Folders required.

---

# 5. Settings — still stub for U3–U5

```
┌─ Leasegrid Sync ──────────────────────────────── Connected ✓┐
│  Folders   Credit   Recovery   Settings                     │
│═════════════════════════════════════════════════════════════│
│  Settings                                                   │
│                                                             │
│  Startup                                                    │
│  ☑ Start Leasegrid Sync when I log in   (thin OK)           │
│                                                             │
│  Coming later                                               │
│  · Linux AppImage / .deb installer — U3                     │
│  · Recovery key export HITL — U4                            │
│  · Monero (XMR) top-up — U5 (after mint rails)              │
│                                                             │
│  About                                                      │
│  Leasegrid Sync (buyer) · version 0.x                       │
│  Grid: lab-friendnet                                        │
│  Credit: open the Credit place to view balance / Top up.    │
└─────────────────────────────────────────────────────────────┘
```

**U2:** Strike any “Credit (U2)” deferred line once Credit place ships. Do not put live Top up only here.

---

# State matrix (Credit + Folders bridge)

| Surface | Empty | Loading | Error (FAIL + next) | Needs judgment |
|---------|-------|---------|---------------------|----------------|
| 3 Credit | Zero balance + Top up | Loading balance / Requesting credit… | Load FAIL; faucet/issuer FAIL | Expansion surprise |
| 2 Folders (U2) | (U1) | (U1) | Add FAIL → Open Credit | Expansion REVIEW → Top up |

---

# Operate-or-FAIL copy pattern (binding)

Every FAIL block:

1. **FAIL —** what failed (buyer words)  
2. **Why** (one line, no ADR dump)  
3. **Next:** concrete in-app action  
4. **Primary button** that navigates or retries  

Never: blank swallow · terminal-only path · localhost WUI link · “see docs/00-decision.md” · fake XMR success.

---

# Checklist — U2 wireframes

- [x] Credit balance visible (plain language + denomination)  
- [x] Zero / empty + Top up  
- [x] Top-up faucet stub (no live XMR fields)  
- [x] Loading balance + redeeming  
- [x] Load FAIL + redeem FAIL  
- [x] Success / updated balance after faucet  
- [x] Expansion REVIEW  
- [x] Opaque wallet reject  
- [x] Folders → Open Credit on zero credit  
- [x] Settings stub notes U3–U5; Credit not deferred  
