# 61, Android Invite: join link copy (#50, option 1)

Status: copy-only. Short-code redeem on Android is a follow-up and not built yet.

Rule: every phone message sends people to desktop Share invite > tick 'Show full join link (advanced)'. The labels match desktop exactly and a test pins them. Banned in user-visible text: furl, pb://, introducer, wormhole, friendnet, and lowercase 'could not join'.

Strings:
- Title / join button: Join a shared folder
- Body: On your computer, click Share invite in Leasegrid Sync and tick Show full join link (advanced). Copy that link and paste it below.
- Hint: Paste the full join link
- Empty: Paste the join link first. (Join stays disabled while the field is empty, if it's cheap.)
- Short code: That's a short code. This phone can't use short codes yet. On your computer, tick Show full join link (advanced), then paste that link here.
- Garbage / no-address / malformed / web URL: the approved strings in Invite.kt. None of them gets a Next line.
- Join failed: Couldn't reach your computer. Next: Check that Leasegrid Sync is open on your computer and this phone is online, then tap Retry. If it still fails, copy the join link again from your computer and paste it here. Retry reruns the join.
- Folders refresh failed: Couldn't reach your computer. Next: Check that Leasegrid Sync is open on your computer and this phone is online, then tap Retry.
- Folders import failed after save: Saved on this phone. Couldn't reach your computer to finish. (Next is the same as refresh.)

Tests: the banned-word guard covers every user-visible string. The desktop label test pins 'Share invite' and 'Show full join link (advanced)'. Pasting a short code shows its own message, with no Next line and no join attempt. With a fake unreachable desktop, the failure pair shows and Retry rejoins. Recover: if a desktop label drifts, the pin test fails before release.

Guard scope today: Invite.kt, SessionFlow.kt, AppModel.learn() and the SyncApp Invite/join section; other legacy banners are tracked as a follow-up.
