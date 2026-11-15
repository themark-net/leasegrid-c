# P4 Android Slice B - Journey (write into a folder you already have)

**Status:** Design DoD 2026-10-03 PT
**Cite:** issue [#44](https://github.com/themark-net/leasegrid-c/issues/44) only · tip ≥ **`be1cfea`** (`be1cfea32ae0277adb8ca0b9698a3c844e4b9862`) · Slice A read path stays `35`–`39` (bodies not rewritten)
**Product:** **Leasegrid Sync (Android)** - the phone can put a file into a folder it already shows. Desktop Sync stays the primary sync home.
**Preserve:** Slice A join / import / folders / download / open; unpaid default; one U4 recovery format; no Tahoe WUI; no new payment rails.

---

## North star (one sentence)

Someone who already has folders on this phone can **add a file to the folder they are looking at**, see that file **In the shared folder** or an in-app **FAIL**, and find the same bytes from desktop Sync - without joining again, without a write-settings screen, and without the phone becoming a second desktop.

---

## Slice B scope (binding)

```
  Folders (already joined)          Slice A welcome if not joined
       │                                      │
       ▼                                      ▼
  Open one folder                      No Add file. Read path only.
       │
       ├─ Add file → pick on device → row: Not in the shared folder yet → In the shared folder
       ├─ Same name already there → Replace / Keep both / Cancel
       └─ Remove (confirm) → gone from the shared folder, or FAIL
```

| In this pack | Out |
|--------------|-----|
| Add a file into a folder already on screen | Create a new folder or a new grid from the phone |
| Row status: Not in the shared folder yet / In the shared folder / FAIL | A fake green "synced" before the write lands |
| Replace or keep both when the name exists | Silent overwrite |
| Remove that file from the shared folder, with confirm | Swipe-to-delete with no confirm |
| Download / open still works (Slice A) | Continuous mirror of the whole tree onto phone storage |
| Desktop Sync still primary | Phone as the only writer, or "make this phone primary" |

---

## What we already know (do not ask)

| Already known after Slice A | Do not ask |
|-----------------------------|------------|
| This phone joined or imported | Invite, user key, recovery file, "which grid" |
| The folder name and that it is open | "Which folder should I sync?" |
| Unpaid is the default | Credit, Offer, or a payment step before the write |
| Desktop Sync is the primary home | "Use this phone as your main sync?" |
| Transport honesty from first-run | A new I2P/Tor/LAN toggle to unlock Add file |

The only new question is the one we cannot know: **which file**, and **replace or keep both** when that name is already in the folder.

---

## Happy path - add a file (already joined)

| Step | Place | Operator does | System does | Exit |
|------|-------|---------------|-------------|------|
| 0 | Launch | Opens Sync Mobile | Restores the session | Folders. No join form. |
| 1 | Folder | Taps the folder they mean | Shows the file list (read still works) | Folder detail |
| 2 | Add file | Taps **Add file** | Opens the system picker. No second Leasegrid form. | Picker |
| 3 | Pick | Picks one file | Copies bytes from the picker; row appears at once as **Not in the shared folder yet** with progress | Row visible |
| 4 | Land | Waits, or leaves the folder | Writes through the same shared folder desktop Sync uses. Chip flips to **In the shared folder** only after that write is acknowledged | In the shared folder, or FAIL |

**Steady state:** Folders stay home. Add file lives on the open folder, not in Settings.

**In the shared folder** means the shared folder has the bytes. It does **not** mean desktop Sync has already pulled them down. If the computer is off, the chip still says In the shared folder, not "On your computer."

---

## Happy path - name already in the folder

| Step | Place | Operator does | System does | Exit |
|------|-------|---------------|-------------|------|
| 1 | Folder detail | Adds a file whose name is already listed | Does **not** overwrite | Sheet |
| 2 | Sheet | Picks **Replace**, **Keep both**, or **Cancel** | Replace writes over that one object. Keep both stores a distinct name and shows it (`beach (phone).jpg`). Cancel drops the pending row. | One clear row, or no change |

We ask because we do not know which copy they want. We do not ask them to type a filename when Keep both can name it.

---

## Happy path - remove

| Step | Place | Operator does | System does | Exit |
|------|-------|---------------|-------------|------|
| 1 | File row that is In the shared folder | Taps **Remove** | Confirm sheet: this leaves the shared folder, not just this phone | Sheet |
| 2 | Confirm | Taps **Remove** | Deletes that object in the shared folder, or FAIL | Row gone, or FAIL |

A row that is still **Not in the shared folder yet** uses different copy: **Discard** - it was never in the shared folder. No shared folder delete.

---

## Happy path - not joined yet

Launch still follows Slice A (welcome / join / import). **Add file is absent** until Folders has a real folder. Do not show a write button that only fails.

---

## FAIL paths (operate-or-FAIL, on this folder)

| Action | What the operator sees |
|--------|------------------------|
| Picker cancelled | No new row. No error. |
| Could not read the picked file | FAIL: could not read this file. Next: pick it again. |
| Not enough space to hold the pending copy | FAIL: not enough free space. Next: free space; Retry. The chip never says In the shared folder. |
| Shared folder unreachable or write rejected | Row stays **Not in the shared folder yet**. FAIL: could not add this file. Next: check network; Retry. |
| Write started and did not finish | Same. Not in the shared folder. Retry sends this file again. Cancel drops the pending row. |
| Folder is read-only for this phone | **Add file** is hidden. One line: "You can download from this folder. Adding files is not available here." Do not offer a button that only fails. |
| Remove did not land | FAIL: could not remove this file. Next: Retry. The row stays until the remove is acknowledged. |

No Tahoe WUI as Next. No "open desktop Sync" as the only Next for a write this phone should do. No silent "will sync later" that looks done.

---

## Phone vs desktop

| Rule | Behavior |
|------|----------|
| Desktop primary | AppImage / native Sync remains the sync home. New folders are still created there. |
| Phone Slice B | Puts, replaces, and removes files in a folder the phone already lists |
| Independence | After join/import, the phone writes to the shared folder without the desktop app running |
| Desktop pickup | Desktop Magic Folder sees the object on its next sync. The phone does not wait for the desktop to claim success |
| Slice A | Download, open, join, and import keep working. This pack does not rewrite `35`–`39` |

---

## Exit criterion

Design exit: this package (`55`–`59`) plus the pointer beside `docs/09-ui-track.md` is on a docs PR. No product UI in that PR.

Implement exit (after this pack is on the PR, then PM RELEASE): **And** emulator dogfood - open an existing folder, add one known file, see **In the shared folder** or FAIL + Retry, and a desktop Sync (or a second client on the same folder) can read those bytes. Read path from Slice A still downloads one file. Desktop Sync on tip still launches.

---

## Honesty

- Do not claim the phone is the primary sync home.
- Do not claim a new folder can be created here.
- Do not claim iOS, Play Store, or a new payment rail.
- Do not claim **In the shared folder** before the write is acknowledged.
- Do not rewrite the U4 recovery format. Export stays on desktop Sync.
