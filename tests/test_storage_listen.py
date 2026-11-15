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
