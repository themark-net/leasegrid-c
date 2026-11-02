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
    "IMPORT_SAVED_MSG": "Saved on this phone. Couldn't reach your computer to finish.",
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


# Em dash and en dash. A colon is the plain stand-in on the phone.
_DASH = re.compile("[\u2014\u2013]")
# JSON field name. It is not copy. Anything else that squashes to the word is.
_CODE_INTRODUCER_KEYS = frozenset({"introducer_furl"})


def _joined_literals(source: str) -> list[str]:
    """Literal contents. `"a" + "b"` with only whitespace around + is one piece."""
    pieces: list[str] = []
    ends: list[int] = []
    for match in _LITERAL.finditer(source):
        content = match.group(1)
        gap = source[ends[-1] : match.start()] if pieces else ""
        if pieces and re.fullmatch(r"\s*\+\s*", gap):
            pieces[-1] = pieces[-1] + content
            ends[-1] = match.end()
        else:
            pieces.append(content)
            ends.append(match.end())
    return pieces


def _squash_introducer(text: str) -> str:
    """Drop the breaks a split 'introducer' hides behind."""
    text = text.replace("\\n", "\n").replace("\\r", "\n").replace("\\t", " ")
    text = re.sub(r"-\s*", "", text)
    text = re.sub(r"\s+", "", text)
    return text.lower()


def _banned(literals: list[str]) -> list[str]:
    hits = []
    for item in literals:
        if item in _CODE_OK or item in _CODE_INTRODUCER_KEYS:
            continue
        split = "introducer" in _squash_introducer(item)
        if _DASH.search(item) or _FORBIDDEN.search(item) or split:
            hits.append(item)
    return hits


def _banned_source(source: str) -> list[str]:
    return _banned(_joined_literals(source))


def test_banned_word_guard_catches_each_word():
    samples = (
        "the furl",
        "pb://x",
        "Introducer",
        "wormhole",
        "this friendnet",
        "could not join",
        "Could Not Join",
        "em \u2014 dash",
        "en \u2013 dash",
    )
    for bad in samples:
        assert _banned([bad]) == [bad], bad


def test_split_introducer_misses_the_exact_scan_and_the_guard_catches_it():
    """K3c splits the word. The old per-literal scan misses it. The guard does not."""
    samples = (
        '"Intro" + "ducer"',
        '"intro-" +\n"ducer"',
        '"INTRO" + "DUCER"',
        '"intro " + " ducer"',
        '"intro-\\nducer"',
    )
    for sample in samples:
        exact = [
            item
            for item in _LITERAL.findall(sample)
            if re.search(r"introducer", item, re.IGNORECASE)
        ]
        assert exact == [], sample
        assert _banned_source(sample), sample


def test_invite_kt_user_strings_pass_banned_word_guard():
    text = INVITE.read_text(encoding="utf-8")
    literals = _LITERAL.findall(text)
    assert any("join link" in item for item in literals)
    assert 'startsWith("pb://")' in text
    assert not _banned_source(text)
    # Every InviteFail goes through a named constant (no inline copy).
    assert not re.search(r'InviteFail\(\s*"', text)


def test_learn_failure_strings_pass_banned_word_guard():
    """learn() shows nothing; SessionFlow owns the copy (#50 B2, N1).

    What SessionFlow shows is behavior-tested in SessionFlowTest.kt. learn() itself
    calls the Python grid (Chaquopy), so this one structural check stays a source scan.
    """
    model = APP_MODEL.read_text(encoding="utf-8")
    learn = _fun_body(model, "    private suspend fun learn(")
    assert not _banned_source(learn)
    assert "show(" not in learn and "FailBanner" not in learn
    flow = SESSION_FLOW.read_text(encoding="utf-8")
    assert not _banned_source(flow)
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


def _invite_section(ui: str) -> str:
    """SyncApp's Invite/join section: from the Invite title to the Welcome fail card."""
    start = ui.index("    Text(Invite.TITLE")
    return ui[start : ui.index("    FailCard(model)", start)]


def _flow_host(model: str) -> str:
    start = model.index("object : FlowHost {")
    end = model.index("\n    })", start)
    return model[start:end]


def test_appmodel_flowhost_delegates_exactly():
    """SessionFlow's fake host does not catch a broken AppModel delegation.

    Tester mutants M4c, J4a, J1c, N4b and N4d survived because these one-liners
    were untested. The bodies were not in the repo, so each delegation is pinned.
    """
    host = _flow_host(APP_MODEL.read_text(encoding="utf-8"))
    # J1c: the setter stores the typed text. Clearing it is a different line.
    assert "set(value) { this@AppModel.inviteText = value }" in host
    assert 'inviteText = ""' not in host
    assert "get() = this@AppModel.session" in host
    # J4a: launch is runGrid with the same label and block.
    assert (
        "override fun launch(label: String, block: suspend () -> Unit) = runGrid(label, block)"
        in host
    )
    # N4b: learn returns the model's result, not null.
    assert (
        "override suspend fun learn(furl: String): List<ServerRef>? = this@AppModel.learn(furl)"
        in host
    )
    # N4d: save writes the store, adopts the session, and opens Folders.
    assert "store.save(next)" in host
    assert "this@AppModel.session = next" in host
    assert "place = Place.Folders" in host
    # M4c: show forwards the Retry action. An empty lambda would drop it.
    assert (
        "override fun show(banner: FailBanner, again: () -> Unit) = this@AppModel.show(banner, again)"
        in host
    )
    assert "show(banner, {})" not in host


def test_syncapp_invite_section_passes_banned_word_guard():
    """#50 surfaces in SyncApp: title, body, field, Join button, import link."""
    section = _invite_section(SYNC_APP.read_text(encoding="utf-8"))
    literals = _LITERAL.findall(section)
    assert "Joining…" in literals
    assert not _banned_source(section)
    # The Join button reads the Invite title (Design: "Join a shared folder").
    assert 'label = if (model.busy) "Joining…" else Invite.TITLE,' in section
    assert _kotlin_const(INVITE.read_text(encoding="utf-8"), "TITLE") == "Join a shared folder"


def test_syncapp_passes_banned_word_guard():
    """Every string literal in SyncApp.kt, not only the Invite section.

    The threat card, empty Folders line, remove sheet, discard sheet, and
    transport line used to say friendnet. A regression puts the word back.
    Chips and recovery copy live in other files and are not this scan.
    """
    text = SYNC_APP.read_text(encoding="utf-8")
    literals = _LITERAL.findall(text)
    assert not _banned_source(text), _banned_source(text)
    joined = (
        "Joined. Import a recovery key from Leasegrid Sync on your computer to see folder names. "
        "This phone cannot invent folders."
    )
    trust = "Shared folder trust: unpaid by default. This is not Dropbox-the-company and not Filecoin."
    assert trust in literals
    assert joined in literals
    assert "It is not in the shared folder yet." in literals
    assert "Remove ${sheet.name} from ${sheet.folder} for every Sync computer?" in literals
    assert "the storage address this phone learned" in text


def test_introducer_unreachable_is_never_on_screen():
    """The grid's introducer text only reaches Log.w (#50 B2).

    A contiguous phrase search misses K3c. This scan joins concatenated
    literals and ignores case, whitespace, and a break hyphen.
    """
    main_java = INVITE.parents[5]  # android/app/src/main/java
    hits = []
    for path in main_java.rglob("*.kt"):
        found = [
            item
            for item in _banned_source(path.read_text(encoding="utf-8"))
            if "introducer" in _squash_introducer(item)
        ]
        hits.extend(f"{path.relative_to(main_java)}: {item}" for item in found)
    assert hits == [], hits
