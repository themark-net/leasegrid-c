"""The exit-test log dump must not leak furl, swissnum or tub-id material (#59).

Runs the real packaging/tahoe-log-filter.sh on a planted log. Every secret
below is fake and only ever appears in this test.

Contrived shapes on an allowlisted line (#54 follow-up): uppercase, dashed,
spaced, base64 and hex are redacted since v0.1.4. A short fragment under 20
chars stays a strict xfail as a written design limit.
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


def _windows8(text: str) -> tuple[str, ...]:
    return tuple(text[i : i + 8] for i in range(len(text) - 7))


# One shape per v0.1.4 rule, each sized so only that rule can catch it.
HEX_32 = SWISS[:16].encode("ascii").hex()  # 32 hex chars: hex rule only
B64_PADDED_SHORT = base64.b64encode(SWISS[:20].encode("ascii")).decode("ascii")  # 28, ends "="
B64_UNPADDED_40 = base64.b64encode(SWISS[:30].encode("ascii")).decode("ascii")  # 40, no "="
assert len(HEX_32) == 32 and len(B64_PADDED_SHORT) == 28 and B64_PADDED_SHORT.endswith("=")
assert len(B64_UNPADDED_40) == 40 and "=" not in B64_UNPADDED_40

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
        ),
        pytest.param(
            SWISS.upper(),
            (),
            id="uppercase-swiss",
        ),
        pytest.param(
            SHORT,
            (),
            id="short-fragment",
            marks=_known_gap(
                "design limit: a base32 fragment under 20 chars on an allowlisted "
                "line is not redacted. Any length floor leaves a shorter fragment, "
                "and below 20 [a-z2-7] the rule starts eating ordinary words, "
                "module names and path parts on the very lines we keep for "
                "debugging. Non-allowlisted lines (bare fragments) are dropped"
            ),
        ),
        pytest.param(
            DASHED,
            (),
            id="separated-dashes",
        ),
        pytest.param(
            SPACED,
            (),
            id="separated-spaces",
        ),
        pytest.param(
            B64_SWISS,
            (),
            id="base64-swiss",
        ),
        pytest.param(
            HEX_SWISS,
            HEX_WINDOWS,
            id="hex-swiss",
        ),
        pytest.param(HEX_32, _windows8(HEX_32), id="hex-32"),
        pytest.param(B64_PADDED_SHORT, _windows8(B64_PADDED_SHORT), id="base64-padded-short"),
        pytest.param(B64_UNPADDED_40, _windows8(B64_UNPADDED_40), id="base64-unpadded-40"),
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


UUIDISH = "3f2a9c1e-0b7d-4e8a-9f61-2c5d8e7b4a10"
LEGIT_LINES = (
    '2026-10-15T21:40:05.000Z [-] Error: lock held, see /home/runner/work/leasegrid-c/leasegrid-c/tmp/tahoe/logs/twistd.log',
    '  File "/opt/hostedtoolcache/Python/3.11.9/x64/lib/python3.11/site-packages/twisted/internet/tcp.py", line 1338, in startListening',
    "twisted.internet.error.CannotListenError: Couldn't listen on 127.0.0.1:3456: [Errno 98] Address already in use.",
    "2026-10-15T21:40:06.000Z [-] Stopping factory <leasegrid-sync magic-folder client at 0x7f3a2b1c90>",
    "2026-10-15T21:40:07.000Z [-] Main loop terminated. Exit status 1 (pid 4242, port 3456)",
    f"2026-10-15T21:40:08.000Z [-] Error: request {UUIDISH} failed: ConnectionRefusedError",
    "2026-10-15T21:40:09.000Z [-] Unhandled error in Deferred: tahoe version 1.19.0",
)


def test_legit_lines_survive_the_new_rules():
    """The v0.1.4 rules must not eat ordinary diagnostic text."""
    out = _filter_stdout("\n".join(LEGIT_LINES + ("",)))
    assert "REDACTED" not in out, out
    for line in LEGIT_LINES:
        assert line in out, line


# --- v0.1.5: glued hex + base32 (Tester, PR #71 review) ---------------------
# In v0.1.4 the hex rule ran first and could eat the hex-alphabet prefix of a
# base32 secret glued to a 32+ hex run, leaving a sub-20 base32 remnant that
# the base32 rule no longer matched (2/2000 leaked at 26 chars, 107/2000 at 22;
# 0 on v0.1.3). Seeded, so a failure is reproducible.
_B32 = "abcdefghijklmnopqrstuvwxyz234567"
_GLUE_SEED = 20261017
_GLUE_N = 2000
_GLUE_TS = "2026-10-15T21:40:01.000Z [-] Error: node lock held for "


def _glued_cases(length: int, seed: int) -> list[tuple[str, str, str]]:
    import random

    rng = random.Random(seed + length)
    cases = []
    for _ in range(_GLUE_N):
        hexrun = "".join(rng.choice("0123456789abcdef") for _ in range(32))
        secret = "".join(rng.choice(_B32) for _ in range(length))
        cases.append((hexrun, secret, f"{_GLUE_TS}{hexrun}{secret} ok"))
    return cases


@pytest.mark.parametrize("length", [20, 22, 26, 32])
def test_glued_hex_and_base32_secret_never_leaks(length: int) -> None:
    cases = _glued_cases(length, _GLUE_SEED)
    out_lines = _filter_stdout("\n".join(line for _, _, line in cases) + "\n").splitlines()
    assert len(out_lines) == len(cases)
    leaked = 0
    for (hexrun, secret, _), out in zip(cases, out_lines):
        body = out[len(_GLUE_TS) :]
        if any(w in body for w in _windows8(secret)) or any(w in body for w in _windows8(hexrun)):
            leaked += 1
    assert leaked == 0, f"{leaked}/{len(cases)} glued lines leaked an 8-char window"
