# 02 — Objects

Nothing in this file is a coin. These are the records C moves around.

## 2.1 Voucher id (`vid`)

8 random bytes. This is what fits in a Monero **encrypted payment ID** (integrated address).

It is a correlation handle between one XMR payment and one issuance session. It is not a ZKAP. Do not put a fURL, cap, or token here.

Preferred mint: issuer allocates `vid` and returns an integrated address that already embeds it.

## 2.2 Voucher (issuer-private)

```
vid
xmr_txid          # issuer-internal; not published
amount_piconero
confirmations
tokens_owed
tokens_issued
expires
spent             # voucher redeemed for a token batch
quote_id
```

Never published. Client knows `vid` because they paid that integrated address.

## 2.3 ZKAP (bearer credit)

Privacy Pass / `challenge-bypass-ristretto`, same family as Least Authority ZKAPAuthorizer.

| Form | Typical size | Where |
|---|---|---|
| Compact on disk `t \|\| W` | ~64 B | client token wallet |
| Wire redeem `(t, R, MAC_K(R))` | ~100 B + `\|R\|` | Tahoe allocate / add_lease / renew |
| Batch DLEQ on issue | hundreds of B to a few KB | issuer → client, once per voucher |

- `t` — 32-byte preimage
- `W` — 32-byte unblinded ristretto point
- `K = H2(t, W)` — derived, not sent
- Tokens do not split. Overpay and hold change.

**v0 denomination:** 1 token = 1 GiB-share × 30 days on **one** node.

PrivateStorage historically used ~1 MiB-month. That denomination explodes redeem count. Do not put tokens in `tx_extra`.

## 2.4 Request binding `R`

`R` authorizes *this* operation on *this* node. It is not the cap.

```
R = domain || nodeid || storage_index || lease_seconds || share_bytes
    || token_epoch || issuer_pubkey_id
```

- `domain` — constant `leasegrid-c-v0`
- `storage_index` — Tahoe shareset identifier. Nodes already see this on put.
- Do **not** bind to the read or write cap.
- `nodeid` stops replay onto another server.
- `token_epoch` rotates issuer keys.

Settlement with the issuer sends spent `t` values only. **Do not forward `R` to the issuer.**

## 2.5 Node advertisement / grid-manager cert

```
nodeid
storage_furl          # prefer onion
advertised_free_bytes
issuer_pubkeys_accepted[]
cert_expiry
software_version
bond_ref?             # optional B-lite; see docs/05-bonds.md
bond_amount?
slash_policy_id?
```

No XMR intake address on this document. Payout addresses are negotiated out of band at first settlement.

## 2.6 Lease

Tahoe lease, unchanged semantics: renew or the node may GC. Token spend is how a client is allowed to create or extend that lease. After expiry the node may delete. That is the only automatic punishment in C.

## 2.7 Spent-set

Per issuer epoch, held by the node. Replay of the same `t` against a compatible existing lease is idempotent success. Replay against a different `R` is failure.
