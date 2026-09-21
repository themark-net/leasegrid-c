"""Invite share: URL + short code + i2p page. Not a wall of text, not Tahoe WUI."""

from __future__ import annotations

import pytest

from leasegrid_sync.backend import SyncError, validate_invite, validate_introducer_furl
from leasegrid_sync.invite import (
    DEFAULT_JOIN_ORIGIN,
    format_join_url,
    invite_page_html,
    parse_invite,
    qr_svg,
    share_url_for_nodedir,
)

GOOD_FURL = "pb://hashhashhash@127.0.0.1:45001/swissnumswiss"


def test_parse_wormhole_and_furl():
    p = parse_invite(" 7-Guitarist-Revenge ")
    assert p.kind == "code" and p.token == "7-guitarist-revenge"
    p = parse_invite(GOOD_FURL)
    assert p.kind == "furl" and p.token == GOOD_FURL and p.shares is None


def test_join_url_roundtrip_fragment_hides_furl_from_host():
    url = format_join_url(GOOD_FURL, shares=(2, 3, 3), origin="http://alice.i2p/join")
    assert url.startswith("http://alice.i2p/join#")
    assert "pb://" not in url.split("#", 1)[0]
    assert GOOD_FURL not in url.split("#", 1)[0]
    parsed = parse_invite(url)
    assert parsed.kind == "url"
    assert parsed.token == GOOD_FURL
    assert parsed.shares == (2, 3, 3)
    assert parsed.origin.startswith("http://alice.i2p")


def test_leasegrid_scheme_and_pasted_hash_only():
    url = format_join_url(GOOD_FURL, scheme="leasegrid")
    assert url.startswith("leasegrid:join#")
    assert parse_invite(url).token == GOOD_FURL
    frag = url.split("#", 1)[1]
    assert parse_invite("#" + frag).token == GOOD_FURL


def test_validate_invite_accepts_i2p_join_url():
    url = format_join_url(GOOD_FURL, origin=DEFAULT_JOIN_ORIGIN)
    assert validate_invite(url) == GOOD_FURL


def test_http_wui_still_rejected():
    with pytest.raises(SyncError) as exc:
        validate_introducer_furl("http://127.0.0.1:3456/")
    assert "does not use the Tahoe web UI" in exc.value.banner()
    with pytest.raises(SyncError) as exc:
        parse_invite("http://127.0.0.1:3456/")
    assert "web ui" in exc.value.banner().lower()


def test_join_url_without_fragment_fails_clearly():
    with pytest.raises(SyncError) as exc:
        parse_invite("http://alice.i2p/join")
    assert "full link" in exc.value.next_hint.lower() or "#" in exc.value.next_hint


def test_invite_page_is_self_contained_i2p_html():
    url = format_join_url(GOOD_FURL, origin="http://alice.i2p/join")
    html = invite_page_html(url, name="alice-friendnet")
    assert "<!doctype html>" in html.lower() or "<!DOCTYPE html>" in html
    assert "http://alice.i2p/join#" in html
    assert "leasegrid:join#" in html
    assert "Open in Leasegrid Sync" in html
    assert "cdn." not in html.lower()
    assert "<svg" in html.lower() or "data:image/svg" in html.lower()
    assert "Dropbox" not in html  # no lecture; one action


def test_qr_svg_encodes_the_url():
    url = format_join_url(GOOD_FURL)
    svg = qr_svg(url)
    assert "<svg" in svg.lower()
    assert len(svg) > 200


def test_share_url_for_nodedir_puts_furl_in_fragment(tmp_path, monkeypatch):
    nodedir = tmp_path / "tahoe"
    nodedir.mkdir()
    (nodedir / "tahoe.cfg").write_text(
        "[node]\n[client]\nintroducer.furl = %s\nshares.needed = 2\n"
        "shares.happy = 3\nshares.total = 3\n" % GOOD_FURL,
        encoding="utf-8",
    )
    monkeypatch.setenv("LEASEGRID_JOIN_ORIGIN", "http://alice.i2p/join")
    url = share_url_for_nodedir(nodedir)
    assert url.startswith("http://alice.i2p/join#")
    assert parse_invite(url).token == GOOD_FURL
    assert parse_invite(url).shares == (2, 3, 3)
    with pytest.raises(SyncError) as exc:
        share_url_for_nodedir(tmp_path / "missing")
    assert "No friendnet joined" in exc.value.banner()
