#!/usr/bin/env bash
# Print PASS/FAIL for gate 0c.1–0c.5. Default intake is SIMULATED (no chain).
# Never uses nimo mainnet monerod :18081/:18083.
set -euo pipefail

usage() {
  cat <<'EOF'
usage: check-0c.sh [--live --issuer URL --storage URL] [--venv DIR]

Default: in-process local harness (SIMULATED XMR intake).
EOF
}

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
VENV="${ROOT}/.venv"
LIVE=0
ISSUER=""
STORAGE=""
NODEID=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --live) LIVE=1; shift ;;
    --issuer) ISSUER="$2"; shift 2 ;;
    --storage) STORAGE="$2"; shift 2 ;;
    --nodeid) NODEID="$2"; shift 2 ;;
    --venv) VENV="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown arg: $1" >&2; usage; exit 2 ;;
  esac
done

if [[ -x "${VENV}/bin/leasegrid-zkap" ]]; then
  BIN="${VENV}/bin/leasegrid-zkap"
elif command -v leasegrid-zkap >/dev/null 2>&1; then
  BIN="$(command -v leasegrid-zkap)"
else
  echo "FAIL  install leasegrid-zkap (pip install -e .) first" >&2
  exit 1
fi

if [[ "$LIVE" -eq 1 ]]; then
  exec "$BIN" check-0c --live --issuer "$ISSUER" --storage "$STORAGE" ${NODEID:+--nodeid "$NODEID"}
fi
exec "$BIN" check-0c
