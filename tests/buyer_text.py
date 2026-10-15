"""Assertions for buyer-visible Sync text.

Paths may appear. A furl, a traceback, an exception class, and a module
name must not.
"""

from __future__ import annotations

import re

# Obviously fake. Tests feed this through each raw-text site.
POISON = (
    "Traceback (most recent call last): fake.mod.RuntimeError: "
    "pb://FAKE-TUBID@127.0.0.1:1/FAKE-SWISS"
)
FURL_SHAPE = re.compile(r"pb://[^\s/]+@[^\s/]+/[^\s]+", re.IGNORECASE)
EXC_CLASS = re.compile(r"\b[A-Za-z_][\w.]*(?:Error|Exception)\b")


def assert_no_raw_user_text(blob: str) -> None:
    assert "pb://" not in blob
    assert FURL_SHAPE.search(blob) is None
    assert "Traceback" not in blob
    assert EXC_CLASS.search(blob) is None
    assert "fake.mod" not in blob
    assert "RuntimeError" not in blob
    assert POISON not in blob
