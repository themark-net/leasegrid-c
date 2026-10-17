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
- Keep Qt's default stale lock time by deleting setStaleLockTime(0) | pass 30000 explicitly | the default is already 30000 ms; the bug is that 0 turns staleness off
- Age empty, garbage, and foreign locks by 120s with os.utime | sleep 30s in the test | the file only has to be older than Qt's 30s stale time
- Foreign lock is three lines (pid, app name, other hostname) | rewrite a live lock's hostname and boot id | a probed 3-line other-host file older than 30s is taken; a fresh one is not
- Live-holder refusal is checked as soon as the first process prints WINDOW_SHOWN | wait 35s past the stale time | the holder is alive and the lock is younger than 30s; a probe also kept an aged live lock refused
- Title-bar check is an 80 by 28 grab at the top-left | require the whole frame inside the screen | the offscreen desktop is 800x600 and the round-trip window is 1000x980, so the full strip cannot fit
- A left-of-screen frame is pulled into availableGeometry when Qt leaves it there | rely on Qt's clamp alone | offscreen clamped y=-650 to y=18 but left x=-196 in place
- Tray menu is built even when the platform has no tray icon | skip the tray-quit test offscreen | offscreen has no system tray; an unshown menu does not change the window, and Quit is the same action
- A file path says "That path is not a folder" | reuse the missing-folder banner | the file is on the computer, so "not on this computer any more" would be wrong
- Geometry read catches Exception | only ValueError, RecursionError, OSError, and TypeError | a missing geometry key is a KeyError and must fall back too; RecursionError is a RuntimeError
- Geometry write-failure test patches os.replace | a read-only directory | a read-only directory does not block rename on Windows
