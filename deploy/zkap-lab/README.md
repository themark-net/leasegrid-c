# Gate 0b — ZKAP lease lab (no XMR)

Thin Leasegrid authorizer for Tahoe **1.20.0**. This is **not** PrivateStorage `ZKAPAuthorizer` (PyPI pin `tahoe-lafs<1.18.1`). Crypto is `python-challenge-bypass-ristretto` (same family). Binding `R` follows [`docs/02-objects.md`](../../docs/02-objects.md). Decision: [`docs/adr/0001-thin-lab-zkap-authorizer.md`](../../docs/adr/0001-thin-lab-zkap-authorizer.md).

Corner C stays: no slash, no on-chain caps, no L1.

## Topology (existing friendnet)

| Role | Host | Address |
|------|------|---------|
| Introducer | lab-introducer | <introducer-ip> |
| Storage | lab-storage-a, lab-storage-b, lab-storage-c | `<storage-a-ip>`, `<storage-b-ip>`, `<storage-c-ip>` |
| Client | lab-client | (this builder) |
| Issuer | lab-client or lab-introducer (not a storage box) | default `127.0.0.1:8700` |

Tahoe is already running via `tahoe run` under tmux (`lg-intro`, `lg-s2`, `lg-s3`, `lg-smax`). Node dirs: `~/.tahoe-introducer` / `~/.tahoe-storage` / `~/.tahoe` (client).

## Secrets (off git)

Default paths under `$LEASEGRID_LAB_DIR` (default `~/leasegrid-lab-private`; create the directory yourself):

```
~/leasegrid-lab-private/issuer.signing.key
~/leasegrid-lab-private/client-wallet.json
~/leasegrid-lab-private/storage-spent.json
```

Never commit furls, caps, the signing key, or wallets.

## Denomination

**1 token = 1 GiB-share × 30 days on one node.** Tokens do not split.

## Invariant (0b.5)

Settlement POSTs `{spent-preimages: [t, ...]}` to the issuer. The issuer **rejects** JSON that contains `R` / `mac` / `storage_index`. Storage may keep `R` in its spent-set; the issuer must not see it.

## Local PASS/FAIL (no friendnet changes)

From the repo root, on lab-client (Tahoe 1.20 present):

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/leasegrid-zkap check-0b
```

Honest output is `PASS` / `FAIL` per `0b.1`–`0b.5`, then `GATE 0b: PASS` or `GATE 0b: FAIL`.

`0b.2` requires `allmydata.storage.server.StorageServer` (Tahoe 1.20). If that import fails, 0b.2 is **FAIL**, not a skip.

## Friendnet enable (opt-in; breaks unpaid `tahoe put`)

Wrapping a live storage node makes **anonymous allocate fail** (that is 0b.2). `shares.happy = 3` means one gated node is enough to fail unpaid uploads. Restore by removing the plugin section and restarting `tahoe run`.

1. Vendor wheels on lab-client (VMs often lack PyPI DNS):

   ```bash
   deploy/zkap-lab/scripts/vendor-wheels.sh
   ```

2. Generate the issuer key once on lab-client, copy to storage (scp, not git):

   ```bash
   .venv/bin/leasegrid-zkap keygen --key-file ~/leasegrid-lab-private/issuer.signing.key
   ```

3. On a storage host, install into that host's `~/tahoe-venv` and enable the plugin. Example lab-storage-a:

   ```bash
   deploy/zkap-lab/scripts/install-lab.sh --venv ~/tahoe-venv --copy-dropin
   deploy/zkap-lab/scripts/enable-storage-plugin.sh \
     --node-dir ~/.tahoe-storage \
     --key-file ~/leasegrid-lab-private/issuer.signing.key \
     --spend-listen <storage-a-ip>:8701
   ```

   Restart the existing tmux session (`tahoe run ~/.tahoe-storage`). Do not invent a second process manager.

4. Issuer on lab-client (or lab-introducer):

   ```bash
   .venv/bin/leasegrid-zkap issuer --listen <client-lan-ip>:8700 --faucet
   ```

   Bind the address lab-client actually has on the lab LAN; do not publish it in git.

5. Live check:

   ```bash
   .venv/bin/leasegrid-zkap check-0b --live \
     --issuer http://<client-lan-ip>:8700 \
     --storage http://<storage-a-ip>:8701
   ```

Record a row in `docs/08-lab.md` **only** when this live check prints `GATE 0b: PASS`.

## Paid allocate vs `tahoe put`

GBS HTTP has no field for `(t, R, MAC_K(R))`. The lab spend is `POST /v0/spend` on the storage gate, then wrapped `allocate_buckets` for that `storage_index`. `check-0b` uses `/v0/lab/allocate` which calls the real Tahoe `StorageServer` when wrapped.

A future client plugin / GBS header can attach passes to CHK upload. That is not required to score 0b.4 on the protocol objects.

## CLI

```
leasegrid-zkap keygen
leasegrid-zkap issuer --listen 127.0.0.1:8700 --faucet          # faucet is opt-in; --chain fake for the XMR lab flow
leasegrid-zkap issuer --chain wallet-rpc --wallet-rpc-url http://127.0.0.1:18083/json_rpc --db ~/leasegrid-lab-private/issuer.sqlite
leasegrid-zkap storage-gate --nodeid <my_nodeid> --listen 127.0.0.1:8701
leasegrid-zkap faucet --issuer http://127.0.0.1:8700 --out ~/leasegrid-lab-private/client-wallet.json
leasegrid-zkap spend --storage http://127.0.0.1:8701 --nodeid ... --storage-index <32 hex chars>
leasegrid-zkap settle --issuer http://127.0.0.1:8700 --from-storage http://127.0.0.1:8701
leasegrid-zkap check-0b
```

## Issuer backup (S3)

`WalletRpcChain` is view-only: restore the SQLite file + view key + signing key and nothing is lost (subaddress indices are never reused).

```bash
deploy/zkap-lab/scripts/backup-issuer.sh \
  --db ~/leasegrid-lab-private/issuer.sqlite \
  --out-dir ~/leasegrid-lab-private/issuer-backups \
  --signing-key ~/leasegrid-lab-private/issuer.signing.key

# stop the issuer, then:
deploy/zkap-lab/scripts/restore-issuer.sh \
  --from ~/leasegrid-lab-private/issuer-backups/issuer-YYYYMMDDThhmmssZ.sqlite \
  --db ~/leasegrid-lab-private/issuer.sqlite \
  --force
```

Live stagenet smoke (`--chain wallet-rpc` against a real view-only wallet) is gate 0c / S7, not this lab README.

## Silent eject (0d, local)

```bash
leasegrid-zkap check-0d
leasegrid-zkap eject --nodeid NODE --eject-set ~/leasegrid-lab-private/ejected.json
deploy/zkap-lab/scripts/repair-drill.sh --nodeid NODE --url http://127.0.0.1:8701
```

Ejected nodeids are not paid and not written. Repair is reconstruct onto remaining nodes. No slash.

