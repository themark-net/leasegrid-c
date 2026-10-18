"""The systems-safety skill, AGENTS.md, and Semgrep messages name the same ids.

This is a cross-file check. It fails when a rule cites an id the docs dropped,
when the skill's name drifts from its folder, or when the AGENTS.md link is dead.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".grok" / "skills" / "systems-safety" / "SKILL.md"
AGENTS = ROOT / "AGENTS.md"
RULES = ROOT / "tools" / "semgrep"
_SS = re.compile(r"SS\d+")


def _frontmatter(text: str) -> dict[str, str]:
    """Parse the leading `--- / key: value / ---` block. Raises if it is not that shape."""
    if not text.startswith("---\n"):
        raise ValueError("skill does not start with frontmatter")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise ValueError("skill frontmatter does not close")
    meta: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if not line.strip():
            continue
        key, sep, value = line.partition(":")
        if not sep or not key.strip():
            raise ValueError("frontmatter line is not key: value")
        meta[key.strip()] = value.strip()
    if not meta:
        raise ValueError("frontmatter is empty")
    return meta


def _cited_ids() -> set[str]:
    found: set[str] = set()
    for path in sorted(RULES.glob("*.yml")):
        found.update(_SS.findall(path.read_text(encoding="utf-8")))
    return found


def test_semgrep_ids_are_in_agents_and_the_skill() -> None:
    """Every SS id a Semgrep message cites is written in both docs."""
    cited = _cited_ids()
    assert cited, "tools/semgrep rules cite no SS ids"
    agents = AGENTS.read_text(encoding="utf-8")
    skill = SKILL.read_text(encoding="utf-8")
    missing_agents = sorted(ss for ss in cited if ss not in agents)
    missing_skill = sorted(ss for ss in cited if ss not in skill)
    assert not missing_agents, "AGENTS.md missing %s" % ", ".join(missing_agents)
    assert not missing_skill, "skill missing %s" % ", ".join(missing_skill)


def test_skill_frontmatter_matches_its_folder() -> None:
    """name equals the folder, and description is a non-empty string under 1024 chars."""
    meta = _frontmatter(SKILL.read_text(encoding="utf-8"))
    assert meta.get("name") == SKILL.parent.name
    description = meta.get("description", "")
    assert description, "description is empty"
    assert len(description) < 1024


def test_agents_links_to_the_skill_file() -> None:
    """AGENTS.md points at the skill, and that file is in the tree."""
    rel = ".grok/skills/systems-safety/SKILL.md"
    assert rel in AGENTS.read_text(encoding="utf-8")
    assert (ROOT / rel).is_file()
