"""Single frozen entry point for the Leasegrid Sync bundle.

One PyInstaller build serves three programs. Which one runs is chosen by
LEASEGRID_LAUNCH (set by the thin `tahoe` / `magic-folder` wrappers in the
AppDir) or, failing that, by the basename we were invoked as. Default: Sync.
"""

from __future__ import annotations

import os
import sys


def main() -> None:
    which = os.environ.get("LEASEGRID_LAUNCH") or os.path.basename(sys.argv[0])
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
