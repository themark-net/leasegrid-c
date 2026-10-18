# Grok Build drop-in: dev safety rails (Semgrep + ruff gate, systems-safety skill, proof-of-RED)

/orchestrate: follow ~/.grok/skills/orchestrator/SKILL.md for the loop. Where that skill or any other says to ask the user, decide yourself instead.

**This run is PRE-AUTHORIZED by the owner (Mark). Nobody is watching. Ask no questions and wait for no one.** For every small, reversible ambiguity, pick the most conservative option, add ONE line to `docs/ops/AUTONOMOUS-DECISIONS-dev-safety-rails.md` (`choice | alternatives | why`), and keep going.

**Launch only after v0.1.7 (PR #74) has merged to main.** Mark's ask: "Process Id locks and secrets leaks seem like rookie development mistakes." Tester and Reviewer catch these, but each costs a gate round. This run makes the repo catch them first.

## 0. Exits (read first)

You stop only on one of these. Before you stop for any reason, do **Finish** (§5).

1. **Goal met.** Items 1–4 in §3 are DONE or SKIPPED (reason logged), and §5 is pushed.
2. **Precondition.** v0.1.7 is not on `origin/main` (`pyproject.toml` version on origin/main is not `0.1.7` or later). Change nothing, write one line in the run log, stop.
3. **Per-item cap.** At most 8 attempts per item. After that, revert that item's uncommitted changes, mark it SKIPPED, and go on.
4. **Same failure 3 times** in a row on one item: SKIP it, revert its uncommitted changes, next item.
5. **No progress.** 40 minutes on one item with no commit: do §5 and stop.
6. **Red base.** If the baseline fails, log the failing tests and carry on. Never go below the baseline.
7. **Wall clock.** About 2.5 hours after start: finish the current commit, do §5, stop.
8. **Host safety.** Under 2 GB free, or low memory: do §5 and stop.
9. **Owner stop.** A `STOP` file in the worktree root: do §5 and stop.

**Resume.** If `docs/ops/RUN-LOG-dev-safety-rails.md` exists, continue from the first item that is not DONE or SKIPPED.

## 1. Context

- Repo themark-net/leasegrid-c (Leasegrid Sync, PyQt5). Read `AGENTS.md`; its testing rule applies.
- **Branch:** `build/dev-safety-rails`. It already holds this file and the seed rules in `tools/semgrep/` (committed off main `b4e9b70`).
- **Your only working tree:** the standalone clone `/tmp/lg-dev-safety-rails` (already on `build/dev-safety-rails`, push URL is SSH). Do **not** create a worktree under `~/DEVELOP/leasegrid-c`. In the clone: `git fetch origin && git checkout build/dev-safety-rails && git merge --ff-only origin/build/dev-safety-rails`.
  Then bring in main **by merge, never rebase**: `git merge --no-edit origin/main`. Commit `dev-safety-rails: merge main (v0.1.7)`.
- **Interpreter:** `python3 -m venv .venv` in the worktree, then `PYTHON=$PWD/.venv/bin/python bash scripts/ci-local.sh`. Qt offscreen.
- **Seed already on the branch** (verified on the Grok Bot box with semgrep 1.181.0):
  - `tools/semgrep/leasegrid-systems.yml`: 7 rules (`ipc-endpoint-in-shared-tmp`, `qlocalserver-listen-without-user-access-option`, `qlockfile-manual-stale-removal`, `signal-to-stored-pid`, `restore-untrusted-serialized-state`, `posix-only-process-api`, `af-unix-path-length`), each citing a rule id SS1–SS7.
  - `tools/semgrep/shell-portability.yml`: `awk-interval-expression` (SS6).
  - Fixtures `leasegrid-systems.py` and `shell-portability.sh` with `# ruleid:` / `# ok:` lines. `semgrep --test tools/semgrep` gave 8/8 passed.
  - Replay on old heads: `b4e9b70` 0 hits. PR #73 `bd7b09e` hit B1 (app.py:139) and B2-area `restoreGeometry`. `8a70dd3` hit B5 (app.py:2361). PR #74 `fbeb6f1` gave 11 hits, including the T2 awk line, the T3 stale removal, the `/tmp` socket, the QLocalServer without options, and the T4 `killpg`. Generic tools (bandit, ruff `S`, semgrep `p/python`) hit **none** of those blockers.
- **Run log:** `docs/ops/RUN-LOG-dev-safety-rails.md`.

## 2. Hard rules

- Work only inside the worktree (and `/tmp`). **Never touch `/home/mark/DEVELOP/leasegrid-c` itself** (Mark's checkout) or other worktrees (`tmp/v017-*` included). Only this `.venv`. No sudo, no system packages, no services, no sign-ins, no spending money, no posting. Don't kill processes you didn't start.
- Never print or commit secrets; fakes only.
- No PR creation or edits, no merge to main, no tag, **no force-push, no rebase**. Push only `build/dev-safety-rails`, normally: `git push origin HEAD:refs/heads/build/dev-safety-rails`. Stage explicit paths only.
- This run adds gates and docs. **Don't change app behavior** (sole exception: the bug fixes named in item 4). If a new rule flags v0.1.7 code, either suppress it on that line with a reason (`# nosemgrep: <rule-id> -- <why it is safe>`, or `# noqa: S<nnn> <why>`) or, if it is a real bug, log it under "Found by the new gate" in the handoff and **don't fix it here**.
- **Tests:** prefer E2E/integration/operate-or-FAIL (Testing Trophy). No tautological or implementation-detail unit sprawl. Each new test must be able to fail with the bug present. All CI platforms stay green (Linux, macOS, Windows).
- **Proof per item:** apply the named mutation, confirm RED, restore. Log `RED: <mutant> → <test or gate>`. Never commit a mutated state.
- One commit per item (`dev-safety-rails N: <summary>`). ci-local must PASS before each commit. Push after each.

**Before item 1:** run ci-local and record the baseline counts in the run log. Commit `dev-safety-rails: run log baseline`.

## 3. Work list

**1. Semgrep project rules plus stricter ruff, gated in ci-local and Actions.**
- **Semgrep.** Add `semgrep==1.181.0` to a new `lint` extra in `pyproject.toml` (not `dev`; it is large).
  - `scripts/ci-local.sh` installs `.[lint]` and runs, after ruff: `"$PYTHON" -m semgrep --test --metrics=off tools/semgrep` then `"$PYTHON" -m semgrep scan --metrics=off --error --config tools/semgrep src scripts packaging`. If semgrep cannot install or run, ci-local **FAILs** with a clear message. `CI_LOCAL_SKIP_SEMGREP=1` skips it with a loud `SKIPPED semgrep` line, for hosts without wheels. Log any use of it.
  - `.github/workflows/ci.yml`: a separate `semgrep` job on `ubuntu-latest` (semgrep has no native Windows build) running the same two commands.
- **Ruff.** CI passes `--select E4,E7,E9,F` on the command line, which overrides `pyproject.toml`. Move the selection into `[tool.ruff.lint]` and drop `--select` from ci-local and `ci.yml` (keep the same paths).
  - New selection: the current `E4,E7,E9,F`, plus `B`, `SIM115`, `PLW1510`, plus these bandit rules: `S102,S103,S104,S108,S301,S302,S306,S307,S324,S377,S403,S506,S602,S604,S605,S606`.
  - `[tool.ruff.lint.per-file-ignores]`: `"tests/**" = ["S", "B"]`.
  - On `b4e9b70` this set gave about 4 `B` hits (B904 ×3, B905 ×1) and 2 `SIM115` in src/scripts/packaging, and 0 for the listed `S` rules. (That measurement used ruff's default target; with the repo's `target-version = "py39"`, B905 may not fire, since `zip(strict=)` needs 3.10.) Fix trivial ones without behavior change (e.g. `raise ... from err`); otherwise suppress with a reason. Re-measure after the merge with main.
- **Triage the v0.1.7 code.** Run the new gates. For every hit, suppress with a reason or log it as "Found by the new gate" (see §2). The scan must end at 0 unsuppressed hits.
- **Standing rule** (add to `CONTRIBUTING.md` and AGENTS.md in item 2): every Tester or Reviewer blocker that a code pattern could have caught gets a Semgrep rule in `tools/semgrep/` with `ruleid`/`ok` fixture lines, **in the same PR as the fix**. Name the blocker in the rule message (e.g. "PR #74 T4").
- DoD and mutations (log each):
  - (a) `semgrep --test tools/semgrep` passes in ci-local and in the Actions job.
  - (b) Rule mutant: delete the `pattern-not-inside ... setSocketOptions` block from `qlocalserver-listen-without-user-access-option`. `semgrep --test` goes RED.
  - (c) Gate mutant: add `lock.setStaleLockTime(0)` to the instance-lock code in `src/leasegrid_sync/app.py`. ci-local goes RED at the semgrep step.
  - (d) Ruff mutant: add `os.chmod(path, 0o777)` somewhere in `src/`. ci-local goes RED at ruff (S103).
  - (e) Fixture mutant: change one `# ruleid:` line in a fixture to `# ok:`. `semgrep --test` goes RED.

**2. `systems-safety` Grok skill plus the AGENTS.md rule block.**
- Create `.grok/skills/systems-safety/SKILL.md` with frontmatter `name: systems-safety` and a `description` under 1024 chars: "Use when writing or reviewing code that touches locks, PIDs/signals, local IPC, temp files, restored/serialized state, ints passed to Qt or C, log redaction, or platform-specific process code." Body: the rules below, one short section per rule with a "do / don't / test that proves it" line. Cite CWE-367, 377, 732, 502, 190. Reference `tools/semgrep/` rule ids per rule. Keep it under about 150 lines.
- Add this block to `AGENTS.md` under a `## Systems rules` heading (verbatim, then a link to the skill):

```
Systems rules (Reviewer FAILs on violation; cite the id):
SS1 Locks: never delete or "recover" a lock you don't hold. Use QLockFile defaults, flock or O_EXCL. Ship an N-proc x M-round test asserting exactly one holder.
SS2 PIDs: signal only a child you still own (Popen.poll() is None right before), or use pidfd. Never kill a stored or reaped pid or pgid.
SS3 IPC: no endpoints in /tmp or gettempdir(). Use $XDG_RUNTIME_DIR or a 0700 dir whose owner you verify. Use QLocalServer UserAccessOption and check the peer uid. AF_UNIX path < 104 bytes.
SS4 Untrusted state: never feed file bytes to restoreGeometry, restoreState or pickle. Parse into fields, clamp to the screen and int32, and default on any error. Add a property or fuzz test.
SS5 Ints to C/Qt: clamp to [-2^31, 2^31-1] and to a sane domain before any Qt or ctypes call.
SS6 Secrets: one redactor, tested with generated secrets in random context plus an independent detector. No awk regex intervals ({n,}).
SS7 Platforms: guard POSIX-only calls with sys.platform (killpg, getpgid, SIGHUP/SIGKILL). Claim CI green only with `gh pr checks` output.
SS8 Proof of RED: every fix ships a test shown failing with the fix reverted (paste the receipt).
Standing rule: every Tester/Reviewer blocker a pattern could catch becomes a tools/semgrep rule with fixtures, in the same PR as the fix.
```

- Add `tests/test_systems_rules_doc.py`, a cross-file consistency check, not prose snapshots:
  - every `SS<n>` id cited in a `tools/semgrep/*.yml` message exists in both AGENTS.md and the skill;
  - the skill frontmatter parses, `name` equals its folder, and the description is non-empty and under 1024 chars;
  - AGENTS.md links to the skill path, and that path exists.
- In the run log, record whether a Grok session started in the worktree lists `systems-safety`. If you can't confirm it, say so; don't guess.
- DoD and mutations:
  - (a) Delete the SS3 section from the skill: the test goes RED.
  - (b) Rename the skill's `name:` field: RED.
  - (c) Add `SS9` to one rule message without documenting it: RED.

**3. Proof-of-RED and evidence rule.**
- Add `scripts/prove-red.py` (stdlib only), a generalized version of Tester's harness.
  - Usage: `prove-red.py <cases.py> [--python PY]`. `cases.py` defines `CASES = [(name, file, old, new, [pytest args])]`.
  - For each case: refuse if `old` is not in the file (exit 2, "PATTERN MISSING"). Otherwise replace the first occurrence, run `PY -m pytest -q -p no:cacheprovider <args>` with `QT_QPA_PLATFORM=offscreen`, record RED (non-zero) or SURVIVED (zero), and restore the file in a `finally`, including on Ctrl-C.
  - At the end, check `git diff --quiet` on every touched file. Print a table and write it to `--receipt PATH` if given.
  - Exit 0 only if every case is RED; exit 1 if any survived; exit 2 on setup errors.
  - Refuse to start (exit 2) if any target file has uncommitted changes, so a mutant can never be committed.
- Add `tests/test_prove_red.py`. Use a temp git repo with a tiny module and a test, and run the script in a subprocess:
  - a caught mutant gives exit 0 and RED;
  - a surviving mutant gives exit 1 and SURVIVED;
  - a missing pattern gives exit 2;
  - a dirty target file gives exit 2 and the file is unchanged;
  - after every run the target file's bytes equal the original.
  - Must pass on Windows CI too: use `sys.executable` and no shell; skip the Ctrl-C case on Windows with a reason.
- Add `.github/pull_request_template.md` with two required sections:
  - **Proof of RED**: for each fix, the case and the `prove-red.py` table.
  - **CI evidence**: paste `gh pr checks <n>` output, or the Actions run URL with every job listed. ci-local is Linux only and never counts as "CI green".
- AGENTS.md (in the `## Systems rules` area): "Before claiming done: run `scripts/prove-red.py` on a cases file for your fixes and paste the table into the PR body. Never write 'CI green' without `gh pr checks` output or a run URL listing all jobs."
- Add a cases file for this run's own item 2 test (`docs/ops/prove-red-dev-safety-rails.py`), and paste its receipt in the handoff as the first real use.
- DoD and mutations:
  - (a) Remove the restore from the `finally`: the "bytes equal original" test goes RED.
  - (b) Make the script exit 0 when a mutant survives: the survivor test goes RED.
  - (c) Drop the dirty-tree refusal: the dirty test goes RED.

**4. Tests for Tester's v0.1.7 mutation survivors (plus the R9n fix).**
Each test must be behavioral (real subprocess / real QLockFile / real widget flow where practical, Qt offscreen) and must go RED on the named mutant via `scripts/prove-red.py` (item 3). Put the cases in `docs/ops/prove-red-dev-safety-rails.py` alongside item 2's, and paste the receipt into the handoff.
- **R9n — `TahoeClient.start` treats a zombie as running** (`src/leasegrid_sync/backend.py`, `start()` / `_leader_state()`). A daemon that has exited but is unreaped must not count as "running", so a dead daemon gets restarted. **Fix it** (this is the one allowed app-behavior change besides follow-up 1 below): an exited-unreaped leader takes the reap-then-respawn path. Test: start a fake `tahoe` that exits immediately (leave it unreaped), call `start()` again, assert a new process was spawned and is alive. RED mutant: make `_leader_state` report a zombie as `"running"` (or restore the pre-fix check) → test RED. Do not regress the v0.1.7-fix3 group-kill / pid-reuse tests.
- **N1i — "Yes" on the handed-invite replace box must not auto-join.** Test: with invite A in the join field and B pending, answer Yes; assert the field now holds B, no join was started (no join worker / tahoe spawn / `_joined` stays false), and the user must still press Join. RED mutant: call the join action from the Yes handler → RED.
- **L5n — second lock try after the writer grace** (`src/leasegrid_sync/app.py`, `_lock_writer_grace` and the second `lock.tryLock(0)`). Test: an empty/mid-write lock file whose writer finishes during the grace; assert the second `tryLock` takes the lock (or correctly refuses a live holder), with exactly one holder. RED mutant: drop the second `tryLock(0)` (treat the first failure as final) → RED.
- **Tester follow-up 1 — latest handed invite must win.** Today, if B is pending in the replace box and the user re-hands the invite that is already in the field (A), the `current == text` early return leaves B pending, so a later Yes applies the *older* B. Fix: re-handing A while B is pending clears the pending replacement and closes the box (latest wins); a subsequent Yes must not apply B. Test via the `LEASEGRID_TEST_INVITE_DUMP` hook or direct widget calls: hand B (pending), hand A again, assert `pending=` empty and `boxes=0`, field still A. RED mutant: restore the early return without clearing pending → RED.
- **Tester follow-up 3 — "already running" second launch exits 0 on SIGTERM.** Unmocked: start a first instance (offscreen), start a plain second launch that shows the "already running" box (`ALREADY_RUNNING`), send it SIGTERM, assert exit code 0 (not 134/-15/abort) within a timeout. POSIX only; skip on Windows with a reason. If it fails today, fix only the second-launch SIGTERM handling and log it. RED mutant: remove the SIGTERM handler/quit hookup for the box path → RED.
- One commit `dev-safety-rails 4: survivor tests + R9n/latest-wins fixes`. All three CI platforms must stay green. If any fix turns out to need more than a small change, log it under "Found by the new gate / open" in the handoff, keep the test as `xfail(strict=True)` with the reason, and move on.

## 4b. Out of scope (do NOT implement)

Hypothesis property tests (geometry, redaction, lock), the redaction rewrite in Python, betterleaks, mutmut, atheris. These are investigation items 4–5, a later drop-in. Any real bug the new gates find: log it only.

## 5. Finish (always)

1. Run ci-local and record the counts. Push.
2. Write `docs/ops/HANDOFF-dev-safety-rails.md`, about 30 lines at most. Include:
   - one row per item (status, commit, tests, mutation results);
   - the semgrep/ruff hit triage (suppressed with reasons vs "Found by the new gate");
   - the first prove-red receipt;
   - whether Grok lists the skill;
   - the final counts and the head SHA;
   - the compare URL `https://github.com/themark-net/leasegrid-c/compare/main...build/dev-safety-rails?expand=1`.
3. Commit `dev-safety-rails: handoff`, push normally, and write the PR body to `/tmp/pr-dev-safety-rails.md` (don't open the PR). Stop.
