"""prove-red.py restores the file and reports RED only when the test fails."""

from __future__ import annotations

import importlib.util
import os
import signal
import subprocess
import sys
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


def _cases(
    repo: Path,
    name: str,
    old: str,
    new: str,
    node: str = "test_mod.py",
    target: str = "mod.py",
    extra: list[str] | None = None,
) -> Path:
    path = repo / "cases.py"
    args = [node, *(extra or [])]
    path.write_text(
        "CASES = [(%r, %r, %r, %r, %r)]\n" % (name, target, old, new, args),
        encoding="utf-8",
    )
    return path


def _harness():
    """The prove-red module. Tests reuse its mutant spelling so they cannot drift."""
    spec = importlib.util.spec_from_file_location("prove_red_harness", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load prove-red")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def test_sigkill_and_invalid_are_documented() -> None:
    """The harness and AGENTS.md name the SIGKILL leftover and INVALID."""
    script = SCRIPT.read_text(encoding="utf-8")
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for text in (script, agents):
        assert "INVALID" in text
        assert "SIGKILL" in text
        assert "git restore --source=HEAD --" in text


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
    assert "SETUP-ERROR" not in proc.stdout


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


def test_crlf_leftover_mutant_is_restored(tmp_path: Path) -> None:
    """A SIGKILL leftover in a CRLF checkout is restored, not refused.

    Windows git stores LF and checks out CRLF. The harness writes the mutant
    with those CRLF bytes. ``git show`` is the LF blob. A raw compare misses
    the leftover, and writing the blob back leaves the checkout dirty.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.check_call(["git", "init", "-q", str(repo)], stdout=subprocess.DEVNULL)
    _git(repo, "config", "core.autocrlf", "true")
    target = repo / "mod.py"
    # Same bytes Windows write_text produces. A second commit of this text
    # would be empty: autocrlf already stored the LF form in the first commit.
    target.write_bytes(MODULE.replace("\n", "\r\n").encode("utf-8"))
    (repo / "test_mod.py").write_bytes(TEST.replace("\n", "\r\n").encode("utf-8"))
    _git(repo, "add", "mod.py", "test_mod.py")
    _git(repo, "commit", "-q", "-m", "crlf")
    original = target.read_bytes()
    assert b"return 1\r\n" in original
    mutant = _harness()._mutant_bytes(original, "return 1\n", "return 2\n")
    assert b"return 2\r\n" in mutant
    target.write_bytes(mutant)
    cases = _cases(repo, "caught-crlf-leftover", "return 1\n", "return 2\n")
    proc = _run(repo, cases)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "restored leftover mutant" in proc.stderr
    assert "RED" in proc.stdout
    assert target.read_bytes() == original


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


def test_typo_node_id_is_setup_error(tmp_path: Path) -> None:
    """A missing node id is a usage error on the clean tree, not a RED mutant."""
    repo = tmp_path / "repo"
    target = _init_repo(repo, MODULE, TEST)
    original = target.read_bytes()
    cases = _cases(repo, "typo", "return 1\n", "return 2\n", node="test_mod.py::test_answr")
    proc = _run(repo, cases)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "SETUP-ERROR (baseline rc=4)" in proc.stdout
    assert target.read_bytes() == original


def test_no_tests_collected_is_setup_error(tmp_path: Path) -> None:
    """``-k zzz`` collects nothing. That is a setup error, not RED."""
    repo = tmp_path / "repo"
    target = _init_repo(repo, MODULE, TEST)
    original = target.read_bytes()
    cases = _cases(repo, "none", "return 1\n", "return 2\n", extra=["-k", "zzz"])
    proc = _run(repo, cases)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "SETUP-ERROR (baseline rc=5)" in proc.stdout
    assert target.read_bytes() == original


def test_import_break_is_setup_error(tmp_path: Path) -> None:
    """A mutant that breaks importing the test module is a setup error, not RED."""
    repo = tmp_path / "repo"
    _init_repo(repo, MODULE, TEST)
    test_path = repo / "test_mod.py"
    original = test_path.read_bytes()
    cases = _cases(
        repo,
        "import-break",
        "import mod\n",
        "import mod_that_is_not_there\n",
        target="test_mod.py",
    )
    proc = _run(repo, cases)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "SETUP-ERROR (rc=2)" in proc.stdout
    assert "baseline" not in proc.stdout
    assert test_path.read_bytes() == original


def test_missing_fixture_is_setup_error(tmp_path: Path) -> None:
    """A test that cannot even start on the clean tree is a setup error."""
    repo = tmp_path / "repo"
    test_body = "import mod\n\ndef test_answer(does_not_exist):\n    assert mod.answer() == 1\n"
    target = _init_repo(repo, MODULE, test_body)
    original = target.read_bytes()
    cases = _cases(repo, "fixture", "return 1\n", "return 2\n")
    proc = _run(repo, cases)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "SETUP-ERROR (baseline rc=1)" in proc.stdout
    assert target.read_bytes() == original


def test_always_failing_baseline_is_setup_error(tmp_path: Path) -> None:
    """An already-failing test is not proof that the mutant was caught."""
    repo = tmp_path / "repo"
    test_body = "import mod\n\ndef test_answer():\n    assert False\n"
    target = _init_repo(repo, MODULE, test_body)
    original = target.read_bytes()
    cases = _cases(repo, "always-fail", "return 1\n", "return 2\n")
    proc = _run(repo, cases)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "SETUP-ERROR (baseline rc=1)" in proc.stdout
    assert target.read_bytes() == original


def test_syntax_error_mutant_is_invalid_not_a_kill(tmp_path: Path) -> None:
    """A syntax error is INVALID. It is not a kill, even when pytest would exit 1.

    The import sits inside the test, so collection succeeds and a SyntaxError
    during the test used to print RED and exit 0.
    """
    repo = tmp_path / "repo"
    test_body = "def test_answer():\n    import mod\n    assert mod.answer() == 1\n"
    target = _init_repo(repo, MODULE, test_body)
    original = target.read_bytes()
    cases = _cases(repo, "syntax", "return 1\n", "return (\n")
    proc = _run(repo, cases)
    assert target.read_bytes() == original
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "INVALID" in proc.stdout
    assert "RED" not in proc.stdout
    assert "SURVIVED" not in proc.stdout


def test_leftover_mutant_from_sigkill_is_restored(tmp_path: Path) -> None:
    """SIGKILL leaves the mutant. The next run restores that exact mutant and continues.

    A different uncommitted edit is still refused and left in place.
    """
    repo = tmp_path / "repo"
    target = _init_repo(repo, MODULE, TEST)
    original = target.read_bytes()
    target.write_bytes(_harness()._mutant_bytes(original, "return 1\n", "return 2\n"))
    cases = _cases(repo, "caught", "return 1\n", "return 2\n")
    proc = _run(repo, cases)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "restored leftover mutant" in proc.stderr
    assert "RED" in proc.stdout
    assert target.read_bytes() == original
    local = MODULE + "# local edit\n"
    target.write_text(local, encoding="utf-8")
    proc = _run(repo, cases)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "uncommitted" in proc.stderr
    assert target.read_text(encoding="utf-8") == local


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
    test_body = "import mod\n\ndef test_answer():\n    assert mod.answer() == 1\n"
    target = _init_repo(repo, module, test_body)
    original = target.read_bytes()
    # The clean test returns at once, so the baseline is green. The mutant is
    # what sleeps, which is the window where the file is dirty.
    cases = _cases(
        repo,
        "interrupt",
        "return 1\n",
        "import time\n    time.sleep(30)\n    return 1\n",
    )
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


@pytest.mark.skipif(
    sys.platform == "win32",
    reason=(
        "os.kill(SIGTERM) and os.kill(SIGINT) terminate without running the "
        "Python handler. CTRL_C_EVENT would hit this pytest process."
    ),
)
@pytest.mark.parametrize(
    ("sig", "code"),
    [(signal.SIGTERM, 143), (signal.SIGINT, 130)],
    ids=["SIGTERM", "SIGINT"],
)
def test_signal_restores_bytes_and_skips_the_receipt(
    tmp_path: Path, sig: int, code: int
) -> None:
    """A signal mid-run restores the target, writes no receipt, and exits non-zero."""
    repo = tmp_path / "repo"
    module = "def answer():\n    return 1\n"
    test_body = "import mod\n\ndef test_answer():\n    assert mod.answer() == 1\n"
    target = _init_repo(repo, module, test_body)
    original = target.read_bytes()
    marker = tmp_path / "marker"
    mutant = (
        "    import pathlib\n"
        "    import time\n"
        "    pathlib.Path(%r).write_text('up', encoding='utf-8')\n"
        "    time.sleep(30)\n"
        "    return 1\n" % str(marker)
    )
    cases = _cases(repo, "hold", "    return 1\n", mutant)
    receipt = repo / "receipt.txt"
    proc = subprocess.Popen(
        [sys.executable, str(SCRIPT), str(cases), "--receipt", str(receipt)],
        cwd=repo,
        start_new_session=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    pgid = os.getpgid(proc.pid)
    try:
        deadline = time.time() + 20
        while time.time() < deadline and not marker.is_file():
            if proc.poll() is not None:
                break
            time.sleep(0.05)
        assert marker.is_file(), "sleeper did not start rc %s" % proc.returncode
        os.kill(proc.pid, sig)
        try:
            # wait, not communicate: the sleeper still holds the stdout pipe.
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            pytest.fail("prove-red still alive after the signal")
    finally:
        if proc.poll() is None:
            os.killpg(pgid, signal.SIGKILL)
            proc.wait(timeout=5)
        else:
            try:
                os.killpg(pgid, signal.SIGKILL)
            except OSError:
                pass
    assert target.read_bytes() == original, "target left mutated"
    diff = subprocess.run(
        ["git", "-C", str(repo), "diff", "--quiet", "--", "mod.py"],
        check=False,
    )
    assert diff.returncode == 0
    assert not receipt.is_file()
    assert proc.returncode not in (0, None)
    assert proc.returncode == code, proc.returncode


@pytest.mark.skipif(
    sys.platform == "win32" or not hasattr(signal, "pthread_sigmask"),
    reason="POSIX signal mask is what holds SIGINT off during the restore write",
)
def test_signal_during_restore_still_restores(tmp_path: Path) -> None:
    """A SIGINT during the restore write still puts the original bytes back.

    The harness sleeps inside the masked section when PROVE_RED_RESTORE_DELAY
    is set. A second SIGINT in that window must not skip the write.
    """
    repo = tmp_path / "repo"
    module = "def answer():\n    return 1\n"
    test_body = "def test_answer():\n    import mod\n    assert mod.answer() == 1\n"
    target = _init_repo(repo, module, test_body)
    original = target.read_bytes()
    marker = tmp_path / "marker"
    mutant = (
        "    import pathlib\n"
        "    import time\n"
        "    pathlib.Path(%r).write_text('up', encoding='utf-8')\n"
        "    time.sleep(30)\n"
        "    return 1\n" % str(marker)
    )
    cases = _cases(repo, "hold", "    return 1\n", mutant)
    env = os.environ.copy()
    env["PROVE_RED_RESTORE_DELAY"] = "0.6"
    proc = subprocess.Popen(
        [sys.executable, str(SCRIPT), str(cases)],
        cwd=repo,
        env=env,
        start_new_session=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.time() + 20
        while time.time() < deadline and not marker.is_file():
            if proc.poll() is not None:
                break
            time.sleep(0.05)
        assert marker.is_file(), "sleeper did not start rc %s" % proc.returncode
        os.kill(proc.pid, signal.SIGINT)
        time.sleep(0.15)
        if proc.poll() is None:
            os.kill(proc.pid, signal.SIGINT)
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            pytest.fail("prove-red still alive after the restore signal")
    finally:
        if proc.poll() is None:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait(timeout=5)
    assert target.read_bytes() == original, "target left mutated"
    assert proc.returncode == 130, proc.returncode
