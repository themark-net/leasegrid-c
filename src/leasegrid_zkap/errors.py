"""Lease-gate errors. ZKAPRequired is what Tahoe allocate/add_lease/renew raise."""


class ZKAPRequired(Exception):
    """Anonymous/unpaid allocate, add_lease, or renew is refused."""


class SpendError(Exception):
    """Spend rejected (bad MAC, bad R, wrong node, etc.)."""
