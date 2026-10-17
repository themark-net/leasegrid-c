"""Tester pages link the current version's assets, with no stale caveat (v0.1.4 item 6)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from leasegrid_sync import __version__

ROOT = Path(__file__).resolve().parents[1]
PAGES = ("README.md", "docs/TESTERS.md", "docs/TESTER-GUIDE.md")
_ASSET = re.compile(r"Leasegrid_Sync-(\d+\.\d+\.\d+)-")
_DOWNLOAD = re.compile(r"/releases/download/v(\d+\.\d+\.\d+)/")
_TAG = re.compile(r"/releases/tag/v(\d+\.\d+\.\d+)")


@pytest.mark.parametrize("page", PAGES)
def test_tester_page_has_no_resolve_once_tagged_caveat(page: str) -> None:
    text = (ROOT / page).read_text(encoding="utf-8").lower()
    assert "resolve once" not in text
    assert "once the `v" not in text


@pytest.mark.parametrize("page", PAGES)
def test_tester_page_links_current_version(page: str) -> None:
    text = (ROOT / page).read_text(encoding="utf-8")
    versions = set(_ASSET.findall(text)) | set(_DOWNLOAD.findall(text)) | set(_TAG.findall(text))
    assert versions == {__version__}, versions


def test_release_notes_exist_for_current_version() -> None:
    notes = ROOT / "docs" / "release-notes" / ("v%s.md" % __version__)
    text = notes.read_text(encoding="utf-8")
    assert text.startswith("# Leasegrid Sync v%s\n" % __version__)
    assert "X.Y.Z" not in text and "<sha>" not in text and "#NN" not in text
