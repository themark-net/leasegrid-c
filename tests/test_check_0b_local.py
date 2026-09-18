"""Local gate 0b harness (may skip Tahoe wrap if allmydata missing)."""

import pytest

from leasegrid_zkap.check_0b import run_local


def test_check_0b_local_prints_gate_line(capsys):
    # Full PASS needs Tahoe StorageServer; without it 0b.2 fails honestly.
    # CI asserts the harness runs and reports per-step lines, not live grid PASS.
    code = run_local()
    out = capsys.readouterr().out
    assert "0b.1" in out
    assert "0b.3" in out or "FAIL" in out or "PASS" in out
    # If Tahoe present, expect overall PASS (exit 0); else allow non-zero.
    try:
        import allmydata  # noqa: F401

        assert code == 0, out
        assert "GATE 0b: PASS" in out
    except ImportError:
        pytest.skip("Tahoe not installed in this environment; unit suite still covers R/spent/issuer")
