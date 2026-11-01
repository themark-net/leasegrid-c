# 77, Android Invite option 2: short-code redeem or QR scan

Status: design only. No behavior change in this lane.

Cite: issue [#77](https://github.com/themark-net/leasegrid-c/issues/77), follow-up to [#50](https://github.com/themark-net/leasegrid-c/issues/50). Option 1 copy is design [61-ANDROID-INVITE-JOINLINK.md](61-ANDROID-INVITE-JOINLINK.md) and is what the phone ships. Out of scope here: [#30](https://github.com/themark-net/leasegrid-c/issues/30), [#33](https://github.com/themark-net/leasegrid-c/issues/33), [#26](https://github.com/themark-net/leasegrid-c/issues/26), Feature GO.

#78 and #80 are a parallel lane (`bot/lg-78-invite-1031`) that owns `Invite.kt`. This design does not edit that file. Slice 1 below assumes their length bound and tighter address checks stay in front of any redeem.

## What is already true

Read these before changing the phone:

| Fact | Where |
|------|--------|
| Phone join is paste a full join link, tick the four points, tap Join a shared folder. | `Invite.kt` `TITLE`, `BODY`, `INPUT_HINT`. Design 61. |
| A short code (`7-guitarist-revenge` shape) never joins. Banner is `WORMHOLE_MSG`. No Next line. | `Invite.parse`, `InviteCopyTest.shortCodeShowsShortCodeMessageAndNeverJoins`. |
| A join link, a `leasegrid:join#…` link, and a raw address already parse to an introducer plus optional share counts. `SessionFlow.join` then calls `learn(furl)` and saves a session. Null shares become 2, 3, 3. | `Invite.fromFragment`, `SessionFlow.join`. |
| Any `learn` failure is one pair: `JOIN_FAILED` / `JOIN_FAILED_NEXT`. Raw errors never reach the screen. The field is kept. Retry calls `join()` again. | Design 61. `SessionFlow`. |
| User-visible phone strings must not contain: furl, pb://, introducer, wormhole, friendnet, or "could not join" (any case). | `bannedWords` in `InviteCopyTest.kt`. |
| Desktop Share invite card shows a short code, a QR of that code, and Copy code. The join link stays behind "Show full join link (advanced)". | `InviteSharePanel` in `src/leasegrid_sync/app.py`. `_paint_qr(code)`. |
| The I2P invite page QR is different: it encodes the join link, not the short code. | `invite_page_html` calls `qr_svg(share)` in `src/leasegrid_sync/invite.py`. |
| Desktop redeem is not an in-process import. `tahoe create-node --join=<code>` talks to the relay. `tahoe invite` must stay running until someone joins. | `TahoeClient.create_node`, `start_invite_code`. |
| Default relay and app id, Tahoe-LAFS 1.20 `runner.py`: `ws://wormhole.tahoe-lafs.org:4000/v1` and `tahoe-lafs.org/invite`. `LEASEGRID_WORMHOLE_SERVER` overrides the relay on the desktop only. Unset means Tahoe's public relay. | `docs/ops/dev-grid.md`. Tahoe tag `tahoe-lafs-1.20.0`. |
| Desktop join budget for a code is 120 seconds (`WORMHOLE_JOIN_TIMEOUT`). Phone `learn` budget is 25 seconds and is a different step. | `backend.py`, `leasegrid_read.dispatch`. |
| The mailbox payload is Tahoe's invite handshake, not a bare address. The inviter sends `{abilities: {server-v1: {}}}`, waits for `{abilities: {client-v1: {}}}`, then sends JSON with `introducer`, `shares-needed`, `shares-happy`, `shares-total`, and `nickname`. | `tahoe_invite.py` and `create_node._get_config_via_wormhole` at that tag. |
| Android already embeds CPython 3.11 (Chaquopy) with foolscap 24.9.0, Twisted 25.5.0, cryptography below 45, pyOpenSSL below 25, service-identity below 25. ABIs are arm64-v8a and x86_64. Manifest permission is INTERNET only. There is no camera permission and no `tahoe` binary. | `android/app/build.gradle.kts`, `AndroidManifest.xml`. |
| `learn` connects to the introducer with the code under `android/app/src/main/python/`. It does not redeem a code. | `lg_intro.learn_servers`. |

Issue #77's "QR of the join link" does not match the share card. The card QR is the short code. Scanning that card still yields text that `Invite.parse` refuses today. A join-link QR is the I2P page, or a new desktop image this design does not add.

## The two paths

Both paths end at the same place: `learn` with an introducer, then the existing Folders save. They differ in how the phone gets that introducer.

| | Short-code redeem | QR scan |
|--|-------------------|---------|
| What the person does | Types or pastes `7-word-word` from the share card (or taps Copy code on the desktop and pastes). | Points the camera at a QR. |
| What the phone receives | The short code. | Whatever the symbol encodes. |
| Current share card | This is the text on the card and in the card's QR. | The card's QR decodes to the short code, so the camera still needs redeem. |
| Join link | Not required. Pasting the advanced link stays the option 1 path and skips redeem. | A QR of the join link (the I2P page today) decodes to text option 1 already accepts. No mailbox. |
| New protocol on the phone | Yes. Tahoe 1.20 client handshake, then `learn`. | Only if the symbol is a short code. A join-link symbol adds a camera and no protocol. |
| New permission | No. | CAMERA, runtime, minSdk 26. |
| Desktop change | None. Keep Sync open on the share card, which is already the rule. | None if the camera reads the existing card. A join-link QR on that card would be a desktop change and is rejected below. |

Rejected: put the join link into the share-card QR so a camera can avoid the mailbox. `invite.py` keeps the introducer in the advanced fragment on purpose. The card QR is the one-time code. Changing that payload would also break the desktop tester step "a phone camera that reads the QR produces the same text" as Copy code (`docs/TESTER-GUIDE.md`).

## User flow

Common steps, both paths:

1. The person already on the grid opens Share invite and leaves Leasegrid Sync open. Quitting the app stops the code (`shutdown` calls `InviteCodeSession.close`). Dismissing the Share invite dialog does not. Done is not an expire step.
2. On the phone, the four points and the checkbox stay. Join stays disabled until the box is checked and the field is non-empty (`Invite.joinEnabled`), and while a join is already running (`joinControlEnabled` in `DogfoodProbe.kt`, used by `SyncApp`). The Invite field stays a URI keyboard. A short code types there. This slice does not change the keyboard.
3. The Invite field stays. Retry re-reads it. A failure does not clear it (`AppModel` comment on #50).
4. Parse runs before any network. A parse failure does not call `learn` and does not redeem.
5. After a good introducer, `learn` is the same call as option 1. Its failure copy stays `JOIN_FAILED` / `JOIN_FAILED_NEXT`.

### Short-code redeem (first slice)

1. Body and hint change so the screen no longer says the phone cannot use short codes. Exact strings are in Fail and recover copy. Both desktop labels stay in the body so the existing pin still has something to pin.
2. Person types the code, or pastes Copy code. The field's `dogfoodField("invite_field")` stays, so `adb input text` still lands after the checkbox.
3. Tap Join a shared folder.
4. Phone opens the mailbox as the Tahoe 1.20 client: app id `tahoe-lafs.org/invite`, relay as below, send `client-v1`, require `server-v1`, read the config JSON.
5. `introducer` from that JSON is checked with the same rules as a pasted link (including the #78 length bound and the #80 character checks, once those land). Share counts are kept only when `n > 0` and `n <= h <= t`, same as `fromFragment`. Otherwise shares stay null and the save path's 2, 3, 3 default applies. `nickname` is ignored. The phone does not create a Tahoe node.
6. `learn` runs. Folders appear on success.

Relay choice: if nothing is injected, use Tahoe 1.20's default `ws://wormhole.tahoe-lafs.org:4000/v1`. Do not add a relay field on the phone. A desktop that was started with `LEASEGRID_WORMHOLE_SERVER` (dev-grid's `ws://127.0.0.1:45040/v1`) minted a code the public relay cannot open. Recovery is the advanced join link, which never touches the relay. Lab tests inject the relay. They do not add a setting.

Budget: 120 seconds, matching `WORMHOLE_JOIN_TIMEOUT`, then the nobody-answered copy. This budget is not the 25 second `learn` timeout. Leaving the screen cancels the attempt. Retry starts a new one. No second attempt is left running.

### QR scan (later slice, not the first)

1. A Scan control sits beside the field. It is not the only way in. The field and option 1 paste still work.
2. The first tap asks for the camera. Denial does not loop the system dialog. The field stays usable.
3. Frames are decoded on the device. No upload, no Play services barcode API.
4. Decoded text is handed to the same parser as a paste:
   - short code: redeem, then `learn`
   - join link or raw address: option 1, no mailbox
   - empty symbol or no symbol: bad-QR copy, no redeem, no `learn`
   - other text: today's garbage copy
5. A photo of the I2P page QR is a join link, not a bad QR.

Do not build this slice until short-code redeem has passed the E2E below. The scanner library is an open question. The constraint is fixed: on-device, no network.

## Where the mailbox client runs

Recommendation: Chaquopy, a small redeem op next to `learn`, then the existing Kotlin `learn(furl)`.

| Place | What it means here | Verdict |
|-------|--------------------|---------|
| Chaquopy (Python 3.11 already in the APK) | Call `wormhole.create(appid=..., relay_url=..., reactor=...)` the way Tahoe 1.20's `create_node._get_config_via_wormhole` does. Return a status plus the introducer and shares to Kotlin. Kotlin never sees exception text. | First slice. Twisted is already on the pip line. |
| Native Kotlin mailbox client | Reimplement SPAKE2, the mailbox websocket, and Tahoe's two-message handshake. | Not this design. No such client exists in the repo. That would be an ADR, not a patch. |
| `tahoe` binary or `tahoe-lafs` inside the APK | Desktop already shells out to Tahoe for `--join`. The phone has no Tahoe binary, and `learn` does not want a nodedir. | Rejected. Tahoe 1.20's own dependency set is far larger than a mailbox client, and it would duplicate `lg_intro`. |

The redeem op returns one of: `ok`, `expired`, `rejected`, `relay`, `timeout`. Kotlin maps those to the strings below. A thrown traceback is a bug, same rule as `leasegrid_read.dispatch`.

Version: Tahoe 1.20 requires `magic-wormhole >= 0.10.2` and does not pin a single release. Do not float a version in this doc. The contract test in the E2E plan (desktop `tahoe invite` against the phone client, or the same library the desktop venv resolved) is what accepts a version. PyPI's current release at the time of writing is 0.24.0 (pure-Python wheel 213579 bytes, requires Python >= 3.10, which Chaquopy 3.11 satisfies). That number is a size data point, not the pin.

Do not install `magic-wormhole-mailbox-server` or `magic-wormhole-transit-relay` on the phone. The relay stays where it is (Tahoe's public relay, or the lab relay).

## Dependencies and APK size

Already on the phone (`chaquopy.defaultConfig.pip`):

- Python 3.11, ABIs arm64-v8a and x86_64
- foolscap==24.9.0
- twisted==25.5.0
- cryptography below 45, pyOpenSSL below 25, service-identity below 25

Those stay. Do not bump Twisted or cryptography to satisfy the new package. magic-wormhole's lower bound (`twisted[tls] >= 17.5.0`) is already met.

A mailbox client adds, from magic-wormhole 0.24.0's `install_requires` (confirm against the version the contract test accepts):

| Package | Why it is there | Size note |
|---------|-----------------|-----------|
| magic-wormhole | The client. Wheel on PyPI for 0.24.0 is 213579 bytes, pure Python. | Small. |
| spake2==0.9 | Password-authenticated key exchange. Pure Python. | Small. |
| pynacl | libsodium. PyPI ships manylinux and macOS wheels, not Android wheels. Two published PyNaCl 1.5.0 manylinux wheels are 680.1 kB (aarch64) and 1.1 MB (x86_64). Those are glibc wheels, not APK entries, and 1.5.0 may not be the version the resolver picks. | This is the native-build risk. One libsodium `.so` per ABI already in the app (two ABIs). |
| autobahn[twisted] | Websocket. 0.24.0 excludes several 25.x releases. Honor that exclusion. | Do not force a newer autobahn. |
| automat, attrs, click, humanize, tqdm, iterable-io, zipstream-ng | Library deps. Pure Python. | Small. The phone does not need the CLI. |
| txtorcon >= 18.0.2 | Install requirement of the package. | Do not add a Tor path on the phone. |
| qrcode >= 8 | Install requirement. The phone does not draw a QR. | Confirm at implement time whether this pulls Pillow. If it does, that weight is unused. Prefer not to import `qrcode` from the redeem op. Desktop QR stays on segno in `invite.py`. |
| cryptography | Already capped. | No second copy. |

This lane did not build an APK. The GitHub runner was up at the start of the run, and the drop-in forbids `uv`, `./pfy`, and a Python suite while it is. There is no checked-in APK size to subtract from. Do not treat the wheel sizes above as the APK delta.

Implement gate for size, before calling the slice done:

1. Record `app-debug.apk` bytes on the parent commit, and again after the pip line, same machine, both ABIs.
2. The expected growth is the libsodium `.so` files plus a few hundred kilobytes of Python, not a Tahoe install.
3. If pynacl will not build for arm64-v8a under Chaquopy, stop. That is the open question on a native client, not a silent fallback.
4. If Pillow appears in the APK only because of `qrcode`, drop that import path or exclude the unused wheel. Do not add segno to Android.

## Fail and recover copy

Voice of design 61: short sentences, desktop labels exact, no banned word, parse problems carry the recovery in the banner and have an empty Next line, operational problems have a Next line, Retry reruns `join()` with the current field.

`JOIN_FAILED` / `JOIN_FAILED_NEXT` stay for a redeem that succeeded and a `learn` that did not. Do not add a second learn-fail sentence.

### Screen (first slice)

| Key | String |
|-----|--------|
| TITLE | Join a shared folder (unchanged) |
| BODY | On your computer, click Share invite in Leasegrid Sync. Type the short code below, or tick Show full join link (advanced) and paste that link. |
| INPUT_HINT | Short code or join link |
| EMPTY | Enter a short code or paste the join link first. |

BODY still contains `Share invite` and `Show full join link (advanced)` so the label pin has the same words. `InviteCopyTest.screenCopyMatchesDesign` changes the hint pin, and `failCopyMatchesDesign` changes the empty-field pin, to these sentences. Do not delete either pin. Join stays disabled while the field is empty, so this banner is the fallback if a caller still shows it.

`WORMHOLE_MSG` is no longer what a short code shows. The test that asserts that banner and "never joins" is the red proof that option 1's refusal is gone. Replace it. Do not leave both.

### Redeem failures (first slice)

These have a Next line. None of them call `learn`.

| Case | Banner | Next | How it recovers |
|------|--------|------|-----------------|
| Expired, or the code was already used (`Lonely` / expired on the desktop map) | This code expired. | On your computer, click Share invite again. Keep Leasegrid Sync open, type the new short code here, then tap Retry. | A new code from a live Share invite, then Retry. Retry on the dead code fails again, on purpose. |
| Relay unreachable, name lookup failed, connection refused, or the desktop used a different relay | Couldn't reach the invite relay. | Check that this phone is online and Leasegrid Sync is still open on your computer, then tap Retry. If it still fails, tick Show full join link (advanced) and paste that link here. | Network back and the same relay, then Retry. Or paste the advanced link, which skips the mailbox even while the relay is down. |
| Rejected (`WrongPassword`, crowded, or Tahoe refused the client hello) | This code was not accepted. | On your computer, click Share invite again and use the new short code. Keep Leasegrid Sync open, then tap Retry. | A new code. Same as the desktop "not accepted" path, without the desktop's banned words. |
| 120 seconds with no inviter answer | Nobody answered this code yet. | Keep Leasegrid Sync open on your computer until this phone joins, then tap Retry. If the code is old, click Share invite again and type the new short code. | Retry only works if the desktop card is still waiting. Otherwise take a new code. |

Map desktop `join_process_failure` markers onto these four statuses in the Python op. Do not copy stderr, the exception class, the relay URL, or the code into the banner.

### QR failures (later slice)

Empty Next line, same as today's parse refusals. Scan is not required for Join.

| Case | Banner | Recovery |
|------|--------|----------|
| Camera denied or the permission dialog dismissed | This phone can't use the camera. Type the short code, or tick Show full join link (advanced) and paste that link. | Type or paste. Join still runs. Do not ask for the camera again until they tap Scan. |
| No symbol, or a symbol that decodes to text today's parser already calls garbage | That QR isn't a join. Point the camera at the code on Share invite, or type the short code under it. | A QR of the share-card code redeems. A QR of the advanced join link, or of the I2P page, takes the option 1 path. Typing the short code also works. |

Garbage, web URL, missing address, and malformed link keep today's banners. A too-long paste (#78) is still that class of failure, never a redeem.

## Privacy

| Data | Short code | Join-link QR or advanced paste |
|------|------------|--------------------------------|
| Who can see the introducer | The two ends, after the key exchange. The relay sees the numeric nameplate, both IPs, timing, and ciphertext size. It does not see the introducer if the exchange holds. Tahoe's own invite doc describes this as a one-time code plus a server that opens a channel, and says the introducer address must stay secret. | The fragment holds the introducer in the clear (`format_join_url` puts it in `i`). Anyone who can see the screen, the clipboard, the I2P page, or a photo of a join-link QR has the long-lived address. |
| Lifetime | Single use. The desktop process must stay up. A second phone with the same code fails closed (expired or not accepted). | The link keeps working until the introducer changes. That is why it is behind the checkbox. |
| Phone logs | Do not log the code, the link, the mailbox JSON, or the relay URL. `dispatch` already returns JSON to Kotlin. The redeem result must not include the raw message. | Same rule option 1 already has for the pasted link: it is in the field, not in a banner. |
| Camera | Not used in the first slice. | Later slice: decode on device. A decoder that uploads frames is out. |
| Bug reports | Desktop already redacts codes through the PGP word list (`pgp_words.py`) without importing the wormhole package. The phone has no bug-report sender in this slice. Do not add one. If a later slice adds one, it reuses that word list. | A pasted link is a secret of the same class as a recovery file. Do not put it in logcat. |

Dev-grid note, not a user string: a code minted on `127.0.0.1` is not reachable from a phone or from an emulator (the emulator's name for the host is `10.0.2.2`). Using the public relay for a lab test would send a real nameplate to `wormhole.tahoe-lafs.org`. Lab E2E injects the lab relay on both sides.

## E2E test plan

Name: desktop share card to phone join.

This is one behavior test with fail and recover arms, not a test that the design file exists. Doubles sit only at the mailbox and at `learn`. One contract test talks to a real mailbox.

### Setup

- Desktop: Leasegrid Sync joined to a lab grid, Share invite open, short code visible, process alive. Relay is the dev-grid mailbox (`docs/ops/dev-grid.md`: `ws://127.0.0.1:45040/v1` on the host), injected on the phone as the host address the emulator can route. Do not point this test at the public relay.
- Phone: the slice-1 build, emulator is enough for the no-camera slice. After the threat checkbox, `adb input text` into `invite_field` (the focus handoff in `SyncApp` already exists).
- Record the code only inside the test process. Do not print a real grid's code or address in the run log.

### Happy path

1. Desktop shows a code and a QR of that same code (existing UI test already decodes the card).
2. Phone: checkbox, enter that code, Join.
3. Pass: Folders is showing, `learn` was called with the lab introducer, and shares match the invite or the 2, 3, 3 default. The invite field is not on the Folders screen. On a failed join, before this pass, the field still holds what was typed.
4. A second client (a fresh phone process, not a second tap on Folders) redeems the same code. It does not create a session. Banner is "This code expired." or "This code was not accepted." `learn` is not called on that second attempt. After a successful join the app is on Folders, which has no invite field.

### Fail and recover

| Arm | How it fails | What the phone shows | How the test recovers |
|-----|--------------|----------------------|------------------------|
| Expired | Quit Sync, or kill the `tahoe invite` process, before Join. Do not use the dialog's Done button. That button does not stop the code. | This code expired. Field kept. No Folders. | Open Leasegrid Sync, open Share invite again, enter the new code, Retry. Folders appear. |
| Relay down | Phone relay injected at a closed port. Desktop card still open on the lab relay. | Couldn't reach the invite relay. `learn` not called. | Paste the advanced join link from the same card. Folders appear with the relay still closed. Then, separately, point the phone back at the lab relay, put the code back, Retry, and Folders appear without the link. |
| Nobody answered | Invite process alive, but the test double's budget is a fraction of a second and the client hello is withheld. Do not sleep 120 seconds, and do not assert that a source constant equals 120 by reading it back. The production op uses `WORMHOLE_JOIN_TIMEOUT` unless the test injects a shorter budget. | Nobody answered this code yet. | Deliver the hello on Retry while the desktop card is still up. Folders appear. |
| Camera denied | Later slice only. Do not grant CAMERA. | This phone can't use the camera. ... | Enter the short code. Join works. The permission dialog does not reopen by itself. |
| Bad QR | Later slice only. Feed a fixture image with no symbol, then a QR whose text is `hello`. | That QR isn't a join. ... No redeem. | Feed a QR fixture of the share-card payload (the short code). Redeem runs. Feed a QR fixture of the advanced link. `learn` runs and redeem does not. |

### What is not a sufficient test

- A unit test that asserts the new banner constants equal themselves.
- A mock that only checks the mailbox function was called, with no introducer coming back.
- An emulator screenshot of the empty Invite screen.
- A camera test that needs a physical phone. The later slice uses image fixtures. A hardware camera pass is And's dogfood, not the merge gate.

### Contract test (the double's reality check)

Against `magic-wormhole-mailbox-server` (already in the desktop `[tahoe]` extra) or a lab `tahoe invite`:

1. Inviter runs the Tahoe 1.20 server side of the handshake and sends a known fake introducer plus shares 2, 3, 3.
2. The phone redeem op, on the host, returns `ok` and that introducer.
3. A client that skips `client-v1` does not receive the config. That is the failure mode of a partial port.
4. An inviter that has already closed returns `expired` or `rejected`, never the introducer.

JVM tests use a fake redeem op that returns those statuses. They do not reimplement the handshake. If the fake and the contract test disagree, the contract test wins.

### Copy guards that stay

- `bannedWords` covers every new string, including the QR banners.
- Desktop label strings stay exact: `Share invite`, `Show full join link (advanced)`.
- `screenCopyMatchesDesign` is updated for BODY and INPUT_HINT, not weakened to a substring of the old sentence.
- Parse failures still have an empty Next line. Redeem failures do not.

## Recommendation

Build short-code redeem first, in Chaquopy, with no camera and no desktop change.

The share card people already see is a short code and a QR of that code. The phone refuses that text today. Redeeming it is the gap #77 names. A camera pointed at the card does not remove the gap. A camera pointed at a join-link QR only skips a paste the phone already accepts, and it asks for a new permission. Putting the join link into the share-card QR would undo the #32 choice to keep that address behind the checkbox.

Option 1 paste remains in the same field and is the recovery when the relay is wrong, down, or not the one the desktop used.

Do not port the mailbox protocol to Kotlin in this slice. Do not put Tahoe in the APK.

QR scan is a second slice, after the E2E above is green: Scan beside the field, on-device decode, same parser. Not a different join.

## OPEN QUESTIONS

For Mark. Defaults are what implement should use if these stay unanswered. None of them block this design.

1. Is short-code redeem, without a camera, the slice to build? Default: yes.
2. What APK growth is too much? This lane did not measure the current APK. Default: record the byte delta at implement time, accept libsodium for the two existing ABIs, stop if pynacl will not build for arm64-v8a.
3. Native mailbox client instead of Chaquopy? Default: no. Needs an ADR if the answer is yes. Do not start one in the implement slice.
4. Phone wait before "nobody answered"? Default: 120 seconds, same as desktop `WORMHOLE_JOIN_TIMEOUT`.
5. A phone setting for a private relay? Default: no. Unset means Tahoe's public relay. Lab tests inject the URL. A code minted on a loopback relay recovers by pasting the advanced link.
6. Build the camera slice after redeem is green? Default: not until then. Decoder must be on-device and offline. Which library is undecided on purpose.
7. Should `nickname` from the invite be stored? Default: no. The phone does not create a Tahoe node. Share counts are stored only when they pass the same `n <= h <= t` check as a join link.

## Implement slice (not this lane)

When a later lane is allowed to touch the files:

| Piece | Files | Notes |
|-------|--------|-------|
| Accept a code, new copy | `Invite.kt`, `InviteCopyTest.kt` | After #78 and #80. Keep their length bound ahead of the pattern. |
| Redeem then learn | `SessionFlow.kt`, `SessionFlowTest.kt` | Fake redeem op. `learn` not called on expired, relay, rejected, or timeout. |
| Handshake | new module under `android/app/src/main/python/`, one op on `leasegrid_read.dispatch` | Status enum only across the Kotlin boundary. |
| Pip line | `android/app/build.gradle.kts` | Plus the APK byte note in the implement handoff. |
| Contract | a host test beside `android/pytests/`, mailbox only | Not a full `unittest discover` while the GitHub runner is up. |
| Leave alone in slice 1 | `app.py`, `AndroidManifest.xml`, the share-card QR payload | Camera permission waits for the QR slice. |

`bot/lg-78-invite-1031` owns `Invite.kt` until that lane finishes. `bot/lg-80-appmodel-1031` owns `AppModel.kt` and `SyncApp.kt`. Slice 1 does not need those two if the field, the checkbox, and `join()` stay as they are.
