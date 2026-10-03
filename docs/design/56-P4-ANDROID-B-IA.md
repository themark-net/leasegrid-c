# P4 Android Slice B — Information architecture (phone)

**Status:** Design DoD 2026-10-03 PT
**Cite:** issue [#44](https://github.com/themark-net/leasegrid-c/issues/44) only · tip ≥ `be1cfea` · Slice A places stay `36` (not rewritten)

---

## Places (phone)

| Place | Rank | Role in Slice B |
|-------|------|-----------------|
| **Folders** | **Primary** | Home after join/import. Unchanged from Slice A. No write control here except opening a folder. |
| **Folder detail** | **Primary** | File list plus **Add file**. This is the write surface. |
| **Add / picker** | Transient | System file picker. Not a Leasegrid form. |
| **Name clash sheet** | Transient | Replace / Keep both / Cancel. Only when the name exists. |
| **Remove confirm** | Transient | On that file row. Friendnet remove vs discard-pending. |
| **File row status** | On the row | Not on friendnet yet · On friendnet · FAIL |
| **Welcome / Join** | First-run only | Slice A. No Add file. |
| **More / Settings** | Secondary | Slice A notes only. **No write-sync settings.** |
| **Offer / Credit** | N/A | Not a gate and not a new tab. |

Write stays on the folder you have open. It does not get a new home, a new tab, or a settings graveyard.

---

## Object model (buyer-facing)

| Object | Operator meaning |
|--------|------------------|
| **Folder** | A friendnet folder this phone already listed. Write targets this one. |
| **File row** | An object in that folder, whether it came from desktop or from this phone |
| **Pending file** | Bytes we have, not yet acknowledged on the friendnet. Label: **Not on friendnet yet** |
| **On friendnet** | The folder on the friendnet has this version. Not a claim about the desktop's disk. |
| **Read-only folder** | This phone can download. It cannot add. Say so. Hide Add file. |

---

## Primary vs secondary CTA

| Context | Primary | Secondary |
|---------|---------|-----------|
| Folder detail (writable) | **Add file** | Tap a file to Download / Open (Slice A). Row overflow: Replace, Remove. |
| Folder detail (read-only) | Download / Open | The read-only line. No Add file. |
| Name clash | **Replace** or **Keep both** (both real) | Cancel |
| Pending row | Wait, or **Retry** if FAIL | Cancel (drops the pending row) |
| On friendnet row | Open | Remove |
| Remove confirm (on friendnet) | **Remove** | Cancel |
| Pending discard | **Discard** | Cancel |
| Folders home | Tap a folder | Pull to refresh. No Add folder. |

---

## Navigation rules

1. Already joined → Folders. Do not insert a write setup step.
2. Add file, replace, and remove never leave this folder for a settings screen.
3. Back from folder detail → Folders. A pending row survives leaving the screen, still labeled Not on friendnet yet.
4. Offer and Credit stay off this path.
5. Do not add a bottom-nav "Sync" or "Upload" item.
6. Slice A frames (welcome, import, download) stay as they are. This pack only adds write on folder detail.

---

## Copy hierarchy

| Layer | Tone | Example |
|-------|------|---------|
| Add | Calm, local | "Add file" |
| Pending | Honest, not done | "Not on friendnet yet" |
| Success | Specific | "On friendnet" |
| Clash | One decision | "A file named beach.jpg is already in Photos." |
| Remove | Direct | "Remove beach.jpg from Photos on the friendnet? Other Sync computers will lose this copy." |
| Discard pending | Different verb | "Discard this file? It is not on the friendnet yet." |
| Read-only | Plain | "You can download from this folder. Adding files is not available here." |
| FAIL | Operate-or-FAIL | FAIL — could not add this file. Next: check network; Retry. |
| Desktop | Honest, not demoting | "New folders are still added in Leasegrid Sync on your computer." |

---

## Relationship to Slice A

| Slice A lock | Slice B |
|--------------|---------|
| Folders primary | Stands |
| Phone is not a second desktop writer | Stands as "not a second desktop." Write is an explicit put into a folder you already have. |
| Add folder parked | Still parked. Not this pack. |
| Hide half-shipped write buttons | Lifted only for Add file / Replace / Remove on a writable folder. Anything else stays hidden. |
| Export recovery on desktop | Stands. Write does not export a key. |
| `35`–`39` bodies | Not rewritten |

P4-B **adds** `55`–`59`. It does not replace `35`–`39`.
