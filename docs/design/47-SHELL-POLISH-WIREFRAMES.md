# Shell polish — ASCII wireframes

**Status:** Design DoD 2026-09-23 PT (~11:26pm PT)  
**Cite:** [#38](https://github.com/themark-net/leasegrid-c/issues/38) · [#32](https://github.com/themark-net/leasegrid-c/issues/32) · tip ≥ **`f46ab7c`**  
**Shell:** Desktop Leasegrid Sync. No Tahoe WUI. Visual cleanup + flow straighten — not a rebrand.

#32 invite locks drawn below: **short code + QR + Copy**; **never** dump raw introducer FURL in primary share UI.

---

## W1 — Clean home: Join-first (accept invite)

```
┌─ Leasegrid Sync ─────────────────────────────────────────┐
│                                                           │
│   Join a friendnet                                        │
│                                                           │
│   Paste a short code, join link, or text from a QR.       │
│                                                           │
│   ┌─ Please read before you join ─────────────────────┐   │
│   │  1. Same invite joins and can Offer disk.         │   │
│   │  2. Keys live on your devices.                    │   │
│   │  3. …                                             │   │
│   │  4. Export a recovery key after you join.         │   │
│   │  [✓] I understand the four points above.          │   │
│   └───────────────────────────────────────────────────┘   │
│                                                           │
│   Invite                                                  │
│   ┌───────────────────────────────────────────────────┐   │
│   │ 7-word-word   or join link                        │   │
│   └───────────────────────────────────────────────────┘   │
│                                                           │
│   [✓] Offer disk on this device                           │
│                                                           │
│   [ Join friendnet ]     ← primary CTA weight             │
│                                                           │
│   Import recovery key instead…                            │
│                                                           │
│   ✦ No Online-N chip. No raw pb:// placeholder.           │
└───────────────────────────────────────────────────────────┘
```

---

## W2 — Join FAIL (in-window)

```
┌─ Leasegrid Sync ─────────────────────────────────────────┐
│  Join a friendnet                                         │
│  … threat + invite field …                                │
│                                                           │
│  ┌─ FAIL ─────────────────────────────────────────────┐   │
│  │ Could not join this friendnet.                     │   │
│  │ Check the short code or link, then Retry.          │   │
│  │                                         [ Retry ]  │   │
│  └────────────────────────────────────────────────────┘   │
│  (no “open Tahoe WUI” Next)                               │
└───────────────────────────────────────────────────────────┘
```

---

## W3 — Post-join Folders (PRIMARY) — cleaned hierarchy

```
┌─ Leasegrid Sync ─────────────────────────────────────────┐
│  Folders ●          Storage servers         More ▾        │
│  Online — 2 computers storing files   (click → Servers)   │
│                                                           │
│  Folders                              [ Add folder ]      │
│  ┌─────────────────────────────────────────────────────┐  │
│  │  Documents/work     ● synced                        │  │
│  │  Photos             ● synced                        │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                           │
│  Hosts: 2 connected     [ Manage storage servers ]        │
│                                                           │
│  ┌─ Offer storage on this disk ────────────────────────┐  │
│  │  [==== pie ====]   Offering 40% of this disk        │  │
│  │  Used · Free · Offered                              │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                           │
│  Invite a friend to store files?  [ Share invite ]        │
│  (opens Invite share card — short code + QR + Copy)       │
│                                                           │
│  ✦ Credit stays under More (not a primary tab)            │
│  ✦ Spacing / title weight cleaned vs tip dump             │
└───────────────────────────────────────────────────────────┘
```

---

## W4 — Storage servers (PRIMARY host UX) — polish

```
┌─ Leasegrid Sync ─────────────────────────────────────────┐
│  Folders            Storage servers ●         More ▾      │
│                                                           │
│  Storage servers                                          │
│  Where your files’ shares are stored.                     │
│                                                           │
│  [ + Add storage server ]     ← primary CTA               │
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
│  │  lab-node-3         Available     Announced [ Add ] │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                           │
│  Note: Disconnect removes a server from this home only.   │
└───────────────────────────────────────────────────────────┘
```

---

## W5 — Invite share card (#32) — short code + QR + Copy

Used from: **Servers → Add → Invite**, **Folders → Share invite**, and/or **More → Invite**. Same card.

```
┌─ Share invite ───────────────────────────────────────────┐
│                                                           │
│  Invite someone to join this friendnet                    │
│  (they can Offer disk so you get more storage)            │
│                                                           │
│         ┌──────────────┐                                  │
│         │              │                                  │
│         │   [ QR ]     │                                  │
│         │              │                                  │
│         └──────────────┘                                  │
│                                                           │
│  Short code                                               │
│  ┌───────────────────────────────────────────────────┐    │
│  │  7-orange-tunnel                                  │    │
│  └───────────────────────────────────────────────────┘    │
│                                                           │
│  [ Copy code ]          ← primary                         │
│                                                           │
│  ▸ Show full join link (advanced)                         │
│    (collapsed by default — join URL OK; NOT raw pb://)    │
│                                                           │
│  Wait for them to Join (+ Offer if storing for you).      │
│  They appear under Storage servers when ready.            │
│                                                           │
│                         [ Done ]                          │
└───────────────────────────────────────────────────────────┘
```

**Locks:**
- Primary share = **short code + QR + Copy**
- **No raw introducer FURL** as the default visible invite string or sole Copy target
- Advanced may show join URL (fragment holds secret) — still not labeled as “the FURL”
- Operator copy; FAIL in-window if create/share fails before join

---

## W6 — Add storage server dialog (both paths; Invite uses #32)

```
┌─ Add storage server ─────────────────────────────────────┐
│                                                           │
│  How do you want to add storage?                          │
│                                                           │
│  ● Invite someone to Offer disk                           │
│     → opens / embeds Invite share card (W5)               │
│       short code + QR + Copy                              │
│                                                           │
│  ○ Paste a server link                                    │
│     Paste a storage server link (pb://…) from a host      │
│     you trust.  ← #27 Path B (storage furl, not invite)   │
│                                                           │
│  ───────────────────────────────────────────────────────  │
│  (when Paste selected)                                    │
│  Server link  [ pb://…________________________________ ]  │
│  Nickname (optional) [ _______________________________ ]  │
│                                                           │
│            [ Cancel ]              [ Add server ]         │
└───────────────────────────────────────────────────────────┘
```

Default: **Invite** selected. Paste path always visible (Design DoD #27).

---

## W7 — Add FAIL (paste storage furl)

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

## W8 — Disconnect confirm (unchanged honesty)

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
│            [ Cancel ]              [ Disconnect ]         │
└───────────────────────────────────────────────────────────┘
```

---

## W9 — More menu + Credit secondary (#34 lock)

```
┌─ More ▾ ─────────────────────┐
│  Invite…                     │  ← optional entry to W5
│  Credit                      │  ← secondary; opens Credit place
│  Recovery                    │
│  Settings                    │  ← advanced export OK below Invite
└──────────────────────────────┘

┌─ Credit ─────────────────────────────────────────────────┐
│  Credit                                                   │
│  remaining…                                               │
│  [ Top up ]   ← existing #34 XMR quote → pay → redeem     │
│                                                           │
│  ✦ Not promoted to primary chrome beside Folders/Servers  │
└───────────────────────────────────────────────────────────┘
```

---

## W10 — Anti-wireframe (do NOT ship)

```
┌─ Share invite — FAIL pattern ────────────────────────────┐
│  Introducer FURL                                          │
│  [ pb://long-raw-furl………………………………… ]                  │
│  [ Copy FURL ]                                            │
│  ✦ FORBIDDEN as primary share surface (#32)               │
└───────────────────────────────────────────────────────────┘
```

Also forbidden for this slice: Credit as a third primary top-tab equal to Folders/Servers; burying Invite share only inside a Settings lecture with long URL and no short code/QR/Copy; Tahoe WUI Next.

---

## Visual cleanup checklist (wireframe intent)

| Item | Intent |
|------|--------|
| Margins | Consistent content margins (~24–28px Join; ~12–16px main) |
| Titles | One bold place title per screen |
| Primary CTAs | Join / Add folder / Add server / Copy code — filled button weight |
| Secondary | Flat/text for Import recovery, What's a friendnet, advanced link |
| Density | Reduce stacked lecture before Invite actions |
| FAIL | In-window banner + Retry; never WUI |

Not a full rebrand. Not Marketing.
