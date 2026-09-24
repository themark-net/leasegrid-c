# Shell polish — information architecture

**Status:** Design DoD 2026-09-23 PT (~11:26pm PT)  
**Cite:** [#38](https://github.com/themark-net/leasegrid-c/issues/38) · [#32](https://github.com/themark-net/leasegrid-c/issues/32) · tip ≥ **`f46ab7c`** · #27/#34 locks stand  
**Preserve:** P1 Folders-first; Offer pie; Servers primary roster; Credit under More; U0–U4 / P4-A / #27 bodies cite-only.

---

## Places (desktop Sync) — ranks after polish

| Place | Rank | Role for #38 / #32 |
|-------|------|--------------------|
| **Welcome / Join** | Primary **only** when clean / never-joined | Threat HITL + invite accept (short code / join link / QR payload). Sole surface until Join or recovery import. |
| **Folders** | Primary **after** join | CrashPlan shell: folder list + sync status + **Offer pie**. Entry to Servers. Light unpaid → Credit cue stays secondary. |
| **Storage servers** ★ | First-class (primary host UX) | List / status / **Add** / **Disconnect**. Add → Invite uses #32 share chrome. |
| **Invite share** (surface) | First-class action (not lecture) | **Short code + QR + Copy** — used from Servers → Add → Invite and from a clear post-join Invite entry. Must not live *only* as Settings dump of long URL. |
| **Add server** dialog | Modal from Servers | Path A Invite (#32 wrap); Path B paste storage furl (#27). |
| **Credit** | **Secondary under More** | #34 XMR top-up unchanged. Do not promote to primary tab for polish. |
| **Recovery** | Secondary (More) | U4 — cite only. |
| **Settings** | Secondary (More) | About / notes; may retain advanced export (I2P page) **below** Invite primary actions. |
| Tray | Persist | Open → Folders (joined) or Join (clean); Credit optional. |

★ #27 Mark lock: Servers remains primary host-management UX.  
★ #34: Credit remains secondary under More.

---

## CTA ranks (binding)

| Rank | CTA | Notes |
|------|-----|-------|
| 1 (clean home) | Join friendnet | Only primary |
| 1 (post-join) | Folders / Add folder | CrashPlan primary |
| 1b (host control) | Storage servers → Add / Disconnect | Always reachable |
| 1c (invite share) | Short code + QR + **Copy** | Primary share actions — not raw FURL |
| 2 | Offer pie adjust | Unchanged on Folders |
| 3 | More → Credit / Recovery / Settings | Credit stays here |

**FAIL:** Credit elevated to equal primary tab beside Folders/Servers for this slice.  
**FAIL:** Invite share primary = raw introducer FURL field.  
**FAIL:** Join/Add disappear after first connect.

---

## Invite surfaces (IA) — #32

### Accept (Join)

| Element | Rule |
|---------|------|
| Primary field | Paste **short code** or join link (existing accept kinds OK) |
| Hint copy | “Paste a short code, join link, or text from a QR.” |
| Raw FURL | Optional advanced accept may still parse `pb://` if already supported — **must not** be the placeholder or primary instruction |
| FAIL | In-window; Retry; no WUI |

### Share (Offer / invite someone)

| Element | Rule |
|---------|------|
| **Short code** | Human-readable code displayed large / selectable |
| **QR** | Encodes the shareable invite (code or join URL — implement picks encoding that Join accepts) |
| **Copy** | One primary button copies the short code (or the human join link if code is one-time and expired — prefer code when live) |
| Not primary | Raw introducer `pb://…` must not be the default visible string or the only Copy target |
| Advanced (optional) | “Show full join link” / Export I2P page — secondary; still avoid labeling raw FURL as the invite |
| Placement | Servers → Add → Invite **and** a reachable Invite entry post-join (Folders CTA and/or More → Invite). Settings may keep advanced export but is not the only home for share |

### Paste storage furl (#27 Path B)

Remains on Add → Paste server link (`pb://…` **storage** furl). This is host pinning — **not** the friendnet invite share surface. Do not conflate storage furl paste with introducer FURL sharing.

---

## Chrome layout (target)

```
┌─ Leasegrid Sync ─────────────────────────────────────────┐
│  [Folders]   [Storage servers]          status   [More ▾] │
│                                      Credit / Recovery /   │
│                                      Invite / Settings     │
└───────────────────────────────────────────────────────────┘
```

Notes:
- **Folders** and **Storage servers** are the two primary places post-join.
- **More** holds Credit (secondary), Recovery, Settings; Invite may appear under More **and/or** as Folders/Servers CTA — but Credit must not leave More for a primary tab.
- Status chip remains glance-only after join; click → Storage servers.

---

## Lead journey IA map

```
Join (clean) ──► Folders ──► Storage servers ──► Offer pie / Add folder
                     │                │
                     │                └── Invite: short code + QR + Copy
                     │
                     └── More → Credit (when capacity needed)
```

---

## Honesty / copy constraints

| UI may say | UI must not say |
|------------|-----------------|
| “Copy invite code” / “Scan QR to join” | “Paste this pb:// introducer furl” as primary |
| “Disconnect from this Sync home” | “Remove from the grid forever” |
| “Credit is under More” / unpaid cue | Implying Credit is a primary product tab in this slice |
| “Storage server link (advanced)” for Path B | Calling storage furl the “invite code” |

Operator copy only. FAIL in-window. No ADR theology in chrome.

---

## Non-IA (explicit)

- No Tahoe WUI place  
- No demoting Folders / Offer / Servers  
- No elevating Credit out of More  
- No #28 Offer→payment IA  
- No #33 introducer marketplace  
- No Android Slice B IA in this pack  
- No Mark ops / mainnet rails
