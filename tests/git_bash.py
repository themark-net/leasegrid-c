"""Bash for packaging-script tests.

On Windows, ``bash`` on PATH may be WSL. CI's windows-2022 job has Git Bash.
"""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

import pytest

# Git for Windows. bin/bash.exe is the wrapper; usr/bin/bash.exe is the real bash.
_GIT_BASH = (
    r"C:\Program Files\Git\bin\bash.exe",
    r"C:\Program Files\Git\usr\bin\bash.exe",
)


def resolve_bash() -> str | None:
    if sys.platform == "win32":
        found = shutil.which("bash")
        if found and "Git" in found and Path(found).is_file():
            return found
        for candidate in _GIT_BASH:
            if Path(candidate).is_file():
                return candidate
        return None
    return shutil.which("bash")


def require_bash() -> str:
    bash = resolve_bash()
    if bash is None:
        if sys.platform == "win32":
            pytest.skip("Git Bash not found; bash on PATH may be WSL")
        pytest.skip("bash not on PATH")
    return bash


def bash_path(path: Path) -> str:
    """Absolute path Git Bash can open. Windows ``C:\\...`` becomes ``/c/...``."""
    resolved = str(path.resolve())
    if sys.platform != "win32":
        return resolved
    match = re.match(r"^([A-Za-z]):[\\/](.*)$", resolved)
    if not match:
        return resolved.replace("\\", "/")
    return "/" + match.group(1).lower() + "/" + match.group(2).replace("\\", "/")
