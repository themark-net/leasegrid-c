## Proof of RED

For each fix, name the case and paste the `scripts/prove-red.py` table. Exit 0 means every case is RED. A baseline that is not green, or a pytest exit other than 1, is a setup error (exit 2), not RED. A mutated Python file that does not compile is INVALID (exit 2), not a kill. SIGKILL leaves the mutant applied; the next run restores it when the bytes match that case, otherwise `git restore --source=HEAD -- <file>`.

## CI evidence

Paste `gh pr checks <n>` output, or the Actions run URL with every job listed.

`scripts/ci-local.sh` is Linux only and never counts as "CI green".
