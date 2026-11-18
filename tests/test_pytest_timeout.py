"""A hung test must fail on its own timer, not run until the CI job limit (#90)."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

if not os.environ.get("CI"):
    # CI installs .[dev], which carries pytest-timeout. A local venv may not.
    pytest.importorskip("pytest_timeout")


def _ini_timeout() -> float:
    try:
        import tomllib
    except ModuleNotFoundError:  # Python < 3.11
        import tomli as tomllib
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return float(data["tool"]["pytest"]["ini_options"]["timeout"])


def test_suite_has_a_per_test_timeout_well_under_the_job_limit() -> None:
    # The CI test job stops at 30 minutes; one test must not use most of it.
    assert 0 < _ini_timeout() <= 300


def test_a_hung_test_fails_fast_with_a_timeout(tmp_path: Path) -> None:
    hung = tmp_path / "test_hung.py"
    hung.write_text("import time\n\ndef test_hangs():\n    time.sleep(60)\n", encoding="utf-8")
    started = time.monotonic()
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-o", "timeout=3", str(hung)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    took = time.monotonic() - started
    out = proc.stdout + proc.stderr
    assert proc.returncode != 0, out
    assert "Timeout" in out, out
    assert took < 60, "hung test ran %.0fs" % took
