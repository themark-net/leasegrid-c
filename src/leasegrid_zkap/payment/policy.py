"""Price, quote window, and confirmation policy (docs/07-payment.md §2.3, §2.4, §4).

All amounts are integer piconero (1 XMR = 10**12). Tokens do not split.
"""

from __future__ import annotations

from dataclasses import dataclass

PICONERO = 10**12


@dataclass(frozen=True)
class PricePolicy:
    price_piconero: int  # per token, operator-set
    quote_ttl: int = 30 * 60  # seconds the quoted amount is shown as "exact"
    grace: int = 24 * 3600  # seconds after quote_expires the quoted price is still honoured
    confirmations_small: int = 2
    confirmations_large: int = 10
    large_amount_piconero: int = PICONERO // 2  # ≥ this needs confirmations_large
    max_tokens_per_quote: int = 1000

    def __post_init__(self) -> None:
        if self.price_piconero <= 0:
            raise ValueError("price_piconero must be positive")
        if self.confirmations_small < 1 or self.confirmations_large < self.confirmations_small:
            raise ValueError("confirmations must be ≥ 1 and large ≥ small")
        if self.max_tokens_per_quote < 1:
            raise ValueError("max_tokens_per_quote must be ≥ 1")

    def amount_due(self, tokens: int) -> int:
        if tokens < 1 or tokens > self.max_tokens_per_quote:
            raise ValueError("tokens must be 1..%d" % self.max_tokens_per_quote)
        return tokens * self.price_piconero

    def confirmations_required(self, amount_seen_piconero: int) -> int:
        if amount_seen_piconero >= self.large_amount_piconero:
            return self.confirmations_large
        return self.confirmations_small

    def effective_price(self, quoted_price: int, first_confirmed_at: float, grace_until: float) -> int:
        """Quoted price inside the grace window; today's price after it."""
        if first_confirmed_at <= grace_until:
            return quoted_price
        return self.price_piconero

    @staticmethod
    def tokens_owed(amount_confirmed: int, effective_price: int) -> int:
        if effective_price <= 0:
            raise ValueError("effective_price must be positive")
        return max(0, amount_confirmed // effective_price)

    @staticmethod
    def format_xmr(piconero: int) -> str:
        whole, frac = divmod(int(piconero), PICONERO)
        s = "%d.%012d" % (whole, frac)
        return s.rstrip("0").rstrip(".") if "." in s else s
