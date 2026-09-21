"""Tahoe + Magic Folder control plane for Leasegrid Sync (no Qt, no WUI)."""

from __future__ import annotations

import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote

from . import APP_ID

DEFAULT_TAHOE_NODEDIR = Path.home() / ".tahoe"
DEFAULT_MF_PORT = 19780
GRID_NICKNAME = "lab-friendnet"
# needed, happy, total for a client Sync creates itself. The lab friendnet has
# three storage nodes with shares.happy = 3; Tahoe's 3/7/10 default would make
# every upload fail there. Override with LEASEGRID_SHARES="n,h,t".
DEFAULT_SHARES = (2, 3, 3)
CREDIT_PLUGIN_NAME = "leasegrid-zkap-v0"
CREDIT_PLUGIN_SECTION = "[storageclient.plugins.%s]" % CREDIT_PLUGIN_NAME
TAHOE_START_TIMEOUT = 30.0
STORAGE_SETTLE_SECONDS = 6.0
# `tahoe invite` prints a code only once the inviter is parked on the relay, so a
# code join normally completes in seconds; this bounds a dead code / relay.
WORMHOLE_JOIN_TIMEOUT = 120.0
TAHOE_CONNECT_TIMEOUT = 30.0


class SyncError(Exception):
    """Buyer-visible failure. ``next_hint`` is the in-window Next line."""

    def __init__(self, message: str, next_hint: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.next_hint = next_hint

    def banner(self) -> str:
        text = self.message if self.message.startswith("FAIL") else "FAIL — " + self.message
        if self.next_hint:
            return text + "\nNext: " + self.next_hint
        return text


@dataclass
class ConnectionStatus:
    state: str  # Connecting | Connected | Offline | FAIL
    detail: str = ""
    introducer_ok: bool = False
    servers_connected: int = 0
    server_nicknames: list[str] = field(default_factory=list)


@dataclass
class FolderRow:
    name: str
    path: str
    status: str
    detail: str = ""


def default_home(platform: Optional[str] = None) -> Path:
    """Sync's data dir: Tahoe node, Magic Folder config, wallet, logs.

    LEASEGRID_SYNC_HOME wins. Otherwise the OS convention: %LOCALAPPDATA% on
    Windows, ~/Library/Application Support on macOS, $XDG_DATA_HOME or
    ~/.local/share elsewhere.
    """
    override = os.environ.get("LEASEGRID_SYNC_HOME")
    if override:
        return Path(override).expanduser()
    plat = platform or sys.platform
    if plat.startswith("win"):
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        return (Path(base) if base else Path.home() / "AppData" / "Local") / APP_ID
    if plat == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_ID
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / APP_ID
    return Path.home() / ".local" / "share" / APP_ID


def default_nodedir() -> Path:
    """Explicit env wins; then a pre-existing ~/.tahoe; else a Sync-owned dir.

    A fresh install has no ~/.tahoe, and Sync should create its own node under
    its data home rather than squat on Tahoe's default path.
    """
    env = os.environ.get("LEASEGRID_TAHOE_NODEDIR")
    if env:
        return Path(env).expanduser()
    if (DEFAULT_TAHOE_NODEDIR / "tahoe.cfg").is_file():
        return DEFAULT_TAHOE_NODEDIR
    return default_home() / "tahoe"


def storage_hostname() -> str:
    """Where this node advertises storage. Lab default is loopback.

    Set ``LEASEGRID_STORAGE_HOSTNAME`` to a LAN name or IP when other machines
    should put shares here. Unpaid join and offer use the same invite either way.
    """
    return (os.environ.get("LEASEGRID_STORAGE_HOSTNAME") or "127.0.0.1").strip() or "127.0.0.1"


def shares_config() -> tuple[int, int, int]:
    raw = os.environ.get("LEASEGRID_SHARES", "")
    if raw:
        try:
            parts = [int(p) for p in raw.split(",")]
        except ValueError:
            parts = []
        if len(parts) == 3 and 0 < parts[0] <= parts[1] <= parts[2]:
            return parts[0], parts[1], parts[2]
    return DEFAULT_SHARES


def frozen_sibling(name: str) -> Optional[str]:
    """In a PyInstaller bundle the daemons sit next to this executable.

    The bundle ships `tahoe` / `magic-folder` (`.exe` on Windows) beside
    `leasegrid-sync`; those must win over anything on the user's PATH so the
    versions we tested together are the ones that run.
    """
    if not getattr(sys, "frozen", False):
        return None
    here = Path(sys.executable).parent
    for candidate in (here / name, here / (name + ".exe")):
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def which_bin(name: str, env_key: str) -> Optional[str]:
    env = os.environ.get(env_key)
    if env:
        p = Path(env).expanduser()
        if p.is_file() and os.access(p, os.X_OK):
            return str(p)
    sibling = frozen_sibling(name)
    if sibling:
        return sibling
    found = shutil.which(name)
    return found


def redact_furl(value: str) -> str:
    text = value.strip()
    if text.startswith("pb://") and len(text) > 12:
        return text[:8] + "…" + text[-6:]
    return text


def popen_hidden(cmd: list[str], log_f) -> subprocess.Popen:
    """Spawn a daemon without a console flash (Windows CREATE_NO_WINDOW)."""
    kwargs: dict[str, Any] = {
        "stdin": subprocess.PIPE,
        "stdout": log_f,
        "stderr": subprocess.STDOUT,
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.Popen(cmd, **kwargs)


def storage_offered(nodedir: Path) -> bool:
    """True when this Tahoe node is configured to store shares for others."""
    import configparser

    cfg = configparser.ConfigParser()
    path = Path(nodedir) / "tahoe.cfg"
    if not path.is_file():
        return False
    cfg.read(path, encoding="utf-8")
    if not cfg.has_section("storage"):
        return False
    try:
        return cfg.getboolean("storage", "enabled", fallback=True)
    except ValueError:
        return True


# magic-wormhole code as printed by `tahoe invite`: "7-guitarist-revenge"
WORMHOLE_CODE_RE = re.compile(r"^[0-9]{1,3}(-[a-z0-9]+){2,}$")


def is_wormhole_code(text: str) -> bool:
    return bool(WORMHOLE_CODE_RE.match((text or "").strip().lower()))


# Tahoe 1.20 `create-node --join` (and create-client) writes the invited encoding as bytes reprs
# ("shares.needed = b'3'"), which `tahoe run` then rejects with ValueError.
JOINED_BYTES_RE = re.compile(r"^(\s*shares\.(?:needed|happy|total)\s*=\s*)b'([0-9]+)'\s*$")


def fix_joined_shares(cfg_path: Path) -> bool:
    """Rewrite b'N' share counts left by `--join`. Returns True if changed."""
    if not cfg_path.is_file():
        return False
    changed = False
    out: list[str] = []
    for line in cfg_path.read_text(encoding="utf-8").splitlines():
        m = JOINED_BYTES_RE.match(line)
        if m:
            line = "%s%s" % (m.group(1), m.group(2))
            changed = True
        out.append(line)
    if changed:
        cfg_path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return changed


def validate_invite(raw: str) -> str:
    """Accept a join URL, a pb:// introducer furl, or a short `tahoe invite` code."""
    from .invite import parse_invite

    return parse_invite(raw).token


def validate_introducer_furl(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        raise SyncError(
            "could not join this friendnet. Invite is empty.",
            "paste the invite from your inviter (a short code like 7-word-word, or a pb:// furl).",
        )
    low = text.lower()
    if low.startswith("http://") or low.startswith("https://"):
        raise SyncError(
            "could not join this friendnet. That looks like a web URL.",
            "Leasegrid Sync does not use the Tahoe web UI. Paste the invite code or pb:// furl.",
        )
    if not text.startswith("pb://"):
        raise SyncError(
            "could not join this friendnet. Invite code invalid.",
            "ask your inviter for a fresh invite (short code like 7-word-word, or pb://…); Retry.",
        )
    rest = text[5:]
    if "/" not in rest or len(rest) < 12:
        raise SyncError(
            "could not join this friendnet. Invite furl is malformed.",
            "get a fresh code from your inviter; check network; Retry.",
        )
    return text


def endpoint_to_url(endpoint: str) -> str:
    text = endpoint.strip()
    if text in ("", "not running"):
        raise SyncError(
            "Magic Folder daemon is not running.",
            "Restart Sync. If this persists, check that magic-folder is on PATH.",
        )
    parts = text.split(":")
    if parts[0] != "tcp" or len(parts) < 3:
        raise SyncError(
            "Magic Folder endpoint is unreadable.",
            "Restart Sync. Delete the daemon config only if you know it is stale.",
        )
    host = parts[1] or "127.0.0.1"
    port = parts[2]
    if "=" in host:
        host = "127.0.0.1"
    return "http://%s:%s" % (host, port)


class TahoeClient:
    def __init__(
        self,
        nodedir: Optional[Path] = None,
        tahoe_bin: Optional[str] = None,
        home: Optional[Path] = None,
    ) -> None:
        self.nodedir = Path(nodedir) if nodedir else default_nodedir()
        self.tahoe_bin = tahoe_bin or which_bin("tahoe", "LEASEGRID_TAHOE_BIN")
        self.home = Path(home) if home else default_home()
        self.log_path = self.home / "logs" / "tahoe.log"
        self._proc: Optional[subprocess.Popen] = None

    # -- process management -------------------------------------------------

    def require_bin(self) -> str:
        if not self.tahoe_bin:
            raise SyncError(
                "could not join this friendnet. The Tahoe client is not installed.",
                "install it next to Sync: pip install 'leasegrid-zkap-lab[sync,tahoe]'; Retry.",
            )
        return self.tahoe_bin

    def is_reachable(self) -> bool:
        try:
            self.welcome(timeout=2.0)
            return True
        except SyncError:
            return False

    def create_client(self, invite: str, shares: Optional[tuple[int, int, int]] = None) -> None:
        """Client-only node: ``create-node --no-storage``. Prefer ``create_node``."""
        self.create_node(invite, shares=shares, offer_storage=False)

    def create_node(
        self,
        invite: str,
        shares: Optional[tuple[int, int, int]] = None,
        offer_storage: bool = True,
    ) -> None:
        """``tahoe create-node`` into self.nodedir.

        Unpaid join and offer are the same command. ``offer_storage=False`` adds
        ``--no-storage --listen=none``. ``invite`` is a pb:// introducer furl
        (we pick the encoding) or a short ``tahoe invite`` code (the inviter's
        introducer + encoding arrive through magic-wormhole).
        """
        if self.has_nodedir():
            return
        if self.nodedir.exists() and any(self.nodedir.iterdir()):
            raise SyncError(
                "could not join this friendnet. %s exists but is not a Tahoe node."
                % self.nodedir,
                "move that directory aside or set LEASEGRID_TAHOE_NODEDIR; Retry.",
            )
        cmd = [self.require_bin()]
        relay = os.environ.get("LEASEGRID_WORMHOLE_SERVER")
        if relay:
            cmd += ["--wormhole-server", relay]
        cmd += [
            "create-node",
            "--nickname=%s" % (os.environ.get("LEASEGRID_NICKNAME") or "leasegrid-sync"),
            "--webport=tcp:0:interface=127.0.0.1",
        ]
        if offer_storage:
            storage_dir = self.home / "storage"
            storage_dir.mkdir(parents=True, exist_ok=True)
            cmd += [
                "--listen=tcp",
                "--hostname=%s" % storage_hostname(),
                "--storage-dir=%s" % storage_dir,
            ]
        else:
            cmd += ["--no-storage", "--listen=none"]
        code = is_wormhole_code(invite)
        if code:
            cmd.append("--join=%s" % invite.strip().lower())
            timeout = WORMHOLE_JOIN_TIMEOUT
        else:
            needed, happy, total = shares or shares_config()
            cmd += [
                "--introducer=%s" % invite,
                "--shares-needed=%d" % needed,
                "--shares-happy=%d" % happy,
                "--shares-total=%d" % total,
            ]
            timeout = 120
        cmd.append(str(self.nodedir))
        self.nodedir.parent.mkdir(parents=True, exist_ok=True)
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout, check=False
            )
        except subprocess.TimeoutExpired as exc:
            shutil.rmtree(self.nodedir, ignore_errors=True)
            if code:
                raise SyncError(
                    "could not join this friendnet. Nobody answered invite code %s in %ds."
                    % (invite, int(timeout)),
                    "your inviter must keep `tahoe invite` running until you join; "
                    "get a fresh code; Retry.",
                ) from exc
            raise SyncError(
                "could not join this friendnet. tahoe create-node did not run: %s" % exc,
                "check that tahoe is installed; Retry.",
            ) from exc
        except OSError as exc:
            raise SyncError(
                "could not join this friendnet. tahoe create-node did not run: %s" % exc,
                "check that tahoe is installed; Retry.",
            ) from exc
        if proc.returncode != 0:
            shutil.rmtree(self.nodedir, ignore_errors=True)
            err = (proc.stderr or proc.stdout or "create-node failed").strip().split("\n")[-1]
            if code:
                raise SyncError(
                    "could not join this friendnet. Invite code %s was not accepted: %s"
                    % (invite, err),
                    "codes are single-use and expire; ask your inviter for a fresh one; Retry.",
                )
            raise SyncError(
                "could not join this friendnet. Tahoe could not create a node: %s" % err,
                "check the invite code with your inviter; Retry.",
            )
        if code:
            fix_joined_shares(self.nodedir / "tahoe.cfg")
        self.ensure_credit_plugin()

    def ensure_credit_plugin(self) -> bool:
        """Enable the ZKAP storage plugin in tahoe.cfg, pointed at this app's wallet.

        Harmless on an ungated grid (Tahoe falls back to anonymous storage when a
        node does not announce the plugin); on a gated grid it is what pays for
        uploads. force_foolscap is required: 1.20 prefers GBS/HTTP when a node
        announces it, and the HTTP path never consults storage plugins.
        Edits are line-based so Tahoe's commented template survives.
        Returns True when the file changed (a running node needs a restart).
        """
        cfg_path = self.nodedir / "tahoe.cfg"
        if not cfg_path.is_file():
            return False
        text = cfg_path.read_text(encoding="utf-8")
        if CREDIT_PLUGIN_SECTION in text:
            return False
        lines = text.splitlines()
        out: list[str] = []
        in_client = False
        added_plugins = False
        client_lines = ["storage.plugins = %s" % CREDIT_PLUGIN_NAME, "force_foolscap = true"]
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                if in_client and not added_plugins:
                    out += client_lines
                    added_plugins = True
                in_client = stripped == "[client]"
            elif in_client and (
                stripped.startswith("storage.plugins") or stripped.startswith("force_foolscap")
            ):
                continue  # replaced by client_lines
            out.append(line)
        if in_client and not added_plugins:
            out += client_lines
            added_plugins = True
        if not added_plugins:
            out += ["", "[client]"] + client_lines
        out += [
            "",
            CREDIT_PLUGIN_SECTION,
            "wallet-path = %s" % (self.home / "credit-wallet.json"),
            "grants-path = %s" % (self.home / "credit-grants.json"),
            "recent-path = %s" % (self.home / "credit-recent.json"),
        ]
        cfg_path.write_text("\n".join(out) + "\n", encoding="utf-8")
        return True

    def start(self, timeout: float = TAHOE_START_TIMEOUT) -> None:
        """Run `tahoe run` as a child, holding stdin (Tahoe exits when stdin closes)."""
        if self.is_reachable():
            return
        if not self.has_nodedir():
            raise SyncError(
                "could not join this friendnet. No Tahoe node at %s." % self.nodedir,
                "paste an introducer furl to create one; Retry.",
            )
        if self._proc is not None and self._proc.poll() is None:
            return
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        log_f = open(self.log_path, "ab")
        try:
            self._proc = popen_hidden(
                [self.require_bin(), "run", str(self.nodedir)],
                log_f,
            )
        except OSError as exc:
            log_f.close()
            raise SyncError(
                "could not join this friendnet. Tahoe did not start: %s" % exc,
                "check that tahoe is installed; Retry.",
            ) from exc
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._proc.poll() is not None:
                tail = _tail(self.log_path)
                self._proc = None
                raise SyncError(
                    "could not join this friendnet. Tahoe exited while starting.",
                    "see %s (%s); Retry." % (self.log_path, tail),
                )
            if self.is_reachable():
                return
            time.sleep(0.3)
        raise SyncError(
            "could not join this friendnet. Tahoe did not become ready in %ds." % int(timeout),
            "see %s; Retry." % self.log_path,
        )

    def stop(self) -> None:
        proc = self._proc
        if proc is None:
            return
        try:
            if proc.stdin:
                proc.stdin.close()
        except OSError:
            pass
        try:
            proc.terminate()
            proc.wait(timeout=10)
        except Exception:
            try:
                proc.kill()
            except OSError:
                pass
        self._proc = None

    def owns_process(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def wait_connected(self, timeout: float = TAHOE_CONNECT_TIMEOUT) -> ConnectionStatus:
        """Poll until the introducer reports connected; return the last status otherwise."""
        deadline = time.time() + timeout
        status = self.connection_status()
        while status.state != "Connected" and time.time() < deadline:
            time.sleep(0.5)
            status = self.connection_status()
        # Storage (Foolscap) handshakes land a beat after the introducer; don't
        # report "0 storage" for a grid that is simply still connecting.
        settle = time.time() + STORAGE_SETTLE_SECONDS
        while status.state == "Connected" and "0 storage" in status.detail and time.time() < settle:
            time.sleep(0.5)
            status = self.connection_status()
        return status

    # -- status -------------------------------------------------------------

    def node_url(self) -> str:
        path = self.nodedir / "node.url"
        if not path.is_file():
            raise SyncError(
                "could not join this friendnet. No Tahoe client is configured at %s."
                % self.nodedir,
                "create or point LEASEGRID_TAHOE_NODEDIR at a running client; Retry.",
            )
        url = path.read_text(encoding="utf-8").strip()
        if not url:
            raise SyncError(
                "could not join this friendnet. Tahoe node.url is empty.",
                "start the Tahoe client and Retry.",
            )
        return url.rstrip("/")

    def welcome(self, timeout: float = 5.0) -> dict[str, Any]:
        url = self.node_url() + "/?t=json"
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                body = resp.read().decode("utf-8")
        except urllib.error.URLError as exc:
            raise SyncError(
                "could not join this friendnet. Tahoe client is not reachable.",
                "start Tahoe (tahoe run %s) and Retry." % self.nodedir,
            ) from exc
        try:
            data = json.loads(body)
        except json.JSONDecodeError as exc:
            raise SyncError(
                "could not join this friendnet. Tahoe returned unreadable status.",
                "check the Tahoe client logs; Retry.",
            ) from exc
        if not isinstance(data, dict):
            raise SyncError(
                "could not join this friendnet. Tahoe returned unreadable status.",
                "check the Tahoe client logs; Retry.",
            )
        return data

    def mkdir(self, timeout: float = 60.0) -> str:
        """Create an empty mutable directory on the grid; return its write cap."""
        url = self.node_url() + "/uri?t=mkdir"
        req = urllib.request.Request(url, data=b"", method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                cap = resp.read().decode("utf-8").strip()
        except urllib.error.URLError as exc:
            raise SyncError(
                "could not create a folder on the friendnet. Tahoe returned an error.",
                "check that storage nodes are connected; Retry.",
            ) from exc
        if not cap.startswith("URI:DIR2:"):
            raise SyncError(
                "could not create a folder on the friendnet. Unexpected reply from Tahoe.",
                "check the Tahoe client log; Retry.",
            )
        return cap

    def connection_status(self) -> ConnectionStatus:
        try:
            data = self.welcome()
        except SyncError as exc:
            return ConnectionStatus(state="FAIL", detail=exc.message)

        intro = data.get("introducers") or {}
        statuses = intro.get("statuses") or []
        introducer_ok = any(
            isinstance(s, str) and s.lower().startswith("connected") for s in statuses
        )
        servers = data.get("servers") or []
        nicknames = []
        connected = 0
        for srv in servers:
            if not isinstance(srv, dict):
                continue
            nick = str(srv.get("nickname") or "")
            st = str(srv.get("connection_status") or "").lower()
            if nick:
                nicknames.append(nick)
            if st.startswith("connected"):
                connected += 1
        if introducer_ok:
            state = "Connected"
            detail = "introducer up · %d storage" % connected
        elif connected:
            state = "Connecting"
            detail = "storage visible, introducer not confirmed"
        else:
            state = "Offline"
            detail = "Tahoe is up but the friendnet introducer is not connected"
        return ConnectionStatus(
            state=state,
            detail=detail,
            introducer_ok=introducer_ok,
            servers_connected=connected,
            server_nicknames=nicknames,
        )

    def has_nodedir(self) -> bool:
        return (self.nodedir / "tahoe.cfg").is_file()

    def _bring_up(self) -> ConnectionStatus:
        """Reach the node (starting it if we can), then wait for the introducer."""
        if not self.is_reachable():
            if not self.tahoe_bin:
                status = self.connection_status()
                raise SyncError(
                    "could not join this friendnet. %s" % status.detail,
                    "start the Tahoe client (tahoe run %s); Retry." % self.nodedir,
                )
            # Node is down anyway, so this is the safe moment to (re)enable paying.
            self.ensure_credit_plugin()
            self.start()
        status = self.wait_connected()
        if status.state == "FAIL":
            raise SyncError(
                "could not join this friendnet. %s" % status.detail,
                "start the Tahoe client; check network; Retry.",
            )
        if status.state == "Offline":
            raise SyncError(
                "could not join this friendnet. Introducer is unreachable.",
                "check the network path to the introducer (and that it is running); Retry.",
            )
        return status

    def join_existing(self) -> ConnectionStatus:
        """Attach to a Tahoe node already configured at self.nodedir.

        If the node exists but is not running and `tahoe` is available, Sync
        starts it and owns that process until quit.
        """
        if not self.has_nodedir():
            raise SyncError(
                "could not join this friendnet. No Tahoe node at %s." % self.nodedir,
                "paste an introducer furl, or set LEASEGRID_TAHOE_NODEDIR; Retry.",
            )
        return self._bring_up()

    def join_invite(self, invite: str, offer_storage: bool = True) -> ConnectionStatus:
        """Join from a join URL, pb:// introducer furl, or short `tahoe invite` code.

        No node yet: create a Tahoe node for that friendnet (client+storage
        unless ``offer_storage`` is false), start it, wait for the introducer.
        Node already present: reuse it (start it if needed) and confirm it
        reaches an introducer. Unpaid join and offer are this same path.
        """
        from .invite import parse_invite

        parsed = parse_invite(invite)
        furl = parsed.token
        if self.has_nodedir():
            try:
                return self._bring_up()
            except SyncError as exc:
                if "Introducer is unreachable" not in exc.message:
                    raise
                raise SyncError(
                    "could not join this friendnet. A Tahoe node already exists at %s "
                    "but is not connected to an introducer (invite %s)."
                    % (self.nodedir, redact_furl(furl)),
                    "if that node belongs to another grid, set LEASEGRID_TAHOE_NODEDIR "
                    "to a new path; otherwise check the introducer is up; Retry.",
                ) from exc
        self.create_node(furl, shares=parsed.shares, offer_storage=offer_storage)
        return self._bring_up()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


class MagicFolderCtl:
    def __init__(
        self,
        config_dir: Optional[Path] = None,
        nodedir: Optional[Path] = None,
        mf_bin: Optional[str] = None,
        listen_port: int = DEFAULT_MF_PORT,
    ) -> None:
        home = default_home()
        self.config_dir = Path(config_dir) if config_dir else home / "magic-folder"
        self.nodedir = Path(nodedir) if nodedir else default_nodedir()
        self.mf_bin = mf_bin or which_bin("magic-folder", "LEASEGRID_MAGIC_FOLDER_BIN")
        self.listen_port = int(os.environ.get("LEASEGRID_MF_PORT") or listen_port)
        self._proc: Optional[subprocess.Popen] = None
        self.log_path = default_home() / "logs" / "magic-folder.log"

    def require_bin(self) -> str:
        if not self.mf_bin:
            raise SyncError(
                "folder not added. The Magic Folder daemon is not installed.",
                "install magic-folder on PATH (see docs/ops/u1-dogfood.md) and Retry.",
            )
        return self.mf_bin

    def _run_cli(self, args: list[str], timeout: float = 60.0) -> subprocess.CompletedProcess:
        bin_ = self.require_bin()
        cmd = [bin_, "--config", str(self.config_dir), *args]
        try:
            return subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except FileNotFoundError as exc:
            raise SyncError(
                "folder not added. magic-folder executable is missing.",
                "install magic-folder on PATH; Retry.",
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise SyncError(
                "folder not added. Magic Folder command timed out.",
                "check the daemon log at %s; Retry." % self.log_path,
            ) from exc

    def ensure_init(self) -> None:
        self.require_bin()
        if (self.config_dir / "global.sqlite").is_file() or (
            self.config_dir / "api_token"
        ).is_file():
            return
        if not (self.nodedir / "tahoe.cfg").is_file():
            raise SyncError(
                "folder not added. Tahoe node directory is missing.",
                "join the friendnet first, then Add folder.",
            )
        # magic-folder init requires the config directory to not exist yet.
        if self.config_dir.is_dir():
            try:
                next(self.config_dir.iterdir())
            except StopIteration:
                self.config_dir.rmdir()
            else:
                raise SyncError(
                    "folder not added. Magic Folder config dir exists but is not initialized.",
                    "remove %s if it is leftover, then Retry." % self.config_dir,
                )
        self.config_dir.parent.mkdir(parents=True, exist_ok=True)
        listen = "tcp:%d:interface=127.0.0.1" % self.listen_port
        proc = subprocess.run(
            [
                self.require_bin(),
                "--config",
                str(self.config_dir),
                "init",
                "--listen-endpoint",
                listen,
                "--node-directory",
                str(self.nodedir),
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "init failed").strip()
            raise SyncError(
                "folder not added. Could not initialize Magic Folder: %s" % err.split("\n")[0],
                "fix the Magic Folder config path; Restart Sync.",
            )

    def is_running(self) -> bool:
        ep = self.config_dir / "api_client_endpoint"
        if not ep.is_file():
            return False
        try:
            url = endpoint_to_url(_read_text(ep))
        except SyncError:
            return False
        try:
            self._http_get("/v1/magic-folder", base=url, timeout=1.5)
            return True
        except SyncError:
            return False

    def ensure_running(self) -> None:
        self.ensure_init()
        if self.is_running():
            return
        if not _port_free(self.listen_port) and not self.is_running():
            raise SyncError(
                "folder not added. Port %d is busy and Magic Folder is not answering."
                % self.listen_port,
                "stop the other process or set LEASEGRID_MF_PORT; Restart Sync.",
            )
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        log_f = open(self.log_path, "ab")
        try:
            self._proc = popen_hidden(
                [self.require_bin(), "--config", str(self.config_dir), "run"],
                log_f,
            )
        except OSError as exc:
            log_f.close()
            raise SyncError(
                "folder not added. Could not start Magic Folder: %s" % exc,
                "install magic-folder; Restart Sync.",
            ) from exc
        deadline = time.time() + 20
        while time.time() < deadline:
            if self._proc.poll() is not None:
                tail = _tail(self.log_path)
                raise SyncError(
                    "folder not added. Magic Folder daemon exited.",
                    "see %s (%s); Restart Sync." % (self.log_path, tail),
                )
            if self.is_running():
                return
            time.sleep(0.2)
        raise SyncError(
            "folder not added. Magic Folder daemon did not become ready.",
            "see %s; Restart Sync." % self.log_path,
        )

    def stop(self) -> None:
        proc = self._proc
        if proc is None:
            return
        try:
            if proc.stdin:
                proc.stdin.close()
        except OSError:
            pass
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except OSError:
                pass
        self._proc = None

    def _auth_headers(self) -> dict[str, str]:
        token_path = self.config_dir / "api_token"
        if not token_path.is_file():
            raise SyncError(
                "Magic Folder API token is missing.",
                "Restart Sync so the daemon can rewrite its config.",
            )
        token = token_path.read_bytes().decode("ascii", "replace").strip()
        return {"Authorization": "Bearer %s" % token}

    def _base_url(self) -> str:
        ep = self.config_dir / "api_client_endpoint"
        if not ep.is_file():
            raise SyncError(
                "Magic Folder daemon is not running.",
                "Restart Sync.",
            )
        return endpoint_to_url(_read_text(ep))

    def _http_get(self, path: str, base: Optional[str] = None, timeout: float = 10.0) -> Any:
        url = (base or self._base_url()) + path
        req = urllib.request.Request(url, headers=self._auth_headers())
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            try:
                detail = exc.read().decode("utf-8", "replace")[:300]
            except Exception:
                detail = str(exc.reason)
            raise SyncError(
                "Magic Folder API error (%s)." % exc.code,
                detail or "Retry.",
            ) from exc
        except urllib.error.URLError as exc:
            raise SyncError(
                "Magic Folder daemon is not reachable.",
                "Restart Sync.",
            ) from exc
        if not body:
            return {}
        try:
            return json.loads(body)
        except json.JSONDecodeError as exc:
            raise SyncError(
                "Magic Folder returned unreadable JSON.",
                "see %s; Restart Sync." % self.log_path,
            ) from exc

    def _http_post(self, path: str, timeout: float = 30.0, body: Optional[dict] = None) -> Any:
        url = self._base_url() + path
        headers = self._auth_headers()
        data = b""
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, method="POST", headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            try:
                detail = exc.read().decode("utf-8", "replace")[:300]
            except Exception:
                detail = str(exc.reason)
            raise SyncError(
                "Magic Folder API error (%s)." % exc.code,
                detail or "Retry.",
            ) from exc
        except urllib.error.URLError as exc:
            raise SyncError(
                "Magic Folder daemon is not reachable.",
                "Restart Sync.",
            ) from exc
        if not body:
            return {}
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return {"raw": body}

    def list_folders(self) -> list[FolderRow]:
        self.ensure_running()
        data = self._http_get("/v1/magic-folder")
        if not isinstance(data, dict):
            return []
        rows = []
        for name, details in data.items():
            if not isinstance(details, dict):
                details = {}
            path = str(details.get("magic_path") or "")
            rows.append(
                FolderRow(
                    name=str(name),
                    path=path,
                    status="Idle",
                    detail="poll %ss" % details.get("poll_interval", "?"),
                )
            )
        for row in rows:
            row.status, row.detail = self.folder_status(row.name)
        return rows

    def folder_status(self, name: str) -> tuple[str, str]:
        try:
            files = self._http_get(
                "/v1/magic-folder/%s/file-status" % quote(name, safe="")
            )
            recent = self._http_get(
                "/v1/magic-folder/%s/recent-changes?number=5" % quote(name, safe="")
            )
        except SyncError as exc:
            return "FAIL", exc.message
        nfiles = len(files) if isinstance(files, list) else 0
        last = ""
        if isinstance(recent, list) and recent:
            item = recent[0]
            if isinstance(item, dict):
                last = str(item.get("relpath") or "")
                if item.get("conflicted"):
                    return "Conflict", last
        if nfiles == 0:
            return "Idle", "empty"
        if last:
            return "Up to date", "%d files · last %s" % (nfiles, last)
        return "Up to date", "%d files" % nfiles

    def add_folder(self, local_path: str, name: Optional[str] = None, author: Optional[str] = None) -> str:
        path = Path(local_path).expanduser()
        if not path.exists() or not path.is_dir():
            raise SyncError(
                "folder not added. Path is not a readable directory.",
                "pick an existing local folder; Retry.",
            )
        if not os.access(path, os.R_OK | os.W_OK):
            raise SyncError(
                "folder not added. Path is not readable/writable.",
                "fix permissions on %s; Retry." % path,
            )
        folder_name = name or path.name or "folder"
        folder_name = "".join(ch if ch.isalnum() or ch in "-_." else "-" for ch in folder_name)
        if not folder_name:
            raise SyncError(
                "folder not added. Folder name is empty.",
                "choose a different directory name; Retry.",
            )
        author = author or os.environ.get("USER") or os.environ.get("LOGNAME") or "leasegrid"
        self.ensure_running()
        existing = self._http_get("/v1/magic-folder")
        if isinstance(existing, dict) and folder_name in existing:
            return folder_name
        proc = self._run_cli(
            [
                "add",
                "--author",
                author,
                "--name",
                folder_name,
                "--poll-interval",
                "5",
                "--scan-interval",
                "5",
                str(path),
            ],
            timeout=120,
        )
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "add failed").strip().split("\n")[0]
            raise SyncError(
                "folder not added. %s" % err,
                "fix the path; Restart Sync; Retry Add folder.",
            )
        return folder_name

    def scan_local(self, name: str) -> None:
        path = "/v1/magic-folder/%s/scan-local" % quote(name, safe="")
        try:
            self._http_post(path, timeout=60)
            return
        except SyncError:
            pass
        try:
            self._http_get(path, timeout=60)
        except SyncError:
            pass

    def file_status(self, name: str) -> list[dict[str, Any]]:
        data = self._http_get("/v1/magic-folder/%s/file-status" % quote(name, safe=""))
        return data if isinstance(data, list) else []

    def recent_changes(self, name: str, number: int = 10) -> list[dict[str, Any]]:
        data = self._http_get(
            "/v1/magic-folder/%s/recent-changes?number=%d" % (quote(name, safe=""), number)
        )
        return data if isinstance(data, list) else []

    def participants(self, name: str) -> dict[str, Any]:
        data = self._http_get("/v1/magic-folder/%s/participants" % quote(name, safe=""))
        return data if isinstance(data, dict) else {}

    def add_participant(self, name: str, author_name: str, personal_dmd_readcap: str) -> None:
        """Register another device's personal DMD in this folder's collective."""
        self._http_post(
            "/v1/magic-folder/%s/participants" % quote(name, safe=""),
            timeout=60,
            body={"author": {"name": author_name}, "personal_dmd": personal_dmd_readcap},
        )

    def snapshots(self, name: Optional[str] = None) -> dict[str, Any]:
        data = self._http_get("/v1/snapshot")
        if not isinstance(data, dict):
            return {}
        if name:
            item = data.get(name) or {}
            return item if isinstance(item, dict) else {}
        return data


def _port_free(port: int, host: str = "127.0.0.1") -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.settimeout(0.3)
        return sock.connect_ex((host, port)) != 0
    finally:
        sock.close()


def _tail(path: Path, n: int = 180) -> str:
    try:
        data = path.read_bytes()[-n:]
        return data.decode("utf-8", "replace").replace("\n", " ").strip()
    except OSError:
        return ""


def write_probe_file(folder: Path, name: str = "u1-hello.txt") -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_text("leasegrid-u1 %s\n" % time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), encoding="utf-8")
    return path


def wait_for_file_status(
    ctl: MagicFolderCtl,
    folder_name: str,
    relpath: str,
    timeout: float = 90.0,
) -> dict[str, Any]:
    deadline = time.time() + timeout
    last: list[dict[str, Any]] = []
    while time.time() < deadline:
        try:
            ctl.scan_local(folder_name)
        except SyncError:
            pass
        try:
            last = ctl.file_status(folder_name)
        except SyncError:
            last = []
        for item in last:
            if isinstance(item, dict) and str(item.get("relpath") or "") == relpath:
                return item
        try:
            recent = ctl.recent_changes(folder_name)
        except SyncError:
            recent = []
        for item in recent:
            if isinstance(item, dict) and str(item.get("relpath") or "") == relpath:
                return item
        time.sleep(1.0)
    raise SyncError(
        "sync paused for %r. Local file %s did not appear in Magic Folder status."
        % (folder_name, relpath),
        "wait/retry; confirm Tahoe is connected; see %s." % ctl.log_path,
    )
