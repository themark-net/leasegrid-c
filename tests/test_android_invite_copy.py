"""Android invite copy asks for the join link, not a raw furl (#50).

Option 1 is copy only. The parser still names a pb:// furl in code.
A user string must not, and neither may a failed learn().
"""

from __future__ import annotations

import re
from pathlib import Path

INVITE = (
    Path(__file__).resolve().parents[1]
    / "android/app/src/main/java/net/themark/leasegrid/sync/invite/Invite.kt"
)
APP_PY = Path(__file__).resolve().parents[1] / "src" / "leasegrid_sync" / "app.py"
APP_MODEL = INVITE.parents[1] / "ui" / "AppModel.kt"
SESSION_FLOW = INVITE.parents[1] / "ui" / "SessionFlow.kt"
SYNC_APP = INVITE.parents[1] / "ui" / "SyncApp.kt"

# Exact tokens the code still uses. Any other literal that names them is copy.
_CODE_OK = frozenset({"pb://", "furl"})
_LITERAL = re.compile(r'"((?:\\.|[^"\\])*)"')
_FORBIDDEN = re.compile(r"pb://|furl|introducer|wormhole|friendnet|could not join", re.IGNORECASE)

# Design copy for #50 (exact).
_DESIGN = {
    "SHARE_INVITE": "Share invite",
    "SHOW_FULL_JOIN_LINK": "Show full join link (advanced)",
    "TITLE": "Join a shared folder",
    "BODY": "On your computer, click Share invite in Leasegrid Sync and tick Show full join link (advanced). "
    "Copy that link and paste it below.",
    "INPUT_HINT": "Paste the full join link",
    "EMPTY_MSG": "Paste the join link first.",
    "WORMHOLE_MSG": "That's a short code. This phone can't use short codes yet. On your computer, "
    "tick Show full join link (advanced), then paste that link here.",
    "GARBAGE_MSG": "That isn't a join link. On your computer, tick Show full join link (advanced), "
    "then copy and paste the whole link.",
    "WEB_URL_MSG": "That's the Sync web page address, not a join link. On your computer, "
    "tick Show full join link (advanced) and paste that link here.",
    "NO_ADDRESS_MSG": "That link is missing your computer's address. On your computer, "
    "tick Show full join link (advanced), then copy and paste the whole link.",
    "MALFORMED_MSG": "That join link is incomplete. On your computer, tick Show full join link (advanced), "
    "then copy and paste the whole link.",
    "JOIN_FAILED": "Couldn't reach your computer.",
    "JOIN_FAILED_NEXT": "Check that Leasegrid Sync is open on your computer and this phone is online, "
    "then tap Retry. If it still fails, copy the join link again from your computer and paste it here.",
    "REFRESH_FAILED_NEXT": "Check that Leasegrid Sync is open on your computer and this phone is online, then tap Retry.",
    "IMPORT_SAVED_MSG": "Folder names are on this phone. Couldn't reach your computer to finish.",
}

_PARSE_FAILS = ("EMPTY_MSG", "WORMHOLE_MSG", "GARBAGE_MSG", "WEB_URL_MSG", "NO_ADDRESS_MSG", "MALFORMED_MSG")


def _kotlin_const(text: str, name: str) -> str:
    match = re.search(r"const val %s =\s*\"((?:\\.|[^\"\\])*)\"" % name, text)
    assert match, name
    # Resolve $OTHER_CONST templates from the same file.
    return re.sub(r"\$([A-Z_]+)", lambda m: _kotlin_const(text, m.group(1)), match.group(1))


def _fun_body(text: str, signature: str) -> str:
    start = text.index(signature)
    end = text.find("\n    }\n", start)
    return text[start:end]


def _banned(literals: list[str]) -> list[str]:
    return [item for item in literals if item not in _CODE_OK and _FORBIDDEN.search(item)]


def test_banned_word_guard_catches_each_word():
    for bad in ("the furl", "pb://x", "Introducer", "wormhole", "this friendnet", "could not join", "Could Not Join"):
        assert _banned([bad]) == [bad], bad


def test_invite_kt_user_strings_pass_banned_word_guard():
    text = INVITE.read_text(encoding="utf-8")
    literals = _LITERAL.findall(text)
    assert any("join link" in item for item in literals)
    assert 'startsWith("pb://")' in text
    assert not _banned(literals)
    # Every InviteFail goes through a named constant (no inline copy).
    assert not re.search(r'InviteFail\(\s*"', text)


def test_learn_failure_strings_pass_banned_word_guard():
    """learn() shows nothing; SessionFlow owns the copy (#50 B2, N1).

    What SessionFlow shows is behavior-tested in SessionFlowTest.kt. learn() itself
    calls the Python grid (Chaquopy), so this one structural check stays a source scan.
    """
    model = APP_MODEL.read_text(encoding="utf-8")
    learn = _fun_body(model, "    private suspend fun learn(")
    assert not _banned(_LITERAL.findall(learn))
    assert "show(" not in learn and "FailBanner" not in learn
    flow = SESSION_FLOW.read_text(encoding="utf-8")
    assert not _banned(_LITERAL.findall(flow))
    # The import screen's learn() fail uses the same pair; no inline introducer copy anywhere.
    assert "introducer yet" not in model
    assert "Introducer is unreachable" not in model


def test_invite_copy_matches_design():
    text = INVITE.read_text(encoding="utf-8")
    for name, want in _DESIGN.items():
        assert _kotlin_const(text, name) == want, name
    assert "WORMHOLE_NEXT" not in text


def test_show_full_join_link_matches_desktop_label():
    """One pinned label, exactly the desktop share card checkbox (#50). Anchored on text."""
    label = _kotlin_const(INVITE.read_text(encoding="utf-8"), "SHOW_FULL_JOIN_LINK")
    desktop = re.findall(r'QtWidgets\.QCheckBox\("(Show full join link[^"]*)"\)', APP_PY.read_text(encoding="utf-8"))
    assert desktop == [label]


def test_share_invite_matches_desktop_button():
    label = _kotlin_const(INVITE.read_text(encoding="utf-8"), "SHARE_INVITE")
    desktop = re.findall(r'QtWidgets\.QPushButton\("(Share invite[^"]*)"\)', APP_PY.read_text(encoding="utf-8"))
    assert desktop == [label]


def test_parse_fails_have_no_next_line():
    text = INVITE.read_text(encoding="utf-8")
    assert _kotlin_const(text, "NO_NEXT") == ""
    for name in _PARSE_FAILS:
        assert "InviteFail(%s, NO_NEXT)" % name in text, name
    assert not re.search(r"InviteFail\([A-Z_]+, (?!NO_NEXT\))", text)
    ui = SYNC_APP.read_text(encoding="utf-8")
    assert "failNextLine(banner.next)" in ui
    assert 'Text("Next: ${banner.next}")' not in ui


def test_screen_uses_design_copy_and_join_keeps_pasted_text():
    ui = SYNC_APP.read_text(encoding="utf-8")
    for name in ("TITLE", "BODY", "INPUT_HINT"):
        assert "Invite.%s" % name in ui, name
    assert "paste invite" not in ui
    model = APP_MODEL.read_text(encoding="utf-8")
    body = _fun_body(model, "    fun join() {")
    assert "flow.join()" in body
    flow = SESSION_FLOW.read_text(encoding="utf-8")
    assert "Invite.attempt(" in flow
    # A fail leaves the pasted text in the field.
    assert "inviteText =" not in body
    assert "inviteText =" not in flow


def test_folders_screen_copy_never_says_paste():
    """Refresh and import fail on the Folders screen, which has no link field (#50 N1)."""
    text = INVITE.read_text(encoding="utf-8")
    for name in ("REFRESH_FAILED_NEXT", "IMPORT_SAVED_MSG"):
        low = _kotlin_const(text, name).lower()
        assert "paste" not in low and "join link" not in low, name


def test_learn_rethrows_cancellation_and_done_matches_join_button():
    """S1: a cancelled join paints nothing; keyboard Done uses the Join button's check.

    Source scans: AppModel.learn() needs Chaquopy and the Compose keyboard action needs a device.
    SessionFlowTest.aCancelledJoinPaintsNothing covers the flow side.
    """
    learn = _fun_body(APP_MODEL.read_text(encoding="utf-8"), "    private suspend fun learn(")
    assert re.search(r"catch \(exc: CancellationException\) \{\s*(//[^\n]*\s*)?throw exc", learn)
    assert learn.index("CancellationException") < learn.index("catch (exc: Exception)")
    ui = SYNC_APP.read_text(encoding="utf-8")
    assert "val joinOn = joinControlEnabled(model.acknowledged, model.inviteText, model.busy)" in ui
    assert "KeyboardActions(onDone = { if (joinOn) model.join() })" in ui
    assert "enabled = joinOn," in ui
    assert ui.index("val joinOn =") < ui.index("onDone")
