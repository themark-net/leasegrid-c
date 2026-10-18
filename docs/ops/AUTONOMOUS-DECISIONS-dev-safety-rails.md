# Autonomous decisions — dev safety rails

choice | alternatives | why

Lead implements every item in `/tmp/lg-dev-safety-rails` | one sub-agent worktree per item | items share AGENTS.md, ci-local, and one branch with a commit-then-push gate; the drop-in names this clone as the only tree
Merge message set with `git merge -m` | `--no-edit` default "Merge remote-tracking branch" | the drop-in names the commit `dev-safety-rails: merge main (v0.1.7)`
Omit ruff selector S377 | include S377 and let ruff fail the gate | ruff 0.17.1 (from `ruff>=0.6`) has no S377 rule and rejects the selector; the other listed S codes stay
Enable ruff `preview` plus `explicit-preview-rules` | leave S403 as a no-op warning | S403 is preview-only in ruff 0.17.1; explicit codes keep prefix `B` on stable rules
Call the venv `semgrep` entry point | `python -m semgrep`, which the drop-in names | semgrep 1.181.0's `__main__` exits 2 before parsing arguments; the console script is the supported command
