# U3 — Linux AppImage installer

**Cite:** `docs/09-ui-track.md` U3 · `docs/03-roadmap.md` Phase 2 “installers”  
**Exit test (roadmap):** clean machine, no Python tooling, run the AppImage, paste a furl,
reach `Connected`. **Status: PASS** on the dev grid (below) and re-run in CI on every build.

## What is in the file

`dist/Leasegrid_Sync-<ver>-x86_64.AppImage` (~70 MB squashfs) = one PyInstaller onedir
bundle serving three programs, chosen by `LEASEGRID_LAUNCH` or `argv[0]`:

| Path inside AppDir | Runs |
|---|---|
| `AppRun` | sets `LEASEGRID_TAHOE_BIN` / `LEASEGRID_MAGIC_FOLDER_BIN` to the bundled wrappers, then Sync |
| `usr/bin/leasegrid-sync/leasegrid-sync` | Leasegrid Sync (PyQt5), Tahoe 1.20.0, Magic Folder 24.3.0, Twisted 26, Python 3.12 |
| `usr/bin/tahoe`, `usr/bin/magic-folder` | sh wrappers → same binary with `LEASEGRID_LAUNCH=<tool>` |

`Leasegrid_Sync.AppImage tahoe --version` and `… magic-folder --version` are exposed on
purpose so a user can debug the bundled daemons.

Bundle gotchas already handled in `packaging/leasegrid-sync.spec`:

- Twisted plugins are discovered by listing `.py` files → shipped as data under `twisted/plugins/`
  (Tahoe storage plugins, Magic Folder twistd dropin, our ZKAP dropin).
- `autobahn.nvx` compiles a cffi module from `_utf8validator.c` at import → `collect_data_files("autobahn")`.
- `challenge_bypass_ristretto` dlopen()s `_native__lib.so` by path → added as a binary.
- Read-only mount means Twisted cannot write `dropin.cache`; it logs a warning and carries on.

## Build

```bash
python -m venv .venv && .venv/bin/pip install -e '.[sync,tahoe]' pyinstaller
packaging/build-appimage.sh          # ~40 s; downloads appimagetool once into build/
```

Build on the **oldest** distro you want to support (CI uses ubuntu-22.04, glibc 2.35);
PyInstaller bundles Python and Qt but not glibc.

## Run

```bash
chmod +x Leasegrid_Sync-*.AppImage
./Leasegrid_Sync-*.AppImage                       # window; paste furl on the join page
./Leasegrid_Sync-*.AppImage --join pb://…         # headless join, prints Connected line
./Leasegrid_Sync-*.AppImage --appimage-extract-and-run …   # no FUSE (containers)
```

State lives in `~/.local/share/leasegrid-sync/` (override `LEASEGRID_SYNC_HOME`), never inside
the image.

## Evidence (dev grid, 2026-09-20)

```
$ env -i HOME=/tmp/h PATH=/usr/bin:/bin … Leasegrid_Sync-0.1.0-x86_64.AppImage --join pb://…
Connected	introducer up · 3 storage	/tmp/lg-appimage-home/tahoe
$ … --dogfood-folder /tmp/lg-appimage-sync
U1 dogfood folder=/tmp/lg-appimage-sync probe=…/u1-hello.txt status={… 'size': 34}
$ … --credit-dogfood --credit-tier small
U2 credit-dogfood before=0 after=10 remaining=About 10 GiB kept for ~30 days on this friendnet
$ head -3 ~/.local/share/leasegrid-sync/logs/tahoe.log
twistd 26.4.0 (/tmp/.mount_LeasegCEGnii/usr/bin/leasegrid-sync/leasegrid-sync 3.12.3) starting up.
```

The last line is the proof that the *bundled* Tahoe ran, not a system one.

Short invite code, second device, bundled wormhole client through the grid's local relay:

```
$ scripts/dev-grid.sh --invite ci-code          # Invite Code for client: 7-stupendous-pupil
$ env -i … LEASEGRID_WORMHOLE_SERVER=ws://127.0.0.1:45040/v1 …AppImage --join 7-stupendous-pupil
Connected	introducer up · 3 storage	/tmp/ci-home2/tahoe
$ grep -E '^(nickname|shares.needed)' /tmp/ci-home2/tahoe/tahoe.cfg
nickname = ci-code
shares.needed = 2
```

## CI

`.github/workflows/appimage.yml`: builds on ubuntu-22.04, runs the exit test above against a
gated `scripts/dev-grid.sh` grid with the client side restricted to `PATH=/usr/bin:/bin`
(furl join, paid upload spends on every node, second home joins via short code), uploads the
AppImage as an artifact, and attaches it to the GitHub Release on `v*` tags.

## Not done

- No `.deb`, no macOS, no Windows (Tahoe + PyQt both build there; the launcher is portable).
- Placeholder icon (`packaging/make_icon.py`).
- No code signing / update channel. Users verify the SHA from the release page.
- No Tor bundled; transport policy setting still to come.
