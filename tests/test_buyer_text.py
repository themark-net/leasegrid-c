"""The buyer-text helper rejects a 6-character window of a planted secret."""

from __future__ import annotations

import pytest

from tests.buyer_text import FAKE_SWISSNUM, FAKE_TUBID, assert_no_raw_user_text

_BASE32 = set("abcdefghijklmnopqrstuvwxyz234567")


def test_six_char_window_fails_and_clean_blob_passes() -> None:
    assert_no_raw_user_text("could not join this friendnet.")
    for secret in (FAKE_SWISSNUM, FAKE_TUBID):
        assert len(secret) == 32
        assert set(secret) <= _BASE32
        assert "fake" in secret or "planted" in secret
        window = secret[7:13]
        assert len(window) == 6
        with pytest.raises(AssertionError):
            assert_no_raw_user_text(window)
