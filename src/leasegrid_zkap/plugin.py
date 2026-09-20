"""Tahoe 1.20 IFoolscapStoragePlugin.

Server side: wrap the anonymous StorageServer so allocate/add_lease/renew/writev
refuse unpaid leases, run the spend HTTP next to it, and announce where to pay.

Client side: an IStorageServer that pays (one token per node x storage index)
*before* forwarding each write to the node, reads for free.
"""

from __future__ import annotations

import os

from twisted.internet.defer import fail, succeed
from twisted.web.static import Data
from zope.interface import implementer

from allmydata.client import AnnounceableStorageServer
from allmydata.interfaces import IFoolscapStoragePlugin, IStorageServer
from allmydata.storage.server import FoolscapStorageServer
from allmydata.storage_client import _StorageServer

from .constants import DEFAULT_WALLET, PLUGIN_NAME
from .crypto import load_signing_key
from .gate import LeaseGate, install_on_storage_server
from .spender import NoCredit, WalletSpender
from .spentset import SpentSet
from .storage_http import start_storage_http

CLIENT_SECTION = "storageclient.plugins." + PLUGIN_NAME


def _cfg(configuration, key, default=None):
    if hasattr(configuration, "get"):
        return configuration.get(key, default)
    return default


def _node_cfg(node_config, key, default=None):
    """Read [storageclient.plugins.<name>] from a Tahoe _Config (or a plain dict in tests)."""
    if node_config is None:
        return default
    if hasattr(node_config, "get_config"):
        try:
            value = node_config.get_config(CLIENT_SECTION, key, default)
        except Exception:
            return default
        return value if value not in (None, "") else default
    return _cfg(node_config, key, default)


@implementer(IFoolscapStoragePlugin)
class LeasegridZKAPPlugin:
    name = PLUGIN_NAME

    def get_storage_server(self, configuration, get_anonymous_storage_server):
        key_file = _cfg(configuration, "issuer-signing-key-file") or _cfg(
            configuration, "issuer_signing_key_file"
        )
        if not key_file:
            raise ValueError(
                "storageserver.plugins.%s issuer-signing-key-file is required"
                % PLUGIN_NAME
            )
        nodeid = _cfg(configuration, "nodeid") or _cfg(configuration, "node-id")
        spent_path = _cfg(configuration, "spent-set-path") or _cfg(
            configuration, "spent_set_path"
        )
        listen = _cfg(configuration, "spend-listen") or _cfg(
            configuration, "spend_listen"
        )
        spend_url = _cfg(configuration, "spend-url") or _cfg(configuration, "spend_url")

        ss = get_anonymous_storage_server()
        if not nodeid:
            # Tahoe nodeid is 20 raw bytes; my_nodeid file is base32. Prefer config.
            raw = getattr(ss, "my_nodeid", b"")
            try:
                from allmydata.util import base32

                nodeid = base32.b2a(raw).decode("ascii") if raw else "unknown"
            except Exception:
                nodeid = raw.hex() if raw else "unknown"

        key = load_signing_key(key_file)
        gate = LeaseGate(key, nodeid=nodeid, spent=SpentSet(spent_path) if spent_path else SpentSet())
        issuer_url = _cfg(configuration, "issuer-url") or _cfg(configuration, "issuer_url")
        if issuer_url:
            try:
                from .client import http_json

                gate.pull_keys(http_json(str(issuer_url).rstrip("/") + "/v0/keys"), signing_keys={0: key})
            except Exception as exc:
                print("leasegrid-zkap: key pull from %s failed: %s" % (issuer_url, exc))
        install_on_storage_server(ss, gate)
        if listen:
            url, _httpd = start_storage_http(gate, listen)
            spend_url = spend_url or url

        announcement = {
            "issuer-pubkey-id": gate.issuer_pubkey_id,
            "domain": "leasegrid-v0",
            "denomination": gate.info["denomination"],
            "nodeid": nodeid,
        }
        if spend_url:
            announcement["spend-url"] = spend_url
        return succeed(
            AnnounceableStorageServer(
                announcement,
                FoolscapStorageServer(ss),
            )
        )

    def get_storage_client(self, configuration, announcement, get_rref):
        wallet_path = (
            _node_cfg(configuration, "wallet-path")
            or os.environ.get("LEASEGRID_ZKAP_WALLET")
            or DEFAULT_WALLET
        )
        spender = WalletSpender.shared(
            wallet_path,
            grants_path=_node_cfg(configuration, "grants-path"),
            recent_path=_node_cfg(configuration, "recent-path"),
        )
        return ZKAPStorageClient(
            get_rref,
            spender=spender,
            spend_url=_cfg(announcement, "spend-url"),
            nodeid=_cfg(announcement, "nodeid"),
            issuer_pubkey_id=_cfg(announcement, "issuer-pubkey-id"),
        )

    def get_client_resource(self, configuration):
        body = (
            b'{"plugin":"leasegrid-zkap-v0","note":"spend HTTP is on the storage node"}'
        )
        return Data(body, "application/json")


@implementer(IStorageServer)
class ZKAPStorageClient:
    """Pay-then-forward wrapper around Tahoe's Foolscap storage client."""

    def __init__(self, get_rref, spender: WalletSpender, spend_url, nodeid, issuer_pubkey_id):
        self.get_rref = get_rref
        self._inner = _StorageServer(get_rref=get_rref)
        self.spender = spender
        self.spend_url = spend_url
        self.nodeid = nodeid
        self.issuer_pubkey_id = issuer_pubkey_id

    # -- paying --------------------------------------------------------------

    def _pay(self, storage_index, need_bytes):
        if not (self.spend_url and self.nodeid and self.issuer_pubkey_id):
            return fail(
                NoCredit(
                    "leasegrid-zkap-v0: node %s announced no spend-url; cannot pay for writes"
                    % (self.nodeid or "?")
                )
            )
        return self.spender.ensure_grant(
            self.spend_url, self.nodeid, self.issuer_pubkey_id, storage_index, int(need_bytes)
        )

    # -- IStorageServer (writes pay first) -----------------------------------

    def get_version(self):
        return self._inner.get_version()

    def allocate_buckets(self, storage_index, renew_secret, cancel_secret, sharenums,
                         allocated_size, canary):
        n = max(len(list(sharenums)), 1)
        d = self._pay(storage_index, int(allocated_size) * n)
        d.addCallback(
            lambda _grant: self._inner.allocate_buckets(
                storage_index, renew_secret, cancel_secret, sharenums, allocated_size, canary
            )
        )
        return d

    def add_lease(self, storage_index, renew_secret, cancel_secret):
        d = self._pay(storage_index, 0)
        d.addCallback(lambda _g: self._inner.add_lease(storage_index, renew_secret, cancel_secret))
        return d

    def get_buckets(self, storage_index):
        return self._inner.get_buckets(storage_index)

    def slot_readv(self, storage_index, shares, readv):
        return self._inner.slot_readv(storage_index, shares, readv)

    def slot_testv_and_readv_and_writev(self, storage_index, secrets, tw_vectors, r_vector):
        written = 0
        for _shnum, (_testv, datav, _new_length) in (tw_vectors or {}).items():
            for _offset, data in datav or []:
                written += len(data or b"")
        d = self._pay(storage_index, written)
        d.addCallback(
            lambda _g: self._inner.slot_testv_and_readv_and_writev(
                storage_index, secrets, tw_vectors, r_vector
            )
        )
        return d

    def advise_corrupt_share(self, share_type, storage_index, shnum, reason):
        return self._inner.advise_corrupt_share(share_type, storage_index, shnum, reason)


plugin = LeasegridZKAPPlugin()
