"""Source-level guarantee: U1 does not ship Tahoe WUI as product UI."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SYNC = ROOT / "src" / "leasegrid_sync"

BANNED = (
    "open the web ui",
    "open tahoe wui",
    "webbrowser.open",
    "qdesktopservices.openurl",
)


def test_sync_package_has_no_wui_product_path():
    blob = []
    for path in SYNC.rglob("*.py"):
        blob.append(path.read_text(encoding="utf-8"))
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
