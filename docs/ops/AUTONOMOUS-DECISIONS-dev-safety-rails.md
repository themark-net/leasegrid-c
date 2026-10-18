# Autonomous decisions — dev safety rails

choice | alternatives | why

Lead implements every item in `/tmp/lg-dev-safety-rails` | one sub-agent worktree per item | items share AGENTS.md, ci-local, and one branch with a commit-then-push gate; the drop-in names this clone as the only tree
Merge message set with `git merge -m` | `--no-edit` default "Merge remote-tracking branch" | the drop-in names the commit `dev-safety-rails: merge main (v0.1.7)`
Omit ruff selector S377 | include S377 and let ruff fail the gate | ruff 0.17.1 (from `ruff>=0.6`) has no S377 rule and rejects the selector; the other listed S codes stay
Enable ruff `preview` plus `explicit-preview-rules` | leave S403 as a no-op warning | S403 is preview-only in ruff 0.17.1; explicit codes keep prefix `B` on stable rules
Call the venv `semgrep` entry point | `python -m semgrep`, which the drop-in names | semgrep 1.181.0's `__main__` exits 2 before parsing arguments; the console script is the supported command
R9n plants the exited fake `run` on `_proc` | call `start()` for the dying run, then `start()` again | `start()` reaps a daemon that dies during its own wait, so the second call would not see a zombie
N1i uses wormhole-shaped invites, a marker binary, and a patched welcome | letter invites, or a real welcome | letters fail `parse_invite` before any spawn, so a joining Yes would stay green; a real welcome waits out the 30s start timeout
SIGTERM clicks Ok on the already-running box | `app.quit()` alone | `QMessageBox.information` runs a nested loop that `quit()` does not end
No new Semgrep rules in item 4 | one rule per survivor | item 4's gate is the behavioral test and its mutant; these bugs are state and control flow, not a local pattern the seed rules missed
Official prove-red receipt runs after the item 4 commit | run it on the dirty tree | prove-red refuses a target with uncommitted changes, and `app.py` holds the fix until that commit
Lead implements fix round 1 in this clone | one worktree sub-agent per failure | the drop-in names this clone as the only tree; both fixes share one branch and the push/CI gate
Normalize newlines only while prove-red matches, then restore the original bytes | force the tests to write LF, or skip them on win32 | `Path.write_text` and a Windows checkout turn `\n` patterns into `\r\n`, so a literal match fails for real users; the tests already restore and only reported PATTERN MISSING
On win32 accept the worker pid or its parent; POSIX stays `client._proc.pid == new_pid` | skip `test_start_respawns_an_unreaped_exited_leader` on win32 | the runner already respawned (spawned.pid alive and not the leader); CreateProcess of a `.bat` holds cmd.exe, and a skip would make the r9n mutant exit 0
Update `docs/ops/HANDOFF-dev-safety-rails.md` for this round | a new `HANDOFF-dev-safety-rails-fix1-<date>.md` | the drop-in names that file; the dated orchestrator name would split the handoff
Skip the prove-red signal-restore test on win32, including SIGINT | run the SIGINT row with os.kill or CTRL_C_EVENT | os.kill(SIGINT) TerminateProcess-kills without the handler, and CTRL_C_EVENT would hit the pytest console group; the existing SIGINT test already skips win32
