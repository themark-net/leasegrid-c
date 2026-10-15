# leasegrid-c — pending handoff (CEO pause dated 2026-09-24 ~11:20pm PT) — main @ `5ac69aa`

**2026-10-09 handoff refresh:** Docs-only update of this file to `main` @ `5ac69aa`. Not Feature GO. Not a new RELEASE. #44 (P4-B Android write) shipped after the 2026-09-24 pause via PR #45 (design pack 55–59, `1c327c9`, merged 2026-10-04) and PR #46 (`cursor/android-p4b-write-sync-7258`, tip `6e7bf01`, merged 2026-10-04 as `5ac69aa`).

**Purpose:** Freeze current queue + design map so another model/harness can take over without bot chat history.

**Repo tip:** `main` @ `5ac69aa` (merge of PR #46, 2026-10-04; PR tip `6e7bf01`). P4-B Android write sync issue #44 is SHIPPED. Design pack 55–59 landed in PR #45 (`1c327c9`, merged 2026-10-04). Shell polish #38 / invite #32 remain shipped at `83b3e66` (ancestor). Nimo checkout: `~/DEVELOP/leasegrid-c` (canonical; lab secrets under `lab-private/` if present).

**Org posture (dated 2026-09-24):** PAUSED. No auto RELEASE / Build / Cursor implement until founder says go. **Public marketing / loud v\* HOLD** (quiet F&F `v0.1.0` already cut). Marketing silent. This paragraph is the 2026-09-24 pause. It is not a new RELEASE. #44 shipped after that pause via PR #45 and PR #46. That ship does not lift the pause.

**2026-10-14 docs slice (branch `build/ff-0111-testers-doc`, merged as PR #48, `d326c5b`):** Friends-and-family tester page [`TESTERS.md`](TESTERS.md), linked from the README. Draft notes [`release-notes/v0.1.1-DRAFT.md`](release-notes/v0.1.1-DRAFT.md) are marked DRAFT and are not a release. `v0.1.1` was not tagged or published. Write-up: [`ops/HANDOFF-ff-0111-2026-10-14.md`](ops/HANDOFF-ff-0111-2026-10-14.md). #30 stays open. #32 stays shipped in source at `83b3e66` and is not in the published v0.1.0 installer files. Not Feature GO.

---

## Source of truth

| Kind | Where |
|------|--------|
| Work items | **GitHub issues** (this repo) |
| Designs | `docs/design/` — start at [`docs/design/README.md`](design/README.md) |
| Product / rails | `docs/00-decision.md` … `docs/08-lab.md`, `docs/07-payment.md` |
| UI track pointers | `docs/09-ui-track*.md` |
| Roadmap | `docs/03-roadmap.md` |

---

## Open GitHub issues (pending)

| # | Title | Posture |
|---|--------|---------|
| [#26](https://github.com/themark-net/leasegrid-c/issues/26) | Android relative `EXTRA_RECOVERY_FILE` residual | Non-blocking residual (abs path PASS). Feature GO pending, untouched (2026-10-09) |
| [#30](https://github.com/themark-net/leasegrid-c/issues/30) | plant↔maximum Magic Folder HTTP 500 (glibc22) | Residual multi-host; parked; does not block buyer UX |
| [#33](https://github.com/themark-net/leasegrid-c/issues/33) | Vision: discoverable introducers / LeaseGrid as introducer | Exploratory only — **no build** |

## Recently closed (shipped / complete — keep designs)

| # | Note |
|---|------|
| [#27](https://github.com/themark-net/leasegrid-c/issues/27) | Buyer Servers + Join reachable — SHIPPED; design pack `40`–`44` |
| [#28](https://github.com/themark-net/leasegrid-c/issues/28) | Offer Used → settlement — issue closed completed; Design DoD `50`–`54` on main (confirm tip implements Hosted strip before re-opening) |
| [#32](https://github.com/themark-net/leasegrid-c/issues/32) | Invite short code + QR + Copy — SHIPPED inside #38; design pack `45`–`49` |
| [#34](https://github.com/themark-net/leasegrid-c/issues/34) / [#35](https://github.com/themark-net/leasegrid-c/issues/35) | XMR Credit top-up / gate 0d — SHIPPED |
| [#38](https://github.com/themark-net/leasegrid-c/issues/38) | Sync shell polish — SHIPPED @ `83b3e66` |
| [#44](https://github.com/themark-net/leasegrid-c/issues/44) | P4-B Android write sync — SHIPPED on `main` @ `5ac69aa` (PR #46 tip `6e7bf01`, merged 2026-10-04). Design pack `55`–`59` via PR #45 (`1c327c9`) |

Open PRs (2026-10-09): **none**.

---

## Design export map (`docs/design/`)

Full index is already in [`design/README.md`](design/README.md). Summary:

| Slice | Files | Status |
|-------|-------|--------|
| U0 buyer journey | `10`–`14` | Design DoD |
| U2 Credit | `15`–`19` | Design / SHIP |
| U4 Recovery | `30`–`34` | SHIP |
| P4-A Android read | `35`–`39` | Design / Slice A |
| #27 Buyer storage | `40`–`44` | SHIP |
| #38 Shell polish (+ #32) | `45`–`49` | SHIP @ `83b3e66` |
| #28 Offer → settlement | `50`–`54` | Design DoD ready; implement lane was Build-first on nimo |
| P4-B Android write (#44) | `55`–`59` | SHIPPED (#44, design 55–59, PR #46 @ `5ac69aa`, tip `6e7bf01`; design PR #45) |

Pointers beside `docs/09-ui-track.md`: `09-ui-track-*-POINTER.md`.

---

## Next implement candidates (only after founder RELEASE)

1. Confirm #28 Hosted-for-others strip is on tip vs Design DoD `54`; if missing, implement from `54-OFFER-SETTLEMENT-DEVBOT-HANDOFF.md`.
2. Optional residual #30 (plant↔maximum MF 500) if capacity.
3. Android P4-B write (#44, design 55–59) — shipped on `main` @ `5ac69aa` (PR #46). Not a next candidate.
4. #33 vision — never auto-start.

---

## Standing product locks

- CrashPlan-simple Sync metaphor (folders-first + Offer pie); no Tahoe WUI as product front door.
- Join-first empty home until invite; Servers roster dynamic add/remove (#27).
- Credit secondary under More; unpaid default; stagenet until Mark says otherwise.
- No Mark ops drip from bots; Namecheap/Epik/DNS out of this repo.

---

## Done when this handoff is useful

Next agent reads this file + `docs/design/README.md`, picks an **open** issue (#26/#30/#33) or waits for RELEASE, and does not invent public marketing or #33 implement.

---

## 2026-10-14 — #48 and #49 merged; pre-release follow-up

Not Feature GO. Not a release. No v0.1.1 tag. PR #51 is open for this follow-up (`build/ff-0111-prerelease`).

#48 (`d326c5b`, tester guide) and #49 (`9029086`, invite polish) are merged. `main` is `9029086`. This follow-up is `build/ff-0111-prerelease` in worktree `tmp/ff-0111-prerel`, based on that `main`.

| | |
|--|--|
| **Issue** | [#32](https://github.com/themark-net/leasegrid-c/issues/32) stays closed. |
| **main** | `9029086`. #48 is `d326c5b`. #49 is the merge of the invite-polish follow-up. |
| **This branch** | `build/ff-0111-prerelease` |
| **Already shipped** | `83b3e66` share card: short code, QR, Copy code. #49 kept raw introducer furls out of join failure copy, uses a standard QR, and round-trips the code. |
| **This follow-up** | Missing `tahoe` and a join timeout use the same friendly sentences as expired, rejected, and network failures. Unrecognised stderr is not echoed. macOS 15: try to open the app, then **Open Anyway**. README glibc phrase has one balanced pair of parentheses. |
| **CI** | `PYTHON=/tmp/lg-ff-prerel-venv/bin/python scripts/ci-local.sh` → 311 passed, exit 0. |
| **Write-up** | [`docs/ops/HANDOFF-ff-0111-2026-10-14.md`](ops/HANDOFF-ff-0111-2026-10-14.md) |
| **Not done** | Live two-machine wormhole. Phone camera. Android invite still refuses a short code and still names a `pb://` furl in that recovery line. #30, #33, #26. Feature GO. A v0.1.1 tag. |

Earlier sections stay. This does not reopen #32 and does not lift the 2026-09-24 pause.

## 2026-10-14 — PR #51 fix round after tester FAIL at `b63742b`

Not Feature GO. Not a release. No v0.1.1 tag. PR #51 stays open. Do not merge it from here.

| | |
|--|--|
| **Branch** | `build/ff-0111-prerelease` in worktree `tmp/ff-0111-prerel` |
| **Tester FAIL** | `b63742b` |
| **PR** | [#51](https://github.com/themark-net/leasegrid-c/pull/51) is open |
| **Join copy** | No `tahoe.log` tail in the window. Disk errors (`PermissionError` / other `OSError`) are one friendly sentence, and `on_join_invite` enables Join again. `on_join_existing` is fixed in the PR #53 scope round. The lead phrase appears at most once. Paths in that text stay for friends-and-family reports. |
| **Mutation: log tail** | Re-adding the tail fails `tests/test_sync_backend.py::test_start_log_tail_is_not_shown` at `assert "pb://" not in blob` (`tests/test_sync_backend.py:566`). |
| **Mutation: Join button** | Removing the `finally` fails `tests/test_sync_ui.py::test_join_permission_denied_reenables_button` at `assert ui.join_btn.isEnabled()` (`tests/test_sync_ui.py:250`, `assert False`). |
| **Mutation: OSError echo** | Appending `str(exc)` on the non-permission return fails `tests/test_sync_backend.py::test_join_other_oserror_text_is_not_echoed` at `assert "other OSError text" not in blob` (`tests/test_sync_backend.py:615`). The permission-only test stayed green. The same echo fails `tests/test_sync_ui.py::test_join_other_oserror_text_is_not_shown` (`tests/test_sync_ui.py:262`). Spawn echo fails `tests/test_sync_backend.py::test_join_spawn_oserror_text_is_not_echoed` (`tests/test_sync_backend.py:636`). |
| **Docs** | SmartScreen reputation and Windows 11 Smart App Control in `docs/ops/installers.md` and `docs/TESTERS.md`. macOS **Open Anyway** lasts about an hour and asks for the login password. Decision row in `docs/ops/AUTONOMOUS-DECISIONS-2026-10-14.md`. |
| **CI** | `PYTHON=/tmp/lg-ff-prerel-venv/bin/python scripts/ci-local.sh` → 319 passed, exit 0. |
| **Write-up** | [`docs/ops/HANDOFF-ff-0111-2026-10-14.md`](ops/HANDOFF-ff-0111-2026-10-14.md) |

## 2026-10-14 — PR #51 fix round 2 (Magic Folder log tail)

Not Feature GO. Not a release. No v0.1.1 tag. PR #51 stays open. Do not merge it from here. Do not tag v0.1.1.

| | |
|--|--|
| **Branch** | `build/ff-0111-prerelease` in worktree `tmp/ff-0111-prerel` |
| **Parent** | `e6312a4` |
| **PR** | [#51](https://github.com/themark-net/leasegrid-c/pull/51) is open |
| **Magic Folder** | A daemon exit no longer pastes `magic-folder.log`. The sentence names known issue #30 (Magic Folder HTTP 500) and points at Retry or a bug per `docs/TESTERS.md`. #30 stays open. |
| **Mutation** | Re-adding the log text fails `tests/test_sync_backend.py::test_magic_folder_exit_log_tail_is_not_shown` at `assert "pb://" not in blob` (`tests/test_sync_backend.py:602`). |
| **Left in place** | Other stderr, stdout, and `str(exc)` echoes are listed in the handoff. No other log tail. |
| **CI** | `PYTHON=/tmp/lg-ff-prerel-venv/bin/python scripts/ci-local.sh` → 320 passed, exit 0. |
| **Write-up** | [`docs/ops/HANDOFF-ff-0111-2026-10-14.md`](ops/HANDOFF-ff-0111-2026-10-14.md) |

## 2026-10-14 — #52 raw error text (`build/ff-0111-rawtext`)

Not Feature GO. Not a release. No v0.1.1 tag. PR #51 stays open on `build/ff-0111-prerelease`. PR #53 is open on `build/ff-0111-rawtext`. Do not merge from here. Do not tag v0.1.1.

| | |
|--|--|
| **Issue** | [#52](https://github.com/themark-net/leasegrid-c/issues/52) raw error text in Sync UI. Release blocker for v0.1.1. #30 stays open. |
| **Branch** | `build/ff-0111-rawtext` in worktree `tmp/ff-0111-rawtext` |
| **Parent** | `e9de382` on `build/ff-0111-prerelease` (PR #51) |
| **Decision** | Gate #51 as-is. Do not fold these sites into #51. The blocker label stops a release. Row in `docs/ops/AUTONOMOUS-DECISIONS-2026-10-14.md`. |
| **Buyer text** | Paths may stay. Furls, tracebacks, and exception class or module names do not. Magic Folder HTTP 500 names #30. Init and add stderr, unexpected errors, the REVIEW chip, and recovery credit errors use fixed sentences. Disk errno text is dropped. The path stays. |
| **Mutation** | Re-echoing each site failed the test named in [`docs/ops/HANDOFF-ff-0111-2026-10-14.md`](ops/HANDOFF-ff-0111-2026-10-14.md). HTTP POST fails `assert "pb://" not in blob` at `tests/buyer_text.py:21`. Recovery CLI fails `tests/test_sync_cli.py:210`. |
| **Static check** | `tests/test_no_raw_exception_text.py`. A planted `f"plant {exc}"` failed `assert not hits` at `tests/test_no_raw_exception_text.py:251`, then was removed. |
| **CI** | `PYTHON=/tmp/lg-ff-rawtext-venv/bin/python scripts/ci-local.sh` → 336 passed, exit 0. |
| **Write-up** | [`docs/ops/HANDOFF-ff-0111-2026-10-14.md`](ops/HANDOFF-ff-0111-2026-10-14.md) |

## 2026-10-14 — PR #53 scope on `build/ff-0111-rawtext`

Not Feature GO. Not a release. No v0.1.1 tag. PR #51 stays on `build/ff-0111-prerelease`. Do not merge from here. Do not tag v0.1.1. Do not push `build/ff-0111-prerelease`.

| | |
|--|--|
| **PR** | [#53](https://github.com/themark-net/leasegrid-c/pull/53) on `build/ff-0111-rawtext` |
| **Parent** | `8eca081` |
| **Magic Folder** | A daemon process exit says "Magic Folder stopped while starting" and names the log file. It does not name #30. An HTTP 500 still names known issue #30. #30 stays open. |
| **Use existing** | `on_join_existing` maps a read-only or undecodable `tahoe.cfg` to the same friendly sentence as `on_join_invite`, and `try`/`finally` enables Join again. The #51 "Join is enabled again" line is `on_join_invite`. |
| **Spawn text** | "Could not start Magic Folder." does not append the exception. The scanner sample covers `'%s' % exc`. |
| **Mutation: Join button** | Removing the `finally` fails `tests/test_sync_ui.py::test_join_existing_permission_denied_reenables_button` at `assert ui.join_btn.isEnabled()` (`tests/test_sync_ui.py:268`, `assert False`). The decode test fails the same way at `tests/test_sync_ui.py:285`. |
| **Mutation: echo** | Appending `str(exc)` fails `assert "Permission denied" not in text` (`tests/test_sync_ui.py:263`) and `assert "poison-decode-reason" not in text` (`tests/test_sync_ui.py:281`). |
| **Mutation: plant** | Putting `'Could not start Magic Folder: %s' % exc` back fails `tests/test_no_raw_exception_text.py::test_sync_package_has_no_raw_exception_text` at `assert not hits` (`tests/test_no_raw_exception_text.py:251`). The hit was `src/leasegrid_sync/backend.py:1379`. The spawn test fails `assert "Could not start Magic Folder." in blob` (`tests/test_sync_backend.py:1218`). The plant was removed. |
| **Decision** | Row in `docs/ops/AUTONOMOUS-DECISIONS-2026-10-14.md`: deferred from #51 to this PR. |
| **CI** | `PYTHON=/tmp/lg-ff-rawtext-venv/bin/python scripts/ci-local.sh` → 338 passed, exit 0. |
| **Write-up** | [`docs/ops/HANDOFF-ff-0111-2026-10-14.md`](ops/HANDOFF-ff-0111-2026-10-14.md) |

## 2026-10-14 — PR #53 fix round after tester FAIL at `27f9799`

Not Feature GO. Not a release. No v0.1.1 tag. PR #51 stays open on `build/ff-0111-prerelease`. PR #53 stays open on `build/ff-0111-rawtext`. Do not merge from here. Do not tag v0.1.1. Do not push `build/ff-0111-prerelease`.

| | |
|--|--|
| **Tester FAIL** | `27f9799` on PR #53. Reviewer passed. |
| **Invite** | The existing-node introducer failure no longer includes the invite, in any form. Join with a furl, join with a link, and recovery import share that sentence. The node path stays. |
| **Mutation: invite** | Putting the full invite back fails `assert "pb://" not in blob` in `tests/test_sync_backend.py::test_existing_node_furl_join_hides_invite` (`tests/test_sync_backend.py:1305`), `test_existing_node_link_join_hides_invite` (`tests/test_sync_backend.py:1322`), and `test_recovery_import_existing_node_hides_invite` (`tests/test_sync_backend.py:1349`). Restored. All three passed. |
| **Magic Folder log** | `ensure_running` creates the log directory and opens the log inside a `try`. A read-only directory is one friendly sentence. The path stays. The errno text does not. |
| **Mutation: log** | Leaving `mkdir` and `open` outside the `try` raises `PermissionError` at `ctl.ensure_running()` (`tests/test_sync_backend.py:1367`). Echoing the exception fails `assert "Permission denied" not in blob` (`tests/test_sync_backend.py:1371`). Restored. The test passed. |
| **Scanner** | Every `except ... as <name>` binding is exception text inside that handler, including `ex`. `redact_furl(...)` flowing into buyer text is a hit. `name.banner()` stays allowed. |
| **Mutation: scanner** | Planted `except OSError as ex` and `redact_furl(...)` in `SyncError` failed `assert not hits` (`tests/test_no_raw_exception_text.py:291`). Hits were `src/leasegrid_sync/backend.py:1721` and `src/leasegrid_sync/backend.py:1725`. Plants removed. The test passed. |
| **Disk offer** | A bad `reserved_space` value is not copied into the window. |
| **Mutation: reserved_space** | Putting the raw value back fails `assert raw not in blob` (`tests/test_sync_backend.py:1403`). Restored. The test passed. |
| **Refresh** | A Magic Folder HTTP 500 while listing folders says "could not refresh folders." It does not say "folder not added." An add still does. #30 stays open. |
| **Mutation: refresh** | Leaving the add sentence in place fails `assert "folder not added" not in blob.lower()` (`tests/test_sync_backend.py:1420`) and `assert "folder not added" not in rows[0].detail.lower()` (`tests/test_sync_backend.py:1457`). Restored. Both tests passed. |
| **Parked** | Import dialog truncates the Next line. Not fixed. Row in `docs/ops/AUTONOMOUS-DECISIONS-2026-10-14.md`. |
| **CI** | `PYTHON=/tmp/lg-ff-rawtext-venv/bin/python scripts/ci-local.sh` → 345 passed, exit 0. |
| **Write-up** | [`docs/ops/HANDOFF-ff-0111-2026-10-14.md`](ops/HANDOFF-ff-0111-2026-10-14.md) |

## 2026-10-14 — #32 fix round after tester FAIL at `18d921e` (PR #49)

Not Feature GO. Not a release. No v0.1.1 tag. This round landed in #49, merged to `main` as `9029086`. PR A (tester guide) is merged as #48 (`d326c5b`).

| | |
|--|--|
| **Branch** | `build/ff-0111-invite-polish` in worktree `tmp/ff-0111-invite` |
| **Tester FAIL** | `18d921e` |
| **Code** | `7ab178f` |
| **CI** | `PYTHON=/tmp/lg-ff-invite-venv/bin/python scripts/ci-local.sh` → 308 passed, exit 0. |
| **QR** | Share-dialog slot matches the pixmap. The UI test decodes `widget.grab()`. Overlap mutation fails with `QR finder is covered`. |
| **Join copy** | Expired, rejected, and network failures are different sentences. No `wormhole.`, `Error`, or traceback in the window. |
| **Node folder** | Test Tahoe refuses an existing basedir. Failed join deletes it. Cleanup mutation fails `assert not nodedir.exists()`. |
| **Android** | Not changed. `Invite.kt` still does not redeem a short code. |
| **Docs** | macOS 15+ leads with Open Anyway. One glibc phrase: `glibc 2.35 or newer (Ubuntu 22.04+, Debian 12+, Fedora 36+)`. |
| **Write-up** | [`docs/ops/HANDOFF-ff-0111-2026-10-14.md`](ops/HANDOFF-ff-0111-2026-10-14.md) |

---

## P4-B Android write sync — issue #44 (this slice)

Earlier sections stay. This section is only #44. It does not close #26, #30, or #33, and it does not rewrite `docs/design/35`–`39`.

| | |
|--|--|
| **Issue** | [#44](https://github.com/themark-net/leasegrid-c/issues/44) only |
| **Branch** | `cursor/android-p4b-write-sync-7258` |
| **Parent that must stay** | `46814dc09ee76600789ffc5de3f46957c2d0f011` |
| **Product commit** | `993466a62f42c6760e155c1d46b13a1fc9750f63` |
| **Fix SHA** | `2c31383108c5d1a31943d81165d0eb950bbedeb4` |
| **Tip SHA** | PR #46 merged @ `5ac69aa`; tip `6e7bf01` |
| **Design** | `docs/design/55`–`59` and `docs/09-ui-track-P4-ANDROID-B-POINTER.md` |
| **Base** | `1c327c9b1b5c5478e21bbfe3ec19fb1b9c8c9d43` (docs PR #45) |

The 45-second FAIL behavior is `2c31383108c5d1a31943d81165d0eb950bbedeb4`. Its parent is `46814dc09ee76600789ffc5de3f46957c2d0f011`. `46814dc09ee76600789ffc5de3f46957c2d0f011` stays in history. PR #46 merged to `main` as `5ac69aa` on 2026-10-04. PR tip is `6e7bf01`.

Dogfood the debug APK from the **new** GitHub Actions run on this commit. Not Actions run `37228703131`. Not `98a9c906bb469f58f5395ffc91166d7ec1290421`. Not `0ba8dc42b2ea743a5548187b5b24fe2f38780400`. `android/pytests/test_live_grid.py` is not in CI and was not run. This is not a live dogfood pass.

### What this commit changes

A phone add into a Magic Folder collective was stored as a raw CHK filenode on the collective root. Photos is `@metadata` plus the read-only `mark` participant. `_is_collective` required every child to be a mutable directory, so `@metadata` made the folder look plain and `put_file` took the raw-CHK path. Magic Folder does not download a CHK on the collective root. It also skips `mark`: that directory is this desktop's upload DMD (`is_self`), and the collective link has no write cap, so the phone cannot rewrite it.

The add is now a signed Magic Folder snapshot in a participant directory the downloader polls (its cap is not the desktop upload directory). The first add links that directory. Later adds reuse it. `@metadata` stays. `mark` is not rewritten. A raw CHK already sitting on the collective root is unlinked in that same rewrite, because the poll treats it as a participant and aborts. Those bytes are not copied into `~/Leasegrid/Photos`. **On friendnet** still requires a read-back of the same bytes.

### What this commit does not change

- Hide-Remove stays. A read-only folder hides Remove. Open stays. Add file stays hidden. Design pack `56`.
- The 45-second FAIL stays. After 45s with no read-back, the chip stays **Not on friendnet yet** and the existing FAIL + Retry show. **On friendnet** only after a read-back of the same bytes, including when that read-back arrives after FAIL. A stalled add does not sit on a moving bar.
- Directory rewrite stops at the share count in the first share header.
- No new Magic Folder, no introducer change, no systemd unit, no VM onboot change, no folder control, no write settings, no new payment rail, no chrome rewrite.
- Design packs `35`–`39` are not rewritten. Issues #26, #30, and #33 are not touched. Desktop Sync stays primary.
- PR #46 merged to `main` @ `5ac69aa` (tip `6e7bf01`, 2026-10-04). This handoff refresh is docs-only. Not Feature GO. Not a new RELEASE.
- `android/pytests/test_live_grid.py` is not in CI and was not run. No live dogfood pass is claimed.

### What shipped

An already-joined phone can add one file to the folder that is already open.

- **Add file** is on that folder (system picker). It is absent on Folders home, on Welcome, and on a read-only cap.
- The row stays **Not on friendnet yet**, with progress and Cancel, until the friendnet read-back succeeds. The chip then says **On friendnet**. It does not say "On your computer".
- If that read-back has not succeeded after 45 seconds, the progress bar stops. The row stays **Not on friendnet yet** and shows the existing FAIL — could not add this file. Next: check network; Retry. A later read-back that does succeed still becomes **On friendnet**.
- The same name opens a sheet: **Replace**, **Keep both** (`beach (phone).jpg`), **Cancel**.
- **Remove** confirms and deletes that object on the friendnet, or leaves the row and shows FAIL. **Discard** only drops a pending row that never landed. **Remove** is hidden when the folder is read-only. Download and Open stay.
- A read-only folder hides Add file and shows: "You can download from this folder. Adding files is not available here."
- Slice A download/open still works. Desktop Sync stays the place that creates folders. No write settings screen. No new payment rail.

### How it can fail, and how we recover

| Risk | How it fails | How we recover |
|------|----------------|----------------|
| Chip says done before the write lands | Operator trusts a lie | `put` returns ok only after a read-back of the same bytes. The UI chip stays **Not on friendnet yet** until that ok. Progress never reaches a success chip on its own. |
| Put never returns | Row sits on a progress bar with no error, as in And's step 3 | After 45 seconds the bar stops, the chip stays **Not on friendnet yet**, and the existing FAIL plus Retry show. The put is not cancelled: a later read-back ok still becomes **On friendnet**. Retry sends the same local file. |
| Rewrite probes shares past `n` | Each missing share can block on the socket timeout, so read-back never runs | Locate stops at the share count in the first share header. A miss is the existing FAIL, not **On friendnet**. |
| Phone add is a raw CHK on the collective root | Photos Magic Folder's poll ignores it, or aborts, and `~/Leasegrid/Photos` stays empty | The add is a signed snapshot in a participant directory that is not the desktop's own. `@metadata` stays. The desktop participant is not rewritten. A raw CHK child is unlinked in that same rewrite. **On friendnet** still waits for a read-back of the same bytes. |
| Network dies mid-write | Partial upload, row would look finished | Row stays **Not on friendnet yet**. FAIL — could not add this file. Next: check network; Retry. Retry sends the same local file. Cancel discards it. |
| Same filename | Silent overwrite | Sheet: Replace / Keep both / Cancel. Cancel deletes the pending copy and leaves the list. |
| Read-only cap | Add file fails every time, or Remove offers a friendnet delete the cap cannot do | Add file stays hidden. Remove is hidden. Download and Open still work. |
| Remove vs discard | Phone-only delete, or a friendnet delete of a file that never landed | Remove asks, and the copy says the friendnet. Discard's copy says it is not on the friendnet yet. A remove that does not disappear from a fresh listing stays FAIL with the row still there. |
| Slice A read regresses | Can't download | `android/pytests/test_live_grid.py` did not run on `46814dc09ee76600789ffc5de3f46957c2d0f011`. It is not in CI. Do not treat that file as evidence for this slice. |
| Desktop regresses | Sync won't launch | This VM did not prove Tahoe `ls`/`get` of a phone write. And should still smoke-launch desktop Sync on the tip. |

### Dogfood for And (emulator)

And's step 3 on the draft APK from GitHub Actions run `37169908352` (`versionName` `0.4.0-slice-b`, emulator `pixel_api34_lg_dogfood`, API 34) **FAIL**. Phone already joined. Photos already open. Add file put `lg44-live-20261003T230457.txt` (33 bytes, token `lg44-token-20261003T230457-27628`). The row stayed **Not on friendnet yet** for about 90 seconds, with a progress bar and Cancel. It never became **On friendnet**. It never said "On your computer". No on-screen error. The desktop Photos folder was empty before and after. Steps before the add had already passed. This VM cannot see that grid. Do not claim a live pass.

This fix: a small add completes put, then a read-back of those same bytes, and only then the chip says **On friendnet**. If read-back does not succeed, the row stays **Not on friendnet yet** and shows the existing FAIL plus Retry. Not an endless progress bar.

Debug APK: `leasegrid-sync-android-slice-a-debug.apk` from the **new** GitHub Actions run on this commit. Not Actions run `37228703131`. Not `98a9c906bb469f58f5395ffc91166d7ec1290421`. Not `0ba8dc42b2ea743a5548187b5b24fe2f38780400`. Install with `adb install -r`.

Prereqs: emulator API 34+; a phone already joined to a folder desktop Sync can also see; one small new file; one file already in that folder.

1. Launch. Confirm Folders, not a join form, and no Tahoe WUI.
2. Open the known writable folder. Confirm **Add file** is on that screen, not on Folders and not in Settings.
3. Add the new file. Confirm the row reads **Not on friendnet yet** before it reads **On friendnet**. If the friendnet does not read the bytes back, confirm FAIL — could not add this file. / Next: check network; Retry. — and that the progress bar is not still moving. The chip must not say On friendnet in that case.
4. From desktop Sync, confirm the bytes show up in `~/Leasegrid/Photos`. The file is a snapshot under the phone's participant, not a raw CHK on the collective root, and not a new child of `mark`. `tahoe get` of the content cap should match. The two earlier raw CHK names on the collective root are unlinked by a successful add and are not copied into Photos.
5. Add a file with the same name. Confirm Replace / Keep both / Cancel. Cancel leaves the list unchanged. Keep both shows a distinct name.
6. Airplane mode, add another file. Confirm FAIL + Retry, and the chip is not On friendnet.
7. Download/open one file that was already in the folder.
8. If a read-only folder is in the lab, confirm Add file is absent, Remove is absent, Download/Open still work, and the read-only line is shown.
9. Remove an On friendnet file only after the confirm sheet. Discard a pending file from Cancel; that sheet must not say the friendnet lost a copy.
10. Note PASS/FAIL, the APK path above, the emulator image, the tip SHA, and issue #44. No Mark drip.

### Non-goals (do not add in review)

- No new folder and no new grid from the phone.
- No write settings, sync dashboard, or new tab.
- No "On your computer" and no green chip before friendnet ack.
- No new payment rail, Credit gate, or Offer step on the write path.
- No rewrite of `docs/design/35`–`39`.
- Desktop Sync stays primary. Issues #26, #30, and #33 are untouched.

---

## 2026-10-09 check — Settings deferred list / Credit (U2)

Code read of `src/leasegrid_sync/app.py` on this worktree (`main` @ `5ac69aa`). No code change.

The Settings note (`settingsNote`) builds “Coming later” at lines 1792–1793. The only deferred bullet is:

`.deb package (AppImage / macOS / Windows installers ship now)`

Credit is not in that list.

Credit is a real place:

- More → Credit: line 1156 `more.addAction("Credit")`, wired at line 1158 to `open_credit_place`.
- Tray menu Credit: line 1910 `menu.addAction("Credit")`, wired at line 1911 to `open_credit_place`.
- Panel title: line 1558 `QLabel("Credit")` inside `_build_credit_tab`.

`_sync_gated_chrome` (lines 2078–2088) shows the More Credit action, the tray Credit action, and the separate `paymentLecture` label only when `credit_enforced()` is true. That gate is not a Settings deferred line. `paymentLecture` (lines 1805–1811) says “Credit → Top up quotes XMR. Open Credit from More to see the balance.” and starts hidden. It is not the Coming later list.

Design 16 (strike “Credit panel (U2)” from any Settings deferred list), design 17 (strike any “Credit (U2)” deferred line; checklist “Credit not deferred”), and design 19 build-order item 6 (“strike Credit from Settings deferred list”) are DONE on this tip. No code change.

---

## Bot/Build caveat — ci-local venv

`scripts/ci-local.sh` lines 7–19 leave `PYTHON` unset, then pick `/home/mark/tahoe-venv/bin/python` when that file is executable. The script runs `"$PYTHON" -m pip install -q -e ".[dev]"` (and the sync and tahoe extras). That install would repoint Mark’s `tahoe-venv` at whichever worktree is current.

Bot or Build runs must set `PYTHON` to a worktree venv before calling the script:

```bash
python3 -m venv .venv && PYTHON=$PWD/.venv/bin/python bash scripts/ci-local.sh
```

`.venv` lives under the worktree. `.gitignore` line 4 is `.venv/`, so that directory is ignored. Do not commit it. Never run `ci-local` against `tahoe-venv`. This refresh did not run `scripts/ci-local.sh`.

