#!/usr/bin/env bash
# Local Leasegrid server side on 127.0.0.1: Tahoe introducer + N storage nodes +
# ZKAP issuer (faucet + fake-chain XMR flow). Runs in the foreground (Ctrl-C stops everything),
# prints the invite furl and the env the Sync client needs.
#
#   scripts/dev-grid.sh            # start (reuses state in $LEASEGRID_DEVGRID_DIR)
#   scripts/dev-grid.sh --reset    # wipe state, then start
#   scripts/dev-grid.sh --chain fake|none   # payment detector (default: fake)
#   scripts/dev-grid.sh --furl     # print the invite furl of a running grid and exit
#   scripts/dev-grid.sh --invite [NICK]   # (grid running, other shell) print a one-time
#                                         # short invite code and wait for the joiner
#   LEASEGRID_GATED=1 scripts/dev-grid.sh   # storage refuses unpaid leases (ZKAP plugin)
#
# This is the lab "server". With LEASEGRID_GATED=1 every storage node runs the
# leasegrid-zkap-v0 plugin: uploads need a token per (node, storage index) and
# the Sync client pays from its Credit wallet. Without it storage is free.
# The client side is `leasegrid-sync`.
#
# Invites: the furl always works. `--invite` additionally hands out a short
# magic-wormhole code (`tahoe invite`); the grid runs its own mailbox relay on
# 127.0.0.1 when magic-wormhole-mailbox-server is installed (pip extra [tahoe]),
# otherwise codes go through Tahoe's public relay. LEASEGRID_DEVGRID_WORMHOLE=public
# forces the public relay.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIR="${LEASEGRID_DEVGRID_DIR:-$HOME/.local/share/leasegrid-devgrid}"
STORAGE_COUNT="${LEASEGRID_DEVGRID_STORAGE:-3}"
INTRO_PORT="${LEASEGRID_DEVGRID_INTRO_PORT:-45001}"
STORAGE_PORT_BASE="${LEASEGRID_DEVGRID_STORAGE_PORT_BASE:-45010}"
ISSUER_LISTEN="${LEASEGRID_DEVGRID_ISSUER_LISTEN:-127.0.0.1:8700}"
GATED="${LEASEGRID_GATED:-0}"
SPEND_PORT_BASE="${LEASEGRID_DEVGRID_SPEND_PORT_BASE:-8710}"
WORMHOLE_MODE="${LEASEGRID_DEVGRID_WORMHOLE:-auto}"   # auto | local | public
WORMHOLE_PORT="${LEASEGRID_DEVGRID_WORMHOLE_PORT:-45040}"
# Encoding a `--invite` hands to the joiner; same default as a Sync-created client.
SHARES="${LEASEGRID_SHARES:-2,3,3}"

if [[ -x "$ROOT/.venv/bin/tahoe" ]]; then
  export PATH="$ROOT/.venv/bin:$PATH"
elif [[ -x "$ROOT/.venv/Scripts/tahoe.exe" ]]; then
  export PATH="$ROOT/.venv/Scripts:$PATH"
fi
case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*)
    # Git Bash: hand Python C:/-style paths and stop MSYS rewriting furls/endpoints.
    mkdir -p "$DIR"
    DIR="$(cygpath -m "$DIR")"
    export MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*'
    ;;
esac
PY=python; command -v python >/dev/null 2>&1 || PY=python3

FURL_FILE="$DIR/intro/private/introducer.furl"
RELAY_FILE="$DIR/private/wormhole.url"   # present only while a local relay runs

if [[ "${1:-}" == "--furl" ]]; then
  if [[ -s "$FURL_FILE" ]]; then cat "$FURL_FILE"; exit 0; fi
  echo "dev-grid: no introducer furl at $FURL_FILE (is the grid running?)" >&2
  exit 1
fi

if [[ "${1:-}" == "--invite" ]]; then
  # Inviter = storage-1: it knows the introducer. `tahoe invite` sits on the relay
  # until exactly one joiner pastes the code (Sync → Join, or `leasegrid-sync --join CODE`).
  NICK="${2:-leasegrid-sync}"
  if [[ ! -s "$FURL_FILE" || ! -f "$DIR/storage-1/tahoe.cfg" ]]; then
    echo "dev-grid: grid is not running (no $FURL_FILE); start scripts/dev-grid.sh first" >&2
    exit 1
  fi
  IFS=, read -r NEEDED HAPPY TOTAL <<<"$SHARES"
  RELAY_ARGS=()
  RELAY=""
  if [[ -s "$RELAY_FILE" ]]; then
    RELAY="$(cat "$RELAY_FILE")"
    RELAY_ARGS=(--wormhole-server "$RELAY")
  fi
  echo "dev-grid: inviting '$NICK' with encoding $NEEDED/$HAPPY/$TOTAL via ${RELAY:-the public Tahoe relay}"
  if [[ -n "$RELAY" ]]; then
    echo "dev-grid: the joiner must use the same relay:  export LEASEGRID_WORMHOLE_SERVER=\"$RELAY\""
  fi
  echo "dev-grid: paste the code below into Leasegrid Sync → Join; keep this running until they join."
  echo
  exec env PYTHONUNBUFFERED=1 tahoe ${RELAY_ARGS[@]+"${RELAY_ARGS[@]}"} -d "$DIR/storage-1" invite \
    --shares-needed="$NEEDED" --shares-happy="$HAPPY" --shares-total="$TOTAL" "$NICK"
fi

for bin in tahoe leasegrid-zkap; do
  if ! command -v "$bin" >/dev/null 2>&1; then
    echo "dev-grid: '$bin' not on PATH. Install with: pip install -e '.[sync,tahoe]'" >&2
    exit 1
  fi
done

CHAIN="${LEASEGRID_DEVGRID_CHAIN:-fake}"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --reset)
      rm -rf "$DIR"
      shift
      ;;
    --chain)
      CHAIN="${2:-}"
      shift 2 || true
      ;;
    --chain=*)
      CHAIN="${1#--chain=}"
      shift
      ;;
    *)
      echo "dev-grid: unknown argument: $1 (try --reset, --chain fake|none, --furl, --invite)" >&2
      exit 1
      ;;
  esac
done
if [[ "$CHAIN" != "fake" && "$CHAIN" != "none" ]]; then
  echo "dev-grid: --chain must be fake or none (got '$CHAIN')" >&2
  exit 1
fi
mkdir -p "$DIR/logs" "$DIR/private"

# A stale grid (or anything else) on our ports would make this one look up while
# the client actually talks to the other issuer/relay. Refuse instead of guessing.
port_busy() { "$PY" -c 'import socket,sys; s=socket.socket(); s.settimeout(0.3); sys.exit(0 if s.connect_ex(("127.0.0.1",int(sys.argv[1])))==0 else 1)' "$1"; }
for p in "$INTRO_PORT" "${ISSUER_LISTEN##*:}" "$WORMHOLE_PORT" "$((STORAGE_PORT_BASE + 1))"; do
  if port_busy "$p"; then
    echo "dev-grid: 127.0.0.1:$p is already in use (another dev-grid still running?). Stop it or change LEASEGRID_DEVGRID_*_PORT." >&2
    exit 1
  fi
done

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
  # (Python, not sed -i: BSD sed on macOS has no \n in replacements.)
  "$PY" - "$cfg" "$KEY" "$sport" "$nodedir" <<'PY'
import sys
cfg, key, sport, nodedir = sys.argv[1:]
text = open(cfg, encoding="utf-8").read()
text = text.replace("[storage]\n", "[storage]\nplugins = leasegrid-zkap-v0\nforce_foolscap = true\n", 1)
text += (
    "\n[storageserver.plugins.leasegrid-zkap-v0]\n"
    f"issuer-signing-key-file = {key}\n"
    f"spend-listen = tcp:{sport}:interface=127.0.0.1\n"
    f"spend-url = http://127.0.0.1:{sport}\n"
    f"spent-set-path = {nodedir}/private/spent-set.json\n"
)
open(cfg, "w", encoding="utf-8").write(text)
PY
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

# Issuer: faucet on (lab), payment chain from --chain / LEASEGRID_DEVGRID_CHAIN
# (fake = quote → /v0/fake/pay → redeem; none = quotes 503).
run_bg issuer leasegrid-zkap issuer --key-file "$KEY" --listen "$ISSUER_LISTEN" \
  --faucet --chain "$CHAIN" --db "$DIR/private/issuer-vouchers.sqlite" --poll-interval 1
for _ in $(seq 1 20); do
  curl -fsS "http://$ISSUER_LISTEN/health" >/dev/null 2>&1 && break
  sleep 0.5
done

# Magic-wormhole mailbox relay for short invite codes (`--invite`). Local keeps
# the lab offline and deterministic; public is Tahoe's ws://wormhole.tahoe-lafs.org.
rm -f "$RELAY_FILE"
RELAY_NOTE="public relay (Tahoe's); LEASEGRID_DEVGRID_WORMHOLE=local needs magic-wormhole-mailbox-server"
if [[ "$WORMHOLE_MODE" != "public" ]]; then
  if "$PY" -c "import wormhole_mailbox_server" >/dev/null 2>&1; then
    RELAY="ws://127.0.0.1:$WORMHOLE_PORT/v1"
    run_bg wormhole twist wormhole-mailbox \
      --port "tcp:$WORMHOLE_PORT:interface=127.0.0.1" \
      --channel-db "$DIR/private/wormhole-relay.sqlite"
    for _ in $(seq 1 20); do
      "$PY" - "$WORMHOLE_PORT" <<'PY' && break
import socket, sys
s = socket.socket(); s.settimeout(0.5)
sys.exit(0 if s.connect_ex(("127.0.0.1", int(sys.argv[1]))) == 0 else 1)
PY
      sleep 0.5
    done
    echo "$RELAY" > "$RELAY_FILE"
    RELAY_NOTE="local $RELAY"
  elif [[ "$WORMHOLE_MODE" == "local" ]]; then
    echo "dev-grid: LEASEGRID_DEVGRID_WORMHOLE=local but magic-wormhole-mailbox-server is not installed" >&2
    exit 1
  fi
fi

cat <<EOF

dev-grid up  (state: $DIR)
  introducer   tcp:127.0.0.1:$INTRO_PORT
  storage      $STORAGE_COUNT nodes on 127.0.0.1:$((STORAGE_PORT_BASE + 1)).. (webport none)
  paid leases  $(if [[ "$GATED" == "1" ]]; then echo "ON — spend HTTP 127.0.0.1:$((SPEND_PORT_BASE + 1)).. ; unpaid uploads refused"; else echo "off — LEASEGRID_GATED=1 to require credit"; fi)
  issuer       http://$ISSUER_LISTEN  (faucet /v0/issue; XMR quote/redeem on chain=$CHAIN)
  invite codes $RELAY_NOTE
  logs         $DIR/logs/

Invite furl (paste into Leasegrid Sync → Join friendnet):
$FURL

Short invite code instead:  scripts/dev-grid.sh --invite   (other shell; one code per joiner)

Client (new shell):
  export LEASEGRID_ISSUER_URL="http://$ISSUER_LISTEN"$(if [[ -s "$RELAY_FILE" ]]; then printf '\n  export LEASEGRID_WORMHOLE_SERVER="%s"   # only for short codes' "$(cat "$RELAY_FILE")"; fi)
  leasegrid-sync

Ctrl-C here stops the grid. State is kept; --reset wipes it.
EOF

wait
