"""The frozen bundle's one entry point picks the program from how it was started."""

from __future__ import annotations

import importlib.util
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "lg_launcher", Path(__file__).resolve().parents[1] / "packaging" / "launcher.py"
)
launcher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(launcher)
program_name = launcher.program_name


def test_frozen_uses_executable_name_and_strips_exe():
    assert program_name("ignored", "/b/leasegrid-sync/tahoe", True, {}) == "tahoe"
    assert program_name("ignored", r"C:\b\leasegrid-sync\tahoe.exe", True, {}) == "tahoe"
    assert program_name("ignored", r"C:\b\Magic-Folder.EXE", True, {}) == "magic-folder"
    assert program_name("ignored", "/b/leasegrid-sync", True, {}) == "leasegrid-sync"
    # the Windows console twin is still Sync
    assert program_name("ignored", r"C:\b\leasegrid-sync-cli.exe", True, {}) == "leasegrid-sync"


def test_source_run_uses_argv0_and_env_overrides_both():
    assert program_name("packaging/launcher.py", "/usr/bin/python3", False, {}) == "leasegrid-sync"
    assert program_name("tahoe", "/usr/bin/python3", False, {}) == "tahoe"
    assert program_name("x", "/b/tahoe", True, {"LEASEGRID_LAUNCH": "magic-folder"}) == "magic-folder"
    assert program_name("x", "/b/tahoe", True, {"LEASEGRID_LAUNCH": "nonsense"}) == "leasegrid-sync"
