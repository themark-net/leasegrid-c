# Leasegrid C

Monero-prepaid Tahoe-LAFS friendnet with bearer storage credits and silent eject.

This repository is an **architecture specification**, not a token, not an L1, and not a Tahoe fork. Encoding stays stock Tahoe-LAFS (CHK, zfec, capability URIs, leases, GBS/HTTPS). Payment is XMR → issuer → Privacy Pass / ristretto ZKAPs. Liveness is client repair plus stopping payment to dead nodes.

> Leasegrid C does not punish lying nodes with money. It stops feeding them and moves shares. Privacy is the reason slashing is absent. If you add a public proof and a public bond, you are no longer building C.

Optional **B-lite** (a federated 2-of-3 escrow or a BTC Taproot/DLC lock advertised on the node certificate) can be bolted on later. It is not required to store a byte.

## Status

Design draft. No issuance code, no Tahoe plugin, no mainnet wallet. Lab success criterion is in [`docs/08-lab.md`](docs/08-lab.md).

## Read in this order

1. [`docs/00-decision.md`](docs/00-decision.md) — what this is and is not
2. [`docs/01-architecture.md`](docs/01-architecture.md) — roles and rails
3. [`docs/02-objects.md`](docs/02-objects.md) — voucher id, ZKAP, request binding `R`, lease, cert
4. [`docs/03-flows.md`](docs/03-flows.md) — quote, pay, put, repair, eject, settle
5. [`docs/04-wire.md`](docs/04-wire.md) — JSON and encoding sketches
6. [`docs/05-bonds.md`](docs/05-bonds.md) — optional B-lite; why not swap-timeout, XMR clone, or `unlock_time`
7. [`docs/06-privacy.md`](docs/06-privacy.md) — privacy budget
8. [`docs/07-threats.md`](docs/07-threats.md) — attack list
9. [`docs/08-lab.md`](docs/08-lab.md) — three-process lab

## Two rails

```
C (always):      client --XMR--> issuer --ZKAP--> node lease
B-lite (optional): node posts a named lock; cert may carry bond_ref
```

Clients who ignore `bond_ref` are still on C. Nodes who never post a bond can still be paid in tokens.

## Non-goals

- PoRep / PoSt / protocol-level slashing
- A second Monero, or any new consensus
- Caps, storage indexes, or spent tokens on any chain
- Charging for reads in v0
- Replacing Tahoe repair with an economic miracle

## Terms (short)

- **Cap** — Tahoe capability URI (`URI:CHK:…`). The URI *is* the key. Not a CephX ACL, not a market cap.
- **Bond** — stake a *node* locks so it has something to lose. C does not require one.
- **ZKAP** — unlinkable store credit. ~64 bytes on disk, ~100 B + `|R|` at redeem. Not an 8-byte Monero memo.
- **vid** — 8-byte voucher id. This is what fits in a Monero encrypted payment ID.

## License

Specification text: Apache-2.0. A future Tahoe plugin would follow Tahoe-LAFS license terms and is out of scope here.
