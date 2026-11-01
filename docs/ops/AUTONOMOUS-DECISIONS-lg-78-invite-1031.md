# Autonomous decisions lg-78-invite-1031

1. 2026-11-01T02:02Z: Skills write-loop-exits-first and repo-handoff-doc-required are not files in this worktree or ~/.grok/skills. Choice: follow the drop-in exit list, the agent-loops eight-exit card in the run log, and docs/ops/HANDOFF-lg-78-invite-1031.md. Alternative: stop and ask. Why: the drop-in already states the exits and the handoff path, and it says not to ask.

2. 2026-11-01T02:02Z: This drop-in is one owned file (Invite.kt) plus its tests and the lane docs. Choice: the lead implements it. No second writer on Invite.kt. The project-map subagent may write only .project-map/. Alternative: spawn an implementation subagent. Why: a second writer on the same files would race this session, and the subagent preamble forbids the push this drop-in requires.

3. 2026-11-01T02:50Z: Short-code check is a linear scan, and a paste longer than 256 characters is not a short code. Alternative: keep the regex behind a length cap. Why: a 4 KB near-miss already throws StackOverflowError on this JDK's default stack (red: InviteCopyTest.aHundredKilobytePasteDoesNotOverflowAndStaysAPlainError, Pattern.java). A cap large enough for a long code can still overflow. 256 covers a nameplate plus many words. A real invite code is two or three words.
