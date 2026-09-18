"""Lease-gate errors. ZKAPRequired is what Tahoe allocate/add_lease/renew raise."""


class ZKAPRequired(Exception):
    """Anonymous/unpaid allocate, add_lease, or renew is refused."""


class SpendError(Exception):
    """Spend rejected (bad MAC, bad R, wrong node, etc.)."""


class MainnetBanned(Exception):
    """Refused to use nimo mainnet monerod (:18081/:18083) or any mainnet nettype."""


class IssueError(Exception):
    """Paid issuance refused (unpaid, underpay, vid mismatch, already spent)."""
