# 03 — Product roadmap

Owner direction (2026-09-17): **Magic Folder–class sync is the product UX goal.** Tahoe’s native UI is unacceptable. Leasegrid must work for a normal person — folder sync, visible credit, recovery that does not require reading Tahoe docs — while the rails stay corner **C** (paid friendnet, XMR → ZKAP, silent eject, no slash).

This file is the product roadmap. Architecture constraints remain in [`00-decision.md`](00-decision.md) and [`01-architecture.md`](01-architecture.md). Lab success criterion for the paid rails is [`08-lab.md`](08-lab.md) (gates 0a–0d).

## North star

**Paid friendnet kit:** people who trust a small set of operators get Dropbox-shaped sync, top up with Monero, and operators get a node package that accepts ZKAPs and ejects dead peers — without Filecoin-style public proofs.

Closest substitute today is PrivateStorage + ProxyStore (same Tahoe/ZKAP family, already sells for XMR, single operator). Leasegrid’s wedge is **multi-operator friendnet** plus native XMR mint. The wedge only matters if the client is usable by a non-Tahoe person.

## Phases

### Phase 0 — Paid rails lab (prove C)

**Goal:** The documented loop works on real machines. Not a market release.

- [ ] XMR faucet (or tiny spend) → `vid` → ZKAP batch from issuer — design: [`07-payment.md`](07-payment.md)
- [x] Spend ZKAP on allocate / add_lease / renew against a storage node (gate 0b faucet; no XMR)
- [ ] Kill or eject a node; client (or repair agent) moves shares; stop paying the dead node
- [x] Document as [`08-lab.md`](08-lab.md); no slogan-only criterion

**Out of scope here:** Magic Folder polish, mobile, marketing, B-lite bonds.

**Exit:** Lab PASS on LAN (or Tor lab). Capital stays lab-only until this passes *and* there is a non-you demand signal.

### Phase 1 — Normal-person buyer surface (first revenue shape)

**Goal:** Someone who is not a Tahoe operator can store and sync folders and top up credit.

| Workstream | Intent | Notes |
|---|---|---|
| **Magic Folder sync client (native)** | Primary UX. Folder in ↔ encrypted shares out. Multi-device invite codes. **Native desktop + installer required** (see [`09-ui-track.md`](09-ui-track.md)). Web is optional alt only. | **This is the product.** Reuse / wrap Gridsync + Magic Folder; Linux AppImage/.deb first. Do not ship WUI-as-product. Start UI in parallel with Phase 0 (do not wait for 0c/0d). |
| **Credit / balance UI** | Show remaining GiB-share-months; “Top up with XMR” as smooth as ProxyStore redeem. | Opaque ZKAP wallets do not convert. |
| **Recovery Key / capability backup** | Scary defaults; export path; loss = total loss made obvious. | Cap DIY is not acceptable for a normal person. |
| **Renewal automation** | Daemon renews leases before expiry so data is not silently stranded. | PrivateStorage already trains ~31-day renew habit; we must not make it worse. |
| **Honest threat-model copy** | Issuer mint trust, no storage proofs, Tor for full claim — on the first screen, not a footnote. | Privacy buyers churn when this is discovered late. |

**Exit:** A non-expert can sync a folder, see balance, top up, and recover from a documented key backup on a friendnet that runs Phase 0 rails.

### Phase 2 — Operator supply package

**Goal:** A friendnet peer can run a node without reading the Tahoe man pages.

- [ ] Install path for storage node (scripted or packaged)
- [ ] Dashboard: accepted ZKAPs, disk used, lease count, eject / probe logs
- [ ] Payout status (even if settlement stays out-of-band at first — make the *status* visible)
- [ ] Short-TTL cert / silent-eject policy that matches [`01-architecture.md`](01-architecture.md)

**Exit:** A second operator can join the buyer’s friendnet and get paid in the product sense (tokens accepted; eject visible).

### Phase 3 — GTM and demand falsification

**Goal:** Prove the multi-op wedge before scaling polish.

- [ ] Landing / docs aimed at **paid friendnet kit**, not “decentralized Dropbox vs Storj”
- [ ] 5–10 cold conversations with Tahoe friendnet operators and/or PrivateStorage+XMR buyers: would they pay multi-op nodes with unlinkable credits?
- [ ] Invite-only early grids; no broad DePIN marketing

**Exit:** Either clear non-you demand, or honest park / narrow to personal tooling.

### Phase 4 — Category table-stakes (after revenue shape works)

- Mobile read (then write)
- Sharing UX beyond raw caps
- Versioning
- Fiat on-ramp (expands market; optional for the maximalist niche)
- Optional **B-lite** bonds per [`05-bonds.md`](05-bonds.md) — never required to store a byte

## Architecture-heavy / careful-design flags

These are roadmap items that **must not** be hacked in as afterthoughts. They need design notes (and likely their own docs) before implementation. Do not treat a checkbox here as “ship a quick filter.”

| Flag | Why it is heavy | Earliest phase it blocks |
|---|---|---|
| **Abuse prevention & free reads (v0)** | Free protocol reads + multi-op + no KYC invites adversarial load and egress burn. Needs rate limits, authz at read path or metering, AUP, and operator kill switches without becoming KYC-Filecoin. | Blocks serious Phase 2 supply and any public invite grid |
| **Issuer trust, key rotation, compromise** | Mint sees XMR amounts/timing/`vid`. Epoch rotation, spent-set, and “issuer died” recovery need a written model. **Designed:** [`07-payment.md`](07-payment.md) §8. | Blocks Phase 0 exit for anything beyond a toy faucet |
| **Multi-issuer / settlement** | Friendnet economics fail if every grid is secretly one mint. How nodes get XMR from ZKAP spends (out-of-band → explicit) needs a design. **Designed:** [`07-payment.md`](07-payment.md) §9, [ADR-0002](adr/0002-payment-attribution-and-token-scheme.md). | Blocks Phase 2 “get paid” honesty |
| **Tor-mandatory UX vs sync performance** | Full privacy claim wants Tor; Magic Folder users expect LAN/WAN sync that feels normal. Policy for lab vs production transports. | Blocks Phase 1 “normal person” on the privacy claim |
| **Operator legal / AUP / liability** | Multi-op paid storage attracts CSAM and takedown risk. Templates and defaults without pretending to be a lawyer product. | Blocks Phase 3 public invites |
| **Pricing & denomination UX** | Share-byte-months and expansion confuse normals. UI must translate without lying about cost. **Designed:** [`07-payment.md`](07-payment.md) §4, §11. | Blocks Phase 1 conversion |
| **Silent-eject vs paid SLA expectations** | Paying customers expect availability stories. Document social/friendnet trust; do not fake PoRep. Optional B-lite is separate and later. | Blocks pitching as general cloud |

When one of these is opened, add a design doc (e.g. `docs/06-abuse.md`, `docs/07-issuer.md`) and link it here. Do not implement from a one-line ticket.

## Explicit non-goals (still)

Unchanged from the architecture decision:

- PoRep / PoSt / protocol-level slashing
- A second Monero or any new L1
- Caps, storage indexes, or spent tokens on a public chain
- Replacing Tahoe repair with an “economic miracle”
- Shipping Tahoe WUI as the product UI

## Reading order update

1. [`00-decision.md`](00-decision.md) — what this is and is not  
2. **This file** — what we build for users and in what order  
3. [`01-architecture.md`](01-architecture.md) — roles and rails  
4. [`02-objects.md`](02-objects.md) — wire objects  
5. [`05-bonds.md`](05-bonds.md) — optional B-lite only  
6. [`08-lab.md`](08-lab.md) — paid rails PASS/FAIL (when written)

## Status snapshot

| Layer | Status |
|---|---|
| Architecture spec (00–02, 05) | Draft published |
| Paid rails (issuer, plugin, eject) | 0b lab PASS; XMR quote/redeem against FakeChain (S0–S2, S5–S6, S8); S3 WalletRpcChain (CI); S9 `rsa-bssa-v1` in CI; live 0c / 0d / 0e open — [`08-lab.md`](08-lab.md) |
| Magic Folder / normal-person client | **UI track locked 2026-09-19** — native + installer; see [`09-ui-track.md`](09-ui-track.md); U0–U5 |
| Operator package | Not started (local stock-Tahoe bootstrap only) |
| Abuse / settlement / issuer-compromise designs | Payment, settlement, issuer-compromise: **designed** ([`07-payment.md`](07-payment.md), proposed). Abuse / free reads: flagged; not designed |

## Research / distribution layer (MictlanX)

**Added 2026-09-18.** Steal the *distribution* parts of MictlanX (MIT, `muyal-research-group/mictlanx-client`), not the whole system.

- Keep Tahoe’s encryption, capability model, CHK/zfec, and repair logic.
- Evaluate MictlanX’s router-based placement, chunked concurrent transfers, and dynamic replication as a faster or smarter placement/transport layer on top of Tahoe shares.
- Silent-eject and ZKAP payment stay ours; MictlanX assumes mostly-trusted peers and has no mandatory crypto or capability model.
- Prototype only after Phase 0 rails lab passes. No dependency on their research poster or 16-node numbers.
- Name candidate: **Mictlan** (Aztec underworld — data vanishes into shares, reassembles only for the right person). Domains still messy; treat as lore/name exploration, not a blocker.
