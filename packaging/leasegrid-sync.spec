# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec: Leasegrid Sync + Tahoe 1.20 + Magic Folder 24.3 in one onedir bundle.

One Analysis, several executables sharing `_internal`: `leasegrid-sync` (the
window), `tahoe` and `magic-folder` (the daemons Sync spawns; it finds them as
siblings of its own executable), and on Windows `leasegrid-sync-cli` because a
windowed exe there has no stdout for --status / --join. On macOS the COLLECT is
wrapped into `Leasegrid Sync.app`.

Build with packaging/build-desktop.sh (Linux: build-appimage.sh wraps that).
"""

import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

HERE = Path(SPECPATH)
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "src"))

# Twisted discovers plugins by listing .py files under twisted.plugins.__path__;
# a frozen PYZ has no .py files, so ship them as data. Tahoe finds storage
# plugins and magic-folder finds its twistd dropin this way.
import twisted.plugins as _tp  # noqa: E402

plugin_dir = Path(list(_tp.__path__)[0])
datas = [(str(p), "twisted/plugins") for p in plugin_dir.glob("*.py")]
datas += [(str(ROOT / "src" / "twisted" / "plugins" / "leasegrid_zkap_dropin.py"), "twisted/plugins")]
datas += collect_data_files("allmydata")
datas += collect_data_files("magic_folder")
datas += collect_data_files("foolscap")
datas += collect_data_files("challenge_bypass_ristretto")
# cffi dlopen()s this by path next to the module; PyInstaller does not see it as an import.
import challenge_bypass_ristretto as _cbr  # noqa: E402

binaries = [
    (str(p), "challenge_bypass_ristretto")
    for p in Path(_cbr.__file__).parent.glob("_native__lib*")
    if p.suffix in (".so", ".dylib", ".dll", ".pyd")
]
# autobahn.nvx compiles its cffi UTF-8 validator from a .c file at import time.
datas += collect_data_files("autobahn")
datas += collect_data_files("wormhole")

hiddenimports = (
    collect_submodules("allmydata")
    + collect_submodules("magic_folder")
    + collect_submodules("foolscap")
    + collect_submodules("twisted.plugins")
    + collect_submodules("leasegrid_sync")
    + collect_submodules("leasegrid_zkap")
    + [
        "twisted.internet.epollreactor",
        "twisted.internet.selectreactor",
        "zope.interface",
        "cryptography.fernet",
        "PyQt5.sip",
        "sqlite3",
        "segno",
        # Py≥3.13: stdlib cgi gone; legacy-cgi provides it for Tahoe
        "cgi",
        "legacy_cgi",
    ]
)

# Version strings some of these read back at runtime.
for dist in ("tahoe-lafs", "magic-folder", "foolscap", "twisted", "zope.interface", "autobahn", "magic-wormhole",
             "python-challenge-bypass-ristretto", "cryptography", "leasegrid-zkap-lab", "segno"):
    try:
        datas += copy_metadata(dist)
    except Exception:
        pass

a = Analysis(
    [str(HERE / "launcher.py")],
    pathex=[str(ROOT / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy", "PyQt5.QtWebEngine", "PyQt5.QtWebEngineWidgets",
              "PyQt5.QtQml", "PyQt5.QtQuick", "PyQt5.Qt3DCore", "PyQt5.QtMultimedia"],
    noarchive=False,
)
pyz = PYZ(a.pure)

WINDOWS = sys.platform.startswith("win")
MACOS = sys.platform == "darwin"
# Optional: a PNG the build script generated with make_icon.py (Pillow converts).
ICON = os.environ.get("LEASEGRID_ICON") or None


def program(name, console):
    return EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name=name,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=console,
        icon=ICON,
        # macOS: Sync forks daemons and opens sockets; no hardened-runtime entitlements needed.
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )


# The window: no console on Windows (else a black box sits behind the GUI).
programs = [program("leasegrid-sync", console=not WINDOWS)]
if WINDOWS:
    programs.append(program("leasegrid-sync-cli", console=True))
programs += [program("tahoe", console=True), program("magic-folder", console=True)]

coll = COLLECT(
    *programs,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="leasegrid-sync",
)

if MACOS:
    from leasegrid_sync import __version__  # noqa: E402

    app = BUNDLE(
        coll,
        name="Leasegrid Sync.app",
        icon=ICON,
        bundle_identifier="net.themark.leasegrid-sync",
        version=__version__,
        info_plist={
            "CFBundleDisplayName": "Leasegrid Sync",
            "CFBundleShortVersionString": __version__,
            "NSHighResolutionCapable": True,
            # Sync is a menu-bar/tray style app; do not steal focus at launch.
            "LSUIElement": False,
        },
    )
