# P4 Android Slice A — Wireframes (mobile ASCII)

**Status:** Design DoD 2026-09-22 PT  
**Cite:** issue [#23](https://github.com/themark-net/leasegrid-c/issues/23) · tip ≥ `7837ef8` · U4 frames (`32`) · P1 folders-first  
**Shell:** Phone folders-first; Offer/Credit N/A or secondary; read/download only.

ASCII only. Operate-or-FAIL banners stay in-app. Portrait phone (~360dp wide metaphor).

---

## M1 — Welcome / Join + threat HITL

```
┌─────────────────────────────┐
│ Leasegrid Sync              │
│                             │
│ See your folders on this    │
│ phone. Download files when  │
│ you need them.              │
│                             │
│ ┌─ Read before you join ──┐ │
│ │ 1. Friendnet trust —    │ │
│ │    unpaid by default.   │ │
│ │ 2. No storage proofs —  │ │
│ │    dead nodes dropped.  │ │
│ │ 3. Transport honesty —  │ │
│ │    invite may claim     │ │
│ │    I2P/Tor; reads may   │ │
│ │    use LAN/WAN.         │ │
│ │ 4. Recovery — lose key  │ │
│ │    AND devices ⇒ total  │ │
│ │    loss. Import U4 key. │ │
│ └─────────────────────────┘ │
│                             │
│ ☐ I understand the points   │
│                             │
│ Invite                      │
│ ┌─────────────────────────┐ │
│ │ paste invite…           │ │
│ └─────────────────────────┘ │
│                             │
│ [ Join friendnet ]  ← off   │
│                             │
│ Import recovery key instead…│
└─────────────────────────────┘
```

**HITL:** Join disabled until threat ACK. No skip on first install.

---

## M2 — Import recovery key

```
┌─────────────────────────────┐
│ ←  Import recovery key      │
│                             │
│ Use a *.leasegrid-recovery  │
│ file exported from desktop  │
│ Sync (U4). Same format.     │
│                             │
│ ⚠ Loss of this key and your │
│   devices can mean TOTAL    │
│   LOSS of access.           │
│                             │
│ File                        │
│ ┌─────────────────────────┐ │
│ │ Photos-backup.leasegrid │ │
│ │ -recovery          [‥]  │ │
│ └─────────────────────────┘ │
│                             │
│ Passphrase (if any)         │
│ ┌─────────────────────────┐ │
│ │ ••••••••                │ │
│ └─────────────────────────┘ │
│                             │
│ [ Import recovery key ]     │
│ [ Cancel ]                  │
└─────────────────────────────┘
```

---

## M3 — Folders home (primary)

```
┌─────────────────────────────┐
│ Folders              [⋮]    │
│ Online · unpaid             │
│                             │
│ ┌─────────────────────────┐ │
│ │ 📁 Photos               │ │
│ │    Available            │ │
│ ├─────────────────────────┤ │
│ │ 📁 Docs                 │ │
│ │    Available            │ │
│ ├─────────────────────────┤ │
│ │ 📁 Projects             │ │
│ │    Checking…            │ │
│ └─────────────────────────┘ │
│                             │
│ (pull to refresh)           │
│                             │
│ — no Offer pie —            │
│ — no Credit required —      │
└─────────────────────────────┘

⋮ → About · Settings · Recovery note
```

Optional one-line note after import: “Restored from recovery key. Folders may take a moment to appear.”

---

## M4 — Folder detail (file list)

```
┌─────────────────────────────┐
│ ← Photos                    │
│                             │
│ ┌─────────────────────────┐ │
│ │ 🖼  beach.jpg            │ │
│ │     2.4 MB · Tap to open│ │
│ ├─────────────────────────┤ │
│ │ 🖼  hike.png             │ │
│ │     1.1 MB              │ │
│ ├─────────────────────────┤ │
│ │ 📁  2024/               │ │
│ │     Folder              │ │
│ └─────────────────────────┘ │
└─────────────────────────────┘
```

Tap file → sheet: **Download** · **Open** (download-then-open OK as one action).

---

## M5 — Download / open in progress

```
┌─────────────────────────────┐
│ ← beach.jpg                 │
│                             │
│ Downloading…                │
│ ████████░░░░  62%           │
│                             │
│ [ Cancel ]                  │
│                             │
│ When finished: Open with…   │
└─────────────────────────────┘
```

Success: system chooser or in-app “Open”. Local copy retained for offline reopen when possible.

---

## M6 — FAIL banner (operate-or-FAIL)

```
┌─────────────────────────────┐
│ Folders              [⋮]    │
│                             │
│ ┌─ FAIL ──────────────────┐ │
│ │ Could not download this │ │
│ │ file. Network error or  │ │
│ │ not enough free space.  │ │
│ │                         │ │
│ │ Next: check network /   │ │
│ │ free space; Retry.      │ │
│ │                         │ │
│ │ [ Retry ]  [ Dismiss ]  │ │
│ └─────────────────────────┘ │
│                             │
│ (folder list still visible) │
└─────────────────────────────┘
```

Same shape for join / import / list failures. No “Open Tahoe WUI” Next.

---

## M7 — More → Recovery note (secondary)

```
┌─────────────────────────────┐
│ ← About / Recovery          │
│                             │
│ Recovery keys are exported  │
│ from Leasegrid Sync on your │
│ computer (U4).              │
│                             │
│ This phone imports that     │
│ same *.leasegrid-recovery   │
│ file to restore folder      │
│ access (read / download).   │
│                             │
│ Loss of your recovery key   │
│ and your devices can mean   │
│ TOTAL LOSS of access.       │
│                             │
│ [ Import recovery key… ]    │
│                             │
│ To add folders or export a  │
│ new key, use desktop Sync.  │
└─────────────────────────────┘
```

---

## M8 — Empty Folders (edge)

```
┌─────────────────────────────┐
│ Folders              [⋮]    │
│                             │
│ No folders yet.             │
│                             │
│ Join a friendnet or import  │
│ a recovery key to see your  │
│ folders here.               │
│                             │
│ [ Join / Import… ]          │
└─────────────────────────────┘
```

---

## Chrome locks (binding)

| Lock | Frame |
|------|-------|
| Folders primary | M3 |
| No Offer pie | M3 |
| No Credit gate | M3–M5 |
| Threat HITL | M1 |
| U4 import | M2 |
| Operate-or-FAIL | M6 |
| Desktop not demoted | M7 honesty line |
