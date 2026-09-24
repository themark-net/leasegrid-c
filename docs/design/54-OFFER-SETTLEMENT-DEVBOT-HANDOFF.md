# Offer Used → settlement → DevBot / Build handoff (#28)

**Status:** Design DoD 2026-09-24 PT (~2:20am PT) — ready for PM RELEASE implement  
**Cite:** [#28](https://github.com/themark-net/leasegrid-c/issues/28) · tip ≥ **`83b3e66`** (`83b3e66d4afdc7499619a43af82b78c54b6dd939`) · #27 @ `639163a` · #34 @ `442b76e` · #38 @ `83b3e66`  
**Design refs:** [50](50-OFFER-SETTLEMENT-JOURNEY.md) · [51](51-OFFER-SETTLEMENT-IA.md) · [52](52-OFFER-SETTLEMENT-WIREFRAMES.md) · [53](53-OFFER-SETTLEMENT-NON-GOALS.md) · pointer `docs/09-ui-track-OFFER-SETTLEMENT-POINTER.md`  
**Lane:** DevBot **Build-first on nimo** (Cursor only if Build blocked).  
**Do not:** implement in the Design pass; contact Mark; ship WUI; promote Credit tab; invent new payment rails; rewrite `10`–`49` bodies.

**Supersedes:** #27 pack `43` footnote (“#28 log-only”) — full Design is this pack.

---

## Product DoD (implement must prove)

1. **Disk vs hosted distinct:** Offer pie remains disk-local Used / Kept-free / Offered. A separate **Hosted for others / Offer consumed** strip shows settlement-relevant usage.  
2. **Honest empty:** Zero hosted → calm empty copy (“Nothing hosted…”), not FAIL, not fake zero earnings.  
3. **Honest missing:** When ZKAP/settlement fields are absent on this network/build → missing copy (not unknown forever; not fabricated balances).  
4. **Honest FAIL:** Accounting / settlement load errors → in-window FAIL + Retry; pie/slider stay operable.  
5. **Deep-link:** Offer chip **Credit & settlement** opens existing Credit place under More (reuse #34 surfaces).  
6. **Credit secondary:** Credit stays under More — **no** primary-tab promotion (#38).  
7. **Top up entry unchanged:** Buyer top-up remains Credit → Top up (#34). No second top-up chrome on Offer.  
8. **Host settlement strip (optional):** On Credit, if this home Offers disk and rails answer, show accepted/settled/pending **from real data only**; else FAIL/missing. Payout remains out-of-band — Sync does not invent XMR earnings.  
9. **Operate-or-FAIL:** Every new control operates or FAIL in-window; operator copy only; no WUI; no Marketing.  
10. **Tip base** ≥ **`83b3e66`**. Stagenet only; mainnet refused.

---

## Suggested files / areas to touch (Sync tree @ tip `83b3e66`)

| Area | Likely paths | Why |
|------|--------------|-----|
| Offer box / pie | `src/leasegrid_sync/app.py` (`_build_offer_box`, `_make_disk_pie`, offer refresh) | Hosted strip + chip; keep pie disk-local |
| Disk accounting | `src/leasegrid_sync/backend.py` (`DiskSlices`, `read_disk_offer`) | Do not overload `used` for hosted; add separate hosted metric source |
| Hosted / share usage | Tahoe storage accounting / local node stats (implement chooses honest source) | Settlement-relevant consumed capacity |
| Settlement visibility | `src/leasegrid_zkap/` settlement / spent-set / issuer ledger clients already on tip | Read-only visibility; no new settle protocol |
| Credit place | `src/leasegrid_sync/app.py` Credit tab; `credit.py` | Optional host settlement strip; preserve Top up |
| Navigation | More menu → Credit | Deep-link from Offer chip |
| Tests | `tests/` | Distinct disk vs hosted; empty/missing/FAIL; chip → Credit; no Credit tab promotion |

Stack remains Gridsync-class PyQt Sync — **no** Electron, **no** Tahoe WUI.

---

## Recommended implement order

1. Define hosted/Offer-consumed data source (honest; FAIL if unavailable) — do **not** reuse pie `used`  
2. Hosted strip UI on Offer box (PASS / empty / missing / FAIL)  
3. Chip → More → Credit deep-link  
4. Optional Host settlement strip on Credit (rail-backed only)  
5. Regression: #34 Top up; #38 Credit-under-More; #27 Servers; Offer pie disk-local  
6. Dogfood on nimo AppImage / lab friendnet (stagenet)

---

## Dogfood steps (nimo)

| # | Step | PASS |
|---|------|------|
| 1 | Joined home; Offer disk > 0% | Pie shows Used / Kept / Offered (disk-local) |
| 2 | No shares hosted yet | Hosted strip = honest empty (not FAIL) |
| 3 | After peer stores to this node (lab) | Hosted strip shows consumed capacity |
| 4 | Click **Credit & settlement** | Lands on More → Credit (#34 place) |
| 5 | Credit → Top up (lab/stagenet) | #34 path still works; Credit not a primary tab |
| 6 | Kill hosted accounting source | Offer shows FAIL + Retry; pie/slider still work |
| 7 | Settlement fields unavailable | Missing copy — no fake XMR earnings |
| 8 | Home with Offer unchecked / no storage | Host settlement strip hidden on Credit |

---

## Operate-or-FAIL examples

| Case | Banner spirit | Next |
|------|---------------|------|
| Hosted load error | could not load how much you are hosting… | Retry; pie still works |
| Settlement load error | could not load settlement status… | Retry; do not assume paid |
| Credit navigation fail | Credit place could not open… | Use More → Credit; Retry |
| Zero hosted | Nothing hosted for others yet. | (not FAIL) |

---

## Explicit rejects

- New payment rails / mainnet wallet  
- Credit promoted to primary tab  
- Fake host earnings / green paid without data  
- Merging Hosted into disk Used pie slice  
- Rewriting #34 Top up entry  
- #33 / #26 / #30 work in this slice  
- Tahoe WUI Next  
- Mark drip from implement bots  
- Marketing copy

---

## Exit checklist (DevBot reports)

- [ ] Tip ≥ `83b3e66`  
- [ ] Screenshot: Offer pie disk-local + Hosted strip distinct  
- [ ] Empty hosted honest; missing settlement honest; FAIL + Retry  
- [ ] Chip opens Credit under More  
- [ ] Credit still under More; #34 Top up intact  
- [ ] No fabricated XMR host earnings  
- [ ] #27 Servers + #38 lead journey preserved  
- [ ] FAIL in-window; no WUI; operator copy only  

**#28 implement FAIL examples:** Hosted equals pie Used; Credit tab promoted; fake earnings; new rails; Top up moved onto Offer only; Mark contacted.

---

## One-liner

> Implement #28 on tip ≥ `83b3e66`: Offer shows disk Used vs Hosted-for-others; link to Credit/ZKAP settlement visibility under More; honest empty/missing/FAIL; no new rails; Build-first on nimo.
