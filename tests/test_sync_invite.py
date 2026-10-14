"""Invite share: URL + short code + i2p page. Not a wall of text, not Tahoe WUI."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from leasegrid_sync.backend import SyncError, TahoeClient, validate_invite, validate_introducer_furl
from tests.qr_decode import INVITE_JOIN_TAHOE, decode_qr_png, write_executable
from leasegrid_sync.invite import (
    DEFAULT_JOIN_ORIGIN,
    InviteCodeSession,
    format_join_url,
    invite_code_from_output,
    invite_page_html,
    parse_invite,
    qr_png,
    qr_svg,
    share_url_for_nodedir,
    start_invite_code,
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
    pytest.importorskip("segno")
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
    pytest.importorskip("segno")
    url = format_join_url(GOOD_FURL)
    svg = qr_svg(url)
    assert "<svg" in svg.lower()
    assert len(svg) > 200


def test_invite_code_line_is_not_a_raw_furl():
    assert invite_code_from_output("Invite Code for client: 7-Orange-Tunnel\n") == "7-orange-tunnel"
    dumped = "Invite Code for client: pb://hashhashhash@127.0.0.1:45001/swissnumswiss\n"
    assert invite_code_from_output(dumped) == ""
    assert invite_code_from_output(GOOD_FURL) == ""


def test_qr_png_encodes_a_short_code():
    pytest.importorskip("segno")
    png = qr_png("7-orange-tunnel")
    assert png.startswith(b"\x89PNG")
    assert len(png) > 200


def _joined_nodedir(tmp_path: Path) -> Path:
    nodedir = tmp_path / "tahoe"
    nodedir.mkdir()
    (nodedir / "tahoe.cfg").write_text(
        "[node]\n[client]\nintroducer.furl = %s\nshares.needed = 2\n"
        "shares.happy = 3\nshares.total = 3\n" % GOOD_FURL,
        encoding="utf-8",
    )
    return nodedir


def test_start_invite_code_before_join_fails(tmp_path: Path):
    with pytest.raises(SyncError) as exc:
        start_invite_code(tmp_path / "missing")
    assert "join a friendnet first" in exc.value.banner()
    assert "pb://" not in exc.value.banner()


def _fake_tahoe_bin(tmp_path: Path, body: str) -> str:
    """A Tahoe stand-in that CreateProcess can start on Windows and POSIX.

    A shebang script is not a Win32 image (WinError 193). Windows gets a .bat
    that runs this interpreter, matching tests/test_sync_backend.py.
    """
    script = tmp_path / "fake-tahoe.py"
    # Shebang is how POSIX execs the file. Python ignores it when the .bat
    # launches this interpreter on Windows.
    script.write_text("#!/usr/bin/env python3\n" + body, encoding="utf-8")
    if os.name == "nt":
        bat = tmp_path / "fake-tahoe.bat"
        bat.write_text('@"%s" "%s" %%*\n' % (sys.executable, script), encoding="utf-8")
        return str(bat)
    script.chmod(0o755)
    return str(script)


def test_start_invite_code_reads_tahoe_stdout(tmp_path, monkeypatch):
    nodedir = _joined_nodedir(tmp_path)
    tahoe_bin = _fake_tahoe_bin(
        tmp_path,
        "import sys, time\n"
        "sys.stdout.write('Connecting to wormhole server\\n')\n"
        "sys.stdout.write('Invite Code for client: 7-orange-tunnel\\n')\n"
        "sys.stdout.flush()\n"
        "time.sleep(60)\n",
    )
    monkeypatch.setenv("LEASEGRID_WORMHOLE_SERVER", "ws://127.0.0.1:45040/v1")
    session = start_invite_code(nodedir, tahoe_bin=tahoe_bin, timeout=5)
    proc = session.proc
    try:
        assert session.code == "7-orange-tunnel"
        assert proc is not None and proc.poll() is None
        cmd = proc.args
        assert "--wormhole-server" in cmd
        assert "ws://127.0.0.1:45040/v1" in cmd
        assert "invite" in cmd
    finally:
        session.close()
    assert proc is not None and proc.poll() is not None


def test_start_invite_code_rejects_furl_only_output(tmp_path):
    nodedir = _joined_nodedir(tmp_path)
    tahoe_bin = _fake_tahoe_bin(
        tmp_path,
        "import sys\nsys.stdout.write(%r)\n" % (GOOD_FURL + "\n"),
    )
    with pytest.raises(SyncError) as exc:
        start_invite_code(nodedir, tahoe_bin=tahoe_bin, timeout=5)
    assert "short code" in exc.value.banner()
    assert GOOD_FURL not in exc.value.banner()


def test_start_invite_code_missing_tahoe(tmp_path, monkeypatch):
    nodedir = _joined_nodedir(tmp_path)
    monkeypatch.setattr("leasegrid_sync.backend.which_bin", lambda *_a, **_k: None)
    with pytest.raises(SyncError) as exc:
        start_invite_code(nodedir)
    assert "not installed" in exc.value.banner()


def test_injected_session_stays_alive_without_a_process():
    session = InviteCodeSession(code="7-orange-tunnel")
    assert session.alive()
    session.close()
    assert session.alive()


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


def test_garbled_invite_does_not_ask_for_a_raw_furl():
    """A mistyped code must not tell a person to paste an introducer furl."""
    with pytest.raises(SyncError) as exc:
        parse_invite("%%%not-a-code%%%")
    banner = exc.value.banner()
    assert "FAIL" in banner
    assert "pb://" not in banner
    assert "7-word-word" in banner
    with pytest.raises(SyncError) as exc:
        parse_invite("http://127.0.0.1:3456/")
    assert "pb://" not in exc.value.banner()
    assert "web ui" in exc.value.banner().lower()


def _gray_png(grid: list[list[int]]) -> bytes:
    """Encode a 0/1 grid (1 = dark) as an 8-bit gray PNG."""
    import struct
    import zlib

    height = len(grid)
    width = len(grid[0]) if height else 0
    raw = bytearray()
    for row in grid:
        raw.append(0)
        raw.extend(0 if cell else 255 for cell in row)

    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    return b"".join(
        (
            b"\x89PNG\r\n\x1a\n",
            chunk(b"IHDR", ihdr),
            chunk(b"IDAT", zlib.compress(bytes(raw))),
            chunk(b"IEND", b""),
        )
    )


def test_qr_png_decodes_to_the_payload_it_was_given():
    """Two different payloads must come back out of the image, not a fixed stamp."""
    pytest.importorskip("segno")
    short = "7-orange-tunnel"
    other = "9-other-words"
    assert decode_qr_png(qr_png(short)) == short
    assert decode_qr_png(qr_png(other)) == other
    assert decode_qr_png(qr_png(GOOD_FURL)) == GOOD_FURL


def test_scene_qr_decodes_until_a_finder_is_covered():
    """A grab is not a tight symbol. Covering one finder must fail the decode."""
    pytest.importorskip("segno")
    from tests.qr_decode import _png_gray

    symbol, width, height = _png_gray(qr_png("7-orange-tunnel"))
    canvas = [[0] * (width + 36) for _ in range(height + 48)]
    for y in range(height):
        canvas[16 + y][12 : 12 + width] = symbol[y]
    assert decode_qr_png(_gray_png(canvas)) == "7-orange-tunnel"
    for y in range(height - 36, height):
        for x in range(48):
            canvas[16 + y][12 + x] = (x + y) % 2
    with pytest.raises(ValueError):
        decode_qr_png(_gray_png(canvas))


def _welcome_after_node_url(client: TahoeClient):
    def welcome(timeout: float = 5.0):
        if not (client.nodedir / "node.url").is_file():
            raise SyncError("could not join this friendnet. Tahoe client is not reachable.")
        return {
            "introducers": {"statuses": ["Connected to tcp:127.0.0.1:45001 via tcp"]},
            "servers": [{"nickname": "storage-1", "connection_status": "connected"}],
        }

    return welcome


def test_generated_code_round_trips_after_bad_garbled_and_expired(tmp_path: Path):
    """Share prints a short code. Join rejects garbage, then that code connects."""
    pytest.importorskip("segno")
    inviter = _joined_nodedir(tmp_path)
    tahoe_bin = write_executable(tmp_path / "bin", INVITE_JOIN_TAHOE)
    session = start_invite_code(inviter, tahoe_bin=tahoe_bin, timeout=5)
    joiner = TahoeClient(
        nodedir=tmp_path / "joiner" / "tahoe",
        tahoe_bin=tahoe_bin,
        home=tmp_path / "joiner-home",
    )
    try:
        code = session.code
        assert code == "7-orange-tunnel"
        assert session.alive()
        assert decode_qr_png(qr_png(code)) == code
        assert "pb://" not in code

        with pytest.raises(SyncError) as exc:
            joiner.join_invite("%%%not-a-code%%%")
        assert "pb://" not in exc.value.banner()
        assert "short code" in exc.value.banner()
        assert not joiner.has_nodedir()

        with pytest.raises(SyncError) as exc:
            joiner.join_invite("3-bad-code")
        rejected = exc.value.banner()
        assert "not accepted" in rejected
        assert "expire" not in rejected.lower()
        assert "wormhole." not in rejected and "Error" not in rejected
        assert "Traceback" not in rejected
        assert not joiner.nodedir.exists()

        with pytest.raises(SyncError) as exc:
            joiner.join_invite("0-dead-code")
        expired = exc.value.banner()
        assert "expire" in expired.lower()
        assert "not accepted" not in expired.lower()
        assert expired != rejected
        assert "wormhole." not in expired and "Error" not in expired
        assert "Traceback" not in expired
        assert not joiner.nodedir.exists()

        assert session.alive()
        with patch.object(joiner, "welcome", side_effect=_welcome_after_node_url(joiner)):
            status = joiner.join_invite(code)
        assert status.state == "Connected"
        cfg = (joiner.nodedir / "tahoe.cfg").read_text(encoding="utf-8")
        assert "--join=%s" % code in cfg
        assert "--introducer" not in cfg.split("\n", 1)[0]
        assert GOOD_FURL not in cfg
    finally:
        session.close()
        joiner.stop()
