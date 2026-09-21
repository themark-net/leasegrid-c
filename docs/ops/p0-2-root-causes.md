# P0.2 — top 3 root causes (boots + sync one folder)

**Issue:** [#10](https://github.com/themark-net/leasegrid-c/issues/10) · **Plan:** [docs/10-post-fable-plan.md](https://github.com/themark-net/leasegrid-c/blob/main/docs/10-post-fable-plan.md) P0.2  
**Branch:** `cursor/runnable-local-client-server-056d` (PR #7)

P0.1 ([#8](https://github.com/themark-net/leasegrid-c/issues/8)) had no crash logs on the ticket. Harvest is founder dogfood on this branch plus self-repro: close-to-tray, daemon consoles, add-folder exceptions escaping Qt.

## Ranked

1. **Close hid the window to tray** (`setQuitOnLastWindowClosed(False)` + `_on_close` `event.ignore()` / `hide()`). Closing looked like a crash. Relaunch started a second process while the first still held Tahoe/Magic Folder. **Fix:** X quits; daemons stop.

2. **Add folder / folder list exceptions aborted or vanished.** `refresh` and `on_add_folder` only caught `SyncError`. Anything else reached a PyQt5 slot → `qFatal` (process abort) or a tiny red line with no progress. First Magic Folder start can take a minute with no indicator. **Fix:** wrap unexpected errors as in-window FAIL; show “Adding folder…”.

3. **Tahoe / magic-folder spawned with a console** (`Popen` of `console=True` frozen exes, no `CREATE_NO_WINDOW`). A second window flashed then disappeared — same “crash” report. **Fix:** `popen_hidden`.

## Dogfood bar (this slice)

- App boots; closing the window quits.
- Chip is “Online — N computers storing files”, plus a line for offering disk or not.
- Unpaid Add folder: progress copy, FAIL stays in the Folders place, no process abort.

**Self-repro (unpaid, this branch):** local `dev-grid.sh` (GATED unset) + `leasegrid-sync --join <furl> --dogfood-folder`. Result: `U1 dogfood folder=… probe=…/u1-hello.txt` uploaded; `[storage] enabled = true`. Pytest 244 passed.

Not in P0.2: CrashPlan disk pie (P1); Magic Folder *invite someone to this folder* UI; payment lecture.
