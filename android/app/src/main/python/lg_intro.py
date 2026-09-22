"""Learn unpaid friendnet storage servers from the introducer.

Uses Foolscap the same way a Tahoe client does (subscribe_v2 / announce_v2).
The phone does not offer storage and does not open the Tahoe web UI.
"""

from __future__ import annotations

import json
import threading
import time
from typing import Any

from lg_tahoe import ReadFail, _host_candidates

_reactor_lock = threading.Lock()
_reactor_started = False


def _subscriber_interface():
    """Foolscap remote name Tahoe 1.20 expects. Defined once per process.

    Defining it inside each join raises DuplicateRemoteInterfaceError the
    second time, including Refresh on the phone.
    """
    from foolscap.api import Any, RemoteInterface, SetOf

    class SubscriberV2(RemoteInterface):
        __remote_name__ = "RIIntroducerSubscriberClient_v2.tahoe.allmydata.com"

        def announce_v2(announcements=SetOf(Any())):
            return None

    return SubscriberV2


_SUBSCRIBER_V2 = None


def _subscriber_v2():
    """Reuse Tahoe's interface when it is already registered.

    Defining a second class with the same ``__remote_name__`` raises
    DuplicateRemoteInterfaceError. The phone does not import allmydata, so
    the local class is what the APK uses. A process that already loaded
    Tahoe keeps that registration.
    """
    global _SUBSCRIBER_V2
    if _SUBSCRIBER_V2 is not None:
        return _SUBSCRIBER_V2
    from foolscap.remoteinterface import getRemoteInterfaceByName

    name = "RIIntroducerSubscriberClient_v2.tahoe.allmydata.com"
    existing = getRemoteInterfaceByName(name)
    if existing is not None:
        _SUBSCRIBER_V2 = existing
        return existing
    _SUBSCRIBER_V2 = _subscriber_interface()
    return _SUBSCRIBER_V2


def _ensure_reactor():
    global _reactor_started
    from twisted.internet import reactor

    with _reactor_lock:
        if _reactor_started:
            return reactor
        threading.Thread(
            target=lambda: reactor.run(installSignalHandlers=False),
            name="leasegrid-reactor",
            daemon=True,
        ).start()
        for _ in range(100):
            if reactor.running:
                _reactor_started = True
                return reactor
            time.sleep(0.05)
    raise ReadFail(
        "could not join this friendnet. The phone network stack did not start.",
        "Retry.",
    )


def _rewrite_furl(furl: str, host: str, replacement: str) -> str:
    return furl.replace("@%s:" % host, "@%s:" % replacement).replace(
        "tcp:%s:" % host, "tcp:%s:" % replacement
    )


def _candidates(furl: str) -> list[str]:
    out = [furl]
    for host in ("127.0.0.1", "localhost", "::1"):
        if ("@%s:" % host) in furl or ("tcp:%s:" % host) in furl:
            for alt in _host_candidates(host):
                if alt != host:
                    rewritten = _rewrite_furl(furl, host, alt)
                    if rewritten not in out:
                        out.append(rewritten)
    return out


def learn_servers(furl: str, timeout: float = 25.0) -> dict[str, Any]:
    """Return {ok, detail, servers:[{furl, nickname}]} or raise ReadFail."""
    reactor = _ensure_reactor()
    from twisted.internet.threads import blockingCallFromThread

    def _call() -> dict[str, Any]:
        from twisted.internet.defer import Deferred, inlineCallbacks, returnValue
        from foolscap.api import Referenceable, Tub
        from zope.interface import implementer

        subscriber = _subscriber_v2()

        @inlineCallbacks
        def _attempt(one_furl: str):
            found: list[dict[str, str]] = []

            @implementer(subscriber)
            class _Sub(Referenceable):
                def remote_announce_v2(self, announcements):
                    for ann_t in announcements:
                        row = _announcement_server(ann_t)
                        if row and all(row["furl"] != have["furl"] for have in found):
                            found.append(row)
                    return None

            tub = Tub()
            yield tub.startService()
            try:
                publisher = yield tub.getReference(one_furl)
                yield publisher.callRemote(
                    "subscribe_v2",
                    _Sub(),
                    b"storage",
                    {
                        b"version": 0,
                        b"nickname": "leasegrid-sync-android",
                        b"app-versions": [],
                        b"my-version": b"leasegrid-sync-android-slice-a",
                        b"oldest-supported": b"1.0.0",
                    },
                )
                deadline = time.time() + timeout
                while time.time() < deadline and not found:
                    pause: Deferred[None] = Deferred()
                    reactor.callLater(0.4, pause.callback, None)
                    yield pause
            finally:
                try:
                    yield tub.stopService()
                except Exception:
                    pass
            returnValue(
                {
                    "ok": True,
                    "detail": "introducer up · %d storage" % len(found),
                    "servers": found,
                }
            )

        @inlineCallbacks
        def _run():
            last_exc: Exception | None = None
            last_result: dict[str, Any] | None = None
            for candidate in _candidates(furl):
                try:
                    result = yield _attempt(candidate)
                except Exception as exc:
                    last_exc = exc
                    continue
                last_result = result
                if result["servers"]:
                    returnValue(result)
            if last_result is not None:
                returnValue(last_result)
            detail = type(last_exc).__name__ if last_exc else "timeout"
            raise ReadFail(
                "could not join this friendnet. Introducer is unreachable.",
                "check the network path to the introducer (and that it is running); Retry. (%s)"
                % detail,
            )

        return _run()

    try:
        return blockingCallFromThread(reactor, _call)
    except ReadFail:
        raise
    except Exception as exc:
        raise ReadFail(
            "could not join this friendnet. Introducer is unreachable.",
            "check the network path to the introducer (and that it is running); Retry. (%s)"
            % type(exc).__name__,
        ) from exc


def _announcement_server(ann_t: Any) -> dict[str, str] | None:
    try:
        msg = ann_t[0]
    except (TypeError, ValueError, IndexError):
        return None
    if isinstance(msg, str):
        msg = msg.encode("utf-8")
    if not isinstance(msg, (bytes, bytearray)):
        return None
    try:
        ann = json.loads(bytes(msg).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError):
        return None
    if not isinstance(ann, dict):
        return None
    furl = ann.get("anonymous-storage-FURL") or ann.get("FURL") or ""
    if isinstance(furl, str) and furl.startswith("pb://"):
        return {"furl": furl, "nickname": str(ann.get("nickname") or "")}
    return None
