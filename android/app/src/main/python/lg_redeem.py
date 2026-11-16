"""Redeem a Tahoe 1.20 invite short code.

The phone is the client. It sends client-v1, requires server-v1, then reads
the config JSON. Kotlin maps the status. This module does not build a node
and does not log the code, the address, or the relay.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any

_log = logging.getLogger("lg_redeem")

# Tahoe 1.20 runner.py. Lab tests pass a different relay. The phone has no field for it.
APP_ID = "tahoe-lafs.org/invite"
DEFAULT_RELAY = "ws://wormhole.tahoe-lafs.org:4000/v1"
DEFAULT_BUDGET = 120.0

_lock = threading.Lock()
_generation = 0
_open: Any = None
# token, Deferred. Cancel drops a wait that is still on the relay.
_wait: tuple[int, Any] | None = None


class _Discard:
    """wormhole.create takes a stderr file. Writes here never reach the phone log."""

    def write(self, text: str) -> int:
        return len(text)

    def flush(self) -> None:
        return None


# The library can echo a code when tracing is on. The phone log must not.
_stderr = _Discard()


class _Budget(Exception):
    """The attempt used its whole budget without an inviter answer."""


class _Rejected(Exception):
    """The other side refused the client hello, or this attempt was replaced."""


def cancel_redeem() -> dict[str, Any]:
    """Drop whatever attempt is open. The screen already left, so no banner."""
    _invalidate()
    return {"ok": True, "status": "cancelled"}


def redeem_invite(data: dict[str, Any]) -> dict[str, Any]:
    """Return ok plus an address, or a status and nothing else. Never raises."""
    code = str(data.get("code") or "").strip().lower()
    if not code:
        return _fail("rejected")
    relay = data.get("relay")
    relay_url = str(relay).strip() if relay else DEFAULT_RELAY
    budget = _budget(data.get("timeout"))
    if budget <= 0:
        return _fail("timeout")
    token = _invalidate()
    try:
        payload = _exchange(code, relay_url, budget, token)
    except _Budget:
        if _current() != token:
            return _fail("rejected")
        return _fail("timeout")
    except _Rejected:
        return _fail("rejected")
    except Exception as exc:
        if _current() != token:
            return _fail("rejected")
        _log.warning("redeem failed: %s", type(exc).__name__)
        return _fail(status_for(exc))
    if _current() != token or not isinstance(payload, dict):
        return _fail("rejected")
    return _ok(payload)


def status_for(exc: BaseException) -> str:
    """Map a handshake failure onto expired, rejected, relay, or timeout.

    The text of the exception is not returned. A connect failure is relay.
    Our own budget is timeout, handled before this function.
    """
    name = type(exc).__name__.lower()
    if name in {"importerror", "modulenotfounderror", "readfail"}:
        return "relay"
    if name == "lonelyerror":
        return "expired"
    if name in {"wrongpassworderror", "keyformaterror", "reflectionattack"}:
        return "rejected"
    if "crowd" in name:
        return "rejected"
    text = str(exc).lower()
    if "server-v1" in text or "expected 'abilities'" in text:
        return "rejected"
    if name in {
        "serverconnectionerror",
        "welcomeerror",
        "connectionrefusederror",
        "gaierror",
        "oserror",
        "connecterror",
    }:
        return "relay"
    if any(
        bit in text
        for bit in (
            "connection refused",
            "name or service not known",
            "nodename nor servname",
            "network is unreachable",
            "no route to host",
            "temporary failure in name resolution",
            "could not connect",
            "failed to connect",
            "connection reset",
        )
    ):
        return "relay"
    if "wrong password" in text or "crowded" in text:
        return "rejected"
    if "lonely" in text or "has expired" in text or "code expired" in text:
        return "expired"
    return "rejected"


def _exchange(code: str, relay_url: str, budget: float, token: int) -> dict[str, Any]:
    from lg_intro import _ensure_reactor
    from twisted.internet.threads import blockingCallFromThread

    reactor = _ensure_reactor()

    def _call():
        return _run(reactor, code, relay_url, budget, token)

    return blockingCallFromThread(reactor, _call)


def _run(reactor: Any, code: str, relay_url: str, budget: float, token: int) -> Any:
    from twisted.internet.defer import inlineCallbacks, returnValue
    from wormhole import create

    @inlineCallbacks
    def _go():
        global _open, _wait
        deadline = time.monotonic() + budget
        wh = create(APP_ID, relay_url, reactor, stderr=_stderr)
        with _lock:
            if _generation != token:
                stale = wh
            else:
                _open = wh
                stale = None
        if stale is not None:
            _fire_close(stale)
            raise _Rejected()
        try:
            yield _bound(wh.get_welcome(), reactor, deadline, token)
            _check(token)
            wh.set_code(code)
            wh.send_message(json.dumps({"abilities": {"client-v1": {}}}).encode("utf-8"))
            server_raw = yield _bound(wh.get_message(), reactor, deadline, token)
            server_intro = json.loads(_as_text(server_raw))
            _check(token)
            abilities = server_intro.get("abilities") if isinstance(server_intro, dict) else None
            if not isinstance(abilities, dict) or "server-v1" not in abilities:
                raise _Rejected()
            remote_raw = yield _bound(wh.get_message(), reactor, deadline, token)
            remote = json.loads(_as_text(remote_raw))
            _check(token)
            if not isinstance(remote, dict):
                raise _Rejected()
            returnValue(remote)
        finally:
            with _lock:
                if _open is wh:
                    _open = None
                if _wait is not None and _wait[0] == token:
                    _wait = None
            try:
                yield wh.close()
            except Exception:
                _log.warning("redeem close failed: %s", "close")

    return _go()


def _bound(deferred: Any, reactor: Any, deadline: float, token: int) -> Any:
    global _wait
    left = deadline - time.monotonic()
    if left <= 0:
        raise _Budget()

    def _on_timeout(_result: Any, _timeout: float) -> Any:
        raise _Budget()

    wrapped = deferred.addTimeout(left, reactor, onTimeoutCancel=_on_timeout)
    with _lock:
        if _generation != token:
            stale = wrapped
        else:
            _wait = (token, wrapped)
            stale = None
    if stale is not None:
        stale.cancel()
    return wrapped


def _as_text(raw: Any) -> str:
    if isinstance(raw, bytes):
        return raw.decode("utf-8")
    return str(raw)


def _ok(payload: dict[str, Any]) -> dict[str, Any]:
    raw = payload.get("introducer")
    if isinstance(raw, bytes):
        try:
            raw = raw.decode("utf-8")
        except UnicodeDecodeError:
            raw = ""
    furl = raw if isinstance(raw, str) else ""
    out: dict[str, Any] = {"ok": True, "status": "ok", "furl": furl}
    shares = _shares(payload)
    if shares is not None:
        out["shares"] = shares
    return out


def _shares(payload: dict[str, Any]) -> list[int] | None:
    try:
        needed = int(payload["shares-needed"])
        happy = int(payload["shares-happy"])
        total = int(payload["shares-total"])
    except (KeyError, TypeError, ValueError):
        return None
    if needed > 0 and needed <= happy <= total:
        return [needed, happy, total]
    return None


def _fail(status: str) -> dict[str, Any]:
    return {"ok": False, "status": status}


def _budget(value: Any) -> float:
    if value is None or value == "":
        return DEFAULT_BUDGET
    try:
        number = float(value)
    except (TypeError, ValueError):
        return DEFAULT_BUDGET
    if number <= 0:
        return 0.0
    return number


def _current() -> int:
    with _lock:
        return _generation


def _invalidate() -> int:
    global _generation
    with _lock:
        _generation += 1
        wh = _open
        token = _generation
        waiting = _wait
    _close_soon(wh)
    if waiting is not None and waiting[0] != token:
        _cancel_deferred(waiting[1])
    return token


def _check(token: int) -> None:
    if _current() != token:
        raise _Rejected()


def _close_soon(wh: Any) -> None:
    if wh is None:
        return
    try:
        from twisted.internet import reactor

        if getattr(reactor, "running", False):
            reactor.callFromThread(_fire_close, wh)
            return
    except Exception as exc:
        _log.warning("redeem cancel failed: %s", type(exc).__name__)
        return
    _fire_close(wh)


def _cancel_deferred(deferred: Any) -> None:
    try:
        from twisted.internet import reactor

        if getattr(reactor, "running", False):
            reactor.callFromThread(_fire_cancel, deferred)
            return
    except Exception as exc:
        _log.warning("redeem cancel failed: %s", type(exc).__name__)
        return
    _fire_cancel(deferred)


def _fire_cancel(deferred: Any) -> None:
    try:
        deferred.cancel()
    except Exception as exc:
        _log.warning("redeem cancel failed: %s", type(exc).__name__)


def _fire_close(wh: Any) -> None:
    try:
        closing = wh.close()
        if closing is not None and hasattr(closing, "addErrback"):
            closing.addErrback(lambda _fail: None)
    except Exception as exc:
        _log.warning("redeem close failed: %s", type(exc).__name__)
