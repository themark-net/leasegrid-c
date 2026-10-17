# Autonomous decisions — v0.1.7 batch

Format: choice | alternatives | why

- Lead implements items in order on this worktree | parallel sub-agents in sibling worktrees | items share src/leasegrid_sync and tests, commits must stay ordered, and the drop-in forbids sibling directories
- Signals call MainWindow.quit() directly | route them through the invite-close dialog | a service manager must not wait on a dialog nobody can click
- Windows process test covers SIGBREAK only | also send CTRL_C_EVENT or SIGTERM | SIGTERM is TerminateProcess, SIGHUP does not exist, and CTRL_C_EVENT hits the whole console. The handler still installs SIGINT and SIGBREAK.
- Windows daemon tree kill is CTRL_BREAK_EVENT then taskkill /T /F | a job object, or TerminateProcess on the leader only | taskkill /T /F is the tree kill Windows actually ships; the group flag is set only on daemons popen_hidden starts
- A second --join while already joined shows "Leasegrid Sync is already on a friendnet. This invite was not opened." and drops the invite | auto-join, or open a second grid | there is no add-another-grid path
- POSIX handoff connects to the QLocalServer socket in the temp dir | an in-process QLocalSocket | a QCoreApplication in the caller would break later UI tests. Windows sends through a helper process so the invite stays on stdin
