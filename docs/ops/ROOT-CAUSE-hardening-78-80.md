# Root cause, hardening #78 and #80

Base `7ce07856`. Each section is the note written before the fix.

## #78 long paste overflows the short-code check

Symptom: a ~100 KB paste shaped like a short code, then one bad character, throws `StackOverflowError` from `Pattern` instead of a plain banner. Retry never runs.

Cause: `Invite.kt:12` `Regex("^[0-9]{1,3}(-[a-z0-9]+){2,}$")` backtracks on each `-a` group. `Invite.kt:71` calls `wormhole.matches` on the whole paste.

Fix: drop the regex. A linear scan, and pastes longer than 256 characters are not short codes. The banner is `GARBAGE_MSG` with no Next line. Retry reads the field again.

## #78 cancelled join paints over a newer attempt

Symptom: a join cancelled inside `learn()` could be reported as "Couldn't reach your computer." on top of a newer attempt.

Cause: already fixed on this base. `AppModel.kt` `learn` (the `CancellationException` branch) rethrows. `SessionFlow.kt:83` rethrows the same way, so `finishImport` / `join` do not call `show`. `SessionFlowTest.aCancelledJoinPaintsNothing` covers the join path. This lane only extends that test so a later successful join is not left on the failure card.

Fix: no production change. Keep the rethrow. Add the newer-attempt assertions.

## #80 F1 dirty or short join link

Symptom: a paste with `%00`, U+FFFD, a `+` that decodes to a space, an embedded newline, or an empty/short swissnum is treated as a usable furl. `learn()` runs, or the failure is not `MALFORMED_MSG`.

Cause: `Invite.kt:132` `validateFurl` only checks the `pb://` prefix, one slash, and `rest.length < 12`. `fromFragment` (`Invite.kt:106`) already decodes the fragment, so `+` is a space and `%00` is a NUL before this check. Those characters are then ignored.

Fix: reject `%00`, U+FFFD, whitespace, and C0/C1 controls. Require the swissnum (after the last slash, before `#`) to be at least 8 characters. Return `MALFORMED_MSG` and do not call `learn()`. `swissnumswiss` (13) still joins.

## #80 F2 zero-width paste marks

Symptom: a join link with a leading or trailing U+200B or U+FEFF is "That isn't a join link." A paste of only those marks is not the empty-field message.

Cause: `Invite.kt:67` and `Invite.kt:133` use `trim()`. `trim` does not remove U+200B or U+FEFF.

Fix: `stripPaste` strips whitespace and those two marks from both ends, in `parse` and in `validateFurl`. A mark in the middle stays. Marks-only is `EMPTY_MSG`. Retry with the real link calls `learn()`.

## #80 F4 busy cleared by a stale job

Symptom: an older grid job's `finally` sets `busy = false` while a newer join is still running. The phone looks idle.

Cause: `AppModel.kt:784` always clears `busy` in `finally`. `download`, `remove`, and `beginRecoveryImport` share that same `job`.

Fix: one `GridRun` ticket. `launch` and `cancel` bump the ticket before the old job is cancelled. `finally` clears `busy` only when the ticket is still current. `cancel` clears `busy` immediately.

## #80 Retry runs twice

Symptom: a second tap of Retry runs the same action again.

Cause: `AppModel.kt:163` `retryFail` reads `retry` and invokes it. The field is still set, so the next tap runs it too.

Fix: `RetryOnce.pull` clears the slot before the action runs. `dismissFail` and a finished upload clear it. A later failure can arm a new action.

## #80 damaged recovery file escapes the import card

Symptom: a bundle that is not an object, or shares that are not an array, throws `IllegalArgumentException` ("is not a JsonObject" / json array). The screen shows the generic card, not the import card.

Cause: `RecoveryCodec.kt:64` `envelope["bundle"]?.jsonObject` throws when `bundle` is a string. `RecoveryCodec.kt:100` `data["shares"]?.jsonArray` throws when `shares` is a number. Neither throw is `ImportFail`.

Fix: those shapes throw `ImportFail` with `IMPORT_FAIL_MSG` and a Retry next line. Nothing is imported.

## #80 phone strings say friendnet

Symptom: the threat card, empty Folders line, remove sheet, discard line, settings transport line, forget-downloads, and the write chips say "friendnet".

Cause: `SyncApp.kt:58` ("Friendnet trust U+2014 ..."), `SyncApp.kt:228`, `SyncApp.kt:352`, `SyncApp.kt:367`, `SyncApp.kt:414`, `AppModel.kt:467`, `FolderWrite.kt:8` `PENDING`, `FolderWrite.kt:9` `LANDED`.

Fix: shared-folder wording. Chips are "Not in the shared folder yet" and "In the shared folder". They do not say the file is on the computer. Design packs 55-59 stay as they are.

## #80 FlowHost one-liners and the SyncApp guard

Symptom: clearing `inviteText`, returning null from `learn`, or dropping the Retry lambda in the `FlowHost` object changes nothing a test sees. The banned-word guard only reads the Invite section of `SyncApp.kt`, so the threat card can say friendnet again.

Cause: `AppModel.kt:91` delegations are one line each and were not pinned. `tests/test_android_invite_copy.py` `_invite_section` stops at the welcome fail card.

Fix: pin the five delegations (mutants M4c, J4a, J1c, N4b, N4d). Scan every string literal in `SyncApp.kt`.

## #80 generic grid card names the class and Retry does nothing

Symptom: an unexpected grid failure shows "could not complete that. IllegalStateException". Retry dismisses the card and does not run the block again.

Cause: `AppModel.kt:780` puts `exc.javaClass.simpleName` on the card. `AppModel.kt:783` arms `{ }`.

Fix: the card is "could not complete that." The class goes to the log. Retry calls `runGrid(label, block)` once. A second tap does not, because `pull` already cleared it.

## #80 download next line names the class

Symptom: a failed download's next line is "Retry. (IllegalStateException)".

Cause: `AppModel.kt:420` appends `exc.javaClass.simpleName` to the next line.

Fix: when `AndroidGrid.dispatch` throws, the Kotlin next line is "check network / free space; Retry." and the class is logged. Retry still calls `download`. This fix covered only that Kotlin catch. Python `dispatch` does not throw, and its own fallback still added the class. See "Reviewer B3" below.

## Em dash and en dash in guarded literals

Symptom: the banned-word guard accepts U+2014 and U+2013. The threat card and the fail title still use an em dash, including the lines the friendnet edit did not rewrite.

Cause: `tests/test_android_invite_copy.py` `_FORBIDDEN` has no dash. After the friendnet edit, `SyncApp.kt` still has em dashes on the storage-proofs, transport, and recovery threat lines, and on `FAIL U+2014 ${banner.message}` (em dash written as its code point).

Fix: `_banned` flags U+2014 and U+2013. Those literals use a colon instead.

## Design 61 overclaims the guard

Symptom: the Tests line says the guard covers every user-visible string. It does not. Chips live in `FolderWrite.kt`. Recovery copy lives in `RecoveryCodec.kt`.

Cause: `docs/design/61-ANDROID-INVITE-JOINLINK.md` line 18. The guard scope line under it names the real files, and the Tests line does not match it.

Fix: the Tests line states the same scan as the guard scope line: string literals in `Invite.kt`, `SessionFlow.kt`, `AppModel.learn()`, and every string literal in `SyncApp.kt`.

## Introducer split evades the scan (mutant K3c)

Symptom: the introducer check matches the contiguous word inside one literal. `"Intro" + "ducer"` and `"intro-\nducer"` are not caught.

Cause: `_LITERAL.findall` splits the concatenation into two literals. `_FORBIDDEN` then searches each one for `introducer`. A newline or hyphen inside one literal also breaks the contiguous match. `test_introducer_unreachable_is_never_on_screen` looks for the exact phrase "introducer is unreachable".

Fix: join literals that are only separated by `+`, then drop whitespace, a break hyphen, and `\n` escapes before looking for `introducer`. The per-literal exact scan still misses the samples. The new scan catches them.

## Recovery import cancel, already implemented

Symptom: the design note did not say what a cancel during import does.

Cause: behavior is already on this base. `SessionFlow.kt:83` rethrows `CancellationException` before `finishImport` reaches `save`. An unreachable learn returns null, and `finishImport` still saves, then shows `IMPORT_SAVED_MSG`.

Fix: no production change. Record the PM sentence in design 61. A behavior test locks cancel-saves-nothing and a later import.

## Reviewer B1: dash characters on added doc lines

Symptom: Reviewer found U+2014 on four added lines: HANDOFF lines 37 and 99, ROOT-CAUSE lines 65 and 97. Each one quotes an old string that had an em dash.

Cause: the dash ban was applied to guarded Kotlin literals, not to the docs that quote the old literals. Nobody grepped the added doc lines.

Fix: write the dash as its code point, `U+2014`, in those quotes. `git diff 7ce07856 | grep -P '^\+.*[\x{2013}\x{2014}]'` is empty after the fix.

## Reviewer B3: the download next line still names the class

Symptom: Reviewer reproduced a failed download whose next line is "check network / free space; Retry. (FileNotFoundError)". The handoff said the class name was gone.

Cause: the Kotlin `catch` in `AppModel.download` only runs if `AndroidGrid.dispatch` throws. `leasegrid_read.dispatch` never raises across the boundary. It returns JSON, and the phone shows its `message` and `next` as they are. `leasegrid_read.py:58` (the `OSError` branch) appended `(%s)` with the class name. `leasegrid_read.py:65` (the last-resort branch) put the class name on the message: "could not complete that. ValueError". The earlier Kotlin fix changed a path that real failures do not take.

Fix: both branches return the plain copy and log `dispatch <op> failed: <Class>` to the `leasegrid_read` logger. The log line has the op and the class only, never the payload, so no furl reaches it. `android/pytests/test_dispatch_copy.py` makes the real function fail (a download whose folder is missing, and a timeout that is not a number) and checks the returned copy.

Not changed: `lg_intro.py` puts a class name on the learn next line. `AppModel.learn()` only logs that result and never shows it, so it does not reach the screen. `lg_tahoe.py:404` appends the last storage error message (copy text, not a class) to the download next line. That is listed as a follow-up.

## Reviewer B2: "Retry runs exactly once" had no behavior test

Symptom: Reviewer mutant K15 (`retryFail` arms the action again after `pull`, so a double tap runs it twice) and mutant K16 (the `runGrid` error handler is swallowed, so there is no card and no Retry) both survived all 61 Kotlin tests.

Cause: the Retry tests never ran `AppModel`. `GridFailTest` checked the text of `AppModel.kt` and ran a local copy of the retry logic. `RetryOnceTest.appModelPullsTheRetryBeforeItRuns` looked for `retries.pull()` in the source. `AppModel` could not be built in a JVM test: it took the grid, `viewModelScope`, `Dispatchers.IO`, and the files dir from Android with no way to swap them.

Fix: `AppModel` gets an internal constructor that takes `AppSeams` (files dir, scope, IO context, grid dispatch). The public `AppModel(app)` passes the defaults, which are the old values, so the app is unchanged. `AppModelRetryTest` builds a real `AppModel` with a fake grid, makes a folder load and a download fail, checks the card and its Next line, taps Retry twice, and counts grid calls. The source-text tests and the local copy are deleted.

## Reviewer follow-up 1: cancel and error do not prove busy clears

Symptom: mutant K9 (`GridRun.cancel` does not clear busy) survived. No test checked busy after an error either.

Cause: `GridRunTest` only covered the stale-ticket finally and a clean finish.

Fix: no production change. `GridRunTest.cancelClearsBusyWhileTheJobIsStillRunning` and `.busyClearsAfterAnErrorAndTheErrorReachesTheHandler` lock both.

## Tester pass on 2be4d7e

Tester FAILed 2be4d7e with its own list. Tester's mutant bodies are not in the repo. Each mutant below is my own patch written from Tester's one-line description; `tmp/mut2.py` on the box holds them, and the handoff has the table.

### Tester B2: double tap and swallowed error handler (R2, R3, R4, F4e, F4f)

Symptom: Tester mutants R2, R3, R4 (a double tap on Retry runs the action twice) and F4e, F4f (the error handler is swallowed) survived 2be4d7e.

Cause: same as Reviewer B2. Nothing ran the real `AppModel`. The Reviewer B2 fix (`AppSeams` and `AppModelRetryTest`) came after 2be4d7e.

Fix: no further production change. `AppModelRetryTest` and `AppModelFlowTest` drive the real model. My versions of each mutant go red (handoff table).

### Tester B3: class names through the bridge at every call site

Symptom: Tester asked for proof that a class name never reaches the screen through `AppModel.kt` lines 252, 432, 576 and 632 (2be4d7e numbering: folder load, download, add, remove) when the bridge fails, and flagged `lg_tahoe.py:404`.

Cause: the Python fix (Reviewer B3) covered `leasegrid_read.dispatch`. `lg_tahoe.fetch_share` still put the last storage error on the next line as `(...)`. That text comes from any server and can carry a class name or a second sentence. On the Kotlin side only the download site had a test.

Fix: `fetch_share` logs the last error to the `lg_tahoe` logger and returns the plain next line. A pytest makes `fetch_share` fail with a refusal whose text names `ConnectionRefusedError` and checks the copy and the log. `AppModelFlowTest` makes the bridge throw an exception whose text names `FileNotFoundError`, `Errno` and a furl at all four sites (folder load, download, add, remove) and checks the card has none of them.

### Tester T1: Cancel during an import did not cancel it

Symptom: design 61 line 22 said cancelling an import saves nothing. On the Import screen, Cancel and the back arrow called `goWelcome()`. Cancel stayed enabled while busy. The import kept running, saved, and moved the phone from Welcome to Folders.

Cause: the sentence described `SessionFlow`'s own cancellation (a newer job cancels the older). No UI control cancelled the job.

Fix: new `AppModel.cancelImport()` cancels the grid job, clears Retry, and goes to Welcome. Cancel and the back arrow call it, so Cancel stays enabled while busy on purpose. `withContext` checks for cancellation when the decode returns, so `finishImport` and `save` never run. `AppModelFlowTest.cancelOnImportStopsTheImportSavesNothingAndStaysOnWelcome` queues the decode, cancels, drains, and checks: Welcome, no session, nothing in the store, no grid call, busy off. Design 61 now says what the buttons do.

### Tester S1: a hostile recovery file could crash the phone

Symptom: a deeply nested JSON file, a file with huge scrypt `n`, `r` or `p`, or a huge file could end in an Error (stack overflow or out of memory) or a very long hang instead of the import card.

Cause: `RecoveryCodec.decode` parsed any depth, passed any scrypt params straight to BouncyCastle (memory is 128 * r * n bytes), and defaulted a non-integer `n` to 2^15. `MainActivity` read the whole picked file with `readBytes()`. A catch of `Exception` does not catch an `Error`.

Fix: `decode` rejects files over 1 MiB (`MAX_RECOVERY_BYTES`). A depth scan (brackets inside strings do not count) rejects nesting over 32 before parsing, for the envelope and the decrypted bundle. scrypt `n` must be a power of two in 2..2^20, `r` in 1..32, `p` in 1..16, and 128 * r * n at most 64 MiB; a present but non-integer value is a bad file. Desktop writes n=2^15, r=8, p=1 (32 MiB), which still imports. New `readAtMost` reads a stream up to a cap and throws `TooLarge` past it. `MainActivity` uses it for the recovery file (1 MiB) and an added file (64 MiB), and `DogfoodIntents.readRecoverySeed` uses it too. A too large recovery file shows the import card; a too large added file shows "could not read this file." with "pick a file under 64 MB.". The class name is dropped from both read failure next lines and logged.

### Tester S2: marks inside the link

Symptom: U+200C, U+200D and U+2060 were not stripped, and U+200B or U+FEFF inside the link (Reviewer follow-up 4) made it MALFORMED.

Cause: `stripPaste` trimmed only the ends, and only U+200B and U+FEFF.

Fix: `stripPaste` drops U+200B, U+200C, U+200D, U+2060 and U+FEFF anywhere, then trims. None of them can be part of a furl or a join link.

### Tester S3 and S4: one furl check

Symptom: the recovery file's furl was only checked for `pb://`. `validateFurl` accepted an empty tub id (`pb://@host/swiss`) and a furl with no location (`pb://tub/swiss`, `pb://tub@/swiss`).

Cause: two checks grew separately, and `validateFurl` never split the authority.

Fix: `validateFurl` is `internal` and `RecoveryCodec.parseBundle` calls it (an `InviteFail` becomes the import card). An empty tub id is MALFORMED. No `@` or nothing after it is NO_ADDRESS ("That link is missing your computer's address."), which is the advice that fits.

### Tester S5: source grep and constant tests

Symptom: `GridFailTest` asserted two constant strings. The FlowHost delegation pins used substring matches, so a longer line still passed (Reviewer follow-up 2). `unexpectedGridCard` had no red-first.

Fix: `GridFailTest` is deleted; `AppModelFlowTest` checks the same copy through the real model when the bridge throws. The pins in `tests/test_android_invite_copy.py` now match whole stripped lines. Behavior tests through the real model (join saves what learn returned, Retry after a failed join) kill N4b, N4d, J1c and M4c on their own. A mutant that puts the class name back into `unexpectedGridCard` goes red.

### Tester mutants on Invite and recovery (H78b, H78d, H78e, F1e, F1i, C3, C4)

Cause: no test sat exactly at the 256 short code cap, used a C1 control, hid a short swiss number behind `#`, or broke a recovery bundle's shares or folders one field at a time.

Fix: tests only. A short code of exactly 256 chars is a short code; 257 is not. U+0080, U+0090, U+009C and U+009F are MALFORMED. `pb://tub@host/ab#swissnumswissnum` is MALFORMED. Recovery shares must be three ints with 1 <= n <= h <= t <= 256 (new check, desktop writes [2,3,3]); a blank name, a cap without `URI:`, or a missing field is the import card.

### Tester A5, A6, A8, A9, U8

Cause: nothing checked that `cancelDownload` stops the job, and the copy guard read only `AppModel.learn()`, so friendnet or a dash in any other AppModel banner passed.

Fix: `AppModelFlowTest.cancelDownloadStopsItAndItNeverLandsOnReady`. The copy guard now scans every literal in `AppModel.kt` and `MainActivity.kt`. Both files pass today.

### Introducer E5 to E12: spellings the guard missed

Cause: the guard read raw literals. It saw `"a" + "b"` joins only.

Fix: the guard now reads what `Text()` would show: `\uXXXX` escapes decoded, soft hyphen and zero-width marks removed, common Cyrillic look-alikes folded to Latin, `${"x"}` templates unwrapped, literals joined across `+`, `.plus(` and `append(` in `buildString`, and runs of 4 or more char literals joined. It checks introducer, friendnet and wormhole on the squashed text. Not caught: a word split across variables (`val a = "intro"`; `Text(a + b)`) and text built at run time. That is a handoff follow-up.
