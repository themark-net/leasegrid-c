"""Tracked files must not name the internal lab hosts, LAN or dev checkout.

The repo is public and holds code plus abstract deploy docs. Real host names,
the lab LAN and the developer's checkout layout live in the private ops repo
(see AGENTS.md). Docs use role placeholders instead: ``lab-introducer``,
``lab-storage-a`` and so on, ``<introducer-ip>``, and ``$LEASEGRID_LAB_DIR``.

``plant`` and ``maximum`` are also English words, so they only count in a host
context: next to another host name or an arrow, in backticks or quotes, or
after "on" or "host". The other names count anywhere.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve().relative_to(ROOT).as_posix()

# Vendored upstream file. "MAX_FD=maximum" there is the Gradle wrapper's own text.
ALLOW_FILES = {"android/gradlew"}
SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".icns", ".jar", ".svg", ".webp", ".zip"}

_ALWAYS = re.compile(r"(?i)\b(?:nimo|borg|beelink|leasegrid-\d+)\b")
_DEV = re.compile(r"DEVELOP/")
_LAN = re.compile(r"\b10\.42\.0\.\d+")
_WORD = r"(?:plant|maximum)"
_HOSTISH = re.compile(
    r"(?i)"
    r"\b" + _WORD + r"\s*(?:\u2194|<->|<-->)"  # plant <-> x
    r"|(?:\u2194|<->|<-->)\s*" + _WORD + r"\b"  # x <-> maximum
    r"|\b" + _WORD + r"\s+and\s+" + _WORD + r"\b"
    r"|\b" + _WORD + r",\s*" + _WORD + r"\b"
    r"|`" + _WORD + r"`"
    r"|[\"']" + _WORD + r"[\"']"
    r"|\b(?:on|hosts?)\s+" + _WORD + r"\b"
)


def internal_names(line: str) -> list[str]:
    found: list[str] = []
    for rx in (_ALWAYS, _DEV, _LAN, _HOSTISH):
        found += [m.group(0) for m in rx.finditer(line)]
    return found


def _tracked() -> list[str]:
    out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True).stdout
    return [p for p in out.decode("utf-8").split("\0") if p]


def test_matcher_flags_hosts_and_skips_english() -> None:
    host = "ni" + "mo"
    assert internal_names("Dogfood on %s" % host) == [host]
    assert internal_names("introducer leasegrid-" + "1 at 10.42." + "0.70") == ["leasegrid-1", "10.42.0.70"]
    assert internal_names("~/" + "DEVELOP/leasegrid-c") == ["DEVELOP/"]
    assert internal_names("plant \u2194 x") == ["plant \u2194"]
    assert internal_names("x <-> maximum") == ["<-> maximum"]
    assert internal_names("hosts plant and maximum") != []
    assert internal_names('{"nickname": "maximum"}') == ['"maximum"']
    assert internal_names("storage `borg`, `plant`") != []
    # English uses stay legal.
    assert internal_names("a span past Qt's widget maximum, is not a window") == []
    assert internal_names("the maximum file descriptor limit") == []
    assert internal_names("plant a fake secret in the log") == []
    assert internal_names("leasegrid-c and leasegrid-zkap-lab and lab-storage-a") == []
    assert internal_names("~/src/leasegrid-c, 192.0.2.10, 10.4.0.1") == []


def test_no_tracked_file_names_an_internal_host() -> None:
    hits: list[str] = []
    for rel in _tracked():
        for found in sorted(set(internal_names(rel.replace("-", " ").replace("_", " ")))):
            hits.append(f"{rel}: file name has {found}")
        if rel == SELF or rel in ALLOW_FILES or Path(rel).suffix.lower() in SKIP_SUFFIXES:
            continue
        path = ROOT / rel
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for n, line in enumerate(text.splitlines(), 1):
            for found in internal_names(line):
                hits.append(f"{rel}:{n}: {found}")
    assert not hits, (
        "use role placeholders (lab-introducer, lab-storage-a, <introducer-ip>, $LEASEGRID_LAB_DIR); "
        "real names belong in the private ops repo:\n" + "\n".join(hits)
    )
