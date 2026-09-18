#!/usr/bin/env bash
# Install leasegrid-zkap-lab into a Tahoe venv (offline wheels optional).
set -euo pipefail

usage() {
  cat <<'EOF'
usage: install-lab.sh [--venv DIR] [--wheels DIR] [--copy-dropin]

Installs this repo editable into the Tahoe virtualenv and python-challenge-bypass-ristretto.
VMs without PyPI DNS: pass --wheels ~/DEVELOP/leasegrid-lab-private/wheels
--copy-dropin copies twisted/plugins/leasegrid_zkap_dropin.py into the venv.
EOF
}

VENV="${HOME}/tahoe-venv"
WHEELS=""
COPY_DROPIN=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --venv) VENV="$2"; shift 2 ;;
    --wheels) WHEELS="$2"; shift 2 ;;
    --copy-dropin) COPY_DROPIN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown arg: $1" >&2; usage; exit 2 ;;
  esac
done

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
PY="${VENV}/bin/python"
PIP="${VENV}/bin/pip"
if [[ ! -x "$PY" ]]; then
  echo "missing $PY" >&2
  exit 1
fi

if [[ -n "$WHEELS" ]]; then
  "$PIP" install --no-index --find-links "$WHEELS" python-challenge-bypass-ristretto
else
  "$PIP" install python-challenge-bypass-ristretto==2022.6.30
fi
"$PIP" install -e "$ROOT"

if [[ "$COPY_DROPIN" -eq 1 ]]; then
  DEST="$("$PY" -c 'import twisted.plugins, os; print(os.path.dirname(twisted.plugins.__file__))')"
  cp "$ROOT/twisted/plugins/leasegrid_zkap_dropin.py" "$DEST/"
  rm -f "$DEST/dropin.cache"
  echo "dropin -> $DEST/leasegrid_zkap_dropin.py"
fi

"$PY" -c "import leasegrid_zkap, challenge_bypass_ristretto; print('ok', leasegrid_zkap.__version__)"
echo "install-lab done"
