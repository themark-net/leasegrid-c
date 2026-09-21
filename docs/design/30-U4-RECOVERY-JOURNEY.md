# U4 — Recovery journey (threat HITL + recovery key)

**Status:** Design DoD 2026-09-21 PT  
**Cite:** issue [#15](https://github.com/themark-net/leasegrid-c/issues/15) · `docs/09-ui-track.md` U4 · tip **`4e1e6bd`** (P0+P1 CrashPlan shell on main)  
**Product:** Native **Leasegrid Sync** (buyer). CrashPlan shell (P1) stays files-first — Recovery is secondary chrome with a clear primary CTA **when** the operator needs restore.  
**Preserve:** U1 Magic Folder / join / tray / no-WUI · P1 folders-first + Offer pie · unpaid default · payment lecture gated.

---

## North star (one sentence)

A non-expert can **acknowledge honest threat copy**, **export a recovery key** behind a scary dual-ACK gate, and **restore on a new device** (import → folders download from the friendnet) without Tahoe WUI or a shell tutorial — **Non-expert walkthrough PASS**.

---

## Single recovery-copy path (binding)

```
  First-run: threat copy HITL (ACK required) → Join
           │
           ▼
  Folders home (P1 primary) + Offer pie
           │
           ▼
  More → Recovery  OR  post-join nudge
           │
           ▼
  Export recovery key… (scary gate → dual ACK → optional passphrase → Write)
           │
           ▼
  (Later / new device) Import recovery key instead… → Folders restore
```

Primary chrome after join remains **Folders**. Recovery is **not** the first story after join — but when the operator opens Recovery (or imports on a blank device), the **primary CTA is unmistakable**: Export / Import / Write / Retry.

---

## Happy path A — first device (export)

| Step | Place | Operator does | System does | Exit |
|------|-------|---------------|-------------|------|
| 0 | Launch | Opens Sync | Boots native Sync; no WUI | Join or Folders |
| 1 | Join + threat | Reads four threat points; checks ACK; pastes invite; Join | Enables Join only after threat ACK; unpaid join+offer | Connected or FAIL |
| 2 | Folders (P1) | Lands on folder list + Offer pie | P1 chrome unchanged | Folders primary |
| 3 | Recovery | More → Recovery (or Export nudge) | Shows intro + scary loss line | Recovery place |
| 4 | Export gate | Checks both ACKs; optional passphrase; picks path; Write | Writes `*.leasegrid-recovery` (0600); verify decrypt | Success note or FAIL |
| 5 | Steady | Stores file offline | May show “Last export: …” | Safe to continue using Folders |

**Steady state:** Folders + Offer pie remain home. Recovery stays under **More**. Credit stays gated/secondary (P1).

---

## Happy path B — new / replacement device (import)

| Step | Place | Operator does | System does | Exit |
|------|-------|---------------|-------------|------|
| 0 | Launch (empty home) | Opens Sync | Join page | Join |
| 1 | Import | **Import recovery key instead…** | Opens import dialog | Dialog |
| 2 | Unlock | Picks file; enters passphrase if any; Import | Restores grid + folders as **new participant**; downloads into restore root | Folders or FAIL |
| 3 | Folders | Sees restored folder rows; files appear from friendnet | Magic Folder sync | Non-expert PASS |

---

## Journey map (ASCII)

```
  [Launch Sync]
       │
       ├─ empty home ──► Join + threat HITL
       │                      │
       │                      ├─ Join friendnet ──► Folders (P1)
       │                      │                        │
       │                      │                        └─ More → Recovery → Export…
       │                      │
       │                      └─ Import recovery key instead… ──► Restore ──► Folders
       │
       └─ already joined ──► Folders (P1) ──► More → Recovery
```

---

## Threat copy (first-run HITL) — binding intent

Threat block is **on screen one** with join. Join / Continue stays **disabled** until the operator ACKs understanding. No skip on first install.

Four points (buyer voice; align with shipped `THREAT_COPY` / U0 §1a):

1. **Friendnet trust** — joining and offering disk are one unpaid step by default (not Dropbox-the-company / not Filecoin).  
2. **No storage proofs** — dead nodes dropped and shares moved, not slashed.  
3. **Transport honesty** — invite/share path may use I2P/Tor claims; folder sync may still use LAN/WAN (visible policy, not a hidden toggle).  
4. **Recovery** — lose the recovery key **and** this device and access can be gone forever; export from Recovery after join.

---

## Recovery key semantics (Design lock)

| Topic | Rule |
|-------|------|
| Artifact | One file `*.leasegrid-recovery` (JSON envelope) |
| Secrets | Introducer/furl + folder collective caps + wallet/issuer as needed to rejoin |
| Passphrase | Optional; empty ⇒ plaintext warning in UI |
| Write | Mode `0600`; read-back / decrypt before success copy |
| Restore model | **New participant** per Magic Folder (do not clone old upload cap as self) |
| Landing | Restored folders under restore root (default `~/Leasegrid/<name>`; override env OK) |
| Wallet | Bearer copy — honest caveat; spent-set stops double spend |

Ops detail may live in `docs/ops/u4-recovery.md`; Design owns buyer journey + HITL + FAIL copy.

---

## FAIL paths (operate-or-FAIL, in-window)

| Action | Banner shape |
|--------|----------------|
| Export, disk / permission / encrypt | FAIL — recovery key was not written. Next: pick another path; Retry. Do not assume you are safe. |
| Export, not joined | FAIL — recovery key was not written. No friendnet joined yet. |
| Import, wrong passphrase / corrupt / incompatible | FAIL — could not import this recovery key. Wrong passphrase, corrupt file, or incompatible grid. Next: check passphrase; try backup file; Retry. |
| Import, introducer down | FAIL — could not join this friendnet. Introducer is unreachable. Next: check network / invite still valid; Retry. |
| Threat ACK missing | Join stays disabled — not a silent skip |

No Tahoe WUI as Next. No “check the terminal” as the only Next.

---

## CrashPlan shell fit (binding)

| Rule | Behavior |
|------|----------|
| Primary after join | **Folders** + Offer pie (P1) |
| Recovery chrome | **More → Recovery** (secondary) |
| Import on blank device | Visible on Join: **Import recovery key instead…** |
| Payment / XMR | Stays behind gated friendnet (P1); Recovery must not open a payment lecture |
| Unpaid default | Export/import work on unpaid grids |
| Primary CTA when in Recovery | **Export recovery key…** / **Write recovery key** / **Import recovery key** |

---

## Exit criterion (UI track U4)

Per `docs/09-ui-track.md` **U4**:

> Recovery key export + first-run threat copy → **Non-expert walkthrough PASS**.

Design DoD exit: this package (`30`–`34`) ready for DevBot. Implement exit: non-expert completes threat ACK → join → export (dual ACK) and, on a second empty profile, import → sees folders/files without a shell tutorial or WUI.

---

## Honesty

- Do **not** claim U5 / mainnet XMR done.  
- Do **not** claim AppImage (#12) done.  
- Do **not** claim P0 crash matrix fixed unless separately PASS.  
- Known stretch: per-folder local path picker after import (U0 wireframe 4f) — default restore root is acceptable for U4 Design exit if documented; call out in handoff.
