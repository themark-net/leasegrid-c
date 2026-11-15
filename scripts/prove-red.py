#!/usr/bin/env python3
"""Run a mutation and require the named tests to fail, then restore the file.

cases.py defines CASES = [(name, file, old, new, [pytest args])].

Each case runs on the clean tree first. A baseline that is not exit 0 is
``SETUP-ERROR (baseline rc=N)`` and the file is not mutated. After a green
baseline, pytest rc 1 is RED, rc 0 is SURVIVED, and any other rc (including
2, 3, 4, and 5) is ``SETUP-ERROR (rc=N)``.

Exit 0 when every case is RED. Exit 1 when any case SURVIVED and none is a
setup error. Exit 2 when any case is a setup error (setup errors win), the
pattern is missing, or a target is dirty or absent. A target with
uncommitted changes is refused so a mutant cannot be committed.

SIGINT, and SIGTERM on POSIX, restore the open target and exit 130 or 143.
Those signals are blocked while the original bytes are written, then
delivered, so a second signal during the write cannot skip the restore.
No receipt is written on that path.

A mutated Python file that does not compile is INVALID, not RED. INVALID
is not a kill. The process exits 2.

SIGKILL cannot be caught and leaves the mutant applied. The next run
restores a target whose bytes are exactly that case's mutant, then
continues. Any other uncommitted change is still refused. Hand recovery:
``git restore --source=HEAD -- <file>``.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


class _Stopped(BaseException):
    """SIGINT or SIGTERM. ``code`` is the process status after restore."""

    def __init__(self, code: int) -> None:
        self.code = code


def _install_stop_handlers() -> None:
    """Raise so ``finally`` restores the file. SIGTERM is POSIX-only."""

    def _handler(signum, _frame) -> None:
        raise _Stopped(130 if signum == signal.SIGINT else 143)

    signal.signal(signal.SIGINT, _handler)
    if sys.platform != "win32":
        signal.signal(signal.SIGTERM, _handler)


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


def _mutant_bytes(original: bytes, old: str, new: str) -> bytes:
    """Apply one replacement. Patterns use ``\\n``; a Windows tree may be CRLF.

    The match ignores the file's newline spelling. The bytes written back use
    that same spelling. The caller still restores ``original`` exactly.
    """
    text = original.decode("utf-8")
    crlf = b"\r\n" in original
    folded = text.replace("\r\n", "\n")
    old_n = old.replace("\r\n", "\n")
    new_n = new.replace("\r\n", "\n")
    if old_n not in folded:
        print("PATTERN MISSING", file=sys.stderr)
        raise SystemExit(2)
    mutated = folded.replace(old_n, new_n, 1)
    if crlf:
        mutated = mutated.replace("\n", "\r\n")
    return mutated.encode("utf-8")


def _python_syntax_error(path: Path) -> bool:
    """True when the mutated file is Python that does not compile."""
    if path.suffix != ".py":
        return False
    try:
        compile(path.read_bytes(), str(path), "exec")
    except SyntaxError:
        return True
    return False


def _restore_bytes(path: Path, original: bytes) -> None:
    """Write ``original`` back. Stop signals wait until the write finishes.

    ``PROVE_RED_RESTORE_DELAY`` (seconds) sleeps inside the blocked section.
    Tests use it to deliver a signal during the restore. Production runs
    leave it unset.
    """
    delay = os.environ.get("PROVE_RED_RESTORE_DELAY", "")
    block = sys.platform != "win32" and hasattr(signal, "pthread_sigmask")
    if block:
        signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGINT, signal.SIGTERM})
    try:
        if delay:
            try:
                time.sleep(float(delay))
            except ValueError:
                pass
        path.write_bytes(original)
    finally:
        if block:
            signal.pthread_sigmask(signal.SIG_UNBLOCK, {signal.SIGINT, signal.SIGTERM})


def _head_bytes(path: Path) -> bytes | None:
    """Committed bytes of ``path``, or None when git cannot show them."""
    proc = subprocess.run(
        ["git", "show", "HEAD:%s" % path.as_posix()],
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        return None
    return proc.stdout


def _exact_leftover(path: Path, old: str, new: str) -> bool:
    """True when the working tree is exactly one application of this mutant."""
    head = _head_bytes(path)
    if head is None:
        return False
    try:
        mutant = _mutant_bytes(head, old, new)
    except SystemExit:
        return False
    try:
        current = path.read_bytes()
    except OSError:
        return False
    return current == mutant


def _pytest(python: str, args: list[str]) -> int:
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        [python, "-m", "pytest", "-q", "-p", "no:cacheprovider", *args],
        env=env,
        check=False,
    )
    return proc.returncode


def _run_case(python: str, path: Path, old: str, new: str, args: list[str]) -> str:
    original = path.read_bytes()
    baseline = _pytest(python, args)
    if baseline != 0:
        return "SETUP-ERROR (baseline rc=%s)" % baseline
    result = "SETUP-ERROR (rc=?)"
    try:
        # Bytes, not write_text: write_text would turn ``\\n`` into CRLF again.
        path.write_bytes(_mutant_bytes(original, old, new))
        if _python_syntax_error(path):
            result = "INVALID"
        else:
            rc = _pytest(python, args)
            if rc == 1:
                result = "RED"
            elif rc == 0:
                result = "SURVIVED"
            else:
                result = "SETUP-ERROR (rc=%s)" % rc
    finally:
        _restore_bytes(path, original)
    return result


def _table(rows: list[tuple[str, str]]) -> str:
    name_w = max([len("name")] + [len(name) for name, _result in rows])
    lines = ["%s  %s" % ("name".ljust(name_w), "result")]
    for name, result in rows:
        lines.append("%s  %s" % (name.ljust(name_w), result))
    return "\n".join(lines) + "\n"


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prove a fix is RED when reverted.")
    parser.add_argument("cases", type=Path)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args(argv)
    if not args.cases.is_file():
        print("cases file not found", file=sys.stderr)
        return 2
    cases = _load_cases(args.cases)
    seen: list[Path] = []
    for _name, path, _old, _new, _pytest_args in cases:
        if path in seen:
            continue
        seen.append(path)
        if not path.is_file():
            print("target missing: %s" % path, file=sys.stderr)
            return 2
        if not _uncommitted(path):
            continue
        restored = False
        for _case_name, case_path, old, new, _case_args in cases:
            if case_path != path:
                continue
            if not _exact_leftover(path, old, new):
                continue
            head = _head_bytes(path)
            if head is None:
                break
            _restore_bytes(path, head)
            print(
                "restored leftover mutant in %s. SIGKILL leaves a mutant applied. "
                "Hand recovery: git restore --source=HEAD -- %s" % (path, path),
                file=sys.stderr,
            )
            restored = True
            break
        if _uncommitted(path):
            if restored:
                print("could not restore %s" % path, file=sys.stderr)
            else:
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
    if any(result == "INVALID" or result.startswith("SETUP-ERROR") for _name, result in rows):
        return 2
    if any(result == "SURVIVED" for _name, result in rows):
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    _install_stop_handlers()
    try:
        return _main(argv)
    except _Stopped as stopped:
        return stopped.code


if __name__ == "__main__":
    raise SystemExit(main())
