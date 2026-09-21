# 08 — Lab criterion (Phase 0)

This is the **PASS/FAIL** gate for corner C. Do not call Phase 0 done until every required gate below is **PASS** with a dated note (operator, hostnames, commit/SHA). A slogan in the README is not a PASS.

Architecture: [`00-decision.md`](00-decision.md), [`01-architecture.md`](01-architecture.md), [`02-objects.md`](02-objects.md). Sequencing: [`03-roadmap.md`](03-roadmap.md).

## What “PASS” means

One continuous story on real machines (LAN lab is enough; Tor optional for Phase 0):

1. Pay (or faucet) **XMR** that embeds a `vid`.
2. Issuer mints a **ZKAP** batch for that `vid`.
3. Client spends ZKAPs so a storage node **allocates / renews a lease**.
4. Operator **silently ejects** a dead or unpaid node (stop feeding it).
5. Client or repair agent **moves shares** onto live certified nodes until the upload/repair happy-set is met again.

B-lite bonds are **out of scope**. Magic Folder UX is **out of scope** for this file (Phase 1).

## Topology (lab default)

Match the stock friendnet bootstrap when present (`deploy/friendnet/`):

| Role | Example host |
|---|---|
| Introducer | `leasegrid-1` |
| Storage | `borg`, `maximum`, `plant` (need ≥ happy) — **0a used** `leasegrid-2`, `leasegrid-3`, `maximum` |
| Client | `nimo` |
| Issuer | Separate process/box from storage as soon as two machines exist (one-box OK for gate 0b only) |

Secrets (furls, keys, wallet files) stay **off git**.

## Gates (run in order)

### Gate 0a — Stock friendnet smoke

**Intent:** Unpaid Tahoe grid works before payment code.

| Step | Action | PASS if |
|---|---|---|
| 0a.1 | Install Tahoe on introducer, ≥3 storage, client | `tahoe --version` on each |
| 0a.2 | Create introducer; storage + client join | Client WUI/CLI sees all storage nicknames connected |
| 0a.3 | Set `shares.needed` / `happy` / `total` to fit live storage count | Config matches node count |
| 0a.4 | `smoke-put-get` (or equivalent put→get→byte-compare) | Prints **PASS**; no caps committed to git |

**FAIL if:** any storage missing, put refused for happy-set, or secrets landed in the repo.

**Record:** date, hosts, Tahoe version, happy/needed/total, PASS/FAIL.

### Gate 0b — ZKAP lease gate (no XMR yet)

**Intent:** Storage refuses allocate/renew without a valid ZKAP; accepts with one. Proves plugin + issuer mint without Monero.

| Step | Action | PASS if |
|---|---|---|
| 0b.1 | Run lab issuer (ristretto / ZKAPAuthorizer-compatible) | Issuer URL reachable from client; pubkey id recorded |
| 0b.2 | Configure storage with ZKAPAuthorizer (or Leasegrid plugin) requiring ZKAP on allocate/add_lease/renew | Anonymous allocate **fails** |
| 0b.3 | Faucet-mint a ZKAP batch to the client (no chain) | Client holds tokens; denomination documented (v0: 1 token = 1 GiB-share × 30 days on one node) |
| 0b.4 | Spend ZKAP with request binding `R` per [`02-objects.md`](02-objects.md) | Allocate/renew **succeeds**; replay of same `t` on different `R` **fails**; idempotent replay on same lease OK |
| 0b.5 | Issuer does **not** receive `R` | Settlement path sends spent `t` only (or lab stub documents the same invariant) |

**FAIL if:** storage still allows unpaid writes, or caps/`R` leak to issuer logs.

**Record:** issuer pubkey id, plugin versions, token denomination, PASS/FAIL.

**Implementation (code, not a PASS):** `src/leasegrid_zkap/` + `deploy/zkap-lab/`. Thin lab authorizer using `python-challenge-bypass-ristretto`; **not** PyPI ZKAPAuthorizer (Tahoe 1.20). Run `deploy/zkap-lab/scripts/check-0b.sh`. Append a results-log row only when `--live` against the friendnet prints `GATE 0b: PASS`. See [ADR-0001](adr/0001-thin-lab-zkap-authorizer.md).

### Gate 0c — XMR → `vid` → ZKAP

**Intent:** Real Monero payment (testnet, stagenet, or tiny mainnet) drives issuance. Design: [`07-payment.md`](07-payment.md) (quote / voucher / redeem protocol, confirmation policy, build order S0–S7).

| Step | Action | PASS if |
|---|---|---|
| 0c.1 | Issuer allocates `vid` (8 bytes) and returns an integrated address embedding it | Client pays that address only |
| 0c.2 | Client pays XMR with that integrated address | Payment confirms; issuer view-key scan matches `vid` |
| 0c.3 | Issuer issues ZKAP batch for amount → `tokens_owed` | Batch DLEQ verifies; voucher marked spent for issuance |
| 0c.4 | Wrong/`vid` mismatch or underpay | **No** tokens issued |
| 0c.5 | Client spends new tokens on lease as in 0b | Lease extends; unpaid path still fails |

**FAIL if:** ZKAPs fit in a payment memo, or issuance without matching payment.

**Record:** network (stage/main), approximate amount, confirmations required, PASS/FAIL. No tx secrets in git.

**Implementation (code, not a PASS):** the quote → voucher → redeem lifecycle runs in CI against `FakeChain` (`src/leasegrid_zkap/payment/`, `leasegrid-zkap topup`, gated `packaging/exit-test.sh`). `WalletRpcChain` talks to `monero-wallet-rpc` (`create_address` / `get_transfers` / `get_height`) and is covered by a JSON-RPC stand-in in CI; `--chain wallet-rpc` is wired. Attribution is a **fresh subaddress per quote** ([`07-payment.md`](07-payment.md) §3 / [ADR-0002](adr/0002-payment-attribution-and-token-scheme.md)), not the integrated-address form in 0c.1–0c.2 above — those rows stay until the owner accepts §14. Live 0c (stagenet + dated PASS) is S7 and is not started.

### Gate 0d — Silent eject + repair

**Intent:** Liveness without slash.

| Step | Action | PASS if |
|---|---|---|
| 0d.1 | Upload object with redundant shares across ≥ happy storage nodes | Object readable |
| 0d.2 | Stop or partition one storage node that holds shares | Node unreachable |
| 0d.3 | Grid-manager / introducer policy: short-TTL cert expiry or probe → **silent eject** (drop from client’s usable set); **stop paying** that nodeid | Ejected nodeid no longer receives new leases/payments |
| 0d.4 | Client or repair agent reconstructs onto remaining live certified nodes | Object readable again; happy-set restored (or documented degraded mode with explicit FAIL if happy cannot be met) |
| 0d.5 | No public slash, no PoRep, no bond required | Logs show eject + repair only |

**FAIL if:** data permanently lost when happy could still be met, or “repair” requires a bond/slash path.

**Record:** which node ejected, repair method, before/after connected storage count, PASS/FAIL.

**Implementation (code, not a live PASS):** `src/leasegrid_zkap/eject.py` (`EjectSet` + probe), spender/plugin refuse to pay an ejected nodeid, `leasegrid-zkap check-0d` / `eject` / `probe` / `repair`, `deploy/zkap-lab/scripts/repair-drill.sh`. Covered by `tests/test_zkap_eject.py`. Dated live 0d PASS (real Tahoe happy-set) is not started.

### Gate 0e — Publicly verifiable tokens (`rsa-bssa-v1`)

**Intent:** a second paid operator cannot mint and cannot re-bind a token it received. Lab (0b/0c) stays on `ristretto-v0`. This gate is required before operator #2 joins a paid grid ([`07-payment.md`](07-payment.md) §9, [ADR-0002](adr/0002-payment-attribution-and-token-scheme.md)).

| Step | Action | PASS if |
|---|---|---|
| 0e.1 | Issuer opens an `rsa-bssa-v1` epoch; client quotes/redeems that scheme | Tokens verify with the RSA **public** key only |
| 0e.2 | Storage node accepts a spend `(t, pk_tok, σ, R, Sign_sk_tok(R))` | Lease granted; node holds no issuer signing secret |
| 0e.3 | Fabricated `σ` / unknown `t` | Node refuses; issuer settlement of that `t` is rejected or unpaid |
| 0e.4 | Node that saw a valid spend retries the same `t` at a second node with a new `R` | Second spend refused (`pk_tok` did not sign `R'`) |
| 0e.5 | Settlement body is spent `t` only | Issuer rejects any body that includes `R` |

**FAIL if:** the node can mint, or can re-bind a received token, or 0b `ristretto-v0` regresses.

**Implementation (code, not a PASS):** `src/leasegrid_zkap/rsa_bssa.py` + issuer quote/redeem + `LeaseGate.spend_rsa` covered by `tests/test_zkap_rsa_bssa.py` (RFC 9474 A.3). Dated live PASS is not started.

**Record:** issuer pubkey id, scheme, commit/SHA, PASS/FAIL. No secrets in git.

## Phase 0 exit

| Required | Status |
|---|---|
| Gate 0a PASS | ✅ 2026-09-17 |
| Gate 0b PASS | ✅ 2026-09-17 |
| Gate 0c PASS | ☐ |
| Gate 0d PASS | ☐ |
| Results dated below (or linked private operator notes — no secrets) | ✅ partial (0a, 0b) |

**Phase 0 PASS** only when all four gates are PASS. Then capital may move to Phase 1 (Magic Folder buyer surface) **and** demand falsification — not before.

## Results log

Append rows; never paste furls, caps, seed phrases, or view keys.

| Date (PT) | Gate | Operator | Result | Notes (hosts, versions) |
|---|---|---|---|---|
| 2026-09-17 ~7:44pm PT | 0a | Leasegrid Stress Test (via nimo) | **PASS** | Tahoe 1.20.0. Introducer `leasegrid-1` (10.42.0.70). Storage `leasegrid-2` (10.42.0.40), `leasegrid-3` (10.42.0.161), `maximum` (10.42.0.238). Client `nimo`. shares needed/happy/total = 1/3/3. `smoke-put-get` PASS. Nodes kept alive with tmux/screen (`tahoe run`). Lab notes: pin cryptography 41.0.7 + pyOpenSSL 23.3.0 + service-identity 23.1.0 (VMs lack PyPI DNS); nimo needs `legacy-cgi` on Python 3.14. `deploy/friendnet/` still local-only. No furls/caps in git. |
| 2026-09-17 ~9:10pm PT | 0b | Leasegrid Stress Test (via nimo) | **PASS** | Thin lab authorizer `leasegrid-zkap-lab` 0.1.0 + `python-challenge-bypass-ristretto` 2022.6.30 (not PyPI ZKAPAuthorizer; Tahoe 1.20). Issuer on nimo; pubkey id `09e9633f194ba8bf2df91e69c0e497619a24ebd6a4fa7814406c836796995ab5`. Plugin wrap on storage `leasegrid-2` only (`spend-listen` 10.42.0.40:8701). Denomination: 1 token = 1 GiB-share × 30 days on one node. `leasegrid-zkap check-0b --live` GATE 0b PASS (0b.1–0b.5). Unpaid non-LIT `tahoe put` → `UploadUnhappinessError` (GBS allocate 500/`ZKAPRequired` on leasegrid-2; 2/3 servers placed shares). LIT puts still skip allocate. Issuer rejects settlement JSON that contains `R`. Signing key off-git (`~/DEVELOP/leasegrid-lab-private/`). Restore unpaid: `enable-storage-plugin.sh --disable` + restart `tahoe run`. |

## First implementation slice (after this doc)

Build in this order; each slice should make the next gate runnable:

1. **0a** — Keep/finish stock friendnet bootstrap; record 0a PASS on LAN.
2. **0b** — Lab issuer + ZKAPAuthorizer (or thin wrapper) on one storage node; faucet mint; lease gate tests.
3. **0c** — Monero intake (`vid` + integrated address + view-key scan) wired to the same issuer.
4. **0d** — Short-TTL cert / probe eject policy + repair drill script.

Do not start Magic Folder, MictlanX placement experiments, or B-lite until Phase 0 PASS (see roadmap).
