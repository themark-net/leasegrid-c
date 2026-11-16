"""Short-code redeem: status mapping, and one mailbox contract.

The mailbox test injects a local relay. It does not call the public one.
A code in this file is a fixture, and the test does not print it.
"""

from __future__ import annotations

import json
import logging
import queue
import socket
import sys
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "app/src/main/python"
sys.path.insert(0, str(ROOT))

import lg_redeem  # noqa: E402

FURL = "pb://hashhashhash@127.0.0.1:1/swissnumswiss"
CODE = "7-guitarist-revenge"


def test_a_zero_budget_is_timeout_and_does_not_open_a_relay(monkeypatch):
    def boom(*_args, **_kwargs):
        raise AssertionError("budget 0 must not open a relay")

    monkeypatch.setattr(lg_redeem, "_exchange", boom)
    reply = lg_redeem.redeem_invite({"code": CODE, "timeout": 0})
    assert reply == {"ok": False, "status": "timeout"}
    assert CODE not in json.dumps(reply)


def test_failure_status_mapping_keeps_the_code_out_of_the_log(caplog, monkeypatch):
    from wormhole.errors import LonelyError, WrongPasswordError, ServerConnectionError

    cases = [
        (LonelyError(), "expired"),
        (WrongPasswordError(), "rejected"),
        (ServerConnectionError("ws://127.0.0.1:9/v1", ConnectionRefusedError(111, "refused")), "relay"),
        (lg_redeem._Budget(), "timeout"),
        (RuntimeError("Expected 'server-v1' in server abilities"), "rejected"),
        (ImportError("wormhole"), "relay"),
    ]

    def boom(exc):
        def _raise(*_args, **_kwargs):
            raise exc

        return _raise

    for exc, status in cases:
        monkeypatch.setattr(lg_redeem, "_exchange", boom(exc))
        with caplog.at_level(logging.WARNING, logger="lg_redeem"):
            reply = lg_redeem.redeem_invite(
                {"code": CODE, "relay": "ws://127.0.0.1:9/v1", "timeout": 5}
            )
        assert reply == {"ok": False, "status": status}, type(exc).__name__
        text = json.dumps(reply) + caplog.text
        assert CODE not in text
        assert "127.0.0.1" not in text
        assert FURL not in text
        caplog.clear()


def test_good_shares_are_kept_and_bad_shares_and_nickname_are_not(monkeypatch):
    def good(*_args, **_kwargs):
        return {
            "introducer": FURL,
            "shares-needed": "2",
            "shares-happy": 3,
            "shares-total": 3,
            "nickname": "phone-must-ignore",
        }

    monkeypatch.setattr(lg_redeem, "_exchange", good)
    reply = lg_redeem.redeem_invite({"code": CODE})
    assert reply == {"ok": True, "status": "ok", "furl": FURL, "shares": [2, 3, 3]}
    assert "phone-must-ignore" not in json.dumps(reply)

    def bad(*_args, **_kwargs):
        return {
            "introducer": FURL,
            "shares-needed": 3,
            "shares-happy": 2,
            "shares-total": 3,
            "nickname": "phone-must-ignore",
        }

    monkeypatch.setattr(lg_redeem, "_exchange", bad)
    reply = lg_redeem.redeem_invite({"code": CODE})
    assert reply == {"ok": True, "status": "ok", "furl": FURL}
    assert "shares" not in reply


def test_dispatch_redeem_returns_status_and_not_a_traceback(monkeypatch, caplog):
    import leasegrid_read

    def boom(*_args, **_kwargs):
        raise lg_redeem._Budget()

    monkeypatch.setattr(lg_redeem, "_exchange", boom)
    with caplog.at_level(logging.WARNING):
        reply = json.loads(
            leasegrid_read.dispatch(
                "redeem",
                json.dumps({"code": CODE, "relay": "ws://127.0.0.1:9/v1", "timeout": 1}),
            )
        )
    assert reply == {"ok": False, "status": "timeout"}
    assert CODE not in caplog.text
    assert "Traceback" not in json.dumps(reply)


def _free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def _start_mailbox(tmp_path: Path, reactor):
    from twisted.internet.threads import blockingCallFromThread
    from wormhole_mailbox_server.server_tap import makeService

    port = _free_port()
    config = {
        "port": "tcp:%d:interface=127.0.0.1" % port,
        "blur-usage": None,
        "log-fd": None,
        "channel-db": str(tmp_path / "relay.sqlite"),
        "usage-db": None,
        "advertise-version": None,
        "signal-error": None,
        "motd": None,
        "allow-list": True,
        "websocket-protocol-options": [],
    }

    def _up():
        service = makeService(config, reactor=reactor)
        return service.startService(), service

    started, service = blockingCallFromThread(reactor, _up)
    if started is not None and hasattr(started, "addCallback"):
        blockingCallFromThread(reactor, lambda: started)
    return service, "ws://127.0.0.1:%d/v1" % port


def test_leaving_cancels_the_open_attempt_before_the_budget(tmp_path, monkeypatch):
    """A screen leave stops the wait. The budget is not slept out."""
    pytest.importorskip("wormhole")
    pytest.importorskip("wormhole_mailbox_server")
    from twisted.internet.defer import inlineCallbacks
    from twisted.internet.threads import blockingCallFromThread
    from lg_intro import _ensure_reactor

    reactor = _ensure_reactor()
    service, relay = _start_mailbox(tmp_path, reactor)
    entered = threading.Event()
    real_bound = lg_redeem._bound

    def _spy(*args, **kwargs):
        entered.set()
        return real_bound(*args, **kwargs)

    monkeypatch.setattr(lg_redeem, "_bound", _spy)
    try:
        code_box: queue.Queue[str] = queue.Queue()

        @inlineCallbacks
        def _hold():
            from wormhole import create

            wh = create(lg_redeem.APP_ID, relay, reactor, stderr=lg_redeem._stderr)
            try:
                yield wh.get_welcome()
                wh.allocate_code()
                code_box.put((yield wh.get_code()))
                pause = wh.get_message().addTimeout(8, reactor)
                try:
                    yield pause
                except Exception:
                    pass
            finally:
                try:
                    yield wh.close()
                except Exception:
                    pass

        holder = threading.Thread(
            target=lambda: blockingCallFromThread(reactor, _hold),
            daemon=True,
        )
        holder.start()
        code = code_box.get(timeout=20)
        box: queue.Queue[tuple[float, dict]] = queue.Queue()

        def _client():
            started = time.monotonic()
            reply = lg_redeem.redeem_invite({"code": code, "relay": relay, "timeout": 20})
            box.put((time.monotonic() - started, reply))

        client = threading.Thread(target=_client, daemon=True)
        client.start()
        assert entered.wait(5)
        # The welcome returns at once. Give the client time to wait on the inviter.
        time.sleep(0.4)
        lg_redeem.cancel_redeem()
        elapsed, reply = box.get(timeout=5)
        assert elapsed < 5
        assert reply["status"] != "ok"
        assert reply.get("furl", "") == ""
        assert FURL not in json.dumps(reply)
        holder.join(timeout=10)
    finally:
        from twisted.internet.threads import blockingCallFromThread

        try:
            blockingCallFromThread(reactor, service.stopService)
        except Exception:
            pass


def test_mailbox_contract_client_hello_and_a_skip_and_a_closed_inviter(tmp_path):
    """Real local mailbox. A client that skips client-v1 gets no address."""
    pytest.importorskip("wormhole")
    pytest.importorskip("wormhole_mailbox_server")
    from twisted.internet.defer import inlineCallbacks, returnValue
    from twisted.internet.threads import blockingCallFromThread
    from wormhole import create
    from lg_intro import _ensure_reactor

    reactor = _ensure_reactor()
    service, relay = _start_mailbox(tmp_path, reactor)
    try:
        code_box: queue.Queue[str] = queue.Queue()
        sent = queue.Queue()

        @inlineCallbacks
        def _invite():
            wh = create(lg_redeem.APP_ID, relay, reactor, stderr=lg_redeem._stderr)
            try:
                yield wh.get_welcome()
                wh.allocate_code()
                code = yield wh.get_code()
                code_box.put(code)
                wh.send_message(json.dumps({"abilities": {"server-v1": {}}}).encode("utf-8"))
                raw = yield wh.get_message()
                intro = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
                abilities = intro.get("abilities") if isinstance(intro, dict) else None
                if not isinstance(abilities, dict) or "client-v1" not in abilities:
                    sent.put("refused")
                    returnValue("refused")
                wh.send_message(
                    json.dumps(
                        {
                            "introducer": FURL,
                            "shares-needed": 2,
                            "shares-happy": 3,
                            "shares-total": 3,
                            "nickname": "ignored",
                        }
                    ).encode("utf-8")
                )
                sent.put("sent")
                returnValue("sent")
            finally:
                try:
                    yield wh.close()
                except Exception:
                    pass

        inviter = threading.Thread(
            target=lambda: blockingCallFromThread(reactor, _invite),
            daemon=True,
        )
        inviter.start()
        code = code_box.get(timeout=20)
        reply = lg_redeem.redeem_invite({"code": code, "relay": relay, "timeout": 20})
        inviter.join(timeout=20)
        assert reply["status"] == "ok"
        assert reply["furl"] == FURL
        assert reply["shares"] == [2, 3, 3]
        assert "nickname" not in reply
        assert sent.get(timeout=5) == "sent"

        # A client that skips client-v1 does not receive the address.
        refused_box: queue.Queue[str] = queue.Queue()
        seen: queue.Queue[str] = queue.Queue()

        @inlineCallbacks
        def _refuse():
            wh = create(lg_redeem.APP_ID, relay, reactor, stderr=lg_redeem._stderr)
            try:
                yield wh.get_welcome()
                wh.allocate_code()
                refused_box.put((yield wh.get_code()))
                wh.send_message(json.dumps({"abilities": {"server-v1": {}}}).encode("utf-8"))
                raw = yield wh.get_message()
                intro = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
                abilities = intro.get("abilities") if isinstance(intro, dict) else None
                if not isinstance(abilities, dict) or "client-v1" not in abilities:
                    seen.put("refused")
                    returnValue("refused")
                seen.put("sent")
                returnValue("sent")
            finally:
                try:
                    yield wh.close()
                except Exception:
                    pass

        @inlineCallbacks
        def _skip(skip_code):
            wh = create(lg_redeem.APP_ID, relay, reactor, stderr=lg_redeem._stderr)
            try:
                yield wh.get_welcome()
                wh.set_code(skip_code)
                wh.send_message(json.dumps({"abilities": {"client-v9000": {}}}).encode("utf-8"))
                try:
                    raw = yield wh.get_message().addTimeout(3, reactor)
                except Exception as exc:
                    returnValue(type(exc).__name__)
                text = raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)
                returnValue(text)
            finally:
                try:
                    yield wh.close()
                except Exception:
                    pass

        refuser = threading.Thread(
            target=lambda: blockingCallFromThread(reactor, _refuse),
            daemon=True,
        )
        refuser.start()
        skip_code = refused_box.get(timeout=20)
        skipped = blockingCallFromThread(reactor, lambda: _skip(skip_code))
        refuser.join(timeout=10)
        assert seen.get(timeout=5) == "refused"
        assert FURL not in str(skipped)

        # The inviter closes after the hello and before the address.
        # The mailbox does not fail the waiting read, so the phone budget
        # ends the attempt. No address comes back.
        closed_box: queue.Queue[str] = queue.Queue()
        client_seen = threading.Event()

        @inlineCallbacks
        def _close_after_hello():
            wh = create(lg_redeem.APP_ID, relay, reactor, stderr=lg_redeem._stderr)
            try:
                yield wh.get_welcome()
                wh.allocate_code()
                closed_box.put((yield wh.get_code()))
                wh.send_message(json.dumps({"abilities": {"server-v1": {}}}).encode("utf-8"))
                raw = yield wh.get_message()
                intro = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
                abilities = intro.get("abilities") if isinstance(intro, dict) else None
                if isinstance(abilities, dict) and "client-v1" in abilities:
                    client_seen.set()
            finally:
                try:
                    yield wh.close()
                except Exception:
                    pass

        closer = threading.Thread(
            target=lambda: blockingCallFromThread(reactor, _close_after_hello),
            daemon=True,
        )
        closer.start()
        closed_code = closed_box.get(timeout=20)
        closed = lg_redeem.redeem_invite({"code": closed_code, "relay": relay, "timeout": 3})
        closer.join(timeout=10)
        assert client_seen.is_set()
        assert closed["status"] == "timeout"
        assert closed.get("furl", "") == ""
        assert FURL not in json.dumps(closed)

        # Nobody answered: the inviter withholds its hello and the budget is short.
        held_box: queue.Queue[str] = queue.Queue()

        @inlineCallbacks
        def _withhold():
            wh = create(lg_redeem.APP_ID, relay, reactor, stderr=lg_redeem._stderr)
            try:
                yield wh.get_welcome()
                wh.allocate_code()
                held_box.put((yield wh.get_code()))
                pause = wh.get_message().addTimeout(5, reactor)
                try:
                    yield pause
                except Exception:
                    pass
            finally:
                try:
                    yield wh.close()
                except Exception:
                    pass

        holder = threading.Thread(
            target=lambda: blockingCallFromThread(reactor, _withhold),
            daemon=True,
        )
        holder.start()
        held_code = held_box.get(timeout=20)
        withheld = lg_redeem.redeem_invite({"code": held_code, "relay": relay, "timeout": 0.4})
        holder.join(timeout=10)
        assert withheld["status"] == "timeout"
        assert withheld.get("furl", "") == ""
    finally:
        from twisted.internet.threads import blockingCallFromThread

        try:
            blockingCallFromThread(reactor, service.stopService)
        except Exception:
            pass
