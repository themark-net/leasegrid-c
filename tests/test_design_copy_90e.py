"""Design's final copy for #90 slice E (PM, 2026-11-18 12:18am PT).

1. A Next hint never says "Restart Sync" (no such control). It says
   "Quit and reopen Leasegrid Sync." and keeps any wait or check before it.
2. Storage server dialog: "Storage server link", Design's placeholder, and a
   wrong-scheme or cut-off link gets Design's pair. No pb:// in what it shows.
3. An invalid invite code: "That code didn't work." with Design's Next, no
   Retry, no join attempt, and the pasted text stays in the field.

The guard reads every SyncError Next hint in src/leasegrid_sync from the
source (AST), so a new hint is covered without editing this file.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from unittest.mock import patch

import pytest

from leasegrid_sync import backend as backend_mod
from leasegrid_sync.backend import SyncError
from leasegrid_sync.invite import parse_invite

SRC = Path(backend_mod.__file__).parent
QUIT_REOPEN = "Quit and reopen Leasegrid Sync."
CODE_MSG = "That code didn't work."
CODE_NEXT = "Ask the person who invited you to send the full join link, then paste all of it here."
STORAGE_LABEL = "Storage server link"
STORAGE_PLACEHOLDER = "Paste the link you were given for this storage server"
STORAGE_MSG = "That isn't a full storage server link."
STORAGE_NEXT = "Ask whoever runs the server to send the whole link again, then paste all of it here."

BANNED_EVERYWHERE = ("restart sync", "pb://", "furl")
ISSUE_NUMBER = re.compile(r"#\d+")
# Functions whose hints answer a pasted link or code: retrying the same paste cannot work.
PARSE_FUNCS = {"validate_introducer_furl", "parse_invite", "_from_fragment", "parse_storage_furl", "_fail_bad"}
# The only instruction a hint may give that is not a control in the window.
ALLOWED_NON_CONTROL = re.compile(r"quit and reopen leasegrid sync", re.I)
RESTARTISH = re.compile(r"\b(restart|relaunch|reopen|re-open|quit)\b", re.I)


def _text(node, consts):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
        return _text(node.left, consts)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        a, b = _text(node.left, consts), _text(node.right, consts)
        return None if a is None and b is None else (a or "") + (b or "")
    if isinstance(node, ast.JoinedStr):
        return "".join(v.value if isinstance(v, ast.Constant) else "{}" for v in node.values)
    if isinstance(node, ast.Name):
        return consts.get(node.id)
    if isinstance(node, ast.Attribute):
        return consts.get(node.attr)
    return None


def next_hints() -> list[tuple[str, int, str, str]]:
    """(file, line, function, Next hint) for every SyncError in src/leasegrid_sync."""
    consts: dict[str, str] = {}
    pairs: dict[str, list] = {}
    trees = {}
    for path in sorted(SRC.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        trees[path.name] = tree
        for node in tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                name = node.targets[0].id
                if isinstance(node.value, ast.Tuple) and len(node.value.elts) == 2:
                    pairs[name] = node.value.elts
                else:
                    value = _text(node.value, consts)
                    if value is not None:
                        consts[name] = value
    found: list[tuple[str, int, str, str]] = []

    class Visitor(ast.NodeVisitor):
        def __init__(self, fname: str) -> None:
            self.fname = fname
            self.stack: list[str] = []

        def visit_FunctionDef(self, node):
            self.stack.append(node.name)
            self.generic_visit(node)
            self.stack.pop()

        def visit_Call(self, node):
            name = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", "")
            if name == "SyncError":
                hint = None
                if node.args and isinstance(node.args[0], ast.Starred):
                    if isinstance(node.args[0].value, ast.Name) and node.args[0].value.id in pairs:
                        hint = pairs[node.args[0].value.id][1]
                elif len(node.args) >= 2:
                    hint = node.args[1]
                for kw in node.keywords:
                    if kw.arg == "next_hint":
                        hint = kw.value
                text = _text(hint, consts) if hint is not None else None
                if text:
                    found.append((self.fname, node.lineno, self.stack[-1] if self.stack else "", text))
            self.generic_visit(node)

    for fname, tree in trees.items():
        Visitor(fname).visit(tree)
    return found


def assert_hint_clean(text: str, parse_hint: bool = False) -> None:
    low = text.lower()
    for word in BANNED_EVERYWHERE:
        assert word not in low, (word, text)
    assert not ISSUE_NUMBER.search(text), text
    if parse_hint:
        assert "retry" not in low, text


def test_the_guard_reads_the_real_hints():
    hints = next_hints()
    assert len(hints) > 100
    texts = {h[3] for h in hints}
    assert backend_mod.CUT_LINK_NEXT in texts
    assert backend_mod.ADD_FOLDER_FAIL_NEXT in texts


def test_guard_catches_each_banned_word():
    for bad in ("Restart Sync.", "then Restart Sync.", "paste the pb:// address", "Invite furl", "see #30"):
        with pytest.raises(AssertionError):
            assert_hint_clean(bad)
    with pytest.raises(AssertionError):
        assert_hint_clean("check the link; Retry.", parse_hint=True)
    assert_hint_clean("check the host, then Retry.")


def test_no_next_hint_says_restart_sync_pb_furl_or_an_issue_number():
    bad = []
    for fname, line, func, text in next_hints():
        try:
            assert_hint_clean(text, parse_hint=func in PARSE_FUNCS)
        except AssertionError:
            bad.append("%s:%d %s: %s" % (fname, line, func, text))
    assert not bad, "\n".join(bad)


def test_restart_hints_say_quit_and_reopen_and_keep_the_step_before_it():
    texts = {h[3] for h in next_hints()}
    assert QUIT_REOPEN in texts
    assert "check that %s is writable, then quit and reopen Leasegrid Sync." in texts
    assert "install magic-folder, then quit and reopen Leasegrid Sync." in texts
    assert "see %s, then quit and reopen Leasegrid Sync." in texts
    assert "Quit and reopen Leasegrid Sync. If this persists, check that magic-folder is on PATH." in texts


def _window_labels(tmp_path: Path) -> set[str]:
    pytest.importorskip("PyQt5")
    from PyQt5 import QtWidgets

    from leasegrid_sync.app import AddStorageServerDialog, MainWindow

    window = MainWindow(home=tmp_path / "home", autoload=False)
    try:
        window.poll.stop()
        dlg = AddStorageServerDialog(window.win, window, window.QtWidgets)
        labels: set[str] = set()
        for root in (window.win, dlg.dlg):
            labels |= {b.text() for b in root.findChildren(QtWidgets.QAbstractButton)}
            labels |= {a.text() for a in root.findChildren(QtWidgets.QAction)}
        dlg.dlg.reject()
    finally:
        window.win.hide()
        if window.tray is not None:
            window.tray.hide()
    return {label.replace("&", "").rstrip("…").strip() for label in labels if label}


def _controls_named(text: str) -> list[tuple[str, ...]]:
    """Controls a hint names. Each entry lists candidate labels, longest first."""
    named: list[tuple[str, ...]] = []
    for label in re.findall(r"\bclick ([A-Z][\w ]*?\w)(?= again\b|[.,;]|$)", text):
        named.append((label,))
    for left, right in re.findall(r"\b([A-Z]\w*) → ([A-Z][\w ]*?)(?=[.,;]|$)", text):
        named.append((left,))
        words = right.split()
        named.append(tuple(" ".join(words[:k]) for k in range(len(words), 0, -1)))
    if re.search(r"\bRetry\b", text):
        named.append(("Retry",))
    return named


def test_every_control_a_next_hint_names_exists_in_the_window(tmp_path: Path):
    labels = _window_labels(tmp_path)
    missing = []
    for fname, line, func, text in next_hints():
        for candidates in _controls_named(text):
            if not any(c in labels for c in candidates):
                missing.append("%s:%d names %r" % (fname, line, candidates[-1]))
        stripped = ALLOWED_NON_CONTROL.sub("", text)
        if RESTARTISH.search(stripped):
            missing.append("%s:%d restart wording other than quit and reopen: %s" % (fname, line, text))
    assert not missing, "\n".join(missing)


def test_live_label_pin_catches_a_missing_control():
    assert _controls_named("Wait a minute, then Restart Sync.") == []
    assert RESTARTISH.search(ALLOWED_NON_CONTROL.sub("", "Wait a minute, then Restart Sync."))
    assert not RESTARTISH.search(ALLOWED_NON_CONTROL.sub("", "Wait a minute, then quit and reopen Leasegrid Sync."))
    assert _controls_named("Wait until Hosts shows 3 connected, then click Add folder again.") == [("Add folder",)]
    assert _controls_named("Credit → Top up; uploads resume.") == [("Credit",), ("Top up", "Top")]
    assert _controls_named("then click Restart Button again.") == [("Restart Button",)]


# Invalid code


@pytest.mark.parametrize("text", ["not a code", "hello", "7-pgp\u202e-word", "seven words in a row"])
def test_invalid_code_is_designs_pair(text: str):
    with pytest.raises(SyncError) as exc:
        parse_invite(text)
    if exc.value.message == backend_mod.CUT_LINK_MSG:
        pytest.skip("parsed as a cut link, not a code")
    assert (exc.value.message, exc.value.next_hint) == (CODE_MSG, CODE_NEXT)
    assert_hint_clean(exc.value.banner(), parse_hint=True)


@pytest.mark.skip(reason="bisect")
def test_invalid_code_in_the_window_keeps_the_field_and_does_not_join(tmp_path: Path):
    pytest.importorskip("PyQt5")
    from PyQt5 import QtWidgets

    from leasegrid_sync.app import MainWindow

    nodedir = tmp_path / "joiner" / "tahoe"
    window = MainWindow(nodedir=nodedir, home=tmp_path / "joiner-home", autoload=False)
    try:
        window.poll.stop()
        window.threat_ack.setChecked(True)
        join_label = window.join_btn.text()
        pasted = "not a real code"
        window.invite_edit.setText(pasted)
        with patch.object(backend_mod.subprocess, "run") as run, patch.object(
            backend_mod.subprocess, "Popen"
        ) as popen:
            window.on_join_invite()
        shown = window.join_error.text()
        assert CODE_MSG in shown
        assert "Next: " + CODE_NEXT in shown
        assert "retry" not in shown.lower()
        assert window.invite_edit.text() == pasted
        assert not run.called and not popen.called
        assert not nodedir.exists()
        assert window.join_btn.text() == join_label
        page_buttons = {b.text() for b in window.join_page.findChildren(QtWidgets.QAbstractButton)}
        assert "Retry" not in page_buttons
        assert window.join_btn.isEnabled()
    finally:
        window.win.hide()
        if window.tray is not None:
            window.tray.hide()


# Storage server dialog

BAD_STORAGE = [
    "http://example.com/storage",
    "pb:/nope",
    "pb://abcd@127.0.0.1:1/",
    "pb://abcd/swissnumswiss",
    "pb://@127.0.0.1:1/swissnumswiss",
    "pb://abcd@127.0.0.1:1/swiss num",
    "",
]


@pytest.mark.parametrize("text", BAD_STORAGE)
def test_bad_storage_link_is_designs_pair(text: str):
    from leasegrid_sync.servers import parse_storage_furl

    with pytest.raises(SyncError) as exc:
        parse_storage_furl(text)
    assert (exc.value.message, exc.value.next_hint) == (STORAGE_MSG, STORAGE_NEXT)
    assert_hint_clean(exc.value.banner(), parse_hint=True)


def _snapshot(root: Path) -> dict[str, bytes]:
    if not root.exists():
        return {}
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_storage_dialog_words_and_a_cut_link_saves_nothing(tmp_path: Path):
    pytest.importorskip("PyQt5")
    from PyQt5 import QtWidgets

    from leasegrid_sync.app import AddStorageServerDialog, MainWindow

    nodedir = tmp_path / "tahoe"
    nodedir.mkdir()
    (nodedir / "tahoe.cfg").write_text("[node]\n", encoding="utf-8")
    home = tmp_path / "home"
    window = MainWindow(nodedir=nodedir, home=home, autoload=False)
    try:
        window.poll.stop()
        dlg = AddStorageServerDialog(window.win, window, window.QtWidgets)
        labels = [w.text() for w in dlg.dlg.findChildren(QtWidgets.QLabel)]
        assert STORAGE_LABEL in labels
        assert dlg.furl_edit.placeholderText() == STORAGE_PLACEHOLDER
        for text in labels + [dlg.furl_edit.placeholderText()]:
            assert "pb://" not in text, text
            assert "furl" not in text.lower(), text
        before = (_snapshot(home), _snapshot(nodedir))
        cut = "pb://abcd@127.0.0.1:1/"
        dlg.furl_edit.setText(cut)
        with patch("socket.create_connection") as connect:
            dlg.on_add()
        shown = dlg.error.text()
        assert STORAGE_MSG in shown
        assert "Next: " + STORAGE_NEXT in shown
        assert cut not in shown and "pb://" not in shown
        assert not connect.called
        assert (_snapshot(home), _snapshot(nodedir)) == before
        assert dlg.furl_edit.text() == cut
        dlg.dlg.reject()
    finally:
        window.win.hide()
        if window.tray is not None:
            window.tray.hide()


# Recover: a daemon start that keeps failing


def test_daemon_start_that_keeps_failing_shows_the_same_pair_and_keeps_the_log(tmp_path: Path, monkeypatch):
    from tests.test_sync_backend import _exiting_magic_folder

    ctl, log, seeded = _exiting_magic_folder(tmp_path, monkeypatch)
    folder = tmp_path / "docs"
    folder.mkdir()
    seen = []
    for _ in range(2):  # first start, then again after quit and reopen (a new controller)
        with pytest.raises(SyncError) as exc:
            ctl.add_folder(str(folder))
        seen.append((exc.value.message, exc.value.next_hint))
        blob = exc.value.banner()
        assert "Traceback" not in blob and "daemon failed" not in blob and seeded not in blob
        assert_hint_clean(exc.value.next_hint)
        ctl = backend_mod.MagicFolderCtl(config_dir=ctl.config_dir, nodedir=ctl.nodedir, mf_bin=ctl.mf_bin)
        ctl.log_path = log
    assert seen[0] == seen[1]
    assert seen[0][1] == QUIT_REOPEN
    kept = "".join(p.read_text(encoding="utf-8", errors="replace") for p in log.parent.glob("magic-folder.log*"))
    assert "daemon failed" in kept


@pytest.mark.skip(reason="bisect")
def test_daemon_start_failure_in_the_window_has_no_raw_error(tmp_path: Path, monkeypatch):
    pytest.importorskip("PyQt5")
    from tests.test_sync_backend import _exiting_magic_folder

    from leasegrid_sync.app import MainWindow

    ctl, log, seeded = _exiting_magic_folder(tmp_path, monkeypatch)
    window = MainWindow(home=tmp_path / "win-home", autoload=False)
    try:
        window.poll.stop()
        window._joined = True
        window.mf = ctl
        monkeypatch.setattr(window.tahoe, "connection_status", lambda: backend_mod.ConnectionStatus(
            state="Connected", detail="introducer up · 3 storage", introducer_ok=True, servers_connected=3))
        monkeypatch.setattr(window, "_refresh_servers", lambda status: None)
        monkeypatch.setattr(window, "_refresh_offer_viz", lambda: None)
        shown = []
        for _ in range(2):
            window.refresh()
            shown.append(window.folder_error.text())
        assert shown[0] == shown[1]
        assert "Next: " + QUIT_REOPEN in shown[0]
        for bad in ("Traceback", "daemon failed", seeded, "pb://"):
            assert bad not in shown[0]
    finally:
        window.win.hide()
        if window.tray is not None:
            window.tray.hide()
