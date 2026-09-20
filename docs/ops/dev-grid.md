# Local client/server in two shells

Runs the whole Leasegrid loop on one Linux box with no friendnet, no nimo, no
VMs: a Tahoe introducer, three storage nodes, the lab ZKAP issuer/faucet, and the
native **Leasegrid Sync** window joining from an invite like a new user would.

Not: Tahoe WUI. Not mainnet XMR. Storage is **not** ZKAP-gated here (that is the
friendnet plugin under [`deploy/zkap-lab/`](../../deploy/zkap-lab/README.md)); the
Credit place still works against the real issuer/faucet.

## Install (once)

```bash
git clone https://github.com/themark-net/leasegrid-c && cd leasegrid-c
python3 -m venv .venv
.venv/bin/pip install -U pip
.venv/bin/pip install -e ".[sync,tahoe]"
```

`[tahoe]` pulls Tahoe-LAFS 1.20, Magic Folder 24.3 and the three pins
(`pyOpenSSL<25`, `cryptography<45`, `service-identity<25`) that keep `tahoe run`
booting on a current resolver. Needs `python3-dev` + a C compiler for `netifaces`
(`sudo apt install python3-dev build-essential` on Debian/Ubuntu).

## Shell 1 — server side

```bash
scripts/dev-grid.sh            # or --reset to wipe previous state
```

Prints the invite furl and stays in the foreground. Ctrl-C stops everything.
State lives in `~/.local/share/leasegrid-devgrid` (`LEASEGRID_DEVGRID_DIR` to
move it). Logs are under `logs/` there.

## Shell 2 — the client

```bash
export PATH="$PWD/.venv/bin:$PATH"
export LEASEGRID_ISSUER_URL="http://127.0.0.1:8700"
leasegrid-sync
```

1. Paste the furl from shell 1 into **Invite** → **Join friendnet**.
   Sync runs `tahoe create-client` into `~/.local/share/leasegrid-sync/tahoe`,
   starts `tahoe run`, and waits for the introducer. Chip:
   **Connected · introducer up · 3 storage**.
2. **Credit** → **Top up** → **Request faucet credit**. Balance updates.
3. **Folders** → **Add folder**. Drop a file in; the row goes **Up to date**.
4. Tray **Quit** stops Magic Folder and the Tahoe client Sync started.
   Relaunching `leasegrid-sync` restarts them and lands on Folders.
5. **Recovery → Export recovery key…**, then on a second `LEASEGRID_SYNC_HOME`
   use **Import recovery key instead…** on the join page. See
   [`u4-recovery.md`](u4-recovery.md).

Headless equivalents (CI / no display):

```bash
leasegrid-sync --status
leasegrid-sync --credit-status
leasegrid-sync --offscreen --credit-dogfood --credit-tier small --screenshot /tmp/credit.png
leasegrid-sync --offscreen --dogfood-folder ~/Leasegrid/demo --screenshot /tmp/sync.png
```

## Which Tahoe node Sync uses

| Situation | Node dir |
|-----------|----------|
| `--nodedir` or `LEASEGRID_TAHOE_NODEDIR` set | that path (nimo: `~/.tahoe`) |
| `~/.tahoe/tahoe.cfg` exists | `~/.tahoe` (pre-existing operator client) |
| otherwise | `~/.local/share/leasegrid-sync/tahoe` (Sync creates it on Join) |

If the node exists but is not running and `tahoe` is on PATH, Sync starts it and
owns the process until Quit. Encoding for a Sync-created client is
`shares.needed/happy/total = 2/3/3` (matches the lab friendnet); override with
`LEASEGRID_SHARES="n,h,t"` before the first Join.

## Env

| Name | Purpose |
|------|---------|
| `LEASEGRID_DEVGRID_DIR` | dev-grid state (default `~/.local/share/leasegrid-devgrid`) |
| `LEASEGRID_DEVGRID_STORAGE` | number of storage nodes (default 3) |
| `LEASEGRID_ISSUER_URL` | issuer for the Credit place (dev-grid: `http://127.0.0.1:8700`) |
| `LEASEGRID_SYNC_HOME` | Sync data: Tahoe client, Magic Folder config, wallet, logs |
| `LEASEGRID_TAHOE_NODEDIR` | force a specific Tahoe client dir |
| `LEASEGRID_SHARES` | `needed,happy,total` for a Sync-created client (default `2,3,3`) |
| `LEASEGRID_TAHOE_BIN` / `LEASEGRID_MAGIC_FOLDER_BIN` | explicit executables |

## FAIL (in-window)

| Action | FAIL copy |
|--------|-----------|
| Join, `tahoe` not installed | FAIL — The Tahoe client is not installed. Next: pip install '…[sync,tahoe]' |
| Join, introducer down | FAIL — Introducer is unreachable. Next: check the network path… |
| Join, node dir exists for another grid | FAIL — A Tahoe client already exists at … but is not connected… Next: set LEASEGRID_TAHOE_NODEDIR |
| Join, Tahoe crashes on start | FAIL — Tahoe exited while starting. Next: see …/logs/tahoe.log |

## Not in this slice

Installer (U3), XMR top-up (U5), ZKAP-gated storage in dev-grid, invite codes
shorter than a furl, macOS / Windows.
