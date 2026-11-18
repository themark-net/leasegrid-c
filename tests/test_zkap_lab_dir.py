"""Lab secrets default under LEASEGRID_LAB_DIR, not a developer checkout layout.

Runs the real `leasegrid-zkap keygen` in a fresh HOME, so the defaults are
read at import time the way an operator's shell would see them.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _keygen(home: Path, lab_dir: str | None) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("LEASEGRID_")}
    env.update(HOME=str(home), USERPROFILE=str(home), PYTHONPATH=str(ROOT / "src"))
    if lab_dir is not None:
        env["LEASEGRID_LAB_DIR"] = lab_dir
    return subprocess.run(
        [sys.executable, "-m", "leasegrid_zkap.cli", "keygen"],
        cwd=home,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_keygen_writes_under_leasegrid_lab_dir(tmp_path: Path) -> None:
    lab = tmp_path / "secrets"
    lab.mkdir()
    proc = _keygen(tmp_path, str(lab))
    assert proc.returncode == 0, proc.stderr
    assert (lab / "issuer.signing.key").is_file()
    assert not (tmp_path / "DEVELOP").exists()


def test_keygen_default_is_a_home_dir_not_a_checkout_layout(tmp_path: Path) -> None:
    (tmp_path / "leasegrid-lab-private").mkdir()
    proc = _keygen(tmp_path, None)
    assert proc.returncode == 0, proc.stderr
    assert (tmp_path / "leasegrid-lab-private" / "issuer.signing.key").is_file()
    assert not (tmp_path / "DEVELOP").exists()


def test_lab_dir_tilde_expands(tmp_path: Path) -> None:
    (tmp_path / "labkeys").mkdir()
    proc = _keygen(tmp_path, "~/labkeys")
    assert proc.returncode == 0, proc.stderr
    assert (tmp_path / "labkeys" / "issuer.signing.key").is_file()
