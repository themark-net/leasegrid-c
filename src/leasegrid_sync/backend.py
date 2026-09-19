"""Tahoe + Magic Folder control plane for Leasegrid Sync (no Qt, no WUI)."""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
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


def default_home() -> Path:
    override = os.environ.get("LEASEGRID_SYNC_HOME")
    if override:
        return Path(override).expanduser()
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / APP_ID
    return Path.home() / ".local" / "share" / APP_ID


def default_nodedir() -> Path:
    env = os.environ.get("LEASEGRID_TAHOE_NODEDIR")
    if env:
        return Path(env).expanduser()
    return DEFAULT_TAHOE_NODEDIR


def which_bin(name: str, env_key: str) -> Optional[str]:
    env = os.environ.get(env_key)
    if env:
        p = Path(env).expanduser()
        if p.is_file() and os.access(p, os.X_OK):
            return str(p)
    found = shutil.which(name)
    return found


def redact_furl(value: str) -> str:
    text = value.strip()
    if text.startswith("pb://") and len(text) > 12:
        return text[:8] + "…" + text[-6:]
    return text


def validate_introducer_furl(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        raise SyncError(
            "could not join this friendnet. Invite is empty.",
            "paste an introducer furl (starts with pb://) or use the existing Tahoe node.",
        )
    low = text.lower()
    if low.startswith("http://") or low.startswith("https://"):
        raise SyncError(
            "could not join this friendnet. That looks like a web URL.",
            "Leasegrid Sync does not use the Tahoe web UI. Paste a pb:// introducer furl.",
        )
    if not text.startswith("pb://"):
        raise SyncError(
            "could not join this friendnet. Invite code invalid.",
            "ask your inviter for a fresh introducer furl (starts with pb://); Retry.",
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
    def __init__(self, nodedir: Optional[Path] = None, tahoe_bin: Optional[str] = None) -> None:
        self.nodedir = Path(nodedir) if nodedir else default_nodedir()
        self.tahoe_bin = tahoe_bin or which_bin("tahoe", "LEASEGRID_TAHOE_BIN")

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

    def join_existing(self) -> ConnectionStatus:
        if not self.has_nodedir():
            raise SyncError(
                "could not join this friendnet. No Tahoe node at %s." % self.nodedir,
                "paste an introducer furl, or set LEASEGRID_TAHOE_NODEDIR; Retry.",
            )
        status = self.connection_status()
        if status.state == "FAIL":
            raise SyncError(
                "could not join this friendnet. %s" % status.detail,
                "start the Tahoe client; check network; Retry.",
            )
        if status.state == "Offline":
            raise SyncError(
                "could not join this friendnet. Introducer is unreachable.",
                "check LAN to the introducer; Retry.",
            )
        return status

    def join_invite(self, invite: str) -> ConnectionStatus:
        furl = validate_introducer_furl(invite)
        if self.has_nodedir():
            status = self.connection_status()
            if status.state in ("Connected", "Connecting"):
                return status
            raise SyncError(
                "could not join this friendnet. Tahoe is running but not connected "
                "to this invite (%s)." % redact_furl(furl),
                "use the existing node if this is the lab friendnet, or restart Tahoe "
                "after an operator drops the introducer; Retry.",
            )
        raise SyncError(
            "could not join this friendnet. No local Tahoe node to attach this invite to.",
            "on nimo, use the existing ~/.tahoe client (Use existing node). "
            "Creating a fresh client is lab-operator work.",
        )


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
            self._proc = subprocess.Popen(
                [self.require_bin(), "--config", str(self.config_dir), "run"],
                stdin=subprocess.PIPE,
                stdout=log_f,
                stderr=subprocess.STDOUT,
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

    def _http_post(self, path: str, timeout: float = 30.0) -> Any:
        url = self._base_url() + path
        req = urllib.request.Request(
            url,
            data=b"",
            method="POST",
            headers=self._auth_headers(),
        )
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
