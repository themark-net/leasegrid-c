# Contributing

This repo is a spec. Changes should make C more implementable or more honest, not more like Filecoin.

Product sequencing (Magic Folder UX, operator package, architecture-heavy flags) lives in [`docs/03-roadmap.md`](docs/03-roadmap.md).

## Rules that stay at the top of the repo

1. Do not put Tahoe caps, storage indexes, or spent token preimages on a public ledger.
2. Do not add a second consensus network.
3. Do not treat atomic-swap timeout, Monero `unlock_time`, or XMR↔XMR "swaps" as slashing.
4. Do not fork zfec / CHK / capability encoding.
5. Price share-byte-months, not plaintext terabytes.
6. Do not ship Tahoe WUI as the product UI; Magic Folder–class sync is the buyer surface.

## How to change the spec

Open an issue first for anything that moves trust (new issuer powers, new slash condition, new on-chain field) or any **architecture-heavy** roadmap flag (abuse/free reads, issuer compromise, settlement, operator AUP). Patches that only clarify wire formats or lab steps can go straight to a PR.

## What is not here yet

- Monero intake scanner (gate 0c)
- Grid-manager policy daemon (gate 0d)
- Magic Folder / normal-person client (product goal — see roadmap Phase 1)

Lab issuer + Tahoe 1.20 lease gate (gate 0b, no XMR) lives in `src/leasegrid_zkap/` with operator notes in `deploy/zkap-lab/`. Do not treat a green local `check-0b` as Phase 0 PASS until `docs/08-lab.md` records a dated live-grid row.

Product order of work is in `docs/03-roadmap.md`.
