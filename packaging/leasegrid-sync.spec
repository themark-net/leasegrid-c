# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec: Leasegrid Sync + Tahoe 1.20 + Magic Folder 24.3 in one onedir bundle.

Build with packaging/build-appimage.sh (which then wraps the result as an AppImage).
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
datas += [(str(ROOT / "twisted" / "plugins" / "leasegrid_zkap_dropin.py"), "twisted/plugins")]
datas += collect_data_files("allmydata")
datas += collect_data_files("magic_folder")
datas += collect_data_files("foolscap")
datas += collect_data_files("challenge_bypass_ristretto")
# cffi dlopen()s this by path next to the module; PyInstaller does not see it as an import.
import challenge_bypass_ristretto as _cbr  # noqa: E402

binaries = [
    (str(p), "challenge_bypass_ristretto")
    for p in Path(_cbr.__file__).parent.glob("_native__lib*.so")
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
    ]
)

# Version strings some of these read back at runtime.
for dist in ("tahoe-lafs", "magic-folder", "foolscap", "twisted", "zope.interface", "autobahn", "magic-wormhole",
             "python-challenge-bypass-ristretto", "cryptography", "leasegrid-zkap-lab"):
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

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="leasegrid-sync",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,  # tahoe / magic-folder are CLIs sharing this binary
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="leasegrid-sync",
)
