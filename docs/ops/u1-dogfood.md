# U1 dogfood — Leasegrid Sync on nimo

**Cite:** `docs/design/14-U0-DEVBOT-HANDOFF.md` · `docs/09-ui-track.md` U1 · design 10–14  
**Host:** nimo (Linux) · **Friendnet:** lab introducer on `leasegrid-1` (`10.42.0.70`) via existing Tahoe client `~/.tahoe`  
**Not:** Tahoe WUI. Do not open `http://127.0.0.1:3456/` as the buyer UI.

## What this proves

A native **Leasegrid Sync** window (PyQt, Gridsync folder-list mental model) joins the existing lab friendnet and one Magic Folder shows observable sync status.

## Prerequisites

- Tahoe 1.20 client already running on nimo: `~/.tahoe` (nickname `nimo`), introducer `friendnet`.
- Confirm without using WUI as product: `leasegrid-sync --status` or `curl -sS 'http://127.0.0.1:3456/?t=json'` (operator check only).
- Python 3.11 or 3.12 with PyQt5 (system 3.14 / `tahoe-venv` may lack PyQt wheels).

## Launch (nimo)

```bash
cd ~/DEVELOP/leasegrid-c
python3.11 -m venv .venv-sync
.venv-sync/bin/pip install -U pip
.venv-sync/bin/pip install -e ".[sync]"
.venv-sync/bin/pip install magic-folder==24.3.0

export LEASEGRID_TAHOE_NODEDIR="$HOME/.tahoe"
export LEASEGRID_TAHOE_BIN="${LEASEGRID_TAHOE_BIN:-$HOME/tahoe-venv/bin/tahoe}"
export PATH="$PWD/.venv-sync/bin:$PATH"

# native window (title: Leasegrid Sync)
leasegrid-sync
```

**Use existing Tahoe node** on first-run if the join page appears (lab-acceptable pre-seeded grid). Invite field accepts a `pb://` introducer furl; HTTP WUI URLs are rejected in-window.

## Folder path

Lab dogfood folder (create if missing):

```text
~/Leasegrid/u1-dogfood
```

In the app: **Folders → Add folder** → pick that directory. Or one-shot with window + probe file:

```bash
mkdir -p ~/Leasegrid/u1-dogfood
leasegrid-sync \
  --dogfood-folder ~/Leasegrid/u1-dogfood \
  --screenshot ~/Leasegrid/u1-sync.png
```

A file `u1-hello.txt` is written; Sync waits until Magic Folder `file-status` / `recent-changes` lists it. Screenshot is evidence for the U1 report.

## Magic Folder daemon

- Config: `$XDG_DATA_HOME/leasegrid-sync/magic-folder` (default `~/.local/share/leasegrid-sync/magic-folder`)
- Listen: `127.0.0.1:19780` (`LEASEGRID_MF_PORT` to override)
- Log: `~/.local/share/leasegrid-sync/logs/magic-folder.log`

The Sync process keeps the Magic Folder daemon alive (stdin held). Closing the window hides to tray when a tray is available; **Quit** from the tray menu stops the app.

## FAIL (in-window)

| Action | FAIL copy |
|--------|-----------|
| Join garbage / HTTP URL / empty invite | Banner on the join page — not a silent no-op |
| Add folder with missing daemon / bad path | Banner on Folders |

There is no “open the web UI” button.

## Env

| Name | Purpose |
|------|---------|
| `LEASEGRID_TAHOE_NODEDIR` | Tahoe client dir (lab: `~/.tahoe`) |
| `LEASEGRID_TAHOE_BIN` | `tahoe` executable |
| `LEASEGRID_MAGIC_FOLDER_BIN` | `magic-folder` executable |
| `LEASEGRID_SYNC_HOME` | App data (daemon config + logs) |
| `LEASEGRID_MF_PORT` | Magic Folder API port (default 19780) |
| `QT_QPA_PLATFORM=offscreen` | CI / no display |

## Deferred (do not expect in this spike)

U2 credit/faucet UI — see [`u2-dogfood.md`](u2-dogfood.md) · U3 AppImage/.deb · U4 recovery HITL · U5 XMR · Settings Tor polish · brand-final name (provisional **Leasegrid Sync**).
