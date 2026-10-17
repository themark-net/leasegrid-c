# Autonomous decisions — v0.1.6 batch

One line per choice: `choice | alternatives | why`

- Sequential commits in this worktree, lead implements | parallel sub-agents or extra git worktrees | items share `app.py`, tests, and one branch; the drop-in forbids any other worktree
- `CI_LOCAL_PRINT_PYTHON=1` prints only the interpreter path | path plus the reason sentence | a worktree run must not print the shared venv path
- ci-local tests arm a bash DEBUG trap that refuses `pip install` | run a reverted script with no guard | a red proof must not retarget the shared venv
- One `reap_child` for Tahoe and Magic Folder `stop` | two copied wait-after-kill blocks | the bug is the same missing `wait` after `kill`
- Rotate `sync-ui.log` only when size is over 1 MiB | rotate at exactly 1 MiB | the prompt says over 1 MiB
- QLockFile with staleLockTime 0 on the window launch only | fcntl.flock, or also blocking --join | kill -9 recovery worked in a probe; headless CLI stays unblocked
- Allow `openUrl` only when the argument is `fromLocalFile` | keep the blanket ban and skip Open logs | the WUI ban stays, and a local folder is not the Tahoe web UI
- Trouble-section checks live in `tests/test_tester_trouble.py` | add them to `tests/test_tester_pages.py` | v0.1.5 already edits that file; a new file keeps the rebase hunk local
- Saved frame is checked before restoreGeometry; file is `window-geometry.json` | restore first, or an ini file | Qt's restoreGeometry moved an off-screen window back on screen and kept the old size
- README and TESTERS "What's new" describe 0.1.6 only | leave the v0.1.4 #30 bullets under the new heading | those sentences stay word for word in Known issues and in `v0.1.4.md`
- Fix round stays sequential in this worktree | one sub-agent per item, or extra git worktrees | items share app.py; the drop-in forbids any other worktree and requires a push of this branch after each commit
