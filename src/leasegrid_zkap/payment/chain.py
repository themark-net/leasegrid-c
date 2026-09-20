"""ChainWatcher: the only question the issuer asks Monero.

    "what has subaddress #i received, and how deep is each transfer?"

FakeChain answers it from memory so the whole voucher lifecycle runs in tests
and in the dev grid. The real adapter (monero-wallet-rpc, view-only wallet) is
a separate module and the only piece that needs block time.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Transfer:
    amount_piconero: int
    confirmations: int  # 0 = seen in the mempool / unconfirmed


class ChainWatcher(Protocol):
    def new_address(self, vid: bytes) -> tuple[str, int]:
        """Allocate a fresh subaddress for this quote; return (address, index)."""

    def received(self, index: int) -> list[Transfer]:
        """Every transfer to subaddress #index, with its current depth."""

    def height(self) -> int: ...


class FakeChain:
    """In-memory chain for tests and `--chain fake` dev grids.

    pay() adds an unconfirmed transfer; mine(n) deepens every transfer by n.
    Addresses are deterministic from the index so tests can assert on them.
    """

    prefix = "FAKE"

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._next_index = 1
        self._addr_to_index: dict[str, int] = {}
        self._transfers: dict[int, list[Transfer]] = {}
        self._height = 1000

    def new_address(self, vid: bytes) -> tuple[str, int]:
        with self._lock:
            index = self._next_index
            self._next_index += 1
            address = "%s%08d%s" % (self.prefix, index, vid.hex())
            self._addr_to_index[address] = index
            self._transfers.setdefault(index, [])
            return address, index

    def index_of(self, address: str) -> int | None:
        with self._lock:
            return self._addr_to_index.get(address)

    def pay(self, address_or_index: str | int, amount_piconero: int) -> int:
        """Send amount to a subaddress (unconfirmed). Returns the index paid."""
        if amount_piconero <= 0:
            raise ValueError("amount must be positive")
        with self._lock:
            if isinstance(address_or_index, int):
                index = address_or_index
            else:
                if address_or_index not in self._addr_to_index:
                    raise KeyError("unknown address")
                index = self._addr_to_index[address_or_index]
            if index not in self._transfers:
                raise KeyError("unknown subaddress index")
            self._transfers[index].append(Transfer(int(amount_piconero), 0))
            return index

    def mine(self, blocks: int = 1) -> int:
        with self._lock:
            self._height += blocks
            for index, lst in self._transfers.items():
                self._transfers[index] = [
                    Transfer(t.amount_piconero, t.confirmations + blocks) for t in lst
                ]
            return self._height

    def received(self, index: int) -> list[Transfer]:
        with self._lock:
            return list(self._transfers.get(index, []))

    def height(self) -> int:
        with self._lock:
            return self._height
