"""Single frozen entry point for the Leasegrid Sync bundle.

One PyInstaller Analysis serves three programs. The spec emits one executable
per program (`leasegrid-sync`, `tahoe`, `magic-folder`, plus a console
`leasegrid-sync-cli` on Windows) that all run this module; which program runs
is chosen by LEASEGRID_LAUNCH or, failing that, by the executable's own name.
Default: Sync.
"""

from __future__ import annotations

import os
import sys


def program_name(argv0: str, executable: str, frozen: bool, env: dict | None = None) -> str:
    """Map how we were started onto one of: tahoe, magic-folder, leasegrid-sync."""
    env = os.environ if env is None else env
    which = env.get("LEASEGRID_LAUNCH")
    if not which:
        # Frozen: sys.executable is the per-program exe. Source: argv[0] is the script.
        path = executable if frozen else argv0
        which = path.replace("\\", "/").rsplit("/", 1)[-1].lower()
        if which.endswith(".exe"):
            which = which[:-4]
    if which in ("tahoe", "magic-folder"):
        return which
    return "leasegrid-sync"


def main() -> None:
    which = program_name(sys.argv[0], sys.executable, bool(getattr(sys, "frozen", False)))
    if which == "tahoe":
        from allmydata.scripts.runner import run

        run()  # calls sys.exit itself
        return
    if which == "magic-folder":
        from magic_folder.cli import _entry

        _entry()
        return
    from leasegrid_sync.cli import main as sync_main

    sys.exit(sync_main())


if __name__ == "__main__":
    main()
