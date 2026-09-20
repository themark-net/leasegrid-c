# 07 — Payment design: XMR → `vid` → ZKAP → settlement

**Status:** Proposed design, 2026-09-20. **Implemented against `FakeChain`:** S0–S2, S5 (three-OS installer CI green 2026-09-20: quote → `/v0/fake/pay` → Credit collects → paid upload → recovery-key re-collect), S6 U5 UI (Top up quotes XMR, Pending list, recovery-key credit-seed copy). **Not started:** S3 `WalletRpcChain` / stagenet, S7 live gate 0c, S8 epochs, S9 `rsa-bssa-v1`. Covers gate 0c ([`08-lab.md`](08-lab.md)), U5 ([`09-ui-track.md`](09-ui-track.md)), and three roadmap flags: *issuer trust / key rotation / compromise*, *multi-issuer / settlement*, *pricing & denomination UX* ([`03-roadmap.md`](03-roadmap.md)). Companion ADR: [ADR-0002](adr/0002-payment-attribution-and-token-scheme.md). Owner decisions in §14 are still open.

Constraints inherited, not re-argued: corner C ([`00-decision.md`](00-decision.md)), roles and rails ([`01-architecture.md`](01-architecture.md)), wire objects ([`02-objects.md`](02-objects.md)). Where this doc deviates from `02-objects.md` it says so and the ADR carries the decision.

**Transport is out of scope here.** Everything below is plain HTTP+JSON between client and issuer and JSON-RPC between issuer and its own wallet. It works identically over Tor onion, I2P, or a LAN. The Tor-vs-I2P decision is a separate owner call (see §14).

---

## 0. How to attack this

The payment rail looks like one problem ("take Monero, hand out tokens"). It is four, and they fail differently. Design and test them separately:

| Problem | Question | State lives in | Test double |
|---|---|---|---|
| **Attribution** | Which payment belongs to which buyer session? | Chain + issuer DB | `FakeChain` |
| **Issuance** | Turn a confirmed payment into exactly one batch of unlinkable tokens, once, even if either side crashes | Issuer DB + client wallet WAL | in-process issuer |
| **Custody / recovery** | Bearer credit on a laptop that can die | Client wallet + recovery key | fixture wallets |
| **Settlement** | How operators get paid for tokens they accepted, without being able to cheat | Node spent-set + issuer ledger | fake nodes |

Rules that make the rest of the doc fall out:

1. **The chain is a payment detector and nothing more.** The only question the issuer ever asks Monero is "how much has address *A* received, with how many confirmations?" No memos, no on-chain state, no scripts. This is what keeps corner C honest and what makes the fake chain trivial.
2. **Money-losing states are impossible by construction.** Every piconero that lands on an issuer address maps to exactly one voucher forever; every voucher issues at most once; every issued batch is retrievable by the same client until voucher expiry. Underpay, overpay, late pay, crash mid-redeem: all reach a defined state, none lose funds silently.
3. **Build the whole lifecycle against a fake chain first.** The real `monero-wallet-rpc` adapter is the only piece that cannot run in CI and it is small. Everything else — quote, confirm, redeem, resume, recover, settle — runs in `pytest` and in the existing three-OS exit test.
4. **Do not invent cryptography.** Lab keeps `challenge-bypass-ristretto` (gate 0b PASS). Multi-operator switches to a publicly verifiable token (RFC 9578 type 2 / RFC 9474 blind RSA) because the current scheme lets a storage node mint. Both are standards; neither is ours.
5. **Issuer state is boring.** One SQLite file, one writer, append-only ledger tables, view-only wallet. If the issuer box dies, restore DB + view key and nothing is lost.

---

## 1. Scope

**In:** quote, payment attribution, confirmation policy, redemption protocol, client wallet custody, recovery, issuer key epochs and compromise handling, settlement and operator payout, U5 UI states, test plan, build order.

**Out (still non-goals):** fiat on-ramp (Phase 4), bonds (`05-bonds.md`), charging reads, anything on-chain beyond a plain transfer, a second issuer *protocol* (multiple issuers of the same protocol are in).

---

## 2. Objects

Extends `02-objects.md`. Nothing here is a coin.

### 2.1 Quote → Voucher (issuer-private, one row)

```
vid                 8 random bytes; client-facing handle. Hex in JSON.
subaddr_account     issuer wallet account (0)
subaddr_index       fresh per quote; never reused
address             the subaddress string handed to the client
scheme              "ristretto-v0" | "rsa-bssa-v1"
epoch               issuer key epoch the batch will be signed under
tokens_quoted       what the buyer asked for
price_piconero      price per token at quote time
amount_due          tokens_quoted × price_piconero
quote_expires       now + QUOTE_TTL (default 30 min)
grace_until         quote_expires + GRACE (default 24 h) — quoted price honoured until here
amount_seen         piconero received at 0 conf (for UI only)
amount_confirmed    piconero received with ≥ confirmations_required
confirmations_required
tokens_owed         floor(amount_confirmed / effective_price)
tokens_issued       0 or tokens_owed (all-or-nothing batch)
batch_hash          sha256 over the blinded tokens the client sent
signed_batch        cached issuer response (blinded signatures + DLEQ / RSA blind sigs)
state               see 2.2
created / updated
```

**Deviation from `02-objects.md §2.1`:** the correlation handle on-chain is a **fresh subaddress per quote**, not an 8-byte encrypted payment ID in an integrated address. `vid` stays as the client-facing handle and maps to `subaddr_index` inside the issuer. Reasons in §3. The integrated-address form is still offered as an alternative payment target for wallets that cannot pay subaddresses (rare), pointing at the main address with `vid` as the payment ID; both routes land on the same voucher row.

### 2.2 Voucher states

```
quoted ──(any tx seen, 0 conf)──► seen ──(confs < required)──► confirming
  │                                                                  │
  │ quote_expires && amount_seen == 0                                │ confs ≥ required
  ▼                                                                  ▼
expired_unpaid  (subaddress stays mapped forever; a late payment    payable ──(POST /v0/redeem)──► issued
                 moves it straight to seen/confirming)                 │
                                                                       │ tokens_owed == 0 (paid < 1 token)
                                                                       ▼
                                                                   underpaid  (buyer can pay more to the same address; sums accumulate)
```

Terminal: `issued`. Everything else can still move. `expired_unpaid` is cosmetic (hides the row from the UI); nothing about it prevents a later payment being credited.

### 2.3 Effective price

```
effective_price = price_piconero                 if first confirmed payment ≤ grace_until
                = current_price_at_confirmation  otherwise
tokens_owed     = floor(amount_confirmed / effective_price)
```

Tokens do not split (`02-objects.md`). Dust above a whole token is kept by the issuer and **the UI says so before payment** ("send exactly this amount; overpayment under one credit is not returned — Monero has no refund address"). Underpayment is not lost: the voucher sits in `underpaid` and further payment to the same subaddress tops it up.

### 2.4 Confirmation policy

| Amount confirmed | Confirmations required | Why |
|---|---|---|
| < `LARGE_AMOUNT` (default 0.5 XMR) | 2 | Reorgs deeper than 2 are rare; losing 0.5 XMR to one is an acceptable operator risk |
| ≥ `LARGE_AMOUNT` | 10 | Same depth Monero wallets use for spendability |

0 confirmations is shown to the buyer as *seen* (reassurance) and never issues. Both numbers are issuer config; the quote response carries the value so the UI can show "n of k".

### 2.5 Issuer key epoch

```
epoch_id            uint16, monotonic
scheme              "ristretto-v0" | "rsa-bssa-v1"
public_key          scheme-specific (ristretto: PublicKey; rsa: SPKI)
valid_from / issue_until / accept_until
```

Published at `GET /v0/keys`. Tokens carry `epoch_id` (already in `R` as `token_epoch`). Nodes accept every epoch whose `accept_until` has not passed. Issuer signs only under the epoch whose `issue_until` has not passed. Defaults: issue for 90 days, accept for 90 + 400 days (one denomination period plus margin, so a token bought on the last issuing day is still spendable for its natural life).

---

## 3. Attribution: subaddress per quote

Why not the integrated address in `02-objects.md`:

- A wallet or exchange that strips the payment ID produces a payment to the issuer's main address with **no way to attribute it and no refund path**. That is the one money-losing state this design refuses to have. Subaddresses cannot be stripped; the funds land on the index or they do not leave the buyer.
- Subaddresses are what every current Monero wallet does by default. Integrated addresses survive Carrot/FCMP++ (one encrypted 8-byte pid per tx, checked 2026-09), but they are the legacy path and some senders refuse them.
- A subaddress accumulates. Underpayment recovery (§2.3) and "pay the rest later" are free.
- View-only wallet attribution by `subaddr_index` is a plain `get_transfers` filter; no pid decryption edge cases.

Cost: the issuer creates one subaddress per quote (`create_address`), so unpaid quotes consume indices and DB rows. Index space is 2^32 per account; rate-limit `POST /v0/quote` (§10) and it is a non-issue. Indices are **never reused** — a late payment to a five-year-old quote is still credited.

`vid` keeps its role as the *client-facing* opaque handle so nothing about wallet internals leaks into the API or the UI.

---

## 4. Quote and pricing

```
POST /v0/quote
  {"tokens": 20, "scheme": "ristretto-v0"}          # scheme optional; default = current epoch's
→ 200
  {"vid": "9f3a…", "address": "8Bxx…", "amount_piconero": 120000000000,
   "price_piconero": 6000000000, "tokens": 20,
   "pay_uri": "monero:8Bxx…?tx_amount=0.12&tx_description=leasegrid%209f3a",
   "quote_expires": "2026-09-20T06:30:00Z", "grace_until": "2026-09-21T06:30:00Z",
   "confirmations_required": 2, "epoch": 3, "scheme": "ristretto-v0",
   "denomination": "1 token = 1 GiB-share × 30 days on one node"}
```

**Price source.** v0: operator-set `price_piconero_per_token` in issuer config, changed by hand; no oracle in the protocol. A later issuer may peg to fiat via its own rate feed; the quote API does not change because the buyer only ever sees `amount_piconero` and a locked window. The client shows a fiat *estimate* only if the user has opted in to fetching a rate, labelled as an estimate.

**Pricing & denomination UX flag.** The Credit panel (U2) already translates GiB-share-months to "about N GiB of synced files for a month at your grid's 3-of-10". The Top-up dialog reuses that copy above the amount and never says "1 GiB upload = 1 credit".

Tiers in the UI are just presets for `tokens` (e.g. 10 / 50 / 200). The API takes any positive integer ≤ `MAX_TOKENS_PER_QUOTE` (default 1000).

---

## 5. Redemption protocol

### 5.1 Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/v0/keys` | Epochs, schemes, public keys, price hint |
| `POST` | `/v0/quote` | §4 |
| `GET` | `/v0/voucher/{vid}` | `{state, amount_seen, amount_confirmed, confirmations, confirmations_required, tokens_owed, tokens_issued, grace_until}` |
| `POST` | `/v0/redeem` | `{vid, blinded-tokens[]}` → signed batch (+ DLEQ for ristretto) |
| `POST` | `/v0/settlement` | unchanged from 0b (spent `t` only; refuses `R`) plus `nodeid`, `epoch` |
| `GET` | `/v0/ledger` | public solvency-lite totals (§8) |
| `POST` | `/v0/faucet/issue` | lab only; absent unless `--faucet` |

Status codes on `/v0/redeem`: `402` voucher not payable yet (body echoes voucher state so the client just keeps polling), `409` batch hash differs from the one already cached for this `vid`, `410` epoch closed for issuing (client re-quotes; funds are re-attributed to the new quote by the issuer, see §8), `200` batch.

### 5.2 Idempotent, resumable redeem

The failure that actually happens: client sends blinded tokens, issuer signs and stores, response is lost (crash, Tor circuit dies, laptop lid). Without care the buyer has paid and holds nothing.

- Client **writes a pending-redemption record to its wallet file before the first POST**: `{vid, epoch, tokens[] (unblinded secrets), blinded[], batch_hash}`.
- Issuer signs, stores `signed_batch` keyed by `(vid, batch_hash)`, then replies. Same request again → same cached reply. Different `batch_hash` for an issued voucher → `409`.
- Client unblinds, verifies (DLEQ or RSA signature), moves tokens into the spendable set, deletes the pending record. All under the existing `wallet_lock`.
- Batch size is exactly `tokens_owed`. Issuing is all-or-nothing per voucher; there is no partial redeem to reason about.

### 5.3 Deterministic tokens (enables recovery, §6)

Client holds a 32-byte `credit_seed` (generated once, stored in the wallet file and in the recovery key). Per voucher:

```
vid_n        = HKDF(credit_seed, info="leasegrid/vid/v0" || n)[:8]        # n = quote counter
token_{n,i}  = HKDF(credit_seed, info="leasegrid/token/v0" || vid_n || i)  # 96 B for ristretto: 64 B preimage || 32 B scalar (wide-reduced mod ℓ, canonical)
```

The client sends `vid_n` **in** `POST /v0/quote` (issuer accepts client-supplied `vid` if unused; collisions are 2^-64 and return `409`). With deterministic `vid` and tokens, a restored client can reproduce every blinded batch it ever sent and get the cached signed batch back. Nothing new leaks to the issuer: it only ever sees blinded points and the `vid` it would have seen anyway.

Implementation note: `challenge_bypass_ristretto.RandomToken.decode_base64` accepts the 96-byte encoding, so deterministic tokens are constructible without touching the library. If the canonical-scalar requirement bites, the write-ahead record in §5.2 is the fallback and recovery degrades to "vouchers not yet redeemed are recoverable; issued tokens are only as safe as the last wallet snapshot".

---

## 6. Custody and recovery

Tokens are bearer credit. Lost wallet file = lost credit unless we do something. What the U4 recovery key holds after U5:

```
credit_seed            32 B   — regenerates vids and tokens (§5.3)
issuer_url, epoch info        — where to ask
quote_counter_hint            — last n at export time (scan continues past it)
wallet_snapshot?              — optional: current spendable tokens at export time
```

**Recovery procedure:** for `n = 0, 1, 2, …` derive `vid_n`, `GET /v0/voucher/{vid_n}`; stop after `GAP` (20) consecutive unknown vids. For each `issued` voucher, re-derive the batch, `POST /v0/redeem`, receive the cached signatures, unblind. For each `payable`, redeem normally. Result: every token ever issued to this seed is back in the wallet.

**Spent tokens after recovery.** The client cannot ask the issuer "which of these `t` are spent" without linking tokens to a `vid` at the issuer, which is exactly the linkage ZKAPs exist to prevent. So recovered tokens are marked *unverified*; the first spend attempt of a spent token fails at the node (`t` in spent-set with a different `R`) and the client drops it. Balance after recovery is shown as "up to N credits; confirming as you sync". Honest, and it converges within one renewal cycle because renewals touch every lease.

**Retention.** Issuer keeps `signed_batch` until `accept_until` of its epoch (~16 months by default), then purges. Recovery beyond that window is impossible and the recovery-key copy says so.

Wallet snapshot in the recovery key is a convenience (faster, no issuer round-trip) not a requirement; the seed is what matters.

---

## 7. Privacy analysis

What each party learns, payment layer only:

| Party | Learns | Does not learn |
|---|---|---|
| Issuer | `vid`, XMR amount, timing, token count, client IP unless anonymised transport, blinded points | which node any token is spent at, `R`, storage indexes, caps, unblinded tokens |
| Storage node | `(t, sig/MAC, R)` at spend, epoch, client IP unless anonymised | which voucher/payment the token came from, how many tokens the buyer has |
| Issuer + node colluding | timing correlation ("batch of 20 issued at 14:02; 20 spends at node X from 14:03") | still not a cryptographic link |
| Chain observer | nothing attributable: subaddresses are unlinkable to each other and to the main address |

Mitigations, in order of cheapness:

- **Epoch size.** Anonymity set for a token is *all tokens issued under that epoch*. Quarterly epochs on a small friendnet may still be small sets; that is a friendnet property, documented in the threat copy, not solvable in the protocol.
- **Spend from a pool, not from the batch you just bought.** Client spends oldest tokens first (FIFO) and the UI does not encourage "top up then immediately sync 20 GiB". Cheap, weak, worth doing.
- **Anonymised transport client→issuer** is what breaks the IP link; this is the Tor/I2P decision (§14). The protocol is indifferent.
- **Do not put nodeid in the redeem request.** Redeem is per `vid`; nothing about where tokens will be spent is sent.

Settlement leaks `nodeid` + spent `t` + time to the issuer. That is inherent (the issuer pays that node) and is already the 0b invariant: `R` never travels.

---

## 8. Issuer trust, rotation, compromise, death

The issuer is trusted for **credit issuance only** (`01-architecture.md`). Make that trust inspectable and bounded.

**Rotation (planned).** New epoch every 90 days. `/v0/keys` publishes it ahead of `valid_from`. Nodes pull `/v0/keys` daily and accept any epoch in its `accept_until` window. Clients quote against the current epoch; tokens in an old epoch remain spendable until `accept_until`, which covers their natural 30-day life many times over. No re-minting ceremony needed in the normal case.

**Compromise (unplanned).** Attacker with the signing key can mint unlimited tokens under that epoch. Response: issuer publishes `accept_until = now` for the epoch and opens a new one; nodes stop accepting on their next key pull (≤ 24 h; a node may also be told out of band). Honest buyers holding tokens of the burnt epoch **exchange** them: `POST /v0/exchange {epoch_old, tokens[] (unblinded, spent-style), blinded_new[]}`; issuer checks each `t` against its settlement ledger (not spent) and its issuance count, signs the new batch. Exchange links "someone held N tokens of epoch k" to a new batch — acceptable in an incident, and the copy says so.

**Solvency-lite ledger.** `GET /v0/ledger` publishes per epoch: `xmr_received_piconero`, `tokens_quoted`, `tokens_issued`, `tokens_settled`, `tokens_exchanged`. Operators watch `tokens_settled ≤ tokens_issued` and `tokens_issued × price ≈ xmr_received`. This is what makes a compromise or a dishonest mint *visible* to the people who eat the loss (operators), without publishing any per-payment data. Nodes may also enforce a per-epoch acceptance cap read from the ledger.

**Issuer death.** Tokens are verified at the node without the issuer (both schemes), so existing credit keeps working until `accept_until`. No new credit can be bought; renewals eventually fail; sync UI shows the U2 "cannot renew" state with "your grid's issuer is unreachable" copy. A friendnet recovers by standing up a new issuer and adding its key to `issuer_pubkeys_accepted[]` on the node certs. Clients hold tokens from several issuers in one wallet keyed by `(issuer_pubkey_id, epoch)`. **Backups that make death recoverable:** issuer SQLite + view key + (offline) spend key + signing keys, all off-git, documented in the operator runbook.

---

## 9. Settlement: paying operators without letting them cheat

**Flow (v0, out-of-band payout).** Each node batches its spent-set to `POST /v0/settlement {nodeid, epoch, spent-preimages[]}` daily. Issuer dedups `t` globally (first node to settle a `t` owns it; a second claim is logged as a conflict against both nodeids). Ledger row per `(nodeid, epoch)`: `tokens_settled`. Payout = `tokens_settled × price_at_settlement × (1 − issuer_fee)` in XMR to an operator address exchanged out of band, monthly, from a separate spend wallet. Phase 2 dashboard shows `tokens_settled`, `paid_through`, `pending`.

**The problem the lab scheme has.** ADR-0001 gives storage nodes the issuer **signing key** so they can verify tokens offline. With that key a node can (a) mint tokens and settle them for XMR, and (b) recompute `K` for a token a client spent at it and re-spend that token at a competitor with a forged `MAC_K(R')`. Both are invisible to the issuer. Fine for one operator (PrivateStorage's shape). Fatal for a multi-operator friendnet, which is the entire wedge.

**Fix: publicly verifiable tokens for multi-op.** Switch `scheme` to `rsa-bssa-v1`: RFC 9474 blind RSA (RSABSSA-SHA384-PSS-Deterministic, 2048-bit), the same construction as Privacy Pass type `0x0002` (RFC 9578). Nodes hold only the **public** key; they cannot mint. To stop a node re-spending a token it received, the token carries a client key:

```
client picks  (sk_tok, pk_tok) = Ed25519 keypair, derived from credit_seed like the token itself
message       m = H("leasegrid/tok/v1" || t || pk_tok)
issuer signs  σ = BlindRSA(m)                          # issuer never sees m
spend         (t, pk_tok, σ, R, Sign_sk_tok(R))
node verifies RSA_verify(pk_issuer, m, σ)  ∧  Ed25519_verify(pk_tok, R)  ∧  t ∉ spent-set(epoch)
```

A node that saw a spend holds `(t, pk_tok, σ)` but not `sk_tok`, so it cannot bind the token to a different `R`. Settlement still sends `t` only. Token on disk grows from 96 B to ~330 B; at one token per GiB-share-month that is irrelevant. DLEQ disappears (an RSA signature is its own proof).

**Why not the alternatives:**

- *Online verification with the issuer at spend time* (node forwards `t`, issuer confirms): couples every allocate to issuer availability, and gives the issuer real-time spend timing per node. Rejected.
- *Threshold ristretto key across nodes*: research project. Rejected by rule 4.
- *Trust the nodes*: is what corner A/PrivateStorage does. It is not a friendnet.

**Timing.** Lab (gate 0c) ships on `ristretto-v0` to keep the 0b PASS intact. `rsa-bssa-v1` lands as its own gate (**0e**, below) before the second operator joins a paid grid. The wallet, `R`, spent-set, settlement, and UI are scheme-agnostic from day one so the swap touches `crypto.py`, the plugin verifier, and the `scheme` field — not the product.

---

## 10. Issuer deployment

- **Wallet:** `monero-wallet-rpc` running a **view-only** wallet (address + private view key) against the operator's own `monerod`. Spend key lives elsewhere (payout wallet; cold or separate host). The issuer process talks to wallet-rpc on localhost.
- **Chain adapter interface** (the seam that makes CI possible):

```python
class ChainWatcher(Protocol):
    def new_address(self, vid: bytes) -> tuple[str, int]: ...          # (subaddress, index)
    def received(self, index: int) -> tuple[int, int, int]: ...         # (piconero_0conf, piconero_confirmed, min_confirmations)
    def height(self) -> int: ...
```

Implementations: `FakeChain` (in-memory; `pay(index, piconero)` + `mine(n)`; exposed at `POST /v0/fake/pay` **only** when the issuer starts with `--chain fake`, with a red banner in logs and `/v0/info`), `WalletRpcChain` (`create_address`, `get_transfers in/pool` filtered by `subaddr_indices`), later `LwsChain` (monero-lws) if scale needs it.

- **State:** one SQLite file, WAL mode, single issuer process. Tables: `voucher`, `epoch`, `signed_batch`, `settlement`, `conflict`, `ledger_daily`. Never delete `voucher` rows.
- **Poller:** every 30 s walk vouchers in `quoted|seen|confirming|underpaid` (bounded by index range), update amounts, promote states. Idle vouchers older than `grace_until` with `amount_seen == 0` flip to `expired_unpaid` and drop out of the hot loop; they are still credited if paid later because the subaddress mapping is permanent.
- **Rate limits:** `POST /v0/quote` ≤ 10/min per source (per circuit/destination when anonymised — expect to fall back to a global cap); `MAX_OPEN_QUOTES` (unpaid) global. Quote creation is the only free write an anonymous party can trigger.
- **Backups:** SQLite + view key + signing keys nightly, off the issuer host, off git. Restore drill is a gate step.
- **Split from storage:** already required by `01-architecture.md`. With `rsa-bssa-v1` the storage host holds no secret at all.

---

## 11. U5 UI (Leasegrid Sync → Credit → Top up)

Reuses U2 Top up dialog chrome (`docs/design/17-U2-WIREFRAMES.md`); replaces the faucet body. Non-blocking: the dialog runs quote/poll/redeem on a worker thread (this also retires the known "join blocks the UI" pattern for this path).

| State | Dialog shows | Buyer can |
|---|---|---|
| Choose | tiers (10/50/200 credits) + custom; plain-language capacity line; XMR amount; "estimate in USD" only if opted in | Continue / Cancel |
| Pay | QR of `pay_uri`, address, exact amount, countdown to `quote_expires`, "send exactly this amount; after the timer we still credit for 24 h at this price" | Copy address / Copy amount / Open in wallet / Cancel (keeps voucher; shows in Pending) |
| Seen | "Payment seen. Confirming 0 of 2…" | Close (continues in background) |
| Confirming | "n of k confirmations (~2 min each)" | Close |
| Issuing | "Collecting your credits…" | — |
| Done | "+20 credits. Balance: 37" + Recent row | Done |
| Underpaid | "Received 0.05 XMR; one credit is 0.06. Send at least 0.01 more to the same address, or leave it — nothing is lost." | Copy address / Close |
| Late | "Paid after the price window; credited at today's price: 19 credits." | Done |
| Issuer unreachable | REVIEW: "Your grid's issuer did not answer. Payments already sent are safe; retry later." (no localhost URLs, no WUI, no terminal) | Retry / Close |

**Pending** list in the Credit panel: every voucher not `issued`, with state and amount; survives restart (it is just the wallet file). **Recovery key** export copy gains one line: "includes your credit seed; credits bought after this export can be recovered from the issuer for about a year."

Copy rules carried from U2 non-goals: no "XMR received" before confirmations, no 1:1 GiB claim, no raw token dumps, no admin/mint chrome.

---

## 12. Testing strategy

Everything except the real chain adapter runs in CI on all three OSes.

| Level | What | Where |
|---|---|---|
| Unit | voucher state machine (every transition in §2.2 incl. late/underpaid/overpaid), effective-price math, confirmation policy, deterministic `vid`/token derivation vectors, redeem idempotency (`200`/`409`/`402`/`410`), settlement dedup + conflict, ledger arithmetic, wallet WAL crash points | `tests/test_zkap_payment_*.py` |
| Integration | issuer with `FakeChain` + in-process client: quote → fake pay → mine → redeem → spend at fake node → settle; recovery from `credit_seed` alone; epoch burn + exchange | `tests/test_zkap_payment_lifecycle.py` |
| Exit test | `scripts/dev-grid.sh --chain fake`; `packaging/exit-test.sh` gains: quote → `/v0/fake/pay` → redeem → paid upload with those tokens; second home restores from recovery key and re-redeems | existing `installers.yml` |
| Gate 0c live | issuer `--chain wallet-rpc` on **stagenet**; faucet XMR from a public stagenet faucet; `leasegrid-zkap check-0c --live` prints PASS per `08-lab.md` 0c.1–0c.5 | manual, dated row in `08-lab.md` |
| Gate 0e live | `rsa-bssa-v1` epoch; storage node verifies with public key only; node cannot settle a fabricated `t`; node cannot re-spend a received token at a second node | manual, dated row |

Fake-chain mode is refused by the issuer unless `--chain fake` is explicit; the frozen builds carry the flag but the default is `wallet-rpc`, so no shipped binary accidentally issues free credit.

---

## 13. Build order (each slice leaves the previous ones green)

Written so a devbot can take one row at a time; every row names its test and its exit.

| # | Slice | Code | Exit |
|---|---|---|---|
| S0 | ✅ Voucher store + state machine + effective price + `FakeChain` | `leasegrid_zkap/payment/{store,chain,policy}.py` | unit tests for every §2.2 transition |
| S1 | ✅ Issuer endpoints `/v0/keys`, `/v0/quote`, `/v0/voucher/{vid}`, `/v0/redeem` (idempotent, cached batch), `/v0/ledger`; `--chain fake|wallet-rpc` flag; `--faucet` opt-in | `issuer.py`, `cli.py` | integration: quote → fake pay → redeem twice → identical batch |
| S2 | ✅ Client: `credit_seed`, deterministic vid/tokens, WAL pending record, `topup` + `recover` in `leasegrid_zkap` CLI; wallet keyed by `(issuer, epoch)` | `client.py`, `credit.py` | recovery test: wipe wallet, keep seed, balance returns |
| S3 | `WalletRpcChain` against `monero-wallet-rpc` (view-only, stagenet); poller; SQLite backup/restore script | `payment/chain_walletrpc.py`, `deploy/zkap-lab/` | manual stagenet smoke; restore drill |
| S4 | Settlement v1: `nodeid`+`epoch` in body, global dedup, conflicts, per-node ledger; `spend-listen` batches nightly | `issuer.py`, `plugin.py` | unit + integration |
| S5 | ✅ dev-grid `--chain fake`; exit-test payment steps | `scripts/dev-grid.sh`, `packaging/exit-test.sh` | three-OS installers workflow green 2026-09-20 |
| S6 | ✅ U5 UI: Top up quote → pay → poll; Pending list; recovery-key credit-seed copy | `leasegrid_sync/app.py`, `credit.py` | `tests/test_sync_ui.py` (Continue/pay/issued/underpaid/pending/export); faucet path kept for unpaid grids |
| S7 | **Gate 0c live** on stagenet | — | dated PASS row in `08-lab.md` |
| S8 | Epoch rotation + `/v0/exchange` + node key pull | `crypto.py`, `plugin.py` | burn-epoch integration test |
| S9 | `rsa-bssa-v1` scheme (RFC 9474 via `cryptography`), `pk_tok` spend binding, node verifies with public key only | `crypto.py`, `plugin.py`, `client.py` | **Gate 0e** dated PASS; then and only then a second paid operator |

S0–S2 and S4–S6 need no Monero at all. S3 and S7 need a stagenet wallet and an afternoon of block time.

---

## 14. Decisions this doc needs from the owner

1. **Transport: Tor or I2P.** Every existing doc (`01-architecture.md`, roadmap flag, U0 wireframes, Settings) says Tor; I2P is mentioned nowhere. Tahoe supports both (`[tor]`/`[i2p]`, `txtorcon`/`txi2p`); Monero supports both for tx broadcast; Magic Wormhole has `--tor` but no I2P; I2P adds noticeably more latency to sync than Tor. The payment rail does not care. If I2P is the intent, that is a docs-wide change (roughly a dozen files) and a Settings-copy change, and it should be its own ADR.
2. **Subaddress-per-quote instead of integrated address** (§3; ADR-0002). Accept, or keep `02-objects.md` as written.
3. **Confirmation defaults** 2 / 10 with 0.5 XMR threshold (§2.4).
4. **Grace window** 24 h at quoted price (§2.3).
5. **Scheme swap timing:** `rsa-bssa-v1` at gate 0e before operator #2 (recommended), or now for 0c (cleaner, but reopens 0b).
6. **Issuer fee** default for the payout formula (§9) — a number, not a design question, but it shows up in operator copy.
