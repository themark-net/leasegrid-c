# Gate 0c report

**Status: PASS (SIMULATED)** (local harness, 2026-09-17)

No Monero chain was used. nimo mainnet `monerod` `:18081`/`:18083` was **not** contacted. No mainnet wallet, view key, or transaction.

`leasegrid-zkap check-0c` printed `GATE 0c: PASS  intake=SIMULATED  network=stagenet-format (no chain)` for 0c.1–0c.5. `check-0b` still prints `GATE 0b: PASS` (regression). `docs/08-lab.md` results log updated. ADR-0002.

## What landed

- Paid mint on the existing issuer: `POST /v0/quote` allocates an 8-byte `vid` and a **stagenet-format** integrated address that embeds it (netbyte 25, 106 chars, keccak checksum, Monero base58).
- **SIMULATED** intake: `POST /v0/intake/simulate` injects a payment; issuer “view-key scan” matches `payment_id == vid`.
- `POST /v0/issue` **with `vid`** mints a ZKAP batch only if the voucher is paid, not underpaid, and not already spent. Batch DLEQ still verifies via `python-challenge-bypass-ristretto`.
- `POST /v0/issue` **without `vid`** remains the 0b faucet.
- Hard ban: wallet-rpc URLs on ports **18081** and **18083** fail closed before a socket. Mainnet address encoding is refused.
- Optional `--intake rpc --xmr-rpc` is wired for a future stagenet/regtest daemon (not used here; no `:38081` listener).

Reuse: `src/leasegrid_zkap/` (issuer, ristretto, `R`, spent-set, Tahoe 1.20 wrap). No PyPI ZKAPAuthorizer.

## DoD (docs/08-lab.md gate 0c)

| Step | Result | Notes |
|------|--------|-------|
| 0c.1 | **PASS** | 8-byte `vid` embedded in stagenet integrated address |
| 0c.2 | **PASS (SIMULATED)** | Injected payment; scan matched `vid`; confirmations = 1 |
| 0c.3 | **PASS** | 2 tokens issued; DLEQ ok; voucher marked spent |
| 0c.4 | **PASS** | Unpaid, wrong `vid`, underpay, unknown `vid` → no tokens |
| 0c.5 | **PASS** | Spend on Tahoe 1.20 wrapped allocate + renew; unpaid SI still 403 |

**FAIL-if checks:** ZKAPs are not in the 8-byte memo (only `vid`). Issuance without a matching payment is refused on the paid path.

## Record (no secrets)

| Field | Value |
|-------|-------|
| Network | **SIMULATED** (stagenet-format addresses; no daemon) |
| Approximate amount | 0.002 XMR quote (2 tokens × 0.001 XMR lab rate) |
| Confirmations required | 1 (simulated) |
| Mainnet `:18081`/`:18083` | never used |
| Tahoe | 1.20.0 wrap on local `StorageServer` for 0c.5 |
| Denomination | 1 token = 1 GiB-share × 30 days on one node |

## How to run

```bash
# from this worktree; do not use /home/mark/DEVELOP/leasegrid-c
PYTHONPATH=src /home/mark/tahoe-venv/bin/python -m leasegrid_zkap.check_0c
PYTHONPATH=src /home/mark/tahoe-venv/bin/python -m leasegrid_zkap.check_0b
```

Or after `pip install -e .` into a worktree venv:

```bash
leasegrid-zkap check-0c
```

Signing key stays at `~/DEVELOP/leasegrid-lab-private/issuer.signing.key` (mode 0600, not in git).

## Blockers

None for **SIMULATED** 0c. Known limits (not FAIL):

- No stagenet or private `monerod` was running; live chain scan is not claimed.
- Faucet mint without `vid` still exists for 0b.
- Paid `tahoe put` (CHK) still has no GBS ZKAP header; 0c.5 is spend + wrapped allocate/renew, same as 0b.4.

## PR

Push target: `origin/lab/gate-0c-stagenet`.

Do **not** push from `/home/mark/DEVELOP/leasegrid-c` (DevBot / gate 0b CI).
