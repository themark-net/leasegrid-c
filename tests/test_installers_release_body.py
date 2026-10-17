"""Only the Linux tag job may ask GitHub to generate release notes.

Parses `.github/workflows/installers.yml` as text so the test runs when PyYAML
is absent (CI installs `.[dev]` / `.[sync]` / `.[tahoe]`, not PyYAML). When
PyYAML imports, its view of the same file must agree.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows" / "installers.yml"
NOTES_TAG = "v0.1.2"
MISSING_TAG = "v9.9.9-test"

_JOB_HEADER = re.compile(r"^  (linux|macos|windows):\s*$", re.M)

_ASSETS = {
    "linux": ("Leasegrid_Sync-9.9.9-x86_64.AppImage",),
    "macos": ("Leasegrid_Sync-9.9.9-macos-x86_64.dmg",),
    "windows": (
        "Leasegrid_Sync-9.9.9-win64.zip",
        "Leasegrid_Sync-9.9.9-win64-setup.exe",
    ),
}
_SUMS = {
    "linux": "SHA256SUMS-linux-x86_64",
    "macos": "SHA256SUMS-macos-x86_64",
    "windows": "SHA256SUMS-win64",
}

_needs_bash = pytest.mark.skipif(
    sys.platform == "win32" or shutil.which("bash") is None,
    reason="relnotes steps run under bash; Windows bash on PATH may be unsuitable",
)


def _job_sections(text: str) -> dict[str, str]:
    matches = list(_JOB_HEADER.finditer(text))
    names = [match.group(1) for match in matches]
    assert names == ["linux", "macos", "windows"], names
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[match.group(1)] = text[match.end() : end]
    return sections


def _attach_block(section: str) -> str:
    parts = section.split("      - name: Attach to release\n", 1)
    assert len(parts) == 2, "missing Attach to release step"
    rest = parts[1]
    nxt = rest.find("\n      - ")
    return rest if nxt == -1 else rest[:nxt]


def _attach_generate(section: str) -> str:
    lines = [
        line.strip()
        for line in _attach_block(section).splitlines()
        if line.strip().startswith("generate_release_notes:")
    ]
    assert len(lines) == 1, lines
    return lines[0].split(":", 1)[1].strip()


def _relnotes_script(section: str) -> str:
    marker = "        id: relnotes\n"
    start = section.find(marker)
    assert start != -1, "missing relnotes step"
    rest = section[start + len(marker) :]
    run_header = "        run: |\n"
    run_at = rest.find(run_header)
    assert run_at != -1, "relnotes step has no run block"
    body = rest[run_at + len(run_header) :]
    lines: list[str] = []
    for line in body.split("\n"):
        if line.startswith("          "):
            lines.append(line[10:])
        elif line.strip() == "" and lines:
            lines.append("")
        else:
            break
    script = "\n".join(lines)
    if script and not script.endswith("\n"):
        script += "\n"
    assert script.startswith("set -euo pipefail\n"), script
    return script


def _flags_from_text(text: str) -> dict[str, str]:
    return {name: _attach_generate(section) for name, section in _job_sections(text).items()}


def _scripts_from_text(text: str) -> dict[str, str]:
    return {name: _relnotes_script(section) for name, section in _job_sections(text).items()}


def _agree_with_pyyaml(text: str, flags: dict[str, str], scripts: dict[str, str]) -> None:
    try:
        import yaml
    except ImportError:
        return
    data = yaml.safe_load(text)
    yaml_flags: dict[str, str] = {}
    yaml_scripts: dict[str, str] = {}
    for name, job in data["jobs"].items():
        for step in job["steps"]:
            if step.get("id") == "relnotes":
                yaml_scripts[name] = step["run"]
            uses = str(step.get("uses") or "")
            if uses.startswith("softprops/action-gh-release"):
                value = step["with"]["generate_release_notes"]
                if value is False:
                    yaml_flags[name] = "false"
                elif value is True:
                    yaml_flags[name] = "true"
                else:
                    yaml_flags[name] = str(value)
                assert step["with"]["body_path"] == "${{ steps.relnotes.outputs.path }}"
    assert yaml_flags == flags
    assert yaml_scripts.keys() == scripts.keys()
    for name in scripts:
        assert yaml_scripts[name].strip() == scripts[name].strip()


def _workflow() -> tuple[dict[str, str], dict[str, str]]:
    text = WORKFLOW.read_text(encoding="utf-8")
    flags = _flags_from_text(text)
    scripts = _scripts_from_text(text)
    _agree_with_pyyaml(text, flags, scripts)
    return flags, scripts


def _hash_path_prefix(bin_dir: Path) -> str | None:
    """Shim the hash tool this host lacks. The workflow files stay as written."""
    have_sum = shutil.which("sha256sum") is not None
    have_shasum = shutil.which("shasum") is not None
    if have_sum and have_shasum:
        return None
    if not have_sum and not have_shasum:
        pytest.fail("need sha256sum or shasum to run the relnotes scripts")
    bin_dir.mkdir(parents=True)
    if not have_shasum:
        shim = bin_dir / "shasum"
        shim.write_text(
            "#!/bin/sh\n"
            'if [ "$1" = "-a" ]; then shift 2; fi\n'
            'exec sha256sum "$@"\n',
            encoding="utf-8",
        )
        shim.chmod(0o755)
    if not have_sum:
        shim = bin_dir / "sha256sum"
        shim.write_text(
            "#!/bin/sh\nexec shasum -a 256 \"$@\"\n",
            encoding="utf-8",
        )
        shim.chmod(0o755)
    return str(bin_dir)


def _parse_output(path: Path) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        key, value = line.split("=", 1)
        parsed[key] = value
    return parsed


def _run_relnotes(script: str, tag: str, work: Path, notes: str | None) -> tuple[dict[str, str], Path]:
    repo = work / "repo"
    dist = repo / "dist"
    dist.mkdir(parents=True)
    for names in _ASSETS.values():
        for name in names:
            (dist / name).write_bytes(b"fake-installer\n")
    if notes is not None:
        dest = repo / "docs" / "release-notes" / ("%s.md" % tag)
        dest.parent.mkdir(parents=True)
        dest.write_text(notes, encoding="utf-8")
    runner = work / "runner"
    runner.mkdir()
    github_output = work / "github_output.txt"
    script_path = work / "relnotes.sh"
    script_path.write_text(script, encoding="utf-8")
    env = os.environ.copy()
    env["RUNNER_TEMP"] = str(runner)
    env["GITHUB_OUTPUT"] = str(github_output)
    env["GITHUB_REF_NAME"] = tag
    prefix = _hash_path_prefix(work / "bin")
    if prefix:
        env["PATH"] = prefix + os.pathsep + env.get("PATH", "")
    proc = subprocess.run(
        ["bash", str(script_path)],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    return _parse_output(github_output), dist


def _assert_sums(job: str, dist: Path) -> None:
    text = (dist / _SUMS[job]).read_text(encoding="utf-8")
    assert text.strip()
    for name in _ASSETS[job]:
        assert name in text


def test_only_linux_attach_generates_release_notes():
    text = WORKFLOW.read_text(encoding="utf-8")
    sections = _job_sections(text)
    for section in sections.values():
        assert "body_path: ${{ steps.relnotes.outputs.path }}" in _attach_block(section)
    flags, _scripts = _workflow()
    assert flags == {
        "linux": "${{ steps.relnotes.outputs.generate == 'true' }}",
        "macos": "false",
        "windows": "false",
    }
    assert text.count("generate == 'true'") == 1


@_needs_bash
def test_relnotes_with_notes_file_copies_body_and_does_not_generate(tmp_path: Path):
    notes = (ROOT / "docs" / "release-notes" / ("%s.md" % NOTES_TAG)).read_text(encoding="utf-8")
    _flags, scripts = _workflow()
    for job, script in scripts.items():
        parsed, dist = _run_relnotes(script, NOTES_TAG, tmp_path / job, notes)
        assert parsed["generate"] == "false"
        assert Path(parsed["path"]).read_text(encoding="utf-8") == notes
        _assert_sums(job, dist)


@_needs_bash
def test_relnotes_without_notes_file_only_linux_generates(tmp_path: Path):
    _flags, scripts = _workflow()
    for job, script in scripts.items():
        parsed, dist = _run_relnotes(script, MISSING_TAG, tmp_path / job, None)
        if job == "linux":
            assert parsed["generate"] == "true"
            body = Path(parsed["path"]).read_text(encoding="utf-8")
            assert body == "Release %s\n\n" % MISSING_TAG
        else:
            assert parsed["generate"] == "false"
            assert parsed["path"] == ""
        _assert_sums(job, dist)
