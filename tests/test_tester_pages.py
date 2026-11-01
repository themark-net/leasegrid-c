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


# Common "these links work only after the tag" caveat phrasings (PR #71 review
# T4: "These links work once v0.1.4 is tagged." passed the old guard). This is
# a keyword guard, not a proof: it catches the phrasings listed in
# test_caveat_guard_catches_known_rewordings. A sentence that avoids those
# words can still pass (PR #72 review follow-up 3). The three v0.1.8 examples
# ("Coming soon", "available shortly after release", "may not work until CI
# publishes them") are in that list.
_LINK_TARGETS = re.compile(r"\]\([^)]*\)|<https?://[^>]*>|https?://\S+")
_TAGWORD = r"(?:tag\w*|publish\w*|releas\w*|push\w*|cut)"
# Up to 60 chars inside one sentence; a dot inside "v0.1.4" does not end it.
_SPAN = r"(?:[^.\n]|\.(?=\w)){0,60}"
_CAVEAT = (
    re.compile(r"\bresolv\w*", re.IGNORECASE),
    re.compile(r"\bonce\b" + _SPAN + r"\b" + _TAGWORD + r"\b", re.IGNORECASE),
    re.compile(r"\b(?:until|after|when)\b" + _SPAN + r"\btag\w*\b", re.IGNORECASE),
    re.compile(r"\b404\b"),
    re.compile(r"\bnot\s+(?:yet\s+)?(?:live|available|published|released|tagged|up)\b", re.IGNORECASE),
    # v0.1.8 candidates the keyword list missed. Each phrase is enough on its own.
    re.compile(r"\bcoming soon\b", re.IGNORECASE),
    re.compile(r"\bshortly\b" + _SPAN + r"\b(?:releas\w*|publish\w*)\b", re.IGNORECASE),
    re.compile(r"\bmay not work\b", re.IGNORECASE),
    re.compile(r"\buntil\b" + _SPAN + r"\bci\b" + _SPAN + r"\bpublish\w*", re.IGNORECASE),
)


def caveat_hits(text: str) -> list[str]:
    """Caveat phrases in prose; link targets are ignored (they hold /tag/ URLs)."""
    prose = _LINK_TARGETS.sub(" ", text)
    return [m.group(0) for rx in _CAVEAT for m in rx.finditer(prose)]


@pytest.mark.parametrize("page", PAGES)
def test_tester_page_has_no_resolve_once_tagged_caveat(page: str) -> None:
    text = (ROOT / page).read_text(encoding="utf-8")
    assert caveat_hits(text) == []


@pytest.mark.parametrize(
    "caveat",
    [
        "Download links point at the v0.1.4 release; they resolve once the `v0.1.4` tag is pushed.",
        "These links work once v0.1.4 is tagged.",
        "Links go live once the release is published.",
        "The assets appear when v0.1.5 is tagged.",
        "Downloads return 404 until the tag exists.",
        "Links are not yet live.",
        "They will start working after tagging.",
        "Coming soon.",
        "Downloads will be available shortly after release.",
        "The installers may not work until CI publishes them.",
        "The build may not work on a new laptop.",
        "Wait until CI publishes them.",
    ],
)
def test_caveat_guard_catches_known_rewordings(caveat: str) -> None:
    for page in PAGES:
        text = (ROOT / page).read_text(encoding="utf-8")
        assert caveat_hits(text + "\n" + caveat + "\n"), (page, caveat)


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


@pytest.mark.parametrize("page", ("README.md", "docs/TESTERS.md"))
def test_tester_page_says_other_http_errors(page: str) -> None:
    """PR #71 review: with no HTTP status the message is "daemon is not reachable"."""
    text = (ROOT / page).read_text(encoding="utf-8")
    assert "Other errors say" not in text
    assert "Other HTTP errors say *Magic Folder API error (NNN)*" in text
    assert "Magic Folder daemon is not reachable." in text
    # PR #72 review B1: the overstated #30 claim was in the v0.1.4 notes.
    assert "the v0.1.4 notes made the #30 change sound user-visible" in text
    assert not re.search(r"v0\.1\.(?!4\b)\d+ notes made the #30", text)


def test_release_notes_correct_the_v014_30_claim() -> None:
    text = (ROOT / "docs" / "release-notes" / "v0.1.5.md").read_text(encoding="utf-8")
    assert "v0.1.4 notes overstated #30" in text
    assert "Users see no change" in text
