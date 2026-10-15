"""The exit-test log dump must not leak furl, swissnum or tub-id material (#59).

Runs the real packaging/tahoe-log-filter.sh on a planted log. Every secret
below is fake and only ever appears in this test.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

FILTER = Path(__file__).resolve().parents[1] / "packaging" / "tahoe-log-filter.sh"

TUBID = "faketubidplanted2345abcdefghijkl"  # 32 chars, base32 alphabet
SWISS = "fakeswissplanted7654mnopqrstqwxy"  # 32 chars, base32 alphabet
SWISS_TAIL = SWISS[-6:]
FURL = f"pb://{TUBID}@tcp:127.0.0.1:47001/{SWISS}"
BENIGN = "2026-10-15T21:40:00.000Z [-] Listening on port 3456 (benign-marker)"

PLANTED = "\n".join(
    [
        BENIGN,
        f"2026-10-15T21:40:01.000Z [-] Error: introducer at {FURL} refused",
        f"2026-10-15T21:40:02.000Z [-] Starting client with introducer pb://{TUBID}@tcp:127.0.0.1:47001/fakeswiss",
        "planted7654mnopqrstqwxy",
        f"2026-10-15T21:40:03.000Z [-] Exception: node lock held for {SWISS}",
        SWISS,
        SWISS_TAIL,
        f"  tub id {TUBID}",
        TUBID,
        "",
    ]
)


@pytest.mark.skipif(
    sys.platform == "win32" or shutil.which("bash") is None,
    reason="filter runs under bash on the CI runners; Windows bash on PATH may be WSL",
)
def test_tahoe_log_filter_drops_and_redacts_secrets():
    out = subprocess.run(
        ["bash", str(FILTER)], input=PLANTED, capture_output=True, text=True, check=True
    ).stdout
    assert "benign-marker" in out
    for secret in (TUBID, SWISS, SWISS_TAIL, "planted7654mnopqrstqwxy"):
        assert secret not in out, f"leaked {secret[:4]}…"
    assert "pb://" not in out
