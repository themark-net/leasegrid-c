#!/usr/bin/env bash
# Append leasegrid-zkap-v0 plugin config to a storage node's tahoe.cfg.
# Does not restart tahoe. Does not print furls.
set -euo pipefail

usage() {
  cat <<'EOF'
usage: enable-storage-plugin.sh --node-dir DIR --key-file PATH --spend-listen HOST:PORT
       [--spent-set PATH] [--disable]

Idempotent: skips if [storageserver.plugins.leasegrid-zkap-v0] already exists.
--disable comments out plugins= and the plugin section (restore unpaid 0a).
EOF
}

NODE_DIR=""
KEY_FILE=""
SPEND=""
SPENT=""
DISABLE=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --node-dir) NODE_DIR="$2"; shift 2 ;;
    --key-file) KEY_FILE="$2"; shift 2 ;;
    --spend-listen) SPEND="$2"; shift 2 ;;
    --spent-set) SPENT="$2"; shift 2 ;;
    --disable) DISABLE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown arg: $1" >&2; usage; exit 2 ;;
  esac
done

if [[ -z "$NODE_DIR" ]]; then
  echo "--node-dir required" >&2
  exit 2
fi
CFG="${NODE_DIR}/tahoe.cfg"
if [[ ! -f "$CFG" ]]; then
  echo "missing $CFG" >&2
  exit 1
fi

if [[ "$DISABLE" -eq 1 ]]; then
  python3 - "$CFG" <<'PY'
import pathlib, sys
p = pathlib.Path(sys.argv[1])
text = p.read_text(encoding="utf-8")
text = text.replace("plugins = leasegrid-zkap-v0\n", "# plugins = leasegrid-zkap-v0  # disabled\n")
marker = "[storageserver.plugins.leasegrid-zkap-v0]"
if marker in text:
    pre, rest = text.split(marker, 1)
    # drop until next section or EOF
    lines = rest.splitlines(True)
    body = []
    started = False
    for ln in lines:
        if started and ln.startswith("["):
            body.append(ln)
            started = True
            # actually we skip plugin lines then keep from next [
            pass
    kept = []
    skip = True
    for ln in rest.splitlines(True):
        if skip:
            if ln.startswith("[") and not ln.startswith(marker):
                skip = False
                kept.append(ln)
            continue
        kept.append(ln)
    text = pre + "".join(kept)
p.write_text(text, encoding="utf-8")
print("disabled plugin in", p)
PY
  exit 0
fi

if [[ -z "$KEY_FILE" || -z "$SPEND" ]]; then
  echo "--key-file and --spend-listen required" >&2
  exit 2
fi
if [[ ! -f "$KEY_FILE" ]]; then
  echo "missing key file $KEY_FILE" >&2
  exit 1
fi
SPENT="${SPENT:-$NODE_DIR/private/leasegrid-spent.json}"
NODEID="$(tr -d '[:space:]' < "${NODE_DIR}/my_nodeid")"

if grep -q '\[storageserver.plugins.leasegrid-zkap-v0\]' "$CFG"; then
  echo "plugin section already present in $CFG"
  exit 0
fi

if grep -q '^\[storage\]' "$CFG"; then
  python3 - "$CFG" <<'PY'
import pathlib, sys
p = pathlib.Path(sys.argv[1])
lines = p.read_text(encoding="utf-8").splitlines(True)
out = []
in_storage = False
inserted = False
for ln in lines:
    if ln.startswith("[storage]"):
        in_storage = True
    elif ln.startswith("["):
        if in_storage and not inserted:
            out.append("plugins = leasegrid-zkap-v0\n")
            inserted = True
        in_storage = False
    out.append(ln)
if in_storage and not inserted:
    out.append("plugins = leasegrid-zkap-v0\n")
p.write_text("".join(out), encoding="utf-8")
PY
else
  printf '\n[storage]\nplugins = leasegrid-zkap-v0\n' >> "$CFG"
fi

cat >> "$CFG" <<EOF

[storageserver.plugins.leasegrid-zkap-v0]
issuer-signing-key-file = ${KEY_FILE}
spend-listen = ${SPEND}
spent-set-path = ${SPENT}
nodeid = ${NODEID}
EOF

echo "enabled leasegrid-zkap-v0 in $CFG (restart tahoe run to load)"
echo "nodeid ${NODEID}"
echo "spend-listen ${SPEND}"
