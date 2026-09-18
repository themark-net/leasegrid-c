"""Storage-node spend HTTP + lab allocate/add_lease/renew."""

from __future__ import annotations

from http.server import ThreadingHTTPServer

from .errors import SpendError, ZKAPRequired
from .gate import LeaseGate, parse_r_input, parse_storage_index
from .httpjson import make_handler, parse_listen, serve_background


def build_storage_handler(gate: LeaseGate):
    def info(body, headers):
        return 200, {
            "nodeid": gate.nodeid,
            "issuer-pubkey-id": gate.issuer_pubkey_id,
            "spent": len(gate.spent),
            "domain": gate.info["domain"],
            "denomination": gate.info["denomination"],
            "token-epoch": gate.info["token-epoch"],
            "invariant": "settlement sends spent t only; R stays on the node",
        }

    def spend(body, headers):
        if not body:
            return 400, {"error": "JSON object required"}
        t = body.get("t")
        mac = body.get("mac")
        if not t or not mac:
            return 400, {"error": "t and mac required"}
        try:
            r = parse_r_input(body)
            out = gate.spend(t, r, mac)
        except SpendError as e:
            return 403, {"error": str(e)}
        return 200, out

    def _si(body):
        if not body or "storage_index" not in body:
            raise SpendError("storage_index required")
        return parse_storage_index(body["storage_index"])

    def lab_allocate(body, headers):
        try:
            si = _si(body)
            sharenums = body.get("sharenums") or [0]
            allocated_size = int(body.get("allocated_size") or 64)
            out = gate.lab_allocate(si, sharenums, allocated_size)
        except ZKAPRequired as e:
            return 403, {"error": str(e), "anonymous": True}
        except SpendError as e:
            return 400, {"error": str(e)}
        return 200, out

    def lab_add_lease(body, headers):
        try:
            out = gate.lab_add_lease(_si(body))
        except ZKAPRequired as e:
            return 403, {"error": str(e), "anonymous": True}
        except SpendError as e:
            return 400, {"error": str(e)}
        return 200, out

    def lab_renew(body, headers):
        try:
            out = gate.lab_renew(_si(body))
        except ZKAPRequired as e:
            return 403, {"error": str(e), "anonymous": True}
        except SpendError as e:
            return 400, {"error": str(e)}
        return 200, out

    def settlement_bundle(body, headers):
        # Storage → issuer payload. t only.
        return 200, {
            "spent-preimages": gate.settlement_preimages(),
            "nodeid": gate.nodeid,
        }

    routes = {
        ("GET", "/v0/info"): info,
        ("GET", "/health"): lambda b, h: (200, {"ok": True, "nodeid": gate.nodeid}),
        ("POST", "/v0/spend"): spend,
        ("POST", "/v0/lab/allocate"): lab_allocate,
        ("POST", "/v0/lab/add_lease"): lab_add_lease,
        ("POST", "/v0/lab/renew"): lab_renew,
        ("GET", "/v0/settlement-bundle"): settlement_bundle,
    }
    return make_handler(routes, name="StorageHandler")


def start_storage_http(gate: LeaseGate, listen: str) -> tuple[str, ThreadingHTTPServer]:
    host, port = parse_listen(listen)
    handler = build_storage_handler(gate)
    httpd, _ = serve_background(host, port, handler)
    url = "http://%s:%d" % (host, httpd.server_address[1])
    return url, httpd
