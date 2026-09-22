# P4 Android Slice A — Information architecture (phone)

**Status:** Design DoD 2026-09-22 PT  
**Cite:** issue [#23](https://github.com/themark-net/leasegrid-c/issues/23) · tip ≥ `7837ef8` · P1 folders-first (`25`–`29`) · U4 Recovery (`30`–`34`)

---

## Places (phone)

| Place | Rank | Role in Slice A |
|-------|------|-----------------|
| **Folders** | **Primary** | Home after join/import; list of friendnet folders (read) |
| **Welcome / Join** | First-run | Threat HITL + invite; **Import recovery key instead…** |
| **Folder detail** | Primary drill-in | File/dir list inside one folder |
| **File action** | Transient | Download progress / Open with… |
| **More / About** | Secondary | App version; threat/recovery honesty note; link to “export on desktop” |
| **Settings** | Secondary (minimal) | Transport honesty note; clear local cache; storage permission helper |
| **Offer** | **N/A or hidden** on Slice A | Desktop Offer pie is not phone primary; do not force Offer on Android MVP |
| **Credit** | **N/A or deep-secondary** | Unpaid default; payment/XMR **not** required for Slice A |

Folders stay primary. Offer/Credit must not steal chrome on phone Slice A.

---

## Object model (buyer-facing)

| Object | Operator meaning |
|--------|------------------|
| **Threat block** | Honest points; checkbox ACK gates Join |
| **Invite** | Friendnet join string (same family as desktop) |
| **Recovery key file** | U4 `*.leasegrid-recovery` — offline backup; loss = total loss |
| **Folder row** | Named Magic Folder / sync folder visible on friendnet (read) |
| **File row** | Downloadable object inside a folder |
| **Downloaded copy** | Local bytes on device for offline open |
| **New participant** | Phone joins as a **reader / new participant** — not a clone of the desktop write identity |

---

## Primary vs secondary CTA

| Context | Primary CTA | Secondary |
|---------|-------------|-----------|
| Welcome (empty) | **Join friendnet** (after threat ACK) | Import recovery key instead… · What's a friendnet? |
| Folders | Tap folder / pull to refresh | More · Settings |
| Folder detail | Tap file → **Download** or **Open** | Up to Folders |
| Import dialog | **Import recovery key** | Cancel · Browse |
| Download FAIL | **Retry** | Cancel · free space help |
| More | About / Recovery note | “Export recovery key on desktop Sync” (honest — Slice A phone is import-first) |

**Export on phone:** Not required for Slice A Design PASS. Phone is **import / read**. Desktop remains the recovery-key **export** home (U4). Optional later: phone export — stretch only.

---

## Navigation rules

1. After successful join or import → land on **Folders**.  
2. Back from folder detail → Folders.  
3. No Offer pie as default home chrome.  
4. No Credit / Top-up gate before download on unpaid grids.  
5. Import success → Folders with short restore note in-app.  
6. Slice B write affordances (Add folder, Upload, Offer) must **not** appear as half-shipped stubs that look broken — hide or clearly “Coming later” without blocking read path.

---

## Copy hierarchy

| Layer | Tone | Example |
|-------|------|---------|
| Welcome | Calm | “See your Leasegrid folders on this phone. Download files when you need them.” |
| Threat | Honest | Four points; Join disabled until ACK |
| Scary recovery | Direct | “Loss of your recovery key and your devices can mean TOTAL LOSS of access.” |
| Folders empty | Practical | “No folders yet. Join a friendnet or import a recovery key.” |
| Download | Actionable | Progress % · Cancel |
| FAIL | Operate-or-FAIL | FAIL — … Next: … Retry |
| Desktop pointer | Honest, not demoting | “To export a new recovery key or add folders, use Leasegrid Sync on your computer.” |

---

## Slice B park (follow-on only)

| Slice B topic | Status vs Slice A Design |
|---------------|--------------------------|
| Write / Magic Folder–class sync on Android | **Parked** — document only |
| Add folder / upload from phone | Out of Slice A |
| Offer disk from phone | Out of Slice A |
| Blocking Slice A Design PASS on Slice B | **Forbidden** |

Design PASS for #23 Slice A does **not** require Slice B wireframes beyond this park note.

---

## Relationship to prior Design

| Package | Interaction |
|---------|-------------|
| P1 `25`–`29` | Folders-first metaphor → phone Folders list primary |
| U4 `30`–`34` | Recovery import + threat honesty — **reuse**; same file format |
| U2 Credit | Phone: N/A or deep-secondary for Slice A |
| Desktop UI track | Remains primary buyer product; P4 opens mobile read |

P4-A **adds** `35`–`39`. It does **not** rewrite `10`–`34`.
