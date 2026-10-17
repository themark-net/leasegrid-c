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
**v0.1.5** (`build/release-0.1.5`, off `ef17434`). No other PR was open, so these rows are appended here instead of going in a `-b` file. | |
Glued hex+base32 leak: run the base32 rule first, and have the base32, hex and uppercase rules eat the whole `[A-Za-z0-9]` token | only reorder the rules | reordering alone leaves a sub-32 hex remnant when the base32 rule eats the hex tail. Token expansion closes both directions; with it, rule order no longer matters (that mutant is equivalent)
base64url: `[A-Za-z0-9_-]{40,}` (no `/`) | include `/` | with `/` the rule would eat paths that contain `-` (`…/leasegrid-c/…`)
Mixed-case base32: floor 32 | floor 20 | 20–31 chars looks like CamelCase class names (`ConnectionRefusedError`); 32 is the tub-id/swissnum length
Dashed 8-char groups: exactly 8, 3+ groups | 3–8-char groups | variable groups eat hyphenated names such as `tahoe-lafs-magic-folder`
Over-redaction tuning skipped (4-letter-word runs, separator-free 40+ paths, 40-hex SHAs, 20+ uppercase constants), kept as strict xfails with reasons | spare those shapes | each exemption lets a real secret shape through (digitless 4-chunked base32 ≈0.13%, base64 with `/` ≈half of draws, 40-hex = 20-byte hex secret, uppercase base32 tub-id). Redact-more wins
Tester-page caveat guard: regex families (`resolv*`, `once … tag/publish/release/push`, `until/after/when … tag`, `404`, `not yet live`) over prose with link targets removed | exact phrases | PR #71 T4: a reworded caveat passed the old guard
v0.1.4 release notes get a one-line italic correction under the #30 bullet only | rewrite v0.1.4.md | keeps the published meaning; v0.1.5 notes carry the full correction
