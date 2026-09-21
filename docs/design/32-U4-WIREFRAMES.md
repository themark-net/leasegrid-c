# U4 — Wireframes (threat HITL + Recovery)

**Status:** Design DoD 2026-09-21 PT  
**Cite:** issue [#15](https://github.com/themark-net/leasegrid-c/issues/15) · tip `4e1e6bd` · U0 `12` §1a / §4 · P1 `27` chrome  
**Shell:** CrashPlan files-first — Folders primary; Recovery under **More**.

ASCII only. Operate-or-FAIL banners stay in-window.

---

## W1 — Join + threat HITL (first install)

```
┌─ Leasegrid Sync ────────────────────────────────────────────┐
│  Welcome                                                    │
│                                                             │
│  ┌─ Please read before you join ──────────────────────────┐ │
│  │ 1. Friendnet trust — join + offer disk are one unpaid  │ │
│  │    step. Not Dropbox-the-company. Not Filecoin.        │ │
│  │ 2. No storage proofs — dead nodes dropped; shares      │ │
│  │    moved — not slashed.                                │ │
│  │ 3. Transport honesty — invite may use I2P/Tor claims;  │ │
│  │    folder sync may still use LAN/WAN.                  │ │
│  │ 4. Recovery — lose the recovery key AND this device    │ │
│  │    and access can be gone forever. Export after join.  │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                             │
│  ☐ I understand the four points above.                      │ │
│                                                             │
│  Invite                                                     │ │
│  ┌──────────────────────────────────────────────────────┐   │ │
│  │ paste invite / furl…                                 │   │ │
│  └──────────────────────────────────────────────────────┘   │ │
│  ☑ Offer disk on this device                                │ │
│                                                             │ │
│  [ Join friendnet ]          ← disabled until ☐ checked     │ │
│  [ Import recovery key instead… ]                           │ │
└─────────────────────────────────────────────────────────────┘
```

**HITL:** Join disabled until threat ACK. No skip on first install.

---

## W2 — Folders home (P1) + recovery nudge (optional)

```
┌─ Leasegrid Sync ──────────────────── Online ──── [More ▾] ─┐
│  Folders                                                    │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ Name        Status                                     │ │
│  │ Photos      Synced                                     │ │
│  │ Docs        Syncing…                                   │ │
│  └────────────────────────────────────────────────────────┘ │
│  [ Add folder ]                                             │ │
│                                                             │ │
│  ┌─ Offer storage on this disk ───────────────────────────┐ │
│  │  (pie)   Offering 25% of this disk                     │ │
│  │          Used · Free · Offered                         │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                             │ │
│  ⚠ No recovery key exported yet.                            │ │
│  [ Export recovery key… ]  [ Dismiss ]                      │ │
└─────────────────────────────────────────────────────────────┘

More ▾ → Recovery · Settings · Credit*   (*gated only)
```

Nudge must not block Add folder / Offer. Dismissible; may return later.

---

## W3 — Recovery place (More → Recovery)

```
┌─ Leasegrid Sync ──────────────────── Online ──── [More ▾] ─┐
│  [← Folders]  Recovery                                      │ │
│                                                             │ │
│  A recovery key restores access to your folders if this     │ │
│  device is lost. Store it offline (encrypted USB, safe).    │ │
│                                                             │ │
│  ⚠  Loss of your recovery key and this device can mean      │ │
│     TOTAL LOSS of access. There is no “reset password.”      │ │
│     Leasegrid cannot recover it for you.                    │ │
│                                                             │ │
│  [ Export recovery key… ]  ← primary                        │ │
│  [ Import recovery key… ]                                   │ │
│                                                             │ │
│  Last export: never                                         │ │
└─────────────────────────────────────────────────────────────┘
```

---

## W4 — Export scary gate (HITL before write)

```
┌─ Export recovery key ───────────────────────────────────────┐
│  STOP — read this.                                          │
│                                                             │
│  Anyone with this key (and its passphrase, if set) can      │
│  read and change your synced folders and spend credit.      │
│  If you lose the key and this computer, access can be       │
│  gone forever. Leasegrid cannot reset it.                   │
│                                                             │
│  ☐ I understand: loss can mean total loss.                  │ │
│  ☐ I will store this file somewhere safe, offline.          │ │
│                                                             │
│  Passphrase (recommended)                                   │ │
│  ┌────────────────────┐  ┌────────────────────┐             │ │
│  │ ••••••••••         │  │ confirm            │ │
│  └────────────────────┘  └────────────────────┘             │ │
│  ⚠ No passphrase: the file is plaintext. Anyone who copies  │ │
│    it has your folders.     ← show when fields empty        │ │
│                                                             │ │
│  Save to  [ ~/backups/…leasegrid-recovery ] [ Browse… ]     │ │
│                                                             │ │
│  [ Write recovery key ] ← disabled until both ☐             │ │
│  [ Cancel ]                                                 │ │
└─────────────────────────────────────────────────────────────┘
```

---

## W5 — Export success

```
│  Recovery key written to                                    │
│  /home/you/backups/leasegrid-nimo.leasegrid-recovery        │
│  Move it somewhere safe and offline.                        │
│  [ Done ]                                                   │
```

---

## W6 — Export FAIL

```
│  FAIL — recovery key was not written.                       │
│  Disk error, permission denied, or encrypt failed.          │
│  Next: pick another path; Retry. Do not assume you are safe.│
│  [ Retry ]  [ Cancel ]                                      │
└─────────────────────────────────────────────────────────────┘
```

---

## W7 — Import (Join or Recovery)

```
┌─ Import recovery key ───────────────────────────────────────┐
│  Recovery key file                                          │
│  ┌──────────────────────────────────────┐ [ Browse… ]       │
│  │ /media/usb/….leasegrid-recovery      │                   │
│  └──────────────────────────────────────┘                   │
│  Passphrase (if you set one)                                │
│  ┌──────────────────────────────────────┐                   │
│  │                                      │                   │
│  └──────────────────────────────────────┘                   │
│  [ Import recovery key ]  ← primary                         │
│  [ Cancel ]                                                 │
└─────────────────────────────────────────────────────────────┘
```

---

## W8 — Import progress → Folders

```
│  Importing recovery key…                                    │
│  Joining friendnet · restoring folders…                     │
```

Then Folders (P1) with note:

```
│  Restored 2 folder(s): Photos, Docs. Files will download    │
│  from the friendnet into ~/Leasegrid/…                      │
```

---

## W9 — Import FAIL

```
│  FAIL — could not import this recovery key.                 │
│  Wrong passphrase, corrupt file, or incompatible grid.      │
│  Next: check passphrase; try the file from your backup;     │
│  Retry.                                                     │
│  [ Retry ]  [ Cancel ]                                      │
└─────────────────────────────────────────────────────────────┘
```

Introducer down variant:

```
│  FAIL — could not join this friendnet.                      │
│  Introducer is unreachable.                                 │
│  Next: check network; confirm the friendnet is up; Retry.   │
```

---

## Checklist (wireframe coverage)

- [x] Threat HITL on Join (ACK gates Join)  
- [x] Import from Join (`Import recovery key instead…`)  
- [x] Recovery under More; Folders remains primary  
- [x] Optional dismissible export nudge on Folders  
- [x] Dual-ACK export gate + plaintext warning  
- [x] Export / import success + FAIL + Next  
- [x] Restore lands on Folders with in-window note  
- [x] No Tahoe WUI affordance  
