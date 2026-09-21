# U4 — Recovery key (export / import)

**Cite:** `docs/09-ui-track.md` U4 · `docs/design/12-U0-WIREFRAMES.md` §4 · `docs/03-roadmap.md` Phase 1 “Recovery Key / capability backup”  
**Not:** Tahoe WUI. Not a Tahoe rootcap you paste by hand. Not a “reset password”.

Screenshots: [`u4-recovery.png`](u4-recovery.png) (Recovery place), [`u4-export-gate.png`](u4-export-gate.png) (scary gate).

## What the key holds

One file, `*.leasegrid-recovery`, JSON envelope. With a passphrase the body is
scrypt (n=2^15, r=8, p=1) → Fernet; without one it is plaintext and the UI says so.

| Field | Why |
|-------|-----|
| `introducer_furl`, `shares`, `nickname` | recreate the Tahoe client on a new device |
| `folders[]` — `name`, `collective_dircap`, `upload_dircap`, `magic_path`, intervals | rejoin each Magic Folder |
| `wallet` | credit tokens (bearer; see caveat) |
| `issuer_url` | which friendnet issuer the wallet belongs to |

Written `0600`, then read back and decrypted before the UI reports success.

## How restore works (and why it is a *new participant*)

Magic Folder never downloads a participant's own snapshots: the downloader
marks the DMD that matches our upload cap as `is_self` and skips it. Restoring
the old `upload_dircap` on an empty disk would therefore sync nothing.

So restore does what a second device does:

1. `tahoe create-node` from the furl + shares (same unpaid join=offer path), start it, wait for the introducer.
2. `magic-folder init`.
3. Per folder: `mkdir` a fresh personal DMD on the grid, write the folder into the
   Magic Folder config with the **old collective cap** and the **new personal DMD**,
   under a new author name `user@host-xxxx`.
4. Start the daemon and `POST …/participants` to announce the new DMD in the collective.
5. The old device's files download into `~/Leasegrid/<folder>` (`LEASEGRID_RESTORE_ROOT`).

The lost device stays listed as a participant. If it comes back, both keep syncing
(normal Magic Folder multi-device behaviour).

## Dogfood

Window: **More → Recovery**. Check the threat box (HITL). **Restore to Folders** is the primary button and lands on the folder list. **Export recovery key…** stays disabled until that box is checked, then still needs both export ACKs (no one-click dump). Folders also has **Restore from recovery key…**. Fresh device: join page → **Import recovery key instead…** (same threat box, then the folder list).

Headless (same as the e2e run on the dev grid). Export without the three ACKs FAILs and writes nothing:

```bash
export LEASEGRID_RECOVERY_PASSPHRASE='correct horse'
# device A
leasegrid-sync --export-recovery ~/leasegrid-nimo.leasegrid-recovery \
  --ack-threat --ack-loss --ack-store
# device B (empty LEASEGRID_SYNC_HOME)
LEASEGRID_RESTORE_LINGER=45 leasegrid-sync --restore-recovery ~/leasegrid-nimo.leasegrid-recovery \
  --ack-threat
ls ~/Leasegrid/<folder>       # files back from the friendnet
```

Evidence (dev grid, 2026-09-20): `recovery-restore folders=e2e … author=ubuntu@cursor-d79c
grid=introducer up · 3 storage`; `e2e-hello.txt` byte-identical with original mtime;
`--credit-status` on B shows the restored 10 GiB·mo. Wrong passphrase: `FAIL — could not
import this recovery key` and nothing created.

## FAIL (in-window)

| Action | Copy |
|--------|------|
| Export, disk/permission | FAIL — recovery key was not written. Next: pick another path; Retry. Do not assume you are safe. |
| Export, not joined | FAIL — recovery key was not written. No friendnet joined yet. |
| Import, wrong passphrase / corrupt | FAIL — could not import this recovery key. Wrong passphrase, corrupt file, or incompatible grid. |
| Import, introducer down | FAIL — could not join this friendnet. Introducer is unreachable. |

## Caveats (honest)

- **Wallet is a bearer copy.** A and B both hold the same tokens after restore; the
  storage spent-set rejects the second spend. Top up on the surviving device.
- Restored folders land under `~/Leasegrid/<name>`; wireframe 4f “choose a path per
  folder” is not built. `LEASEGRID_RESTORE_ROOT` overrides the root.
- The key file is as sensitive as the folders. Passphrase is optional per design;
  the UI shows a plaintext warning when it is empty.
- Needs the pinned `magic-folder` package importable next to Sync (`[sync,tahoe]`).
