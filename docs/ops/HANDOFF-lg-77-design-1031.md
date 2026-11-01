# Handoff: lg-77-design-1031

Issue #77 design only. No behavior code. Branch `bot/lg-77-design-1031`. No PR, no merge, no tag.

## Items done

| Item | SHA | What |
|------|-----|------|
| Exits, then the design | `a251f92426dd74d7ef4cbf99f2ff4a551b430858` | `docs/design/77-ANDROID-INVITE-OPTION2.md`. Compares short-code redeem and QR scan. Recommends Chaquopy redeem, no camera, no desktop change. OPEN QUESTIONS for Mark are in the doc. |
| Review pass | `b0196ca624f4b2e482788e8365dbc074cfe5a7ed` | One lead pass. Findings were fixed inside `a251f92` before it was pushed. The run log lists them. Re-read passed. |

## Items skipped

| Item | Why |
|------|-----|
| Behavior code, pip line, tests | This lane is design only. |
| `scripts/pregate.sh` | The operator runs pregate. The drop-in also says not to run it from this lane. |
| Python suite | No code change. `Runner.Worker` was present at launch, so a suite was forbidden then anyway. |
| `Invite.kt` | `bot/lg-78-invite-1031` owns it for #78 and #80. |
| `AppModel.kt`, `SyncApp.kt` | `bot/lg-80-appmodel-1031` owns them. Slice 1 does not need them. |
| `docs/design/README.md`, `docs/PENDING-HANDOFF.md` | Shared status docs. Left as they are. |
| Native mailbox client, camera slice, project map | Camera and a native port are open questions, not this lane. A project map would add files outside the owned set. |

## Test evidence

None run. The change is a design document. There is no new runtime path to fail.

The design's own E2E is "desktop share card to phone join", with expired, relay-down, and nobody-answered arms on the first slice, and camera-denied plus bad-QR arms on the later slice. Those tests do not exist yet. They are the implement gate, not this lane's result.

## How this change fails and recovers

The only shipped change is the document. A wrong claim would send the next lane at the wrong join.

The review caught one of those: the share dialog's Done button does not stop `tahoe invite`. Quitting Sync does (`shutdown` calls `InviteCodeSession.close`). The expire arm in the doc now says that.

The other correction that matters: issue #77 says "QR of the join link", and the share card QR is the short code (`InviteSharePanel._paint_qr`). A camera on that card still needs redeem. The join-link QR is the I2P page (`invite_page_html`). The recommendation follows the card, not the issue's shorthand.

No user-visible string changed in the app. Option 1 copy still ships.

## Cross-lane requests

- #78 / #80 (`bot/lg-78-invite-1031`): keep the paste length bound and the tighter address checks in front of any future redeem. Do not start #77 inside `Invite.kt` while that lane owns the file.
- #80 app model (`bot/lg-80-appmodel-1031`): slice 1 does not need `AppModel.kt` or `SyncApp.kt` if the field, the checkbox, and `join()` stay.
- `docs/PENDING-HANDOFF.md` still says option 2 is deferred and does not link this design. Not edited here.
- `docs/design/README.md` has no #77 row. Not edited here.

## Gate

Pregate (operator) plus Reviewer (docs). No Tester. No runtime change.

Reviewer should read `docs/design/77-ANDROID-INVITE-OPTION2.md` at `a251f92` or later on `bot/lg-77-design-1031`.

## Next step

Reviewer pass on the design. If Mark does not answer the OPEN QUESTIONS, the defaults in that list are the implement slice: short-code redeem in Chaquopy, 120 second budget, Tahoe 1.20's public relay when unset, no camera, no phone relay setting, no native port. Implement waits until `Invite.kt` is free, and it records the APK byte delta. It does not run while this handoff is the only deliverable.

## Decisions

`docs/ops/AUTONOMOUS-DECISIONS-lg-77-design-1031.md`
