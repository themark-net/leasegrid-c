# U4 — Information architecture (Recovery + threat HITL)

**Status:** Design DoD 2026-09-21 PT  
**Cite:** issue [#15](https://github.com/themark-net/leasegrid-c/issues/15) · tip `4e1e6bd` · P1 files-first (`25`–`29`) · U0 Recovery surface (`12` §4)

---

## Places (CrashPlan shell)

| Place | Rank | Role in U4 |
|------|------|------------|
| **Folders** | Primary | Post-join home; Offer pie; restored folders land here |
| **Join** | First-run | Threat HITL + invite; **Import recovery key instead…** |
| **Recovery** | Secondary (More) | Export / Import; scary copy; last-export status |
| **Credit** | Secondary / gated | Unchanged P1 — not required for recovery |
| **Settings** | Secondary (More) | May link “Open Recovery”; transport honesty note |

Recovery is **not** demoted to Settings-only. It is a named place under **More**, matching “scary loss” importance without stealing Folders primacy.

---

## Object model (buyer-facing)

| Object | Operator meaning |
|--------|------------------|
| **Threat block** | Four honest points; checkbox ACK gates Join |
| **Recovery key file** | Offline backup of access to folders (+ credit seed); as sensitive as the data |
| **Export gate** | STOP copy + two ACKs + optional passphrase + path + Write |
| **Import** | On blank device or Recovery place; unlocks restore |
| **Restore root** | Where folder trees download after import |
| **New participant** | This device is a *new* sync peer — not a clone of the lost machine |

---

## Primary vs secondary CTA

| Context | Primary CTA | Secondary |
|---------|-------------|-----------|
| Join (empty) | **Join friendnet** (after threat ACK) | Import recovery key instead… · What's a friendnet? |
| Folders (joined) | **Add folder** / Offer slider (P1) | More → Recovery / Settings / Credit* |
| Recovery place | **Export recovery key…** | Import recovery key… |
| Export dialog | **Write recovery key** (after dual ACK) | Cancel · Browse path |
| Import dialog | **Import recovery key** | Cancel · Browse file |
| Export/Import FAIL | **Retry** | Change path / passphrase |

\* Credit visible only when gated friendnet (P1).

---

## Navigation rules

1. After successful join → land on **Folders** (P1), not Recovery.  
2. Optional **one-time nudge** (“Export a recovery key”) may appear on Folders or as a dismissible banner — must not block Add folder / Offer.  
3. Deferred export → later reminder OK; never fake “recovery done” in installer or marketing.  
4. Import success → land on **Folders** with restore note in-window.  
5. Back from Recovery → Folders (P1 back control / More pattern).

---

## Copy hierarchy (recovery-copy UX)

| Layer | Tone | Example |
|-------|------|---------|
| Intro | Calm, practical | “A recovery key restores access if this device is lost. Store it offline.” |
| Scary | Direct, irreversible | “Loss of your recovery key and this device can mean TOTAL LOSS of access.” |
| Gate STOP | Blocking | Dual checkboxes before Write enabled |
| Passphrase empty | Warning | Plaintext file warning visible |
| Success | Actionable | “Written to … Move it somewhere safe and offline.” |
| FAIL | Operate-or-FAIL | FAIL — … Next: … Retry |

---

## What Recovery is **not**

| Anti-pattern | Why rejected |
|--------------|--------------|
| Tahoe WUI / rootcap paste as product | Founder lock |
| “Reset password” affordance | Cryptographically false |
| Credit-first / payment lecture to export | P1 unpaid default |
| Hiding threat only in Settings | Must be first-run HITL |
| Claiming export optional-and-safe | Honest risk if deferred |

---

## Relationship to prior Design

| Package | Interaction |
|---------|-------------|
| U0 `10`–`14` | Baseline Recovery surface + threat on join — U4 **tightens** DoD + CrashPlan fit |
| U2 Credit | Wallet may be inside key; Credit UI stays secondary |
| U3 Installer | Must not claim recovery “included/done” unless U4 walkthrough PASS |
| P1 `25`–`29` | Folders-first chrome; Recovery under More; unpaid default |

U4 **adds** `30`–`34`. It does **not** rewrite U0–P1 bodies.
