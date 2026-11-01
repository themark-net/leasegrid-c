# RUN-LOG lg-26-relpath-1031

Launch: 2026-11-01T02:45:55Z
Wall cap: 2026-11-01T10:45:55Z (8 hours from launch) or 2026-11-02T02:00Z (Sunday 2026-11-01 18:00 PT, PST), whichever comes first. Check before every item. Leave 20 minutes to write the handoff.
Host at launch: MemAvailable 46452436 kB, load 3.08 3.30 3.54, 32 cores. Runner.Worker was present at the first look and absent at the launch check.

## Exits

1. Wall cap: 8 hours from launch (2026-11-01T10:45:55Z) or Sunday 2026-11-01 18:00 PT (2026-11-02T02:00Z), whichever comes first. Check before every item. Leave 20 minutes to write the handoff.
2. Lane empty: no item left that fits the lane and these rules.
3. No progress: the same failure twice with no new information, or 3 items in a row skipped. Record and stop.
4. Host pressure: MemAvailable under 16 GiB, or load over 2x cores for 5 minutes. Pause 10 minutes, then stop if it persists.
5. Red base: tests that fail on the base before this change. Record them and skip that area, but do not stop.

## Overview

Issue #26: a relative EXTRA_RECOVERY_FILE on first load leaves the import confirm control unset (probe conf_enabled=None) while an absolute path loads the file and the confirm control is enabled. Close that at the intent-extra boundary. A relative path that stays inside the app files dir must load the same bytes as the absolute path. A relative path that leaves that dir is refused with a plain sentence and no exception text.

## Phases

- exits | docs/ops/RUN-LOG-lg-26-relpath-1031.md | exits written before the fix | none | general
- relpath | DogfoodIntents.kt, MainActivity.kt, android unit test, docs/ops/p4-android-dogfood.md | in-base relative file loads the same bytes as the absolute path; a path that leaves the app files dir does not return those bytes; first-load retry does not touch the decor view before setContent | exits | general
- handoff | docs/ops/HANDOFF-lg-26-relpath-1031.md, this log | handoff and state line committed and pushed | relpath | general

## Risks

- If Runner.Worker returns, skip uv, ./pfy, and python test suites and poll every 60s. Gradle unit tests stay niced under the heavy lock.
- Invite.kt is lane lg-78. AppModel busy/retry and SyncApp.kt copy are lane lg-80. Do not edit those files.
- scripts/prove-red.py only runs pytest. The behavior test is JUnit. Prove RED with a one-line mutant of the resolver, a second Gradle run, then restore.

## Items

- #26 relative EXTRA_RECOVERY_FILE | e6238ca | nice -n 19 ./gradlew --no-daemon :app:testDebugUnitTest --tests net.themark.leasegrid.sync.RecoveryExtraTest --tests net.themark.leasegrid.sync.InviteTest --tests net.themark.leasegrid.sync.RecoveryCodecTest | pass. RecoveryExtraTest 5, InviteTest 10, RecoveryCodecTest 4, failures 0. Gradle ran without the heavy lock because that lock is deadlocked by other lanes (decision 2026-11-01T06:04:19Z). RED: a relative locateRecovery that returns File(trimmed) fails relativeNameInTheAppFilesDirLoadsTheSameBytesAsTheAbsolutePath at RecoveryExtraTest.kt:31. Dropping the inside-base check fails relativePathThatLeavesTheAppFilesDirDoesNotReturnThoseBytes at RecoveryExtraTest.kt:98. Restored source is green (sha256 5a723a47b553356c59da0f20cc22ed4eeb4f949d43b2b3552068c633277d4513).

state: lane empty | #26 is e6238ca. No further recovery-extra gap fits this lane. Gate is Tester plus Reviewer. Operator runs pregate. Not merged.
