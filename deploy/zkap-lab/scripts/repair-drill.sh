#!/usr/bin/env bash
# Gate 0d repair drill: silent eject a nodeid, reconstruct onto remaining
# live nodes, stop paying the dead one. No slash, no PoRep, no bond.
#
# Usage:
#   repair-drill.sh --nodeid NODE [--url SPEND_URL] [--eject-set PATH] \
#                   [--tahoe-dir DIR] [--cap CAP] [--before N] [--after N]
set -euo pipefail

NODEID=""
URL=""
EJECT_SET="${LEASEGRID_EJECT_SET:-$HOME/DEVELOP/leasegrid-lab-private/ejected.json}"
TAHOE_DIR=""
CAP=""
BEFORE="0"
AFTER="0"

while [ $# -gt 0 ]; do
  case "$1" in
    --nodeid) NODEID="$2"; shift 2 ;;
    --url) URL="$2"; shift 2 ;;
    --eject-set) EJECT_SET="$2"; shift 2 ;;
    --tahoe-dir) TAHOE_DIR="$2"; shift 2 ;;
    --cap) CAP="$2"; shift 2 ;;
    --before) BEFORE="$2"; shift 2 ;;
    --after) AFTER="$2"; shift 2 ;;
    -h|--help) grep '^#' "$0" | sed 's/^# \?//'; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

if [ -z "$NODEID" ]; then
  echo "need --nodeid" >&2
  exit 2
fi

if [ -n "$URL" ]; then
  leasegrid-zkap probe --nodeid "$NODEID" --url "$URL" --eject-set "$EJECT_SET" || true
else
  leasegrid-zkap eject --nodeid "$NODEID" --eject-set "$EJECT_SET" --reason probe
fi

echo "ejected $NODEID: stop paying this nodeid (no slash)"

args=(repair --eject-set "$EJECT_SET" --nodeid "$NODEID" --method reconstruct --before "$BEFORE" --after "$AFTER")
if [ -n "$TAHOE_DIR" ]; then
  args+=(--tahoe-dir "$TAHOE_DIR")
fi
if [ -n "$CAP" ]; then
  args+=(--cap "$CAP")
fi
exec leasegrid-zkap "${args[@]}"
