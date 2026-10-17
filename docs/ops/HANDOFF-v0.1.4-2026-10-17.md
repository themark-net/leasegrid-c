# Handoff — v0.1.4 (`build/release-0.1.4`), 2026-10-17

One PR off `origin/main` @ `67a979e` (v0.1.3, #70). Bump PR only: no tag, no release, no merge. Worktree `~/DEVELOP/leasegrid-c/tmp/release-0.1.4`. Qt ran offscreen only (`QT_QPA_PLATFORM=offscreen`, `DISPLAY` unset). Item 3 tests were written by Grok Build headless on nimo and re-verified by hand, mutations included. Decisions: [`AUTONOMOUS-DECISIONS-2026-10-17.md`](AUTONOMOUS-DECISIONS-2026-10-17.md).

## 1. #30 is exactly HTTP 500

**Root cause / risk.** `_http_failure` and `_refresh_http_message` compared to the literal `500` in two places. A later "5xx" or `>= 500` edit could send 501/503 users to #30, and only status 404 had a test. **Change.** `ISSUE_30_HTTP_STATUS = 500` and `is_issue_30_status()` in `backend.py`; both sites use it. `None` (no HTTP response) is never #30. **Tests** (`tests/test_sync_backend.py`):
- `test_issue_30_is_exactly_http_500` covers 400, 499, 500, 501, 502 and 503.
- `test_issue_30_status_none_is_not_30`
- `test_http_failure_names_30_only_for_500`
- `test_add_and_refresh_name_30_only_for_500`, through urlopen on both list and post.
- `test_refresh_http_message_rewrites_only_status_500`

## 2. Android short-code copy names real desktop controls

`Invite.kt` `WORMHOLE_NEXT` said "open the invite card, click Show full join link (advanced)". `app.py` has no invite card. The Folders tab has a **Share invite** button (`QPushButton("Share invite")`), and More → Invite… opens the same dialog. Its control is a checkbox (`QCheckBox("Show full join link (advanced)")`). The line is now "on desktop Sync, click Share invite, tick Show full join link (advanced), and paste that link here; Retry." Tests:
- `tests/test_android_invite_copy.py::test_wormhole_next_names_real_desktop_labels` reads the Kotlin constant and checks that both widgets exist in `app.py`.
- `RecoveryCodecTest.wormholeIsInAppFailNotASilentJoin` asserts the same strings, and that the line does not say "invite card".

## 3. Import dialog minimum-height coverage (#67 follow-up)

Tests only, in `tests/test_sync_ui.py`. Each asserts that the label `minimumHeight() >= heightForWidth` and the dialog `minimumHeight() >= layout.totalHeightForWidth(width)`. They cover these paths:
- missing file
- restore error
- a shorter second failure
- a dialog that was never shown, which takes the `max(_open_width, minimumWidth())` branch

## 4. Log-filter gaps (#68 follow-up)

`packaging/tahoe-log-filter.sh` adds new rules ahead of the existing base32 rule. Existing rules are unchanged, and each new rule only redacts more:
- `[0-9a-fA-F]{32,}`
- `[A-Za-z0-9+/]{16,}={1,2}`
- `[A-Za-z0-9+/]{40,}`
- `[A-Z2-7]{20,}`
- 5+ groups of exactly 4 `[a-z2-7]` joined by `-` or by a space, bounded by non-alphanumerics

`test_legit_lines_survive_the_new_rules` checks that ordinary lines come through untouched, including:
- a path
- a traceback `File` line
- `CannotListenError`
- hyphenated names
- `0x…` addresses
- a UUID
- a version string

| Gap | Outcome |
|---|---|
| uppercase tub-id | fixed: `[A-Z2-7]{20,}`; xfail removed |
| uppercase swissnum | fixed: same rule; xfail removed |
| short fragment (<20) | **kept strict xfail, design limit.** Any floor leaves a shorter fragment. Below 20 the rule eats ordinary words, module names and path parts on the allowlisted lines. Bare fragments on other lines are already dropped. |
| dashes every 4 | fixed: dashed-group rule; xfail removed |
| spaces every 4 | fixed: spaced-group rule; xfail removed |
| base64 | fixed: padded and 40+ unpadded rules; xfail removed. New single-rule cases `base64-padded-short` (28 chars) and `base64-unpadded-40` |
| hex | fixed: `[0-9a-fA-F]{32,}`; xfail removed. New single-rule case `hex-32` |

## 5–9

- **5. Scratch branch.** The remote branch `cursor/50-mutation-proof` was deleted (authorized). It was at `eb79576`.
- **6. Tester pages.** README, `docs/TESTERS.md` and `docs/TESTER-GUIDE.md` drop the "resolve once the tag is pushed" line. They keep versioned asset links, because asset names carry the version and a `releases/latest/download/…` URL would break on the next tag. README and TESTERS add a `releases/latest` link. `tests/test_tester_pages.py` fails if the caveat returns or a page links a version other than `__version__`.
- **7. Version and notes.** `pyproject.toml` and `__version__` are 0.1.4. New `docs/release-notes/v0.1.4.md`, from `TEMPLATE.md`; the previous build is v0.1.3 at `67a979e`.
- **8. Ops files.** This file and the 2026-10-17 decisions file are new, so the shared ops files get no appends. The **Android `versionName` stays `0.4.0-slice-b`**: it is on its own scheme and is not bumped. That is the conservative choice for Tester's question.
- **9. PR body.** The PR body lists every changed file.

## Mutation proofs (revert → red → restore → green)

| Item | Mutation | Result |
|---|---|---|
| 1 | helper `status >= 500` | 7 failed: 501/502/503 cases |
| 1 | helper `status // 100 == 5` | 7 failed |
| 1 | helper `status > 499` | 7 failed |
| 1 | add path `exc.code >= 500` | 4 failed: `names_30` and `name_30` at 501/503 |
| 1 | refresh path `http_status >= 500` | 2 failed: `rewrites_only_status_500` at 501/503 |
| 2 | `Invite.kt` from main ("invite card") | 1 failed: `test_wormhole_next_names_real_desktop_labels` |
| 3 | comment out `label.setMinimumHeight(needed)` | 4 failed: all `*_minimum_heights` |
| 3 | comment out `dialog.setMinimumHeight(height)` | 4 failed |
| 4 | drop the hex rule | 1 failed: `hex-32` |
| 4 | drop the padded base64 rule | 1 failed: `base64-padded-short` |
| 4 | drop the 40+ base64 rule | 1 failed: `base64-unpadded-40` |
| 4 | drop the uppercase rule | 2 failed: `uppercase-tub` and `uppercase-swiss` |
| 4 | drop the dashed-group rule | 1 failed: `separated-dashes` |
| 4 | drop the spaced-group rule | 1 failed: `separated-spaces` |
| 4 | whole filter from main | 6 failed |
| 6 | caveat line back in TESTERS | 1 failed |
| 6 | README AppImage link left at 0.1.3 | 1 failed |
| all | restored | green |

The Kotlin test was not mutation-run on a scratch branch, to avoid creating another remote branch. The host test carries the item 2 proof. Local CI: `PYTHON=/tmp/lg-ff-rawtext-venv/bin/python scripts/ci-local.sh` → PASS (count in the PR body).
