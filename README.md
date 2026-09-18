# Leasegrid

Monero-prepaid Tahoe-LAFS friendnet with bearer storage credits and silent eject.

This repository is an **architecture specification**, not a token, not an L1, and not a Tahoe fork. Encoding stays stock Tahoe-LAFS (CHK, zfec, capability URIs, leases, GBS/HTTPS). Payment is XMR → issuer → Privacy Pass / ristretto ZKAPs. Liveness is client repair plus stopping payment to dead nodes.

The GitHub slug is still `leasegrid-c`. The letter **C** was a cell in the comparison table (A/B/C/D). The product is **Leasegrid**. It implements corner C: paid friendnet, private everything, no slash.

> Leasegrid does not punish lying nodes with money. It stops feeding them and moves shares. Privacy is the reason slashing is absent. If you add a public proof and a public bond, you are no longer building this.

**Option B** (federated market of bonded *known* nodes) stays on the roadmap as optional **B-lite**: a federated 2-of-3 escrow or a BTC Taproot/DLC lock advertised on the node certificate. It is not required to store a byte. See [`docs/05-bonds.md`](docs/05-bonds.md).

## Status

Architecture spec plus a **gate 0b lab** (ristretto issuer + lease gate) under [`src/leasegrid_zkap/`](src/leasegrid_zkap/) and [`deploy/zkap-lab/`](deploy/zkap-lab/). That lab is **not** PyPI ZKAPAuthorizer (Tahoe 1.20 pin; see [`docs/adr/0001-thin-lab-zkap-authorizer.md`](docs/adr/0001-thin-lab-zkap-authorizer.md)). Gates 0a and 0b have dated PASS rows in [`docs/08-lab.md`](docs/08-lab.md). Gates 0c–0d are not PASS until that log says so. No mainnet wallet. Product UX remains Magic Folder–class sync (Phase 1).

**Product UX goal:** Magic Folder–class folder sync for a **normal person**. Tahoe’s native UI is not the product. Architecture-heavy items (abuse / free reads, issuer compromise, settlement, Tor vs sync performance, operator AUP) are flagged in the roadmap and need design docs before implementation.

## Read in this order

1. [`docs/00-decision.md`](docs/00-decision.md) — what this is and is not
2. [`docs/03-roadmap.md`](docs/03-roadmap.md) — what we build for users and in what order
3. [`docs/01-architecture.md`](docs/01-architecture.md) — roles and rails
4. [`docs/02-objects.md`](docs/02-objects.md) — voucher id, ZKAP, request binding `R`, lease, cert
5. [`docs/05-bonds.md`](docs/05-bonds.md) — optional B-lite; why not swap-timeout, XMR clone, or `unlock_time`
6. [`docs/08-lab.md`](docs/08-lab.md) — paid rails PASS/FAIL criterion
7. [`deploy/zkap-lab/README.md`](deploy/zkap-lab/README.md) — how to run gate 0b on the LAN friendnet

## Two rails

```
Leasegrid (always):  client --XMR--> issuer --ZKAP--> node lease
B-lite (roadmap):    node posts a named lock; cert may carry bond_ref
```

Clients who ignore `bond_ref` are still on Leasegrid. Nodes who never post a bond can still be paid in tokens.

## Non-goals

- PoRep / PoSt / protocol-level slashing
- A second Monero, or any new consensus
- Caps, storage indexes, or spent tokens on any chain
- Charging for reads in v0
- Replacing Tahoe repair with an economic miracle
- Shipping Tahoe WUI as the product UI

## Terms (short)

- **Cap** — Tahoe capability URI (`URI:CHK:…`). The URI *is* the key. Not a CephX ACL, not a market cap.
- **Bond** — stake a *node* locks so it has something to lose. Leasegrid does not require one.
- **ZKAP** — unlinkable store credit. ~64 bytes on disk, ~100 B + `|R|` at redeem. Not an 8-byte Monero memo.
- **vid** — 8-byte voucher id. This is what fits in a Monero encrypted payment ID.

## License

Specification text: Apache-2.0. A future Tahoe plugin would follow Tahoe-LAFS license terms and is out of scope here.
