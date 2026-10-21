# Handoff: v0.1.8 (`build/release-0.1.8`), 2026-10-20 (released 2026-10-21)

Tracks [#76](https://github.com/themark-net/leasegrid-c/issues/76). This is a friends-and-family bump that ships the two `## Unreleased` fixes from #75, which merged at `7e73a64` after v0.1.7 was tagged on `78a691a`.

- **Branch:** `build/release-0.1.8` off `origin/main` @ `7e73a64`.
- **No-PR flow.** This replaces #76 step 4 (open a PR), per Grok Bot's 2026-10-20 instruction.
  - The branch was pushed and CI ran on its `cursor/release-0.1.8` twin.
  - Tester and Reviewer both PASSed at `14027d3`.
  - PM authorized shipping under Mark's standing friends-and-family rule.
  - `main` was then fast-forwarded to `14027d3` with no merge commit.
- **Decisions:** [`AUTONOMOUS-DECISIONS-2026-10-20.md`](AUTONOMOUS-DECISIONS-2026-10-20.md).

## What changed

- **Version 0.1.8:** `pyproject.toml` and `src/leasegrid_sync/__init__.py`. The Android `versionName` is unchanged; it uses its own scheme.
- **`CHANGELOG.md`:** the Unreleased items move under `## 0.1.8 (2026-10-20)`, with an empty `## Unreleased` left on top.
- **`docs/release-notes/v0.1.8.md`:** new, from TEMPLATE.
  - Two What's new bullets (#75, `7e73a64`), plus "same as v0.1.7".
  - Previous build: v0.1.7 at `78a691a`.
  - The Installers workflow reads it via `body_path` on the `v0.1.8` tag.
- **Tester pages** (`README.md`, `docs/TESTERS.md`, `docs/TESTER-GUIDE.md`):
  - current build and asset names now say 0.1.8;
  - the "before it" links point at the v0.1.7 notes;
  - "What's new in v0.1.8" has the two fixes in plain words, and keeps the pinned v0.1.5 #30 correction.
- **`tests/test_release_notes.py`:** two tests assumed the v0.1.7 notes were current. The rotation-wording test now pins the v0.1.7 notes and the guide. The sixth-bullet test pads to exactly six bullets. Both still go red on the wrong wording.
- **No product logic changed.**

## Release (2026-10-21)

1. **Double PASS at `14027d3`.** The Tester ran both behaviors on a real build:
   - with a second invite handed to a running app, the newest one wins;
   - on Linux and macOS, Ctrl-C, SIGTERM or SIGHUP on the "already running" box exits 0. Windows does not install this handler (`app.py` `_arm_already_running_signal_quit`).
2. **`main` fast-forwarded** `7e73a64..14027d3`. Normal push, no PR and no merge commit.
3. **Annotated tag `v0.1.8`,** message "Leasegrid v0.1.8 (friends and family)":
   - tag object `032c5627ff11988b8d86f11fdf9d8b3e1a56c9cc`
   - commit `14027d32ace7bc0799ed88e228b2de42b9cb4787`
4. **Release:** [Leasegrid Sync v0.1.8 on GitHub Releases](https://github.com/themark-net/leasegrid-c/releases/tag/v0.1.8), published 2026-10-21 09:11 PT. Not a draft or a prerelease, and `releases/latest` points at it.
   - **Body:** one body, byte-identical to `docs/release-notes/v0.1.8.md`. No auto-generated notes were appended.
   - **Assets:** 7, the same set as v0.1.7:
     - `Leasegrid_Sync-0.1.8-x86_64.AppImage`
     - `Leasegrid_Sync-0.1.8-macos-x86_64.dmg`
     - `Leasegrid_Sync-0.1.8-win64-setup.exe`
     - `Leasegrid_Sync-0.1.8-win64.zip`
     - `SHA256SUMS-linux-x86_64`, `SHA256SUMS-macos-x86_64` and `SHA256SUMS-win64`
   - **AppImage SHA-256:** `b7e5ab27f52c8fbc8ea0d1cebc383103c8e5103dee58121f7131bc295661be36`. `sha256sum -c SHA256SUMS-linux-x86_64` passes on the downloaded file.
   - **Earlier releases:** v0.1.0 through v0.1.7 are still published, and none are drafts.
   - **Links:** every current-build link in `README.md`, `docs/TESTERS.md` and `docs/TESTER-GUIDE.md` returns 200. That covers the 4 asset downloads, `releases/tag/v0.1.8`, `releases/latest`, and the v0.1.8 and v0.1.7 notes.
5. **Not done:** no marketing and no tester blast.

## CI

Release SHA `14027d3`. All runs are attempt 1, with no reruns:

| Workflow | Run | Event | Result |
|---|---|---|---|
| CI | [39459067594](https://github.com/themark-net/leasegrid-c/actions/runs/39459067594) | push `cursor/release-0.1.8` | success: `test` on ubuntu, windows and macos, plus `semgrep` |
| Android Slice A | [39459067622](https://github.com/themark-net/leasegrid-c/actions/runs/39459067622) | push `cursor/release-0.1.8` | success: `debug APK` |
| Installers | [39459098907](https://github.com/themark-net/leasegrid-c/actions/runs/39459098907) | workflow_dispatch `cursor/release-0.1.8` | success: linux, windows, macos |
| Installers (tag) | [39632073534](https://github.com/themark-net/leasegrid-c/actions/runs/39632073534) | push tag `v0.1.8` | success: built and published the release |
| CI (`main`) | [39632050280](https://github.com/themark-net/leasegrid-c/actions/runs/39632050280) | push `main` | success |
| Android Slice A (`main`) | [39632050282](https://github.com/themark-net/leasegrid-c/actions/runs/39632050282) | push `main` | success |
| Installers (`main`) | [39632050369](https://github.com/themark-net/leasegrid-c/actions/runs/39632050369) | push `main` | success |

The first commit, `011fc2f`, was green too: CI 39455995814, Android 39455995648, Installers 39456514212.

- **Installers on the branch was dispatched by hand.** Its `paths:` filter skipped the new-branch push. On a branch, the publish steps run only on `refs/tags/v*`.
- **`build/**` triggers no workflow,** so CI ran on the `cursor/release-0.1.8` twin at the same SHA.

### Test counts (606 vs 594)

- **Local CI** (`scripts/ci-local.sh`, Linux) at `011fc2f` and at `14027d3`: 606 passed, 5 xfailed.
- **GitHub CI at `14027d3`:**
  - ubuntu: 606 passed, 5 xfailed
  - macos: 605 passed, 1 skipped, 5 xfailed
  - windows: 571 passed, 35 skipped, 5 xfailed

  On these CI runners, the skips are platform-only tests, such as POSIX signals and process groups. That holds only for the CI runners; elsewhere, missing dependencies also cause skips (next bullet).
- **Where 594 comes from:** #75's own handoff (`HANDOFF-dev-safety-rails.md`) and its run log, at #75's intermediate commit `a80979c`. #75's fix2 round then added tests (`RUN-LOG-dev-safety-rails-fix2.md`: 606), and #75 was squash-merged as `7e73a64` with 606.
- **The Reviewer gates measured 594 too.** At `011fc2f` and `14027d3` the gate environments had 594 passed, 12 skipped, 5 xfailed. The 12 skips are environment import-skips, because Tahoe and Magic Folder were not installed: 1 Tahoe, 7 `magic_folder`, 4 `allmydata`. 594 + 12 = 606.
- **v0.1.8 added no tests.** It edited two tests in `tests/test_release_notes.py`; that file has 3 `test_` functions before and after, and `pytest --collect-only` gives 611 at both `7e73a64` and `14027d3`. So 594 is the same suite with those 12 tests skipped. It is not a different test count for v0.1.8.

## Reviewer B1 follow-up (docs only)

- **Fix (b):** the signal exit-0 path is Linux and macOS only. `_arm_already_running_signal_quit` returns early on `win32`. The pages, notes and CHANGELOG now say "On Linux and macOS", and "instead of crashing" now reads "instead of being killed by the signal".
- **CHANGELOG fix (a):** it now says what changed: re-handing the invite already in the Join field drops an older pending replacement, and a replacement still needs Yes and then **Join friendnet**.
