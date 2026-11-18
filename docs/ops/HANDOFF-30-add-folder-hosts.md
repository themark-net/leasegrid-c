# Handoff: #30 slice 1 (Add folder checks the hosts first)

Branch `bot/30-add-folder-storage` off `main` `0383254`. Issue: [#30](https://github.com/themark-net/leasegrid-c/issues/30). No release, no tag. CHANGELOG line under Unreleased.

## Why #30 and not #33

- [#30](https://github.com/themark-net/leasegrid-c/issues/30) is the only known issue in `docs/TESTER-GUIDE.md` that stops a friends-and-family tester from syncing at all: Add folder fails with Magic Folder HTTP 500 and the folder never reaches Up to date.
- [#33](https://github.com/themark-net/leasegrid-c/issues/33) is vision only: "no build yet", mechanism undecided, conceptually blocked by payment rails and Android. Building it needs a founder decision first.

## Root cause read from the #30 report

The failing run reached Connected (introducer up) and then the storage count settled from 3 to 0. Magic Folder `add` makes Tahoe directories, and Tahoe needs `shares.happy` connected hosts for that. With 0 hosts the create fails, and Magic Folder answers HTTP 500. The same class cleared on plant, where the hosts stayed connected. This slice handles that case. It does not prove that every #30 500 is a host shortage, so #30 stays open.

## What changed

1. `src/leasegrid_sync/app.py`: `hosts_short_for_add(status, happy)` returns the error when the introducer is Connected and fewer hosts are connected than `shares.happy`. Any other state (Tahoe unreachable, Offline, Connecting) is not a shortage, so Add folder runs as before.
2. `MainWindow.on_add_folder` checks before the folder picker. `shares.happy` comes from this node's `tahoe.cfg` (`read_shares`), so a grid with happy 2 adds with 2 hosts.
3. If the add fails with a `SyncError` and no credit refusal, the hosts are checked again. Hosts that dropped during the add get the hosts line instead of the #30 HTTP 500 text. A 500 with enough hosts still names #30.
4. Copy: `folder not added. Hosts connected: N of M needed.` and Next `wait until Hosts shows M connected, then Retry Add folder.` It reuses the existing Hosts line on Folders. **Design Bot input requested** for the final wording; the slice ships the plain version, which follows the existing banner grammar.
5. `CHANGELOG.md` Unreleased line. `docs/TESTER-GUIDE.md` is not touched: `tests/test_tester_pages.py` forbids not-released caveats there, so the #30 known-issue text gets updated at the next release prep.
6. `tests/test_sync_folder_journey.py`: the Tahoe stand-in announced 1 connected host on a grid with `shares.happy = 3`, which real Tahoe could not add a folder on. It now announces 3, and the restart check reads "3 computers". With 1 host the journey went red on the new check, which is the behaviour this slice wants.

## Tests (red first)

Six tests at the end of `tests/test_sync_ui.py`. Before the change three failed (no hosts stops before the picker; 2 of 3 stops and 3 of 3 proceeds; 500 after hosts dropped names the hosts). Three pass both before and after and pin what must not change (happy read from config, 500 with enough hosts still names #30, unreachable Tahoe keeps the old path). Full suite (730 passed) and ruff green on nimo.

## What remains on #30

- The `--dogfood-folder` CLI path (`app.py`, `u1-dogfood`) does not have the check yet.
- A live multi-host recheck (plant and maximum) to see whether any 500 remains with enough hosts connected. That needs the hosts and is not a bot task.
- Optional next slice: when hosts come back, offer Retry from the banner without opening the picker again.
