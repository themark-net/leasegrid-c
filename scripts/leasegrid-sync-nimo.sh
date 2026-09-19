#!/usr/bin/env bash
# Launch Leasegrid Sync on nimo against the existing lab friendnet (~/.tahoe).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-}"
if [[ -z "$PYTHON" ]]; then
  if [[ -x "$ROOT/.venv-sync/bin/python" ]]; then
    PYTHON="$ROOT/.venv-sync/bin/python"
  else
    PYTHON="python3"
  fi
fi

export LEASEGRID_TAHOE_NODEDIR="${LEASEGRID_TAHOE_NODEDIR:-$HOME/.tahoe}"
if [[ -x /home/mark/tahoe-venv/bin/tahoe ]]; then
  export LEASEGRID_TAHOE_BIN="${LEASEGRID_TAHOE_BIN:-/home/mark/tahoe-venv/bin/tahoe}"
fi
if [[ -x "$ROOT/.venv-sync/bin/magic-folder" ]]; then
  export LEASEGRID_MAGIC_FOLDER_BIN="${LEASEGRID_MAGIC_FOLDER_BIN:-$ROOT/.venv-sync/bin/magic-folder}"
fi

exec "$PYTHON" -m leasegrid_sync "$@"
