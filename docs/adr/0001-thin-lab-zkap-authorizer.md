# ADR-0001: Thin lab ZKAP authorizer (not PyPI ZKAPAuthorizer)

- **Date:** 2026-09-17
- **Status:** Accepted
- **Deciders:** Gate 0b implementation (lab/gate-0b-zkap)

## Context

Gate 0b needs a ristretto / ZKAPAuthorizer-compatible issuer, a storage lease gate, faucet mint, request binding `R`, and settlement that never forwards `R` to the issuer.

PrivateStorageio ZKAPAuthorizer on PyPI (`zero-knowledge-access-pass-authorizer` 2022.8.21) requires `tahoe-lafs (>=1.17.1,<1.18.1)`. The friendnet runs **Tahoe-LAFS 1.20.0**. Silently installing that plugin would either fail or pin an incompatible Tahoe.

Tahoe 1.20 storage plugins (`IFoolscapStoragePlugin`) wrap Foolscap only. The live client on nimo has `tub.port = disabled` and talks **GBS HTTP**. HTTP allocate has no ZKAP header.

## Decision

1. Do **not** vendor or claim PyPI ZKAPAuthorizer works on Tahoe 1.20.
2. Ship a thin lab authorizer (`leasegrid-zkap-lab`) that:
   - Uses `python-challenge-bypass-ristretto` (same group/MAC family as ZKAPAuthorizer).
   - Encodes `R` per `docs/02-objects.md` with domain `leasegrid-v0`.
   - Faucet-mints via blinded issue + DLEQ (no chain, no `vid` — that is gate 0c).
   - Wraps Tahoe `StorageServer.allocate_buckets` / `add_lease` / `renew_lease` in place so GBS HTTP and Foolscap both refuse unpaid leases.
   - Exposes a small HTTP spend API on the storage node because GBS cannot carry `(t, R, MAC)`.
3. Storage nodes hold a copy of the issuer **signing** key (ZKAPAuthorizer model: rederive `W` from `t`). Issuer settlement accepts spent `t` only and rejects any body that includes `R`.
4. Corner C constraints in `docs/00-decision.md` stay: no slash, no on-chain caps, no L1.

## Rationale

Rejected alternatives:

1. **Install PyPI ZKAPAuthorizer on 1.20.** Version pin is explicit. Forcing it would be a lie in the lab log.
2. **Downgrade the friendnet to Tahoe 1.17.** Gate 0a already PASSed on 1.20.0; do not unwind that.
3. **New Foolscap-only plugin and `force_foolscap` on nimo.** Would work, but the live client is HTTP-only. Wrapping the anonymous `StorageServer` singleton gates the protocol the grid actually uses.
4. **HMAC stand-in instead of ristretto.** Fails 0b.1 (“ristretto / ZKAPAuthorizer-compatible”). The 2022.6.30 manylinux wheel imports on CPython 3.12 and 3.14.

## Consequences

- Paid `tahoe put` (CHK) cannot attach `R` until a GBS header or client plugin exists; 0b.4 is proven by spend + wrapped `allocate_buckets` (lab HTTP or in-process). Anonymous `tahoe put` fails once the wrap is installed.
- Sharing the issuer signing key with storage is a lab/friendnet trust choice. Split issuer process from storage hosts; do not put the key in git.
- Gate 0c can reuse `/v0/issue` and add `vid` + XMR without changing `R` or the spent-set rules.

## References

- `docs/02-objects.md` §2.3–2.7
- `docs/08-lab.md` Gate 0b
- `docs/00-decision.md` corner C
- `src/leasegrid_zkap/`
- `deploy/zkap-lab/README.md`
