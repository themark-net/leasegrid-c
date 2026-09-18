# Gate 0b report

**Status: PASS** (live friendnet, 2026-09-17)

Honest local + live `leasegrid-zkap check-0b` printed `GATE 0b: PASS` for 0b.1–0b.5. Unpaid non-LIT `tahoe put` from nimo then failed with `UploadUnhappinessError` because GBS `allocate_buckets` on `leasegrid-2` returned HTTP 500 / `ZKAPRequired`. LIT puts still skip storage (not an allocate). `docs/08-lab.md` results log updated.

## What landed

- Thin lab authorizer `src/leasegrid_zkap/` (ADR-0001). **Not** PyPI ZKAPAuthorizer (`tahoe-lafs<1.18.1`).
- Ristretto via `python-challenge-bypass-ristretto` 2022.6.30 (imports on CPython 3.12 and 3.14).
- Issuer HTTP: blinded faucet `/v0/issue`, settlement `/v0/settlement` that **rejects `R`**.
- Storage gate: `/v0/spend` + wrap of Tahoe 1.20 `StorageServer.allocate_buckets` / `add_lease` / `renew_lease` (GBS HTTP and Foolscap share that singleton).
- Client: `leasegrid-zkap faucet|spend|settle`.
- Operator: `deploy/zkap-lab/`.
- Check: `leasegrid-zkap check-0b` (local) and `--live`.

Denomination: **1 token = 1 GiB-share × 30 days on one node**. Domain: `leasegrid-v0`.

## How to run

```bash
# local (needs Tahoe 1.20 on PYTHONPATH / tahoe-venv)
/home/mark/tahoe-venv/bin/leasegrid-zkap check-0b

# live (issuer on nimo, plugin already on leasegrid-2)
/home/mark/tahoe-venv/bin/leasegrid-zkap issuer \
  --key-file ~/DEVELOP/leasegrid-lab-private/issuer.signing.key \
  --listen 127.0.0.1:8700
/home/mark/tahoe-venv/bin/leasegrid-zkap check-0b --live \
  --issuer http://127.0.0.1:8700 \
  --storage http://10.42.0.40:8701 \
  --nodeid h4xivcmxr3n3nfdc3bxmdhqe77mokfay
```

Signing key stays at `~/DEVELOP/leasegrid-lab-private/issuer.signing.key` (mode 0600, not in git).

Issuer pubkey id (public): `09e9633f194ba8bf2df91e69c0e497619a24ebd6a4fa7814406c836796995ab5`

Restore unpaid 0a on leasegrid-2:

```bash
ssh leasegrid-2 'bash ~/DEVELOP/leasegrid-c/deploy/zkap-lab/scripts/enable-storage-plugin.sh --node-dir ~/.tahoe-storage --disable'
# then restart tmux session lg-s2: tahoe run ~/.tahoe-storage
```

## Friendnet state after this work

| Host | Change |
|------|--------|
| nimo | `leasegrid-zkap-lab` + CBR in `~/tahoe-venv`; issuer key generated |
| leasegrid-2 | plugin enabled; `tahoe run` restarted in tmux `lg-s2`; spend HTTP `10.42.0.40:8701` |
| leasegrid-1 / leasegrid-3 / maximum | unchanged (ungated storage / introducer) |

`shares.happy = 3` so one gated node is enough to fail unpaid uploads.

## Blockers

None for 0b. Known limits (not FAIL):

- GBS has no ZKAP header; paid CHK `tahoe put` is not wired. 0b.4 is spend + wrapped `allocate_buckets` (`/v0/lab/allocate`). Anonymous CHK put **does** fail.
- Storage holds a copy of the issuer signing key (ZKAPAuthorizer model).
- VMs: no PyPI DNS; used rsync + `--no-index` wheel + `.pth` (setuptools build backend missing in leasegrid-2 venv).

## PR

See git / `gh` output in the same session. If push failed: branch `lab/gate-0b-zkap` is local; next mechanical step is `git push -u origin lab/gate-0b-zkap` then `gh pr create` after `gh auth login`.
