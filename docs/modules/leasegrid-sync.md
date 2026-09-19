# Module: leasegrid_sync

**Architecture layer:** Buyer surface (native desktop; not Tahoe layer 0)  
**Code:** `src/leasegrid_sync/`  
**Related:** `docs/09-ui-track.md` U1–U2 · design 10–14 (U0/U1) · design 15–19 (U2) · `docs/ops/u1-dogfood.md` · `docs/ops/u2-dogfood.md` · `docs/ops/u1-gridsync-blocker.md`

## Operator

### What it does

Native **Leasegrid Sync** window: join an existing friendnet, list/add Magic Folders, show sync status, and a **Credit** place wired to the lab issuer/faucet. Tray or minimized window persists. Join/add/credit failures render in-window. It does not open Tahoe WUI.

### How to run

See [`docs/ops/u1-dogfood.md`](../ops/u1-dogfood.md) (Folders) and [`docs/ops/u2-dogfood.md`](../ops/u2-dogfood.md) (Credit). Short path:

```bash
pip install -e ".[sync]"
export LEASEGRID_TAHOE_NODEDIR="$HOME/.tahoe"
export LEASEGRID_ISSUER_URL="http://127.0.0.1:8700"
leasegrid-sync
```

Headless: `leasegrid-sync --status` · `leasegrid-sync --credit-status`. CI: `QT_QPA_PLATFORM=offscreen`.

### Failure modes

| Symptom | Likely cause | Recovery |
|---------|--------------|----------|
| Join FAIL, empty/garbage invite | Not a `pb://` furl | Paste introducer furl or Use existing node |
| Join FAIL, HTTP URL | Buyer pasted WUI | Rejected; use `pb://` or existing nodedir |
| Join FAIL, Tahoe unreachable | Client not running | `tahoe run ~/.tahoe` |
| Add folder FAIL, daemon missing | `magic-folder` not on PATH | Install `magic-folder` 24.3; see U1 dogfood |
| Add folder FAIL, zero credit | No tokens in Sync wallet | Open Credit → Top up, then Add folder |
| Credit load FAIL | Issuer down / wrong URL | Start `leasegrid-zkap issuer`; Retry |
| Faucet redeem FAIL | Issuer rejected or unreachable | Retry; balance unchanged |
| Opaque wallet FAIL | Foreign ZKAP JSON at wallet path | Do not convert; Top up on this friendnet |

## Configuration / variables

| Name | Where | Purpose |
|------|-------|---------|
| `LEASEGRID_TAHOE_NODEDIR` | env | Tahoe client nodedir (lab: `~/.tahoe`) |
| `LEASEGRID_TAHOE_BIN` | env | `tahoe` binary |
| `LEASEGRID_MAGIC_FOLDER_BIN` | env | `magic-folder` binary |
| `LEASEGRID_SYNC_HOME` | env | App data (default `~/.local/share/leasegrid-sync`) |
| `LEASEGRID_ISSUER_URL` | env | Lab issuer/faucet (default `http://127.0.0.1:8700`) |
| `LEASEGRID_WALLET` | env | Override credit wallet path |
| `LEASEGRID_MF_PORT` | env | Magic Folder API port (default 19780) |
| `QT_QPA_PLATFORM` | env | `offscreen` for CI |

## Agent

### Entry points

- `leasegrid_sync.cli:main` — `leasegrid-sync`
- `leasegrid_sync.app.MainWindow` / `run_app` — Qt window
- `leasegrid_sync.backend.TahoeClient` — welcome JSON, join
- `leasegrid_sync.backend.MagicFolderCtl` — init/run/add/list/status via CLI + HTTP API
- `leasegrid_sync.credit.CreditCtl` — issuer ping, faucet redeem, plain-language balance

### Data shapes

- Tahoe `/?t=json`: `{introducers.statuses, servers[]}`
- Magic Folder `GET /v1/magic-folder`: `{name: {magic_path, poll_interval, author}}`
- `GET /v1/magic-folder/<name>/file-status` and `/recent-changes`
- Issuer `GET /v0/info` · `POST /v0/issue` (blinded-tokens)
- Sync wallet JSON: `{issuer-pubkey-id, tokens: [{t, W}], denomination}` under `$LEASEGRID_SYNC_HOME/credit-wallet.json`

### Callers / callees

- CLI → app (lazy PyQt import) → Tahoe HTTP + magic-folder subprocess
- Credit tab → `CreditCtl` → `leasegrid_zkap.client.faucet_mint` / `http_json`
- Tests patch `TahoeClient.welcome` / `MagicFolderCtl._http_get` / inject `CreditCtl`

### Invariants

- No WUI product path (`QDesktopServices.openUrl`, `webbrowser`, “use the web UI” CTA)
- No furls/caps / wallet tokens in git; redact furls in UI errors
- Operate-or-FAIL: join/add/load/refresh/redeem errors set in-window labels + Next + Retry
- Credit is a primary place (tab), not Settings-only
- Denomination: 1 token ≈ 1 GiB-share × 30 days on one node; expansion is real
- No opaque ZKAP convert; no live XMR fields
- Do not wait on gate 0c/XMR to demo credit (lab faucet)

### Extension points

- Chrome balance chip (optional; not U2 exit)
- Settings transport flag copy (U4)
- Recovery export HITL (U4)
- XMR top-up replacing faucet (U5)
- Installer (U3)

### Do not

- Embed or link Tahoe WUI as buyer UI
- Silently no-op join/add/load/redeem
- Fake a successful balance without a real redeem path
- Vendor GPL Gridsync into this Apache tree without a separate package decision (`docs/ops/u1-gridsync-blocker.md`)
- Ship AppImage, recovery HITL, or mainnet XMR as if they were U2
