# Autonomous decisions: lg-018-fixes-1031

Decision | Alternative rejected | Why
--- | --- | ---
After the four sourced rows, take the "Deferred to v0.1.8" list in docs/HANDOFF-v0.1.7.md as the next gaps | stop as soon as the four sourced rows are recorded | the loop says keep taking the next MVP gap that fits the lane, and v0.1.8 did not ship that list
Issue #30 is recorded and not changed | try to fix the Magic Folder HTTP 500 | the drop-in says #30 is parked
Unsigned installers stay a known issue | write a signing workaround | signing keys and Mark are required
Do not lower log-filter length floors or add separator rules | redact shorter tokens and more separators | the short-fragment note says a lower floor eats ordinary words, module names, and path parts
Do not implement GetNamedPipeServerProcessId | a ctypes call tested with a fake | this host cannot run that Windows API, and the v0.1.7 design says the lock plus the user-only ACL is the defense
Do not adopt an orphaned Tahoe, rotate daemon logs while the process holds them, or add a new cross-user rule | pick one behavior and ship it | each one needs a product or ADR choice that is not written down
A second `--join` while the user is typing is already the v0.1.7 Yes/No question | build another prompt | the field stays until Yes, and the default is No
A 5-second-old other-host lock is already taken (probe ok=True in 0.001s) | add a test that only restates setStaleLockTime(2000) | v0.1.7 already set the stale time to 2s, and the existing foreign-host test covers takeover. No drive-by test
An empty owned directory or a mode 000 file at the lock path, older than 2s, is removed and the launch proceeds | a new error string that leaves the path in place | "already running" forever is the stuck failure, and 2s is the existing PID-less gate. A non-empty directory, a young file, and another user's path stay
Pregate not run | wait for the runner or run ci-local anyway | `pgrep -f 'Runner[.]Worker'` was not empty at the end of the lane
