"""Minimal JSON HTTP server (stdlib). Never logs R, t, or MAC values."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable
from urllib.parse import urlparse

HandlerFn = Callable[[dict | None, dict], tuple[int, dict]]


class QuietJSONHandler(BaseHTTPRequestHandler):
    routes: dict[tuple[str, str], HandlerFn] = {}
    # Keys the issuer must never accept on settlement (0b.5).
    forbidden_r_keys = frozenset(
        {
            "r",
            "R",
            "mac",
            "MAC",
            "request_binding",
            "request-binding",
            "storage_index",
            "storage-index",
            "W",
            "w",
        }
    )

    def log_message(self, fmt: str, *args) -> None:
        # Path + status only. No query, no body.
        sys_stderr_write = super().log_message
        try:
            path = urlparse(self.path).path
        except Exception:
            path = "/"
        sys_stderr_write("%s %s", self.command, path)

    def _read_json(self) -> dict | None:
        length = int(self.headers.get("Content-Length") or "0")
        if length <= 0:
            return None
        raw = self.rfile.read(length)
        if not raw:
            return None
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            raise ValueError("invalid JSON: %s" % e) from e
        if not isinstance(data, dict):
            raise ValueError("JSON body must be an object")
        return data

    def _send(self, code: int, body: dict) -> None:
        payload = json.dumps(body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _dispatch(self) -> None:
        path = urlparse(self.path).path
        fn = self.routes.get((self.command, path))
        if fn is None:
            self._send(404, {"error": "not found"})
            return
        try:
            body = self._read_json() if self.command in ("POST", "PUT") else None
        except ValueError as e:
            self._send(400, {"error": str(e)})
            return
        try:
            code, out = fn(body, dict(self.headers.items()))
        except Exception as e:
            self._send(500, {"error": "internal", "class": type(e).__name__})
            return
        self._send(code, out)

    def do_GET(self) -> None:
        self._dispatch()

    def do_POST(self) -> None:
        self._dispatch()

    def do_PUT(self) -> None:
        self._dispatch()


def make_handler(routes: dict[tuple[str, str], HandlerFn], *, name: str) -> type[QuietJSONHandler]:
    return type(
        name,
        (QuietJSONHandler,),
        {"routes": routes, "server_version": "leasegrid-zkap-lab/0.1"},
    )


def serve_background(host: str, port: int, handler_cls: type[BaseHTTPRequestHandler]) -> tuple[ThreadingHTTPServer, threading.Thread]:
    httpd = ThreadingHTTPServer((host, port), handler_cls)
    t = threading.Thread(target=httpd.serve_forever, name="leasegrid-http", daemon=True)
    t.start()
    return httpd, t


def parse_listen(spec: str) -> tuple[str, int]:
    spec = spec.strip()
    if spec.startswith("tcp:"):
        # tcp:8701:interface=127.0.0.1  or tcp:127.0.0.1:8701
        rest = spec[4:]
        parts = rest.split(":")
        interface = "127.0.0.1"
        port_s = parts[0]
        for p in parts[1:]:
            if p.startswith("interface="):
                interface = p.split("=", 1)[1]
            elif p.isdigit():
                port_s = p
            else:
                interface = p
        return interface, int(port_s)
    if ":" in spec:
        host, port_s = spec.rsplit(":", 1)
        return host or "127.0.0.1", int(port_s)
    return "127.0.0.1", int(spec)
