# Module: leasegrid_zkap

**Architecture layer:** Authorization (layer 2 in `docs/01-architecture.md`)  
**Code:** `src/leasegrid_zkap/`  
**Related ADR / Decisions:** [ADR-0001](../adr/0001-thin-lab-zkap-authorizer.md), `docs/00-decision.md` corner C, `docs/02-objects.md`

## Operator

### What it does

Lab ZKAP issuer (ristretto faucet, no Monero) and a storage lease gate. Storage refuses allocate / add_lease / renew without a valid token bound to request `R`. Settlement to the issuer sends spent `t` only.

### How to run

See [`deploy/zkap-lab/README.md`](../../deploy/zkap-lab/README.md). Short path on nimo:

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
LEASEGRID_ISSUER_KEY=~/DEVELOP/leasegrid-lab-private/issuer.signing.key
.venv/bin/leasegrid-zkap keygen --key-file "$LEASEGRID_ISSUER_KEY"
.venv/bin/leasegrid-zkap check-0b
```

### Failure modes

| Symptom | Likely cause | Recovery |
|---------|--------------|----------|
| `GATE 0b: FAIL 0b.1` | Issuer not listening / wrong URL | Start `leasegrid-zkap issuer`; check `/v0/info` |
| `GATE 0b: FAIL 0b.2` | Plugin not wrapping Tahoe, or unpaid still allowed | Confirm `plugins = leasegrid-zkap-v0` and restart `tahoe run` |
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

## Agent

### Entry points

- `leasegrid_zkap.cli:main` — operator CLI
- `leasegrid_zkap.check_0b:main` — 0b.1–0b.5 PASS/FAIL
- `leasegrid_zkap.plugin.LeasegridZKAPPlugin` — Tahoe `IFoolscapStoragePlugin`
- `leasegrid_zkap.issuer.start_issuer` — faucet + settlement HTTP
- `leasegrid_zkap.gate.LeaseGate.spend` / `require_allocate`

### Data shapes

- Wallet JSON: `{issuer-pubkey-id, tokens: [{t, W}], denomination}`
- Wire spend: `{t, R, mac}` (base64); `R` is length-prefixed fields
- Settlement: `{spent-preimages: [t, ...]}` — **no `R`**
- Spent-set JSON on storage only (may contain `r_b64`)

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

- `/v0/issue` is the 0c mint hook (add `vid` + payment check later)
- GBS `X-Tahoe-Authorization` extra header would replace out-of-band `/v0/spend`

### Do not

- Commit issuer signing keys, wallets, furls, or caps
- Forward `R` or storage indexes to the issuer
- Claim PyPI ZKAPAuthorizer is loaded on Tahoe 1.20
- Fill `docs/08-lab.md` results as PASS unless `check-0b --live` ran on the friendnet
