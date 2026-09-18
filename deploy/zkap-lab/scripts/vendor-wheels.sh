#!/usr/bin/env bash
# Download wheels on a host that can reach PyPI (nimo) for offline VM install.
set -euo pipefail

usage() {
  cat <<'EOF'
usage: vendor-wheels.sh [DEST]

DEST defaults to ~/DEVELOP/leasegrid-lab-private/wheels
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

DEST="${1:-$HOME/DEVELOP/leasegrid-lab-private/wheels}"
mkdir -p "$DEST"
python3 -m pip download -d "$DEST" \
  python-challenge-bypass-ristretto==2022.6.30 \
  "cryptography==41.0.7" \
  "pyOpenSSL==23.3.0" \
  "service-identity==23.1.0" \
  || python3 -m pip download -d "$DEST" python-challenge-bypass-ristretto==2022.6.30

echo "wheels in $DEST"
ls -1 "$DEST"
