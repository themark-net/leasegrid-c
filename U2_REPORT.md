# U2 report — Credit panel ↔ lab issuer/faucet

**Status:** PASS (nimo lab, 2026-09-19)  
**Cite:** `docs/design/19-U2-DEVBOT-HANDOFF.md` · design 15–18 · `docs/09-ui-track.md` U2 · U0 `12` §3 Credit  
**Branch:** `feat/u2-credit-panel` · **Repo:** themark-net/leasegrid-c  
**HEAD:** `becbd12` (`feat/u2-credit-panel`)  
**Base:** `3452a87` (U1 SHIP)

Native **Leasegrid Sync** Credit place (PyQt wrap, same window as U1 Folders). Lab faucet redeem updates remaining GiB·share-months in plain language. Not Tahoe WUI. Not Electron. Not mainnet XMR. AppImage / recovery HITL / XMR wait for U3–U5.

## U2 exit checklist

| # | DoD | Result |
|---|-----|--------|
| 1 | Tip ≥ `3452a87`; U1 Folders/join/tray/no-WUI still PASS | **PASS** — branch from `3452a87`; Folders/join/tray tests green; `tests/test_sync_no_wui.py` |
| 2 | Credit primary place opens in Sync | **PASS** — tabs Folders / **Credit** / Recovery / Settings; screenshot `docs/ops/u2-credit.png` |
| 3 | Balance visible in plain language (incl. zero) | **PASS** — before faucet: `Credit remaining: none.`; after: `About 10 GiB kept for ~30 days on this friendnet` |
| 4 | Denomination / expansion honesty (no 1:1 upload lie) | **PASS** — Remaining card: prepaid share-capacity; shares expand; `1 credit ≈ 1 GiB-share × 30 days on one node` |
| 5 | Top up → lab faucet redeem succeeds in dogfood | **PASS** — `--credit-dogfood --credit-tier small` against `http://127.0.0.1:8700` |
| 6 | **Balance visible / updated after faucet** (exit) | **PASS** — before=0 after=10; `--credit-status` agrees; Recent `Faucet top-up +10 GiB·mo today` |
| 7 | Load FAIL + redeem FAIL in-window with Next + Retry | **PASS** — `tests/test_sync_credit.py` + `tests/test_sync_ui.py` |
| 8 | Folders insufficient credit → Open Credit | **PASS** — zero remaining blocks Add folder; **[ Open Credit ]** primary |
| 9 | No WUI CTA from Credit; no live XMR fields | **PASS** — Top up is faucet only; XMR later label; no address/amount fields |
| 10 | No opaque ZKAP convert | **PASS** — lab note + `reject_opaque_import`; foreign wallet JSON FAILs load |
| 11 | Tests | **PASS** — `pytest -q` 57 passed (offscreen) |
| 12 | Dogfood steps written for nimo | **PASS** — `docs/ops/u2-dogfood.md` |
| — | Deferred U3–U5 listed | **PASS** — below + Settings stub |

**Not FAIL:** Credit only in Settings; faucet no-op; fake balance; WUI; mainnet XMR; 1:1 upload=credit; Magic Folder regression.

## Evidence (nimo)

```
leasegrid-sync --status
Connected    introducer up · 3 storage    /home/mark/.tahoe

curl -sS http://127.0.0.1:8700/health
{"ok": true, "issuer-pubkey-id": "09e9633f194ba8bf2df91e69c0e497619a24ebd6a4fa7814406c836796995ab5"}

leasegrid-sync --credit-status
0    Credit remaining: none.

leasegrid-sync --credit-dogfood --credit-tier small --screenshot ~/Leasegrid/u2-credit.png
U2 credit-dogfood before=0 after=10 remaining=About 10 GiB kept for ~30 days on this friendnet

leasegrid-sync --credit-status
10    About 10 GiB kept for ~30 days on this friendnet
```

Screenshot (copied to git): [`docs/ops/u2-credit.png`](docs/ops/u2-credit.png) — Credit place selected, Remaining **About 10 GiB kept for ~30 days**, denomination note, Top-up complete, Recent faucet row, chip **Connected introducer up · 3 storage**.

Issuer: existing nimo lab issuer (gate 0b pubkey id `09e9633f…`). Wallet: `$LEASEGRID_SYNC_HOME/credit-wallet.json` (off git). Friendnet identity = this issuer’s pubkey id.

## Stack

Same U1 wrap (PyQt + Magic Folder). CreditCtl calls `leasegrid_zkap.client.faucet_mint` → `POST /v0/issue`. No Gridsync PrivateStorage vouchers. **Did not switch to WUI.**

## Deferred to U3–U5

| Item | Slice |
|------|-------|
| Linux AppImage / `.deb` installer polish | **U3** |
| Recovery key export HITL | **U4** |
| XMR top-up replacing faucet | **U5** (after gate 0c) |
| Chrome balance chip | Optional — not exit |
| Brand-final names | provisional **Leasegrid Sync** |
| macOS / Windows | after Linux dogfood |

## How to launch on nimo

`docs/ops/u2-dogfood.md`. Short:

```bash
cd ~/DEVELOP/leasegrid-c
export LEASEGRID_TAHOE_NODEDIR="$HOME/.tahoe"
export LEASEGRID_ISSUER_URL="http://127.0.0.1:8700"
.venv-sync/bin/python -m leasegrid_sync
# Credit → Top up → Request faucet credit
```

## CI

- `scripts/ci-local.sh` — ruff + pytest; `QT_QPA_PLATFORM=offscreen`; `[sync]` extra
- `.github/workflows/ci.yml` — `.[dev,sync]` + offscreen pytest; push `feat/**` + PRs

## Paths

- `src/leasegrid_sync/credit.py` — balance + faucet
- `src/leasegrid_sync/app.py` — Credit place, Top up dialog, Folders bridge
- `docs/design/15–19` + `docs/09-ui-track-U2-POINTER.md` — U2 design package
- `docs/ops/u2-dogfood.md` — nimo steps
