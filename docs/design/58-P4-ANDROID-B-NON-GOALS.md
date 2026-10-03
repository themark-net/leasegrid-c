# P4 Android Slice B — Non-goals

**Status:** Design DoD 2026-10-03 PT
**Cite:** issue [#44](https://github.com/themark-net/leasegrid-c/issues/44) only · tip ≥ `be1cfea`

---

## Hard rejects

| Non-goal | Why |
|----------|-----|
| **Product UI in the docs PR** | Pack first. No Android chrome until `55`–`59` are on that PR. |
| **Rewriting Slice A `35`–`39`** | Add `55`–`59` only. Read path stays. |
| **Creating a folder or a grid from the phone** | Desktop Sync still adds folders. |
| **Phone as primary sync, or a "make primary" control** | Desktop Sync stays primary. |
| **Continuous mirror of the whole tree onto phone storage** | Explicit puts. Slice A on-demand download stands. |
| **Automatic camera-roll or "upload everything" toggle** | A settings lever detached from the folder. Out. |
| **Write settings, sync dashboard, or a new tab** | Levers stay on the open folder. |
| **Re-asking invite, recovery file, or user key** | Slice A already has them. |
| **Fake On friendnet / fake green** | Chip flips only after the friendnet acknowledges the write. |
| **Silent overwrite** | Replace / Keep both / Cancel. |
| **Swipe-delete of a friendnet file** | Confirm. Pending discard uses different copy. |
| **New payment rail, Credit gate, or Offer pie on the write path** | Unpaid default. Offer and Credit stay as they are. |
| **Second recovery format, or export-key on the phone** | U4 stays. Desktop still exports. |
| **Tahoe WUI, WebView-as-product, Electron-on-Android** | Same reject as Slice A. |
| **iOS, Play Store listing** | Sideload / CI APK is enough for dogfood. |
| **Demoting or regressing desktop Sync** | Smoke on tip still launches. |
| **Mark drip** | PM routes. Design does not ping Mark. |

---

## Named work that is not this pack

These stay out even if they look adjacent. Do not fold them into the Android write PR.

| Out | What it is |
|-----|------------|
| Relative recovery-file path residual | Not write sync |
| Plant ↔ maximum Magic Folder failure | Not this phone surface |
| Introducer vision | Not this phone surface |
| Offer hosted strip | Already shipped on desktop. Do not redo it here. |

---

## Stretch (not Design exit)

| Item | Note |
|------|------|
| Multi-file pick | One file is enough for dogfood |
| In-app preview of the pending file | System viewer remains enough |
| Background retry after the app is killed | Foreground Retry is the exit. If you add background retry, the row must still say Not on friendnet yet until ack |
| Rename as its own action | Keep both covers the clash. A general rename control is not required |

---

## In-scope reminder

This pack **does** include: Add file on a writable folder the phone already shows; pending vs On friendnet; name clash; remove with confirm; discard pending; read-only hides Add file; operate-or-FAIL; Slice A download/open still works; desktop Sync stays primary; And emulator dogfood after implement.
