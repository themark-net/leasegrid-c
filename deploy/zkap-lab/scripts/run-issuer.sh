#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
usage: run-issuer.sh [--listen HOST:PORT] [--key-file PATH] [--venv DIR]
                     [--intake simulated|rpc] [--xmr-rpc URL]

Default intake is simulated (no chain). --xmr-rpc to :18081/:18083 is refused.
EOF
}

LISTEN="127.0.0.1:8700"
KEY="${LEASEGRID_ISSUER_KEY:-$HOME/DEVELOP/leasegrid-lab-private/issuer.signing.key}"
VENV=""
INTAKE="simulated"
XMR_RPC=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --listen) LISTEN="$2"; shift 2 ;;
    --key-file) KEY="$2"; shift 2 ;;
    --venv) VENV="$2"; shift 2 ;;
    --intake) INTAKE="$2"; shift 2 ;;
    --xmr-rpc) XMR_RPC="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

if [[ -n "$VENV" ]]; then
  BIN="${VENV}/bin/leasegrid-zkap"
else
  BIN="$(command -v leasegrid-zkap || true)"
  [[ -n "$BIN" ]] || BIN="$(cd "$(dirname "$0")/../../.." && pwd)/.venv/bin/leasegrid-zkap"
fi
EXTRA=()
if [[ -n "$XMR_RPC" ]]; then
  EXTRA+=(--xmr-rpc "$XMR_RPC")
fi
exec "$BIN" issuer --key-file "$KEY" --listen "$LISTEN" --intake "$INTAKE" "${EXTRA[@]}"
