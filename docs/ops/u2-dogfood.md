# U2 dogfood — Credit panel on nimo

**Cite:** `docs/design/19-U2-DEVBOT-HANDOFF.md` · design 15–18 · `docs/09-ui-track.md` U2  
**Host:** nimo (Linux) · **Friendnet:** lab introducer on `leasegrid-1` via existing Tahoe client `~/.tahoe`  
**Issuer:** lab faucet at `http://127.0.0.1:8700` (same issuer as gate 0b)  
**Not:** Tahoe WUI. Do not open `http://127.0.0.1:3456/` as the buyer UI. No mainnet XMR.

## What this proves

A native **Leasegrid Sync** window (U1 Folders intact) exposes **Credit** as a primary place. Balance is remaining GiB·share-months in plain language. **Top up → Request faucet credit** calls the lab issuer and the Credit panel shows the **updated** balance.

## Prerequisites

- U1 still works: `leasegrid-sync --status` shows Connected.
- Lab issuer is up: `curl -sS http://127.0.0.1:8700/health` returns `ok` and an `issuer-pubkey-id`.
- Same venv as U1 (PyQt5 + magic-folder). See [`u1-dogfood.md`](u1-dogfood.md).

## Launch (nimo)

```bash
cd ~/DEVELOP/leasegrid-c
export LEASEGRID_TAHOE_NODEDIR="$HOME/.tahoe"
export LEASEGRID_ISSUER_URL="${LEASEGRID_ISSUER_URL:-http://127.0.0.1:8700}"
.venv-sync/bin/python -m leasegrid_sync
```

Or `scripts/leasegrid-sync-nimo.sh`.

1. Join with **Use existing Tahoe node** if the join page appears.
2. Click **Credit** (next to Folders). Zero credit shows **Credit remaining: none.**
3. **Top up** → pick Medium (≈ 50 GiB·mo) → **Request faucet credit**.
4. Credit home shows **About N GiB kept for ~30 days on this friendnet** and a Recent faucet row.

Headless proof (window + redeem + screenshot, then exit):

```bash
mkdir -p ~/Leasegrid
.venv-sync/bin/python -m leasegrid_sync \
  --offscreen \
  --credit-dogfood \
  --credit-tier small \
  --screenshot ~/Leasegrid/u2-credit.png
```

Balance only (no window):

```bash
.venv-sync/bin/python -m leasegrid_sync --credit-status
```

## Identity / wallet

Faucet mint is bound to **this friendnet's issuer** (`issuer-pubkey-id` from `/v0/info`). Tokens are stored in:

```text
$LEASEGRID_SYNC_HOME/credit-wallet.json
```

Default home: `~/.local/share/leasegrid-sync`. Do not paste a foreign ZKAP wallet here — Credit will reject convert/import.

## Denomination (read this)

**1 token ≈ 1 GiB-share × 30 days on one node.** Encrypted shares expand across nodes, so uploading 1 GiB uses more than 1 GiB of credit. The panel must not read like free disk.

## Folders bridge

With zero credit, **Add folder** FAILs in-window: **[ Open Credit ]**. Top up, then add again. Existing U1 folders keep syncing.

## FAIL (in-window)

| Action | FAIL copy |
|--------|-----------|
| Credit load / Refresh, issuer down | FAIL — could not load credit balance. Next: Retry; … |
| Request faucet credit, issuer/faucet error | FAIL — top-up did not complete. Balance unchanged. Retry / Close |
| Add folder, zero/insufficient credit | FAIL — folder not added. **[ Open Credit ]** |

There is no “open the web UI” button. XMR is a later label only.

## Env

| Name | Purpose |
|------|---------|
| `LEASEGRID_ISSUER_URL` | Lab issuer (default `http://127.0.0.1:8700`) |
| `LEASEGRID_WALLET` | Override wallet path (default `$LEASEGRID_SYNC_HOME/credit-wallet.json`) |
| `LEASEGRID_TAHOE_NODEDIR` | Tahoe client dir (lab: `~/.tahoe`) |
| `LEASEGRID_SYNC_HOME` | App data (wallet + Magic Folder config) |
| `QT_QPA_PLATFORM=offscreen` | CI / no display |

## Deferred (do not expect in this slice)

U3 AppImage/.deb · U4 recovery HITL · U5 XMR top-up · chrome balance chip (optional) · brand-final name (provisional **Leasegrid Sync**).
