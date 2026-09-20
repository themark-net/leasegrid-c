"""Payment rail: XMR → vid → ZKAP batch. Design: docs/07-payment.md.

The chain is a payment detector and nothing more (ChainWatcher). Everything
else — quote, confirmation policy, voucher state machine, idempotent redeem,
settlement ledger — lives here and runs without Monero.
"""

from .chain import ChainWatcher, FakeChain, Transfer
from .policy import PICONERO, PricePolicy
from .store import (
    STATES,
    Voucher,
    VoucherStore,
    advance,
)

__all__ = [
    "PICONERO",
    "STATES",
    "ChainWatcher",
    "FakeChain",
    "PricePolicy",
    "Transfer",
    "Voucher",
    "VoucherStore",
    "advance",
]
