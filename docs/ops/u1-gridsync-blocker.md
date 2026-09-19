# U1 — Gridsync fork / ZKAP credit blocker (short)

**U1 still ships a Gridsync-lineage native Sync** (PyQt window, folder list + status, Magic Folder daemon, tray). It does **not** fall back to Tahoe WUI.

## Why this spike is a wrap, not an in-tree Gridsync fork

| Issue | Detail |
|-------|--------|
| License | Gridsync is **GPL-3.0**. This repo is Apache-2.0. Vendoring Gridsync source here would dual-license / contaminate the tree. A wrap in `src/leasegrid_sync/` stays Apache-2.0; Gridsync remains a separate upstream. |
| Tahoe pin | Lab friendnet is Tahoe **1.20.0** (`/home/mark/tahoe-venv`). Gridsync bundles its own Tahoe + Magic-Folder pins and wants to own `~/.config/gridsync/` nodedirs rather than the existing nimo `~/.tahoe`. |
| ZKAP plugin | Gridsync `zkapauthorizer.py` is hardcoded to PrivateStorage plugin `privatestorageio-zkapauthz-v2` (vouchers, `/storage-plugins/…/voucher`). Leasegrid lab credit is **`leasegrid-zkap-v0`** (ADR-0001), not PyPI ZKAPAuthorizer. |

## U2 implication (not a U1 FAIL)

Credit panel (U2) must talk to `leasegrid_zkap` issuer/faucet, not Gridsync’s PrivateStorage voucher UI. Options then: (1) keep this wrap and add a Credit place; (2) fork Gridsync **out of tree** under GPL and replace `PLUGIN_NAME`. Do not silently embed WUI either way.

U1 DoD does not require that fork. This note exists so U2 does not assume in-tree Gridsync sources.
