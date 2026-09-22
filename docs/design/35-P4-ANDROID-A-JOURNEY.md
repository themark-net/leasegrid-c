# P4 Android Slice A — Journey (read-first APK)

**Status:** Design DoD 2026-09-22 PT  
**Cite:** issue [#23](https://github.com/themark-net/leasegrid-c/issues/23) · `docs/03-roadmap.md` Phase 4 (mobile read, then write) · tip ≥ **`7837ef8`** · U4 Recovery (`30`–`34`) · P1 folders-first (`25`–`29`)  
**Product:** **Leasegrid Sync (Android)** — read-only / restore-oriented companion. Desktop Sync remains primary.  
**Preserve:** U1–U4 desktop; U4 `*.leasegrid-recovery` format; unpaid default; no Tahoe WUI.

---

## North star (one sentence)

A non-expert can **join a friendnet or import a U4 recovery key** on Android, **see their folders**, and **download/open files on the device** without Tahoe WUI, without inventing a second recovery format, and without regressing desktop Sync — **And emulator dogfood PASS** after implement.

---

## Slice A scope (binding)

```
  Launch APK
       │
       ├─ Join friendnet (invite + threat ACK) ──► Folders list
       │                                              │
       └─ Import recovery key (U4 file) ──────────────┤
                                                      ▼
                                              Open folder → file list
                                                      │
                                                      ▼
                                              Download / open on device
```

| In Slice A | Out (Slice B / later) |
|------------|------------------------|
| Join with invite | Add folder / upload / write sync |
| Import `*.leasegrid-recovery` | Magic Folder–class bi-directional sync |
| List restored / joined folders | Offer disk pie as phone primary |
| Browse folder contents (read) | Credit / XMR top-up as required path |
| Download file to device storage / open with viewer | iOS · Play Store listing |
| Operate-or-FAIL in-app | Operator Node kit |

---

## Happy path A — join on phone (empty install)

| Step | Place | Operator does | System does | Exit |
|------|-------|---------------|-------------|------|
| 0 | Launch | Opens Sync Mobile | Boots native APK; no WUI | Welcome / Join |
| 1 | Threat + Join | Reads threat points; checks ACK; pastes invite; Join | Enables Join only after threat ACK; unpaid join | Folders or FAIL |
| 2 | Folders | Sees folder rows from friendnet (read view) | Lists folder names + sync/availability status | Folders primary |
| 3 | Folder detail | Taps a folder | Lists files/dirs (read-only) | File list |
| 4 | Download/Open | Taps a file → Download or Open | Fetches bytes via same friendnet/caps as desktop Sync; writes to app/shared storage or hands to viewer | File on device or FAIL |

**Steady state:** Folders list is home. No Offer pie required on phone. Credit not required.

---

## Happy path B — restore from U4 recovery key (empty install)

| Step | Place | Operator does | System does | Exit |
|------|-------|---------------|-------------|------|
| 0 | Launch (empty) | Opens Sync Mobile | Welcome / Join | Join |
| 1 | Import | **Import recovery key instead…** | Opens SAF / file picker for `*.leasegrid-recovery` | Picker |
| 2 | Unlock | Picks file; enters passphrase if any; Import | Decodes U4 envelope (same format as desktop); joins as **new participant** / read-capable client | Folders or FAIL |
| 3 | Folders | Sees restored folder rows | Lists folders from bundle caps | Folders |
| 4 | Download/Open | Same as path A steps 3–4 | Same cap/read path | File on device or FAIL |

**Binding:** Do **not** invent a second recovery format. Reuse U4 `*.leasegrid-recovery` (version 1 envelope). Loss of recovery key **and** all devices = total loss — same honesty as U4.

---

## Happy path C — already joined (return visit)

| Step | Place | Operator does | System does | Exit |
|------|-------|---------------|-------------|------|
| 0 | Launch | Opens app | Restores local node/session state | Folders |
| 1 | Folders | Browses; pulls to refresh | Reconciles folder list from friendnet | Folders |
| 2 | Download/Open | Opens file | Download/open | File or FAIL |

---

## Journey map (ASCII)

```
  [Launch APK]
       │
       ├─ empty ──► Welcome
       │               │
       │               ├─ Join friendnet (threat ACK + invite) ──► Folders
       │               │                                              │
       │               └─ Import recovery key instead… ──► Unlock ────┤
       │                                                              ▼
       └─ already joined ──► Folders ──► Folder ──► Download / Open
                                              │
                                              └─ More → About / Recovery note / Settings*
```

\* Settings minimal on Slice A (transport honesty note OK). Credit / Offer not primary.

---

## Threat copy (first-run HITL) — binding intent

Threat block on screen one with join (align with U4 / shipped `THREAT_COPY` tone). Join disabled until ACK. No skip on first install.

Four points (buyer voice; phone-trimmed OK if all four remain):

1. **Friendnet trust** — joining is unpaid by default (not Dropbox-the-company / not Filecoin). Phone Slice A does **not** require offering disk.  
2. **No storage proofs** — dead nodes dropped and shares moved, not slashed.  
3. **Transport honesty** — invite/share path may use I2P/Tor claims; reads may still use LAN/WAN (visible policy, not a hidden toggle).  
4. **Recovery** — lose the recovery key **and** your devices and access can be gone forever. Import uses the **same** desktop U4 recovery key file.

---

## Download / open semantics (Design lock)

| Topic | Rule |
|-------|------|
| Metaphor | Folders-first CrashPlan / Sync — phone is a **reader**, not a second desktop writer |
| Caps | Same friendnet / folder caps as desktop Sync (read path) |
| Local write | Downloaded file lands in app-controlled or user-picked storage; then OS open-with |
| Offline | Previously downloaded files may open offline; remote list/fetch FAIL honestly when unreachable |
| Large files | Progress + cancel; FAIL if storage full or fetch aborted |
| Preview | In-app preview optional stretch; system viewer is enough for Design exit |
| Desktop | Must **not** require desktop running for every open once phone has joined/imported |

---

## FAIL paths (operate-or-FAIL, in-app)

| Action | Banner shape |
|--------|----------------|
| Join, bad invite / introducer down | FAIL — could not join this friendnet. Next: check invite / network; Retry. |
| Threat ACK missing | Join stays disabled — not a silent skip |
| Import, wrong passphrase / corrupt / incompatible | FAIL — could not import this recovery key. Wrong passphrase, corrupt file, or incompatible grid. Next: check passphrase; try backup; Retry. |
| Folders list unreachable | FAIL — could not load folders. Next: check network; Retry. |
| File download fail | FAIL — could not download this file. Next: check network / free space; Retry. |
| Open fail (no app / permission) | FAIL — could not open this file. Next: grant storage permission or pick another app; Retry. |

No Tahoe WUI as Next. No “open desktop Sync” as the **only** Next for a file the phone should be able to fetch after join/import.

---

## Phone vs desktop (honesty)

| Rule | Behavior |
|------|----------|
| Desktop primary | AppImage / native Sync remains the sync/write home |
| Phone Slice A | Read / restore companion |
| Slice B | Write sync later — **does not** block Design PASS |
| Recovery format | One U4 format; phone imports; desktop still exports |
| Offer / Credit | Secondary or N/A on phone for Slice A |

---

## Exit criterion (Design → implement)

Design DoD exit: this package (`35`–`39`) ready for DevBot/Cursor.  
Implement exit (post Design PASS + PM RELEASE): **And** completes emulator dogfood — install APK → join **or** import → see folders → download/open one known file — without WUI or shell tutorial.

---

## Honesty

- Do **not** claim Slice B write sync done.  
- Do **not** claim iOS or Play Store listing.  
- Do **not** claim U5 / mainnet XMR done.  
- Do **not** demote desktop Sync.  
- Do **not** rewrite U4 recovery format.  
- Known stretch: rich in-app preview, biometric lock for imported key material, offline full-tree cache — optional; Design exit does not require them.
