---
name: systems-safety
description: Use when writing or reviewing code that touches locks, PIDs/signals, local IPC, temp files, restored/serialized state, ints passed to Qt or C, log redaction, or platform-specific process code.
---

# Systems safety

Reviewer fails a violation of these rules. Cite the id. Patterns live in `tools/semgrep/`. The reviewer checklist is in `AGENTS.md`.

## SS1 Locks

Never delete or "recover" a lock this process does not hold. Use `QLockFile` defaults, `flock`, or `O_EXCL`. Do not call `removeStaleLockFile()` or `setStaleLockTime(0)`.

Do: let Qt's stale time decide, inside `tryLock`. Don't: unlink a lock file to "fix" a rival. Test: an N-process by M-round run has exactly one holder.

CWE-367. Semgrep: `qlockfile-manual-stale-removal`.

## SS2 PIDs

Signal only a child this process still owns (`Popen.poll()` is `None` immediately before the signal) or use a pidfd. Never signal a stored, reaped, or reused pid or pgid.

Do: keep the leader unreaped until the group kill, then reap. Don't: `os.kill` or `os.killpg` a number read from a file. Test: a reaped leader's old pid, now reused, is still alive after stop.

CWE-367. Semgrep: `signal-to-stored-pid`.

## SS3 IPC

No endpoint in `/tmp` or `gettempdir()`. Use `$XDG_RUNTIME_DIR` or a `0700` directory whose owner you checked. `QLocalServer` gets `UserAccessOption`. Check the peer uid. An `AF_UNIX` path is under 104 bytes.

Do: create the directory with mode `0700` and refuse a symlink or a foreign owner. Don't: `os.path.join(tempfile.gettempdir(), name)` or `listen()` before `setSocketOptions`. Test: a foreign uid or a path of 104 bytes or more is refused, and a second launch still delivers one invite.

CWE-377, CWE-732. Semgrep: `ipc-endpoint-in-shared-tmp`, `qlocalserver-listen-without-user-access-option`, `af-unix-path-length`.

## SS4 Untrusted state

Never pass file bytes to `restoreGeometry`, `restoreState`, or `pickle`. Parse fields, clamp to the screen and to int32, and default on any error.

Do: store plain numbers and ignore a record that fails a check. Don't: `pickle.loads` or `marshal.loads` a file the user can edit. Test: one flipped bit in the saved record still opens the window on the screen.

CWE-502. Semgrep: `restore-untrusted-serialized-state`.

## SS5 Ints to C and Qt

Clamp to [-2^31, 2^31-1] and to a sane domain before any Qt or ctypes call.

Do: reject a count, port, or size outside the domain before the call. Don't: pass a Python int straight into a 32-bit Qt or ctypes slot. Test: a value above 2^31-1 takes the default and does not reach the foreign call.

CWE-190. Semgrep: none yet. Add a rule in the same PR as the first fix a pattern could have caught.

## SS6 Secrets

One redactor. Test it with generated secrets in random context, plus a detector that does not share the redactor's regex. No awk interval expressions (`{n,}` or `{n,m}`).

Do: redact in Python, or expand the repetition for sed. Don't: `awk` `match` / `sub` / `gsub` with `{40,}`. Test: a generated token of the protected length is gone, and a shorter lookalike remains.

Semgrep: `awk-interval-expression`.

## SS7 Platforms

Guard POSIX-only calls with `sys.platform` (`killpg`, `getpgid`, `SIGHUP`, `SIGKILL`). Claim CI is green only with `gh pr checks` output.

Do: return before the POSIX call on Windows, and run the Windows job. Don't: call `os.setsid` or `signal.SIGKILL` on a path Windows executes. Test: the Windows CI job is listed, and the POSIX branch is skipped there with a reason.

Semgrep: `posix-only-process-api`.

## SS8 Proof of RED

Every fix ships a test that fails when the fix is reverted. Paste the receipt.

Do: run `scripts/prove-red.py` on a cases file and paste the table. Don't: write "CI green" from a Linux `ci-local` run. Test: the receipt shows RED for the reverted fix, and `git diff` on the target is empty afterwards.

Semgrep: none. The proof is the receipt, not a pattern.

## Standing rule

Every Tester or Reviewer blocker a pattern could catch becomes a `tools/semgrep` rule with `ruleid` and `ok` fixtures, in the same PR as the fix. Name the blocker in the message (for example "PR #74 T4").
