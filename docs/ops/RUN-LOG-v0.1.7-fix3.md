# Run log — v0.1.7 fix round 3

Overview: Tester FAIL on PR #74 at b267059. Fix the nested invite question (N1), the TERM-obeying leader's surviving grandchild (N2), and the second-launch abort (N3), then close the mutation gaps (F1, F3, C2, S1, S10), remove the dead young-lock check, and collapse `display_path` outside home. One commit per item on `build/v0.1.7-batch`. No push.

Phases:
- N1 replace dialog | src/leasegrid_sync/app.py, tests/test_sync_handed_invite.py, tests/test_sync_join_replace.py | flood of 400 distinct invites leaves one box and SIGTERM exits 0; crash sequence A,B,B,nonl exits 0; latest invite wins | none | general
- N2 reap grandchild | src/leasegrid_sync/backend.py, tests/test_sync_process_group.py | leader obeys TERM and an unreaped exited leader both leave no TERM-ignoring grandchild; pid-reuse test stays green | none (after N1 commit so the branch stays linear) | general
- N3 second launch | src/leasegrid_sync/app.py, tests for already-running | unmocked second launch rc is not 134; held oversized --join too | N1 (same file) | general
- F1 F3 log filter | packaging/tahoe-log-filter.sh, tests/test_tahoe_log_filter.py | 40-char base64url with -/_ redacted; digit-underscore fragments no worse than base; mutants RED | none | general
- C2 S1 S10 join | src/leasegrid_sync/app.py, join tests | idle socket closed; foreign uid refused; planted non-socket kept and listen refused | N1 N3 | general
- young lock | src/leasegrid_sync/app.py, tests/test_sync_instance_lock.py | `_pidless_lock_is_young` removed; stale-time drop still RED; lock tests green | N3 C2 (same file) | general
- display_path | src/leasegrid_sync/app.py, tests/test_sync_display_path.py | `/home/u/../other/x` collapses; URLs and relative paths stay | young lock | general
- handoff | docs/HANDOFF-v0.1.7.md, docs/release-notes/v0.1.7.md, docs/ops, drop-in | table, deferrals, final ci-local, base worktree removed | all items | general

Risks:
- Nested `exec_()` ignored SIGTERM — drop the socket and ask with `open()`, one pending question, so the existing wakeup fd can quit.
- `poll()` reaps the leader and skips the group SIGKILL — `waitid` WNOWAIT until after `killpg`.
- Parallel agents on this worktree would race commits — lead implements in order (see autonomous decisions).
- ci-local is the whole suite — run it once per item and stop if the same failure repeats three times.

state: PLAN | tests: not started | files: 0 | err: none

state: DONE | item 1 N1 | tests: tests/test_sync_join_replace.py tests/test_sync_handed_invite.py tests/test_sync_join_flood.py tests/test_sync_join_handoff.py 11 passed; live join/flood.py 400 send-close TERM rc=0; live join/crashseq.py A,B,B,nonl,sleep2 rc=0 lock_left=False crash=none | ci-local: 572 passed, 5 xfailed, 4 warnings in 124.53s | err: none
RED base: test_flood_of_different_invites_keeps_one_box_and_quits → app still alive 15s after SIGTERM; test_sigterm_with_the_replace_question_open_exits_zero → rc -11
RED mutant: drop the one-pending guard → test_flood_of_different_invites_keeps_one_box_and_quits boxes=400. Calling box.exec_() in place of open(), with the guard kept, returned No in ~0.12s on this offscreen Qt and did not nest a loop per invite, so that mutant stayed green. The guard is what stops the nest.

state: DONE | item 2 N2 | tests: tests/test_sync_process_group.py 5 passed in 1.71s; live pg/reap_obey.py leader rc=-15 grandchild state=gone in 0.6s | ci-local: 574 passed, 5 xfailed, 4 warnings in 132.33s | err: none
RED base: test_reap_kills_grandchild_when_the_leader_obeys_term → grandchild survived reap_child; test_stop_kills_grandchild_after_the_leader_exits_on_its_own → grandchild survived stop(); pid-reuse test stayed green
RED mutant: skip the post-exit group SIGKILL in _finish_exited_group → grandchild survived reap_child; replace waitid WNOWAIT with proc.poll() in _leader_state → grandchild survived reap_child (pid-reuse stayed green). Tester R3 "always SIGKILL the group" is now intended while the leader is unreaped; the reaped/pid-reuse test guards the already-reaped case.
