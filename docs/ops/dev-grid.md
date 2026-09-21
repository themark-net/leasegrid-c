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
# --chain fake is the default (XMR quote → /v0/fake/pay → redeem).
# --chain none disables quotes (issuer still serves the lab faucet).
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

1. Paste the furl from shell 1 (or a short code, below) into **Invite** → **Join friendnet**.
   Sync runs `tahoe create-node` into `~/.local/share/leasegrid-sync/tahoe` (client +
   storage; uncheck **Offer disk** for `--no-storage`), starts `tahoe run`, and waits
   for the introducer. Chip: **Connected · introducer up · 3 storage**.
   Offering disk uses `LEASEGRID_STORAGE_HOSTNAME` (default `127.0.0.1`, so other
   lab nodes on this machine can reach it).
2. **Credit** → **Top up** → **Request faucet credit**. Balance updates.
   XMR (FakeChain, no Monero daemon) from another shell:
   `leasegrid-zkap topup --issuer http://127.0.0.1:8700 --wallet "$LEASEGRID_SYNC_HOME/credit-wallet.json" --tokens 20 --json`
   then `POST /v0/fake/pay` with that `vid` and `mine: 2`, then **Credit → Retry**
   (or `leasegrid-sync --credit-status`). U5 will put this quote/pay/pending
   flow in the window.
3. **Folders** → **Add folder**. Drop a file in; the row goes **Up to date**.
4. Tray **Quit** stops Magic Folder and the Tahoe client Sync started.
   Relaunching `leasegrid-sync` restarts them and lands on Folders.
5. **Recovery → Export recovery key…**, then on a second `LEASEGRID_SYNC_HOME`
   use **Import recovery key instead…** on the join page. See
   [`u4-recovery.md`](u4-recovery.md).

### Short invite codes instead of a furl

A furl is ~90 characters. `tahoe invite` hands the same settings over
magic-wormhole as a one-time code (`7-guitarist-revenge`). With the grid up:

```bash
scripts/dev-grid.sh --invite alice        # shell 3: prints "Invite Code for client: 7-…"
```

Paste the code into **Invite** → **Join friendnet** (or `leasegrid-sync --join 7-…`).
The inviter sits on the relay until exactly one joiner uses the code, then exits;
the joiner gets the introducer, the encoding (`LEASEGRID_SHARES`, default 2/3/3)
and the nickname from the invite, and Sync fixes the `b'2'` share counts Tahoe
1.20 writes on `--join` before starting the client.

dev-grid runs its own mailbox relay on `ws://127.0.0.1:45040/v1` (offline,
deterministic) when `magic-wormhole-mailbox-server` is installed (it is in the
`[tahoe]` extra); the client must be pointed at it:
`export LEASEGRID_WORMHOLE_SERVER="ws://127.0.0.1:45040/v1"`. Without that env the
client uses Tahoe's public relay, which is also what a real cross-machine invite
uses (`LEASEGRID_DEVGRID_WORMHOLE=public` makes dev-grid do the same). Codes are
single-use; a dead code fails in-window with "Invite code … was not accepted;
ask your inviter for a fresh one".

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
owns the process until Quit. Encoding for a Sync-created node is
`shares.needed/happy/total = 2/3/3` (matches the lab friendnet); override with
`LEASEGRID_SHARES="n,h,t"` before the first Join. Unpaid join and offer are the
same `create-node` path; `--client-only` / uncheck Offer disk adds `--no-storage`.

## Env

| Name | Purpose |
|------|---------|
| `LEASEGRID_DEVGRID_DIR` | dev-grid state (default `~/.local/share/leasegrid-devgrid`) |
| `LEASEGRID_DEVGRID_CHAIN` | `fake` (default) or `none`; same as `--chain` |
| `LEASEGRID_DEVGRID_STORAGE` | number of storage nodes (default 3) |
| `LEASEGRID_ISSUER_URL` | issuer for the Credit place (dev-grid: `http://127.0.0.1:8700`) |
| `LEASEGRID_SYNC_HOME` | Sync data: Tahoe node, Magic Folder config, wallet, logs |
| `LEASEGRID_TAHOE_NODEDIR` | force a specific Tahoe node dir |
| `LEASEGRID_SHARES` | `needed,happy,total` for a Sync-created node and for `dev-grid --invite` (default `2,3,3`) |
| `LEASEGRID_STORAGE_HOSTNAME` | advertised storage hostname for unpaid offer-on-join (default `127.0.0.1`) |
| `LEASEGRID_WORMHOLE_SERVER` | relay for short invite codes (client; unset = Tahoe's public relay) |
| `LEASEGRID_DEVGRID_WORMHOLE` / `_PORT` | dev-grid relay: `auto` (local if installed), `local`, `public`; port 45040 |
| `LEASEGRID_TAHOE_BIN` / `LEASEGRID_MAGIC_FOLDER_BIN` | explicit executables |

## FAIL (in-window)

| Action | FAIL copy |
|--------|-----------|
| Join, `tahoe` not installed | FAIL — The Tahoe client is not installed. Next: pip install '…[sync,tahoe]' |
| Join, introducer down | FAIL — Introducer is unreachable. Next: check the network path… |
| Join, node dir exists for another grid | FAIL — A Tahoe node already exists at … but is not connected… Next: set LEASEGRID_TAHOE_NODEDIR |
| Join, Tahoe crashes on start | FAIL — Tahoe exited while starting. Next: see …/logs/tahoe.log |

## Paid mode

`LEASEGRID_GATED=1 scripts/dev-grid.sh` makes every storage node run the
`leasegrid-zkap-v0` plugin: uploads are refused until the Sync client has Credit,
and each upload spends tokens. Details, evidence and the denomination finding
in [`paid-path.md`](paid-path.md). A grid created gated stays gated (`--reset` to
go back).

## Not in this slice

U5 window states for XMR (quote / pay URI / pending / confirmed). The rail
itself is in tree against FakeChain — see [`07-payment.md`](../07-payment.md)
S5 and [`paid-path.md`](paid-path.md). Installers for all three OSes are in
[`installers.md`](installers.md).
