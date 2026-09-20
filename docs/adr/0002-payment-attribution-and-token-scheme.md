# ADR-0002: Payment attribution by subaddress; publicly verifiable tokens for multi-operator grids

- **Date:** 2026-09-20
- **Status:** Proposed (owner decision pending; see `docs/07-payment.md` §14)
- **Deciders:** Payment design (gate 0c / U5)

## Context

`docs/02-objects.md` §2.1 defines `vid` as 8 random bytes carried in a Monero **encrypted payment ID** (integrated address) and names that the preferred mint. ADR-0001 gives storage nodes a copy of the issuer **signing key** so they can verify `challenge-bypass-ristretto` tokens offline.

Both were right for the one-operator lab. Neither survives the product shape the roadmap actually wants:

1. A sender that strips the payment ID (some exchanges and wallets) produces a payment to the issuer's main address that cannot be attributed and cannot be refunded (Monero has no return address). That is a silent money-losing state.
2. A storage node holding the signing key can mint tokens and settle them for XMR, and can re-bind a token a client spent at it to a different `R` and spend it at a competitor. The issuer cannot detect either. A multi-operator friendnet — the wedge — cannot be built on that.

## Decision

1. **Attribution:** the issuer allocates a **fresh subaddress per quote** and maps `vid ↔ subaddr_index` internally. `vid` remains the client-facing handle (and may be client-derived from a recovery seed). The integrated-address form (main address + `vid` as payment ID) is offered only as a fallback target; both land on the same voucher. Subaddress indices are never reused, so late payments are always credited.
2. **Token scheme is a field, not an assumption.** Wallet, issuer epochs, `R`, spent-set, settlement and UI carry `scheme ∈ {ristretto-v0, rsa-bssa-v1}`.
3. **Lab stays on `ristretto-v0`** (gate 0b PASS preserved; gate 0c runs on it).
4. **Before a second paid operator joins any grid**, the grid's issuer opens an `rsa-bssa-v1` epoch: RFC 9474 blind RSA (RSABSSA-SHA384-PSS-Deterministic, 2048-bit; the Privacy Pass type `0x0002` construction of RFC 9578). Nodes hold only the public key. Each token embeds a client-held Ed25519 key (`m = H(t || pk_tok)`), and spends carry `Sign_sk_tok(R)`, so a node that received a token cannot re-bind it. This is gate **0e**.

## Rationale

- Subaddresses cannot be stripped by the sender and accumulate, which gives underpayment recovery for free. Integrated addresses do survive Carrot/FCMP++ (checked 2026-09), so the fallback remains valid; it is simply not the primary path.
- Blind RSA is standardised, has a mature implementation surface (`cryptography` provides RSA-PSS; blinding is a few lines of modular arithmetic on public parameters), and removes the DLEQ proof because the signature is publicly verifiable. Token size (~330 B) is irrelevant at one token per GiB-share-month.
- Rejected: online spend verification against the issuer (couples availability, leaks real-time spend timing per node); threshold ristretto (research); trusting nodes (that is corner A, not a friendnet).

## Consequences

- `docs/02-objects.md` §2.1 and §2.3 need amending once accepted (handle = subaddress index; token forms per scheme). Until then `07-payment.md` is authoritative for the deviation.
- `R` is unchanged. Settlement invariant (spent `t` only, never `R`) is unchanged.
- With `rsa-bssa-v1` the storage host holds **no secret**, which also simplifies the operator package (Phase 2).
- Gate 0e is added to `08-lab.md` when S9 in `07-payment.md` §13 is scheduled.

## References

- `docs/07-payment.md`
- `docs/02-objects.md` §2.1, §2.3
- ADR-0001
- RFC 9474 (RSA Blind Signatures), RFC 9578 (Privacy Pass Issuance Protocols)
