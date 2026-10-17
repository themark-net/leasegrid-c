"""Assertions for buyer-visible Sync text.

Paths may appear. A furl, a traceback, an exception class, and a module
name must not. A 6-character window of the planted tub-id or swissnum
must not either.
"""

from __future__ import annotations

import re

# Obviously fake. Tests feed this through each raw-text site.
# 32-char lowercase base32 ([a-z2-7]), with "planted" / "fake" in the token.
FAKE_TUBID = "qqplanted2qqplanted2qqplanted2qq"
FAKE_SWISSNUM = "qqfake2qqfake2qqfake2qqfake2qqf2"
POISON = (
    "Traceback (most recent call last): fake.mod.RuntimeError: "
    "pb://FAKE-TUBID@127.0.0.1:1/FAKE-SWISS "
    f"pb://{FAKE_TUBID}@127.0.0.1:1/{FAKE_SWISSNUM}"
)
FURL_SHAPE = re.compile(r"pb://[^\s/]+@[^\s/]+/[^\s]+", re.IGNORECASE)
EXC_CLASS = re.compile(r"\b[A-Za-z_][\w.]*(?:Error|Exception)\b")


def _six_char_windows(secret: str) -> tuple[str, ...]:
    return tuple(secret[i : i + 6] for i in range(len(secret) - 5))


def assert_no_raw_user_text(blob: str) -> None:
    assert "pb://" not in blob
    assert FURL_SHAPE.search(blob) is None
    assert "Traceback" not in blob
    assert EXC_CLASS.search(blob) is None
    assert "fake.mod" not in blob
    assert "RuntimeError" not in blob
    assert POISON not in blob
    for secret in (FAKE_TUBID, FAKE_SWISSNUM):
        for window in _six_char_windows(secret):
            assert window not in blob
