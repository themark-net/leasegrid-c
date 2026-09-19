# U0 — Wireframes (Leasegrid Sync · all 5 surfaces)

**Status:** Design DoD 2026-09-19 PT  
**Cite:** `docs/09-ui-track.md` screens 1–5 · CEO U0 RELEASE 2026-09-19 · founder product lock  
**Platform:** Native desktop window (Gridsync-class). ASCII is binding for IA/copy; pixels follow Qt.

**Surfaces in this file:** (1) First-run / invite · (2) Folders · (3) Credit · (4) Recovery · (5) Settings  
Plus empty / loading / error / needs-judgment states; HITL threat copy; credit top-up stub; recovery scary gate.

---

## Shared chrome

```
┌─ Leasegrid Sync — friendnet “lab” ───────────────[─][□][×]─┐
│  Folders   Credit   Recovery   Settings          Connected ✓│
│═════════════════════════════════════════════════════════════│
│  (place body)                                               │
└─────────────────────────────────────────────────────────────┘
```

Status chip values: `Connecting…` | `Connected ✓` | `Syncing…` | `Offline` | `FAIL`.

---

# 1. First-run / invite

## 1a. Screen one — threat copy + invite (HITL)

```
┌─ Welcome to Leasegrid Sync ─────────────────────────────────┐
│                                                             │
│  Sync folders with a paid friendnet you trust.              │
│  This is not Dropbox-the-company and not Filecoin.          │
│                                                             │
│  ┌─ Please read before you join ──────────────────────────┐ │
│  │ 1. Issuer trust — Credit is minted by this friendnet’s │ │
│  │    issuer after payment. You are trusting that issuer  │ │
│  │    (payment timing/amount can be visible to the mint). │ │
│  │ 2. No storage proofs — Nodes are not publishing        │ │
│  │    Filecoin-style proofs. Dead or unpaid nodes are     │ │
│  │    dropped and shares moved — not slashed on a chain.  │ │
│  │ 3. Tor vs sync — Full privacy claims often want Tor.   │ │
│  │    Folder sync that feels normal may use LAN/WAN.      │ │
│  │    Transport policy is a visible setting, not hidden.  │ │
│  │ 4. Recovery — Lose your recovery key and this device   │ │
│  │    and access can be gone forever.                     │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                             │
│  ☐ I understand the four points above.                      │
│                                                             │
│  Invite code                                                │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ paste invite here…                                   │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                             │
│  [ Join friendnet ]←primary (disabled until ☐ checked)      │
│  [ Import recovery key instead… ]                           │
└─────────────────────────────────────────────────────────────┘
```

**HITL:** Continue/Join disabled until threat checkbox ACK. No skip of threat block on first install.

## 1b. Loading — joining

```
│  Joining friendnet…                                         │
│  Checking invite · reaching introducer · saving grid…       │
│  [ Cancel ]                                                 │
```

## 1c. Error — invite / network FAIL

```
│  FAIL — could not join this friendnet.                      │
│  Invite invalid/expired, or introducer unreachable.         │
│  Next: get a fresh code from your inviter; check network;   │
│        Retry.                                               │
│  [ Retry ]←primary   [ Paste new code ]                     │
```

## 1d. Optional — pick first folder

```
┌─ Add your first sync folder ────────────────────────────────┐
│  Choose a folder on this computer to keep in sync.          │
│                                                             │
│  Local folder                                               │
│  ┌────────────────────────────────────────┐ [ Browse… ]     │
│  │ /home/you/Documents/Leasegrid        │                   │
│  └────────────────────────────────────────┘                 │
│                                                             │
│  [ Start syncing ]←primary   [ Skip for now ]               │
└─────────────────────────────────────────────────────────────┘
```

## 1e. Needs judgment — invite ambiguous / multi-grid

```
│  REVIEW — this invite matches more than one saved grid      │
│  profile on this device. Pick which to use, or reset.       │
│  ○ lab-friendnet (saved)                                    │
│  ○ new from invite                                          │
│  [ Continue ]←primary   [ Cancel ]                          │
```

## 1f. Nudge — recovery before finish

```
│  Before you finish: export a recovery key.                  │
│  Without it, losing this device can mean total loss.        │
│  [ Export recovery key ]←primary   [ Remind me later ]      │
│  (Remind me later shows one scary confirmation.)            │
```

---

# 2. Folders

## 2a. Empty

```
┌─ Leasegrid Sync ──────────────────────────────── Connected ✓┐
│  Folders   Credit   Recovery   Settings                     │
│═════════════════════════════════════════════════════════════│
│  Folders                                                    │
│                                                             │
│  No sync folders yet.                                       │
│  Add a local folder to sync encrypted shares to your        │
│  friendnet (Dropbox-shaped — not a web file browser).       │
│                                                             │
│  [ Add folder ]←primary                                     │
└─────────────────────────────────────────────────────────────┘
```

## 2b. Populated — sync status

```
┌─ Leasegrid Sync ──────────────────────────────── Syncing… ─┐
│  Folders   Credit   Recovery   Settings                     │
│═════════════════════════════════════════════════════════════│
│  Folders                              [ Add folder ]←primary│
│  ┌─────────────────────────────────────────────────────────┐│
│  │ 📁 Documents     Up to date     ~/Documents/Leasegrid   ││
│  │    Last sync 2 min ago                    [ Open ] [···]││
│  │ 📁 Photos        Syncing 40%    ~/Pictures/Family       ││
│  │    Uploading 12 files…                    [ Open ] [···]││
│  │ 📁 Notes         Conflict       ~/Notes                 ││
│  │    1 conflict — resolve in folder         [ Open ] [···]││
│  └─────────────────────────────────────────────────────────┘│
│  ··· = Pause · Resume · Remove from Sync                    │
└─────────────────────────────────────────────────────────────┘
```

## 2c. Loading — folder list / add

```
│  Loading folders…                                           │
│  Starting Magic Folder…                                     │
```

## 2d. Error — add folder FAIL (no credit)

```
│  FAIL — folder not added.                                   │
│  Not enough storage credit to allocate shares.              │
│  Next: Credit → Top up, then Add folder again.              │
│  [ Open Credit ]←primary   [ Cancel ]                       │
```

## 2e. Error — Magic Folder daemon FAIL

```
│  FAIL — sync engine not running.                            │
│  Magic Folder did not start. Folders are not watching.      │
│  Next: Restart Sync; if it persists, reinstall Sync.        │
│  [ Restart Sync ]←primary                                   │
```

## 2f. Needs judgment — conflict

```
│  REVIEW — “Notes” has a sync conflict.                      │
│  Both this device and another participant changed a file.   │
│  Open the folder and resolve conflict copies, then Retry.   │
│  [ Open folder ]←primary   [ Retry sync ]                   │
```

## 2g. Add folder dialog

```
┌─ Add folder ────────────────────────────────────────────────┐
│  Local folder  [ Browse… ]  /path/…                         │
│  Name on this device  [ Documents            ]              │
│  [ Add ]←primary   [ Cancel ]                               │
└─────────────────────────────────────────────────────────────┘
```

---

# 3. Credit

## 3a. Balance visible (plain language)

```
┌─ Leasegrid Sync ──────────────────────────────── Connected ✓┐
│  Folders   Credit   Recovery   Settings                     │
│═════════════════════════════════════════════════════════════│
│  Credit                                                     │
│                                                             │
│  ┌─ Remaining ────────────────────────────────────────────┐ │
│  │  About **48 GiB** kept for ~**30 days**                │ │
│  │  on this friendnet                                     │ │
│  │                                                        │ │
│  │  Plain meaning: prepaid share-capacity, not a simple   │ │
│  │  “disk free” meter. Encrypted shares expand across     │ │
│  │  nodes — uploading 1 GiB uses more than 1 GiB of       │ │
│  │  credit.                                               │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                             │
│  [ Top up ]←primary                                         │
│                                                             │
│  Lab note: Top up uses a faucet stub until XMR mint is      │
│  ready. Opaque ZKAP wallets from other apps do not convert. │
│                                                             │
│  Recent                                                     │
│  · Faucet top-up  +12 GiB·mo    today                       │
│  · Lease renew                 yesterday                    │
└─────────────────────────────────────────────────────────────┘
```

**Denomination lock:** 1 token ≈ 1 GiB-share × 30 days on **one** node. UI must not lie that 1 GiB upload = 1 GiB credit 1:1.

## 3b. Empty / zero credit

```
│  Credit remaining: **none**.                                │
│  Sync may pause when leases cannot renew.                   │
│  [ Top up ]←primary                                         │
```

## 3c. Top-up stub (faucet now → XMR later)

```
┌─ Top up ────────────────────────────────────────────────────┐
│  Lab faucet (stub)                                          │
│  Request prepaid credit for this friendnet.                 │
│                                                             │
│  Amount  ○ Small (≈ 10 GiB·mo)  ● Medium (≈ 50)  ○ Large    │
│                                                             │
│  Later: Top up with Monero (XMR) when mint rails PASS.      │
│  [ Request faucet credit ]←primary   [ Cancel ]             │
└─────────────────────────────────────────────────────────────┘
```

## 3d. Loading — redeeming

```
│  Requesting credit from faucet…                             │
```

## 3e. Error — faucet / issuer FAIL

```
│  FAIL — top-up did not complete.                            │
│  Faucet or issuer rejected the request (or network error).  │
│  Next: Retry; if lab is down, ask your operator. Balance    │
│        unchanged.                                           │
│  [ Retry ]←primary   [ Close ]                              │
```

## 3f. Needs judgment — denomination / surprise expansion

```
│  REVIEW — this folder needs more credit than the raw size.  │
│  Share expansion is expected. Estimated need: ~3.2× upload. │
│  [ Top up ]←primary   [ Cancel add ]                        │
```

## 3g. Reject — opaque foreign wallet

```
│  This screen shows Leasegrid Sync credit only.              │
│  Pasting an opaque ZKAP wallet from another tool will not   │
│  convert here.                                              │
```

---

# 4. Recovery

## 4a. Home — export / import

```
┌─ Leasegrid Sync ──────────────────────────────── Connected ✓┐
│  Folders   Credit   Recovery   Settings                     │
│═════════════════════════════════════════════════════════════│
│  Recovery                                                   │
│                                                             │
│  A recovery key restores access to your folders if this     │
│  device is lost. Store it offline (encrypted USB, etc.).    │
│                                                             │
│  ⚠  Loss of your recovery key and this device can mean      │
│     TOTAL LOSS of access. There is no “reset password.”      │
│                                                             │
│  [ Export recovery key… ]←primary                           │
│  [ Import recovery key… ]                                   │
│                                                             │
│  Last export: never                                         │
└─────────────────────────────────────────────────────────────┘
```

## 4b. Scary gate (HITL before export write)

```
┌─ Export recovery key ───────────────────────────────────────┐
│  STOP — read this.                                          │
│                                                             │
│  Anyone with this key (and its passphrase, if set) can      │
│  access your synced folders.                                │
│  If you lose the key and this computer, your data access    │
│  can be gone forever. Leasegrid cannot reset it.            │
│                                                             │
│  ☐ I understand: loss can mean total loss.                  │
│  ☐ I will store this file somewhere safe offline.           │
│                                                             │
│  Passphrase (recommended)                                   │
│  ┌────────────────────┐  ┌────────────────────┐             │
│  │ ••••••••••         │  │ confirm            │             │
│  └────────────────────┘  └────────────────────┘             │
│                                                             │
│  Save to  [ Browse… ]                                       │
│                                                             │
│  [ Write recovery key ]←primary (disabled until both ☐)     │
│  [ Cancel ]                                                 │
└─────────────────────────────────────────────────────────────┘
```

## 4c. Loading — writing / importing

```
│  Writing recovery key…                                      │
│  Importing recovery key…                                    │
```

## 4d. Error — export FAIL

```
│  FAIL — recovery key was not written.                       │
│  Disk error, permission denied, or encrypt failed.          │
│  Next: pick another path; Retry. Do not assume you are safe.│
│  [ Retry export ]←primary                                   │
```

## 4e. Error — import FAIL

```
│  FAIL — could not import this recovery key.                 │
│  Wrong passphrase, corrupt file, or incompatible grid.      │
│  Next: check passphrase; try the file from your backup.     │
│  [ Retry import ]←primary                                   │
```

## 4f. After import — remote-only folders (needs judgment)

```
│  Restored 3 folders (stored on friendnet, not local yet).   │
│  Choose a local path to download each folder.               │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ 📁 Documents   remote only   [ Choose folder… ]         ││
│  │ 📁 Photos      remote only   [ Choose folder… ]         ││
│  │ 📁 Notes       remote only   [ Choose folder… ]         ││
│  └─────────────────────────────────────────────────────────┘│
```

## 4g. Defer reminder (from first-run)

```
│  You skipped exporting a recovery key.                      │
│  ⚠ Without it, device loss can mean total loss.             │
│  [ Export now ]←primary   [ I accept the risk for now ]     │
```

---

# 5. Settings

## 5a. Main

```
┌─ Leasegrid Sync ──────────────────────────────── Connected ✓┐
│  Folders   Credit   Recovery   Settings                     │
│═════════════════════════════════════════════════════════════│
│  Settings                                                   │
│                                                             │
│  Startup                                                    │
│  ☑ Start Leasegrid Sync when I log in                       │
│                                                             │
│  ┌─ Transport policy (design flag) ───────────────────────┐ │
│  │ Tor vs sync — visible on purpose                       │ │
│  │                                                        │ │
│  │ Full privacy claims often want Tor for grid traffic.   │ │
│  │ Magic Folder users also expect LAN/WAN sync that feels │ │
│  │ normal. This friendnet’s current policy:               │ │
│  │                                                        │ │
│  │   ● Lab / performance: direct (LAN/WAN)                │ │
│  │   ○ Tor-preferred (slower sync; stronger claim)        │ │
│  │                                                        │ │
│  │ This is not a buried “advanced” toggle. Changing it    │ │
│  │ may pause sync while reconnecting.                     │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                             │
│  About                                                      │
│  Leasegrid Sync (buyer) · version 0.0.x-dev                 │
│  Grid: lab-friendnet                                        │
│  Operators run Leasegrid Node (Phase 2 — separate app).     │
│                                                             │
│  [ Open Recovery ]   [ Quit Leasegrid Sync ]                │
└─────────────────────────────────────────────────────────────┘
```

**Design flag rule:** Tor vs sync appears here and on first-run threat block — never only in a hidden config file or undocumented CLI flag for MVP buyers.

## 5b. Loading — saving prefs

```
│  Saving settings…                                           │
```

## 5c. Error — autostart FAIL

```
│  FAIL — could not change login autostart.                   │
│  OS denied the login item (permissions / portal).           │
│  Next: fix OS permissions; Retry. Toggle shows actual state.│
│  [ Retry ]←primary                                          │
```

## 5d. Error — transport switch FAIL

```
│  FAIL — could not apply transport policy.                   │
│  Reconnect aborted; prior policy still active.              │
│  Next: Retry; check Tor is installed if Tor-preferred.      │
│  [ Retry ]←primary   [ Keep previous ]                      │
```

## 5e. Needs judgment — Tor missing

```
│  REVIEW — Tor-preferred selected but Tor was not found.     │
│  Install Tor and Retry, or stay on direct transport.        │
│  [ Install help ]  [ Use direct ]←primary  [ Retry ]        │
```

---

# State matrix (all 5 surfaces)

| Surface | Empty | Loading | Error (FAIL + next) | Needs judgment |
|---------|-------|---------|---------------------|----------------|
| 1 First-run | Invite fields blank; Join disabled | Joining… | Invite/network FAIL | Multi-grid / ambiguous invite |
| 2 Folders | No folders + Add CTA | Loading folders / Starting MF | Add FAIL; daemon FAIL | Conflict resolve |
| 3 Credit | Zero balance + Top up | Requesting credit… | Faucet/issuer FAIL | Expansion surprise |
| 4 Recovery | Never exported | Writing / Importing | Export/import FAIL | Remote-only after import; defer risk |
| 5 Settings | Defaults | Saving… | Autostart / transport FAIL | Tor missing |

---

# Operate-or-FAIL copy pattern (binding)

Every FAIL block:

1. **FAIL —** what failed (buyer words)  
2. **Why** (one line, no ADR dump)  
3. **Next:** concrete in-app action  
4. **Primary button** that navigates or retries  

Never: blank swallow · terminal instructions as only path · localhost WUI link · “see docs/00-decision.md”.

---

# Checklist — five surfaces present

- [x] 1 First-run / invite (+ HITL threat copy)  
- [x] 2 Folders  
- [x] 3 Credit (+ top-up stub)  
- [x] 4 Recovery (+ scary gate)  
- [x] 5 Settings (+ Tor vs sync design flag)  
