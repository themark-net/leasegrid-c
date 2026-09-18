#!/usr/bin/env bash
# Print PASS/FAIL for gate 0b.1–0b.5. No stub success.
set -euo pipefail

usage() {
  cat <<'EOF'
usage: check-0b.sh [--live --issuer URL --storage URL] [--venv DIR]

Default: in-process local harness (starts issuer + gate on 127.0.0.1).
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
  exec "$BIN" check-0b --live --issuer "$ISSUER" --storage "$STORAGE" ${NODEID:+--nodeid "$NODEID"}
fi
exec "$BIN" check-0b
