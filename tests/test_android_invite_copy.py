"""Android invite copy asks for the join link, not a raw furl (#50).

Option 1 is copy only. The parser still names a pb:// furl in code.
A user string must not.
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
SYNC_APP = INVITE.parents[1] / "ui" / "SyncApp.kt"

# Exact tokens the parser still uses. Any other literal that names them is copy.
_CODE_OK = frozenset({"pb://", "furl"})
_LITERAL = re.compile(r'"((?:\\.|[^"\\])*)"')
_FORBIDDEN = re.compile(r"pb://|furl|introducer|wormhole", re.IGNORECASE)

# Design copy for #50 (exact).
_DESIGN = {
    "TITLE": "Join a shared folder",
    "BODY": "On your computer, open the share card in Leasegrid Sync and choose Show full join link. "
    "Copy that link and paste it below.",
    "INPUT_HINT": "Paste the full join link",
    "WORMHOLE_MSG": "That's a short code. This phone can't use short codes yet. On your computer, "
    "choose Show full join link, then paste that link here.",
    "GARBAGE_MSG": "That isn't a join link. On your computer, choose Show full join link, "
    "then copy and paste the whole link.",
    "WEB_URL_MSG": "That's the Sync web page address, not a join link. On your computer, "
    "choose Show full join link and paste that link here.",
    "WORMHOLE_NEXT": "Couldn't join with that link. On your computer, choose Show full join link again, "
    "paste the new link here, and tap Retry.",
}


def _kotlin_const(text: str, name: str) -> str:
    match = re.search(r"const val %s =\s*\"((?:\\.|[^\"\\])*)\"" % name, text)
    assert match, name
    # Resolve $OTHER_CONST templates from the same file.
    return re.sub(r"\$([A-Z_]+)", lambda m: _kotlin_const(text, m.group(1)), match.group(1))


def test_invite_kt_user_strings_do_not_name_a_furl():
    text = INVITE.read_text(encoding="utf-8")
    literals = _LITERAL.findall(text)
    assert any("join link" in item for item in literals)
    assert 'startsWith("pb://")' in text
    hits = [item for item in literals if item not in _CODE_OK and _FORBIDDEN.search(item)]
    assert not hits
    assert "That join link is malformed." in text
    assert "get a fresh full join link from your inviter; check network; Retry." in text


def test_invite_copy_matches_design():
    text = INVITE.read_text(encoding="utf-8")
    for name, want in _DESIGN.items():
        assert _kotlin_const(text, name) == want, name


def test_show_full_join_link_matches_desktop_label():
    """One pinned label, checked against the desktop share card (#50).

    Desktop is QCheckBox("Show full join link (advanced)"). Design's Android
    copy names it without the "(advanced)" suffix.
    """
    label = _kotlin_const(INVITE.read_text(encoding="utf-8"), "SHOW_FULL_JOIN_LINK")
    assert label == "Show full join link"
    app = APP_PY.read_text(encoding="utf-8")
    match = re.search(r'QtWidgets\.QCheckBox\("(%s[^"]*)"\)' % re.escape(label), app)
    assert match, "desktop has no checkbox labelled %r" % label
    assert match.group(1) in (label, label + " (advanced)")
    assert 'QPushButton("Share invite")' in app


def test_screen_uses_design_copy_and_join_keeps_pasted_text():
    ui = SYNC_APP.read_text(encoding="utf-8")
    for name in ("TITLE", "BODY", "INPUT_HINT"):
        assert "Invite.%s" % name in ui, name
    assert "paste invite" not in ui
    model = APP_MODEL.read_text(encoding="utf-8")
    start = model.index("    fun join() {")
    body = model[start : model.index("\n    fun ", start + 1)]
    assert "Invite.attempt(" in body
    # A fail leaves the pasted text in the field.
    assert "inviteText =" not in body
