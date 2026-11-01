# RUN LOG lg-78-invite-1031

Launch: 2026-11-01T02:02Z
Base: origin/main @ 7ce0785691b925c4b2f0ef06f7cd3c7d2796386a
Branch: bot/lg-78-invite-1031 @ 98d8a8e (drop-in only, in sync with origin)
Worktree: ~/DEVELOP/leasegrid-c/tmp/lg-78-invite-1031
Effective wall cap: 2026-11-01T10:02Z (8 hours from launch). Absolute cap 2026-11-02T02:00Z is later. Stop new items by 2026-11-01T09:42Z so the handoff has 20 minutes.

## LOOP EXIT CARD

Goal (success criteria): Invite.kt paste parsing closes #78 item 1 and #80 F1 and F2. A ~100 KB paste returns a design banner and does not throw. Bad furls (%00, U+FFFD, plus decoded as space, embedded newline, empty or short swissnum) return MALFORMED_MSG. A leading U+200B or U+FEFF still parses. Retry after a bad paste joins a good link. No raw exception text. Android unit tests green under the heavy lock. Handoff written.
1 Goal met: Gradle :app:testDebugUnitTest for the invite tests, plus the lane handoff committed and pushed. Not a model self-score.
2 Turn cap: 8 items (the listed fixes, the already-done check, the suite, the handoff, and at most two Invite.kt follow-ups).
3 Budget cap: cloud Grok only. No local model. No paid deploy.
4 Wall clock: 2026-11-01T10:02Z, or 2026-11-02T02:00Z, whichever comes first. Handoff buffer 20 minutes.
5 No-progress: the same failure twice with no new information, or 3 items in a row skipped.
6 Human interrupt: user stop. No questions. Irreversible forks (force push, merge, tag, release, issue comment) are out.
7 Error threshold: 3 consecutive same failures, then stop.
8 External event: stop an item if origin/main or this bot branch already contains it. n/a for merge (this lane does not merge).
Loop type: goal
Human gate: Tester plus Reviewer for runtime changes. No merge from this lane.

Drop-in exits (same run, checked before every item):
1. Wall cap as above.
2. Lane empty: no Invite.kt item left that fits these rules.
3. No progress: same as exit 5.
4. Host pressure: MemAvailable under 16 GiB, or load over 2x cores (64) for 5 minutes. Pause 10 minutes, then stop if it persists.
5. Red base: tests that fail on the base before this lane's change. Record and skip that area. Do not stop the lane.

## Overview

Harden Android invite paste parsing in Invite.kt. Bound or replace the short-code regex so a ~100 KB paste cannot overflow it. Reject malformed introducer furls with MALFORMED_MSG. Strip a leading zero-width space or BOM before parse. The cancel ghost banner from #78 item 2 is already on origin/main (learn rethrows CancellationException, Done uses joinOn). AppModel.kt and SyncApp.kt stay with lane lg-80-appmodel-1031.

## Phases

- exits | docs/ops/RUN-LOG-lg-78-invite-1031.md, docs/ops/AUTONOMOUS-DECISIONS-lg-78-invite-1031.md | card and plan on the branch | none | lead
- 78-long-paste | Invite.kt, InviteCopyTest.kt | ~100 KB near-miss returns a design banner, no throw, within a few seconds; a real short code still returns WORMHOLE_MSG; a long but well-formed join link still parses | exits | lead
- 78-ghost | no product edit (already on base) | record evidence and the cross-lane line | exits | lead
- 80-f1 | Invite.kt, InviteCopyTest.kt, SessionFlowTest.kt | each dirty furl is MALFORMED_MSG with no raw exception text; a clean link still joins; Retry after a bad paste joins the corrected field | 78-long-paste | lead
- 80-f2 | Invite.kt, InviteCopyTest.kt | leading U+200B or U+FEFF still parses as the same invite | 80-f1 | lead
- gradle-suite | owned tests | nice plus flock, :app:testDebugUnitTest | 80-f2 | lead
- handoff | docs/ops/HANDOFF-lg-78-invite-1031.md, docs/PENDING-HANDOFF.md, this log | state line, push, no merge | gradle-suite | lead

## Risks

- No JDK on PATH. Use the existing Temurin 17 at the grapheneos-mdm SDK tree read-only. Do not write into that tree.
- This host's Android SDK has platform 35, and the app compiles against 34. Install platforms;android-34 only under this worktree tmp/android-sdk.
- A catastrophic regex probe can hang. Run it under timeout in this worktree tmp/, and do not put an unbounded match in the Gradle suite.
- Shared Gradle home can collide with other lanes. This lane uses GRADLE_USER_HOME under its own tmp/.
- The ghost banner lives in AppModel and SyncApp. Editing those files would cross a lane. Leave them.

Host at launch: MemAvailable about 55 GiB, 32 cores, load about 3.9. Under the pressure line.
