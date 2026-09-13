# Contributing

This repo is a spec. Changes should make C more implementable or more honest, not more like Filecoin.

## Rules that stay at the top of the repo

1. Do not put Tahoe caps, storage indexes, or spent token preimages on a public ledger.
2. Do not add a second consensus network.
3. Do not treat atomic-swap timeout, Monero `unlock_time`, or XMR↔XMR "swaps" as slashing.
4. Do not fork zfec / CHK / capability encoding.
5. Price share-byte-months, not plaintext terabytes.

## How to change the spec

Open an issue first for anything that moves trust (new issuer powers, new slash condition, new on-chain field). Patches that only clarify wire formats or lab steps can go straight to a PR.

## What is not here yet

- Tahoe storage-server plugin
- Issuer HTTP service
- Monero intake scanner
- Grid-manager policy daemon

Those belong in later repos or later directories once the lab criterion in `docs/08-lab.md` is the implementation target, not a slogan.
