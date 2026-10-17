"""Source-level guarantee: U1 does not ship Tahoe WUI as product UI."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SYNC = ROOT / "src" / "leasegrid_sync"

BANNED = (
    "open the web ui",
    "open tahoe wui",
    "webbrowser.open",
)


def test_sync_package_has_no_wui_product_path():
    blob = []
    for path in sorted(SYNC.rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        blob.append(source)
        # A local folder may be opened. A web URL here would be the Tahoe WUI.
        for arg in re.findall(r"openUrl\(([^)]*)\)", source):
            assert "fromLocalFile" in arg, "%s opens a non-local URL: %s" % (path.name, arg)
    text = "\n".join(blob).lower()
    for needle in BANNED:
        assert needle.lower() not in text, "WUI product path found: %s" % needle
    assert "leasegrid sync" in text
    assert "magic folder" in text


def test_app_never_mentions_wui_as_cta():
    app = (SYNC / "app.py").read_text(encoding="utf-8")
    credit = (SYNC / "credit.py").read_text(encoding="utf-8")
    assert "Add folder" in app
    assert "Join friendnet" in app
    assert "Credit" in app
    assert "Open web UI" not in app
    assert "web UI" not in app or "does not use the Tahoe web UI" in app
    assert "Open web UI" not in credit
    assert "webbrowser" not in credit.lower()
    assert "expand across nodes" in credit
    assert "one node" in credit
