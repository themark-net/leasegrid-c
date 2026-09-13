# 05 — Bonds (option B, roadmap)

Option **B** in the four-corners table is a federated market: private pay, bonded *known* nodes.

Leasegrid (corner C) does not require a bond. This file is the optional **B-lite** bolt-on. It is not required to store a byte.

## What B-lite is allowed to be

A node *may* post a named lock and advertise it on the grid-manager certificate:

```
bond_ref?
bond_amount?
slash_policy_id?
```

Acceptable shapes, later:

- Federated 2-of-3 XMR escrow (client, node, auditor).
- A BTC Taproot / DLC lock, with XMR→BTC atomic swap used only as an **on-ramp** for collateral — never as the slash condition.

Clients who ignore `bond_ref` are still on Leasegrid. Nodes who never post a bond can still be paid in ZKAPs.

## What B-lite is not

- Not the happy path. C (Leasegrid) is.
- Not a public Filecoin-style deal + PoRep/PoSt.
- Not an XMR clone, not an L1, not `unlock_time` escrow.
- Not "swap timed out ⇒ share is missing." A swap timeout slashes a missed handshake.

If you add a public proof and a public bond as the condition for storing a byte, you are no longer building Leasegrid.

## Why it waits

B needs an auditor role (trusted for attesting nodeid failure, not files) and a scriptable lock. That is extra trust and extra surface. The lab succeeds when XMR → vid → ZKAP → lease → silent eject works without it.
