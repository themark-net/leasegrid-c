# Handoff — v0.1.8 (`build/release-0.1.8`), 2026-10-20

Tracks [#76](https://github.com/themark-net/leasegrid-c/issues/76). This is a friends-and-family bump that ships the two `## Unreleased` fixes from #75, which merged at `7e73a64` after v0.1.7 was tagged on `78a691a`.

- **Branch:** `build/release-0.1.8` off `origin/main` @ `7e73a64`.
- **Pushed only.** There is no PR, tag or merge yet, per Grok Bot's 2026-10-20 instruction, which overrides #76 step 4.
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

## Not done yet (each needs the PR first)

1. Open the PR from `build/release-0.1.8` to `main`.
2. Get a Tester + Reviewer double PASS. The Tester runs both behaviors on a real build:
   - with a second invite handed to a running app, the newest one wins;
   - on Linux and macOS, Ctrl-C, SIGTERM or SIGHUP on the "already running" box exits 0. Windows does not install this handler (`app.py` `_arm_already_running_signal_quit`).
3. Merge.
4. Push an annotated tag `v0.1.8` on the merged main SHA.
5. Check the release: a single body from `docs/release-notes/v0.1.8.md`, and 7 assets, the same set as v0.1.7, including the `SHA256SUMS-*` files. v0.1.0 through v0.1.7 must still be listed.
6. Record the release SHA, the tag and the AppImage SHA-256 here.

## CI

At `011fc2f`, all 8 jobs were green, pushed as `cursor/release-0.1.8`:

| Workflow | Run | Event | Jobs |
|---|---|---|---|
| CI | [39455995814](https://github.com/themark-net/leasegrid-c/actions/runs/39455995814) | push | 4/4: `test` on ubuntu, windows and macos, plus `semgrep` |
| Android Slice A | [39455995648](https://github.com/themark-net/leasegrid-c/actions/runs/39455995648) | push | 1/1: `debug APK` |
| Installers | [39456514212](https://github.com/themark-net/leasegrid-c/actions/runs/39456514212) | workflow_dispatch | 3/3: linux, windows, macos |

- **Installers was dispatched by hand.** Its `paths:` filter skipped the new-branch push. On a branch dispatch, the release-publish steps run only on `refs/tags/v*`, so nothing was published.
- **`build/**` triggers nothing.** It matches no workflow trigger, so CI runs on the matching `cursor/release-0.1.8` branch.
- **Local CI** (`scripts/ci-local.sh`): 606 passed, 5 xfailed, all checks passed.
- **Later commit.** The run report for the docs-only follow-up commit (Reviewer B1) has its CI run IDs.

## Reviewer B1 follow-up (docs only)

- **Fix (b):** the signal exit-0 path is Linux and macOS only. `_arm_already_running_signal_quit` returns early on `win32`. The pages, notes and CHANGELOG now say "On Linux and macOS", and "instead of crashing" now reads "instead of being killed by the signal".
- **CHANGELOG fix (a):** it now says what changed: re-handing the invite already in the Join field drops an older pending replacement, and a replacement still needs Yes and then **Join friendnet**.
