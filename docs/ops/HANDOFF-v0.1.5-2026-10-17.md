# Handoff — v0.1.5 (`build/release-0.1.5`), 2026-10-17

This is one PR off `origin/main` @ `ef17434` (v0.1.4, #71, tagged). Bump PR only: no tag, no release, no merge.
- Worktree: `~/DEVELOP/leasegrid-c/tmp/release-0.1.5`.
- Qt ran offscreen only (`QT_QPA_PLATFORM=offscreen`, `DISPLAY` unset).
- Input: Tester's PR #71 review (pullrequestreview-5556751547) and the evidence in `/workspace/leasegrid-dogfood/pr71-v014-5f4d750/` on the box.
- Decisions: appended to `AUTONOMOUS-DECISIONS-2026-10-17.md`. No other PR was open.

## 1. LEAD: glued hex + base32 leak (first commit, `da3a950`)

**Root cause.** v0.1.4 ran `[0-9a-fA-F]{32,}` before `[a-z2-7]{20,}`. When a base32 secret was glued straight onto a 32+ hex run, the hex rule also took the secret's leading `[a-f2-7]` chars. That left fewer than 20 chars, so the base32 rule no longer matched. v0.1.3 did not leak here.

**Fix.** The base32 rule now runs first. The base32, hex and uppercase rules each redact the whole `[A-Za-z0-9]` token that holds their run, so no rule leaves a remnant of the same token.

**Test.** `test_glued_hex_and_base32_secret_never_leaks[20|22|26|32]` builds 2000 glued lines per secret length from seed `20261017`. It counts any surviving 8-char window, of either the secret or the hex.

Leaks per 2000 lines:

| Length | ef17434 | v0.1.3 secret | v0.1.3 hex | after |
|---|---|---|---|---|
| 20 | 753 | 0 | 1991 | 0 |
| 22 | 99 | 0 | 1986 | 0 |
| 26 | 2 | 0 | 1986 | 0 |
| 32 | 0 | 0 | 1989 | 0 |

v0.1.3 never redacted hex, so its hex column is high by design.

Tester's own probes re-run against this filter:
- `probe_hexglue.py`: 22/26/32 chars go from 97/1/0 to 0/0/0 per 2000.
- `probe_newleak.py`: `hex32 + secret(22)` goes from 14/200 to 0/200.

## 2. Wider shapes and tuning

| Item | Outcome |
|---|---|
| unpadded base64url | **done.** Rule `[A-Za-z0-9_-]{40,}`. Seeded test: 0/200 (186/200 at ef17434). Tester's `base64url-raw32-nopad`: 140/200 → 0/200 |
| mixed-case base32 | **done, floor 32.** Rule `[A-Za-z2-7]{32,}`, token-expanded. Seeded test: 0/200 (200/200 before). Tester's `mixedcase-b32`: 200 → 0. 20–31 chars is **not covered**: it looks like CamelCase class names |
| dashed 8-char groups | **done.** Exactly 8, 3+ groups, bounded. Seeded test: 0/200 (200/200 before). Tester's `dashed-8`: 200 → 0 |
| over-redaction tuning | **skipped** (redact-more wins). Each exemption reopens a leak: digitless 4-chunked base32 (≈0.13% of draws); base64 with `/` (≈half of random draws); 40-hex is also a 20-byte hex secret; 20+ uppercase is indistinguishable from an uppercase tub-id. All four are pinned as strict xfails with reasons in `test_accepted_over_redaction_is_documented`, so a future un-blanking XPASSes and turns red. |

New legit lines, which must pass unchanged:
- `an-ok-ci-run-on-the-box`, which kills F9
- `_start_magic_folder_and_wait_for_api`
- `TwistedDeprecationWarning` and `UnhandledErrorInDeferred`
- `tahoe-lafs magic-folder leasegrid-sync`
- `tahoe-lafs-magic-folder`, which kills a widened dashed-8 rule

Still a design limit: `short-fragment` (<20). Tester's `short-16` still leaks 200/200, as documented.

## 3. Survivors killed

- **F9** (dashed-4 widened to 1–4-char groups): killed by the short-dashed legit line.
- **T4** (reworded caveat): `caveat_hits()` checks prose with link targets stripped, using these patterns:
  - `resolv*`
  - `once … tag*/publish*/releas*/push*/cut`
  - `until/after/when … tag*`
  - `404`
  - `not yet live/available/…`

  `test_caveat_guard_catches_known_rewordings` covers 7 listed rewordings, including Tester's T4. It is a keyword guard: wordings without those keywords (for example "Coming soon") still pass.
- **U7** (unshown-branch width), two tests:
  - `…_unshown_height_is_computed_at_branch_width` asserts the exact minimum height at `max(open, minimumWidth)`, and that it is smaller than at half the width.
  - `…_unshown_respects_larger_minimum_width` sets a minimumWidth above the open width. It kills "ignore minimumWidth", which Qt clamping had masked.

## 4–6. Notes, bump and ops

- The README and TESTERS #30 wording now says users see no change, and uses "Other HTTP errors". It names the no-status case ("Magic Folder daemon is not reachable."). `test_tester_page_says_other_http_errors` guards this.
- `docs/release-notes/v0.1.5.md` comes from TEMPLATE and says the v0.1.4 notes overstated #30. `v0.1.4.md` gets one italic correction line under the #30 bullet.
- `pyproject.toml` and `__version__` are 0.1.5. The tester pages link the v0.1.5 assets, and the previous build is v0.1.4 at `ef17434`.
- The Android `versionName` stays `0.4.0-slice-b`, as recorded in v0.1.4.

## Mutation table (revert → red → restore → green)

| # | Mutation | Result |
|---|---|---|
| G1 | whole filter = ef17434 | 6 failed: glued 20/22/26, base64url, mixed, dashed-8 |
| G2 | base32 rule moved back to last, expansion kept | **survived: equivalent mutant.** Token expansion makes the order irrelevant; the order is kept as defense in depth |
| G3 | base32 first but not token-expanded | 4 failed: glued 20/22/26/32, hex remnant |
| G4 | no token expansion anywhere | 4 failed |
| S1 | drop the base64url rule | 1 failed (181/200 leaked) |
| S2 | drop the mixed-case rule | 1 failed (200/200) |
| S3 | drop the dashed-8 rule | 1 failed (200/200) |
| S4 | base64url floor 40 → 20 | legit corpus red |
| S5 | mixed-case floor 32 → 20 | legit corpus red |
| S6 | dashed-8 widened to 3–8-char groups | legit corpus red |
| F9 | dashed-4 widened to 1–4-char groups | legit corpus red |
| T4 | "These links work once v0.1.5 is tagged." in README | 1 failed |
| T4b | "Asset links resolve after the release is cut." in GUIDE | 1 failed |
| T4c | "Downloads are missing until v0.1.5 is tagged." in TESTERS | 1 failed |
| W1 | "Other errors say" restored in TESTERS | 1 failed |
| U7a | unshown width `max(_open_width // 2, minimumWidth)` | 2 failed |
| U7b | unshown width ignores minimumWidth | 1 failed |
| all | restored | green |

Local CI: `PYTHON=/tmp/lg-ff-rawtext-venv/bin/python scripts/ci-local.sh` → PASS (count in the PR body).

## PR #72 review fixes (Tester, pullrequestreview-5556979371)

- **B1:** README.md:31 and docs/TESTERS.md:32 now say the **v0.1.4** notes made #30 sound user-visible. `test_tester_page_says_other_http_errors` pins the version. A grep found no other occurrence.
- **Follow-up 1** (deleting the main base32 rule passed the suite):
  - Seeded `test_short_lowercase_base32_never_leaks[20..31]`, 100 runs per length.
  - `test_tahoe_cap_keys_never_leak[DIR2|CHK]` uses Tester's `URI:DIR2:{26}:{52}` and `URI:CHK:{26}:{52}:3:10:1234` shapes.
- **Follow-up 2** (hex and uppercase expansion not pinned): `test_rule_redacts_the_whole_token[hex|uppercase]` checks 50 seeded tokens with short affixes outside each rule's alphabet. The full line must read `id=REDACTED end`.
- **Overclaim:** the caveat-guard comment and test name no longer say "however worded"; they say "known rewordings" and state the guard's limit.

| Mutation | Result |
|---|---|
| R4: delete `[A-Za-z0-9]*[a-z2-7]{20,}[A-Za-z0-9]*` | 14 failed (b32 20–31 ×12, DIR2, CHK) |
| O3: hex rule without token expansion | 1 failed (`whole_token[hex]`) |
| O4: uppercase rule without token expansion | 1 failed (`whole_token[uppercase]`) |
| B1: "v0.1.5 notes made" put back in README | 1 failed |
| restored | green |

## Remaining follow-ups (not in v0.1.5)

1. **snake_case 40+ over-redaction.** `[A-Za-z0-9_-]{40,}` blanks long identifiers such as `_get_magic_folder_participants_for_collective`, the one line on Tester's 38-line corpus newly blanked against v0.1.4. Options: accept it as a fifth strict xfail, or require at least one digit or uppercase character in the base64url run. The digit/uppercase option needs a leak measurement first.
2. **`docs/release-notes/v0.1.4.md` differs from the published v0.1.4 release body** by its one correction line. Either edit the published release body to match (needs approval) or accept the drift; v0.1.5.md carries the correction.
3. **v0.1.4 gaps, unchanged:**
   - separators other than `-` or space at 4 chars, and any separator every 5–7 chars;
   - percent-encoded base64 in URLs, and JSON-escaped `\/` base64;
   - secrets split across a line wrap into pieces under 20 chars;
   - lengths below each cutoff: b32 under 20 (the short-fragment xfail), hex under 32, mixed under 32, b64url under 40.
4. **Caveat guard misses 6 of Tester's 10 rewordings.** Examples: "Coming soon", "available shortly after release", "may not work until CI publishes them". A positive check, that a page says nothing about link timing, would be stronger than more keywords.
5. **Base32-last ordering is an equivalent mutant** (Tester confirmed: 0 leaks in every probe). The order is kept only as a backstop.
