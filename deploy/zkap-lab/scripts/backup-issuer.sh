#!/usr/bin/env bash
# Nightly-shaped copy of the issuer SQLite file (and optional key material).
# View key + signing key stay off git; this script just copies what you point at.
set -euo pipefail

usage() {
  cat <<'EOF'
usage: backup-issuer.sh --db PATH --out-dir DIR [--view-key PATH] [--signing-key PATH] [--venv DIR]
EOF
}

DB=""
OUT=""
VIEW=""
SIGN=""
VENV=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --db) DB="$2"; shift 2 ;;
    --out-dir) OUT="$2"; shift 2 ;;
    --view-key) VIEW="$2"; shift 2 ;;
    --signing-key) SIGN="$2"; shift 2 ;;
    --venv) VENV="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

[[ -n "$DB" && -n "$OUT" ]] || { usage >&2; exit 2; }
mkdir -p "$OUT"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DEST="$OUT/issuer-$STAMP.sqlite"

if [[ -n "$VENV" ]]; then
  PY="${VENV}/bin/python"
else
  PY="$(command -v python3)"
fi

"$PY" - "$DB" "$DEST" <<'PY'
import sys
from leasegrid_zkap.payment.backup import backup_sqlite
backup_sqlite(sys.argv[1], sys.argv[2])
print(sys.argv[2])
PY

if [[ -n "$VIEW" ]]; then
  cp -p "$VIEW" "$OUT/view-key-$STAMP"
fi
if [[ -n "$SIGN" ]]; then
  cp -p "$SIGN" "$OUT/signing-key-$STAMP"
fi
