"""The exit-test log dump must not leak furl, swissnum or tub-id material (#59).

Runs the real packaging/tahoe-log-filter.sh on a planted log. Every secret
below is fake and only ever appears in this test.

Contrived shapes that still leak on an allowlisted line are xfail(strict)
(#54 follow-up). A filter fix turns each of those red until the mark is removed.
"""

from __future__ import annotations

import base64
import subprocess
from pathlib import Path

import pytest

from tests.git_bash import require_bash

FILTER = Path(__file__).resolve().parents[1] / "packaging" / "tahoe-log-filter.sh"

TUBID = "faketubidplanted2345abcdefghijkl"  # 32 chars, base32 alphabet
SWISS = "fakeswissplanted7654mnopqrstqwxy"  # 32 chars, base32 alphabet
SWISS_TAIL = SWISS[-6:]
FURL = f"pb://{TUBID}@tcp:127.0.0.1:47001/{SWISS}"
BENIGN = "2026-10-15T21:40:00.000Z [-] Listening on port 3456 (benign-marker)"
SHORT = SWISS[:16]  # 16 < 20, so the [a-z2-7]{20,} rule does not cover it
DASHED = "-".join(SWISS[i : i + 4] for i in range(0, len(SWISS), 4))
SPACED = " ".join(SWISS[i : i + 4] for i in range(0, len(SWISS), 4))
B64_SWISS = base64.b64encode(SWISS.encode("ascii")).decode("ascii")
HEX_SWISS = SWISS.encode("ascii").hex()
# The lowercase run rule splits this hex, but 8-char windows still survive.
HEX_WINDOWS = tuple(HEX_SWISS[i : i + 8] for i in range(len(HEX_SWISS) - 7))

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


def _known_gap(detail: str):
    return pytest.mark.xfail(strict=True, reason=f"known gap: {detail} (#54 follow-up)")


def _filter_stdout(planted: str) -> str:
    bash = require_bash()
    # Bytes and LF line endings. text=True lets Windows translate newlines.
    raw = planted.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
    proc = subprocess.run(
        [bash, str(FILTER)],
        input=raw,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
    return proc.stdout.decode("utf-8", "replace")


def _allowlisted(payload: str) -> str:
    line = f"2026-10-15T21:40:01.000Z [-] Error: connect failed {payload}"
    return "\n".join([line, BENIGN, ""])


def test_tahoe_log_filter_drops_and_redacts_secrets():
    out = _filter_stdout(PLANTED)
    assert "benign-marker" in out
    for secret in (TUBID, SWISS, SWISS_TAIL, "planted7654mnopqrstqwxy"):
        assert secret not in out, f"leaked {secret[:4]}…"
    assert "pb://" not in out


@pytest.mark.parametrize(
    ("payload", "needles"),
    [
        pytest.param(
            TUBID.upper(),
            (),
            id="uppercase-tub",
            marks=_known_gap("uppercase base32 tub-id on an allowlisted line"),
        ),
        pytest.param(
            SWISS.upper(),
            (),
            id="uppercase-swiss",
            marks=_known_gap("uppercase base32 swissnum on an allowlisted line"),
        ),
        pytest.param(
            SHORT,
            (),
            id="short-fragment",
            marks=_known_gap("base32 fragment under 20 chars on an allowlisted line"),
        ),
        pytest.param(
            DASHED,
            (),
            id="separated-dashes",
            marks=_known_gap("swissnum split by dashes every 4 chars on an allowlisted line"),
        ),
        pytest.param(
            SPACED,
            (),
            id="separated-spaces",
            marks=_known_gap("swissnum split by spaces every 4 chars on an allowlisted line"),
        ),
        pytest.param(
            B64_SWISS,
            (),
            id="base64-swiss",
            marks=_known_gap("base64 encoding of a swissnum on an allowlisted line"),
        ),
        pytest.param(
            HEX_SWISS,
            HEX_WINDOWS,
            id="hex-swiss",
            marks=_known_gap("hex encoding of a swissnum on an allowlisted line"),
        ),
    ],
)
def test_allowlisted_contrived_shape_does_not_leak(payload: str, needles: tuple[str, ...]) -> None:
    out = _filter_stdout(_allowlisted(payload))
    assert "benign-marker" in out
    assert payload not in out
    for needle in needles:
        assert needle not in out


@pytest.mark.parametrize("key", ["furl=", "furl:", "FURL="])
def test_allowlisted_furl_value_is_redacted(key: str) -> None:
    # The furl rule rewrites the rest of the line to " REDACTED". The earlier
    # pb: rule alone would leave "furl=pb:REDACTED", hiding the secret but not
    # this redaction.
    payload = f"{key}pb://{TUBID}@tcp:127.0.0.1:47001/{SWISS}"
    out = _filter_stdout(_allowlisted(payload))
    assert "benign-marker" in out
    assert payload not in out
    assert TUBID not in out
    assert SWISS not in out
    assert "pb://" not in out
    assert f"{key} REDACTED" in out
