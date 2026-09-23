# Buyer storage — journey (empty Join-first + Storage servers)

**Status:** Design DoD 2026-09-22 PT (~10:15pm PT)  
**Cite:** issue [#27](https://github.com/themark-net/leasegrid-c/issues/27) · tip ≥ **`5b752c7`** (`5b752c70dda4f5b4857c97556ace8881a8fed8f1`) · PM RELEASE 2026-09-22 ~10:12pm PT · **Mark/CEO lock 2026-09-22**  
**Product:** Native **Leasegrid Sync** (desktop buyer). CrashPlan folders-first shell remains primary after join (P1).  
**Preserve:** U0 Join-first intent (`10`–`14`); P1 folders-first; P4 Android `35`–`39` untouched; Offer pie / Credit rank unchanged.

---

## Founder problem (binding cite)

Mark dogfood ~**10:11pm PT** 2026-09-22: Sync showed **“Online — N computers storing files”** with **no Join page** because the home was already joined. He rejects the **“comes populated”** feel.

Context (not a packaging bug): AppImage does **not** hardcode servers — home was already Joined — still a **product FAIL for MVP clarity**.

**MVP:** host X storage + store files to linked nodes. Buyer must **control** storage hosts (add/remove), not only passive introducer discovery. One-line host chrome is not enough.

---

## North star (one sentence)

A clean Sync home shows **Join-first** until the buyer pastes an invite (or recovers); after connect, **Storage servers** is the place that lists hosts and lets the buyer **Add** and **Disconnect** — Join/Add stay reachable forever; never Join-once-and-gone.

---

## Design locks (Mark / CEO / PM — 2026-09-22)

|| Lock | Rule |
||------|------|
|| Empty Join-first | Clean / never-joined home → Welcome/Join (+ threat HITL + invite) is the **only** primary surface. No Folders status chrome like “Online — N computers storing files” until Join (or recovery import) succeeded for **this** home. |
|| No pre-baked grid | AppImage / installer must **not** ship a pre-joined lab home in the buyer artifact. |
|| **Servers screen primary** | **Storage servers** = where data is stored: list hosts, status, **Add**, **Remove/Disconnect**. This **replaces reliance** on the one-line “N computers storing files” chip as the only host UX. Chip may remain as glance status **after** join, but host management lives on Servers. |
|| Join/Add always reachable | After first connect, **Join / Add server** remains reachable from Folders (or Folders → Storage servers → Add). **Join-once-and-gone is FAIL.** |
|| Both Add paths in Design | Wireframes + journey show **both**: (A) invite that hosts Offer / friendnet join path, and (B) paste **storage server** link (`pb://…` storage furl) on Servers → Add. |
|| Implement slice (optional) | DevBot **may** sequence invite-first then furl in code — Design still shows **both**. Both paths are binding Design DoD (roster primary). |
|| Remove honesty | Disconnect removes from **this Sync home’s** connected/used set only. No fake “remove from grid forever.” |
|| Buyer language | Prefer **“Storage servers”** (nodes that hold shares). Tahoe jargon stays out of chrome. |

---

## Happy path A — Fresh empty home → Join → Folders → Servers

|| Step | Place | Buyer does | System does | Exit |
||------|-------|------------|-------------|------|
|| 0 | Launch clean home | Opens Sync (fresh AppImage / empty home dir) | Detects never-joined (`!has_nodedir` / no successful Join for this home) | Welcome/Join only |
|| 1 | Welcome / Join | Reads threat HITL; checks ack; pastes **invite** (wormhole / join URL / introducer) | Creates node; joins introducer; starts client | Connected **or** FAIL |
|| 2 | Folders (PRIMARY) | Lands on CrashPlan folders list + Offer pie | Shows Folders; optional glance chip “Online — N…” **only after** join | Folders primary |
|| 3 | Open Storage servers | Navigates Folders → **Storage servers** (or clear nav) | Lists discovered + pinned servers with status | Servers list visible |
|| 4 | Add (invite path) | Uses **Add** → invite / “Invite someone to Offer” path when bringing a new host that will Offer disk | Friendnet invite / Offer share flow; new host may appear after they join+offer | New row or FAIL |
|| 5 | Add (paste furl) | Uses **Add** → pastes **storage server** furl (`pb://…`) | Validates; remembers; uses for share placement | Row appears **or** FAIL (bad/unreachable) |
|| 6 | Steady | Manages folders; Offer pie; Credit secondary | Hosts remain manageable on Servers | Buyer controls hosts |

---

## Happy path B — Post-join: always Add / always Join

|| Step | Place | Buyer does | System does | Exit |
||------|-------|------------|-------------|------|
|| 1 | Folders (already joined) | Needs another storage host | — | — |
|| 2 | Storage servers | Opens Servers (always reachable) | Lists current connected / used / available | List |
|| 3a | Add → Invite | Starts invite-to-Offer (or Join another invite if product allows multi-step) | Existing U0/U1 invite machinery | Host appears when they Offer **or** FAIL |
|| 3b | Add → Paste server link | Pastes storage furl | Client pins + connects | Connected **or** operate-or-FAIL |
|| 4 | Confirm control | Sees Add still available next session | Join/Add chrome **not** removed after first success | Always reachable PASS |

**FAIL if:** after first Join, buyer cannot find Add / Join / Servers — Join-once-and-gone.

---

## Happy path C — Disconnect / Remove

|| Step | Place | Buyer does | System does | Exit |
||------|-------|------------|-------------|------|
|| 1 | Storage servers | Selects a server → **Disconnect** | Confirm dialog with honest copy | Confirm / Cancel |
|| 2 | Confirm | Confirms | Removes from **this home’s** connected/used set; stops preferring for **new** shares; forgets local pin/entry | Row gone or marked disconnected |
|| 3 | Re-announce (honest) | Later, introducer re-announces same server | May show as “available again” with honest copy | Buyer can Disconnect again or leave unused |

### Promise vs do-not-promise

|| Promise | Do **NOT** promise |
||---------|---------------------|
|| Remove from **this Sync home’s** connected/used set | Permanently eject node from friendnet / introducer for everyone |
|| Stop preferring for new share placement | Wipe shares already on that node |
|| Forget local entry / pin | “Delete forever from the grid” |

---

## Journey map (ASCII)

```
  [Launch Sync]
       │
       ▼
  Clean / never-joined home?
       │
      YES ──────────────────────────────► ┌─────────────────────────────┐
       │                                  │ Welcome / Join (ONLY)       │
       │                                  │ threat HITL + invite paste  │── FAIL ──► in-app FAIL + Next
       │                                  └────────────┬────────────────┘
       │                                               │ PASS
       NO (already joined / recovered)                 │
       │                                               ▼
       └───────────────────────────────► ┌─────────────────────────────┐
                                         │ Folders (PRIMARY)            │
                                         │ + Offer pie                  │
                                         │ glance: Online — N… (ok)     │
                                         │ nav: Storage servers ★       │
                                         │      Join / Add always ★     │
                                         └──────┬──────────┬────────────┘
                                                │          │
                         ┌──────────────────────┘          └──────────────────┐
                         ▼                                                     ▼
              ┌──────────────────────┐                              Credit / Recovery / Settings
              │ Storage servers ★    │                              (unchanged rank — secondary)
              │ list · status        │
              │ [Add] [Disconnect]   │
              └──────────┬───────────┘
                         │
           ┌─────────────┼──────────────┐
           ▼             ▼              ▼
     Add: Invite    Add: Paste     Disconnect
     to Offer       server furl    (honest confirm)
           │             │              │
           └──────┬──────┘              │
                  ▼                     ▼
            operate-or-FAIL        remove from THIS home only
            on bad/unreachable     (not forever from grid)
```

★ Mark 2026-09-22: Servers screen primary for host UX; Join/Add always reachable post-connect.

---

## FAIL paths (operate-or-FAIL)

|| Fail | Buyer sees | Next |
||------|------------|------|
|| Bad invite / join network | In-app FAIL banner | Fix invite / Retry — no WUI |
|| Bad storage furl / unreachable | In-app FAIL on Add dialog | Correct furl / Retry |
|| Disconnect without confirm | Blocked | Must confirm |
|| Clean home shows “Online — N computers” before Join | **Product FAIL** | Must show Join-only |
|| Join/Add unreachable after first connect | **Product FAIL** | Keep nav to Servers / Add |
|| Buyer artifact ships pre-joined lab home | **Product FAIL** | Empty until Join |
|| Copy claims “removed from grid forever” | **Honesty FAIL** | Use Disconnect promise only |

---

## Recovery import (cite U4 — do not rewrite)

Recovery key import for an **existing** home is an alternate path into Folders (U4). After import succeeds for this home, Folders + Storage servers apply; empty Join-first still applies to a **never-joined** clean home.

---

## One-liner

> Clean home = Join-first empty; after join, **Storage servers** lists hosts with **Add** (invite-to-Offer **and** paste storage furl) and honest **Disconnect** — Join/Add always reachable; no fake forever-remove; tip ≥ `5b752c7` · #27.