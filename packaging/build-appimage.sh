#!/usr/bin/env bash
# Build Leasegrid_Sync-<version>-x86_64.AppImage (Linux).
#
#   packaging/build-appimage.sh            # uses ./.venv (needs [sync,tahoe] + pyinstaller)
#   PYTHON=/path/to/python packaging/build-appimage.sh
#
# Runs packaging/build-desktop.sh for the frozen onedir (leasegrid-sync, tahoe,
# magic-folder side by side), then wraps it as an AppImage.
# Output: dist/Leasegrid_Sync-<ver>-x86_64.AppImage  (+ dist/leasegrid-sync/ onedir for debugging)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PYTHON="${PYTHON:-$ROOT/.venv/bin/python}"
export PYTHON
ARCH="$(uname -m)"
VERSION="$("$PYTHON" -c 'import sys; sys.path.insert(0,"src"); import leasegrid_sync; print(leasegrid_sync.__version__)')"
APPDIR="$ROOT/build/AppDir"
OUT="$ROOT/dist/Leasegrid_Sync-${VERSION}-${ARCH}.AppImage"

packaging/build-desktop.sh

echo "==> AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/share/applications" "$APPDIR/usr/share/icons/hicolor/256x256/apps"
cp -a "$ROOT/dist/leasegrid-sync" "$APPDIR/usr/bin/leasegrid-sync"
cat > "$APPDIR/AppRun" <<'EOF'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
BIN="$HERE/usr/bin/leasegrid-sync"
# Sync finds tahoe / magic-folder as siblings of its own executable; these make
# that explicit for anything that inherits the environment.
export LEASEGRID_TAHOE_BIN="$BIN/tahoe"
export LEASEGRID_MAGIC_FOLDER_BIN="$BIN/magic-folder"
# The bundled Qt platform plugins need this when the host has none.
export QT_QPA_PLATFORM_PLUGIN_PATH="$BIN/_internal/PyQt5/Qt5/plugins/platforms"
case "${1:-}" in
  tahoe|magic-folder) tool="$1"; shift; exec "$BIN/$tool" "$@" ;;
esac
exec "$BIN/leasegrid-sync" "$@"
EOF
chmod +x "$APPDIR/AppRun"
cp packaging/leasegrid-sync.desktop "$APPDIR/"
cp packaging/leasegrid-sync.desktop "$APPDIR/usr/share/applications/"
cp "$ROOT/build/leasegrid-sync.png" "$APPDIR/leasegrid-sync.png"
cp "$APPDIR/leasegrid-sync.png" "$APPDIR/usr/share/icons/hicolor/256x256/apps/leasegrid-sync.png"
ln -sf leasegrid-sync.png "$APPDIR/.DirIcon"

echo "==> appimagetool"
TOOL="$ROOT/build/appimagetool-${ARCH}.AppImage"
if [[ ! -x "$TOOL" ]]; then
  curl -fsSL -o "$TOOL" \
    "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-${ARCH}.AppImage"
  chmod +x "$TOOL"
fi
mkdir -p "$ROOT/dist"
# --appimage-extract-and-run: works without FUSE (CI containers).
ARCH="$ARCH" "$TOOL" --appimage-extract-and-run --no-appstream "$APPDIR" "$OUT"
echo "==> built $OUT"
ls -la "$OUT"
