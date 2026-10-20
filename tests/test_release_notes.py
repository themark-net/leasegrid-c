"""Friends-and-family release notes stay in the template shape.

``check_release_notes`` takes a path so a temp copy can prove a placeholder
or a sixth What's new bullet is rejected.
"""

from __future__ import annotations

import re
from pathlib import Path

from leasegrid_sync import __version__

ROOT = Path(__file__).resolve().parents[1]
_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
_ASSET = re.compile(r"Leasegrid_Sync-(\d+\.\d+\.\d+)-")
_ANGLE = re.compile(r"<[^>\n]+>")
_PREVIOUS = re.compile(r"Previous build: \[v(\d+\.\d+\.\d+)\]")


def _version_tuple(text: str) -> tuple[int, ...]:
    return tuple(int(part) for part in text.split("."))


def _without_allowed_markup(text: str) -> str:
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = re.sub(r"</?details>", "", text)
    text = re.sub(r"</?summary>", "", text)
    return text


def check_release_notes(path: Path, version: str | None = None) -> list[str]:
    """Return human-readable problems. Empty means the notes are acceptable."""
    version = version or __version__
    problems: list[str] = []
    if not path.is_file():
        return ["missing %s" % path]
    text = path.read_text(encoding="utf-8")
    if not text.startswith("# Leasegrid Sync v%s\n" % version):
        problems.append("title is not Leasegrid Sync v%s" % version)
    if "X.Y.Z" in text or "vA.B.C" in text:
        problems.append("template version token")
    if "Release-notes template" in text or "<placeholder>" in text:
        problems.append("template comment or <placeholder>")
    for token in _ANGLE.findall(_without_allowed_markup(text)):
        problems.append("placeholder markup %s" % token)
    for url in _LINK.findall(text):
        if not url.startswith("https://"):
            problems.append("link is not absolute https: %s" % url)
    assets = set(_ASSET.findall(text))
    if assets != {version}:
        problems.append("asset versions %s are not %s" % (sorted(assets), version))
    whats_new = re.search(r"^## What's new\n(.*?)(?=^## |\Z)", text, flags=re.M | re.S)
    if whats_new is None:
        problems.append("What's new section missing")
    else:
        bullets = [line for line in whats_new.group(1).splitlines() if line.startswith("- ")]
        if len(bullets) > 5:
            problems.append("What's new has %d bullets" % len(bullets))
    previous = _PREVIOUS.search(text)
    if previous is None:
        problems.append("previous build link missing")
    elif _version_tuple(previous.group(1)) >= _version_tuple(version):
        problems.append("previous build v%s is not earlier than v%s" % (previous.group(1), version))
    return problems


def test_daemon_logs_rotate_when_the_daemon_starts() -> None:
    """Daemon logs rotate at start. They do not rotate like sync-ui.log.

    The rotation change shipped in v0.1.7, so its notes and the guide must say
    "when the daemon starts". Current notes and pages may drop the bullet in a
    later release, but must never reintroduce the wrong wording.
    """
    v017 = (ROOT / "docs" / "release-notes" / "v0.1.7.md").read_text(encoding="utf-8")
    notes = (ROOT / "docs" / "release-notes" / ("v%s.md" % __version__)).read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    testers = (ROOT / "docs" / "TESTERS.md").read_text(encoding="utf-8")
    guide = (ROOT / "docs" / "TESTER-GUIDE.md").read_text(encoding="utf-8")
    for label, text in (
        ("v0.1.7 notes", v017),
        ("notes", notes),
        ("readme", readme),
        ("testers", testers),
        ("guide", guide),
    ):
        assert "rotate like" not in text, label
        assert "the same way" not in text, label
    for label, text in (("v0.1.7 notes", v017), ("guide", guide)):
        assert "when the daemon starts" in text, label
    assert "A file over 1 MiB rotates" not in guide


def test_current_release_notes_match_the_template_shape() -> None:
    path = ROOT / "docs" / "release-notes" / ("v%s.md" % __version__)
    assert check_release_notes(path) == []


def test_placeholder_and_sixth_bullet_are_rejected(tmp_path: Path) -> None:
    source = ROOT / "docs" / "release-notes" / ("v%s.md" % __version__)
    dest = tmp_path / source.name
    text = source.read_text(encoding="utf-8")
    section = text.split("## What's new\n", 1)[1].split("\n## ", 1)[0]
    have = sum(1 for line in section.splitlines() if line.startswith("- "))
    assert have <= 5
    # One <placeholder> bullet plus fillers: exactly six bullets in all.
    extra = "".join("- filler change %d\n" % i for i in range(5 - have))
    text = text.replace("## What's new\n", "## What's new\n- <placeholder> one more change\n" + extra, 1)
    dest.write_text(text, encoding="utf-8")
    problems = check_release_notes(dest)
    assert any("<placeholder>" in problem or "placeholder markup" in problem for problem in problems)
    assert any("6 bullets" in problem for problem in problems)
    assert problems
