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
# PyQt5 extra: required on GHA (3.12). Local tahoe-venv may be 3.14 without wheels.
if "$PYTHON" -m pip install -q -e ".[sync]"; then
  echo "==> sync extra installed"
else
  echo "==> sync extra skipped (PyQt5 wheels missing; UI tests will skip)"
fi
# Tahoe 1.20 + Magic Folder + pins; on nimo's 3.14 tahoe-venv this may not resolve.
if "$PYTHON" -m pip install -q -e ".[tahoe]"; then
  echo "==> tahoe extra installed"
else
  echo "==> tahoe extra skipped (check-0b local test will skip)"
fi
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-offscreen}"
"$PYTHON" -m ruff check src tests scripts --select E4,E7,E9,F
"$PYTHON" -m pytest -q
echo "==> ci-local PASS"
