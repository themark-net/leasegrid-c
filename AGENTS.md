# AGENTS.md — leasegrid-c

Leasegrid client/operator (device leasing / grid control plane).

## Mandatory reads

1. [README.md](README.md)
2. [docs/](docs/) — design, ops, and module docs

## Testing standing rule
Prefer the Testing Trophy: mostly integration/E2E for product confidence. Unit tests only for shaky/non-obvious behavior. Forbidden: tautological tests and implementation-detail tests. Prefer sociable tests; doubles only at awkward boundaries + contract tests for externals. Every non-trivial change: How could this fail? How do we recover?

No tautological or implementation-detail unit sprawl as Done.

## Systems rules

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

Skill: [.grok/skills/systems-safety/SKILL.md](.grok/skills/systems-safety/SKILL.md)

## Verify / dogfood

```bash
bash scripts/ci-local.sh
# optional local grid dogfood:
# bash scripts/dev-grid.sh
```

A linked git worktree uses `$ROOT/.venv` (created if missing) instead of a shared venv. `CI_LOCAL_PRINT_PYTHON=1` prints the chosen interpreter and exits without installing.
