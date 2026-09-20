#!/usr/bin/env bash
# Exit test for a frozen Leasegrid Sync build. Server side (gated dev grid) runs
# from the dev venv; the client side uses ONLY the bundle, with the venv scrubbed
# from PATH, so a system tahoe could not be hiding the bundle's failure.
#
#   packaging/exit-test.sh <needle> <client command...>
#
#   needle   substring the twistd banner in Sync's tahoe.log must contain, e.g.
#            "leasegrid-sync/tahoe" -- proves the *bundled* tahoe ran.
#   client   how to run the Sync CLI from the bundle, e.g.
#            dist/Leasegrid_Sync-0.1.0-x86_64.AppImage --appimage-extract-and-run
#            "dist/Leasegrid Sync.app/Contents/MacOS/leasegrid-sync"
#            dist/leasegrid-sync/leasegrid-sync-cli.exe
#
# Proves: --version; join by furl -> Connected; credit top-up + paid upload
# (tokens spent on every storage node); a second home joins by short invite code
# through the grid's local wormhole relay.
set -euo pipefail

NEEDLE="$1"; shift
CLIENT=("$@")
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

case "$(uname -s)" in
  Darwin) OS=macos ;;
  MINGW*|MSYS*|CYGWIN*) OS=windows ;;
  *) OS=linux ;;
esac

T="${RUNNER_TEMP:-/tmp}"
if [[ "$OS" == windows ]]; then
  T="$(cygpath -m "$T")"
  export MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*'
  VENV_BIN="$ROOT/.venv/Scripts"
else
  VENV_BIN="$ROOT/.venv/bin"
fi
T="$T/lg-exit"
rm -rf "$T"; mkdir -p "$T/home" "$T/sync" "$T/home2"

# Resolve the timeout tool now, before PATH is scrubbed for the client: on
# Windows a bare `timeout` would then hit System32's TIMEOUT.EXE; macOS ships no
# coreutils timeout(1) at all, and perl is everywhere.
if timeout --version >/dev/null 2>&1; then
  TIMEOUT_CMD=("$(command -v timeout)")
else
  TIMEOUT_CMD=(perl -e 'alarm shift; exec @ARGV')
fi
run_timeout() { # seconds, cmd...
  local s="$1"; shift
  "${TIMEOUT_CMD[@]}" "$s" "$@"
}

# Client env: nothing from the venv; only what a fresh desktop would have.
client() { # SYNC_HOME=<dir> [WORMHOLE=<url>] client args...
  local vars=(LEASEGRID_SYNC_HOME="$SYNC_HOME" LEASEGRID_ISSUER_URL=http://127.0.0.1:8700 QT_QPA_PLATFORM=offscreen)
  [[ -n "${WORMHOLE:-}" ]] && vars+=(LEASEGRID_WORMHOLE_SERVER="$WORMHOLE")
  if [[ "$OS" == windows ]]; then
    # env -i would drop SYSTEMROOT & co. that Windows executables need; scrub PATH instead.
    (export PATH="/c/Windows/System32:/c/Windows" "${vars[@]}"; run_timeout 300 "${CLIENT[@]}" "$@")
  else
    run_timeout 300 env -i HOME="$SYNC_HOME" PATH=/usr/bin:/bin USER=ci "${vars[@]}" "${CLIENT[@]}" "$@"
  fi
}

echo "==> grid (gated) from $VENV_BIN"
GRID_LOG="$T/grid.out"
export LEASEGRID_DEVGRID_DIR="$T/grid" LEASEGRID_GATED=1
PATH="$VENV_BIN:$PATH" scripts/dev-grid.sh > "$GRID_LOG" 2>&1 &
GRID_PID=$!
cleanup() { kill "$GRID_PID" 2>/dev/null || true; kill "${INVITE_PID:-}" 2>/dev/null || true; }
trap cleanup EXIT
for _ in $(seq 1 90); do grep -q "dev-grid up" "$GRID_LOG" && break; sleep 1; done
grep -q "dev-grid up" "$GRID_LOG" || { cat "$GRID_LOG"; exit 1; }
FURL="$(grep -o 'pb://[^ ]*' "$GRID_LOG" | head -1)"
RELAY="$(grep -o 'ws://127.0.0.1:[0-9]*/v1' "$GRID_LOG" | head -1)"
test -n "$FURL"; test -n "$RELAY"

echo "==> client --version"
SYNC_HOME="$T/home" client --version

echo "==> join by furl"
SYNC_HOME="$T/home" client --join "$FURL" | tee "$T/join.out"
grep -q "^Connected" "$T/join.out"

echo "==> credit top-up, then a paid upload"
SYNC_HOME="$T/home" client --dogfood-folder "$T/sync" --credit-dogfood --credit-tier medium | tee "$T/dogfood.out"
grep -q "^U2 credit-dogfood" "$T/dogfood.out"
grep -q "^U1 dogfood" "$T/dogfood.out"
grep -q "$NEEDLE" "$T/home/logs/tahoe.log" || { echo "tahoe.log lacks '$NEEDLE' (did a system tahoe run?)"; head -5 "$T/home/logs/tahoe.log"; exit 1; }
for p in 8711 8712 8713; do
  curl -fsS "http://127.0.0.1:$p/v0/info" | grep -q '"spent": [1-9]'
done
grep -q "Lease on" "$T/home/credit-recent.json"

echo "==> second home joins by short invite code via $RELAY"
PATH="$VENV_BIN:$PATH" scripts/dev-grid.sh --invite ci-code > "$T/invite.out" 2>&1 &
INVITE_PID=$!
for _ in $(seq 1 60); do grep -q "Invite Code" "$T/invite.out" && break; sleep 1; done
CODE="$(grep -o 'Invite Code for client: .*' "$T/invite.out" | awk '{print $NF}' | tr -d '\r')"
test -n "$CODE" || { cat "$T/invite.out"; exit 1; }
SYNC_HOME="$T/home2" WORMHOLE="$RELAY" client --join "$CODE" | tee "$T/join2.out"
grep -q "^Connected" "$T/join2.out"
grep -q "^nickname = ci-code" "$T/home2/tahoe/tahoe.cfg"
grep -q "^shares.needed = 2" "$T/home2/tahoe/tahoe.cfg"

echo "==> exit test PASS ($OS)"
