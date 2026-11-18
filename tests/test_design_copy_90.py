"""Design's final copy for cut join links and Add folder failures (#90 slice C).

Design wrote these strings (PM, 2026-11-17 9:51pm PT). They show in the
desktop window and the CLI exactly as written. The window and the CLI never
name an issue number, never say "furl", and these messages never say "Retry".
"""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import patch
from urllib.parse import quote

import pytest

from leasegrid_sync import backend as backend_mod
from leasegrid_sync.backend import ConnectionStatus, SyncError, validate_introducer_furl
from leasegrid_sync.cli import main
from leasegrid_sync.invite import parse_invite
from tests.test_sync_backend import _mf_api_ready, _poison_http

CUT_MSG = "That join link is cut off."
CUT_NEXT = "Ask the person who invited you to send the whole link again, then paste all of it here."
HOSTS_MSG = "Can't add a folder yet. Only %d of %d hosts are connected."
HOSTS_NEXT = "Wait until Hosts shows %d connected, then click Add folder again."
FAIL_MSG = "Couldn't add the folder."
FAIL_NEXT = "Wait a minute, then click Add folder again."

# Fixture links with a piece missing (same shapes as test_sync_cut_join_link).
CUT = [
    "pb://hashhashhash@127.0.0.1:45001/",
    "pb://hashhashhash@127.0.0.1:45001/cut",
    "pb://@127.0.0.1:45001/swissnumswiss",
    "pb://hashhashhash/swissnumswiss",
    "pb://hashhashhash@extra@127.0.0.1:45001/swissnumswiss",
]
# Links that lost the part after "#" in chat or mail.
NO_FRAGMENT = ["http://leasegrid.i2p/join", "http://leasegrid.i2p/join#", "leasegrid:join", "#n=2&h=3"]

BANNED = ("furl", "known issue #", "#30", "Retry")
ISSUE_NUMBER = re.compile(r"#\d+")


def _forms(furl: str) -> list[str]:
    frag = "v=1&i=%s&n=2&h=3&t=3" % quote(furl, safe="")
    return [furl, "http://leasegrid.i2p/join#" + frag, "leasegrid:join#" + frag]


def assert_clean(text: str) -> None:
    for word in BANNED:
        assert word.lower() not in text.lower(), (word, text)
    assert not ISSUE_NUMBER.search(text), text


def _connected(n: int) -> ConnectionStatus:
    return ConnectionStatus(
        state="Connected", detail="introducer up · %d storage" % n, introducer_ok=True, servers_connected=n
    )


@pytest.mark.parametrize("furl", CUT)
def test_cut_join_link_uses_designs_words_in_every_form(furl: str):
    for form in _forms(furl):
        with pytest.raises(SyncError) as exc:
            parse_invite(form)
        assert exc.value.message == CUT_MSG, form
        assert exc.value.next_hint == CUT_NEXT, form
        assert_clean(exc.value.banner())


@pytest.mark.parametrize("text", NO_FRAGMENT)
def test_join_link_missing_its_invite_part_is_a_cut_link(text: str):
    with pytest.raises(SyncError) as exc:
        parse_invite(text)
    assert (exc.value.message, exc.value.next_hint) == (CUT_MSG, CUT_NEXT), text


def test_cli_join_prints_designs_cut_link_words(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setenv("LEASEGRID_SYNC_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("PATH", str(tmp_path / "empty-bin"))
    monkeypatch.delenv("LEASEGRID_TAHOE_BIN", raising=False)
    code = main(["--join", _forms(CUT[1])[1], "--nodedir", str(tmp_path / "tahoe")])
    err = capsys.readouterr().err
    assert code == 1
    assert CUT_MSG in err
    assert "Next: " + CUT_NEXT in err
    assert_clean(err)
    assert not (tmp_path / "tahoe").exists()


def test_cli_help_does_not_say_furl(capsys):
    with pytest.raises(SystemExit):
        main(["--help"])
    assert "furl" not in capsys.readouterr().out.lower()


def test_other_invite_errors_do_not_say_furl():
    for text in ("", "   ", "https://example.com/", "pb:/nope"):
        with pytest.raises(SyncError) as exc:
            validate_introducer_furl(text)
        assert "furl" not in exc.value.banner().lower(), text


def test_too_few_hosts_shows_live_counts_in_designs_words():
    from leasegrid_sync.app import hosts_short_for_add

    for have, need in ((0, 3), (1, 3), (2, 5)):
        err = hosts_short_for_add(_connected(have), need)
        assert err is not None
        assert err.message == HOSTS_MSG % (have, need)
        assert err.next_hint == HOSTS_NEXT % need
        assert_clean(err.banner())
    assert hosts_short_for_add(_connected(3), 3) is None


def test_add_folder_500_is_the_generic_pair(tmp_path: Path):
    ctl = _mf_api_ready(tmp_path)
    err = ctl._http_failure(_poison_http(500))
    assert (err.message, err.next_hint) == (FAIL_MSG, FAIL_NEXT)
    assert err.http_status == 500
    assert_clean(err.banner())


def test_other_http_errors_keep_their_own_words(tmp_path: Path):
    ctl = _mf_api_ready(tmp_path)
    err = ctl._http_failure(_poison_http(502))
    assert err.message == "Magic Folder API error (502)."


def test_refresh_500_does_not_say_add_or_name_an_issue(tmp_path: Path, monkeypatch):
    ctl = _mf_api_ready(tmp_path)

    def boom(req, timeout=10):
        raise _poison_http(500)

    monkeypatch.setattr(backend_mod.urllib.request, "urlopen", boom)
    with patch.object(ctl, "ensure_running", return_value=None):
        with pytest.raises(SyncError) as listed:
            ctl.list_folders()
    blob = listed.value.banner()
    assert "add" not in listed.value.message.lower()
    assert_clean(blob)


def test_banned_words_never_reach_these_messages():
    """Guard: every string Design wrote for #90, and every banner built from them."""
    from leasegrid_sync import app as app_mod

    strings = [
        backend_mod.CUT_LINK_MSG,
        backend_mod.CUT_LINK_NEXT,
        backend_mod.ADD_FOLDER_FAIL_MSG,
        backend_mod.ADD_FOLDER_FAIL_NEXT,
        backend_mod.REFRESH_FAIL_MSG,
        backend_mod.REFRESH_FAIL_NEXT,
        app_mod.ADD_FOLDER_HOSTS_MSG,
        app_mod.ADD_FOLDER_HOSTS_NEXT,
    ]
    for text in strings:
        assert_clean(text)
    assert_clean(SyncError(backend_mod.CUT_LINK_MSG, backend_mod.CUT_LINK_NEXT).banner())
    # The guard itself catches each banned word.
    for bad in ("Invite furl is malformed.", "This is known issue #12.", "see #30", "then Retry."):
        with pytest.raises(AssertionError):
            assert_clean(bad)
