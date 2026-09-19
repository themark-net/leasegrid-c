# U0 — Buyer journey (Leasegrid Sync)

**Status:** Design DoD 2026-09-19 PT  
**Cite:** `docs/09-ui-track.md` · CEO U0 RELEASE 2026-09-19 · `docs/03-roadmap.md` Phase 1  
**Product:** Native **Leasegrid Sync** (buyer). Operator **Leasegrid Node** is Phase 2 — out of this journey except mention.

---

## North star (one sentence)

A non-Tahoe person installs Sync, joins a friendnet with an invite code, syncs a folder, sees credit in plain language, and exports a recovery key — with honest threat copy on screen one.

---

## Happy path (first-run → folders → credit → recovery)

| Step | Place | Buyer does | System does | Exit |
|------|-------|------------|-------------|------|
| 0 | Installer | Installs AppImage or `.deb` | Places Sync binary, Magic Folder, local Tahoe client config stubs | App launches |
| 1 | First-run / invite | Reads threat-model block; pastes invite code; continues | Validates invite; joins friendnet; stores grid settings | Connected or FAIL |
| 2 | First-run / folder | Picks a local folder to sync (or skip → Folders empty) | Creates/joins Magic Folder; starts watch | Folder appears on Folders |
| 3 | Folders | Sees sync status; opens local path | Magic Folder up/down sync | Status: Idle / Syncing / Up to date / Conflict / FAIL |
| 4 | Credit | Opens Credit; reads remaining capacity | Shows GiB-share-months in plain language (not raw ZKAP blobs) | Balance visible |
| 5 | Credit top-up | Clicks **Top up** (faucet stub in lab) | Redeems faucet → balance increases (XMR when gate 0c PASS) | New balance or FAIL |
| 6 | Recovery | Exports recovery key; confirms scary gate; stores file offline | Writes encrypted recovery key file | Key on disk; buyer confirms location |
| 7 | Settings (optional) | Sets autostart; reads transport policy note | Persists prefs; does not hide Tor vs sync | Prefs saved |

**Steady state:** Tray icon shows Sync connected; Folders is primary window; Credit and Recovery reachable from places without leaving the app.

---

## Journey map (ASCII)

```
  [Installer]
       │
       ▼
  ┌─────────────────────┐
  │ 1. First-run invite │── FAIL invite / network ──► in-window FAIL + next
  │    + threat copy    │
  └──────────┬──────────┘
             │ PASS
             ▼
  ┌─────────────────────┐
  │ 2. Pick sync folder │── skip OK ──► Folders (empty CTA)
  └──────────┬──────────┘
             │
             ▼
  ┌─────────────────────┐     ┌──────────┐
  │ 3. Folders (home)   │◄────┤  Tray    │
  └──────────┬──────────┘     └──────────┘
             │
     ┌───────┼───────────┐
     ▼       ▼           ▼
 Credit   Recovery   Settings
     │       │
  Top up  Export/Import
  (faucet→XMR)
```

---

## Operate-or-FAIL (controls)

| Control | PASS | FAIL (in-window) | Next |
|---------|------|------------------|------|
| Join with invite | Grid connected; places unlock | Invalid code / unreachable introducer / TLS fail | Re-check code with inviter; Retry; Offline help |
| Add folder | Magic Folder created; status row appears | Path unreadable / MF daemon down / no credit for allocate | Fix path; Restart Sync; Top up Credit |
| Sync cycle | Status → Up to date | Share write refused (no ZKAP) / peer unreachable | Top up; wait/retry; contact friendnet operator |
| Top up (faucet) | Balance increases | Faucet down / issuer reject / network | Retry; show last error; lab note “XMR later” |
| Top up (XMR) | U5 only when 0c PASS | Out of U0–U4 UI DoD beyond stub label | — |
| Export recovery key | File written; confirm dialog | Disk full / cancel / encrypt fail | Retry; do not claim success |
| Import recovery key | Folders restore (gray remote until path) | Bad key / wrong passphrase / corrupt file | Re-export from other device; Retry |
| Autostart toggle | Pref persisted; OS login item set/cleared | OS denied | Show FAIL; leave toggle reflecting truth |

**Rule:** No silent no-op. No “check the terminal.” No localhost board URL in product chrome.

---

## FAIL paths (buyer-visible)

### F1 — Invite rejected

```
FAIL — could not join this friendnet.
Invite code invalid or expired, or the introducer is unreachable.
Next: ask your inviter for a fresh code; check network; Retry.
[ Retry ]←primary   [ Paste new code ]
```

### F2 — Folder add blocked (no credit)

```
FAIL — folder not added.
Not enough storage credit to allocate shares for this folder.
Next: open Credit → Top up, then Add folder again.
[ Open Credit ]←primary   [ Cancel ]
```

### F3 — Sync stalled / peer dead

```
FAIL — sync paused for “Photos”.
A storage node stopped accepting shares (or is unreachable).
Shares will move when live nodes are available. You are not being silently charged for a dead node.
Next: wait/retry; contact your friendnet operator if this persists.
[ Retry sync ]←primary   [ Open Folders ]
```

### F4 — Recovery export cancelled mid-gate

```
Export cancelled — no recovery key was written.
Your folders are unchanged. Without a recovery key, loss of this device can mean total loss of access.
[ Export again ]←primary
```

### F5 — Threat copy dismissed without ACK (gate)

First-run Continue stays disabled until buyer checks:

`☐ I understand: I trust this friendnet’s issuer; there are no Filecoin-style storage proofs; losing my recovery key can mean permanent loss.`

---

## Credit denomination (honesty — journey copy)

| Behind the scenes | What the UI says |
|-------------------|------------------|
| ~1 token ≈ 1 GiB-share × ~30 days on **one** node | “About **N GiB** kept for ~**30 days** on this friendnet (share expansion means you need more than N GiB of raw disk across nodes).” |
| Opaque ZKAP batch | Never show raw token blobs as “dollars” or “GB free” without the share-month framing |
| Expansion is real | Do **not** claim 1 GiB uploaded = 1 GiB credit 1:1 |

Opaque ZKAP wallets **do not convert** — Credit shows Leasegrid balance only.

---

## Threat-model beats (must appear)

| Beat | Where | Must say |
|------|-------|----------|
| Issuer mint trust | First-run screen one | You trust the issuer that mints credit after payment; mint can see payment timing/amount metadata |
| No storage proofs | First-run screen one | Nodes are not Filecoin-proving storage; unpaid/dead nodes are dropped and shares moved — not slashed on-chain |
| Tor vs sync | First-run note + Settings design flag | Full privacy claim wants Tor; Magic Folder sync often needs LAN/WAN performance — policy is a visible flag, not a buried toggle |
| Recovery total loss | Recovery scary gate | Loss of recovery key (+ this device) can mean **total loss** of access |

---

## Out of this journey

- Leasegrid Node operator install  
- Full Tahoe directory browse  
- Mobile  
- Sharing beyond invite codes  
- Mainnet XMR before gate 0c (faucet stub is the journey for U2–U4)  
- Waiting on Phase 0 rails to start U1 spike  

---

## Success (journey design)

Buyer can narrate: *install → invite + threat ACK → folder syncs → see credit → top up stub → export recovery key* without reading Tahoe docs or opening a browser WUI.
