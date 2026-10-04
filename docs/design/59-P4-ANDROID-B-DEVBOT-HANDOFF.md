# P4 Android Slice B → DevBot / Cursor handoff — **write into a folder you already have**

**Status:** Design DoD 2026-10-03 PT
**Implement against:** `docs/design/` `55`–`58` + issue [#44](https://github.com/themark-net/leasegrid-c/issues/44)
**Cite tip:** main ≥ **`be1cfea`** (`be1cfea32ae0277adb8ca0b9698a3c844e4b9862`)
**This PR:** docs only. Do not implement the app here. Do not merge on Design's say-so.
**Tester:** **And** (Android UI tester) — emulator dogfood after implement, not before the pack is on the PR.
**Do not:** rewrite `35`–`39`; add a folder-create flow; demote desktop Sync; gate write on payment; show On friendnet before ack; contact Mark.

---

## Track map

| Slice | Work | Owner |
|-------|------|-------|
| Desktop Sync | Primary sync home | Preserve — no regress |
| P4-A `35`–`39` | Read-first APK (shipped design) | Leave bodies alone |
| **P4-B `55`–`59`** | Write a file into a folder the phone already lists | **Design → implement after PM RELEASE** |

**This handoff is P4-B only.**

---

## UI

UI: Design-in-loop. Pack in docs/design/ before product UI. Never ask what we know. Levers stay contextual to the current view. Lab bolts OK; product/dogfood UI needs Design pass. UI is the app.

---

## Tests

Tests: prefer E2E/integration/operate-or-FAIL (Trophy). No tautological or implementation-detail unit sprawl. Unit tests only for shaky behavior; must be able to fail with the bug present (sociable where possible). For each risk: how could this fail + how do we recover.

| Risk | How it fails | How we recover |
|------|----------------|----------------|
| Write never landed but the chip says done | Operator trusts a lie | Chip stays **Not on friendnet yet** until friendnet ack. Dogfood asserts the chip **and** that another client can read the bytes. |
| Network dies mid-write | Partial object, or a hang | FAIL on that row + Retry. Retry resends this file. No second picker unless the bytes were discarded. |
| Same filename | Silent overwrite, or a dead button | Sheet: Replace / Keep both / Cancel. Keep both is a different object name visible on the row. |
| Read-only cap | Add file fails every time | Hide Add file. One honest line. Download/open still works. |
| Remove hits the wrong scope | Phone-only delete, friendnet copy remains, or the reverse | Confirm copy says friendnet. Pending rows use **Discard**, not Remove. |
| Slice A read regresses | Can't download | Dogfood still downloads one existing file. |
| Desktop regresses | Sync won't launch | Smoke desktop Sync on the same tip. |

---

## Must prove (implement, after PM RELEASE)

1. Already joined: open app lands on Folders. No invite, user key, or recovery prompt.
2. Writable folder: **Add file** is on that folder. System picker. No Leasegrid form for the path.
3. Pending row shows **Not on friendnet yet** with progress and Cancel. It does not say On friendnet early.
4. After ack, the chip says **On friendnet**. A desktop Sync or second client on that folder can read the bytes. Copy does not say "On your computer."
5. Name clash: Replace, Keep both, and Cancel all do what the sheet says.
6. Remove of an On friendnet file asks, then removes it on the friendnet or FAILs with the row still there. Discard of a pending file does not pretend to delete a friendnet object.
7. Read-only folder: no Add file. Download/open still works.
8. Airplane mode during add: FAIL + Next + Retry in-app. Not a green chip. Not a WUI. Not "only use desktop" as the only Next.
9. Unpaid path: no Credit or Offer step before the write.
10. No new folder button. No write settings screen. No new tab.
11. `35`–`39` files unchanged by the implement PR except a pointer cross-link if PM asks. Prefer not touching them.
12. Desktop Sync on tip ≥ `be1cfea` still launches.
13. **And** files a dogfood note: PASS/FAIL, APK path, emulator image, tip SHA, issue #44. No Mark drip. No Play Store / iOS / new-rail claims.

---

## Explicitly out of implement

| Item | Why |
|------|-----|
| New folder / new grid on the phone | Desktop adds folders |
| Whole-tree mirror, camera-roll upload | Not this pack |
| Payment, Offer hosted strip, Credit changes | No new rails |
| Recovery-path residual, plant↔maximum Magic Folder, introducer vision | Not this surface |
| Rewriting `35`–`39` | Forbidden |
| iOS, Play Store | Out |
| Tahoe WUI / Electron-on-Android | Rejected |

---

## Stack

Extend the Slice A Android app (Kotlin + Jetpack Compose, same friendnet folder caps). Do not start a second app. Do not wrap Tahoe WUI. Min SDK and the real APK path stay whatever Slice A froze; if they differ, the dogfood note cites the real path.

Suggested dogfood APK, until the tree says otherwise: `android/app/build/outputs/apk/debug/app-debug.apk`, installed with `adb install -r`.

---

## Emulator dogfood (for **And**, after implement)

Prereqs: emulator API 34+; a phone already joined to a folder that desktop Sync can also see; one small new file on the device; one file already in that folder.

1. Install the debug APK. Launch. Confirm Folders, not a join form, and no WUI.
2. Open the known folder. Confirm **Add file** is on that screen.
3. Add the new file. Confirm the row reads **Not on friendnet yet** before it reads **On friendnet**.
4. From desktop Sync (or a second client), read those bytes.
5. Add a file with the same name. Confirm Replace / Keep both / Cancel. Cancel leaves the list unchanged.
6. Turn airplane mode on and add another file. Confirm FAIL + Retry, and the chip is not On friendnet.
7. Download/open one file that was already in the folder (Slice A path).
8. If a read-only folder exists in the lab, confirm Add file is absent there.
9. Smoke-launch desktop Sync. Note tip SHA and issue #44 for PM.

---

## Suggested build order

1. Land this docs PR. Stop. Wait for PM RELEASE before product UI.
2. Add file + pending/On friendnet chip on folder detail, writable folders only.
3. Name-clash sheet.
4. Remove vs discard.
5. FAIL + Retry for the dead-network case.
6. Confirm Slice A download still works and desktop still launches.
7. Hand to **And**.

---

## Design references

| Doc | Use |
|-----|-----|
| [55-P4-ANDROID-B-JOURNEY.md](55-P4-ANDROID-B-JOURNEY.md) | Paths + FAIL |
| [56-P4-ANDROID-B-IA.md](56-P4-ANDROID-B-IA.md) | Places + what not to ask |
| [57-P4-ANDROID-B-WIREFRAMES.md](57-P4-ANDROID-B-WIREFRAMES.md) | ASCII frames |
| [58-P4-ANDROID-B-NON-GOALS.md](58-P4-ANDROID-B-NON-GOALS.md) | Rejects |
| `35`–`39` | Read path. Do not rewrite. |
| Issue [#44](https://github.com/themark-net/leasegrid-c/issues/44) | Binding cite |
| Tip ≥ `be1cfea` | Base |

---

## Exit checklist

- [ ] Docs PR contains `55`–`59`, the UI-track pointer, and the README index row. Diff does not touch `35`–`39` or app code.
- [ ] Implement not started in that PR
- [ ] After RELEASE: Add file on the open folder only
- [ ] Pending vs On friendnet is honest under a killed network
- [ ] Second client can read a landed file
- [ ] Clash and remove/discard match the frames
- [ ] And dogfood note to PM — no Mark drip

---

## One-liner for PM

> **P4-B:** Docs pack `55`–`59` for #44. Phone adds a file to a folder it already shows; chip says On friendnet only after ack; desktop Sync stays primary. No app code until you RELEASE. And dogfoods after implement.
