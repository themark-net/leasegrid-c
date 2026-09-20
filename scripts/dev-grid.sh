#!/usr/bin/env bash
# Local Leasegrid server side on 127.0.0.1: Tahoe introducer + N storage nodes +
# lab ZKAP issuer/faucet. Runs in the foreground (Ctrl-C stops everything),
# prints the invite furl and the env the Sync client needs.
#
#   scripts/dev-grid.sh            # start (reuses state in $LEASEGRID_DEVGRID_DIR)
#   scripts/dev-grid.sh --reset    # wipe state, then start
#   scripts/dev-grid.sh --furl     # print the invite furl of a running grid and exit
#   LEASEGRID_GATED=1 scripts/dev-grid.sh   # storage refuses unpaid leases (ZKAP plugin)
#
# This is the lab "server". With LEASEGRID_GATED=1 every storage node runs the
# leasegrid-zkap-v0 plugin: uploads need a token per (node, storage index) and
# the Sync client pays from its Credit wallet. Without it storage is free.
# The client side is `leasegrid-sync`.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIR="${LEASEGRID_DEVGRID_DIR:-$HOME/.local/share/leasegrid-devgrid}"
STORAGE_COUNT="${LEASEGRID_DEVGRID_STORAGE:-3}"
INTRO_PORT="${LEASEGRID_DEVGRID_INTRO_PORT:-45001}"
STORAGE_PORT_BASE="${LEASEGRID_DEVGRID_STORAGE_PORT_BASE:-45010}"
ISSUER_LISTEN="${LEASEGRID_DEVGRID_ISSUER_LISTEN:-127.0.0.1:8700}"
GATED="${LEASEGRID_GATED:-0}"
SPEND_PORT_BASE="${LEASEGRID_DEVGRID_SPEND_PORT_BASE:-8710}"

if [[ -x "$ROOT/.venv/bin/tahoe" ]]; then
  export PATH="$ROOT/.venv/bin:$PATH"
fi

FURL_FILE="$DIR/intro/private/introducer.furl"

if [[ "${1:-}" == "--furl" ]]; then
  if [[ -s "$FURL_FILE" ]]; then cat "$FURL_FILE"; exit 0; fi
  echo "dev-grid: no introducer furl at $FURL_FILE (is the grid running?)" >&2
  exit 1
fi

for bin in tahoe leasegrid-zkap; do
  if ! command -v "$bin" >/dev/null 2>&1; then
    echo "dev-grid: '$bin' not on PATH. Install with: pip install -e '.[sync,tahoe]'" >&2
    exit 1
  fi
done

if [[ "${1:-}" == "--reset" ]]; then
  rm -rf "$DIR"
fi
mkdir -p "$DIR/logs" "$DIR/private"

PIDS=()
cleanup() {
  echo
  echo "dev-grid: stopping"
  for pid in "${PIDS[@]:-}"; do
    [[ -n "$pid" ]] && kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

run_bg() { # name, cmd...
  local name="$1"; shift
  "$@" </dev/null >"$DIR/logs/$name.log" 2>&1 &
  PIDS+=("$!")
}
# `tahoe run` exits when stdin closes unless told otherwise; we stop it via the trap instead.
run_tahoe() { # name, nodedir
  run_bg "$1" tahoe run --allow-stdin-close "$2"
}

# Introducer
if [[ ! -f "$DIR/intro/tahoe.cfg" ]]; then
  tahoe create-introducer \
    --port "tcp:$INTRO_PORT:interface=127.0.0.1" \
    --location "tcp:127.0.0.1:$INTRO_PORT" \
    "$DIR/intro" >/dev/null
fi
run_tahoe intro "$DIR/intro"
for _ in $(seq 1 30); do [[ -s "$FURL_FILE" ]] && break; sleep 1; done
if [[ ! -s "$FURL_FILE" ]]; then
  echo "dev-grid: introducer did not publish a furl; see $DIR/logs/intro.log" >&2
  exit 1
fi
FURL="$(cat "$FURL_FILE")"

# Issuer key first: gated storage nodes verify passes with it.
KEY="$DIR/private/issuer.signing.key"
if [[ ! -f "$KEY" ]]; then
  leasegrid-zkap keygen --key-file "$KEY" >/dev/null
fi

# Storage nodes (no web UI; they are servers, not the product)
gate_storage_cfg() { # nodedir, spend-port
  local nodedir="$1" sport="$2" cfg="$1/tahoe.cfg"
  grep -q "storageserver.plugins.leasegrid-zkap-v0" "$cfg" && return 0
  # `[storage]` exists in Tahoe's template; plugin lines go right after it.
  # force_foolscap: Tahoe 1.20 clients take GBS/HTTP whenever it is announced and
  # HTTP never consults storage plugins, so a gated node must not offer it.
  sed -i 's/^\[storage\]$/[storage]\nplugins = leasegrid-zkap-v0\nforce_foolscap = true/' "$cfg"
  {
    echo
    echo "[storageserver.plugins.leasegrid-zkap-v0]"
    echo "issuer-signing-key-file = $KEY"
    echo "spend-listen = tcp:$sport:interface=127.0.0.1"
    echo "spend-url = http://127.0.0.1:$sport"
    echo "spent-set-path = $nodedir/private/spent-set.json"
  } >> "$cfg"
}
for n in $(seq 1 "$STORAGE_COUNT"); do
  port=$((STORAGE_PORT_BASE + n))
  if [[ ! -f "$DIR/storage-$n/tahoe.cfg" ]]; then
    tahoe create-node \
      --introducer="$FURL" \
      --nickname="storage-$n" \
      --port "tcp:$port:interface=127.0.0.1" \
      --location "tcp:127.0.0.1:$port" \
      --webport none \
      "$DIR/storage-$n" >/dev/null
  fi
  if [[ "$GATED" == "1" ]]; then
    gate_storage_cfg "$DIR/storage-$n" $((SPEND_PORT_BASE + n))
  elif grep -q "storageserver.plugins.leasegrid-zkap-v0" "$DIR/storage-$n/tahoe.cfg"; then
    echo "dev-grid: storage-$n was created gated; run with LEASEGRID_GATED=1 or --reset" >&2
    exit 1
  fi
  run_tahoe "storage-$n" "$DIR/storage-$n"
done

# Issuer + faucet
run_bg issuer leasegrid-zkap issuer --key-file "$KEY" --listen "$ISSUER_LISTEN"
for _ in $(seq 1 20); do
  curl -fsS "http://$ISSUER_LISTEN/health" >/dev/null 2>&1 && break
  sleep 0.5
done

cat <<EOF

dev-grid up  (state: $DIR)
  introducer   tcp:127.0.0.1:$INTRO_PORT
  storage      $STORAGE_COUNT nodes on 127.0.0.1:$((STORAGE_PORT_BASE + 1)).. (webport none)
  paid leases  $(if [[ "$GATED" == "1" ]]; then echo "ON — spend HTTP 127.0.0.1:$((SPEND_PORT_BASE + 1)).. ; unpaid uploads refused"; else echo "off — LEASEGRID_GATED=1 to require credit"; fi)
  issuer       http://$ISSUER_LISTEN  (faucet /v0/issue)
  logs         $DIR/logs/

Invite furl (paste into Leasegrid Sync → Join friendnet):
$FURL

Client (new shell):
  export LEASEGRID_ISSUER_URL="http://$ISSUER_LISTEN"
  leasegrid-sync

Ctrl-C here stops the grid. State is kept; --reset wipes it.
EOF

wait
