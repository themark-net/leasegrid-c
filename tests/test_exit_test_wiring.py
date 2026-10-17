"""exit-test.sh must not print a raw tahoe or grid log (#60 Tester follow-up).

Does not run packaging/exit-test.sh. The static check reads the script. The
dynamic check runs only dump_tahoe_logs against a temp dir.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from tests.git_bash import bash_path, require_bash
from tests.test_tahoe_log_filter import BENIGN, FURL, SWISS, TUBID

ROOT = Path(__file__).resolve().parents[1]
EXIT_TEST = ROOT / "packaging" / "exit-test.sh"
FILTER_NAME = "tahoe-log-filter.sh"

_LOG_REF = re.compile(r"tahoe\.log|grid\.out|GRID_LOG")
_ASSIGN = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$")
_FOR = re.compile(r"\bfor\s+([A-Za-z_][A-Za-z0-9_]*)\s+in\s+(.+)$")
_REDIR = re.compile(r"<\s*(\"[^\"]*\"|'[^']*'|\$\{[A-Za-z_][A-Za-z0-9_]*\}|\$[A-Za-z_][A-Za-z0-9_]*)")
_VAR = re.compile(r"^\$\{([A-Za-z_][A-Za-z0-9_]*)\}$|^\$([A-Za-z_][A-Za-z0-9_]*)$")
_DUMP_CMDS = {"cat", "tail", "head"}


def _strip_comment(line: str) -> str:
    # exit-test.sh has no '#' inside quotes.
    return line.split("#", 1)[0]


def _split_outside_quotes(line: str, sep: str) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    quote = ""
    for char in line:
        if quote:
            buf.append(char)
            if char == quote:
                quote = ""
            continue
        if char in "\"'":
            quote = char
            buf.append(char)
            continue
        if char == sep:
            parts.append("".join(buf))
            buf = []
            continue
        buf.append(char)
    parts.append("".join(buf))
    return parts


def _var_name(token: str) -> str | None:
    text = token.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        text = text[1:-1]
    match = _VAR.fullmatch(text)
    if not match:
        return None
    return match.group(1) or match.group(2)


def _token_is_log(token: str, log_vars: set[str]) -> bool:
    if _LOG_REF.search(token):
        return True
    name = _var_name(token)
    return bool(name and name in log_vars)


def _leading_command(segment: str) -> tuple[str, list[str]] | None:
    text = re.sub(r"^[\s{]+", "", segment.strip())
    parts = text.split()
    if not parts or parts[0] not in _DUMP_CMDS:
        return None
    return parts[0], parts[1:]


def _unfiltered_log_dumps(script: str) -> list[str]:
    """cat/tail/head of a tahoe or grid log whose pipeline skips the filter."""
    log_vars = {"GRID_LOG"}
    problems: list[str] = []
    for lineno, raw in enumerate(script.splitlines(), 1):
        code = _strip_comment(raw).strip()
        if not code:
            continue
        assign = _ASSIGN.match(code)
        if assign and _LOG_REF.search(assign.group(2)):
            log_vars.add(assign.group(1))
        for match in _FOR.finditer(code):
            if _LOG_REF.search(match.group(2)):
                log_vars.add(match.group(1))
        for statement in _split_outside_quotes(code, ";"):
            segments = _split_outside_quotes(statement, "|")
            for index, segment in enumerate(segments):
                parsed = _leading_command(segment)
                if not parsed:
                    continue
                _cmd, args = parsed
                if not any(_token_is_log(arg, log_vars) for arg in args):
                    continue
                later = " ".join(segments[index + 1 :])
                if FILTER_NAME not in later and FILTER_NAME not in segment:
                    problems.append(f"{lineno}: {code}")
            for redir in _REDIR.finditer(statement):
                if _token_is_log(redir.group(1), log_vars) and FILTER_NAME not in statement:
                    problems.append(f"{lineno}: {code}")
    return problems


def test_exit_test_prints_logs_only_through_filter() -> None:
    script = EXIT_TEST.read_text(encoding="utf-8")
    problems = _unfiltered_log_dumps(script)
    assert not problems, "raw log dump:\n" + "\n".join(problems)
    watched = [
        line
        for line in script.splitlines()
        if FILTER_NAME in line and ("tail " in line or "head " in line or "GRID_LOG" in line)
    ]
    assert len(watched) >= 3


def _extract_function(script: str, name: str) -> str:
    start = script.find(f"{name}()")
    if start < 0:
        raise AssertionError(f"{name}() missing from exit-test.sh")
    open_brace = script.find("{", start)
    depth = 0
    for index in range(open_brace, len(script)):
        char = script[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return script[start : index + 1]
    raise AssertionError(f"{name}() is unclosed")


def _sh_quote(text: str) -> str:
    return "'" + text.replace("'", "'\"'\"'") + "'"


def test_dump_tahoe_logs_hides_planted_secrets(tmp_path: Path) -> None:
    bash = require_bash()
    fn = _extract_function(EXIT_TEST.read_text(encoding="utf-8"), "dump_tahoe_logs")
    log = "\n".join(
        [
            BENIGN,
            f"2026-10-15T21:40:01.000Z [-] Error: introducer at {FURL} refused",
            SWISS,
            TUBID,
            SWISS[-6:],
            "",
        ]
    ).encode("ascii")
    for name in ("home", "home2"):
        directory = tmp_path / name / "logs"
        directory.mkdir(parents=True)
        (directory / "tahoe.log").write_bytes(log)
    runner = "\n".join(
        [
            "set -euo pipefail",
            f"ROOT={_sh_quote(bash_path(ROOT))}",
            f"T={_sh_quote(bash_path(tmp_path))}",
            fn,
            "dump_tahoe_logs",
            "",
        ]
    )
    proc = subprocess.run(
        [bash, "-s"],
        input=runner.encode("utf-8"),
        capture_output=True,
        check=False,
    )
    stdout = proc.stdout.decode("utf-8", "replace")
    combined = stdout + proc.stderr.decode("utf-8", "replace")
    assert proc.returncode == 0, combined
    assert stdout.count("benign-marker") == 2
    assert TUBID not in combined
    assert SWISS not in combined
    assert SWISS[-6:] not in combined
    assert "pb://" not in combined
