"""A loopback storage offer must not listen on every interface.

``LEASEGRID_STORAGE_HOSTNAME`` replaces the default address. Tahoe's
``--listen=tcp`` writes ``tub.port = tcp:PORT`` with no interface, so the
port accepts connections on the LAN as well as on that loopback address.
"""

from __future__ import annotations

import socket
import sys
from pathlib import Path

import pytest

from leasegrid_sync.backend import TahoeClient

# Not a live introducer. create-node only stores it.
_FURL = "pb://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa@tcp:127.0.0.1:1/introducer"


def _tahoe_bin() -> Path:
    exe = Path(sys.executable)
    for folder in (exe.parent, exe.resolve().parent):
        path = folder / "tahoe"
        if path.is_file():
            return path
    pytest.skip("tahoe is not installed beside this interpreter")


def _tub(cfg: str) -> tuple[str, str]:
    port = ""
    location = ""
    for line in cfg.splitlines():
        if line.startswith("tub.port"):
            port = line.split("=", 1)[1].strip()
        elif line.startswith("tub.location"):
            location = line.split("=", 1)[1].strip()
    return port, location


def _can_bind_loopback_alias(host: str = "127.0.0.2") -> bool:
    """True when this host can accept a connection on that loopback address."""
    sock = socket.socket()
    try:
        sock.bind((host, 0))
    except OSError:
        return False
    finally:
        sock.close()
    return True


_LOOPBACK_SKIP_REASON = (
    "127.0.0.2 is not assigned on this host "
    "(macOS lo0 has only 127.0.0.1 unless an alias is added); "
    "refusing to add that alias"
)


def loopback_listen_skip_reason(platform: str | None = None) -> str | None:
    """None when the listen test must run. A reason when this host may skip it.

    Linux never skips: a probe that cannot bind 127.0.0.2 fails the test,
    so a probe hardcoded to False cannot hide behind a skip. Other platforms
    skip only when that bind fails. The reason names the missing address.
    """
    plat = sys.platform if platform is None else platform
    if _can_bind_loopback_alias():
        return None
    if plat.startswith("linux"):
        return None
    return _LOOPBACK_SKIP_REASON


def _listen_addrs(port: int) -> set[str]:
    """Local addresses in /proc/net/tcp{,6} that are listening on ``port``."""
    found: set[str] = set()
    want = "%04X" % port
    for name in ("/proc/net/tcp", "/proc/net/tcp6"):
        try:
            lines = Path(name).read_text(encoding="utf-8").splitlines()[1:]
        except OSError:
            continue
        for line in lines:
            parts = line.split()
            if len(parts) < 4 or parts[3] != "0A":
                continue
            local = parts[1]
            addr, hex_port = local.split(":")
            if hex_port.upper() == want:
                found.add(addr.upper())
    return found


@pytest.mark.skipif(
    loopback_listen_skip_reason() is not None,
    reason=_LOOPBACK_SKIP_REASON,
)
def test_loopback_storage_override_listens_on_that_address_only(tmp_path: Path, monkeypatch):
    """127.0.0.2 replaces 127.0.0.1, and nothing else can connect to the port."""
    monkeypatch.setenv("LEASEGRID_STORAGE_HOSTNAME", "127.0.0.2")
    home = tmp_path / "home"
    client = TahoeClient(nodedir=home / "tahoe", tahoe_bin=str(_tahoe_bin()), home=home)
    try:
        client.create_node(_FURL, shares=(1, 1, 1))
        port_line, location = _tub((home / "tahoe" / "tahoe.cfg").read_text(encoding="utf-8"))
        port = int(port_line.split(":")[1])
        assert location == "tcp:127.0.0.2:%d" % port
        assert port_line == "tcp:%d:interface=127.0.0.2" % port
        assert "example" not in location
        client.start(timeout=25)
        sock = socket.socket()
        try:
            sock.settimeout(3)
            sock.connect(("127.0.0.2", port))
        finally:
            sock.close()
        listeners = _listen_addrs(port)
        assert "0200007F" in listeners  # 127.0.0.2, little-endian
        assert "00000000" not in listeners  # 0.0.0.0
        assert "00000000000000000000000000000000" not in listeners
    finally:
        client.stop()


def test_ipv6_loopback_port_escapes_colons(tmp_path: Path):
    """``::1`` is loopback. A raw colon would split the Twisted endpoint."""
    from leasegrid_sync.backend import tighten_loopback_listen

    cfg = tmp_path / "tahoe.cfg"
    cfg.write_text(
        "[node]\ntub.location = tcp:[::1]:34567\ntub.port = tcp:34567\n",
        encoding="utf-8",
    )
    assert tighten_loopback_listen(tmp_path) is True
    text = cfg.read_text(encoding="utf-8")
    assert "tub.port = tcp:34567:interface=\\:\\:1\n" in text
    assert "tub.location = tcp:[::1]:34567\n" in text


def _skipif_marks(fn):
    marks = getattr(fn, "pytestmark", [])
    if not isinstance(marks, list):
        marks = [marks]
    return [mark for mark in marks if mark.name == "skipif"]


@pytest.mark.skipif(
    not sys.platform.startswith("linux"),
    reason="Linux is where a failed 127.0.0.2 probe must fail the listen test, not skip it",
)
def test_linux_loopback_probe_succeeds_and_the_listen_test_is_not_skipped():
    """Reviewer mutant M3: a probe that always returns False must not skip on Linux.

    On this host the probe really can bind, and the listen test was collected
    with the skip condition false.
    """
    assert _can_bind_loopback_alias() is True
    assert loopback_listen_skip_reason() is None
    assert loopback_listen_skip_reason("darwin") is None
    skipped = _skipif_marks(test_loopback_storage_override_listens_on_that_address_only)
    assert len(skipped) == 1
    assert skipped[0].args[0] is False
    assert "127.0.0.2" in skipped[0].kwargs["reason"]
    source = Path(__file__).read_text(encoding="utf-8")
    assert "loopback_listen_skip_reason() is not None" in source


def test_failed_loopback_probe_skips_only_off_linux(monkeypatch):
    """Linux with a failed probe runs the listen test. darwin skips, with a reason."""
    monkeypatch.setattr(
        sys.modules[__name__],
        "_can_bind_loopback_alias",
        lambda host="127.0.0.2": False,
    )
    linux = loopback_listen_skip_reason("linux")
    assert linux is None, "Linux must not skip when the probe fails (%r)" % (linux,)
    darwin = loopback_listen_skip_reason("darwin")
    assert darwin is not None
    assert "127.0.0.2" in darwin
    assert "alias" in darwin
    assert loopback_listen_skip_reason("win32") == darwin
    monkeypatch.setattr(
        sys.modules[__name__],
        "_can_bind_loopback_alias",
        lambda host="127.0.0.2": True,
    )
    assert loopback_listen_skip_reason("linux") is None
    assert loopback_listen_skip_reason("darwin") is None


def test_lan_storage_hostname_stays_reachable_off_box(tmp_path: Path, monkeypatch):
    """A name that is not loopback is still advertised, and the port is not pinned to loopback."""
    monkeypatch.setenv("LEASEGRID_STORAGE_HOSTNAME", "example.invalid")
    home = tmp_path / "home"
    client = TahoeClient(nodedir=home / "tahoe", tahoe_bin=str(_tahoe_bin()), home=home)
    client.create_node(_FURL, shares=(1, 1, 1))
    port_line, location = _tub((home / "tahoe" / "tahoe.cfg").read_text(encoding="utf-8"))
    port = int(port_line.split(":")[1])
    assert location == "tcp:example.invalid:%d" % port
    assert "interface=" not in port_line
