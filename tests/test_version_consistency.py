"""pyproject.toml project.version must match leasegrid_sync.__version__."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _pyproject_version() -> str:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    if sys.version_info >= (3, 11):
        import tomllib

        data = tomllib.loads(text)
    else:
        tomli = pytest.importorskip("tomli")
        data = tomli.loads(text)
    return data["project"]["version"]


def test_pyproject_version_matches_leasegrid_sync():
    from leasegrid_sync import __version__

    assert _pyproject_version() == __version__
