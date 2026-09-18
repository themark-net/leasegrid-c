#!/usr/bin/env bash
# Local CI mirror for leasegrid-c (Gate 0b lab). Run before every Actions-triggering push.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-}"
if [[ -z "$PYTHON" ]]; then
  if [[ -x /home/mark/tahoe-venv/bin/python ]]; then
    PYTHON=/home/mark/tahoe-venv/bin/python
  elif [[ -x .venv/bin/python ]]; then
    PYTHON=.venv/bin/python
  else
    PYTHON=python3
  fi
fi

echo "==> using $PYTHON"
"$PYTHON" -m pip install -q -e ".[dev]"
"$PYTHON" -m ruff check src tests scripts --select E4,E7,E9,F
"$PYTHON" -m pytest -q
echo "==> ci-local PASS"
