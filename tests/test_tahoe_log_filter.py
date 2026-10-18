"""The exit-test log dump must not leak furl, swissnum or tub-id material (#59).

Runs the real packaging/tahoe-log-filter.sh on a planted log. Every secret
below is fake and only ever appears in this test.

Contrived shapes on an allowlisted line (#54 follow-up): uppercase, dashed,
spaced, base64 and hex are redacted since v0.1.4. A short fragment under 20
chars stays a strict xfail as a written design limit.
"""

from __future__ import annotations

import base64
import os
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
    # v0.1.5 corpus: short dashed tokens (kills a widened dashed rule), snake_case
    # and CamelCase names under the new floors, hyphenated 8-letter words.
    "2026-10-15T21:40:10.000Z [-] Error: stop requested by an-ok-ci-run-on-the-box",
    "2026-10-15T21:40:11.000Z [-] Exception in _start_magic_folder_and_wait_for_api (pid 77)",
    "2026-10-15T21:40:12.000Z [-] Error: TwistedDeprecationWarning then UnhandledErrorInDeferred",
    "2026-10-15T21:40:13.000Z [-] Error: tahoe-lafs magic-folder leasegrid-sync shutdown",
    "2026-10-15T21:40:14.000Z [-] Error: tahoe-lafs-magic-folder plugin stopped (exit 1)",
)


def test_legit_lines_survive_the_new_rules():
    """The v0.1.4 rules must not eat ordinary diagnostic text."""
    out = _filter_stdout("\n".join(LEGIT_LINES + ("",)))
    assert "REDACTED" not in out, out
    for line in LEGIT_LINES:
        assert line in out, line


_SNAKE40 = "_get_magic_folder_participants_for_collective"


def test_long_snake_case_name_survives_on_an_allowlisted_line():
    """A 40+ identifier with no digit and one letter case is not a secret."""
    assert len(_SNAKE40) >= 40
    upper = "GET_MAGIC_FOLDER_PARTICIPANTS_FOR_COLLECTIVE"
    assert len(upper) >= 40
    line = (
        "2026-10-15T21:40:11.000Z [-] Exception in "
        f"{_SNAKE40} {upper} (pid 77)"
    )
    out = _filter_stdout(line + "\n")
    assert _SNAKE40 in out
    assert upper in out
    assert "REDACTED" not in out


def test_long_mixed_token_is_still_redacted():
    """A 40+ token with both letter cases is a secret shape, not a name."""
    token = "Abcdefghij_" * 4
    assert len(token) >= 40
    out = _filter_stdout(_allowlisted(token))
    assert token not in out
    assert "REDACTED" in out


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


# --- v0.1.5: more shapes (seeded) ------------------------------------------
def _rng(tag: str):
    import random

    return random.Random(f"{_GLUE_SEED}-{tag}")


def _b64url_secrets(n: int) -> list[str]:
    rng = _rng("b64url")
    out: list[str] = []
    while len(out) < n:
        raw = bytes(rng.randrange(256) for _ in range(32))
        tok = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
        if "-" in tok or "_" in tok:
            out.append(tok)
    return out


def _mixed_b32_secrets(n: int) -> list[str]:
    rng = _rng("mixed")
    out: list[str] = []
    while len(out) < n:
        tok = "".join(
            c.upper() if rng.random() < 0.5 else c for c in (rng.choice(_B32) for _ in range(32))
        )
        if any(c.isupper() for c in tok) and any(c.islower() for c in tok):
            out.append(tok)
    return out


def _dashed8_secrets(n: int) -> list[str]:
    rng = _rng("dashed8")
    out = []
    for _ in range(n):
        tok = "".join(rng.choice(_B32) for _ in range(32))
        out.append("-".join(tok[i : i + 8] for i in range(0, 32, 8)))
    return out


@pytest.mark.parametrize(
    "shape", ["base64url-unpadded", "mixed-case-base32", "dashed-8"],
)
def test_v015_shapes_never_leak(shape: str) -> None:
    gen = {
        "base64url-unpadded": _b64url_secrets,
        "mixed-case-base32": _mixed_b32_secrets,
        "dashed-8": _dashed8_secrets,
    }[shape]
    toks = gen(200)
    lines = [f"{_GLUE_TS}{tok} ok" for tok in toks]
    outs = _filter_stdout("\n".join(lines) + "\n").splitlines()
    assert len(outs) == len(toks)
    leaked = sum(
        any(w in out[len(_GLUE_TS) :] for w in _windows8(tok.replace("-", "")) + _windows8(tok))
        for tok, out in zip(toks, outs)
    )
    assert leaked == 0, f"{shape}: {leaked}/{len(toks)} leaked an 8-char window"


# --- PR #72 review follow-ups 1 and 2 (seeded) -----------------------------
# Follow-up 1: deleting the main [a-z2-7]{20,} rule left the suite green
# (mixed-case 32 covered every 32-char plant), yet 20-31 char base32 and the
# 26-char key in Tahoe caps leaked 300/300. Shapes follow Tester's
# probe_adversarial.py ("len b32 N", "tahoe cap URI:DIR2", "tahoe cap URI:CHK").
def _b32(rng, n: int) -> str:
    return "".join(rng.choice(_B32) for _ in range(n))


@pytest.mark.parametrize("length", range(20, 32))
def test_short_lowercase_base32_never_leaks(length: int) -> None:
    rng = _rng(f"b32-{length}")
    toks = [_b32(rng, length) for _ in range(100)]
    lines = [f"{_GLUE_TS}{tok} ok" for tok in toks]
    outs = _filter_stdout("\n".join(lines) + "\n").splitlines()
    assert len(outs) == len(toks)
    leaked = sum(any(w in out for w in _windows8(t)) for t, out in zip(toks, outs))
    assert leaked == 0, f"b32-{length}: {leaked}/{len(toks)} leaked an 8-char window"


@pytest.mark.parametrize("kind", ["DIR2", "CHK"])
def test_tahoe_cap_keys_never_leak(kind: str) -> None:
    rng = _rng(f"cap-{kind}")
    cases = []
    for _ in range(100):
        a, b = _b32(rng, 26), _b32(rng, 52)
        tail = ":3:10:1234" if kind == "CHK" else ""
        cases.append((a, b, f"{_GLUE_TS}URI:{kind}:{a}:{b}{tail} ok"))
    outs = _filter_stdout("\n".join(c[2] for c in cases) + "\n").splitlines()
    assert len(outs) == len(cases)
    leaked = sum(
        any(w in out for w in _windows8(a) + _windows8(b)) for (a, b, _), out in zip(cases, outs)
    )
    assert leaked == 0, f"URI:{kind}: {leaked}/{len(cases)} leaked an 8-char window"


# Follow-up 2: the hex and uppercase rules redact the WHOLE alphanumeric token,
# not just the run. Short glued affixes outside each rule's alphabet keep the
# token under 32/40 chars, so no other rule reaches it; with the expansion
# reverted the affixes survive next to REDACTED.
def _whole_token_cases(kind: str) -> list[tuple[str, str]]:
    import re

    rng = _rng(f"whole-{kind}")
    out = []
    while len(out) < 50:
        if kind == "hex":
            run = "".join(rng.choice("0123456789abcdef") for _ in range(32))
            pre = "".join(rng.choice("ghijkmnpqrstuvwxyz") for _ in range(2))
            suf = "".join(rng.choice("GHJKMNPQRSTUVWXYZ") for _ in range(2))
            if re.search(r"[a-z2-7]{20}", pre + run):  # base32 rule would eat it
                continue
        else:
            run = "".join(rng.choice(_B32.upper()) for _ in range(20))
            pre = "".join(rng.choice("abcdefghijklmnopqrstuvwxyz0189") for _ in range(2))
            suf = "".join(rng.choice("0189") for _ in range(2))
        out.append((pre + run + suf, f"{_GLUE_TS}id={pre}{run}{suf} end"))
    return out


@pytest.mark.parametrize("kind", ["hex", "uppercase"])
def test_rule_redacts_the_whole_token(kind: str) -> None:
    cases = _whole_token_cases(kind)
    outs = _filter_stdout("\n".join(line for _, line in cases) + "\n").splitlines()
    assert len(outs) == len(cases)
    bad = [out for out in outs if not out.endswith("id=REDACTED end")]
    assert not bad, f"{kind}: {len(bad)}/{len(cases)} kept part of the token: {bad[0]!r}"


# Over-redaction we accept (PR #71 review follow-up 1). Each would need a rule
# that lets some real secret shape through, so redact-more wins. strict=True:
# if a future tuning un-blanks one, it XPASSes and turns red, forcing a fresh
# look at the leak tests above.
_ACCEPTED = [
    pytest.param(
        "2026-10-15T21:40:20.000Z [-] Error: when node exit code from tahoe stop",
        id="five-four-letter-words",
        marks=pytest.mark.xfail(
            strict=True,
            reason="accepted: a 4-char-chunked base32 secret has no digit in ~0.13% "
            "of draws, so a digit/vowel test to spare English would reopen a leak",
        ),
    ),
    pytest.param(
        '  File "/usr/lib/python3/dist/packages/twisted/internet/defer/tcp", line 9, in run',
        id="separator-free-path-40",
        marks=pytest.mark.xfail(
            strict=True,
            reason="accepted: random base64 contains '/' about half the time, so "
            "sparing slash paths would leave base64 pieces under the 40 floor",
        ),
    ),
    pytest.param(
        "2026-10-15T21:40:21.000Z [-] Error: build rev 3e1f0a9b8c7d6e5f4a3b2c1d0e9f8a7b6c5d4e3f",
        id="git-sha-40",
        marks=pytest.mark.xfail(
            strict=True,
            reason="accepted: a 40-hex token is also a hex-encoded 20-byte secret",
        ),
    ),
    pytest.param(
        "2026-10-15T21:40:22.000Z [-] Error: SSLVTHREEALERTHANDSHAKEFAIL",
        id="uppercase-constant-20",
        marks=pytest.mark.xfail(
            strict=True,
            reason="accepted: indistinguishable from an uppercase base32 tub-id or swissnum",
        ),
    ),
]


@pytest.mark.parametrize("line", _ACCEPTED)
def test_accepted_over_redaction_is_documented(line: str) -> None:
    out = _filter_stdout(line + "\n")
    assert out.strip() == line.strip()


def test_filter_output_does_not_depend_on_awk(tmp_path: Path) -> None:
    """mawk and gawk on PATH must not change the filter. Skip only if absent."""
    found = [p for p in ("/usr/bin/mawk", "/usr/bin/gawk") if os.access(p, os.X_OK)]
    if not found:
        pytest.skip("neither mawk nor gawk is installed")
    bash = require_bash()
    planted = (
        _allowlisted(B64_UNPADDED_40)
        + "2026-10-15T21:40:11.000Z [-] Exception in "
        + _SNAKE40
        + " (pid 77)\n"
    ).encode("utf-8")
    outputs: list[str] = []
    for awk in found:
        bindir = tmp_path / Path(awk).name
        bindir.mkdir()
        shim = bindir / "awk"
        shim.write_text('#!/bin/sh\nexec %s "$@"\n' % awk, encoding="utf-8")
        shim.chmod(0o755)
        env = os.environ.copy()
        env["PATH"] = str(bindir) + os.pathsep + env.get("PATH", "")
        which = subprocess.run(
            [bash, "-c", "command -v awk"],
            capture_output=True,
            check=False,
            env=env,
            text=True,
        )
        assert which.stdout.strip() == str(shim)
        proc = subprocess.run(
            [bash, str(FILTER)],
            input=planted,
            capture_output=True,
            check=False,
            env=env,
        )
        assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
        out = proc.stdout.decode("utf-8", "replace")
        assert B64_UNPADDED_40 not in out
        assert _SNAKE40 in out
        outputs.append(out)
    assert len(set(outputs)) == 1


# Fix round 3. The filter script is unchanged. These fakes pin two survivors:
# a 40-character base64url token, and the fragment rate of a long
# lowercase/digit/underscore token.
def _seeded_tokens(tag: str, alphabet: str, length: int, count: int, accept) -> list[str]:
    import random

    rng = random.Random(tag)
    out: list[str] = []
    while len(out) < count:
        tok = "".join(rng.choice(alphabet) for _ in range(length))
        if accept(tok):
            out.append(tok)
    return out


def _lines_leaking(tokens: list[str]) -> int:
    lines = [f"{_GLUE_TS}{tok} ok" for tok in tokens]
    outs = _filter_stdout("\n".join(lines) + "\n").splitlines()
    assert len(outs) == len(lines)
    leaked = 0
    for tok, out in zip(tokens, outs):
        if any(window in out for window in _windows8(tok)):
            leaked += 1
    return leaked


_B64URL = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
_F3_ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789_"
# This seed on the unchanged filter. Seed v017-fix3-F3. Mutant F3, which
# widens the snake_case protector to digits, leaks far more than this.
_F3_BASE_LEAKS = 46


def test_forty_char_base64url_tokens_are_redacted() -> None:
    """Exactly 40 characters, and the token contains '-' or '_'."""
    tokens = _seeded_tokens(
        "v017-fix3-F1",
        _B64URL,
        40,
        80,
        lambda tok: "-" in tok or "_" in tok,
    )
    assert len(tokens) >= 50
    assert all(len(tok) == 40 for tok in tokens)
    leaked = _lines_leaking(tokens)
    assert leaked == 0, "%d/%d 40-char base64url tokens leaked" % (leaked, len(tokens))


def test_digit_underscore_tokens_leak_no_worse_than_base() -> None:
    """48-character lowercase, digit and underscore tokens.

    Some 8-character fragments survive on the current script, which is the
    same script as b267059. The bound is this seed's count.
    """
    tokens = _seeded_tokens(
        "v017-fix3-F3",
        _F3_ALPHABET,
        48,
        300,
        lambda tok: any(ch.isdigit() for ch in tok) and "_" in tok,
    )
    leaked = _lines_leaking(tokens)
    assert leaked <= _F3_BASE_LEAKS, "%d/300 fragments survived; base count is %d" % (
        leaked,
        _F3_BASE_LEAKS,
    )
