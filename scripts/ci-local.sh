#!/usr/bin/env bash
# Local CI mirror for leasegrid-c (Gate 0b lab). Run before every Actions-triggering push.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Absolute form of a git dir. `git rev-parse` may print a path relative to ROOT.
_abs_dir() {
  local p="$1"
  if [[ "$p" != /* ]]; then
    p="$ROOT/$p"
  fi
  if [[ -d "$p" ]]; then
    (cd "$p" && pwd -P)
  else
    printf '%s\n' "$p"
  fi
}

# A linked worktree's git dir is not the common git dir. `pip install -e .`
# from there must not retarget a shared venv at this tree.
_linked_worktree() {
  local git_dir common_dir
  git_dir="$(git rev-parse --git-dir 2>/dev/null || true)"
  common_dir="$(git rev-parse --git-common-dir 2>/dev/null || true)"
  if [[ -z "$git_dir" || -z "$common_dir" ]]; then
    return 1
  fi
  git_dir="$(_abs_dir "$git_dir")"
  common_dir="$(_abs_dir "$common_dir")"
  [[ "$git_dir" != "$common_dir" ]]
}

PYTHON="${PYTHON:-}"
PYTHON_REASON=""
if [[ -n "$PYTHON" ]]; then
  PYTHON_REASON="explicit PYTHON"
elif _linked_worktree; then
  if [[ ! -x "$ROOT/.venv/bin/python" ]]; then
    python3 -m venv "$ROOT/.venv"
  fi
  PYTHON="$ROOT/.venv/bin/python"
  PYTHON_REASON="linked worktree; using this tree's .venv"
elif [[ -x /home/mark/tahoe-venv/bin/python ]]; then
  PYTHON=/home/mark/tahoe-venv/bin/python
  PYTHON_REASON="main checkout"
elif [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
  PYTHON_REASON="main checkout .venv"
else
  PYTHON=python3
  PYTHON_REASON="main checkout python3"
fi

# Tests pass CI_LOCAL_PRINT_PYTHON=1 so they can read the choice without installing.
if [[ "${CI_LOCAL_PRINT_PYTHON:-}" == "1" ]]; then
  printf '%s\n' "$PYTHON"
  exit 0
fi

echo "==> using $PYTHON ($PYTHON_REASON)"
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
