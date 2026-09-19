# Module: leasegrid_sync

**Architecture layer:** Buyer surface (native desktop; not Tahoe layer 0)  
**Code:** `src/leasegrid_sync/`  
**Related:** `docs/09-ui-track.md` U1 · `docs/design/14-U0-DEVBOT-HANDOFF.md` · design 10–13 · `docs/ops/u1-dogfood.md` · `docs/ops/u1-gridsync-blocker.md`

## Operator

### What it does

Native **Leasegrid Sync** window: join an existing friendnet (pre-seeded Tahoe nodedir or `pb://` introducer furl), list/add one Magic Folder, show sync status. Tray or minimized window persists. Join/add failures render in-window. It does not open Tahoe WUI.

### How to run

See [`docs/ops/u1-dogfood.md`](../ops/u1-dogfood.md). Short path:

```bash
pip install -e ".[sync]"
export LEASEGRID_TAHOE_NODEDIR="$HOME/.tahoe"
leasegrid-sync
```

Headless status: `leasegrid-sync --status`. CI: `QT_QPA_PLATFORM=offscreen`.

### Failure modes

| Symptom | Likely cause | Recovery |
|---------|--------------|----------|
| Join FAIL, empty/garbage invite | Not a `pb://` furl | Paste introducer furl or Use existing node |
| Join FAIL, HTTP URL | Buyer pasted WUI | Rejected; use `pb://` or existing nodedir |
| Join FAIL, Tahoe unreachable | Client not running | `tahoe run ~/.tahoe` |
| Add folder FAIL, daemon missing | `magic-folder` not on PATH | Install `magic-folder` 24.3; see dogfood |
| Add folder FAIL, bad path | Directory missing / not writable | Pick an existing folder |
| Window closes, process gone | No tray on this desktop | Use tray Quit; otherwise window minimizes |

## Configuration / variables

| Name | Where | Purpose |
|------|-------|---------|
| `LEASEGRID_TAHOE_NODEDIR` | env | Tahoe client nodedir (lab: `~/.tahoe`) |
| `LEASEGRID_TAHOE_BIN` | env | `tahoe` binary |
| `LEASEGRID_MAGIC_FOLDER_BIN` | env | `magic-folder` binary |
| `LEASEGRID_SYNC_HOME` | env | App data (default `~/.local/share/leasegrid-sync`) |
| `LEASEGRID_MF_PORT` | env | Magic Folder API port (default 19780) |
| `QT_QPA_PLATFORM` | env | `offscreen` for CI |

## Agent

### Entry points

- `leasegrid_sync.cli:main` — `leasegrid-sync`
- `leasegrid_sync.app.MainWindow` / `run_app` — Qt window
- `leasegrid_sync.backend.TahoeClient` — welcome JSON, join
- `leasegrid_sync.backend.MagicFolderCtl` — init/run/add/list/status via CLI + HTTP API

### Data shapes

- Tahoe `/?t=json`: `{introducers.statuses, servers[]}`
- Magic Folder `GET /v1/magic-folder`: `{name: {magic_path, poll_interval, author}}`
- `GET /v1/magic-folder/<name>/file-status` and `/recent-changes`

### Callers / callees

- CLI → app (lazy PyQt import) → Tahoe HTTP + magic-folder subprocess
- Tests patch `TahoeClient.welcome` / `MagicFolderCtl._http_get`

### Invariants

- No WUI product path (`QDesktopServices.openUrl`, `webbrowser`, “use the web UI” CTA)
- No furls/caps in git; redact furls in UI errors
- Operate-or-FAIL: join/add errors set in-window labels
- Folders is the only primary place in U1; Credit/Recovery are U2/U4
- Do not wait on gate 0c/XMR to demo sync

### Extension points

- Credit tab → `leasegrid_zkap` faucet (U2); not Gridsync PrivateStorage vouchers
- Settings transport flag copy (U4)
- Installer (U3)

### Do not

- Embed or link Tahoe WUI as buyer UI
- Silently no-op join/add
- Vendor GPL Gridsync into this Apache tree without a separate package decision (`docs/ops/u1-gridsync-blocker.md`)
- Implement U2–U5 in this module as if they were U1
