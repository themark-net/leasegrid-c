# ADR-0002: Simulated XMR intake for gate 0c (no mainnet)

- **Date:** 2026-09-17
- **Status:** Accepted
- **Deciders:** Gate 0c implementation (lab/gate-0c-stagenet)

## Context

Gate 0c is XMR → 8-byte `vid` (integrated-address payment ID) → ZKAP batch from the same issuer as gate 0b. `GATE0C_NETWORK_CONSTRAINT.md` forbids nimo mainnet `monerod` (`:18081` / `:18083`). This host has that mainnet daemon and no stagenet/regtest daemon.

## Decision

1. Default issuer intake is **SIMULATED**: allocate `vid`, return a real **stagenet-format** integrated address that embeds it, inject a payment, match by payment ID (the “view-key scan”), then `/v0/issue` with `vid` mints ZKAPs and marks the voucher spent.
2. Never encode mainnet addresses. Refuse wallet-rpc URLs on ports **18081** and **18083** before opening a socket. Refuse `nettype=mainnet` if a future stagenet/regtest RPC is wired.
3. Keep the 0b faucet (`/v0/issue` without `vid`). Paid issuance **requires** a matching payment at or above the quote. Underpay, wrong `vid`, and unknown `vid` issue nothing.
4. Operator reports and `check-0c` output must say **SIMULATED** until a stagenet or local-dev chain is actually scanned.

## Rationale

Rejected alternatives:

1. **Pay on nimo mainnet `:18081`.** Explicitly banned. No mainnet wallets or txs.
2. **Stand up and sync stagenet in this session.** No `:38081` listener; a from-scratch stagenet node is not a gate-0c requirement when simulated intake is allowed.
3. **Stuff ZKAPs into the payment memo.** Encrypted payment ID is 8 bytes. That is `vid`, not a pass (`docs/00-decision.md`).

## Consequences

- Local `leasegrid-zkap check-0c` can PASS 0c.1–0c.5 without a chain. That is not a live stagenet payment.
- A later `--intake rpc --xmr-rpc http://127.0.0.1:38081/json_rpc` (or other non-banned port) can replace inject with `make_integrated_address` + `get_transfers` without changing `vid`, `R`, or the spent-set.
- Faucet remains a lab backdoor for 0b; 0c scoring uses the paid path only.

## References

- `docs/08-lab.md` Gate 0c
- `docs/02-objects.md` §2.1–2.2
- `GATE0C_NETWORK_CONSTRAINT.md`
- `src/leasegrid_zkap/xmr_intake.py`, `xmr_addr.py`, `issuer.py`, `check_0c.py`
