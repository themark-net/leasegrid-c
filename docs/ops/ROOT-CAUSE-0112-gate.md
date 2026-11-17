# Root cause: v0.1.12 gate FAIL at 530dd52 (Tester and Reviewer)

## 1. Why the #87 lock mutants survived

The #87 tests at 45e32da checked the shape of the lock code, not its timing or its order:

- `test_transient_permission_error_on_a_stale_lock_still_takes_it` failed the Python read only once. One failed read is absorbed by any retry count of 2 or more, by any wait, and even by a probe placed before tryLock that retries. So tries 3 to 1, sleep 50 ms to 0 and probe moved before tryLock all passed.
- No test drove the branch after the second tryLock with a rival that writes its PID late, so dropping the PID guard passed.
- No test made the file vanish during the reads, so treating a missing file as unreadable passed.
- The Windows ACL tests use a real deny that never clears, so they cannot tell 1 try from 3.

Fix: `tests/test_sync_lock_retry_order.py` drives `acquire_instance_lock` with a held lock (every tryLock fails) or a real stale lock, and scripts what each Python read of the lock returns: denied for N reads, denied for 80 ms of wall time, missing, or a PID that appears late. Each rule has a test that fails when that rule is broken (table in `docs/ops/HANDOFF-0112-release-prep.md`).

## 2. B2: false "could not read" and false "already running"

- `_lock_path_problem` mapped any stat `OSError` other than `FileNotFoundError` to "could not read its lock file", before tryLock. On Windows a file a rival is deleting (delete pending) stats as access denied, so a lock Qt could take was refused. Now any stat error returns None and tryLock decides. A directory or a mode-000 file is still refused, because those come from a stat that worked.
- After the second tryLock failed, a lock that vanished during the reads returned False, which the app shows as "already running", although the holder had just quit. Now `_lock_read_state` returns missing, and `acquire_instance_lock` tries tryLock once more. Qt's O_EXCL create still allows only one winner.

## 3. Release prep missing

The gate pin had no version bump, notes or Installers run, because release prep was done after the gate. From v0.1.12 on, prep lands before the gate, so the gated SHA is the shipped SHA.

## 4. MainActivity deny wiring

`MainActivity.kt` had the refusal routing inline, so only a source grep covered it. The routing is now `AppModel.onScanResult(contents, missingCameraPermission)` with a JVM test. The permission check itself (`ContextCompat.checkSelfPermission`) and the extra lookup stay in the Activity. A real Activity test needs Robolectric plus a way around `LeasegridApplication` starting Chaquopy Python, which is not cheap; the emulator check covers it.
