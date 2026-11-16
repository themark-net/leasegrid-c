# Handoff: v0.1.11 (`bot/86-xos-pytest`), 2026-11-16

Friends-and-family bump. The #86 cross-OS pytest fix is already on main; this commit is docs and the version only. No PR. Tag and release are not done yet (they wait for the Reviewer scoped re-gate). When that gate passes, the procedure follows v0.1.10 ([`HANDOFF-v0.1.10-2026-11-02.md`](HANDOFF-v0.1.10-2026-11-02.md)): `main` fast-forwarded, annotated tag, Installers publishes the release on the tag with `docs/release-notes/v0.1.11.md` as the body.

- **Gate:** Tester PASS at `6e8b64f` (comment 6926340223). Reviewer FAIL on B1 only (dashes) at that SHA. This pin fixes B1. Reviewer scoped re-gate is pending.
- **`main`:** fast-forward `d3b5c5c..6e8b64f..(this commit)`.
- **Decisions:** [`AUTONOMOUS-DECISIONS-2026-11-16.md`](AUTONOMOUS-DECISIONS-2026-11-16.md) (last two rows).

## What changed

- **Version 0.1.11:** `pyproject.toml` and `src/leasegrid_sync/__init__.py`. The Android `versionName` is unchanged (own scheme, `0.4.0-slice-b`).
- **`CHANGELOG.md`:** `## 0.1.11 (2026-11-16)` holds the items that were under `## Unreleased`, plus one #86 line. Empty `## Unreleased` on top.
- **`docs/release-notes/v0.1.11.md`:** new, from the v0.1.10 notes. Previous build v0.1.10 at `454befa`. What's new stays within the five-bullet shape those notes use; the changelog has every former Unreleased item. No APK asset (the Android app file is on hold).
- **Tester pages** (`README.md`, `docs/TESTERS.md`, `docs/TESTER-GUIDE.md`): current build, asset names and About line say 0.1.11; "before it" links point at v0.1.10; the pinned v0.1.5 #30 correction stays.
- **#86 docs:** Reviewer B1 dashes removed from [`ROOT-CAUSE-86-xos-pytest.md`](ROOT-CAUSE-86-xos-pytest.md). The #86 section of [`PENDING-HANDOFF.md`](../PENDING-HANDOFF.md) uses repo-relative paths and a generic venv.
- **No product logic changed** in this bump. No APK asset.

## Release

Tag, release URL, assets and CI run ids are not done in this commit. They wait for the Reviewer scoped re-gate.
