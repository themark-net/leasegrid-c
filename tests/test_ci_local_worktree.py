"""ci-local must not retarget a shared venv when run from a linked worktree.

The script is executed under bash. A DEBUG trap refuses `pip install` so a
reverted script cannot point a shared interpreter at the temp tree.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "ci-local.sh"
SHARED_PYTHON = "/home/mark/tahoe-venv/bin/python"

# ci-local.sh is a POSIX dev script. On Windows, bash on PATH may be WSL.
pytestmark = pytest.mark.skipif(
    sys.platform == "win32" or shutil.which("bash") is None,
    reason="ci-local.sh runs under POSIX bash; Windows bash on PATH may be WSL",
)


def _git(repo: Path, *args: str) -> None:
    subprocess.check_call(
        ["git", "-C", str(repo), "-c", "user.email=ci-local@example.com", "-c", "user.name=ci-local", *args],
        stdout=subprocess.DEVNULL,
    )


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True)
    subprocess.check_call(["git", "init", "-q", str(path)], stdout=subprocess.DEVNULL)
    _git(path, "commit", "--allow-empty", "-q", "-m", "init")


def _safety_env(tmp: Path, extra: dict[str, str] | None = None) -> dict[str, str]:
    """Block pip install. The choice is printed; packages must not be installed."""
    trap = tmp / "block-pip.sh"
    trap.write_text(
        "trap 'case \"$BASH_COMMAND\" in\n"
        "  *pip\\ install*) echo \"BLOCKED:$BASH_COMMAND\"; exit 99;;\n"
        "esac' DEBUG\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env.pop("PYTHON", None)
    env["BASH_ENV"] = str(trap)
    env["CI_LOCAL_PRINT_PYTHON"] = "1"
    if extra:
        env.update(extra)
    return env


def _run(script_dir: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(script_dir / "scripts" / "ci-local.sh")],
        cwd=script_dir,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=60,
    )


def _install_script(dest: Path) -> None:
    scripts = dest / "scripts"
    scripts.mkdir(exist_ok=True)
    (scripts / "ci-local.sh").write_text(SCRIPT.read_text(encoding="utf-8"), encoding="utf-8")


def test_linked_worktree_uses_its_own_venv(tmp_path: Path) -> None:
    """Unset PYTHON in a linked worktree selects that tree's .venv, never the shared one."""
    base = tmp_path / "repo"
    _init_repo(base)
    wt = tmp_path / "wt"
    _git(base, "worktree", "add", "--detach", str(wt), "HEAD")
    _install_script(wt)
    env = _safety_env(tmp_path)
    proc = _run(wt, env)
    chosen = proc.stdout.strip()
    # Do not Path.resolve() the interpreter: a venv python is a symlink.
    expected = str(wt / ".venv" / "bin" / "python")
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert chosen == expected
    assert "tahoe-venv" not in proc.stdout
    assert "tahoe-venv" not in proc.stderr
    assert Path(chosen).is_file()


def test_explicit_python_is_honored_in_a_worktree(tmp_path: Path) -> None:
    base = tmp_path / "repo"
    _init_repo(base)
    wt = tmp_path / "wt"
    _git(base, "worktree", "add", "--detach", str(wt), "HEAD")
    _install_script(wt)
    explicit = "/tmp/explicit-not-installed"
    proc = _run(wt, _safety_env(tmp_path, {"PYTHON": explicit}))
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert proc.stdout.strip() == explicit
    assert not (wt / ".venv").exists()


def test_main_checkout_still_prefers_shared_venv(tmp_path: Path) -> None:
    """A normal git dir (not a linked worktree) keeps the previous choice."""
    repo = tmp_path / "checkout"
    _init_repo(repo)
    _install_script(repo)
    proc = _run(repo, _safety_env(tmp_path))
    assert proc.returncode == 0, proc.stderr + proc.stdout
    if os.access(SHARED_PYTHON, os.X_OK):
        assert proc.stdout.strip() == SHARED_PYTHON
        assert not (repo / ".venv").exists()
    else:
        assert proc.stdout.strip() == "python3"
