# U4 — Recovery-copy journey

**Status:** Design stub matching the U4 locks (nimo pack 30–34 was not on GitHub main)  
**Cite:** tip `4e1e6bd` (P0+P1 CrashPlan shell) · [`docs/10-post-fable-plan.md`](../10-post-fable-plan.md) · issue #15  
**Product:** Native Leasegrid Sync. Folders stay home. Recovery is how a lost device gets those folders back.

## Happy path

| Step | Place | Operator does | System does |
|------|-------|---------------|-------------|
| 0 | Folders | Already joined (P1). Offer pie is on this page. | Folder list is primary |
| 1 | More → Recovery | Reads the threat copy and checks the threat box | Export and Restore stay disabled until that ACK |
| 2 | Recovery | **Restore to Folders** (primary) and picks a recovery key | Import runs, or FAIL in the window |
| 3 | Folders | Sees the restored folder list | Lands on the Folders list, not a second app |

Export is the same place, after the same threat box, then both export checkboxes. The file is not written on one click.

A fresh device uses **Import recovery key instead…** on the join page. That opens the same threat box, then restore, then the Folders list.

## FAIL

| Action | Result |
|--------|--------|
| Export without threat ACK or either export ACK | FAIL. Nothing written |
| Import without threat ACK | FAIL. No restore |
| Bad passphrase, corrupt file, disk error | Existing recovery FAIL copy (message + Next) |
