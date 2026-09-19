# U1 report — Gridsync spike (Leasegrid Sync)

**Status:** PASS (nimo lab, 2026-09-19)  
**Cite:** `docs/design/14-U0-DEVBOT-HANDOFF.md` · design 10–13 · `docs/09-ui-track.md`  
**Branch:** `feat/u1-gridsync-spike` · **Repo:** themark-net/leasegrid-c  
**HEAD:** fill after commit (`git rev-parse HEAD`)

Native **Leasegrid Sync** (PyQt wrap, Gridsync folder-list mental model + Magic Folder). Not Tahoe WUI. Not Electron. Credit / installer / recovery HITL / XMR wait for U2–U5.

## U1 exit checklist

| # | DoD | Result |
|---|-----|--------|
| 1 | Native window boots on Linux | **PASS** — title `Leasegrid Sync`; screenshot `docs/ops/u1-sync.png` |
| 2 | Joins existing friendnet | **PASS** — nimo `~/.tahoe` introducer `friendnet` on `leasegrid-1` (`10.42.0.70`); status `Connected · introducer up · 3 storage` |
| 3 | One Magic Folder syncs | **PASS** — folder `u1-dogfood` at `~/Leasegrid/u1-dogfood`; probe `u1-hello.txt` appeared in Magic Folder `file-status` (`relpath=u1-hello.txt`, `size=34`, `last-updated` set). Window row: **Up to date**. |
| 4 | No WUI-as-product | **PASS** — no Open-web-UI CTA; HTTP WUI URLs rejected on join; `tests/test_sync_no_wui.py` |
| 5 | Tray or window persist | **PASS** — `QSystemTrayIcon` hide-on-close; `QApplication.setQuitOnLastWindowClosed(False)`; not a one-shot CLI-only demo (`leasegrid-sync` runs `exec_()`) |
| 6 | Crude in-window FAIL on join/add | **PASS** — join garbage/empty/HTTP URL and add-folder bad path set in-window banners (`tests/test_sync_ui.py`) |
| 7 | Dogfood steps written | **PASS** — `docs/ops/u1-dogfood.md` |
| 8 | Explicit U2–U5 deferred list | **PASS** — below + Settings stub + `docs/ops/u1-gridsync-blocker.md` |

**Not FAIL:** CLI-only `tahoe magic-folder` with no window; WUI as primary UI; no folder sync; waiting on gate 0c.

## Evidence (sync)

```
leasegrid-sync --dogfood-folder ~/Leasegrid/u1-dogfood --screenshot ~/Leasegrid/u1-sync.png
U1 dogfood folder=/home/mark/Leasegrid/u1-dogfood
probe=/home/mark/Leasegrid/u1-dogfood/u1-hello.txt
status={'relpath': 'u1-hello.txt', 'mtime': 1789831840, 'last-updated': 1789831900,
        'last-upload-duration': None, 'size': 34}
```

Screenshot (copied to git): [`docs/ops/u1-sync.png`](docs/ops/u1-sync.png) — Folders place, `u1-dogfood` **Up to date**, chip **Connected introducer up · 3 storage**.

Friendnet: existing nimo client `~/.tahoe` (Tahoe 1.20.0), introducer `leasegrid-1`. Magic Folder 24.3.0 in `.venv-sync`. Daemon log: `~/.local/share/leasegrid-sync-u1-dogfood/logs/magic-folder.log` (`Connected to 3 storage-servers`).

## Stack

Tight **wrap**, not an in-tree Gridsync fork (GPL-3.0 vs Apache-2.0; PrivateStorage ZKAP plugin vs `leasegrid-zkap-v0`). Lineage kept: PyQt native window, folder list/status, Magic Folder daemon, tray. See `docs/ops/u1-gridsync-blocker.md`. **Did not switch to WUI.**

## Deferred to U2–U5

| Item | Slice |
|------|-------|
| Credit panel + faucet redeem UI | **U2** |
| AppImage / .deb installer polish | **U3** |
| Recovery key export + first-run threat HITL (production copy) | **U4** |
| XMR top-up replacing faucet | **U5** (after gate 0c) |
| Settings Tor vs sync design-flag polish | U4 / Settings (stub in U1) |
| Brand-final names | provisional **Leasegrid Sync** |
| macOS / Windows | after Linux dogfood |

## How to launch on nimo

`docs/ops/u1-dogfood.md`. Short:

```bash
cd ~/DEVELOP/leasegrid-c
export LEASEGRID_TAHOE_NODEDIR="$HOME/.tahoe"
.venv-sync/bin/python -m leasegrid_sync
# folder: ~/Leasegrid/u1-dogfood
```

## CI

- `scripts/ci-local.sh` — local PASS (ruff + pytest; `QT_QPA_PLATFORM=offscreen`; optional `[sync]` extra)
- `.github/workflows/ci.yml` — `.[dev,sync]` + offscreen pytest; push `feat/**` + PRs

## Paths

- `src/leasegrid_sync/` — app
- `docs/design/10–14` + `docs/09-ui-track.md` — U0 design package on this branch
- `docs/modules/leasegrid-sync.md` — module map
