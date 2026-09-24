# Offer Used → settlement — journey (#28)

**Status:** Design DoD 2026-09-24 PT (~2:20am PT)  
**Cite:** issue [#28](https://github.com/themark-net/leasegrid-c/issues/28) · tip ≥ **`83b3e66`** (`83b3e66d4afdc7499619a43af82b78c54b6dd939`) · CEO/PM RELEASE Design · post-#38 main  
**Product:** Native **Leasegrid Sync** (desktop). Offer host on Folders; settlement visibility reuses Credit / ZKAP rails already shipped.  
**Supersedes:** [#27](https://github.com/themark-net/leasegrid-c/issues/27) pack `43` footnote (“#28 log-only”) — **#28 is now in scope for this pack.**

---

## Founder need (binding)

When **Offering** disk, the UI must show **what’s being used** — consumed Offer capacity / shares hosted for others — in a way that can **link to payment / settlement** (Credit, ZKAP leases, host earnings path).

Today the Offer pie is **disk-local only** (`Used` / `Free` / `Offered` from local FS + `reserved_space`). That is not enough once hosts are paid: operators need usage that maps to “what I’m hosting for the grid” and later to money.

---

## North star (one sentence)

An operator who Offers disk sees **disk Used** and **Offer consumed / hosted-for-others** as distinct facts, with an honest path into existing **Credit / ZKAP / settlement** visibility under More — never a fake balance, never a new payment rail.

---

## Design locks (carry forward — do not reopen)

### From #27 (SHIPPED @ `639163a`)

| Lock | Rule |
|------|------|
| Servers primary | Roster / Add / Disconnect stand |
| Folders-first + Offer pie | Stand; pie remains the disk-offer control |
| Join-first | Empty clean home |
| Storage furl Path B | Stands |

### From #38 (SHIPPED @ `83b3e66`)

| Lock | Rule |
|------|------|
| Lead journey | Join → Servers → Offer/store → Credit |
| Credit secondary under More | **Do not** promote Credit to a primary tab |
| #32 short code + QR + Copy | Unchanged |
| Visual polish locks | Unchanged |

### From #34 / U5 (SHIPPED @ `442b76e`)

| Lock | Rule |
|------|------|
| Credit → Top up | Quote → pay → redeem (stagenet / lab fake; mainnet refused) |
| Entry still Credit → Top up | Do not invent a second top-up surface on Offer |
| No new payment rails | #28 **ties Offer Used → settlement visibility** on the existing Credit/ZKAP path only |

### Payment vocabulary (cite `docs/07-payment.md` — do not redesign)

| Term | Meaning for this slice |
|------|------------------------|
| **Disk Used** | Local filesystem bytes occupied on this disk (pie gray slice) — **not** settlement |
| **Offered** | Free space reserved for friendnet storage (`reserved_space` complement) — capacity committed |
| **Offer consumed / Hosted for others** | Settlement-relevant: shares / capacity this node is storing for buyers (maps toward ZKAP leases accepted → later `tokens_settled`) |
| **Credit** | Buyer prepaid GiB-share-months (ZKAP tokens) — More → Credit |
| **Settlement** | Node sends spent `t` to issuer (`POST /v0/settlement`); ledger `tokens_settled` per `(nodeid, epoch)` — **visibility only** in Sync; payout remains out-of-band / Phase 2 Node kit |

---

## Pain → target

| Pain at tip `83b3e66` | Target |
|------------------------|--------|
| Offer legend says **Used · Free · Offered** and hint explains Offered as free space for friendnet — but **Used is OS disk used**, which mixes OS files + Tahoe storage + unrelated data | Keep disk pie as **disk-local**; add a **separate Hosted / Offer-consumed** strip that is settlement-relevant |
| No link from Offer → payment/settlement | Chip / button: **Credit & settlement** → opens existing Credit place under More (and host settlement strip if data exists) |
| No host-earnings / lease status on Offer | Show **only** what existing rails expose on stagenet; if absent → honest **missing / empty** (not “unknown”, not green fake) |
| Risk of inventing mint/admin / payout chrome | Reuse Credit surfaces (#34); no issuer admin; no mainnet wallet; no Phase 2 Node payout dashboard |

---

## Happy path A — Offer host sees consumed capacity

| Step | Place | Operator does | System does | Exit |
|------|-------|---------------|-------------|------|
| 0 | Folders (PRIMARY) | Already joined; Offer disk on | Offer box + disk pie load | Pie visible |
| 1 | Offer box | Glances pie | Disk-local: Used / Free-kept / Offered | Disk facts OK |
| 2 | Offer box | Sees **Hosted for others** strip | Shows consumed Offer capacity (bytes or share-months) when local/storage accounting available | Consumed visible **or** honest empty |
| 3 | Offer box | Clicks **Credit & settlement** (or “View Credit”) | Navigates to More → Credit (existing place); optional scroll/focus to host-settlement subsection if present | Credit place open |
| 4 | Credit (More) | Reviews buyer balance / Top up as today; sees host lease/settlement status **only if rail data exists** | Reuses #34 load/FAIL; no fabricated earnings | Steady **or** FAIL in-window |

---

## Happy path B — Nothing hosted yet (honest empty)

| Step | Place | System shows | Exit |
|------|-------|--------------|------|
| 1 | Offer box | Disk pie normal; Hosted strip: **“Nothing hosted for others yet.”** (empty, not FAIL) | Operator understands Offer is idle |
| 2 | Chip still works | Opens Credit under More | Credit balance may be zero / unpaid — separate from host empty |

**Rule:** Empty hosted ≠ FAIL. Missing settlement data when rails should answer ≠ empty — that is **FAIL / missing** (see FAIL paths).

---

## Happy path C — Buyer Credit path unchanged (#34)

| Step | Place | Buyer does | System does | Exit |
|------|-------|------------|-------------|------|
| 1 | More → Credit | Opens Credit | Balance load (#34) | Balance **or** FAIL |
| 2 | Credit | Top up | Quote → pay → redeem stagenet | Balance updates **or** FAIL |
| 3 | Offer | Optional deep-link back | Offer does not become a second Top-up UI | #34 entry preserved |

---

## Distinguish: disk Used vs Offer consumed (binding)

```
  ┌─────────────────────────────────────────────────────────┐
  │ DISK PIE (local FS — keep)                              │
  │  Used     = OS disk_usage used (all local files)        │
  │  Kept     = free bytes not offered                      │
  │  Offered  = free bytes reserved for friendnet storage   │
  └─────────────────────────────────────────────────────────┘
                          ≠
  ┌─────────────────────────────────────────────────────────┐
  │ HOSTED / OFFER CONSUMED (settlement-relevant — add)     │
  │  Bytes or share-capacity this node stores for buyers    │
  │  Maps toward ZKAP leases accepted / settleable spent-t  │
  │  NEVER paint this as the pie’s gray “Used” slice        │
  └─────────────────────────────────────────────────────────┘
```

**Copy rule:** Legend and tooltips must not call disk Used “hosted for the grid.” Hosted strip must not say “disk used.”

---

## Settlement visibility (what Sync may show)

| Surface | Allowed content | Forbidden |
|---------|-----------------|-----------|
| Offer → Hosted strip | Consumed capacity; link into Credit/settlement | Fake XMR earnings; mint controls |
| Credit place (More) | Existing buyer Credit + Top up (#34); optional **Host settlement** subsection: leases accepted / `tokens_settled` / pending **if** local node or issuer ledger answers | New wallet UX; mainnet; payout address editor; issuer admin |
| Chip navigation | Deep-link Offer → Credit under More | Promoting Credit to primary tab beside Folders/Servers |

When host settlement fields are **not available** on this build/stagenet:

```
Host settlement: not available on this network yet.
Offer consumed still shows local hosted capacity when known.
Next: use Credit for buyer balance; ask operator if settlement should be on.
```

Never invent a green “earned 0.12 XMR” without a real source.

---

## Operate-or-FAIL

| Control | PASS | FAIL (in-window) | Next |
|---------|------|------------------|------|
| Load disk pie | Used/Kept/Offered update | Disk unreadable | Retry; check storage path |
| Load Hosted / Offer consumed | Number or honest empty | Accounting error / timeout | Retry; leave last-known with stale hint **or** clear FAIL — never silent blank green |
| Credit & settlement chip | Opens Credit under More | Navigation broken | FAIL + Retry; keep Offer usable |
| Credit balance / Top up | Existing #34 behavior | Existing #34 FAIL copy | Retry / check issuer |
| Host settlement subsection | Shows rail-backed figures | Issuer/node unreachable | FAIL + Retry; **no** fabricated pending payout |

**Rule:** Operator copy only. Every control operates or FAIL in-window. No “check the terminal.” No Tahoe WUI. No Marketing copy.

---

## FAIL paths (operator-visible)

### F1 — Hosted accounting down

```
FAIL — could not load how much you are hosting for others.
Next: Retry; Offer disk slider and disk pie still work.
[ Retry ]←primary
```

### F2 — Settlement visibility down (rails expected but silent)

```
FAIL — could not load settlement status.
Buyer Credit may still load separately. Earnings are not shown until this succeeds.
Next: Retry; check network / issuer; do not assume you were paid.
[ Retry ]←primary
```

### F3 — Deep-link target missing

```
FAIL — Credit place could not open.
Next: use More → Credit; Retry.
[ Retry ]←primary
```

---

## Out of journey (see non-goals)

- New payment rails / mainnet wallet / Mark ops  
- #33 introducer marketplace · #26 Android EXTRA_RECOVERY · #30 plant↔maximum MF HTTP 500  
- Phase 2 Leasegrid Node payout dashboard as product in this slice  
- Rewriting #34 Top-up journey  

---

## One-liner

> #28: On Offer, separate disk Used from Offer-consumed/hosted-for-others; link into existing Credit/ZKAP settlement visibility under More; honest empty/missing; no new rails; tip ≥ `83b3e66`.
