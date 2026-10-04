"""Slice A read client against a real Tahoe 1.20 grid.

Not part of host pytest (``testpaths = tests`` and ``norecursedirs`` includes
``android``). Run with ``pytest android/pytests/test_live_grid.py`` in its own
process. Importing this module registers nothing until ``learn`` runs, and
that Foolscap name collides with Tahoe if both load in one pytest session.
"""

from __future__ import annotations

import json
import re
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "app/src/main/python"
sys.path.insert(0, str(ROOT))

from leasegrid_read import dispatch  # noqa: E402

TAHOE = shutil.which("tahoe")


def _free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def _wait_file(path: Path, timeout: float = 40.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if path.is_file() and path.stat().st_size > 0:
            return
        time.sleep(0.2)
    raise AssertionError("missing %s" % path)


def _disable_web(nodedir: Path) -> None:
    """An empty ``web.port`` turns the WUI off. The token ``none`` is not a strport."""
    cfg_path = nodedir / "tahoe.cfg"
    cfg = cfg_path.read_text(encoding="utf-8")
    cfg = re.sub(r"(?m)^web\.port\s*=.*$", "web.port =", cfg)
    cfg_path.write_text(cfg, encoding="utf-8")


def _wait_port(port: int, timeout: float = 25.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            sock = socket.create_connection(("127.0.0.1", port), 0.4)
        except OSError:
            time.sleep(0.2)
            continue
        sock.close()
        return
    raise AssertionError("nothing listening on %s" % port)


@pytest.mark.skipif(TAHOE is None, reason="tahoe is not installed")
@pytest.mark.skipif(sys.platform != "linux", reason="live grid proof runs on Linux CI")
@pytest.mark.parametrize(
    ("needed", "happy", "total", "servers"),
    [
        (1, 1, 1, 1),
        (2, 2, 3, 2),
    ],
)
def test_join_list_and_download_round_trip(
    tmp_path: Path, needed: int, happy: int, total: int, servers: int
):
    assert TAHOE is not None
    intro_port = _free_port()
    intro = tmp_path / "intro"
    subprocess.check_call(
        [
            TAHOE,
            "create-introducer",
            "--port",
            "tcp:%d:interface=127.0.0.1" % intro_port,
            "--location",
            "tcp:127.0.0.1:%d" % intro_port,
            str(intro),
        ]
    )
    _disable_web(intro)
    procs: list[subprocess.Popen] = []
    logs = []
    try:
        log_intro = open(tmp_path / "intro.log", "wb")
        logs.append(log_intro)
        procs.append(
            subprocess.Popen(
                [TAHOE, "run", "--allow-stdin-close", str(intro)],
                stdout=log_intro,
                stderr=subprocess.STDOUT,
            )
        )
        _wait_file(intro / "private" / "introducer.furl")
        _wait_port(intro_port)
        furl = (intro / "private" / "introducer.furl").read_text(encoding="utf-8").strip()
        for index in range(servers):
            port = _free_port()
            node = tmp_path / ("storage-%d" % index)
            subprocess.check_call(
                [
                    TAHOE,
                    "create-node",
                    "--nickname",
                    "storage-%d" % index,
                    "--listen",
                    "tcp",
                    "--port",
                    "tcp:%d:interface=127.0.0.1" % port,
                    "--location",
                    "tcp:127.0.0.1:%d" % port,
                    "--introducer",
                    furl,
                    "--shares-needed",
                    str(needed),
                    "--shares-happy",
                    str(happy),
                    "--shares-total",
                    str(total),
                    "--webport",
                    "none",
                    str(node),
                ]
            )
            log_s = open(tmp_path / ("storage-%d.log" % index), "wb")
            logs.append(log_s)
            procs.append(
                subprocess.Popen(
                    [TAHOE, "run", "--allow-stdin-close", str(node)],
                    stdout=log_s,
                    stderr=subprocess.STDOUT,
                )
            )
        web_port = _free_port()
        client = tmp_path / "client"
        subprocess.check_call(
            [
                TAHOE,
                "create-node",
                "--nickname",
                "reader-client",
                "--no-storage",
                "--listen",
                "none",
                "--introducer",
                furl,
                "--shares-needed",
                str(needed),
                "--shares-happy",
                str(happy),
                "--shares-total",
                str(total),
                "--webport",
                "tcp:%d:interface=127.0.0.1" % web_port,
                str(client),
            ]
        )
        log_c = open(tmp_path / "client.log", "wb")
        logs.append(log_c)
        procs.append(
            subprocess.Popen(
                [TAHOE, "run", "--allow-stdin-close", str(client)],
                stdout=log_c,
                stderr=subprocess.STDOUT,
            )
        )
        node_url = client / "node.url"
        _wait_file(node_url)
        url = node_url.read_text(encoding="utf-8").strip()
        deadline = time.time() + 50
        dircap = ""
        while time.time() < deadline:
            try:
                dircap = subprocess.check_output(
                    [TAHOE, "mkdir", "--node-url", url],
                    text=True,
                    stderr=subprocess.STDOUT,
                ).strip()
            except subprocess.CalledProcessError:
                time.sleep(0.5)
                continue
            if dircap.startswith("URI:DIR2:"):
                break
        assert dircap.startswith("URI:DIR2:"), "grid did not accept mkdir"
        blob = tmp_path / "beach.txt"
        blob.write_bytes(b"hello from leasegrid slice A\n" + (b"x" * 4000))
        note = tmp_path / "note.txt"
        note.write_bytes(b"lit-ok\n")
        for src, name in ((blob, "beach.txt"), (note, "note.txt")):
            subprocess.check_call(
                [TAHOE, "put", "--node-url", url, "--dir-cap", dircap, str(src), name]
            )
        learned = json.loads(dispatch("learn", json.dumps({"furl": furl, "timeout": 25})))
        assert learned["ok"] is True, learned
        assert len(learned["servers"]) >= 1, learned
        listed = json.loads(
            dispatch("list", json.dumps({"cap": dircap, "servers": learned["servers"]}))
        )
        assert listed["ok"] is True, listed
        names = {row["name"]: row for row in listed["children"]}
        assert "beach.txt" in names, listed
        assert "note.txt" in names, listed
        for name, src in (("beach.txt", blob), ("note.txt", note)):
            dest = tmp_path / ("out-" + name)
            downloaded = json.loads(
                dispatch(
                    "download",
                    json.dumps(
                        {
                            "cap": names[name]["cap"],
                            "servers": learned["servers"],
                            "dest": str(dest),
                        }
                    ),
                )
            )
            assert downloaded["ok"] is True, downloaded
            assert dest.read_bytes() == src.read_bytes()
        # Slice B: the phone puts a file, a second client (tahoe get) reads it,
        # a clash does not overwrite, and remove is acknowledged by a new listing.
        added = tmp_path / "receipt.pdf"
        added.write_bytes(b"receipt from the phone\n")
        servers = learned["servers"]
        shares = [needed, happy, total]
        put = json.loads(
            dispatch(
                "put",
                json.dumps(
                    {
                        "cap": dircap,
                        "name": "receipt.pdf",
                        "path": str(added),
                        "servers": servers,
                        "shares": shares,
                        "replace": False,
                    }
                ),
            )
        )
        assert put["ok"] is True, put
        assert put["name"] == "receipt.pdf"
        listed_after = json.loads(
            dispatch("list", json.dumps({"cap": dircap, "servers": servers}))
        )
        assert listed_after["ok"] is True, listed_after
        after = {row["name"]: row for row in listed_after["children"]}
        assert "receipt.pdf" in after, listed_after
        phone_out = tmp_path / "out-receipt.pdf"
        got = json.loads(
            dispatch(
                "download",
                json.dumps(
                    {
                        "cap": after["receipt.pdf"]["cap"],
                        "servers": servers,
                        "dest": str(phone_out),
                    }
                ),
            )
        )
        assert got["ok"] is True, got
        assert phone_out.read_bytes() == added.read_bytes()
        desktop = tmp_path / "desktop-receipt.pdf"
        listed_names = subprocess.check_output(
            [TAHOE, "ls", "--node-url", url, dircap], text=True
        )
        assert "receipt.pdf" in listed_names, listed_names
        subprocess.check_call(
            [
                TAHOE,
                "get",
                "--node-url",
                url,
                after["receipt.pdf"]["cap"],
                str(desktop),
            ]
        )
        assert desktop.read_bytes() == added.read_bytes()
        clash = json.loads(
            dispatch(
                "put",
                json.dumps(
                    {
                        "cap": dircap,
                        "name": "receipt.pdf",
                        "path": str(blob),
                        "servers": servers,
                        "shares": shares,
                        "replace": False,
                    }
                ),
            )
        )
        assert clash["ok"] is False, clash
        assert "already" in clash["message"]
        assert phone_out.read_bytes() == added.read_bytes()
        replaced = json.loads(
            dispatch(
                "put",
                json.dumps(
                    {
                        "cap": dircap,
                        "name": "receipt.pdf",
                        "path": str(blob),
                        "servers": servers,
                        "shares": shares,
                        "replace": True,
                    }
                ),
            )
        )
        assert replaced["ok"] is True, replaced
        replaced_list = json.loads(
            dispatch("list", json.dumps({"cap": dircap, "servers": servers}))
        )
        replaced_cap = {row["name"]: row for row in replaced_list["children"]}["receipt.pdf"]["cap"]
        subprocess.check_call(
            [TAHOE, "get", "--node-url", url, replaced_cap, str(desktop)]
        )
        assert desktop.read_bytes() == blob.read_bytes()
        replaced_names = subprocess.check_output(
            [TAHOE, "ls", "--node-url", url, dircap], text=True
        )
        assert "receipt.pdf" in replaced_names
        removed = json.loads(
            dispatch(
                "remove",
                json.dumps(
                    {
                        "cap": dircap,
                        "name": "receipt.pdf",
                        "servers": servers,
                        "shares": shares,
                    }
                ),
            )
        )
        assert removed["ok"] is True, removed
        listed_gone = json.loads(
            dispatch("list", json.dumps({"cap": dircap, "servers": servers}))
        )
        gone_names = {row["name"] for row in listed_gone["children"]}
        assert "receipt.pdf" not in gone_names, listed_gone
        assert "beach.txt" in gone_names
        from lg_write import readonly_dir_cap

        ro = json.loads(
            dispatch(
                "put",
                json.dumps(
                    {
                        "cap": readonly_dir_cap(dircap),
                        "name": "nope.txt",
                        "path": str(added),
                        "servers": servers,
                        "shares": shares,
                    }
                ),
            )
        )
        assert ro["ok"] is False, ro
        # A directory of directories is a collective: the file must show up
        # in the flattened listing, not as a raw child the phone cannot see.
        collective = subprocess.check_output(
            [TAHOE, "mkdir", "--node-url", url], text=True
        ).strip()
        laptop = subprocess.check_output(
            [TAHOE, "mkdir", "--node-url", url], text=True
        ).strip()
        subprocess.check_call(
            [TAHOE, "ln", "--node-url", url, laptop, "%s/laptop" % collective]
        )
        phone_src = tmp_path / "from-phone.txt"
        phone_src.write_bytes(b"collective bytes from the phone\n")
        collective_put = json.loads(
            dispatch(
                "put",
                json.dumps(
                    {
                        "cap": collective,
                        "name": "from-phone.txt",
                        "path": str(phone_src),
                        "servers": servers,
                        "shares": shares,
                        "replace": False,
                    }
                ),
            )
        )
        assert collective_put["ok"] is True, collective_put
        assert collective_put.get("phone_dmd", "").startswith("URI:DIR2:")
        collective_list = json.loads(
            dispatch("list", json.dumps({"cap": collective, "servers": servers}))
        )
        assert collective_list["ok"] is True, collective_list
        collective_names = {row["name"]: row for row in collective_list["children"]}
        assert "from-phone.txt" in collective_names, collective_list
        collective_out = tmp_path / "out-from-phone.txt"
        collective_got = json.loads(
            dispatch(
                "download",
                json.dumps(
                    {
                        "cap": collective_names["from-phone.txt"]["cap"],
                        "servers": servers,
                        "dest": str(collective_out),
                    }
                ),
            )
        )
        assert collective_got["ok"] is True, collective_got
        assert collective_out.read_bytes() == phone_src.read_bytes()
        listing = subprocess.check_output(
            [TAHOE, "ls", "--node-url", url, collective], text=True
        )
        assert "phone" in listing
        assert "laptop" in listing
    finally:
        for proc in procs:
            proc.terminate()
        for proc in procs:
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
        for handle in logs:
            handle.close()
