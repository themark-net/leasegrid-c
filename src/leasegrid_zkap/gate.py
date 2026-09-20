"""Storage-side spend + lease gate (docs/02-objects.md §2.3–2.7)."""

from __future__ import annotations

import binascii
import time
from base64 import b64decode, b64encode
from typing import Optional

from challenge_bypass_ristretto import SigningKey

from .constants import DOMAIN, TOKEN_EPOCH_V0
from .crypto import InvalidPass, issuer_info, verify_mac
from .errors import SpendError, ZKAPRequired
from .r_bind import RError, decode_r
from .spentset import ReplayError, SpentRecord, SpentSet


def _b64s(raw: bytes) -> str:
    return b64encode(raw).decode("ascii")


class LeaseGate:
    def __init__(
        self,
        signing_key: SigningKey,
        nodeid: str,
        spent: SpentSet | None = None,
        backend=None,
    ):
        self.signing_key = signing_key
        self.nodeid = nodeid
        self.spent = spent or SpentSet()
        self.backend = backend
        self.info = issuer_info(signing_key)
        self.issuer_pubkey_id = self.info["issuer-pubkey-id"]
        self._accepted: dict[int, dict] = {
            TOKEN_EPOCH_V0: {"key": signing_key, "issuer-pubkey-id": self.issuer_pubkey_id}
        }

    def spend(self, t: str, r: bytes, mac: str) -> dict:
        """
        Verify (t, R, MAC_K(R)), enforce spent-set rules, remember the lease.
        Returns a public receipt (no extra secrets).
        """
        try:
            fields = decode_r(r)
        except RError as e:
            raise SpendError("bad R: %s" % e) from e
        if fields["domain"] != DOMAIN:
            raise SpendError("R.domain is not %s" % DOMAIN)
        if fields["nodeid"] != self.nodeid:
            raise SpendError("R.nodeid does not match this storage node")
        acc = self._accepted.get(int(fields["token_epoch"]))
        if acc is None:
            raise SpendError("epoch %s is not accepted" % fields["token_epoch"])
        if fields["issuer_pubkey_id"] != acc["issuer-pubkey-id"]:
            raise SpendError("R.issuer_pubkey_id does not match this issuer key")
        try:
            verify_mac(acc["key"], t, r, mac)
        except InvalidPass as e:
            raise SpendError(str(e)) from e
        rec = SpentRecord(
            t=t,
            r_b64=_b64s(r),
            storage_index_hex=fields["storage_index"].hex(),
            lease_seconds=fields["lease_seconds"],
            share_bytes=fields["share_bytes"],
            token_epoch=fields["token_epoch"],
            issuer_pubkey_id=fields["issuer_pubkey_id"],
            nodeid=fields["nodeid"],
        )
        try:
            stored = self.spent.remember(rec)
        except ReplayError as e:
            raise SpendError(str(e)) from e
        return {
            "ok": True,
            "idempotent": stored is not rec and stored.r_b64 == rec.r_b64,
            "storage_index": rec.storage_index_hex,
            "issuer_pubkey_id": rec.issuer_pubkey_id,
        }

    def pull_keys(
        self,
        keys_doc: dict,
        signing_keys: Optional[dict[int, SigningKey]] = None,
        now: Optional[float] = None,
    ) -> dict:
        """Node key pull: accept epochs whose accept_until has not passed."""
        now = time.time() if now is None else now
        signing_keys = signing_keys or {}
        accepted: dict[int, dict] = {}
        for e in keys_doc.get("epochs") or []:
            until = e.get("accept_until")
            if until is not None and float(until) <= now:
                continue
            eid = int(e["epoch"])
            key = signing_keys.get(eid)
            if key is None and eid == TOKEN_EPOCH_V0:
                key = self.signing_key
            if key is None:
                continue
            pk = e.get("issuer-pubkey-id") or issuer_info(key)["issuer-pubkey-id"]
            accepted[eid] = {"key": key, "issuer-pubkey-id": pk}
        self._accepted = accepted
        return {"accepted": sorted(accepted)}

    def _find_grant(self, storage_index: bytes, op: str) -> SpentRecord:
        want = storage_index.hex()
        for t in self.spent.preimages():
            rec = self.spent.lookup(t)
            if rec and rec.storage_index_hex == want:
                return rec
        raise ZKAPRequired(
            "leasegrid-zkap-v0: %s refused without a valid ZKAP for storage_index=%s"
            % (op, want)
        )

    def require_allocate(self, storage_index: bytes, allocated_size: int, sharenums) -> SpentRecord:
        rec = self._find_grant(storage_index, "allocate")
        n = len(list(sharenums)) if sharenums is not None else 1
        need = int(allocated_size) * max(n, 1)
        # v0: 1 token = 1 GiB-share × 30 days. Tiny lab allocates fit in 1 GiB.
        if need > rec.share_bytes:
            raise ZKAPRequired(
                "leasegrid-zkap-v0: allocate size %s exceeds R.share_bytes %s"
                % (need, rec.share_bytes)
            )
        return rec

    def require_add_lease(self, storage_index: bytes) -> SpentRecord:
        return self._find_grant(storage_index, "add_lease")

    def require_renew(self, storage_index: bytes) -> SpentRecord:
        return self._find_grant(storage_index, "renew")

    def settlement_preimages(self) -> list[str]:
        """Spent t values only. Never includes R."""
        return self.spent.preimages()

    def lab_allocate(self, storage_index: bytes, sharenums, allocated_size: int) -> dict:
        self.require_allocate(storage_index, allocated_size, sharenums)
        if self.backend is None:
            return {"already-have": [], "allocated": list(sharenums), "backend": "memory"}
        renew = b"\x11" * 32
        cancel = b"\x22" * 32
        already, writers = self.backend.allocate_buckets(
            storage_index,
            renew,
            cancel,
            set(sharenums),
            allocated_size,
        )
        # Close writers so shares exist for add_lease/renew in lab checks.
        for bw in list(getattr(writers, "values", lambda: [])()):
            try:
                bw.close()
            except Exception:
                pass
        already_nums = list(already) if not isinstance(already, dict) else list(already.keys())
        return {
            "already-have": [int(x) for x in already_nums],
            "allocated": [int(x) for x in writers],
            "backend": "tahoe",
        }

    def lab_add_lease(self, storage_index: bytes) -> dict:
        self.require_add_lease(storage_index)
        if self.backend is not None:
            self.backend.add_lease(storage_index, b"\x11" * 32, b"\x22" * 32)
        return {"ok": True}

    def lab_renew(self, storage_index: bytes) -> dict:
        self.require_renew(storage_index)
        if self.backend is not None:
            self.backend.renew_lease(storage_index, b"\x11" * 32)
        return {"ok": True}


def install_on_storage_server(storage_server, gate: LeaseGate) -> None:
    """
    Wrap Tahoe StorageServer allocate/add_lease/renew (and mutable writev)
    in place so GBS HTTP and Foolscap both refuse unpaid leases.

    Tahoe 1.20 HTTP GBS has no plugin extra-args; wrapping the singleton
    StorageServer is the hook that actually gates the live protocol.
    """
    orig_alloc = storage_server.allocate_buckets
    orig_add = storage_server.add_lease
    orig_renew = storage_server.renew_lease

    def allocate_buckets(storage_index, renew_secret, cancel_secret, sharenums, allocated_size, *rest, **kw):
        gate.require_allocate(storage_index, allocated_size, sharenums)
        return orig_alloc(
            storage_index, renew_secret, cancel_secret, sharenums, allocated_size, *rest, **kw
        )

    def add_lease(storage_index, renew_secret, cancel_secret, *rest, **kw):
        gate.require_add_lease(storage_index)
        return orig_add(storage_index, renew_secret, cancel_secret, *rest, **kw)

    def renew_lease(storage_index, renew_secret, *rest, **kw):
        gate.require_renew(storage_index)
        return orig_renew(storage_index, renew_secret, *rest, **kw)

    storage_server.allocate_buckets = allocate_buckets
    storage_server.add_lease = add_lease
    storage_server.renew_lease = renew_lease
    if hasattr(storage_server, "slot_testv_and_readv_and_writev"):
        orig_writev = storage_server.slot_testv_and_readv_and_writev

        def slot_testv_and_readv_and_writev(storage_index, secrets, test_and_write_vectors, read_vector, *rest, **kw):
            # Mutable create/write is an allocate-equivalent for quota.
            allocated = 0
            try:
                for vec in (test_and_write_vectors or {}).values():
                    data = getattr(vec, "data", None) or (vec.get("data") if isinstance(vec, dict) else None)
                    if data:
                        allocated += sum(len(x) for x in data if x)
            except Exception:
                allocated = 0
            gate.require_allocate(storage_index, allocated or 1, list((test_and_write_vectors or {})))
            return orig_writev(storage_index, secrets, test_and_write_vectors, read_vector, *rest, **kw)

        storage_server.slot_testv_and_readv_and_writev = slot_testv_and_readv_and_writev
    gate.backend = storage_server


def parse_storage_index(value: str | bytes) -> bytes:
    if isinstance(value, bytes):
        return value
    value = value.strip()
    try:
        raw = binascii.unhexlify(value)
    except binascii.Error as e:
        raise SpendError("storage_index must be hex") from e
    if len(raw) != 16:
        raise SpendError("storage_index must be 16 bytes (got %d)" % len(raw))
    return raw


def parse_r_input(body: dict) -> bytes:
    if "R" in body:
        try:
            return b64decode(body["R"])
        except Exception as e:
            raise SpendError("R must be standard base64") from e
    raise SpendError("missing R")
