#!/usr/bin/env bash
# Build Leasegrid_Sync-<version>-x86_64.AppImage.
#
#   packaging/build-appimage.sh            # uses ./.venv (needs [sync,tahoe] + pyinstaller)
#   PYTHON=/path/to/python packaging/build-appimage.sh
#
# Output: dist/Leasegrid_Sync-<ver>-x86_64.AppImage  (+ dist/leasegrid-sync/ onedir for debugging)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PYTHON="${PYTHON:-$ROOT/.venv/bin/python}"
ARCH="$(uname -m)"
VERSION="$("$PYTHON" -c 'import sys; sys.path.insert(0,"src"); import leasegrid_sync; print(leasegrid_sync.__version__)')"
APPDIR="$ROOT/build/AppDir"
OUT="$ROOT/dist/Leasegrid_Sync-${VERSION}-${ARCH}.AppImage"

"$PYTHON" -c 'import PyInstaller, PyQt5, allmydata, magic_folder' 2>/dev/null || {
  echo "build-appimage: need pyinstaller + [sync,tahoe] in $PYTHON" >&2
  echo "  $PYTHON -m pip install -e '.[sync,tahoe]' pyinstaller" >&2
  exit 1
}

echo "==> pyinstaller"
rm -rf "$ROOT/build/pyinstaller" "$ROOT/dist/leasegrid-sync"
"$PYTHON" -m PyInstaller --noconfirm --clean \
  --workpath "$ROOT/build/pyinstaller" \
  --distpath "$ROOT/dist" \
  packaging/leasegrid-sync.spec

echo "==> smoke: frozen tahoe / magic-folder / sync answer"
LEASEGRID_LAUNCH=tahoe        "$ROOT/dist/leasegrid-sync/leasegrid-sync" --version
LEASEGRID_LAUNCH=magic-folder "$ROOT/dist/leasegrid-sync/leasegrid-sync" --version
"$ROOT/dist/leasegrid-sync/leasegrid-sync" --version

echo "==> AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/share/applications" "$APPDIR/usr/share/icons/hicolor/256x256/apps"
cp -a "$ROOT/dist/leasegrid-sync" "$APPDIR/usr/bin/leasegrid-sync"
for tool in tahoe magic-folder; do
  cat > "$APPDIR/usr/bin/$tool" <<EOF
#!/bin/sh
HERE="\$(dirname "\$(readlink -f "\$0")")"
LEASEGRID_LAUNCH=$tool exec "\$HERE/leasegrid-sync/leasegrid-sync" "\$@"
EOF
  chmod +x "$APPDIR/usr/bin/$tool"
done
cat > "$APPDIR/AppRun" <<'EOF'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
export LEASEGRID_TAHOE_BIN="$HERE/usr/bin/tahoe"
export LEASEGRID_MAGIC_FOLDER_BIN="$HERE/usr/bin/magic-folder"
# The bundled Qt platform plugins need this when the host has none.
export QT_QPA_PLATFORM_PLUGIN_PATH="$HERE/usr/bin/leasegrid-sync/_internal/PyQt5/Qt5/plugins/platforms"
case "${1:-}" in
  tahoe|magic-folder) tool="$1"; shift; exec "$HERE/usr/bin/$tool" "$@" ;;
esac
exec "$HERE/usr/bin/leasegrid-sync/leasegrid-sync" "$@"
EOF
chmod +x "$APPDIR/AppRun"
cp packaging/leasegrid-sync.desktop "$APPDIR/"
cp packaging/leasegrid-sync.desktop "$APPDIR/usr/share/applications/"
"$PYTHON" packaging/make_icon.py "$APPDIR/leasegrid-sync.png"
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
