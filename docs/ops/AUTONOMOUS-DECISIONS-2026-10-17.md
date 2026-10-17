# Autonomous decisions — 2026-10-17

Decision | Alternative rejected | Why
---|---|---
v0.1.4 as one PR off `main` @ `67a979e` | one PR per item | Grok Bot asked for one gate
#30 is exactly HTTP 500, via `is_issue_30_status()` / `ISSUE_30_HTTP_STATUS` in `backend.py` | treat 5xx as #30 | #30 is Magic Folder's 500; a 501/502/503 is another failure and must not send testers to #30
Android short-code Next line: "click Share invite, tick Show full join link (advanced)" | keep "open the invite card" | app.py has no "invite card"; the Folders tab button is `Share invite` (More → Invite… opens the same dialog) and the control is a checkbox, so "tick"
Android `versionName` stays `0.4.0-slice-b` (own scheme, not bumped to 0.1.4) | bump to 0.1.4 | conservative answer to Tester's question: the APK is not a release asset and versions its slices separately; the version test does not cover it
Log filter: add hex, padded/unpadded base64, uppercase base32 and 4-char-chunked rules ahead of the base32 rule; existing rules unchanged | lower the base32 floor below 20 | each new rule only redacts more; a lower floor eats ordinary words/paths and still leaves a shorter fragment
Short base32 fragment (<20 chars) stays a strict xfail as a design limit | redact any short run | indistinguishable from words, module names and path parts on the allowlisted lines; non-allowlisted bare fragments are already dropped
Tester pages keep versioned asset links (v0.1.4) and drop the "resolve once tagged" caveat; add a `releases/latest` link | point assets at `releases/latest/download/…` | asset file names carry the version, so a `latest/download` URL would break on the next tag; `tests/test_tester_pages.py` keeps the pages on `__version__`
New ops files (HANDOFF-v0.1.4-2026-10-17.md, this file) | append to HANDOFF-ff-0111 / AUTONOMOUS-DECISIONS-2026-10-16 | no append conflicts on the shared ops files
Kotlin mutation proof not re-run on a scratch branch | push another scratch branch | the only authorized branch delete was `cursor/50-mutation-proof`; the host test (`tests/test_android_invite_copy.py`) carries the mutation proof and the Kotlin test runs green in the debug APK job
