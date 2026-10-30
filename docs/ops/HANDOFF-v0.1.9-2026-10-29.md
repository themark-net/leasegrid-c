# Handoff: v0.1.9 (`build/release-0.1.9`), 2026-10-29

Friends-and-family bump that ships [#50](https://github.com/themark-net/leasegrid-c/issues/50) option 1 (Android Invite asks for the desktop join link). Same procedure as v0.1.8 ([`HANDOFF-v0.1.8-2026-10-20.md`](HANDOFF-v0.1.8-2026-10-20.md)): no PR, `main` fast-forwarded, annotated tag, Installers publishes the release on the tag with `docs/release-notes/v0.1.9.md` as the body.

- **Gate:** Tester PASS ([comment 6516486459](https://github.com/themark-net/leasegrid-c/issues/50#issuecomment-6516486459)) and Reviewer PASS at `b79d89744ee0442cb7ff526bebdcc591dbda91c8`.
- **`main`:** fast-forwarded `15af439..b79d897` (the #50 commit), then to this bump commit.
- **Decisions:** [`AUTONOMOUS-DECISIONS-2026-10-29.md`](AUTONOMOUS-DECISIONS-2026-10-29.md) (last row).

## What changed

- **Version 0.1.9:** `pyproject.toml` and `src/leasegrid_sync/__init__.py`. The Android `versionName` is unchanged (own scheme).
- **`CHANGELOG.md`:** `## 0.1.9 (2026-10-29)` with the #50 items, empty `## Unreleased` on top.
- **`docs/release-notes/v0.1.9.md`:** new, from TEMPLATE. Previous build v0.1.8 at `14027d3`. Names option 2 ([#77](https://github.com/themark-net/leasegrid-c/issues/77)) as not in this build and follow-ups [#78](https://github.com/themark-net/leasegrid-c/issues/78) and [#80](https://github.com/themark-net/leasegrid-c/issues/80).
- **Tester pages** (`README.md`, `docs/TESTERS.md`, `docs/TESTER-GUIDE.md`): current build, asset names and About line say 0.1.9; "before it" links point at v0.1.8; the pinned v0.1.5 #30 correction stays.
- **No product logic changed.** The desktop app is the same as v0.1.8 apart from the version. No APK asset (no release has shipped one).

## Release

Tag, release URL, assets and CI run ids are reported on #50 when the Installers tag run finishes.
