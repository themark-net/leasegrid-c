# P4 Android Slice B - Wireframes (mobile ASCII)

**Status:** Design DoD 2026-10-03 PT
**Cite:** issue [#44](https://github.com/themark-net/leasegrid-c/issues/44) only · tip ≥ `be1cfea` · Slice A frames stay `37` (not redrawn, not rewritten)
**Shell:** Same phone folders-first app. Write controls sit on the open folder.

ASCII only. Portrait phone. The system file picker is the OS picker; do not rebuild it.

---

## B1 - Folder detail, writable

```
┌──────────────────────────────────────────┐
│ ← Photos                                 │
│                                          │
│ ┌──────────────────────────────────────┐ │
│ │ 🖼  beach.jpg                         │ │
│ │     In the shared folder · 2.4 MB    │ │
│ ├──────────────────────────────────────┤ │
│ │ 🖼  hike.png                          │ │
│ │     In the shared folder · 1.1 MB    │ │
│ └──────────────────────────────────────┘ │
│                                          │
│ [ Add file ]                             │
└──────────────────────────────────────────┘
```

Add file is on this folder. It is not in the overflow menu and not on Folders home.

---

## B2 - Pending row

```
┌──────────────────────────────────────────┐
│ ← Photos                                 │
│                                          │
│ ┌──────────────────────────────────────┐ │
│ │ 🖼  receipt.pdf                       │ │
│ │     Not in the shared folder yet     │ │
│ │     ████████░░░░  62%                │ │
│ │     [ Cancel ]                       │ │
│ ├──────────────────────────────────────┤ │
│ │ 🖼  beach.jpg                         │ │
│ │     In the shared folder             │ │
│ └──────────────────────────────────────┘ │
│                                          │
│ [ Add file ]                             │
└──────────────────────────────────────────┘
```

Cancel drops this pending row. It does not say the file was removed from the shared folder.

---

## B3 - In the shared folder (just landed)

```
┌──────────────────────────────────────────┐
│ ← Photos                                 │
│                                          │
│ ┌──────────────────────────────────────┐ │
│ │ 🖼  receipt.pdf                       │ │
│ │     In the shared folder · 80 KB     │ │
│ │     Open · Remove                    │ │
│ └──────────────────────────────────────┘ │
└──────────────────────────────────────────┘
```

Chip text is **In the shared folder**. Not "Synced", not "On your computer."

---

## B4 - Name already there

```
┌──────────────────────────────┐
│ beach.jpg is already in     │
│ Photos.                     │
│                             │
│ [ Replace ]                 │
│ [ Keep both ]               │
│ [ Cancel ]                  │
└──────────────────────────────┘
```

Replace overwrites that one object. Keep both adds `beach (phone).jpg` as its own row. Cancel leaves the folder unchanged.

---

## B5 - Remove confirm (already in the shared folder)

```
┌──────────────────────────────────────────┐
│ Remove beach.jpg from                    │
│ Photos in the shared folder?             │
│                                          │
│ Other Sync computers will                │
│ lose this copy.                          │
│                                          │
│ [ Remove ]     [ Cancel ]                │
└──────────────────────────────────────────┘
```

---

## B6 - Discard pending (never landed)

```
┌──────────────────────────────────────────┐
│ Discard receipt.pdf?                     │
│                                          │
│ It is not in the shared folder           │
│ yet.                                     │
│                                          │
│ [ Discard ]    [ Cancel ]                │
└──────────────────────────────────────────┘
```

---

## B7 - FAIL on this folder

```
┌──────────────────────────────────────────┐
│ ← Photos                                 │
│                                          │
│ ┌─ FAIL ───────────────────────────────┐ │
│ │ Could not add                        │ │
│ │ receipt.pdf.                         │ │
│ │                                      │ │
│ │ Next: check network;                 │ │
│ │ Retry.                               │ │
│ │                                      │ │
│ │ [ Retry ]  [ Dismiss ]               │ │
│ └──────────────────────────────────────┘ │
│                                          │
│ 🖼  receipt.pdf                           │
│     Not in the shared folder yet         │
│                                          │
│ (rest of the list stays)                 │
└──────────────────────────────────────────┘
```

Dismiss hides the banner. The row stays Not in the shared folder yet. Retry uses this file, not a new picker, unless the bytes were discarded.

---

## B8 - Read-only folder

```
┌──────────────────────────────────────────┐
│ ← Photos                                 │
│                                          │
│ You can download from this               │
│ folder. Adding files is not              │
│ available here.                          │
│                                          │
│ 🖼  beach.jpg                             │
│     In the shared folder · Tap to        │
│     open                                 │
└──────────────────────────────────────────┘
```

No Add file button.

---

## B9 - Folders home (no write chrome)

```
┌─────────────────────────────┐
│ Folders              [⋮]    │
│                             │
│ 📁 Photos                   │
│ 📁 Docs                     │
│                             │
│ - no Add folder -           │
│ - no Sync settings -        │
└─────────────────────────────┘
```

Slice A empty and welcome frames are unchanged. If there is no folder, there is no write control.

---

## Chrome locks (binding)

| Lock | Frame |
|------|-------|
| Add file on the open folder | B1 |
| Pending is not success | B2 |
| In the shared folder, not "on your computer" | B3 |
| Clash is an explicit choice | B4 |
| Remove vs discard are different | B5, B6 |
| FAIL leaves the row honest | B7 |
| Read-only hides Add file | B8 |
| No Add folder, no write settings | B9 |
