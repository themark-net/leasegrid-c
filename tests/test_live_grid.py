"""Opt-in journey on a local dev-grid. Skipped unless LEASEGRID_LIVE_GRID=1.

Default pytest does not set that variable, so CI never starts Tahoe.

The journey matches the deanery-grok b3c0a03 live stations: offer-disk join,
client-only join, an app-made short code and the full join link both joining,
add folder through Up to date, recovery export and import, an offscreen PyQt5
window with screenshots, and a secret sweep of the logs that journey wrote.
The same flag also runs the extras from that replay: a loopback storage-address
override, a conflict, a missing folder, a stopped magic-folder, and the
connection chip parade.

Grid, homes, and screenshots stay under ./tmp. Listeners stay on loopback
(the grid on 127.0.0.1, the storage override on 127.0.0.2).
A short code uses the grid's local wormhole relay.
"""

from __future__ import annotations

import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_LIVE = os.environ.get("LEASEGRID_LIVE_GRID", "").strip().lower() in {"1", "true", "yes", "on"}

pytestmark = pytest.mark.skipif(
    not _LIVE,
    reason="set LEASEGRID_LIVE_GRID=1 to run the local grid journey",
)

HELLO = b"hello from leasegrid journey\n"
PASSPHRASE = "journey-horse-battery"
_SECRET_SHAPES = (
    re.compile(r"pb://"),
    re.compile(r"\b\d+-[A-Za-z]{2,}(?:-[A-Za-z]{2,})+\b"),
    re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----"),
)
# The public filter keeps a short URI:TYPE: label and replaces the body with
# REDACTED. An unredacted body still has a long base32 or hex run.
_URI_TOKEN = re.compile(r"URI:\S+")


def _safe(text: str) -> str:
    """Assertion text with invite material removed."""
    raw = text or ""
    raw = re.sub(r"pb://\S+", "pb://[redacted]", raw)
    raw = re.sub(r"https?://\S+", "[redacted-url]", raw)
    raw = re.sub(r"leasegrid:\S+", "[redacted-url]", raw)
    raw = re.sub(r"\b\d+-[A-Za-z0-9]+(?:-[A-Za-z0-9]+)+\b", "[redacted-code]", raw)
    if PASSPHRASE in raw:
        raw = raw.replace(PASSPHRASE, "[redacted]")
    return raw[:500]


def _port_open(port: int) -> bool:
    sock = socket.socket()
    try:
        sock.settimeout(0.3)
        return sock.connect_ex(("127.0.0.1", port)) == 0
    finally:
        sock.close()


def _hold_port() -> tuple[int, socket.socket]:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    return sock.getsockname()[1], sock


def _hold_consecutive(count: int) -> tuple[int, list[socket.socket]]:
    for _ in range(50):
        start, first = _hold_port()
        first.close()
        socks: list[socket.socket] = []
        try:
            for port in range(start, start + count):
                sock = socket.socket()
                sock.bind(("127.0.0.1", port))
                socks.append(sock)
        except OSError:
            for sock in socks:
                sock.close()
            continue
        return start, socks
    raise AssertionError("no free consecutive ports for the grid")


def _release(socks: list[socket.socket]) -> None:
    for sock in socks:
        try:
            sock.close()
        except OSError:
            pass


def _stop_group(proc: subprocess.Popen | None) -> None:
    if proc is None or proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except OSError:
        proc.terminate()
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            proc.kill()
        proc.wait(timeout=10)


def _tool_bin() -> Path:
    exe = Path(sys.executable)
    for folder in (ROOT / ".venv" / "bin", exe.parent, exe.resolve().parent):
        if (folder / "tahoe").is_file() and (folder / "magic-folder").is_file():
            return folder
    return ROOT / ".venv" / "bin"


def _start_grid(work: Path) -> tuple[subprocess.Popen, str, str, str]:
    """Start scripts/dev-grid.sh on ephemeral loopback ports. Return proc, furl, relay, issuer."""
    intro, intro_sock = _hold_port()
    issuer, issuer_sock = _hold_port()
    wormhole, worm_sock = _hold_port()
    storage_first, storage_socks = _hold_consecutive(3)
    held = [intro_sock, issuer_sock, worm_sock, *storage_socks]
    grid_dir = work / "grid"
    log_path = work / "grid.log"
    grid_dir.mkdir(parents=True)
    venv_bin = _tool_bin()
    env = os.environ.copy()
    for key in (
        "LEASEGRID_SYNC_HOME",
        "LEASEGRID_TAHOE_NODEDIR",
        "LEASEGRID_WORMHOLE_SERVER",
        "LEASEGRID_MF_PORT",
        "LEASEGRID_GATED",
        "LEASEGRID_NICKNAME",
    ):
        env.pop(key, None)
    env["PATH"] = str(venv_bin) + os.pathsep + env.get("PATH", "")
    env["LEASEGRID_DEVGRID_DIR"] = str(grid_dir)
    env["LEASEGRID_DEVGRID_INTRO_PORT"] = str(intro)
    env["LEASEGRID_DEVGRID_STORAGE_PORT_BASE"] = str(storage_first - 1)
    env["LEASEGRID_DEVGRID_STORAGE"] = "3"
    env["LEASEGRID_DEVGRID_ISSUER_LISTEN"] = "127.0.0.1:%d" % issuer
    env["LEASEGRID_DEVGRID_WORMHOLE"] = "local"
    env["LEASEGRID_DEVGRID_WORMHOLE_PORT"] = str(wormhole)
    env["LEASEGRID_DEVGRID_CHAIN"] = "none"
    env["PYTHONUNBUFFERED"] = "1"
    log_handle = log_path.open("w", encoding="utf-8")
    _release(held)
    proc = subprocess.Popen(
        ["stdbuf", "-oL", "-eL", "bash", str(ROOT / "scripts" / "dev-grid.sh"), "--chain", "none"],
        cwd=str(ROOT),
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    furl_path = grid_dir / "intro" / "private" / "introducer.furl"
    relay_path = grid_dir / "private" / "wormhole.url"
    storage_port = storage_first
    deadline = time.monotonic() + 120
    try:
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                raise AssertionError("dev-grid exited before it was ready; see %s" % log_path)
            furl = furl_path.read_text(encoding="utf-8").strip() if furl_path.is_file() else ""
            relay = relay_path.read_text(encoding="utf-8").strip() if relay_path.is_file() else ""
            issuer_up = _port_open(issuer)
            storage_up = _port_open(storage_port)
            if (
                furl.startswith("pb://")
                and relay.startswith("ws://127.0.0.1:")
                and issuer_up
                and storage_up
            ):
                return proc, furl, relay, "http://127.0.0.1:%d" % issuer
            time.sleep(0.5)
        raise AssertionError("dev-grid was not ready; see %s" % log_path)
    except Exception:
        _stop_group(proc)
        raise
    finally:
        log_handle.close()


def _open_window(home: Path, mf_port: int, issuer: str):
    from leasegrid_sync.app import MainWindow

    os.environ["LEASEGRID_SYNC_HOME"] = str(home)
    os.environ["LEASEGRID_MF_PORT"] = str(mf_port)
    os.environ.pop("LEASEGRID_TAHOE_NODEDIR", None)
    home.mkdir(parents=True, exist_ok=True)
    window = MainWindow(
        nodedir=home / "tahoe",
        home=home,
        issuer_url=issuer,
        autoload=False,
    )
    window.app.setQuitOnLastWindowClosed(False)
    window.show()
    window.win.resize(960, 700)
    window.app.processEvents()
    return window


def _retire(window) -> None:
    try:
        window.poll.stop()
    except Exception:
        pass
    try:
        window.shutdown()
    except Exception:
        pass
    try:
        window.win.hide()
    except Exception:
        pass


def _shot(widget, path: Path, *, private: bool = False) -> None:
    from PyQt5.QtWidgets import QApplication

    app = QApplication.instance()
    if app is not None:
        app.processEvents()
    path.parent.mkdir(parents=True, exist_ok=True)
    pixmap = widget.grab()
    if pixmap.isNull() or not pixmap.save(str(path)):
        raise AssertionError("could not save a screenshot at %s" % path.name)
    if path.stat().st_size < 500:
        raise AssertionError("screenshot %s is empty" % path.name)
    if private:
        os.chmod(path, 0o600)


def _wait_online(window, timeout: float = 45) -> None:
    deadline = time.monotonic() + timeout
    last = ""
    while time.monotonic() < deadline:
        last = window.status_chip.text()
        if last.startswith("Online"):
            return
        window.app.processEvents()
        time.sleep(0.4)
    raise AssertionError("chip stayed %r" % _safe(last))


def _join(window, invite: str, *, offer: bool) -> None:
    window.threat_ack.setChecked(True)
    window.offer_storage_cb.setChecked(offer)
    window.invite_edit.setText(invite)
    window.app.processEvents()
    if not window.join_btn.isEnabled():
        raise AssertionError("Join stayed disabled")
    window.join_btn.click()
    if window.stack.currentWidget() is not window.main_page:
        raise AssertionError("join did not open Folders: %s" % _safe(window.join_error.text()))
    _wait_online(window)


def _wait_up_to_date(window, timeout: float = 180) -> str:
    deadline = time.monotonic() + timeout
    last = ""
    while time.monotonic() < deadline:
        name = ""
        if window.table.rowCount() and window.table.item(0, 0) is not None:
            name = window.table.item(0, 0).text()
        if name:
            try:
                window.mf.scan_local(name)
            except Exception:
                pass
        try:
            window.refresh()
        except Exception:
            pass
        window.app.processEvents()
        item = window.table.item(0, 1) if window.table.rowCount() else None
        last = item.text() if item is not None else ""
        if last == "Up to date":
            return name
        if last in {"Conflict", "FAIL"}:
            raise AssertionError("folder status %s" % _safe(last))
        time.sleep(1)
    detail = _safe(window.folder_error.text())
    raise AssertionError("folder status stayed %s (%s)" % (_safe(last), detail))


def _wait_bytes(window, folder_name: str, path: Path, timeout: float = 180) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            window.mf.scan_local(folder_name)
        except Exception:
            pass
        window.app.processEvents()
        if path.is_file() and path.read_bytes() == HELLO:
            return
        time.sleep(1)
    raise AssertionError("restored folder did not receive the file")


def _filtered_log(path: Path) -> str:
    proc = subprocess.run(
        ["bash", str(ROOT / "packaging" / "tahoe-log-filter.sh")],
        input=path.read_bytes(),
        capture_output=True,
        check=False,
    )
    return proc.stdout.decode("utf-8", errors="replace")


def _uri_body_leaks(text: str) -> bool:
    for match in _URI_TOKEN.finditer(text):
        body = match.group(0).replace("REDACTED", "")
        if re.search(r"[A-Za-z2-7]{8,}", body) or re.search(r"[0-9A-Fa-f]{16,}", body):
            return True
    return False


def _assert_clean(text: str, where: str, needles: list[str]) -> None:
    for needle in needles:
        if needle and needle in text:
            raise AssertionError("%s contains a journey secret" % where)
    for pattern in _SECRET_SHAPES:
        if pattern.search(text):
            raise AssertionError("%s contains a secret shape" % where)
    if _uri_body_leaks(text):
        raise AssertionError("%s contains a capability" % where)


def _sweep(homes: list[Path], reports: list[str], needles: list[str]) -> None:
    for index, report in enumerate(reports):
        _assert_clean(report, "bug report %d" % index, needles)
    checked = 0
    for home in homes:
        logs = home / "logs"
        if not logs.is_dir():
            continue
        for path in logs.iterdir():
            if not path.is_file() or path.suffix != ".log":
                continue
            if path.stat().st_size > 5_000_000:
                continue
            raw = path.read_text(encoding="utf-8", errors="replace")
            if path.name == "sync-ui.log":
                _assert_clean(raw, "sync-ui.log", needles)
            else:
                _assert_clean(_filtered_log(path), "filtered %s" % path.name, needles)
            checked += 1
    if checked < 1:
        raise AssertionError("no log files were scanned")


def _tub_lines(nodedir: Path) -> tuple[str, str]:
    port = ""
    location = ""
    text = (nodedir / "tahoe.cfg").read_text(encoding="utf-8")
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("tub.port") and "=" in stripped:
            port = stripped.split("=", 1)[1].strip()
        elif stripped.startswith("tub.location") and "=" in stripped:
            location = stripped.split("=", 1)[1].strip()
    if not port or not location:
        raise AssertionError("the node did not publish a listen address")
    return port, location


def _listen_addrs(port: int) -> set[str]:
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
            addr, hex_port = parts[1].split(":")
            if hex_port.upper() == want:
                found.add(addr.upper())
    return found


def _see_storage_override(work, furl, issuer, mf_port, windows, homes, shots) -> None:
    """One loopback address replaces the default, and the port is not on every interface."""
    previous = os.environ.get("LEASEGRID_STORAGE_HOSTNAME")
    os.environ["LEASEGRID_STORAGE_HOSTNAME"] = "127.0.0.2"
    window = None
    try:
        window = _open_window(work / "home-override", mf_port, issuer)
        windows.append(window)
        homes.append(window.home)
        _join(window, furl, offer=True)
        from leasegrid_sync.backend import storage_offered

        if not storage_offered(window.tahoe.nodedir):
            raise AssertionError("storage override did not offer disk")
        port_line, location = _tub_lines(window.tahoe.nodedir)
        listen_port = int(port_line.split(":")[1])
        if location != "tcp:127.0.0.2:%d" % listen_port:
            raise AssertionError("the override did not replace the advertised address")
        short = socket.gethostname().split(".")[0]
        if short and not short[0].isdigit() and short in location:
            raise AssertionError("the storage address is the machine hostname")
        if "interface=127.0.0.2" not in port_line:
            raise AssertionError("the override is not bound to the chosen address")
        sock = socket.socket()
        try:
            sock.settimeout(3)
            sock.connect(("127.0.0.2", listen_port))
        finally:
            sock.close()
        listeners = _listen_addrs(listen_port)
        if "0200007F" not in listeners:
            raise AssertionError("the override is not listening on 127.0.0.2")
        if "00000000" in listeners or "00000000000000000000000000000000" in listeners:
            raise AssertionError("loopback storage is also listening on every interface")
        _shot(window.win, shots / "storage-override.png")
    finally:
        os.environ["LEASEGRID_STORAGE_HOSTNAME"] = previous or "127.0.0.1"
        if window is not None:
            _retire(window)


def _row_status(window, name: str) -> str:
    for row in range(window.table.rowCount()):
        item = window.table.item(row, 0)
        if item is None or item.text() != name:
            continue
        cell = window.table.item(row, 1)
        return cell.text() if cell is not None else ""
    return ""


def _nudge(window, name: str) -> None:
    try:
        window.mf.scan_local(name)
    except Exception:
        pass
    try:
        window.mf.poll_remote(name)
    except Exception:
        pass
    try:
        window.refresh()
    except Exception:
        pass
    window.app.processEvents()


def _see_conflict(offer, restored, offer_file: Path, restored_file: Path, name: str, shots) -> None:
    offer_file.write_bytes(b"alice edit\n")
    restored_file.write_bytes(b"bob edit\n")
    deadline = time.monotonic() + 150
    last_offer = ""
    last_restored = ""
    while time.monotonic() < deadline:
        _nudge(offer, name)
        _nudge(restored, name)
        last_offer = _row_status(offer, name)
        last_restored = _row_status(restored, name)
        if last_offer == "Conflict" or last_restored == "Conflict":
            winner = offer if last_offer == "Conflict" else restored
            _shot(winner.win, shots / "folder-conflict.png")
            return
        time.sleep(1)
    raise AssertionError(
        "neither computer showed Conflict (%s, %s)" % (_safe(last_offer), _safe(last_restored))
    )


def _see_missing_folder(window, shots) -> None:
    from leasegrid_sync.app import display_path

    item = window.table.item(0, 2) if window.table.rowCount() else None
    path = item.text() if item is not None else ""
    if not path:
        raise AssertionError("the folder row has no path")
    target = Path(path)
    if target.is_dir():
        shutil.rmtree(target)
    window.open_folder_path(path)
    window.app.processEvents()
    banner = window.folder_error.text()
    if "not on this computer any more" not in banner:
        raise AssertionError("missing-folder banner was %s" % _safe(banner))
    shown = display_path(path)
    if shown not in banner and target.name not in banner:
        raise AssertionError("missing-folder banner left out the folder")
    _shot(window.win, shots / "folder-missing.png")


def _see_stopped_magic_folder(window, name: str, shots) -> None:
    from leasegrid_sync.backend import SyncError

    window.mf.stop()
    if window.mf.is_running():
        raise AssertionError("magic-folder was still answering after stop")
    status, detail = window.mf.folder_status(name, "")
    # A clean exit rewrites the endpoint to "not running". No answer at all
    # says "not reachable". Either one is the service being down.
    down = "not running" in detail or "not reachable" in detail
    if status != "FAIL" or not down:
        raise AssertionError("stopped magic-folder said %s" % _safe("%s %s" % (status, detail)))
    window.show_folder_error(SyncError(detail, "Quit and reopen Leasegrid Sync."))
    window.app.processEvents()
    _shot(window.win, shots / "folder-service-down.png")
    try:
        window.refresh()
    except Exception:
        pass
    window.app.processEvents()
    if not window.mf.is_running():
        raise AssertionError(
            "refresh did not start magic-folder again: %s" % _safe(window.folder_error.text())
        )
    if window.table.rowCount() < 1:
        raise AssertionError("refresh dropped the folder: %s" % _safe(window.folder_error.text()))
    _shot(window.win, shots / "folder-service-back.png")


def _owned_pids(proc: subprocess.Popen) -> set[int]:
    owned = {proc.pid}
    stack = [proc.pid]
    while stack:
        current = stack.pop()
        path = Path("/proc/%d/task/%d/children" % (current, current))
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for item in raw.split():
            if item.isdigit():
                child = int(item)
                if child not in owned:
                    owned.add(child)
                    stack.append(child)
    try:
        listing = subprocess.check_output(
            ["ps", "-o", "pid=", "-g", str(os.getpgid(proc.pid))],
            text=True,
        )
    except (OSError, subprocess.CalledProcessError, ProcessLookupError):
        return owned
    for line in listing.splitlines():
        text = line.strip()
        if text.isdigit():
            owned.add(int(text))
    return owned


def _cmdline(pid: int) -> str:
    try:
        raw = Path("/proc/%d/cmdline" % pid).read_bytes()
    except OSError:
        return ""
    return raw.replace(b"\x00", b" ").decode("utf-8", "replace")


def _pid_for(nodedir: Path, owned: set[int]) -> int:
    needle = str(nodedir)
    for pid in owned:
        if needle in _cmdline(pid) and "tahoe" in _cmdline(pid):
            return pid
    pid_path = nodedir / "twistd.pid"
    if pid_path.is_file():
        text = pid_path.read_text(encoding="utf-8").strip()
        if text.isdigit() and int(text) in owned:
            return int(text)
    raise AssertionError("dev-grid node is not one this journey started")


def _ports_closed(ports: list[int], timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if all(not _port_open(port) for port in ports):
            return True
        time.sleep(0.3)
    return False


def _stop_nodedirs(proc: subprocess.Popen, nodedirs: list[Path]) -> None:
    owned = _owned_pids(proc)
    pids: list[int] = []
    ports: list[int] = []
    for nodedir in nodedirs:
        if not (nodedir / "tahoe.cfg").is_file():
            raise AssertionError("dev-grid node directory is missing")
        pids.append(_pid_for(nodedir, owned))
        port_line, _location = _tub_lines(nodedir)
        ports.append(int(port_line.split(":")[1]))
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
    if _ports_closed(ports, 15):
        return
    for pid in pids:
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass
    if not _ports_closed(ports, 8):
        raise AssertionError("a dev-grid node stayed up after stop")


def _pump_chip(window, predicate, timeout: float) -> str:
    deadline = time.monotonic() + timeout
    last = window.status_chip.text()
    while time.monotonic() < deadline:
        try:
            window.refresh()
        except Exception:
            pass
        window.app.processEvents()
        last = window.status_chip.text()
        if predicate(last):
            return last
        time.sleep(0.4)
    return last


def _see_chip_parade(window, proc: subprocess.Popen, grid_dir: Path, shots) -> None:
    """Online with no storage, then offline, then the client itself stopped."""
    storages = sorted(path for path in grid_dir.glob("storage-*") if path.is_dir())
    if len(storages) < 1:
        raise AssertionError("the dev-grid has no storage nodes")
    _stop_nodedirs(proc, storages)
    last = _pump_chip(window, lambda text: "connected to the friendnet" in text, 45)
    if "connected to the friendnet" not in last:
        raise AssertionError("chip stayed %s" % _safe(last))
    _shot(window.win, shots / "status-online-empty.png")
    _stop_nodedirs(proc, [grid_dir / "intro"])
    connecting = _pump_chip(window, lambda text: text.startswith("Connecting"), 8)
    if connecting.startswith("Connecting"):
        _shot(window.win, shots / "status-connecting.png")
    if connecting == "Offline":
        last = connecting
    else:
        last = _pump_chip(window, lambda text: text == "Offline", 40)
    if last != "Offline":
        raise AssertionError("chip stayed %s" % _safe(last))
    _shot(window.win, shots / "status-offline.png")
    window.tahoe.stop()
    last = _pump_chip(window, lambda text: "Can't reach" in text, 30)
    if "Can't reach" not in last:
        raise AssertionError("chip stayed %s" % _safe(last))
    _shot(window.win, shots / "status-could-not-check.png")


def test_live_journey_matches_replay_stations() -> None:
    """Offer disk, client-only, invites, folder, recovery, and the replay extras."""
    pytest.importorskip("PyQt5")
    venv_bin = _tool_bin()
    tahoe_bin = venv_bin / "tahoe"
    mf_bin = venv_bin / "magic-folder"
    if not tahoe_bin.is_file() or not mf_bin.is_file():
        pytest.fail("install .venv with pip install -e '.[sync,tahoe]' before the live journey")

    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    os.environ["PATH"] = str(venv_bin) + os.pathsep + os.environ.get("PATH", "")
    os.environ["LEASEGRID_TAHOE_BIN"] = str(tahoe_bin)
    os.environ["LEASEGRID_MAGIC_FOLDER_BIN"] = str(mf_bin)
    os.environ["LEASEGRID_STORAGE_HOSTNAME"] = "127.0.0.1"
    os.environ.pop("LEASEGRID_GATED", None)

    from leasegrid_sync.app import ExportRecoveryDialog, ImportRecoveryDialog, InviteShareDialog
    from leasegrid_sync.backend import storage_offered
    from leasegrid_sync.invite import is_wormhole_code, parse_invite

    stamp = time.strftime("%Y%m%dT%H%M%S") + "-" + os.urandom(3).hex()
    work = ROOT / "tmp" / "live-grid" / stamp
    shots = work / "screenshots"
    work.mkdir(parents=True)
    started = time.monotonic()
    grid_proc = None
    windows: list = []
    homes: list[Path] = []

    def phase(name: str) -> None:
        line = "phase %s %.1fs" % (name, time.monotonic() - started)
        print(line, flush=True)
        with (work / "phases.txt").open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    try:
        grid_proc, furl, relay, issuer = _start_grid(work)
        os.environ["LEASEGRID_WORMHOLE_SERVER"] = relay
        os.environ["LEASEGRID_ISSUER_URL"] = issuer
        phase("grid")

        mf_ports = [_hold_port() for _ in range(7)]
        _release([sock for _port, sock in mf_ports])
        ports = [port for port, _sock in mf_ports]

        offer = _open_window(work / "home-offer", ports[0], issuer)
        windows.append(offer)
        homes.append(offer.home)
        _join(offer, furl, offer=True)
        if not storage_offered(offer.tahoe.nodedir):
            raise AssertionError("offer-disk join did not enable storage")
        _shot(offer.win, shots / "offer-joined.png")
        phase("offer-disk")
        _see_storage_override(work, furl, issuer, ports[5], windows, homes, shots)
        phase("storage-override")

        client = _open_window(work / "home-client", ports[1], issuer)
        windows.append(client)
        homes.append(client.home)
        _join(client, furl, offer=False)
        if storage_offered(client.tahoe.nodedir):
            raise AssertionError("client-only join offered storage")
        _shot(client.win, shots / "client-only-joined.png")
        phase("client-only")
        _retire(client)

        notes = work / "notes"
        notes.mkdir()
        offer.QtWidgets.QFileDialog.getExistingDirectory = staticmethod(
            lambda *args, **kwargs: str(notes)
        )
        offer.add_btn.click()
        if offer.table.rowCount() < 1 or offer.table.item(0, 0) is None:
            raise AssertionError(
                "add folder did not add a row: %s" % _safe(offer.folder_error.text())
            )
        (notes / "hello.txt").write_bytes(HELLO)
        folder_name = _wait_up_to_date(offer)
        offer.refresh()
        offer.app.processEvents()
        _shot(offer.win, shots / "folder-up-to-date.png")
        phase("up-to-date")

        key_path = work / "recovery.leasegrid-recovery"
        export = ExportRecoveryDialog(offer.win, offer.recovery, offer.QtWidgets, default_dir=work)
        export.path_edit.setText(str(key_path))
        export.ack_loss.setChecked(True)
        export.ack_store.setChecked(True)
        export.pass_edit.setText(PASSPHRASE)
        export.confirm_edit.setText(PASSPHRASE)
        offer.app.processEvents()
        if not export.write_btn.isEnabled():
            raise AssertionError("export stayed disabled after both acknowledgements")
        export.dlg.show()
        offer.app.processEvents()
        _shot(export.dlg, shots / "recovery-export.png", private=True)
        export.write_btn.click()
        if export.written is None or not key_path.is_file():
            raise AssertionError("export did not write a key: %s" % _safe(export.status.text()))
        if key_path.stat().st_mode & 0o777 != 0o600:
            raise AssertionError("recovery key is not mode 0600")
        blob = key_path.read_bytes()
        if b"pb://" in blob or furl.encode("utf-8") in blob or PASSPHRASE.encode("utf-8") in blob:
            raise AssertionError("recovery key stored a secret in plaintext")
        phase("export")

        invite = InviteShareDialog(offer.win, offer, offer.QtWidgets)
        code = invite.panel.code_edit.text().strip()
        if not is_wormhole_code(code):
            raise AssertionError(
                "app did not show a short code: %s" % _safe(invite.panel.status.text())
            )
        invite.dlg.show()
        offer.app.processEvents()
        _shot(invite.dlg, shots / "invite-code.png", private=True)
        invite.panel.advanced.setChecked(True)
        offer.app.processEvents()
        link = invite.panel.join_link.text().strip()
        parsed = parse_invite(link)
        if parsed.kind == "code" or not parsed.token.startswith("pb://"):
            raise AssertionError("advanced control did not show a full join link")
        _shot(invite.dlg, shots / "invite-advanced.png", private=True)
        invite.dlg.accept()
        phase("invites-shown")

        by_link = _open_window(work / "home-link", ports[2], issuer)
        windows.append(by_link)
        homes.append(by_link.home)
        _join(by_link, link, offer=False)
        if storage_offered(by_link.tahoe.nodedir):
            raise AssertionError("join by full link offered storage")
        _shot(by_link.win, shots / "joined-by-link.png")
        phase("join-link")
        _retire(by_link)

        by_code = _open_window(work / "home-code", ports[3], issuer)
        windows.append(by_code)
        homes.append(by_code.home)
        _join(by_code, code, offer=False)
        if storage_offered(by_code.tahoe.nodedir):
            raise AssertionError("join by short code offered storage")
        _shot(by_code.win, shots / "joined-by-code.png")
        phase("join-code")
        _retire(by_code)

        restored = _open_window(work / "home-restore", ports[4], issuer)
        windows.append(restored)
        homes.append(restored.home)
        restored.recovery.folder_root = work / "restored"
        importer = ImportRecoveryDialog(
            restored.win, restored.recovery, restored.QtWidgets, path=key_path
        )
        importer.pass_edit.setText(PASSPHRASE)
        importer.dlg.show()
        restored.app.processEvents()
        _shot(importer.dlg, shots / "recovery-import.png", private=True)
        importer.import_btn.click()
        if importer.result is None:
            raise AssertionError("import did not finish: %s" % _safe(importer.status.text()))
        if (
            folder_name not in importer.result.folders
            and folder_name not in importer.result.skipped
        ):
            raise AssertionError("import did not restore the folder")
        restored.apply_restore_result(importer.result)
        arrived = restored.recovery.folder_root / folder_name / "hello.txt"
        _wait_bytes(restored, folder_name, arrived)
        restored.refresh()
        restored.app.processEvents()
        _shot(restored.win, shots / "recovery-imported.png")
        phase("import")

        _see_conflict(offer, restored, notes / "hello.txt", arrived, folder_name, shots)
        phase("conflict")
        _see_missing_folder(offer, shots)
        phase("missing-folder")
        _see_stopped_magic_folder(offer, folder_name, shots)
        phase("magic-folder-stopped")

        chips = _open_window(work / "home-chips", ports[6], issuer)
        windows.append(chips)
        homes.append(chips.home)
        _join(chips, furl, offer=False)
        if storage_offered(chips.tahoe.nodedir):
            raise AssertionError("chip window offered storage")
        reports = [offer.bug_report_text(), restored.bug_report_text()]
        _retire(offer)
        _retire(restored)
        _see_chip_parade(chips, grid_proc, work / "grid", shots)
        phase("chips")
        reports.append(chips.bug_report_text())
        _sweep(homes, reports, [furl, code, link, PASSPHRASE])
        phase("secrets")
    finally:
        for window in windows:
            _retire(window)
        _stop_group(grid_proc)

    elapsed = time.monotonic() - started
    (work / "duration.txt").write_text("%.1f\n" % elapsed, encoding="utf-8")
    print("live journey PASS in %.1fs" % elapsed, flush=True)
