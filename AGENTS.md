# AGENTS.md — leasegrid-c (Leasegrid)

Thin router for coding agents. Full portable skill packs live in **pfy-mentat** only (`bootstrap/grok-cli/skills/`), not here.

## What this is

Monero-prepaid Tahoe-LAFS friendnet with bearer storage credits (ZKAPs). Product UI is **Leasegrid Sync** (native), not Tahoe WUI. Spec + lab + Sync under one repo (`leasegrid-c` slug; product name Leasegrid).

## Mandatory reads (before non-trivial work)

1. [docs/00-decision.md](docs/00-decision.md) — what this is / is not  
2. [docs/03-roadmap.md](docs/03-roadmap.md) — build order  
3. [docs/09-ui-track.md](docs/09-ui-track.md) — Sync UI sequencing  
4. [docs/design/README.md](docs/design/README.md) — design packs (wireframes / DoD / DevBot handoffs)  
5. [docs/adr/](docs/adr/) — decisions that touch your area  
6. [docs/PENDING-HANDOFF.md](docs/PENDING-HANDOFF.md) — if present: freeze / open issues / tip (harness takeover)

Also as needed: `docs/01-architecture.md`, `docs/07-payment.md`, `docs/08-lab.md`, `docs/ops/`.

## Process

| Situation | Action |
|-----------|--------|
| Architecture / hard-to-reverse choice | ADR under `docs/adr/` |
| UI / UX slice | Design pack under `docs/design/` → then implement |
| End of any slice (Design, implement, pause, ship) | Update or add `docs/PENDING-HANDOFF.md` (in-repo handoff required) |
| Lab gate PASS/FAIL | Dated row in `docs/08-lab.md` |

## Do not

- Ship Tahoe WUI as the product UI  
- Add PoRep / PoSt / protocol-level slashing or a new L1  
- Put caps, storage indexes, or spent tokens on-chain  
- Charge for reads in v0  
- Commit secrets, keys, or mainnet wallet material  
- Scaffold pfy-style portable skill trees into this repo  
- Auto-start work listed as HOLD / frozen in PENDING-HANDOFF or open-issue posture  

## Dogfood / local

```bash
python3 -m venv .venv && .venv/bin/pip install -U pip && .venv/bin/pip install -e ".[sync,tahoe]"
scripts/dev-grid.sh
LEASEGRID_ISSUER_URL=http://127.0.0.1:8700 .venv/bin/leasegrid-sync
```

See [docs/ops/dev-grid.md](docs/ops/dev-grid.md) and [docs/ops/p1-dogfood.md](docs/ops/p1-dogfood.md). Tip SHA and open issues: prefer `docs/PENDING-HANDOFF.md` when present.

## Open work source of truth

GitHub issues on this repo. Design DoDs under `docs/design/`. Do not invent a second backlog outside issues + docs.
