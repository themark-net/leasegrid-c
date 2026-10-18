#!/usr/bin/env python3
"""Run a mutation and require the named tests to fail, then restore the file.

cases.py defines CASES = [(name, file, old, new, [pytest args])].
Exit 0 when every case is RED, 1 when any test still passed, 2 on setup errors.
A target with uncommitted changes is refused so a mutant cannot be committed.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import subprocess
import sys
from pathlib import Path


def _load_cases(path: Path) -> list:
    spec = importlib.util.spec_from_file_location("prove_red_cases", path)
    if spec is None or spec.loader is None:
        print("could not load %s" % path, file=sys.stderr)
        raise SystemExit(2)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    cases = getattr(module, "CASES", None)
    if not isinstance(cases, list) or not cases:
        print("CASES missing", file=sys.stderr)
        raise SystemExit(2)
    parsed = []
    for row in cases:
        if not (isinstance(row, tuple) and len(row) == 5):
            print("CASES row is not a 5-tuple", file=sys.stderr)
            raise SystemExit(2)
        name, file, old, new, args = row
        if not isinstance(name, str) or not isinstance(file, str):
            print("CASES name and file must be strings", file=sys.stderr)
            raise SystemExit(2)
        if not isinstance(old, str) or not isinstance(new, str) or old == "":
            print("CASES old/new must be strings and old must be non-empty", file=sys.stderr)
            raise SystemExit(2)
        if not isinstance(args, (list, tuple)) or not all(isinstance(a, str) for a in args):
            print("CASES pytest args must be a list of strings", file=sys.stderr)
            raise SystemExit(2)
        parsed.append((name, Path(file), old, new, list(args)))
    return parsed


def _uncommitted(path: Path) -> bool:
    """True when git sees staged, unstaged, or untracked content at path."""
    proc = subprocess.run(
        ["git", "status", "--porcelain", "--", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        print(proc.stderr, file=sys.stderr, end="")
        raise SystemExit(2)
    return bool(proc.stdout.strip())


def _run_case(python: str, path: Path, old: str, new: str, args: list[str]) -> str:
    original = path.read_bytes()
    try:
        text = original.decode("utf-8")
        if old not in text:
            print("PATTERN MISSING", file=sys.stderr)
            raise SystemExit(2)
        path.write_text(text.replace(old, new, 1), encoding="utf-8")
        env = os.environ.copy()
        env["QT_QPA_PLATFORM"] = "offscreen"
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        proc = subprocess.run(
            [python, "-m", "pytest", "-q", "-p", "no:cacheprovider", *args],
            env=env,
            check=False,
        )
        return "RED" if proc.returncode != 0 else "SURVIVED"
    finally:
        path.write_bytes(original)


def _table(rows: list[tuple[str, str]]) -> str:
    name_w = max([len("name")] + [len(name) for name, _result in rows])
    lines = ["%s  %s" % ("name".ljust(name_w), "result")]
    for name, result in rows:
        lines.append("%s  %s" % (name.ljust(name_w), result))
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prove a fix is RED when reverted.")
    parser.add_argument("cases", type=Path)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args(argv)
    if not args.cases.is_file():
        print("cases file not found", file=sys.stderr)
        return 2
    cases = _load_cases(args.cases)
    for _name, path, _old, _new, _pytest_args in cases:
        if not path.is_file():
            print("target missing: %s" % path, file=sys.stderr)
            return 2
        if _uncommitted(path):
            print("uncommitted changes in %s" % path, file=sys.stderr)
            return 2
    rows: list[tuple[str, str]] = []
    touched: list[Path] = []
    for name, path, old, new, pytest_args in cases:
        touched.append(path)
        rows.append((name, _run_case(args.python, path, old, new, pytest_args)))
    leaked = []
    for path in touched:
        diff = subprocess.run(["git", "diff", "--quiet", "--", str(path)], check=False)
        if diff.returncode != 0:
            leaked.append(str(path))
    table = _table(rows)
    sys.stdout.write(table)
    if args.receipt is not None:
        args.receipt.write_text(table, encoding="utf-8")
    if leaked:
        print("git diff is not quiet: %s" % ", ".join(leaked), file=sys.stderr)
        return 2
    if any(result == "SURVIVED" for _name, result in rows):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
