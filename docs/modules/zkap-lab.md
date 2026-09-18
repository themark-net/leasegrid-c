# Module: leasegrid_zkap

**Architecture layer:** Authorization (layer 2 in `docs/01-architecture.md`)  
**Code:** `src/leasegrid_zkap/`  
**Related ADR / Decisions:** [ADR-0001](../adr/0001-thin-lab-zkap-authorizer.md), `docs/00-decision.md` corner C, `docs/02-objects.md`

## Operator

### What it does

Lab ZKAP issuer (ristretto faucet **and** paid `vid` redeem) and a storage lease gate. Storage refuses allocate / add_lease / renew without a valid token bound to request `R`. Settlement to the issuer sends spent `t` only.

Gate 0c default intake is **SIMULATED** (no chain): issuer allocates an 8-byte `vid`, returns a stagenet-format integrated address that embeds it, matches an injected payment by payment ID, then issues a ZKAP batch. nimo mainnet `:18081`/`:18083` is refused before any socket. See [ADR-0002](../adr/0002-simulated-xmr-intake.md).

### How to run

See [`deploy/zkap-lab/README.md`](../../deploy/zkap-lab/README.md). Short path on nimo:

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
LEASEGRID_ISSUER_KEY=~/DEVELOP/leasegrid-lab-private/issuer.signing.key
.venv/bin/leasegrid-zkap keygen --key-file "$LEASEGRID_ISSUER_KEY"
.venv/bin/leasegrid-zkap check-0b
.venv/bin/leasegrid-zkap check-0c   # SIMULATED XMR intake; never :18081
```

### Failure modes

| Symptom | Likely cause | Recovery |
|---------|--------------|----------|
| `GATE 0b: FAIL 0b.1` | Issuer not listening / wrong URL | Start `leasegrid-zkap issuer`; check `/v0/info` |
| `GATE 0b: FAIL 0b.2` | Plugin not wrapping Tahoe, or unpaid still allowed | Confirm `plugins = leasegrid-zkap-v0` and restart `tahoe run` |
| `GATE 0c: FAIL 0c.4` | Paid issue accepted underpay / wrong vid | Do not use faucet `/v0/issue` without `vid` for 0c scoring |
| `FAIL refusing …:18081` | Attempted nimo mainnet monerod | Use `--intake simulated` or a stagenet/regtest RPC on another port |
| `MAC_K(R) invalid` | Wallet from a different issuer key | Remint after copying the same signing key |
| `replay of t against a different R` | Expected on a second SI | Spend a new token |
| VMs cannot `pip install` | No PyPI DNS | Copy wheels from nimo (`scripts/vendor-wheels.sh`) |

## Configuration / variables

| Name | Where | Purpose |
|------|-------|---------|
| `LEASEGRID_ISSUER_KEY` | env | Path to ristretto signing key (off git) |
| `issuer-signing-key-file` | `tahoe.cfg` `[storageserver.plugins.leasegrid-zkap-v0]` | Same key on storage |
| `spend-listen` | tahoe.cfg plugin section | HTTP bind for `/v0/spend` (e.g. `10.42.0.40:8701`) |
| `spent-set-path` | tahoe.cfg plugin section | JSON spent-set on the node |
| `nodeid` | tahoe.cfg or `my_nodeid` | Bound into `R` |
| denomination | `constants.py` | 1 token = 1 GiB-share × 30 days on one node |
| `PICONERO_PER_TOKEN` | `constants.py` | Lab rate 0.001 XMR / token (not a market price) |
| `--intake` | CLI `issuer` | `simulated` (default) or `rpc` |
| `--xmr-rpc` | CLI `issuer` | wallet-rpc URL; ports 18081 and 18083 refused |

## Agent

### Entry points

- `leasegrid_zkap.cli:main` — operator CLI
- `leasegrid_zkap.check_0b:main` — 0b.1–0b.5 PASS/FAIL
- `leasegrid_zkap.check_0c:main` — 0c.1–0c.5 PASS/FAIL (SIMULATED default)
- `leasegrid_zkap.plugin.LeasegridZKAPPlugin` — Tahoe `IFoolscapStoragePlugin`
- `leasegrid_zkap.issuer.start_issuer` — faucet + quote/redeem + settlement HTTP
- `leasegrid_zkap.xmr_intake.SimulatedIntake` / `WalletRpcIntake`
- `leasegrid_zkap.gate.LeaseGate.spend` / `require_allocate`

### Data shapes

- Wallet JSON: `{issuer-pubkey-id, tokens: [{t, W}], denomination}`
- Quote: `{vid, integrated-address, amount_piconero, tokens_owed, …}`
- Wire spend: `{t, R, mac}` (base64); `R` is length-prefixed fields
- Settlement: `{spent-preimages: [t, ...]}` — **no `R`**
- Spent-set JSON on storage only (may contain `r_b64`)
- Voucher (issuer-private): `vid`, amount, `tokens_owed`, paid/spent flags; **no tx secrets in git**

### Callers / callees

- CLI → issuer HTTP / storage HTTP / crypto
- Tahoe plugin `get_storage_server` → `install_on_storage_server` → `StorageServer.allocate_buckets`
- Storage settlement-bundle → issuer `/v0/settlement`

### Invariants

- Domain is `leasegrid-v0` (not a product-letter leftover)
- Issuer never stores or accepts `R` (0b.5)
- Same `t` + same `R` is idempotent; same `t` + different `R` fails
- No caps, furls, or signing keys in git
- No slash, no on-chain spent-set, no L1 (corner C)

### Extension points

- `/v0/issue` with `vid` is the paid 0c mint; without `vid` it is the 0b faucet
- `--intake rpc --xmr-rpc` (non-banned port) replaces simulated inject with wallet-rpc
- GBS `X-Tahoe-Authorization` extra header would replace out-of-band `/v0/spend`

### Do not

- Commit issuer signing keys, wallets, furls, caps, view keys, or txids
- Forward `R` or storage indexes to the issuer
- Connect to nimo mainnet monerod `:18081`/`:18083`
- Put ZKAPs in a Monero payment memo (`vid` is 8 bytes)
- Claim PyPI ZKAPAuthorizer is loaded on Tahoe 1.20
- Record 0c as a live-chain PASS unless a stagenet/regtest scan actually ran (SIMULATED must stay labeled)
