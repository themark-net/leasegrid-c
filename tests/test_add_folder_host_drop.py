"""#30 follow-up: a storage host drops while Add folder is running.

Fake hosts only: Tahoe's welcome page and the Magic Folder daemon are local
HTTP stand-ins, and `magic-folder` is a fake binary. The window's Add folder
click, the backend add and the hosts check are the real ones.

Every case must end cleanly: Design's "X of N" hosts pair or the generic add
pair, no folder left in Magic Folder for the failed add, nothing in the folder
list, and no hang (each case has a hard timeout).
"""

from __future__ import annotations

import os
import time
import urllib.request
from pathlib import Path
from unittest.mock import patch

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PyQt5 = pytest.importorskip("PyQt5")
pytest.importorskip("segno")

from leasegrid_sync import backend as backend_mod  # noqa: E402
from leasegrid_sync.app import MainWindow  # noqa: E402
from tests.qr_decode import write_executable  # noqa: E402
from tests.test_dogfood_folder_hosts import _Daemon, _Grid  # noqa: E402
from tests.test_sync_folder_journey import FURL, _free_port, _wait_until  # noqa: E402

HOSTS_MSG = "Can't add a folder yet. Only 0 of 3 hosts are connected."
HOSTS_NEXT = "Wait until Hosts shows 3 connected, then click Add folder again."
GENERIC_MSG = "Couldn't add the folder."
GENERIC_NEXT = "Wait a minute, then click Add folder again."


def _mf_cli(spool: Path, drop_on: Path, mode_file: Path) -> str:
    """Fake `magic-folder`.

    add modes (read from ``mode_file`` at run time):
      drop  - the hosts go away during the add and stay away; exit 1
      blip  - the hosts blink out during the add and are back when it ends; exit 1
      slow  - the add stalls on a dropped host (sleeps past the timeout); exit 1
      lost  - the daemon finished the add but the answer was lost; exit 1
      partial - one of three hosts drops during the add, which still
                completes at shares.needed (2) below shares.happy (3); exit 0
    leave removes the folder from the daemon's list.
    """
    return "\n".join(
        [
            "import json, sys, time",
            "from pathlib import Path",
            "args = sys.argv[1:]",
            "spool = Path(%r)" % str(spool),
            "drop_on = Path(%r)" % str(drop_on),
            "mode = Path(%r).read_text(encoding='utf-8').strip()" % str(mode_file),
            "def rows():",
            "    if not spool.is_file():",
            "        return []",
            "    return [json.loads(x) for x in spool.read_text(encoding='utf-8').splitlines() if x.strip()]",
            "def save(items):",
            "    spool.write_text(''.join(json.dumps(i) + '\\n' for i in items), encoding='utf-8')",
            "if 'leave' in args:",
            "    name = args[args.index('--name') + 1]",
            "    save([r for r in rows() if r['name'] != name])",
            "    spool.with_suffix('.left').write_text(name, encoding='utf-8')",
            "    raise SystemExit(0)",
            "if 'add' in args:",
            "    name = args[args.index('--name') + 1]",
            "    spool.with_suffix('.called').write_text('add', encoding='utf-8')",
            "    if mode in ('drop', 'slow'):",
            "        drop_on.write_text('dropped', encoding='utf-8')",
            "    if mode == 'slow':",
            "        time.sleep(4)",
            "    if mode == 'partial':",
            "        Path(%r).write_text('2', encoding='utf-8')" % str(drop_on.with_name("hosts-left")),
            "        save(rows() + [{'name': name, 'path': args[-1]}])",
            "        raise SystemExit(0)",
            "    if mode == 'lost':",
            "        save(rows() + [{'name': name, 'path': args[-1]}])",
            "    sys.stderr.write('Traceback: tahoe 500 UploadUnhappinessError at pb://secret@x/y\\n')",
            "    raise SystemExit(1)",
            "raise SystemExit(0)",
        ]
    )


class _PartialGrid(_Grid):
    """The fake grid, plus ``hosts-left``: when the fake add writes it, only that many stay up."""

    def body(self) -> dict:
        left = self.drop_on.with_name("hosts-left")
        if left.exists() and not self.drop_on.exists():
            up = int(left.read_text(encoding="utf-8"))
            data = super().body()
            for i, server in enumerate(data["servers"], start=1):
                server["connection_status"] = "connected" if i <= up else ""
            return data
        return super().body()


@pytest.fixture
def drop_rig(tmp_path: Path, monkeypatch):
    home = tmp_path / "home"
    nodedir = home / "tahoe"
    nodedir.mkdir(parents=True)
    spool = tmp_path / "mf-add.jsonl"
    drop_on = tmp_path / "hosts-dropped"
    mode_file = tmp_path / "mode"
    made: dict = {}

    def build(mode: str):
        mode_file.write_text(mode, encoding="utf-8")
        g = _PartialGrid(3, drop_on)
        d = _Daemon(spool)
        g.start()
        d.start()
        made["g"], made["d"] = g, d
        _wait_until("http://127.0.0.1:%d/?t=json" % g.port)
        _wait_until(urllib.request.Request(
            "http://127.0.0.1:%d/v1/magic-folder" % d.port,
            headers={"Authorization": "Bearer %s" % d.token},
        ))
        cfg = home / "magic-folder"
        cfg.mkdir(parents=True, exist_ok=True)
        (cfg / "api_token").write_text(d.token + "\n", encoding="utf-8")
        (cfg / "api_client_endpoint").write_text("tcp:127.0.0.1:%d\n" % d.port, encoding="utf-8")
        (nodedir / "node.url").write_text("http://127.0.0.1:%d/\n" % g.port, encoding="utf-8")
        (nodedir / "tahoe.cfg").write_text(
            "[node]\nnickname = alice\n[client]\nintroducer.furl = %s\n"
            "shares.needed = 2\nshares.happy = 3\nshares.total = 3\n[storage]\nenabled = false\n" % FURL,
            encoding="utf-8",
        )
        monkeypatch.setenv("LEASEGRID_SYNC_HOME", str(home))
        monkeypatch.setenv("LEASEGRID_MF_PORT", str(_free_port()))
        monkeypatch.delenv("LEASEGRID_GATED", raising=False)
        monkeypatch.setenv(
            "LEASEGRID_MAGIC_FOLDER_BIN",
            write_executable(tmp_path / "bin", _mf_cli(spool, drop_on, mode_file), name="magic-folder"),
        )
        window = MainWindow(nodedir=nodedir, home=home, autoload=False)
        window.poll.stop()
        # Joined, so refresh() really lists folders. Without this the "no row"
        # checks below would pass on an empty table that was never filled.
        window._joined = True
        made["w"] = window
        return window, d, spool

    yield build
    w = made.get("w")
    if w is not None:
        w.poll.stop()
        w.win.hide()
        if w.tray is not None:
            w.tray.hide()
    for key in ("g", "d"):
        if key in made:
            made[key].stop()


def _click_add(window: MainWindow, folder: Path) -> tuple[str, float]:
    folder.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    with patch.object(window.QtWidgets.QFileDialog, "getExistingDirectory", return_value=str(folder)):
        window.on_add_folder()
    return window.folder_error.text(), time.monotonic() - start


def _assert_clean(window: MainWindow, daemon: _Daemon, spool: Path, text: str, folder: Path) -> None:
    assert spool.with_suffix(".called").exists(), "magic-folder add never ran"
    assert daemon.folders() == {}, "the failed add left a folder in Magic Folder"
    rows_before = window.table.rowCount()
    window.refresh()
    assert window.table.rowCount() == 0, "the failed add shows up in the folder list"
    assert rows_before == 0
    for bad in ("#30", "Traceback", "500", "pb://", "Retry", "Added folder", str(folder)):
        assert bad not in text, (bad, text)


@pytest.mark.timeout(60)
def test_hosts_that_drop_during_the_add_and_stay_down_show_the_hosts_pair(drop_rig, tmp_path: Path):
    window, d, spool = drop_rig("drop")
    text, _ = _click_add(window, tmp_path / "docs")
    assert HOSTS_MSG in text
    assert "Next: " + HOSTS_NEXT in text
    _assert_clean(window, d, spool, text, tmp_path / "docs")


@pytest.mark.timeout(60)
def test_hosts_that_blink_out_during_the_add_show_the_generic_pair(drop_rig, tmp_path: Path):
    """The add failed on the drop, but every host is back by the time Sync checks."""
    window, d, spool = drop_rig("blip")
    text, _ = _click_add(window, tmp_path / "docs")
    assert GENERIC_MSG in text
    assert "Next: " + GENERIC_NEXT in text
    _assert_clean(window, d, spool, text, tmp_path / "docs")


@pytest.mark.timeout(60)
def test_an_add_that_stalls_on_a_dropped_host_times_out_with_a_pair(drop_rig, tmp_path: Path, monkeypatch):
    monkeypatch.setattr(backend_mod, "MF_ADD_TIMEOUT", 1.0, raising=False)
    window, d, spool = drop_rig("slow")
    text, took = _click_add(window, tmp_path / "docs")
    assert took < 30, "Add folder hung for %.1fs" % took
    assert HOSTS_MSG in text
    assert "Next: " + HOSTS_NEXT in text
    _assert_clean(window, d, spool, text, tmp_path / "docs")


@pytest.mark.timeout(60)
def test_a_timed_out_add_with_hosts_back_shows_the_generic_pair_and_no_log_path(
    drop_rig, tmp_path: Path, monkeypatch
):
    monkeypatch.setattr(backend_mod, "MF_ADD_TIMEOUT", 1.0, raising=False)
    window, d, spool = drop_rig("slow")
    real = window.mf._run_cli

    def run_then_hosts_return(args, timeout=60.0):
        try:
            return real(args, timeout=timeout)
        finally:
            (tmp_path / "hosts-dropped").unlink(missing_ok=True)

    with patch.object(window.mf, "_run_cli", side_effect=run_then_hosts_return):
        text, took = _click_add(window, tmp_path / "docs")
    assert took < 30, "Add folder hung for %.1fs" % took
    assert GENERIC_MSG in text
    assert "Next: " + GENERIC_NEXT in text
    assert "log" not in text.lower()
    _assert_clean(window, d, spool, text, tmp_path / "docs")


@pytest.mark.timeout(60)
def test_an_add_the_daemon_finished_after_a_failure_is_not_left_half_added(drop_rig, tmp_path: Path):
    """The daemon wrote the folder but the add reported failure: Sync must not keep it."""
    window, d, spool = drop_rig("lost")
    text, _ = _click_add(window, tmp_path / "docs")
    assert GENERIC_MSG in text
    assert "Next: " + GENERIC_NEXT in text
    assert spool.with_suffix(".left").read_text(encoding="utf-8") == "docs"
    _assert_clean(window, d, spool, text, tmp_path / "docs")
    assert (tmp_path / "docs").is_dir(), "the local folder must stay on disk"


@pytest.mark.timeout(60)
def test_after_a_drop_the_next_add_with_all_hosts_back_succeeds(drop_rig, tmp_path: Path):
    """Ending cleanly means the same folder can be added once the hosts return."""
    window, d, spool = drop_rig("drop")
    _click_add(window, tmp_path / "docs")
    (tmp_path / "hosts-dropped").unlink()
    (tmp_path / "mode").write_text("ok", encoding="utf-8")
    real = window.mf._run_cli

    def add_ok(args, timeout=60.0):
        if "add" in args:
            spool.write_text('{"name": "docs", "path": "%s"}\n' % (tmp_path / "docs").as_posix(),
                             encoding="utf-8")
            import subprocess
            return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")
        return real(args, timeout=timeout)

    with patch.object(window.mf, "_run_cli", side_effect=add_ok):
        text, _ = _click_add(window, tmp_path / "docs")
    assert "Added folder docs" in text
    assert list(d.folders()) == ["docs"]


@pytest.mark.timeout(60)
def test_an_add_that_completes_at_needed_below_happy_succeeds_with_no_error_pair(drop_rig, tmp_path: Path):
    """PM 3:37am (option A): one of three hosts drops mid-add and the add still completes.

    Magic Folder's mutable directories need shares.needed (2) hosts, so the
    folder is real and readable. Sync reports it as added, with no hosts pair
    and no generic pair, and keeps it (no leave).
    """
    window, d, spool = drop_rig("partial")
    text, _ = _click_add(window, tmp_path / "docs")
    assert text == "Added folder docs"
    for bad in (HOSTS_MSG, "hosts are connected", GENERIC_MSG, "FAIL", "Next:", "Retry"):
        assert bad not in text, (bad, text)
    status = window.tahoe.connection_status()
    assert status.servers_connected == 2, "the grid did not drop a host during the add"
    assert list(d.folders()) == ["docs"]
    assert not spool.with_suffix(".left").exists(), "Sync removed a folder that was added"
    assert window.table.rowCount() == 1
