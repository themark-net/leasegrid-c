# Offer Used → settlement — ASCII wireframes (#28)

**Status:** Design DoD 2026-09-24 PT (~2:20am PT)  
**Cite:** [#28](https://github.com/themark-net/leasegrid-c/issues/28) · tip ≥ **`83b3e66`**  
**Shell:** Desktop Leasegrid Sync. No Tahoe WUI. Operator copy only. No fake green.

Locks drawn in: disk pie stays disk-local; **Hosted for others** is separate; Credit stays under More (#38); Top up entry remains Credit → Top up (#34).

---

## W1 — Offer box PASS (hosting for others)

```
┌─ Leasegrid Sync ──────────────────────────────────────────┐
│  [Folders]←primary   [Storage servers]   [More ▾]         │
├───────────────────────────────────────────────────────────┤
│  Folders                                                  │
│  ┌─ Magic Folders ─────────────────────────────────────┐  │
│  │  docs/          Syncing · 3 peers                   │  │
│  │  [ Add folder ]←primary                             │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                           │
│  ┌─ Offer storage on this disk ────────────────────────┐  │
│  │                                                     │  │
│  │   (pie)     Offering 40% of this disk               │  │
│  │  Used█                                                   │
│  │  Kept░   Used  ·  Kept free  ·  Offered             │  │
│  │  Offered▓                                              │  │
│  │            Offered is free space this device will   │  │
│  │            store for the friendnet.                 │  │
│  │  Offer [========●-------] 40%                       │  │
│  │                                                     │  │
│  │  ── Hosted for others (settlement) ───────────────  │  │
│  │  Hosting 12.4 GiB for the friendnet                 │  │
│  │  (~3.1 GiB·share·mo toward settlement this epoch)   │  │
│  │  [ Credit & settlement ]←secondary                  │  │
│  │                                                     │  │
│  └─────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────┘
```

**Notes**

- Pie legend = **disk-local** only. Do not label gray Used as “hosted.”
- Hosted strip uses settlement-relevant units when available; bytes alone OK if share-months not exposed yet.
- Chip navigates to More → Credit (existing place). Does **not** open a new wallet.

---

## W2 — Offer box empty hosted (honest empty, not FAIL)

```
│  ┌─ Offer storage on this disk ────────────────────────┐  │
│  │   (pie)     Offering 25% of this disk               │  │
│  │            Used  ·  Kept free  ·  Offered           │  │
│  │  Offer [=====●----------] 25%                       │  │
│  │                                                     │  │
│  │  ── Hosted for others (settlement) ───────────────  │  │
│  │  Nothing hosted for others yet.                     │  │
│  │  When buyers store shares here, usage shows up      │  │
│  │  for settlement.                                    │  │
│  │  [ Credit & settlement ]                            │  │
│  └─────────────────────────────────────────────────────┘  │
```

**Rule:** Calm empty. No red FAIL. No “0.00 XMR earned.”

---

## W3 — Settlement / Credit data missing (honest missing)

```
│  │  ── Hosted for others (settlement) ───────────────  │  │
│  │  Hosting 12.4 GiB for the friendnet                 │  │
│  │  Settlement status: not available on this network   │  │
│  │  yet. Hosted size still shown from local storage.   │  │
│  │  [ Credit & settlement ]                            │  │
```

**Rule:** Missing ≠ unknown spinner forever. Missing ≠ invent pending payout.

---

## W4 — FAIL hosted accounting (operate-or-FAIL)

```
│  │  ── Hosted for others (settlement) ───────────────  │  │
│  │  FAIL — could not load how much you are hosting     │  │
│  │  for others.                                        │  │
│  │  Next: Retry. Disk Offer slider and pie still work. │  │
│  │  [ Retry ]←primary                                  │  │
│  │  [ Credit & settlement ]                            │  │
```

Pie + Offer slider remain operable.

---

## W5 — Credit under More (deep-link target; #34 preserved)

```
┌─ Leasegrid Sync ──────────────────────────────────────────┐
│  [Folders]   [Storage servers]   [More ▾]←open            │
│     More menu:  Credit  ·  Recovery  ·  Settings …        │
├───────────────────────────────────────────────────────────┤
│  Credit                                                   │
│  ┌─ Buyer credit ──────────────────────────────────────┐  │
│  │  About 18 GiB of synced files for a month           │  │
│  │  (friendnet 3-of-10).                               │  │
│  │  [ Refresh ]              [ Top up ]←primary        │  │
│  │  Recent: stagenet top-up · …                        │  │
│  └─────────────────────────────────────────────────────┘  │
│  ┌─ Host settlement ───────────────────────────────────┐  │
│  │  This device Offers disk.                           │  │
│  │  Accepted toward settlement (this epoch): 40 tokens │  │
│  │  Settled on ledger: 40 · Pending: none              │  │
│  │  Payout: out-of-band (not shown in Sync).           │  │
│  │  [ Refresh settlement ]                             │  │
│  └─────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────┘
```

**If settlement strip cannot load**

```
│  ┌─ Host settlement ───────────────────────────────────┐  │
│  │  FAIL — could not load settlement status.           │  │
│  │  Buyer Credit above may still be valid.             │  │
│  │  Do not assume you were paid.                       │  │
│  │  [ Retry ]←primary                                  │  │
│  └─────────────────────────────────────────────────────┘  │
```

**If this home does not Offer disk** — hide Host settlement strip entirely.

**Anti-patterns (FAIL Design)**

```
  ✗ Credit as third primary tab: [Folders] [Servers] [Credit]
  ✗ Green “Earned 0.12 XMR” with no rail source
  ✗ Top up button only on Offer (bypassing Credit → Top up)
  ✗ “Unknown” gray forever with no Retry
  ✗ Merging Hosted into pie Used slice
```

---

## W6 — Lead journey context (#38 unchanged)

```
Join → Storage servers → Offer/store (Folders + pie + Hosted strip) → Credit (More)
```

#28 adds Hosted strip + chip inside Offer/store. It does not reorder the lead journey.

---

## Copy chips (operator-only)

| ID | Copy |
|----|------|
| Hosted PASS | `Hosting {size} for the friendnet` |
| Hosted empty | `Nothing hosted for others yet.` |
| Settlement missing | `Settlement status: not available on this network yet.` |
| Chip | `Credit & settlement` |
| Host strip header | `Host settlement` |
| Payout honesty | `Payout: out-of-band (not shown in Sync).` |

---

## One-liner

> Wire #28: Offer shows disk pie + separate Hosted strip + chip to Credit under More; empty/missing/FAIL honest; no fake earnings; no Credit tab promotion.
