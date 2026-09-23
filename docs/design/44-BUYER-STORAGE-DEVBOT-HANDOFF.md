# Buyer storage → DevBot / Cursor handoff (#27)

**Status:** Design DoD 2026-09-22 PT — ready for PM RELEASE implement  
**Cite:** [#27](https://github.com/themark-net/leasegrid-c/issues/27) · tip ≥ **`5b752c7`** (`5b752c70dda4f5b4857c97556ace8881a8fed8f1`) · Mark/CEO lock 2026-09-22  
**Design refs:** [40](40-BUYER-STORAGE-JOURNEY.md) · [41](41-BUYER-STORAGE-IA.md) · [42](42-BUYER-STORAGE-WIREFRAMES.md) · [43](43-BUYER-STORAGE-NON-GOALS.md) · pointer `docs/09-ui-track-BUYER-STORAGE-POINTER.md`  
**Do not:** implement in the Design pass; contact Mark; ship WUI; fake forever-remove; rewrite `10`–`39`.

---

## Product DoD (implement must prove)

1. **Empty Join-first:** Fresh Sync home / clean AppImage home → Welcome/Join only until invite (or recovery import) succeeds. **No** “Online — N computers storing files” before join.  
2. **No pre-baked buyer grid:** Buyer AppImage does not ship a pre-joined lab home.  
3. **Storage servers place:** First-class UI listing hosts (name, status, source) with **Add** and **Disconnect**. Replaces reliance on status chip as sole host UX.  
4. **Add — both paths in UX:**  
   - Invite someone to Offer disk (friendnet invite / Offer share)  
   - Paste storage server furl (`pb://…`) → remember + use for share placement  
   Implement may **sequence** invite-first then furl in milestones; **both** must land for #27 DoD (Design shows both; both are DoD).  
5. **Disconnect:** Confirm → remove from **this home’s** connected/used set; stop preferring for new shares; forget local pin. Honest copy only.  
6. **Join/Add always reachable** after first connect (Folders → Storage servers → Add). Join-once-and-gone = FAIL.  
7. **Operate-or-FAIL:** Bad invite, bad/unreachable furl → in-app FAIL + Next/Retry (no WUI).  
8. **Folders-first + Offer pie + Credit rank** preserved (P1/U2).  
9. Tip base ≥ **`5b752c7`**.

---

## Suggested files / areas to touch (guess from Sync tree on tip)

|| Area | Likely paths | Why |
||------|--------------|-----|
|| Clean-home / Join gate | `src/leasegrid_sync/app.py` (`has_nodedir` branch ~1328+); Welcome/Join widgets | Detect never-joined → Join-only primary |
|| Status chip | `app.py` `format_status_chip` (“Online — N computers storing files”) | Hide until joined; deep-link chip → Storage servers after join |
|| Connection / server count | `backend.py` `ConnectionStatus`, `servers_connected`, `server_nicknames`, `welcome()` | Feed Servers list; distinguish announced vs pinned |
|| Join / invite | `invite.py`, `backend.py` validate/join introducer | Path A Add (invite-to-Offer) + first Join |
|| Storage furl add | **new** helpers beside `backend.py` / `invite.py` | Validate storage `pb://` (not only introducer); persist pin list under Sync home |
|| Persist pins | home config under `default_home()` (e.g. `servers.json` / cfg — implement picks) | Remember Add; honor Disconnect |
|| Share placement preference | Tahoe client / shares config via existing node | Prefer pinned connected set for new shares |
|| Packaging | `packaging/` AppImage | Ensure buyer artifact does not embed joined lab nodedir |
|| Tests | `tests/` | Clean home Join-first; Add furl FAIL; Disconnect local-only |

Stack remains Gridsync-class PyQt Sync — **no** Electron rewrite, **no** Tahoe WUI.

---

## Recommended implement order (optional sequencing)

1. Clean-home detection + suppress pre-join Online-N chrome  
2. Storage servers list UI (read-only from welcome/announced + connected)  
3. Nav always reachable from Folders; chip → Servers  
4. Add path A — invite-to-Offer (reuse invite machinery)  
5. Add path B — paste storage furl + persist + operate-or-FAIL  
6. Disconnect confirm + local forget + honest copy + re-announce Available behavior  
7. AppImage dogfood: fresh home empty; no lab pre-join

Steps 4–5 may be sequenced, but **both** are #27 DoD — do not close issue with only invite path.

---

## Dogfood steps (nimo / multi-client lab)

|| # | Step | PASS |
||---|------|------|
|| 1 | Fresh home (empty nodedir / new `LEASEGRID_*` home) launch Sync | Join-only; **no** Online-N |
|| 2 | Paste invite; Join | Folders primary; Offer pie intact |
|| 3 | Open **Storage servers** from Folders | List visible; Add visible |
|| 4 | Add via invite-to-Offer (second machine Offers) | New host row / status updates |
|| 5 | Add via paste storage furl (known good lab storage furl) | Row Connected |
|| 6 | Paste bad furl | In-app FAIL + Retry |
|| 7 | Disconnect a server; confirm | Removed from Used; honest copy |
|| 8 | If introducer re-announces | Shows Available / “Seen again” — not auto-forced forever-gone claim |
|| 9 | Quit + relaunch joined home | Folders primary; Servers + Add still reachable |
|| 10 | Buyer AppImage on clean machine | No pre-joined lab grid |

Lab multi-client dogfood may continue in parallel as **capability proof only**. Public v* HOLD until Design (this pack) then implement.

---

## Operate-or-FAIL examples

|| Case | Banner spirit | Next |
||------|---------------|------|
|| Join fail | could not join… | Retry / fix invite |
|| Bad storage furl | could not add this storage server… | Retry |
|| Unreachable server | …unreachable… | Retry / check host |
|| Disconnect | confirm only | Cancel / Disconnect |

---

## Explicit rejects

- Status chip as **only** host UX  
- Join-once-and-gone  
- Pre-joined buyer AppImage  
- “Removed from grid forever” copy  
- Tahoe WUI Next  
- Demoting Folders / Offer / Credit  
- Closing #27 without paste-furl Add path  
- Mark drip from implement bots

---

## Exit checklist (DevBot reports)

- [ ] Tip ≥ `5b752c7`  
- [ ] Clean home Join-first (screenshot)  
- [ ] Storage servers list + Add + Disconnect (screenshots)  
- [ ] Both Add paths work (invite-to-Offer **and** paste furl)  
- [ ] Disconnect local-only + honest copy  
- [ ] Join/Add reachable after relaunch  
- [ ] Bad furl FAIL in-app  
- [ ] No WUI; Folders/Offer/Credit preserved  
- [ ] AppImage clean-home check

**#27 implement FAIL examples:** still shows Online-N on empty home; no Servers place; Add missing after join; only chip no list; claims forever-remove; furl path omitted from UX.

---

## One-liner

> Implement #27 on tip ≥ `5b752c7`: empty Join-first; **Storage servers** roster with Add (invite **and** storage furl) + honest Disconnect; Join/Add always reachable; operate-or-FAIL; no WUI / no forever-remove.