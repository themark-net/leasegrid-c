# U4 → implement handoff — recovery-copy

**Status:** Locks for implement. Canonical nimo `docs/design/` 30–34 was not on GitHub; this stub is the cite target.  
**Implement against:** tip `4e1e6bd` (P0+P1 SHIP) · [`docs/10-post-fable-plan.md`](../10-post-fable-plan.md) · this pack (30–33)  
**Stack:** extend `src/leasegrid_sync/`. No greenfield Electron.  
**Issue:** #15

## Must

1. **Threat HITL** before export or restore. The recovery-copy primary CTA is **Restore to Folders**, and success lands on the Folders list.
2. Preserve P1: folders-first, Offer disk pie, unpaid default, payment/XMR only when `LEASEGRID_GATED` (More → Credit / Settings lecture).
3. **Dual-ACK export.** CLI and window. No silent one-click dump. Missing ACK → FAIL, file not written.
4. **Import → Folders.** Join-page import and Recovery restore both return to the folder list.
5. Tip install operate-or-FAIL. CLI is enough. AppImage #12 stays deferred.
6. No Tahoe WUI as product. No mainnet XMR claims.
7. Tests cover the threat gate, the dual-ACK refuse, and restore landing on Folders.

## CLI

```
leasegrid-sync --export-recovery PATH --ack-threat --ack-loss --ack-store
leasegrid-sync --restore-recovery PATH --ack-threat
```

Env equivalents: `LEASEGRID_RECOVERY_ACK_THREAT`, `LEASEGRID_RECOVERY_ACK_LOSS`, `LEASEGRID_RECOVERY_ACK_STORE` set to `1`.
