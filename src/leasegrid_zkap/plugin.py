"""Tahoe 1.20 IFoolscapStoragePlugin: wrap anonymous StorageServer + spend HTTP."""

from __future__ import annotations

from twisted.internet.defer import succeed
from twisted.web.resource import Resource
from twisted.web.static import Data
from zope.interface import implementer

from allmydata.client import AnnounceableStorageServer
from allmydata.interfaces import IFoolscapStoragePlugin, IStorageServer
from allmydata.storage.server import FoolscapStorageServer

from .constants import PLUGIN_NAME
from .crypto import load_signing_key
from .gate import LeaseGate, install_on_storage_server
from .spentset import SpentSet
from .storage_http import start_storage_http


def _cfg(configuration, key, default=None):
    if hasattr(configuration, "get"):
        return configuration.get(key, default)
    return default


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
        install_on_storage_server(ss, gate)
        if listen:
            start_storage_http(gate, listen)

        announcement = {
            "issuer-pubkey-id": gate.issuer_pubkey_id,
            "domain": "leasegrid-v0",
            "denomination": gate.info["denomination"],
        }
        return succeed(
            AnnounceableStorageServer(
                announcement,
                FoolscapStorageServer(ss),
            )
        )

    def get_storage_client(self, configuration, announcement, get_rref):
        return _PassThroughStorageClient(get_rref)

    def get_client_resource(self, configuration):
        body = (
            b'{"plugin":"leasegrid-zkap-v0","note":"spend HTTP is on the storage node"}'
        )
        return Data(body, "application/json")


@implementer(IStorageServer)
class _PassThroughStorageClient:
    """Foolscap client for the plugin FURL. Live grid 1.20 still uses GBS HTTP."""

    def __init__(self, get_rref):
        self.get_rref = get_rref

    def get_version(self):
        return self.get_rref().callRemote("get_version")


plugin = LeasegridZKAPPlugin()
