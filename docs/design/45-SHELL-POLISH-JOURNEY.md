# Shell polish — journey (Join → Servers → Offer/store → Credit)

**Status:** Design DoD 2026-09-23 PT (~11:26pm PT)  
**Cite:** issues [#38](https://github.com/themark-net/leasegrid-c/issues/38) · [#32](https://github.com/themark-net/leasegrid-c/issues/32) · tip ≥ **`f46ab7c`** (`f46ab7ca423b72d7e5422ac46ccb2143ae881cfb`) · CEO RELEASE 2026-09-23 evening · **#27** SHIPPED @ `639163a` · **#34** SHIPPED @ `442b76e`  
**Product:** Native **Leasegrid Sync** (desktop buyer). CrashPlan folders-first shell remains primary after join (P1).  
**Preserve:** #27 Servers primary + empty Join-first + both Add paths; #34 Credit XMR top-up under **More** (secondary); Folders + Offer pie; no new payment rails.

---

## Founder problem (binding cite)

Founder (RELEASE #38, 2026-09-23 evening): Sync is **functionally better** after Servers/Join (#27) and Credit XMR (#34), but still **ugly**, and the **flow is awkward**.

**MVP ask:** make the shell feel coherent on the lead journey **Join → Servers → Offer/store → Credit** — visual cleanup + flow straighten — without inventing new product rails.

Invite/Join (#32) is **in this same Design slice**: wrap human invite as **short code + QR + Copy**; never dump **raw introducer FURL** as the primary share surface.

---

## North star (one sentence)

A buyer can Join a friendnet, manage **Storage servers**, Offer/store on Folders, and open **Credit** under More — with one coherent lead path, readable chrome, and invites that normal people can share (short code / QR / Copy) without seeing a raw FURL.

---

## Design locks (carry forward — do not reopen)

### From #27 (tip lineage ≥ `639163a`)

| Lock | Rule |
|------|------|
| Servers = primary roster | Storage servers lists hosts / status / Add / Remove — not only “N computers” |
| Join/Add always reachable | After connect, Join/Add remain reachable (Join-once-and-gone = FAIL) |
| Fresh home = empty Join-first | Clean home → Welcome/Join only; already-joined get Folders + Servers + Add |
| Both Add paths | Invite-to-Offer **and** paste/remove storage furl in UX; invite-first ok as implement slice |
| Honest Disconnect | This Sync home only — no forever-remove from friendnet |
| Folders-first + Offer pie | Stand; no WUI; no mainnet; no Android Slice B in this slice |

### From #34 (SHIPPED @ `442b76e`)

| Lock | Rule |
|------|------|
| Credit XMR top-up stays | Quote → pay → redeem (stagenet / lab fake; mainnet refused) |
| Credit secondary under More | Do **not** elevate Credit to primary chrome for shell polish |
| No payment-rail redesign | No new rails in #38 |

### From #32 / #38 (this pack)

| Lock | Rule |
|------|------|
| Share = short code + QR + Copy | Primary invite share surfaces use these three |
| No raw FURL primary | Introducer `pb://…` must not be the default visible share string |
| Both Offer and Join | Sharing an invite **and** accepting one get the human wrap |
| Advanced paste may remain | #27 paste storage furl path stays; friendnet share must not force raw FURL |
| Visual cleanup, not rebrand | Spacing, hierarchy, primary CTAs on lead journey — not Marketing / full skin |

---

## Pain → target (lead journey)

| Step | Pain at tip `f46ab7c` (skim) | Target |
|------|----------------------------------|--------|
| **1. Join** | Join accepts link / short code / QR text, but share side is buried and dumps a long join URL (fragment holds introducer). | Join stays empty-first; paste short code **or** scan/paste from QR; FAIL in-window. |
| **2. Servers** | Roster exists (#27) but chrome feels flat / hoppy; invite-to-Offer “Create invite / Copy invite” is not clearly short-code+QR. | Servers stays primary host place; Add → Invite shows **short code + QR + Copy** (not raw FURL). |
| **3. Offer / store** | Offer pie + Folders work; path from Join→Servers→Folders→Offer is easy to miss amid Settings lecture + More hops. | Folders primary after join; Offer pie visible; clear “next” when hosts empty; store via Add folder. |
| **4. Credit** | Credit under More (#34) — correct rank — but lead journey does not make “when you need capacity, More → Credit” obvious without dumping Credit into primary tabs. | Keep Credit **secondary under More**; light wayfinding from Folders when unpaid blocks (existing Open Credit cue) — no tab promotion. |

---

## Happy path A — Fresh buyer (lead journey)

| Step | Place | Buyer does | System does | Exit |
|------|-------|------------|-------------|------|
| 0 | Launch clean home | Opens Sync | Never-joined → Welcome/Join only | Join-first |
| 1 | Welcome / Join | Ack threat; pastes **short code** or join link / QR payload | Joins friendnet; starts client | Folders **or** FAIL in-window |
| 2 | Folders (PRIMARY) | Sees empty folders + Offer pie; hosts line / Manage servers | Glance chip OK after join | Folders primary |
| 3 | Storage servers | Opens Servers (nav / chip / Manage) | Roster list + **Add** | Servers visible |
| 4 | Add → Invite | Creates invite to Offer | Shows **short code + QR + Copy**; waits for peer Join+Offer | Peer appears **or** FAIL |
| 5 | Offer / store | Adjusts Offer pie; Add folder | Syncs / stores shares on used servers | Steady |
| 6 | Credit (as needed) | More → Credit → Top up | Existing #34 XMR flow | Balance update **or** FAIL |

---

## Happy path B — Share invite (already joined)

| Step | Place | Buyer does | System does | Exit |
|------|-------|------------|-------------|------|
| 1 | Folders or Servers → Invite / Add | Opens Invite share (not buried-only in Settings lecture) | Primary surface: **short code**, **QR**, **Copy** | Shareable without reading FURL |
| 2 | Optional advanced | Expands “Show full join link” if needed | May show join URL (fragment secret) — **still not** raw `pb://` as primary | Advanced optional |
| 3 | Peer Join | Peer pastes short code or scans QR | Join accepts code / QR / link | Peer on friendnet |

**FAIL if:** primary share UI forces the buyer to copy/paste a raw introducer FURL.  
**FAIL if:** Invite share exists only as a long URL line with no short code + QR + Copy.

---

## Happy path C — Awkward-hop reductions (flow straighten)

| Awkward today | Straighten |
|---------------|------------|
| Invite share only under Settings (“Invite others”) while Add invite lives on Servers | One **Invite** share pattern reused: Servers → Add → Invite **and** a clear post-join Invite entry (Folders CTA or More → Invite) — same short code / QR / Copy chrome |
| Chrome: flat Folders / Storage servers / More with weak hierarchy | Stronger hierarchy: primary CTAs on Folders (Add folder, Manage servers); Servers Add prominent; secondary under More |
| Long lecture blocks in Settings compete with Invite | Keep About/lab notes secondary; Invite block is the action |
| Credit discovery | Keep under More; reuse unpaid → Open Credit cue on Folders (do not add Credit tab) |

---

## Journey map (ASCII)

```
  [Launch Sync]
       │
       ▼
  Clean / never-joined?
      YES ──► Welcome/Join (short code / link / QR) ── FAIL ──► in-window FAIL + Retry
       │                         │ PASS
       NO                        ▼
       └──────────► Folders (PRIMARY) + Offer pie
                         │
           ┌─────────────┼──────────────────┐
           ▼             ▼                  ▼
     Storage servers   Offer/store     More → Credit (#34)
     (PRIMARY hosts)   Add folder      (SECONDARY)
           │
           └── Add → Invite: short code + QR + Copy  (#32)
               Add → Paste storage furl               (#27 advanced)
               Disconnect: this home only             (#27)
```

---

## Visual cleanup scope (binding)

**In:** spacing / margins consistency; title hierarchy; primary button weight on Join / Add folder / Add server / Copy; reduce competing flat links; Invite share card layout (code + QR + Copy); FAIL banners in-window.

**Out:** Marketing brand system; full theme rebrand; custom illustration pack; non-Sync surfaces; Mark ops drip.

---

## Operate-or-FAIL (spirit)

| Case | Banner spirit | Next |
|------|---------------|------|
| Bad / expired short code | could not join… | Retry / ask for a fresh invite |
| QR decode / paste empty | invite is empty… | Paste code or link; Retry |
| Share before join | join a friendnet first… | Join, then Invite |
| Bad storage furl (#27) | could not add this storage server… | Retry |
| Credit top-up fail (#34) | existing Credit FAIL copy | Credit → Retry |

No Tahoe WUI as Next. Operator copy only.

---

## One-liner

> #38: straighten Join → Servers → Offer/store → Credit; polish chrome; #32 invite = short code + QR + Copy (no raw FURL primary). Preserve #27/#34 locks.
