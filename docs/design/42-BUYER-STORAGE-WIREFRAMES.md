# Buyer storage — ASCII wireframes

**Status:** Design DoD 2026-09-22 PT  
**Cite:** [#27](https://github.com/themark-net/leasegrid-c/issues/27) · tip ≥ **`5b752c7`** · Mark/CEO lock 2026-09-22  
**Shell:** Desktop Leasegrid Sync (CrashPlan folders-first after join). No Tahoe WUI.

Both Add paths drawn below (invite-to-Offer **and** paste server furl). Implement may sequence code; Design shows both.

---

## W1 — Clean home: empty Join-first (ONLY primary)

```
┌─ Leasegrid Sync ─────────────────────────────────────────┐
│                                                           │
│   Welcome                                                 │
│                                                           │
│   You are joining a friendnet you trust — not             │
│   Dropbox-the-company.                                    │
│                                                           │
│   1. Same invite joins and can Offer disk (unpaid).       │
│   2. Keys live on your devices.                           │
│   3. …                                                    │
│   4. Export a recovery key after you join.                │
│                                                           │
│   [✓] I understand the four points above.                 │
│                                                           │
│   Invite                                                  │
│   ┌───────────────────────────────────────────────────┐   │
│   │ paste invite / join URL / code                    │   │
│   └───────────────────────────────────────────────────┘   │
│                                                           │
│   [ Join friendnet ]                                      │
│                                                           │
│   Already have a recovery key?  Import…                   │
│                                                           │
│   ✦ No “Online — N computers storing files” here.         │
│   ✦ No folder list. No pre-baked lab grid chrome.         │
└───────────────────────────────────────────────────────────┘
```

**FAIL chrome (do not ship on clean home):** status chip “Online — N computers storing files” before Join succeeds.

---

## W2 — Join FAIL (operate-or-FAIL)

```
┌─ Leasegrid Sync ─────────────────────────────────────────┐
│  Welcome / Join                                           │
│  … threat + invite field …                                │
│                                                           │
│  ┌─ FAIL ─────────────────────────────────────────────┐   │
│  │ Could not join this friendnet.                     │   │
│  │ Check the invite and your network, then Retry.     │   │
│  │                                         [ Retry ]  │   │
│  └────────────────────────────────────────────────────┘   │
│  (no “open Tahoe WUI” Next)                               │
└───────────────────────────────────────────────────────────┘
```

---

## W3 — Post-join Folders (PRIMARY) + path to Servers

```
┌─ Leasegrid Sync ─────────────────────────────────────────┐
│  Folders          Storage servers    Credit    ⋯          │
│  ───────────────────────────────────────────────────────  │
│  Online — 2 computers storing files          [details →]  │
│  (glance only — click → Storage servers)                  │
│                                                           │
│  ┌─ Offer this disk ─────────────┐                        │
│  │  [==== pie ====]  40% offered │                        │
│  └───────────────────────────────┘                        │
│                                                           │
│  Folders                                                  │
│  ┌─────────────────────────────────────────────────────┐  │
│  │  Documents/work     ● synced                        │  │
│  │  Photos             ● synced                        │  │
│  │  [ + Add folder ]                                   │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                           │
│  Hosts: 2 connected · [ Manage storage servers ]          │
│                                                           │
│  ✦ Join / Add still reachable via Storage servers tab     │
│  ✦ Join-once-and-gone = FAIL                              │
└───────────────────────────────────────────────────────────┘
```

---

## W4 — Storage servers list (PRIMARY host UX) ★

```
┌─ Leasegrid Sync ─────────────────────────────────────────┐
│  Folders          Storage servers ●    Credit    ⋯        │
│  ───────────────────────────────────────────────────────  │
│  Storage servers                                          │
│  Where your files’ shares are stored.                     │
│                                                           │
│  [ + Add storage server ]                                 │
│                                                           │
│  Used by this Sync home                                   │
│  ┌─────────────────────────────────────────────────────┐  │
│  │  home-nas           Connected     Added by you      │  │
│  │                     [ Disconnect ]                  │  │
│  ├─────────────────────────────────────────────────────┤  │
│  │  friend-laptop      Connected     Via invite/Offer  │  │
│  │                     [ Disconnect ]                  │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                           │
│  Available on friendnet (not used yet)                    │
│  ┌─────────────────────────────────────────────────────┐  │
│  │  lab-node-3         Available     Announced         │  │
│  │                     [ Add ]                         │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                           │
│  Note: Disconnect removes a server from this home only.   │
│  It does not eject it from the friendnet for everyone.    │
└───────────────────────────────────────────────────────────┘
```

★ Mark 2026-09-22: this screen replaces reliance on the one-line host chip.

---

## W5 — Add dialog: both paths (Invite + Paste)

```
┌─ Add storage server ─────────────────────────────────────┐
│                                                           │
│  How do you want to add storage?                          │
│                                                           │
│  ○ Invite someone to Offer disk                           │
│     Share an invite so their computer can store shares.   │
│                                                           │
│  ○ Paste a server link                                    │
│     Paste a storage server link (pb://…) from a host      │
│     you trust.                                            │
│                                                           │
│  ───────────────────────────────────────────────────────  │
│  (when Invite selected)                                   │
│                                                           │
│  [ Create invite / Copy invite ]                          │
│  Wait for them to Join + Offer, then they appear in       │
│  Storage servers.                                         │
│                                                           │
│  ───────────────────────────────────────────────────────  │
│  (when Paste selected)                                    │
│                                                           │
│  Server link                                              │
│  ┌───────────────────────────────────────────────────┐    │
│  │ pb://…                                            │    │
│  └───────────────────────────────────────────────────┘    │
│  Nickname (optional)  [ home-nas____________ ]            │
│                                                           │
│            [ Cancel ]              [ Add server ]         │
└───────────────────────────────────────────────────────────┘
```

Default selection in MVP UI: **Invite someone to Offer disk** (recommend). Paste path always visible in the same dialog.

---

## W6 — Add FAIL (bad / unreachable furl)

```
┌─ Add storage server ─────────────────────────────────────┐
│  ○ Paste a server link                                    │
│  Server link  [ pb://bad…___________________________ ]    │
│                                                           │
│  ┌─ FAIL ─────────────────────────────────────────────┐   │
│  │ Could not add this storage server.                 │   │
│  │ Link looks wrong or the server is unreachable.     │   │
│  │ Check the link and Retry.                          │   │
│  └────────────────────────────────────────────────────┘   │
│            [ Cancel ]              [ Retry ]              │
└───────────────────────────────────────────────────────────┘
```

---

## W7 — Disconnect confirm (honest limits)

```
┌─ Disconnect storage server? ─────────────────────────────┐
│                                                           │
│  Disconnect “home-nas” from this Sync home?               │
│                                                           │
│  This will:                                               │
│  • Stop preferring it for new files on this home          │
│  • Forget it from your local server list                  │
│                                                           │
│  This will not:                                           │
│  • Remove it from the friendnet for everyone              │
│  • Delete shares already stored on that computer          │
│                                                           │
│  If the friendnet announces it again, it may show under   │
│  Available — you can Disconnect again or leave unused.    │
│                                                           │
│            [ Cancel ]              [ Disconnect ]         │
└───────────────────────────────────────────────────────────┘
```

---

## W8 — Empty Servers after join (zero hosts — CTA)

```
┌─ Storage servers ────────────────────────────────────────┐
│  No storage servers connected yet.                        │
│                                                           │
│  Add a computer that stores your files’ shares.           │
│                                                           │
│  [ + Add storage server ]                                 │
│                                                           │
│  (opens W5 — Invite or Paste)                             │
└───────────────────────────────────────────────────────────┘
```

Do **not** leave buyer with only “Online — 0 computers” and no Add.

---

## W9 — Re-announce honesty (after Disconnect)

```
│  Available on friendnet (not used yet)                    │
│  ┌─────────────────────────────────────────────────────┐  │
│  │  home-nas           Available     Seen again        │  │
│  │  You disconnected this server earlier.              │  │
│  │  Not used until you Add.            [ Add ]         │  │
│  └─────────────────────────────────────────────────────┘  │
```

---

## Chrome rules (checklist)

- [ ] W1 has no Folders / no Online-N chip  
- [ ] W3 Folders primary; nav to Storage servers visible  
- [ ] W4 is host UX (list + Add + Disconnect)  
- [ ] W5 shows **both** Invite and Paste  
- [ ] W6/W2 operate-or-FAIL in-app  
- [ ] W7 honest Disconnect (no forever-remove)  
- [ ] Join/Add reachable after first connect in every post-join frame