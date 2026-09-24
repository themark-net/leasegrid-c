"""Shareable friendnet invite: short code, QR, join URL, static i2p page.

Primary share is a one-time ``tahoe invite`` code (plus a QR of that code).
The introducer furl stays inside the advanced join-link fragment so an eepsite
never has to see it, and it is not the share string a buyer copies.
"""

from __future__ import annotations

import html
import io
import os
import re
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, quote, urlencode, urlparse

from .backend import SyncError, is_wormhole_code, validate_introducer_furl

# Tahoe 1.20 prints this once the inviter is parked on the relay.
_INVITE_CODE_LINE = re.compile(r"Invite Code for client:\s*(\S+)", re.IGNORECASE)
INVITE_CODE_TIMEOUT = 20.0

DEFAULT_JOIN_ORIGIN = "http://leasegrid.i2p/join"
NATIVE_SCHEME = "leasegrid:join"


@dataclass
class ParsedInvite:
    kind: str  # code | furl | url
    token: str  # wormhole code or pb:// furl (what Tahoe consumes)
    shares: Optional[tuple[int, int, int]] = None
    origin: str = ""
    url: str = ""


def join_origin() -> str:
    raw = (os.environ.get("LEASEGRID_JOIN_ORIGIN") or DEFAULT_JOIN_ORIGIN).strip()
    return raw.rstrip("/") or DEFAULT_JOIN_ORIGIN


def format_join_url(
    furl: str,
    shares: Optional[tuple[int, int, int]] = None,
    origin: Optional[str] = None,
    scheme: str = "http",
) -> str:
    """Build a shareable join URL. Fragment holds the address (like signal.group/#…)."""
    furl = validate_introducer_furl(furl)
    params = {"v": "1", "i": furl}
    if shares:
        needed, happy, total = shares
        params["n"] = str(int(needed))
        params["h"] = str(int(happy))
        params["t"] = str(int(total))
    frag = urlencode(params, quote_via=quote, safe="")
    if scheme == "leasegrid":
        return "%s#%s" % (NATIVE_SCHEME, frag)
    base = (origin or join_origin()).rstrip("/")
    return "%s#%s" % (base, frag)


def to_native_url(url_or_furl: str) -> str:
    parsed = parse_invite(url_or_furl)
    if parsed.kind == "code":
        raise SyncError(
            "could not make a join link. A short code is one-time and not a page.",
            "share a friendnet link (the i2p page) instead of a live invite code.",
        )
    return format_join_url(parsed.token, shares=parsed.shares, scheme="leasegrid")


def parse_invite(raw: str) -> ParsedInvite:
    text = (raw or "").strip()
    if not text:
        raise SyncError(
            "could not join this friendnet. Invite is empty.",
            "paste a join link, a short code like 7-word-word, or scan the QR.",
        )
    if is_wormhole_code(text):
        return ParsedInvite(kind="code", token=text.lower())
    if text.startswith("pb://"):
        return ParsedInvite(kind="furl", token=validate_introducer_furl(text))

    low = text.lower()
    if text.startswith("#") or low.startswith("v=1&") or low.startswith("v=1%"):
        return _from_fragment(text.lstrip("#"))

    if low.startswith("leasegrid:"):
        parsed = urlparse(text)
        frag = parsed.fragment or parsed.query
        if not frag:
            raise SyncError(
                "could not join this friendnet. That link has no address.",
                "paste the full link (it includes a #…); Retry.",
            )
        out = _from_fragment(frag)
        out.url = text
        out.origin = NATIVE_SCHEME
        return out

    if low.startswith("http://") or low.startswith("https://"):
        parsed = urlparse(text)
        host = (parsed.hostname or "").lower()
        path = (parsed.path or "").rstrip("/")
        frag = parsed.fragment or ""
        looks_join = (
            "i=" in frag.lower()
            or path.endswith("/join")
            or host.endswith(".i2p")
        )
        if frag and ("i=" in frag or "i%3d" in frag.lower()):
            origin = "%s://%s%s" % (parsed.scheme, parsed.netloc, path or "/join")
            out = _from_fragment(frag, origin=origin)
            out.url = text
            return out
        if looks_join:
            raise SyncError(
                "could not join this friendnet. That page has no invite in the link.",
                "ask for the full link (it includes a #…); Retry.",
            )
        raise SyncError(
            "could not join this friendnet. That looks like a web URL.",
            "Leasegrid Sync does not use the Tahoe web UI. Paste a join link, short code, or pb:// furl.",
        )

    return ParsedInvite(kind="furl", token=validate_introducer_furl(text))


def _from_fragment(frag: str, origin: str = "") -> ParsedInvite:
    data = parse_qs(frag, keep_blank_values=True)
    vals = data.get("i") or []
    if not vals:
        raise SyncError(
            "could not join this friendnet. That link has no address.",
            "ask for the full link (it includes a #…); Retry.",
        )
    furl = validate_introducer_furl(vals[0])
    shares = None
    try:
        n = int((data.get("n") or [""])[0])
        h = int((data.get("h") or [""])[0])
        t = int((data.get("t") or [""])[0])
        if 0 < n <= h <= t:
            shares = (n, h, t)
    except (TypeError, ValueError):
        shares = None
    return ParsedInvite(kind="url", token=furl, shares=shares, origin=origin)


def qr_svg(data: str) -> str:
    import segno

    buf = io.BytesIO()
    segno.make(data, error="m").save(buf, kind="svg", xmldecl=False, svgns=True, scale=4, border=2)
    return buf.getvalue().decode("ascii")


def qr_png(data: str) -> bytes:
    import segno

    buf = io.BytesIO()
    segno.make(data, error="m").save(buf, kind="png", scale=6, border=2)
    return buf.getvalue()


def invite_code_from_output(text: str) -> str:
    """Return the short code Tahoe printed, or "" if that line is absent.

    A raw ``pb://`` introducer furl in the same log is not a code.
    """
    match = _INVITE_CODE_LINE.search(text or "")
    if not match:
        return ""
    token = match.group(1).strip().strip("\"'")
    if not is_wormhole_code(token):
        return ""
    return token.lower()


@dataclass
class InviteCodeSession:
    """Live ``tahoe invite``. The process must stay up until the peer joins."""

    code: str
    proc: Optional[subprocess.Popen] = None

    def alive(self) -> bool:
        if not self.code:
            return False
        if self.proc is None:
            return True
        return self.proc.poll() is None

    def close(self) -> None:
        proc = self.proc
        self.proc = None
        if proc is None or proc.poll() is not None:
            return
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                pass


def _read_invite_code(proc: subprocess.Popen, timeout: float) -> str:
    """Read stdout until Tahoe prints a short code, the process exits, or timeout."""
    chunks: list[str] = []
    done = threading.Event()

    def _reader() -> None:
        stream = proc.stdout
        try:
            if stream is None:
                return
            while True:
                line = stream.readline()
                if not line:
                    break
                chunks.append(line)
                if invite_code_from_output("".join(chunks)):
                    break
        finally:
            done.set()

    threading.Thread(target=_reader, name="leasegrid-invite-code", daemon=True).start()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        code = invite_code_from_output("".join(chunks))
        if code:
            return code
        if proc.poll() is not None and done.wait(0.05):
            break
        done.wait(0.05)
    return invite_code_from_output("".join(chunks))


def start_invite_code(
    nodedir: Path,
    tahoe_bin: Optional[str] = None,
    timeout: float = INVITE_CODE_TIMEOUT,
) -> InviteCodeSession:
    """Start ``tahoe invite`` and return once the short code is printed.

    Fails in-process (no code) when this home has not joined, Tahoe is missing,
    or the inviter never prints ``Invite Code for client:``. The returned
    session keeps the process alive so the code can still be redeemed.
    """
    from .backend import which_bin
    from .recovery import read_shares

    try:
        share_url_for_nodedir(Path(nodedir))
    except SyncError as exc:
        raise SyncError(
            "could not share an invite. No friendnet joined yet.",
            "join a friendnet first, then Invite.",
        ) from exc

    binary = tahoe_bin or which_bin("tahoe", "LEASEGRID_TAHOE_BIN")
    if not binary:
        raise SyncError(
            "could not create an invite code. The Tahoe client is not installed.",
            "install Tahoe next to Sync, then Retry.",
        )

    needed, happy, total = read_shares(Path(nodedir))
    nick = (os.environ.get("LEASEGRID_NICKNAME") or "leasegrid-sync").strip() or "leasegrid-sync"
    cmd = [binary]
    relay = (os.environ.get("LEASEGRID_WORMHOLE_SERVER") or "").strip()
    if relay:
        cmd += ["--wormhole-server", relay]
    cmd += [
        "-d",
        str(nodedir),
        "invite",
        "--shares-needed=%d" % needed,
        "--shares-happy=%d" % happy,
        "--shares-total=%d" % total,
        nick,
    ]
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env,
        )
    except OSError as exc:
        raise SyncError(
            "could not create an invite code. Tahoe invite did not start.",
            "check that tahoe is installed, then Retry.",
        ) from exc

    code = _read_invite_code(proc, timeout)
    if not code:
        InviteCodeSession(code="", proc=proc).close()
        raise SyncError(
            "could not create an invite code. Tahoe invite did not print a short code.",
            "check the wormhole relay, then Retry.",
        )
    return InviteCodeSession(code=code, proc=proc)


def share_url_for_nodedir(nodedir: Path, origin: Optional[str] = None) -> str:
    """Join URL for a configured Tahoe node. Secret stays in the #fragment."""
    from .recovery import read_introducer_furl, read_shares

    try:
        furl = read_introducer_furl(Path(nodedir))
    except SyncError as exc:
        raise SyncError(
            "could not make a join link. No friendnet joined yet.",
            "join a friendnet first, then copy the link or export the I2P page.",
        ) from exc
    return format_join_url(furl, shares=read_shares(Path(nodedir)), origin=origin)


def invite_page_html(url: str, name: str = "friendnet") -> str:
    """Self-contained page to drop on an I2P eepsite. No CDN, no WUI."""
    parsed = parse_invite(url)
    share = url if "#" in url and url.lower().startswith("http") else format_join_url(
        parsed.token, shares=parsed.shares, origin=parsed.origin or join_origin()
    )
    native = format_join_url(parsed.token, shares=parsed.shares, scheme="leasegrid")
    svg = qr_svg(share)
    title = html.escape(name or "friendnet")
    share_esc = html.escape(share)
    native_esc = html.escape(native, quote=True)
    return f"""<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Join {title}</title>
<style>
  body {{ font-family: ui-sans-serif, system-ui, sans-serif; max-width: 28rem;
         margin: 2.5rem auto; padding: 0 1.25rem; color: #111; }}
  h1 {{ font-size: 1.35rem; margin: 0 0 .4rem; }}
  p {{ color: #444; line-height: 1.45; }}
  .qr {{ width: 14rem; height: 14rem; margin: 1.2rem 0; }}
  .qr svg {{ width: 100%; height: 100%; }}
  code {{ font-size: .8rem; word-break: break-all; }}
  a.btn, button {{ display: inline-block; margin: .35rem .35rem 0 0; padding: .55rem .9rem;
    background: #1f6feb; color: #fff; text-decoration: none; border: 0; border-radius: 6px;
    font: inherit; cursor: pointer; }}
  button.secondary {{ background: #3d3d3d; }}
</style>
<h1>Join {title}</h1>
<p>Scan the code or copy the link. Opens Leasegrid Sync.</p>
<div class="qr">{svg}</div>
<p><code id="link">{share_esc}</code></p>
<p>
  <a class="btn" href="{native_esc}">Open in Leasegrid Sync</a>
  <button class="secondary" type="button" id="copy">Copy link</button>
</p>
<script>
document.getElementById("copy").onclick = function () {{
  var t = document.getElementById("link").textContent;
  if (navigator.clipboard) navigator.clipboard.writeText(t);
}};
</script>
</html>
"""
