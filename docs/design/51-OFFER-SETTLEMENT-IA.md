# Offer Used → settlement — information architecture (#28)

**Status:** Design DoD 2026-09-24 PT (~2:20am PT)  
**Cite:** [#28](https://github.com/themark-net/leasegrid-c/issues/28) · tip ≥ **`83b3e66`** · locks #27 / #38 / #34  
**Companion:** [50](50-OFFER-SETTLEMENT-JOURNEY.md) · [52](52-OFFER-SETTLEMENT-WIREFRAMES.md)

---

## Place map (desktop Sync — post-#38)

```
Leasegrid Sync
├── Folders (PRIMARY after join)
│   ├── Magic Folder list / Add folder
│   └── Offer storage on this disk          ← #28 surface lives HERE
│       ├── Disk pie (Used / Kept / Offered)     [disk-local — keep]
│       ├── Hosted for others (Offer consumed)  [settlement-relevant — add]
│       └── Chip: Credit & settlement → More/Credit
├── Storage servers (PRIMARY roster)
│   └── list / status / Add / Disconnect        [#27 — unchanged]
├── More
│   ├── Credit                                  [#34 — secondary; deep-link target]
│   │   ├── Buyer balance + Top up              [unchanged entry]
│   │   └── Host settlement (optional strip)    [#28 visibility only]
│   ├── Recovery / Settings / …                 [unchanged]
│   └── Invite share (short code + QR + Copy)   [#32/#38 — unchanged]
└── Welcome / Join (clean home only)            [#27 Join-first]
```

**IA rule:** #28 does **not** add a primary chrome tab. Settlement visibility is either (a) on the Offer box or (b) under More → Credit via deep-link.

---

## Offer box — two meters (binding)

| Region | Object name (suggest) | Data source class | Rank |
|--------|----------------------|-------------------|------|
| Disk pie + legend | `diskPie` / `offerLegend` (existing) | Local `disk_usage` + `reserved_space` | Keep |
| Hosted / Offer consumed | `offerHostedStrip` (new) | Local storage accounting for shares hosted **for others** (settlement-relevant) | Add below pie |
| Credit & settlement chip | `offerSettlementChip` (new) | Navigation only → More → Credit | Add |
| Offer slider / percent | existing | Unchanged | Keep |

**Do not** merge Hosted into the pie’s gray Used slice. **Do not** replace Offered with Hosted.

---

## Chip / deep-link contract

| From | Control | To | Notes |
|------|---------|----|-------|
| Offer box | **Credit & settlement** | More → Credit place | Same Credit surface as #34; focus host-settlement subsection if present |
| Folders unpaid cue (existing) | Open Credit | More → Credit | Preserve #38 wayfinding; do not compete |
| Credit | Top up | Existing Top-up dialog | Entry remains **Credit → Top up** (#34 lock) |

**Anti-promotion:** Chip must not promote Credit into Folders/Servers primary chrome. Badge on More is OK if already used elsewhere; do not invent a red “earn $” badge.

---

## Credit place — host settlement subsection (optional strip)

| Element | When shown | Content |
|---------|------------|---------|
| Buyer Credit card | Always (existing) | Balance, Refresh, Top up |
| Host settlement strip | When this home Offers disk **and** rail can answer | Leases / spent accepted toward settlement; `tokens_settled` / pending **if** issuer or local settle bundle exposes it |
| Host settlement missing | Offer on + rail silent | Honest **missing** copy (not unknown spinner forever; not zero-earnings green) |
| Host settlement N/A | Offer off / client-only join | Hide strip entirely |

**Vocabulary on Credit (host strip):**

- Prefer: “Hosted for others,” “Accepted toward settlement,” “Settled (stagenet ledger)”  
- Avoid: “Profit,” “Payout sent,” “Wallet balance” unless a real payout rail exists (it does not in Sync MVP)

---

## Ranking vs #38 lead journey

| Step | Place | #28 impact |
|------|-------|------------|
| Join | Welcome | None |
| Servers | Storage servers | None (no settlement chips on roster rows in this slice) |
| Offer / store | Folders Offer box | **Primary #28 surface** |
| Credit | More → Credit | Deep-link target + optional host strip |

---

## Empty vs missing vs FAIL (IA semantics)

| State | Meaning | UI |
|-------|---------|----|
| **Empty** | Offer on; accounting OK; zero hosted | “Nothing hosted for others yet.” — calm empty |
| **Missing** | Offer on; settlement fields not provided by this network/build | “Settlement status not available on this network yet.” — not a balance |
| **FAIL** | Load attempted; error/timeout | In-window FAIL + Retry (see journey) |
| **Stale** | Last-known hosted figure kept after refresh FAIL | Stale hint + Retry — never silent |

---

## Android / other surfaces

Desktop Sync is primary. P4-A Android is read-first and **out** of this Design implement slice (see non-goals). Do not invent Offer settlement chrome on Android here.

---

## One-liner

> #28 IA: Hosted/Offer-consumed strip on Offer + deep-link to Credit under More; disk pie stays disk-local; no Credit tab promotion.
