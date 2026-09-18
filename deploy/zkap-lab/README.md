# Gate 0b — ZKAP lease lab (no XMR)

Thin Leasegrid authorizer for Tahoe **1.20.0**. This is **not** PrivateStorage `ZKAPAuthorizer` (PyPI pin `tahoe-lafs<1.18.1`). Crypto is `python-challenge-bypass-ristretto` (same family). Binding `R` follows [`docs/02-objects.md`](../../docs/02-objects.md). Decision: [`docs/adr/0001-thin-lab-zkap-authorizer.md`](../../docs/adr/0001-thin-lab-zkap-authorizer.md).

Corner C stays: no slash, no on-chain caps, no L1.

## Topology (existing friendnet)

| Role | Host | Address |
|------|------|---------|
| Introducer | leasegrid-1 | 10.42.0.70 |
| Storage | leasegrid-2, leasegrid-3, maximum | 10.42.0.40, .161, .238 |
| Client | nimo | (this builder) |
| Issuer | nimo or leasegrid-1 (not a storage box) | default `127.0.0.1:8700` |

Tahoe is already running via `tahoe run` under tmux (`lg-intro`, `lg-s2`, `lg-s3`, `lg-smax`). Node dirs: `~/.tahoe-introducer` / `~/.tahoe-storage` / `~/.tahoe` (nimo client).

## Secrets (off git)

Default paths (create the directory yourself):

```
~/DEVELOP/leasegrid-lab-private/issuer.signing.key
~/DEVELOP/leasegrid-lab-private/client-wallet.json
~/DEVELOP/leasegrid-lab-private/storage-spent.json
```

Never commit furls, caps, the signing key, or wallets.

## Denomination

**1 token = 1 GiB-share × 30 days on one node.** Tokens do not split.

## Invariant (0b.5)

Settlement POSTs `{spent-preimages: [t, ...]}` to the issuer. The issuer **rejects** JSON that contains `R` / `mac` / `storage_index`. Storage may keep `R` in its spent-set; the issuer must not see it.

## Local PASS/FAIL (no friendnet changes)

From the repo root, on nimo (Tahoe 1.20 present):

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/leasegrid-zkap check-0b
```

Honest output is `PASS` / `FAIL` per `0b.1`–`0b.5`, then `GATE 0b: PASS` or `GATE 0b: FAIL`.

`0b.2` requires `allmydata.storage.server.StorageServer` (Tahoe 1.20). If that import fails, 0b.2 is **FAIL**, not a skip.

## Friendnet enable (opt-in; breaks unpaid `tahoe put`)

Wrapping a live storage node makes **anonymous allocate fail** (that is 0b.2). `shares.happy = 3` means one gated node is enough to fail unpaid uploads. Restore by removing the plugin section and restarting `tahoe run`.

1. Vendor wheels on nimo (VMs often lack PyPI DNS):

   ```bash
   deploy/zkap-lab/scripts/vendor-wheels.sh
   ```

2. Generate the issuer key once on nimo, copy to storage (scp, not git):

   ```bash
   .venv/bin/leasegrid-zkap keygen --key-file ~/DEVELOP/leasegrid-lab-private/issuer.signing.key
   ```

3. On a storage host, install into that host's `~/tahoe-venv` and enable the plugin. Example leasegrid-2:

   ```bash
   deploy/zkap-lab/scripts/install-lab.sh --venv /home/mark/tahoe-venv --copy-dropin
   deploy/zkap-lab/scripts/enable-storage-plugin.sh \
     --node-dir /home/mark/.tahoe-storage \
     --key-file /home/mark/leasegrid-lab-private/issuer.signing.key \
     --spend-listen 10.42.0.40:8701
   ```

   Restart the existing tmux session (`tahoe run ~/.tahoe-storage`). Do not invent a second process manager.

4. Issuer on nimo (or leasegrid-1):

   ```bash
   .venv/bin/leasegrid-zkap issuer --listen 10.42.0.0:8700
   ```

   Bind the address nimo actually has on `10.42.0.0/24`; do not publish it in git.

5. Live check:

   ```bash
   .venv/bin/leasegrid-zkap check-0b --live \
     --issuer http://<nimo-lan>:8700 \
     --storage http://10.42.0.40:8701
   ```

Record a row in `docs/08-lab.md` **only** when this live check prints `GATE 0b: PASS`.

## Paid allocate vs `tahoe put`

GBS HTTP has no field for `(t, R, MAC_K(R))`. The lab spend is `POST /v0/spend` on the storage gate, then wrapped `allocate_buckets` for that `storage_index`. `check-0b` uses `/v0/lab/allocate` which calls the real Tahoe `StorageServer` when wrapped.

A future client plugin / GBS header can attach passes to CHK upload. That is not required to score 0b.4 on the protocol objects.

## CLI

```
leasegrid-zkap keygen
leasegrid-zkap issuer --listen 127.0.0.1:8700
leasegrid-zkap storage-gate --nodeid <my_nodeid> --listen 127.0.0.1:8701
leasegrid-zkap faucet --issuer http://127.0.0.1:8700 --out ~/DEVELOP/leasegrid-lab-private/client-wallet.json
leasegrid-zkap spend --storage http://127.0.0.1:8701 --nodeid ... --storage-index <32 hex chars>
leasegrid-zkap settle --issuer http://127.0.0.1:8700 --from-storage http://127.0.0.1:8701
leasegrid-zkap check-0b
```
