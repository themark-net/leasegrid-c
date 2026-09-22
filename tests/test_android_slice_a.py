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


def test_host_pytest_does_not_import_phone_reader():
    """Desktop CI must not import the embedded Foolscap stub."""
    for path in (ROOT / "tests").rglob("*.py"):
        if path.name == "test_android_slice_a.py":
            continue
        text = path.read_text(encoding="utf-8")
        assert "lg_intro" not in text, path
        assert "leasegrid_read" not in text, path
        assert "app/src/main/python" not in text, path


def test_dogfood_hooks_are_named():
    ui = (ROOT / "android/app/src/main/java/net/themark/leasegrid/sync/ui/SyncApp.kt").read_text(
        encoding="utf-8"
    )
    for tag in (
        "threat_ack",
        "invite_field",
        "join_button",
        "import_recovery_button",
        "passphrase_field",
        "import_confirm",
        "import_screen",
    ):
        assert f'"{tag}"' in ui, tag
    assert "clearAndSetSemantics" in ui
    assert "mergeDescendants = true" in ui
    assert "heightIn(min = 48.dp)" in ui
    assert "BringIntoViewRequester" in ui
    probe = (ROOT / "android/app/src/main/java/net/themark/leasegrid/sync/ui/DogfoodProbe.kt").read_text(
        encoding="utf-8"
    )
    assert "contentDescription = name" in probe
    assert "disabled()" in probe
    assert "joinControlEnabled" in probe
    assert "FocusRequester" in ui
    activity = (ROOT / "android/app/src/main/java/net/themark/leasegrid/sync/MainActivity.kt").read_text(
        encoding="utf-8"
    )
    assert "beginRecoveryImport" in activity
    assert "deliveryKey" in activity
    assert "postDelayed" in activity
    assert "EXTRA_INVITE" in activity
    assert "acknowledged = true" not in activity
    manifest = (ROOT / "android/app/src/main/AndroidManifest.xml").read_text(encoding="utf-8")
    assert "leasegrid-recovery" in manifest
    assert 'android:scheme="leasegrid"' in manifest
    note = (ROOT / "docs/ops/p4-android-dogfood.md").read_text(encoding="utf-8")
    assert "EXTRA_INVITE" in note
    assert "invite_field" in note
    assert "EXTRA_RECOVERY_FILE" in note
    assert "import_screen" in note


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
