"""Operator docs live in a private repo, not in this public one (#87).

Handoffs, root-cause notes, autonomous-decision logs, run logs, Build drop-ins,
gate reports and the pending-handoff snapshot must not be tracked here. Design
packs such as docs/design/14-U0-DEVBOT-HANDOFF.md are product docs and stay.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_BANNED_DIRS = ("docs/ops/", "docs/build-dropins/")
_BANNED_NAME = re.compile(
    r"^(HANDOFF-|ROOT-CAUSE-|AUTONOMOUS-DECISIONS-|RUN-LOG-|PENDING-HANDOFF)|_REPORT\.md$|^RUN-LOG",
    re.IGNORECASE,
)


def ops_doc(path: str) -> bool:
    if path.startswith(_BANNED_DIRS):
        return True
    return bool(_BANNED_NAME.search(path.rsplit("/", 1)[-1]))


def _tracked() -> list[str]:
    out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True).stdout
    return [p for p in out.decode("utf-8").split("\0") if p]


def test_matcher_flags_ops_docs_and_keeps_product_docs() -> None:
    for bad in (
        "docs/ops/installers.md",
        "docs/build-dropins/v0.2-batch.md",
        "docs/HANDOFF-v0.2.md",
        "docs/notes/ROOT-CAUSE-99.md",
        "AUTONOMOUS-DECISIONS-2027-01-01.md",
        "docs/RUN-LOG-x.md",
        "docs/PENDING-HANDOFF.md",
        "GATE1_REPORT.md",
    ):
        assert ops_doc(bad), bad
    for good in (
        "docs/design/14-U0-DEVBOT-HANDOFF.md",
        "docs/guides/installers.md",
        "docs/release-notes/v0.1.12.md",
        "docs/TESTER-GUIDE.md",
        "CHANGELOG.md",
        "src/leasegrid_sync/app.py",
    ):
        assert not ops_doc(good), good


def test_public_repo_tracks_no_ops_docs() -> None:
    hits = [p for p in _tracked() if ops_doc(p)]
    assert not hits, "operator docs belong in the private ops repo (see AGENTS.md):\n" + "\n".join(hits)
