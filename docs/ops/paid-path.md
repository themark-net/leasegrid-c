# Paid path — credit is spent on upload

**Cite:** `docs/02-objects.md` §2.3–2.7 (spend, R, LeaseGate) · gate 0b report · `docs/09-ui-track.md` U2  
**Status:** PASS on the dev grid with `LEASEGRID_GATED=1` (evidence below). Before this the
storage side could refuse unpaid leases but nothing on the client ever paid, so Credit was
minted and held, never spent.

Screenshot: [`u2-paid-credit.png`](u2-paid-credit.png) — Credit place after a paid upload
(`Lease on <node> · <storage index>  −1 GiB·mo` per node per storage index).

## What happens on upload

```
Sync app ──(wallet file)──► Tahoe client process
                              └─ storage plugin leasegrid-zkap-v0 (client side)
                                   for each write to node N of storage index SI:
                                     1. grant cached for (N, SI)?  → forward
                                     2. else pop token, R = (nodeid, SI, 30d, 1 GiB, issuer),
                                        POST N's /v0/spend {t, R, MAC_K(R)}
                                     3. record grant, append "Lease on N · SI" to credit-recent
                                     4. forward allocate / writev over Foolscap
Storage node N ── LeaseGate: allocate/add_lease/renew/writev refused unless a spend for SI exists
```

Reads (`get_buckets`, `slot_readv`) are free. Wallet-empty → `NoCredit` client-side, nothing
sent, Credit place shows `Upload refused: out of credit`. Node says 403 (forged / replayed
pass) → the token is parked in `wallet["rejected"]`, never retried, `Pass rejected by N`
appears in Recent. Network error → token goes back into the wallet.

## Pieces

| Where | What |
|---|---|
| `leasegrid_zkap/spender.py` | `WalletSpender` — wallet pop, R/MAC, spend HTTP, grant cache (`credit-grants.json`), recent events; **one shared instance per wallet path**, thread lock + `flock` on `<wallet>.lock` |
| `leasegrid_zkap/plugin.py` | server: announces `spend-url` + `nodeid`; client: `ZKAPStorageClient` — full `IStorageServer`, pays before every write |
| `leasegrid_zkap/client.py` | `wallet_lock()`, atomic `save_wallet()` |
| `leasegrid_sync/backend.py` | `TahoeClient.ensure_credit_plugin()` — writes `[client] storage.plugins`, `force_foolscap = true`, `[storageclient.plugins.…] wallet-path/grants-path/recent-path` into the client's `tahoe.cfg` on create and before every start |
| `scripts/dev-grid.sh` | `LEASEGRID_GATED=1` → each storage node gets `plugins = leasegrid-zkap-v0`, `force_foolscap = true`, a spend listener on 8711.. and its own spent set |
| `src/twisted/plugins/leasegrid_zkap_dropin.py` | now installed with the package (was only found when cwd was the repo root) |

## Why `force_foolscap`

Tahoe 1.20 uses GBS/HTTP whenever a node announces `anonymous-storage-NURLs`, and the HTTP
storage client never consults storage plugins (`storage_client._should_we_use_http`). So:

- gated **nodes** set `[storage] force_foolscap = true` — they stop announcing NURLs; there is
  no unpaid HTTP side door;
- the paying **client** sets `[client] force_foolscap = true` — otherwise it would pick HTTP
  against any mixed grid and get refused.

This is the concrete form of the 0b note “GBS HTTP has no ZKAP header”. Moving the paid path to
GBS needs a header/extension upstream; Foolscap is fully supported in 1.20 so the lab runs on it.

## XMR lab path (FakeChain)

Same spend path; credit is bought with a quote instead of the faucet. The issuer
is still `--chain fake` — no Monero daemon. This is what the installer exit test
runs (`07-payment.md` S5):

```
$ leasegrid-zkap topup --issuer http://127.0.0.1:8700 \
    --wallet "$LEASEGRID_SYNC_HOME/credit-wallet.json" --tokens 20 --json
$ # POST /v0/fake/pay  {vid, amount_piconero, mine: 2}
$ leasegrid-sync --credit-status                     20
$ leasegrid-sync --dogfood-folder /tmp/lg-paid-sync
U1 dogfood … probe=u1-hello.txt status={… 'size': 34}
```

`--credit-dogfood` is quote → pay → redeem (fake chain in the lab, stagenet wallet-rpc when `LEASEGRID_STAGENET_WALLET_RPC` is set). It does not call the faucet. Unpaid allocate still fails.

## Evidence (dev grid, gated, 2026-09-20)

```
$ leasegrid-sync --join pb://…                      Connected  introducer up · 3 storage
$ leasegrid-sync --dogfood-folder /tmp/lg-paid-sync  # zero credit
FAIL — folder not added. Error: Magic Folder HTTP API reported error 500 …
credit-recent: ['Upload refused: no credit on this device']
$ leasegrid-sync --credit-dogfood --credit-tier medium
U2 credit-dogfood before=0 after=50
$ leasegrid-sync --dogfood-folder /tmp/lg-paid-sync
U1 dogfood … probe=u1-hello.txt status={… 'size': 34}
$ leasegrid-sync --credit-status                     38
grants: {'2bv4nnpz': 4, '4qoe35ja': 4, 'wooylxr2': 4} total 12
node spent-sets: 4 / 4 / 4          recent events: 13, duplicates: none
```

12 tokens spent = 12 grants = 12 node-side spends. (The first run, before the shared spender,
showed 15 node-side spends for 7 wallet tokens — that bug is what `test_shared_spender_keeps_
exact_accounting_under_concurrency` pins.)

## The finding that needs a design decision

**One folder with one 34-byte file cost 12 tokens = 12 GiB·month of credit.**

Magic Folder creates four storage indexes per folder+file (collective dir, personal DMD,
content CHK, snapshot metadata) and `shares.total = 3` puts each on three nodes. The v0
denomination is *1 token = 1 GiB-share × 30 days on one node* and the LeaseGate keys grants by
storage index, so every tiny object burns a whole token per node.

Options, in rough order of effort:

1. **Smaller denomination** (ZKAPAuthorizer uses 1 MB-month passes and spends `ceil(size / 1 MB)`
   per share). Changes `constants.DENOMINATION`, `R.share_bytes`, `require_allocate`, the
   faucet tiers and the Credit copy (`format_remaining`). Cleanest.
2. **Per-node quota instead of per-SI grants**: a spend buys N bytes on a node, the gate
   decrements across storage indexes. Better fit for Magic Folder's many small objects; needs
   a new grant table and renewal semantics.
3. Leave v0 as is for the lab and raise the faucet tiers. Honest but the Credit copy “About
   48 GiB kept” is then misleading in practice.

`docs/02-objects.md` calls the denomination architecture, not a knob, so this is a design-doc
change first. Nothing in this slice pre-empts it: the spend/grant plumbing is denomination-
agnostic (`share_bytes`, `need_bytes`).

## Dogfood

```bash
LEASEGRID_GATED=1 scripts/dev-grid.sh              # server side
export LEASEGRID_ISSUER_URL=http://127.0.0.1:8700 # client side
leasegrid-sync                                     # join, Credit → Top up (medium), Folders → Add
```

Watch the Credit place: each upload adds `Lease on …  −1 GiB·mo` rows; Remaining drops.
Node view: `curl http://127.0.0.1:8711/v0/info` shows `spent`.

## Not done

- Settlement (node → issuer spent preimages) still manual: `leasegrid-zkap settle …`.
- Lease *renewal* payments: the gate accepts `renew` with the original grant; nothing schedules
  a renewal spend after 30 days.
- Renewal / settlement automation as above. (The Folders place now reads the spender's
  `Upload refused…` events and shows “sync is paused by the friendnet … Credit → Top up”
  instead of Magic Folder's raw error 500.)
