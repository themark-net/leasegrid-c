"""Tracked files must not carry a real account's home path.

The repo is public. A path like /home/<name>/... or /Users/<name>/... names a
real machine account. Docs and scripts use ~/ or $HOME instead. Generic
placeholders (u, x, you, user, other, runner) stay allowed because the tests
and wireframes use them as example paths.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve().relative_to(ROOT).as_posix()

SUFFIXES = {".md", ".txt", ".sh", ".py", ".kt", ".kts", ".yml", ".yaml", ".toml", ".iss", ".bat", ".ps1", ".spec"}
PLACEHOLDERS = {"u", "x", "you", "user", "other", "runner"}

# A home path that starts a path: not "$T/home/..." or "/read-only/home/...".
_HOME = re.compile(r"(?<![\w.$}/])/(?:home|Users)/([A-Za-z0-9._-]+)")


def private_home_paths(text: str) -> list[str]:
    return [m.group(0) for m in _HOME.finditer(text) if m.group(1) not in PLACEHOLDERS]


def _tracked() -> list[str]:
    out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True).stdout
    return [p for p in out.decode("utf-8").split("\0") if p]


def test_matcher_flags_a_real_account_and_skips_placeholders() -> None:
    real = "/" + "home" + "/" + "alice"
    assert private_home_paths(f"see {real}/x.txt") == [real]
    assert private_home_paths("`" + "/" + "Users" + "/bob/x`") == ["/" + "Users" + "/bob"]
    assert private_home_paths("~/DEVELOP/leasegrid-c and $HOME/tahoe-venv") == []
    assert private_home_paths('"/home/x/Photos" C:/Users/u /home/runner/work') == []
    assert private_home_paths('"$T/home/credit.json" /read-only/home/storage lg-exit/home/tahoe') == []


def test_no_tracked_file_names_a_real_home_directory() -> None:
    hits: list[str] = []
    for rel in _tracked():
        if rel == SELF or Path(rel).suffix not in SUFFIXES:
            continue
        path = ROOT / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for n, line in enumerate(text.splitlines(), 1):
            for found in private_home_paths(line):
                hits.append(f"{rel}:{n}: {found}")
    assert not hits, "use ~/ or $HOME instead of a real home path:\n" + "\n".join(hits)
