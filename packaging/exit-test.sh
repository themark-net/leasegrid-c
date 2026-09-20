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
# Proves: --version; join by furl -> Connected; XMR quote → /v0/fake/pay →
# Credit collects → paid upload (tokens spent on every storage node); a second
# home joins by short invite code; a third home restores the recovery key and
# re-collects the XMR batch.
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
rm -rf "$T"; mkdir -p "$T/home" "$T/sync" "$T/home2" "$T/home3"

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
# stdout goes to a file, never a pipe: if the client is killed by the timeout
# while a child still holds the pipe, `| tee` would wait for EOF forever.
client() { # SYNC_HOME=<dir> [WORMHOLE=<url>] [PASSPHRASE=<pw>] OUT=<file> client args...
  local rc=0
  local vars=(LEASEGRID_SYNC_HOME="$SYNC_HOME" LEASEGRID_ISSUER_URL=http://127.0.0.1:8700 QT_QPA_PLATFORM=offscreen)
  [[ -n "${WORMHOLE:-}" ]] && vars+=(LEASEGRID_WORMHOLE_SERVER="$WORMHOLE")
  [[ -n "${PASSPHRASE:-}" ]] && vars+=(LEASEGRID_RECOVERY_PASSPHRASE="$PASSPHRASE")
  if [[ "$OS" == windows ]]; then
    # env -i would drop SYSTEMROOT & co. that Windows executables need; scrub PATH instead.
    (export PATH="/c/Windows/System32:/c/Windows" "${vars[@]}"; run_timeout 300 "${CLIENT[@]}" "$@") >"$OUT" || rc=$?
  else
    run_timeout 300 env -i HOME="$SYNC_HOME" PATH=/usr/bin:/bin USER=ci "${vars[@]}" "${CLIENT[@]}" "$@" >"$OUT" || rc=$?
  fi
  cat "$OUT"
  return "$rc"
}

echo "==> grid (gated) from $VENV_BIN"
GRID_LOG="$T/grid.out"
export LEASEGRID_DEVGRID_DIR="$T/grid" LEASEGRID_GATED=1
PATH="$VENV_BIN:$PATH" scripts/dev-grid.sh > "$GRID_LOG" 2>&1 &
GRID_PID=$!
cleanup() {
  kill "$GRID_PID" 2>/dev/null || true; kill "${INVITE_PID:-}" 2>/dev/null || true
  # A client killed by the timeout can leave its bundled daemons behind; on
  # Windows they are not in our process group, so name them.
  if [[ "$OS" == windows ]]; then
    taskkill /F /T /IM tahoe.exe /IM magic-folder.exe /IM leasegrid-sync-cli.exe >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT
for _ in $(seq 1 90); do grep -q "dev-grid up" "$GRID_LOG" && break; sleep 1; done
grep -q "dev-grid up" "$GRID_LOG" || { cat "$GRID_LOG"; exit 1; }
FURL="$(grep -o 'pb://[^ ]*' "$GRID_LOG" | head -1)"
RELAY="$(grep -o 'ws://127.0.0.1:[0-9]*/v1' "$GRID_LOG" | head -1)"
test -n "$FURL"; test -n "$RELAY"

echo "==> client --version"
SYNC_HOME="$T/home" OUT="$T/version.out" client --version

echo "==> join by furl"
SYNC_HOME="$T/home" OUT="$T/join.out" client --join "$FURL"
grep -q "^Connected" "$T/join.out"

if [[ "$OS" == windows ]]; then
  PY="$VENV_BIN/python.exe"
  ZKAP="$VENV_BIN/leasegrid-zkap.exe"
else
  PY="$VENV_BIN/python"
  ZKAP="$VENV_BIN/leasegrid-zkap"
fi

echo "==> XMR quote → fake pay → Credit collects"
WALLET="$T/home/credit-wallet.json"
"$ZKAP" topup --issuer http://127.0.0.1:8700 --wallet "$WALLET" --tokens 20 --json > "$T/quote.json"
"$PY" - "$T/quote.json" <<'PY'
import json, sys
from leasegrid_zkap.client import http_json
q = json.load(open(sys.argv[1], encoding="utf-8"))
http_json(
    "http://127.0.0.1:8700/v0/fake/pay",
    "POST",
    {"vid": q["vid"], "amount_piconero": q["amount_piconero"], "mine": 2},
)
print("paid", q["vid"], q["amount_piconero"])
PY
SYNC_HOME="$T/home" OUT="$T/credit.out" client --credit-status
grep -q "^20" "$T/credit.out"
grep -q "XMR top-up" "$T/home/credit-recent.json"

echo "==> paid upload with those XMR tokens"
SYNC_HOME="$T/home" OUT="$T/dogfood.out" client --dogfood-folder "$T/sync"
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
SYNC_HOME="$T/home2" WORMHOLE="$RELAY" OUT="$T/join2.out" client --join "$CODE"
grep -q "^Connected" "$T/join2.out"
grep -q "^nickname = ci-code" "$T/home2/tahoe/tahoe.cfg"
grep -q "^shares.needed = 2" "$T/home2/tahoe/tahoe.cfg"

echo "==> third home restores the recovery key and re-collects the XMR batch"
PASSPHRASE=ci-exit SYNC_HOME="$T/home" OUT="$T/export.out" client --export-recovery "$T/key.leasegrid-recovery"
grep -q "credit-seed=yes" "$T/export.out"
PASSPHRASE=ci-exit SYNC_HOME="$T/home3" OUT="$T/restore.out" client --restore-recovery "$T/key.leasegrid-recovery"
# spent tokens are missing from the snapshot; recover fills them from the seed
grep -E -q 'credit=[1-9]' "$T/restore.out" || { echo "restore did not re-collect spent credit"; cat "$T/restore.out"; exit 1; }
SYNC_HOME="$T/home3" OUT="$T/credit3.out" client --credit-status
# 20 XMR tokens again: leftover snapshot + recovered spent ones
grep -q "^20" "$T/credit3.out"

echo "==> exit test PASS ($OS)"
