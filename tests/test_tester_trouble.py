"""The tester guide keeps a short recovery section for shipped behavior."""

from __future__ import annotations

import re
from pathlib import Path

from leasegrid_sync import __version__
from leasegrid_sync.app import (
    ALREADY_RUNNING,
    COPY_BUG_BUTTON,
    FOLDER_FILE_BANNER,
    FOLDER_MISSING_BANNER,
    INVITE_CLOSE_QUESTION,
    INVITE_KEEP_OPEN,
    OPEN_LOGS_BUTTON,
)

ROOT = Path(__file__).resolve().parents[1]
_SECTION = re.compile(
    r"^## If something goes wrong\n(.*?)(?=^## |\Z)",
    flags=re.M | re.S,
)
_VERSION = re.compile(r"\d+\.\d+\.\d+")


def _trouble_section() -> str:
    text = (ROOT / "docs" / "TESTER-GUIDE.md").read_text(encoding="utf-8")
    match = _SECTION.search(text)
    assert match is not None, "If something goes wrong section missing"
    return match.group(1)


def test_trouble_section_names_shipped_recovery_in_at_most_eight_lines() -> None:
    body = _trouble_section()
    bullets = [line for line in body.splitlines() if line.startswith("- ")]
    assert 1 <= len(bullets) <= 8
    text = "\n".join(bullets)
    assert ALREADY_RUNNING in text
    assert INVITE_CLOSE_QUESTION in text
    assert INVITE_KEEP_OPEN in text
    assert OPEN_LOGS_BUTTON in text
    assert COPY_BUG_BUTTON in text
    assert FOLDER_MISSING_BANNER.split("%s", 1)[0].strip() in text
    assert FOLDER_FILE_BANNER.split("%s", 1)[0].strip() in text
    assert "[fallback in the Linux section](#linux)" in text
    assert "--appimage-extract-and-run" not in text
    assert "Smart App Control" in text
    assert "[Windows (SmartScreen)](#windows-smartscreen)" in text
    versions = set(_VERSION.findall(body))
    assert versions <= {__version__}
    testers = (ROOT / "docs" / "TESTERS.md").read_text(encoding="utf-8")
    assert "#if-something-goes-wrong" in testers
