"""Static Slice A locks: design docs landed, no Tahoe WUI in the APK sources."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DESIGN = [
    "docs/design/35-P4-ANDROID-A-JOURNEY.md",
    "docs/design/36-P4-ANDROID-A-IA.md",
    "docs/design/37-P4-ANDROID-A-WIREFRAMES.md",
    "docs/design/38-P4-ANDROID-A-NON-GOALS.md",
    "docs/design/39-P4-ANDROID-A-DEVBOT-HANDOFF.md",
    "docs/09-ui-track-P4-ANDROID-POINTER.md",
    "docs/ops/p4-android-dogfood.md",
]

SOURCE_SUFFIXES = {".kt", ".kts", ".xml", ".py", ".md"}


def test_design_docs_landed():
    for rel in DESIGN:
        path = ROOT / rel
        assert path.is_file(), rel
        text = path.read_text(encoding="utf-8")
        assert "7837ef8" in text or "Slice A" in text or "leasegrid" in text.lower()


def test_no_webview_and_no_wui_next():
    android = ROOT / "android"
    assert android.is_dir()
    blob = []
    for path in android.rglob("*"):
        if not path.is_file() or path.suffix not in SOURCE_SUFFIXES:
            continue
        if "build" in path.parts:
            continue
        blob.append(path.read_text(encoding="utf-8", errors="replace"))
    text = "\n".join(blob)
    assert "WebView" not in text
    assert "webkit" not in text.lower()
    assert "Open Tahoe" not in text
    assert "net.themark.leasegrid.sync" in text
    assert "leasegrid-sync-android-slice-a-debug.apk" in (ROOT / ".github/workflows/android-slice-a.yml").read_text(
        encoding="utf-8"
    )
