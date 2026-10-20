# Autonomous decisions — 2026-10-20

Decision | Alternative rejected | Why
---|---|---
v0.1.8 (#76) is a bump only, on branch `build/release-0.1.8` off `main` @ `7e73a64`, pushed with **no PR** | open the PR that #76 step 4 asks for | Grok Bot's 2026-10-20 instruction overrides #76 step 4: push a branch only; no PR, tag or merge. Someone opens the PR later
Version 0.1.8 in `pyproject.toml` and `src/leasegrid_sync/__init__.py`, plus asset names, About line and current-build links in `README.md`, `docs/TESTERS.md` and `docs/TESTER-GUIDE.md`, the same set as the v0.1.7 bump (#74) | also bump the Android `versionName` | Android keeps its own scheme (decided in v0.1.4)
`CHANGELOG.md`: the two Unreleased items move under `## 0.1.8 (2026-10-20)`, and an empty `## Unreleased` stays on top | drop the Unreleased header | the next change has somewhere to go
The "What's new in v0.1.8" pages keep the v0.1.5 #30 correction bullet | drop it | `test_tester_pages` pins that sentence on README and TESTERS
No product logic changed | | #76: "Do not change product logic in this PR"
`tests/test_release_notes.py`: the rotation test pins "when the daemon starts" on the v0.1.7 notes and the guide, and bans the wrong wording on every page. The sixth-bullet test pads to exactly six bullets | copy the v0.1.7 rotation bullet, or pad the v0.1.8 notes to 5 bullets | both tests read the *current* notes and assumed v0.1.7 content. Stale bullets would mislead testers. Proof: putting "rotate like" in the v0.1.8 notes, or dropping the phrase from the guide, turns the test red
