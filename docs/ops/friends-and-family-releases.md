# Friends-and-family releases

Non-breaking Leasegrid Sync updates ship as **friends-and-family (F&F) GitHub Releases**. Prior version tags and their installer assets stay published. There is no marketing blast and no public X announce for these cuts.

## Gate

1. Tester PASS and Reviewer PASS (double PASS) on the change PR.
2. Merge to `main`.
3. Version bump (Sync `__version__` + `pyproject.toml`) and release notes under `docs/release-notes/vX.Y.Z.md` when the bump is ready.
4. Tag `vX.Y.Z` only after the bump is on `main`. Do not force-push tags. Do not rewrite prior release assets.

The Installers workflow (`.github/workflows/installers.yml`) builds the four desktop assets on a `v*` tag push and attaches them to the GitHub Release. Release body prefers `docs/release-notes/<tag>.md` via `body_path`; if that file is missing, GitHub auto-generated notes are used. Each platform job also attaches a `SHA256SUMS-*` file for its assets.

## Out of scope here

Feature GO, paid-path marketing, and loud `v*` announcements stay on their own holds. Open follow-ups (for example issue trackers tagged non-blocking) do not block an F&F cut once double PASS + merge + bump are done.
