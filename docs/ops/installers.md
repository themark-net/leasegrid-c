# Installers: Linux, macOS, Windows

One PyInstaller build per OS bundles **Leasegrid Sync + Tahoe-LAFS 1.20 + Magic
Folder 24.3** (and the magic-wormhole client for short invite codes). A user
installs nothing else: no Python, no Tahoe.

| OS | Artifact | Built on | Runs on |
|----|----------|----------|---------|
| Linux | `Leasegrid_Sync-<ver>-x86_64.AppImage` | ubuntu-22.04 | x86_64, glibc ≥ 2.35 (Ubuntu 22.04+, Debian 12+, Fedora 36+) |
| macOS | `Leasegrid_Sync-<ver>-macos-x86_64.dmg` (`Leasegrid Sync.app`) | macos-15-intel | Intel Macs natively; Apple Silicon via Rosetta 2 |
| Windows | `Leasegrid_Sync-<ver>-win64.zip`, `Leasegrid_Sync-<ver>-win64-setup.exe` | windows-2022 | Windows 10/11 x64 |

`.github/workflows/installers.yml` builds all three on every push that touches
`src/`, `packaging/`, `scripts/dev-grid.sh` or `pyproject.toml`, uploads them as
workflow artifacts, and attaches them to the GitHub Release on `v*` tags.
Linux-only detail (AppRun, desktop file) is in [`u3-appimage.md`](u3-appimage.md).

## Layout

One PyInstaller `Analysis` (`packaging/leasegrid-sync.spec`) emits several
executables that share one `_internal/`:

| Executable | What |
|------------|------|
| `leasegrid-sync` | the window (windowed on Windows: no console box behind the GUI) |
| `leasegrid-sync-cli.exe` | Windows only: same program with a console, for `--status`, `--join`, dogfood, CI |
| `tahoe` | Tahoe-LAFS 1.20 CLI + `tahoe run` |
| `magic-folder` | Magic Folder 24.3 CLI + daemon |

All of them run `packaging/launcher.py`, which dispatches on its own executable
name (`LEASEGRID_LAUNCH` overrides). Sync spawns the daemons as **siblings of
its own executable** (`backend.frozen_sibling`) before it would ever consult
PATH, so the versions tested together are the ones that run even on a machine
with a system Tahoe. On macOS the whole set is wrapped into `Leasegrid Sync.app`
(`Contents/MacOS/{leasegrid-sync,tahoe,magic-folder}`).

Data lives where each OS expects (`backend.default_home`):

| OS | Sync home (Tahoe client, Magic Folder config, wallet, logs) |
|----|-------------------------------------------------------------|
| Linux | `$XDG_DATA_HOME/leasegrid-sync` or `~/.local/share/leasegrid-sync` |
| macOS | `~/Library/Application Support/leasegrid-sync` |
| Windows | `%LOCALAPPDATA%\leasegrid-sync` |

`LEASEGRID_SYNC_HOME` overrides on every OS. The wallet lock is `flock` on
POSIX and `msvcrt.locking` on Windows (`leasegrid_zkap.client.wallet_lock`).

## Build locally

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[sync,tahoe]" pyinstaller pillow
packaging/build-desktop.sh        # macOS: .app + .dmg ; Windows (Git Bash): zip [+ setup.exe] ; Linux: onedir
packaging/build-appimage.sh       # Linux: onedir -> AppImage
```

Windows: run from Git Bash with `.venv\Scripts` (the script finds it). Inno Setup
6 on PATH or in `Program Files (x86)` produces the `setup.exe`; without it you
get the zip only. Pillow is optional: it converts the generated PNG icon to
`.ico` / `.icns`.

## Exit test (what CI proves on every OS)

`packaging/exit-test.sh <needle> <client command…>` starts a **gated** dev grid
from the venv, then drives the bundle with the venv scrubbed from PATH
(`env -i … PATH=/usr/bin:/bin` on Linux/macOS; `PATH=C:\Windows\System32` on Windows):

1. `--version` for the client.
2. `--join <furl> --client-only` → `Connected` (this grid charges; the paying
   home must not offer disk or a share can land unpaid).
3. XMR path (FakeChain): `leasegrid-zkap topup --json` → `POST /v0/fake/pay` →
   bundled `--credit-status` collects the batch → `--dogfood-folder` spends
   those tokens. `/v0/info` on all three storage nodes shows `spent ≥ 1`, and
   the twistd banner in `tahoe.log` names the bundled `tahoe` (the *needle*),
   not a system one. Lab faucet (`--credit-dogfood`) stays as the U2 dogfood
   path; the installer exit test now buys credit the way a real XMR payment
   will.
4. `--join <furl>` on a separate home (no `--client-only`) → `tahoe.cfg`
   `[storage] enabled = true` (unpaid join and offer are the same invite).
5. `dev-grid.sh --invite` → a second Sync home joins with the short code via the
   grid's local wormhole relay; the joined `tahoe.cfg` carries the invite's
   nickname and encoding.
6. `--export-recovery` (with `--ack-threat --ack-loss --ack-store`) from the paying home, `--restore-recovery --ack-threat` on a third
   home → Credit re-collects the same XMR batch from the seed. Missing ACKs FAIL and write nothing.

## Evidence (CI run 35491091151, 2026-09-20)

Same script, three runners, client side is the bundle only:

```
macos-15-intel   ==> built …/dist/Leasegrid_Sync-0.1.0-macos-x86_64.dmg  (85 MB)
                 Connected	introducer up · 3 storage	/Users/runner/work/_temp/lg-exit/home/tahoe
                 U2 credit-dogfood before=0 after=50 …   U1 dogfood … 'size': 34
                 Connected	introducer up · 3 storage	/Users/runner/work/_temp/lg-exit/home2/tahoe   (short code)
                 ==> exit test PASS (macos)
windows-2022     ==> built …/dist/Leasegrid_Sync-0.1.0-win64.zip (104 MB), …-win64-setup.exe (86 MB)
                 Connected	introducer up · 3 storage	D:\a\_temp\lg-exit\home\tahoe
                 U2 credit-dogfood before=0 after=50 …   U1 dogfood folder=D:\a\_temp\lg-exit\sync …
                 Connected	introducer up · 3 storage	D:\a\_temp\lg-exit\home2\tahoe   (short code)
                 ==> exit test PASS (windows)
ubuntu-22.04     ==> built …/dist/Leasegrid_Sync-0.1.0-x86_64.AppImage (70 MB)
                 ==> exit test PASS (linux)
```

The unit suite (`ci.yml`) runs on the same three runners; `wallet_lock`'s
msvcrt path and the `.bat`-wrapped fake `tahoe` are exercised on Windows there.

## Trust and signing (not done)

- **Linux**: unsigned AppImage; verify the SHA-256 from the release page.
- **macOS**: ad-hoc signed only (`codesign -s -`), not notarized. First launch:
  right-click → Open, or `xattr -d com.apple.quarantine "Leasegrid Sync.app"`.
  A Developer ID certificate plus `notarytool` would remove that step.
- **Windows**: unsigned; SmartScreen warns "unknown publisher" until an EV or
  OV code-signing certificate signs `setup.exe` and the exes.

## Known limits

- macOS is **x86_64 only**. `python-challenge-bypass-ristretto` ships no arm64
  or universal2 wheel; building it needs the Rust FFI library. Rosetta 2 runs
  the Intel build on Apple Silicon. GitHub's Intel runners (`macos-15-intel`)
  retire in August 2027, so an arm64 build of ristretto is on the list.
- Linux is x86_64 only (no aarch64 AppImage yet; the spec is arch-agnostic).
- No auto-update. Placeholder icon.
- `netifaces` (a Tahoe dependency) has no cp312 wheels for macOS/Windows; CI
  builds it from source with the runner's compiler. Local builders need clang /
  MSVC Build Tools for the same reason.
