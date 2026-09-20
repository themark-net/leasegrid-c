#!/usr/bin/env bash
# Freeze Leasegrid Sync + Tahoe + Magic Folder with PyInstaller and produce the
# per-OS artifact. Runs under bash on Linux, macOS and Windows (Git Bash).
#
#   packaging/build-desktop.sh          # uses ./.venv ([sync,tahoe] + pyinstaller [+ pillow for icons])
#   PYTHON=/path/to/python packaging/build-desktop.sh
#
# Output (dist/):
#   all      leasegrid-sync/            onedir: leasegrid-sync, tahoe, magic-folder [+ leasegrid-sync-cli.exe]
#   macOS    Leasegrid Sync.app, Leasegrid_Sync-<ver>-macos-<arch>.dmg
#   Windows  Leasegrid_Sync-<ver>-win64.zip [+ Leasegrid_Sync-<ver>-win64-setup.exe when Inno Setup is present]
#   Linux    (nothing more here; packaging/build-appimage.sh wraps the onedir into an AppImage)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

case "$(uname -s)" in
  Darwin) OS=macos ;;
  MINGW*|MSYS*|CYGWIN*) OS=windows ;;
  *) OS=linux ;;
esac

if [[ -z "${PYTHON:-}" ]]; then
  if [[ "$OS" == windows ]]; then PYTHON="$ROOT/.venv/Scripts/python.exe"; else PYTHON="$ROOT/.venv/bin/python"; fi
fi
ARCH="$(uname -m)"
VERSION="$("$PYTHON" -c 'import sys; sys.path.insert(0,"src"); import leasegrid_sync; print(leasegrid_sync.__version__)')"
EXE=""; [[ "$OS" == windows ]] && EXE=".exe"

"$PYTHON" -c 'import PyInstaller, PyQt5, allmydata, magic_folder' 2>/dev/null || {
  echo "build-desktop: need pyinstaller + [sync,tahoe] in $PYTHON" >&2
  echo "  $PYTHON -m pip install -e '.[sync,tahoe]' pyinstaller" >&2
  exit 1
}

echo "==> icon"
mkdir -p "$ROOT/build"
ICON_PNG="$ROOT/build/leasegrid-sync.png"
QT_QPA_PLATFORM=offscreen "$PYTHON" packaging/make_icon.py "$ICON_PNG"
# PyInstaller converts PNG -> .ico/.icns only with Pillow; without it, no icon.
if "$PYTHON" -c 'import PIL' 2>/dev/null; then export LEASEGRID_ICON="$ICON_PNG"; fi

echo "==> pyinstaller ($OS $ARCH, v$VERSION)"
rm -rf "$ROOT/build/pyinstaller" "$ROOT/dist/leasegrid-sync" "$ROOT/dist/Leasegrid Sync.app"
"$PYTHON" -m PyInstaller --noconfirm --clean \
  --workpath "$ROOT/build/pyinstaller" \
  --distpath "$ROOT/dist" \
  packaging/leasegrid-sync.spec

ONEDIR="$ROOT/dist/leasegrid-sync"
echo "==> smoke: every frozen program answers --version"
"$ONEDIR/tahoe$EXE" --version
"$ONEDIR/magic-folder$EXE" --version
if [[ "$OS" == windows ]]; then
  "$ONEDIR/leasegrid-sync-cli.exe" --version
else
  "$ONEDIR/leasegrid-sync" --version
fi

case "$OS" in
  macos)
    APP="$ROOT/dist/Leasegrid Sync.app"
    test -x "$APP/Contents/MacOS/leasegrid-sync"
    "$APP/Contents/MacOS/tahoe" --version
    # Ad-hoc signature: lets Gatekeeper treat the bundle as intact (still "unidentified
    # developer" until a Developer ID signs and notarizes it).
    codesign --force --deep --sign - "$APP" 2>/dev/null || echo "build-desktop: ad-hoc codesign skipped"
    STAGE="$ROOT/build/dmg"
    rm -rf "$STAGE"; mkdir -p "$STAGE"
    cp -R "$APP" "$STAGE/"
    ln -s /Applications "$STAGE/Applications"
    OUT="$ROOT/dist/Leasegrid_Sync-${VERSION}-macos-${ARCH}.dmg"
    rm -f "$OUT"
    hdiutil create -volname "Leasegrid Sync" -srcfolder "$STAGE" -ov -format UDZO "$OUT" >/dev/null
    echo "==> built $OUT"
    ls -la "$OUT"
    ;;
  windows)
    OUT="$ROOT/dist/Leasegrid_Sync-${VERSION}-win64.zip"
    rm -f "$OUT"
    # PowerShell is always there; zip(1) is not in Git Bash.
    powershell.exe -NoProfile -Command \
      "Compress-Archive -Path '$(cygpath -w "$ONEDIR")' -DestinationPath '$(cygpath -w "$OUT")' -Force"
    echo "==> built $OUT"
    ISCC=""
    for c in iscc ISCC "/c/Program Files (x86)/Inno Setup 6/ISCC.exe" "/c/Program Files/Inno Setup 6/ISCC.exe"; do
      if command -v "$c" >/dev/null 2>&1 || [[ -x "$c" ]]; then ISCC="$c"; break; fi
    done
    if [[ -n "$ISCC" ]]; then
      SETUP="$ROOT/dist/Leasegrid_Sync-${VERSION}-win64-setup.exe"
      ICON_ARGS=()
      ICON_ICO="$ROOT/build/leasegrid-sync.ico"
      if "$PYTHON" -c "from PIL import Image; Image.open(r'$ICON_PNG').save(r'$ICON_ICO', sizes=[(256,256),(64,64),(32,32),(16,16)])" 2>/dev/null; then
        ICON_ARGS=("/DIcon=$(cygpath -w "$ICON_ICO")")
      fi
      "$ISCC" "/DAppVersion=$VERSION" "/DSourceDir=$(cygpath -w "$ONEDIR")" \
        "/DOutDir=$(cygpath -w "$ROOT/dist")" ${ICON_ARGS[@]+"${ICON_ARGS[@]}"} \
        "$(cygpath -w "$ROOT/packaging/windows-installer.iss")" >/dev/null
      echo "==> built $SETUP"
    else
      echo "build-desktop: Inno Setup not found; zip only (choco install innosetup for a setup.exe)"
    fi
    ls -la "$ROOT"/dist/Leasegrid_Sync-*
    ;;
  linux)
    echo "==> onedir ready at $ONEDIR (packaging/build-appimage.sh for the AppImage)"
    ;;
esac
