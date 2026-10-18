# Autonomous decisions — dev safety rails

choice | alternatives | why

Lead implements every item in `/tmp/lg-dev-safety-rails` | one sub-agent worktree per item | items share AGENTS.md, ci-local, and one branch with a commit-then-push gate; the drop-in names this clone as the only tree
Merge message set with `git merge -m` | `--no-edit` default "Merge remote-tracking branch" | the drop-in names the commit `dev-safety-rails: merge main (v0.1.7)`
