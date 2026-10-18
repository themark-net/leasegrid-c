"""prove-red.py restores the file and reports RED only when the test fails."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "prove-red.py"


def _git(repo: Path, *args: str) -> None:
    subprocess.check_call(
        ["git", "-C", str(repo), "-c", "user.email=prove-red@example.com", "-c", "user.name=prove-red", *args],
        stdout=subprocess.DEVNULL,
    )


def _init_repo(repo: Path, module: str, test_body: str) -> Path:
    repo.mkdir()
    subprocess.check_call(["git", "init", "-q", str(repo)], stdout=subprocess.DEVNULL)
    (repo / "mod.py").write_text(module, encoding="utf-8")
    (repo / "test_mod.py").write_text(test_body, encoding="utf-8")
    _git(repo, "add", "mod.py", "test_mod.py")
    _git(repo, "commit", "-q", "-m", "init")
    return repo / "mod.py"


def _cases(repo: Path, name: str, old: str, new: str, node: str = "test_mod.py") -> Path:
    path = repo / "cases.py"
    path.write_text(
        "CASES = [(%r, %r, %r, %r, [%r])]\n" % (name, "mod.py", old, new, node),
        encoding="utf-8",
    )
    return path


def _run(repo: Path, cases: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(cases)],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )


MODULE = "def answer():\n    return 1\n"
TEST = "import mod\n\ndef test_answer():\n    assert mod.answer() == 1\n"


def test_caught_mutant_is_red_and_restores(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    target = _init_repo(repo, MODULE, TEST)
    original = target.read_bytes()
    cases = _cases(repo, "caught", "return 1\n", "return 2\n")
    proc = _run(repo, cases)
    assert target.read_bytes() == original
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "RED" in proc.stdout
    assert "SURVIVED" not in proc.stdout


def test_crlf_working_tree_matches_lf_pattern(tmp_path: Path) -> None:
    """A CRLF checkout still matches a pattern written with ``\\n``, then restores."""
    repo = tmp_path / "repo"
    target = _init_repo(repo, MODULE, TEST)
    _git(repo, "config", "core.autocrlf", "false")
    target.write_bytes(MODULE.replace("\n", "\r\n").encode("utf-8"))
    _git(repo, "add", "mod.py")
    _git(repo, "commit", "-q", "-m", "crlf")
    original = target.read_bytes()
    assert b"return 1\r\n" in original
    cases = _cases(repo, "caught-crlf", "return 1\n", "return 2\n")
    proc = _run(repo, cases)
    assert target.read_bytes() == original
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "RED" in proc.stdout
    assert "SURVIVED" not in proc.stdout


def test_surviving_mutant_exits_1(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    target = _init_repo(repo, MODULE, TEST)
    original = target.read_bytes()
    cases = _cases(repo, "survivor", "return 1\n", "return (1)\n")
    proc = _run(repo, cases)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "SURVIVED" in proc.stdout
    assert target.read_bytes() == original


def test_missing_pattern_exits_2(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    target = _init_repo(repo, MODULE, TEST)
    original = target.read_bytes()
    cases = _cases(repo, "missing", "return 99\n", "return 2\n")
    proc = _run(repo, cases)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "PATTERN MISSING" in proc.stderr
    assert target.read_bytes() == original


def test_dirty_target_exits_2_and_is_unchanged(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    target = _init_repo(repo, MODULE, TEST)
    dirty = MODULE + "# local edit\n"
    target.write_text(dirty, encoding="utf-8")
    cases = _cases(repo, "dirty", "return 1\n", "return 2\n")
    proc = _run(repo, cases)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "uncommitted" in proc.stderr
    assert target.read_text(encoding="utf-8") == dirty


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="SIGINT to a new session is not the Windows console control event",
)
def test_sigint_restores_the_file(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    module = "def answer():\n    return 1\n"
    test_body = textwrap.dedent(
        """\
        import time
        import mod

        def test_answer():
            time.sleep(30)
            assert mod.answer() == 1
        """
    )
    target = _init_repo(repo, module, test_body)
    original = target.read_bytes()
    cases = _cases(repo, "interrupt", "return 1\n", "return 2\n")
    proc = subprocess.Popen(
        [sys.executable, str(SCRIPT), str(cases)],
        cwd=repo,
        start_new_session=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.time() + 15
        while time.time() < deadline:
            if target.read_bytes() != original:
                break
            if proc.poll() is not None:
                break
            time.sleep(0.05)
        assert target.read_bytes() != original, "mutant was not applied before SIGINT"
        os.killpg(proc.pid, signal.SIGINT)
        proc.wait(timeout=15)
    finally:
        if proc.poll() is None:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait(timeout=5)
    assert target.read_bytes() == original
