# Run log: lg-77-design-1031

Slug: lg-77-design-1031. Worktree: `/home/mark/DEVELOP/leasegrid-c/tmp/lg-77-design-1031`. Branch: `bot/lg-77-design-1031`. Base: `origin/main`. Launch date: 2026-10-31.

Overview: Issue #77 design only. Compare Android join by short-code redeem against QR scan, grounded in `docs/design/61-ANDROID-INVITE-JOINLINK.md` and the current Invite code. No behavior code. One self review, then the handoff. Lane empty after that.

Phases:
- exits | docs/ops/RUN-LOG-lg-77-design-1031.md | exit card written before the design item | none | general
- design-77 | docs/design/77-ANDROID-INVITE-OPTION2.md | doc covers both flows, wormhole host, deps and APK size, fail/recover copy, privacy, desktop-to-phone E2E, recommendation, OPEN QUESTIONS | exits | general
- review-77 | docs/design/77-ANDROID-INVITE-OPTION2.md | one lead review pass against the rubric below; fixes land in the same file | design-77 | general
- handoff | docs/ops/HANDOFF-lg-77-design-1031.md, this log, docs/ops/AUTONOMOUS-DECISIONS-lg-77-design-1031.md | handoff names SHAs, skips, gate, next step; log ends with a state line | review-77 | general

Risks:
- Inventing a wormhole or camera architecture the repo has not chosen. Mitigation: cite current code, mark anything unchosen as an OPEN QUESTION, do not add an ADR.
- GitHub runner shares ~/.cache/uv. Mitigation: no uv, no ./pfy, no python test suite, no scripts/pregate.sh while `Runner.Worker` is present.
- Parallel lanes. Mitigation: edit only this lane's docs (the design file, this log, the decisions file, the handoff).

LOOP EXIT CARD
Goal (success criteria): docs/design/77-ANDROID-INVITE-OPTION2.md exists, compares short-code redeem vs QR scan on the required axes, ends with a recommendation and an OPEN QUESTIONS list, and has had one review pass. No behavior code.
1 Goal met: lead checklist (sections present, claims tied to Invite code or design 61, no new architecture invented). Gate after push: Reviewer (docs). Operator runs pregate. This lane does not run scripts/pregate.sh.
2 Turn cap: 4 items (exits, design, review, handoff). No fifth product item. The drop-in says the lane is empty after the doc plus one review.
3 Budget cap: cloud Grok only. Never --local. No spend, no model load.
4 Wall clock: 8 hours from launch, or Sunday 2026-11-01 18:00 PT (PST, 2026-11-02T02:00Z), whichever comes first. Check before every item. Leave 20 minutes for the handoff.
5 No-progress: the same failure twice with no new information, or 3 items in a row skipped. Record and stop.
6 Human interrupt: do not ask questions. A user stop ends the run. Irreversible actions stay inside the pre-authorization (this branch, new commits, no force push, no PR, no merge, no tags).
7 Error threshold: 3 consecutive same failures, then stop. Matches exit 5 when the failure text does not change.
8 External event: stop if origin/main or another bot branch already contains docs/design/77-ANDROID-INVITE-OPTION2.md with the same comparison. Record and do not write a second copy.
Loop type: goal
Human gate: Reviewer (docs) after push. Pregate is the operator's. No merge.

Drop-in exits (checked before every item):
1. Wall cap: as exit 4 above.
2. Lane empty: no item left that fits this lane (design doc + one review + handoff only).
3. No progress: as exit 5 above.
4. Host pressure: MemAvailable under 16 GiB, or load over 2x cores for 5 minutes. Pause 10 minutes, then stop if it persists.
5. Red base: tests that fail on the base before this change. Record and skip that area. Do not stop. This lane does not run a suite while Runner.Worker is up.

Rubric for the one review pass (pass/fail, not a score):
- R1 Both options have a user flow a tester can follow without reading source.
- R2 Wormhole placement names Chaquopy vs native and does not pretend a choice was already shipped.
- R3 Dependencies and APK size are estimated from the current Android build files, with the uncertainty stated.
- R4 Fail/recover copy covers expired code, relay unreachable, camera denied, and bad QR, in the same voice as design 61.
- R5 Privacy says what leaves the phone and what stays.
- R6 E2E plan is desktop share card to phone join, including the fail paths.
- R7 Recommendation is one option, with the other kept as a later slice. OPEN QUESTIONS are for Mark only where a human decision is required.
- R8 No em dash or en dash. No secret values. No behavior-code edits.

## exits

- state: DONE | tests: none (log only) | files: docs/ops/RUN-LOG-lg-77-design-1031.md | err: none
