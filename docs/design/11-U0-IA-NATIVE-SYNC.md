# U0 — Information architecture (native Sync)

**Status:** Design DoD 2026-09-19 PT  
**Cite:** `docs/09-ui-track.md` · Gridsync-class desktop IA · CEO U0 RELEASE 2026-09-19  
**Product chrome:** Buyer/operator copy only — no ADR dumps, no localhost board URLs, no Tahoe WUI embeds.

---

## Window chrome

```
┌─ Leasegrid Sync ─────────────────────────────────[─][□][×]─┐
│  [Folders]  [Credit]  [Recovery]  [Settings]     ☁ Sync · ✓ │
│─────────────────────────────────────────────────────────────│
│                                                             │
│                     (place content)                         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

| Element | Spec |
|---------|------|
| Title bar | `Leasegrid Sync` (+ optional grid short name after join) |
| Primary nav | **Top tabs** (Gridsync-class) **or** left **sidebar of places** — pick one in U1 spike; do not ship both competing |
| Status chip | Connection: Connecting / Connected / Offline / FAIL — always visible in chrome |
| Tray | App remains tray-capable when window closed (Linux first) |
| Density | Desktop folder manager, not marketing landing page |

**IA choice for U0 wireframes:** top tabs of places (Folders default). Sidebar equivalent is acceptable if Gridsync fork already has it — same place set.

---

## Places (primary nav)

| Place | Role | Primary objects |
|-------|------|-----------------|
| **Folders** | Home. Magic Folder list, sync status, add folder | Folder rows, status, Add folder |
| **Credit** | Remaining capacity; Top up | Balance card, Top up, history stub |
| **Recovery** | Export / import recovery key | Scary gate, file pickers |
| **Settings** | Autostart; transport policy note; about | Toggles, design-flag callout |

### Folders (default after first-run)

- List of Magic Folders with: name, local path, status, last sync, actions (Open local / Pause / Remove)  
- Empty state CTA: **Add folder**  
- Dropbox/Gridsync metaphor: local directory ↔ encrypted sync, not a remote file browser  

### Credit

- Plain-language remaining **GiB-share-months**  
- **Top up** → faucet stub now → XMR when U5 / gate 0c  
- No opaque ZKAP wallet conversion UI  
- Link to Pricing honesty (short in-panel note, not a separate theology page)  

### Recovery

- Export (primary) and Import  
- Scary “loss = total loss” gate before export completes  
- Post-import: folders remote-only until local path chosen (Gridsync pattern)  

### Settings

- Autostart on login  
- **Transport policy note** (Tor vs sync) as a **visible design flag** — not a hidden advanced toggle buried three menus deep  
- Version / grid name / Quit  

---

## Tray

| Affordance | Behavior |
|------------|----------|
| Left-click / Open | Show main window on Folders (or last place) |
| Status | Icon reflects Connected / Syncing / Offline / FAIL |
| Menu | Open Sync · Folders · Credit · Pause all (optional) · Export recovery key · Quit |
| Close window | Hide to tray (Linux); do not quit unless Quit |

Tray is part of the product, not an afterthought — Sync is always-on folder watch.

---

## First-run (wizard, not a permanent place)

First-run is a **modal wizard** over an empty shell (or dedicated window) until invite PASS + threat ACK. It is **not** a fifth permanent tab. After completion, wizard does not reappear unless reset / fresh install / import recovery.

Wizard steps (IA):

1. Threat-model + invite code  
2. Optional first folder  
3. Nudge: export recovery key (can defer once with scary reminder)  

---

## What is NOT primary nav

| Reject as primary | Why |
|-------------------|-----|
| Tahoe WUI / “Open web UI” | Forbidden as product UI (`09-ui-track.md`) |
| Capability / raw cap browser | Non-goal for MVP; confuses Dropbox metaphor |
| Introducer / storage-server admin | Operator (Leasegrid Node) Phase 2 |
| Issuer mint dashboards | Not buyer chrome |
| Localhost debug boards / lab URLs | Never in product chrome |
| ADR / corner-C essays | Docs for humans reading git; not in-app dumps |
| Marketing landing / pricing SPA | Web optional later; not Sync nav |
| Mobile-style bottom tabs only | Desktop window first |
| Electron shell as default | Requires Gridsync-blocker writeup first |

Advanced power links (if any) live under Settings → Advanced expander, still operate-or-FAIL, still no WUI embed.

---

## Navigation rules

1. **Folders is home** after first-run.  
2. Credit / Recovery / Settings are one click from chrome — no scavenger hunt for balance or keys.  
3. Threat and transport honesty appear on **first-run** and **Settings**, not only in README.  
4. Deep links from FAIL copy jump to the place that fixes the failure (e.g. Add folder FAIL → Credit).  
5. Operate-or-FAIL: every chrome control either performs or explains FAIL + next in-window.

---

## Mapping to `09-ui-track.md` screens

| UI-track screen | IA place / surface |
|-----------------|--------------------|
| 1 First-run / invite | Wizard (pre-places) |
| 2 Folders | Place: Folders |
| 3 Credit | Place: Credit |
| 4 Recovery | Place: Recovery |
| 5 Settings | Place: Settings |

---

## Brand / naming in chrome

| Name | Use |
|------|-----|
| Leasegrid Sync | Window title, installer, tray tooltip |
| Leasegrid Node | Mention only in Settings About (“Operators run Leasegrid Node — Phase 2”) — no Node screens in U0 |
