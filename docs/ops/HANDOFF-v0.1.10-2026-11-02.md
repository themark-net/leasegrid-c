# Handoff: v0.1.10 (`build/release-0.1.10`), 2026-11-02

Friends-and-family bump that ships the Android hardening for [#78](https://github.com/themark-net/leasegrid-c/issues/78) and [#80](https://github.com/themark-net/leasegrid-c/issues/80) (and [#84](https://github.com/themark-net/leasegrid-c/issues/84)). Same procedure as v0.1.9 ([`HANDOFF-v0.1.9-2026-10-29.md`](HANDOFF-v0.1.9-2026-10-29.md)): no PR, `main` fast-forwarded, annotated tag, Installers publishes the release on the tag with `docs/release-notes/v0.1.10.md` as the body.

- **Gate:** Tester PASS and Reviewer PASS at `e60390959362d5d049d71410f91219cc99f12a39` ([`HANDOFF-hardening-78-80-2026-11-02.md`](HANDOFF-hardening-78-80-2026-11-02.md)).
- **`main`:** fast-forwarded `7ce0785..e603909` (the hardening branch), then to this bump commit.
- **Decisions:** [`AUTONOMOUS-DECISIONS-2026-11-02.md`](AUTONOMOUS-DECISIONS-2026-11-02.md) (last row).

## What changed

- **Version 0.1.10:** `pyproject.toml` and `src/leasegrid_sync/__init__.py`. The Android `versionName` is unchanged (own scheme).
- **`CHANGELOG.md`:** `## 0.1.10 (2026-11-02)` with the #78 and #80 items, empty `## Unreleased` on top.
- **`docs/release-notes/v0.1.10.md`:** new, from the v0.1.9 notes. Previous build v0.1.9 at `7ce0785`. Names [#77](https://github.com/themark-net/leasegrid-c/issues/77) as not in this build and follow-ups [#85](https://github.com/themark-net/leasegrid-c/issues/85).
- **Tester pages** (`README.md`, `docs/TESTERS.md`, `docs/TESTER-GUIDE.md`): current build, asset names and About line say 0.1.10; "before it" links point at v0.1.9; the pinned v0.1.5 #30 correction stays.
- **Hardening handoff:** the mutant table intro now says the table is this branch's rebuilt mutants, and that Tester's own 75-mutant run at `e6039095` killed 66, with 9 survivors (E5, N4b, H78e, F4b, F4e, F4f, A5, C3, C4), tracked in #85.
- **No product logic changed.** The desktop app is the same as v0.1.9 apart from the version. No APK asset (no release has shipped one).

## Release

Tag, release URL, assets and CI run ids are reported on #78 and #80 when the Installers tag run finishes.
