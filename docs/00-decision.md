# 00 — Decision

Leasegrid C is a **paid friendnet**.

Tahoe already gives confidentiality and integrity against a hostile disk. It does not pay anyone to keep shares. Filecoin pays by publishing deals, collateral, and proofs. Those publications are the opposite of the privacy budget C accepts.

## The sentence that is the architecture

Leasegrid C does not punish lying nodes with money. It stops feeding them and moves shares. Privacy is the reason slashing is absent. If you add a public proof and a public bond, you are no longer building C.

## Four corners (do not mix the labels)

| Corner | What you get | Honest name |
|---|---|---|
| A | Private pay, trusted operator set | Private S4 |
| B | Private pay, bonded *known* nodes | Federated market |
| **C** | Private everything, no slash | **Paid friendnet** |
| D | Public deals + proofs | Wrapped Filecoin |

This repo is C. `docs/05-bonds.md` is an *optional* B-lite advertisement on the node certificate. Clients may ignore it.

## Why not the ideas we already rejected

- **Clone Monero for bonds.** RingCT hides whether a named stake still exists. Slashing still needs an oracle. You paid for an L1 and kept the federation.
- **Atomic swap as slash.** A swap guarantees both legs complete or both refund. It does not encode "share #7 is missing." Timeout slashes a missed handshake, not a missing share.
- **XMR↔XMR atomic swap.** Atomic swaps exist because two ledgers cannot share a transaction. Same asset is a payment or a multisig. Monero has no HTLC / CSV punish branch.
- **Monero `unlock_time` as escrow.** That field means "recipient cannot spend until height H." It does not mean "counterparty seizes after T." Custom unlock_time is being removed at consensus with FCMP++; relay already rejects it. Official Monero note: no specified swap or channel scheme uses it. Do not build on it.
- **ZKAPs in a Monero memo.** Encrypted payment ID is 8 bytes. That is a booking id (`vid`), not a pass.

## What C does buy

- Client-side encryption and FEC (Tahoe, unchanged).
- Unlinkable prepaid credit (XMR → issuer → ZKAPs).
- Lease-gated writes. No token, no allocate / no renew.
- Client (or hired repair agent) reconstructs onto live certified nodes.
- Introducer / grid-manager silently drops unreachable nodeids.

That is enough to run a lab grid. It is not a miner market.
