# AGENTS.md — leasegrid-c

Leasegrid client/operator (device leasing / grid control plane).

## Mandatory reads

1. [README.md](README.md)
2. [docs/](docs/) — design, ops, and module docs

## Testing standing rule
Prefer the Testing Trophy: mostly integration/E2E for product confidence. Unit tests only for shaky/non-obvious behavior. Forbidden: tautological tests and implementation-detail tests. Prefer sociable tests; doubles only at awkward boundaries + contract tests for externals. Every non-trivial change: How could this fail? How do we recover?

No tautological or implementation-detail unit sprawl as Done.

## Verify / dogfood

```bash
bash scripts/ci-local.sh
# optional local grid dogfood:
# bash scripts/dev-grid.sh
```
