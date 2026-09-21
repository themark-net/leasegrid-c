#!/usr/bin/env bash
# Restore-drill: copy a backup SQLite file over the live issuer db.
# Stop the issuer first. Subaddress indices in the restored file stay valid.
set -euo pipefail

usage() {
  cat <<'EOF'
usage: restore-issuer.sh --from PATH --db PATH [--force] [--venv DIR]
EOF
}

SRC=""
DB=""
FORCE=""
VENV=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --from) SRC="$2"; shift 2 ;;
    --db) DB="$2"; shift 2 ;;
    --force) FORCE="1"; shift ;;
    --venv) VENV="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

[[ -n "$SRC" && -n "$DB" ]] || { usage >&2; exit 2; }

if [[ -n "$VENV" ]]; then
  PY="${VENV}/bin/python"
else
  PY="$(command -v python3)"
fi

"$PY" - "$SRC" "$DB" "$FORCE" <<'PY'
import sys
from leasegrid_zkap.payment.backup import restore_sqlite
restore_sqlite(sys.argv[1], sys.argv[2], force=bool(sys.argv[3]))
print(sys.argv[2])
PY
