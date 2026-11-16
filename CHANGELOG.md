# Changelog

## Unreleased

- A leftover Tahoe or Magic Folder process that was started with a relative folder path is stopped on the next launch. The match uses that process's own directory. A process for a different folder, including one whose name only starts with the same letters, is left alone.
- A folder that already has a sync conflict still says Conflict when a newer file has changed, or when that conflict is outside the five newest changes. The folder page names the file and the next step. That line clears once the conflict is gone.
- Adding a folder whose name is already syncing a different directory stays on the page as a failure. Adding the same directory again does not create a second row.
- Android: an add when the phone has no room says there is not enough free space and does not upload. Retry tries that add again once there is room. The file is not shown as in the shared folder before that.
- Android: Keep both, when the second copy would not fit, leaves the question on screen and does not upload. Retry sends a different name once there is room. The file already in the folder is not replaced.
- Android: Keep both, when the phone will not allow the second copy, says so and leaves the question. Retry sends the next free name. It does not upload the original name, or a name the folder already has.
- Android: a leasegrid join link that puts the address in the query (`?`) joins, the same as on the computer. A non-empty `#` still wins. A web page address that only has a query is still rejected.
- Android: Replace, Keep both, or Cancel stays on screen if the process dies while that question is open. The file is not uploaded until one of those is chosen. A stored path that leaves the phone's files is dropped.
- Android: the list of files still waiting to upload is replaced as a whole. A write that stops keeps the previous list. A half-written temp file next to that list is not used.
- Desktop join: a short code that stops at the start of a word (such as the start of "deadbolt") is refused, and no node is created. The next full code can still join. A code the invite service says has expired still says so.
- Desktop join paste: a soft hyphen or another invisible paste mark in a short code or join link is dropped, so the link still joins. A right-to-left override in that paste is refused.
- Android: an add to a folder gives up after about 25 seconds when storage cannot be reached, the same budget as list, download and remove. It used to open a connection for every share.
- Android: a download the phone cannot save, or a file the phone cannot read for an add, says the phone would not allow it and to check storage permission, then Retry. It does not say network or free space, and it does not say to pick the file again.
- Android: an add that is still pending when the phone process dies stays on the folder as not in the shared folder yet, failed, with Retry. Retry sends the file that is still on the phone.
- Android: opening a recovery file, then rotating the phone or the process dying, does not import that file again and does not drop a home that was already saved.
- Android: a join link with a trailing period or closing mark, or wrapped in quotes, angle brackets, or parentheses, still joins. The extra characters are not sent to the computer.
- Android: Cancel on Import ignores a recovery read that was still waiting, including when Import is opened again.
- While Sync is open, a friendnet that cannot be reached, or storage that drops, shows what is wrong and a next step. The host line says none are connected. The next refresh that reaches them clears that line. A note written after it stays, and a credit pause stays.
- A join or recovery import that cannot reach the friendnet removes the node it just created, so a corrected invite or key can be tried. The window says the friendnet could not be reached, with a next step. A node that was already on this computer stays.
- Offering disk on a loopback address (the default, or `LEASEGRID_STORAGE_HOSTNAME` set to another 127.x address) listens on that address only. A LAN hostname is unchanged, so other computers can still connect.
- A Magic Folder scan or remote poll uses the daemon's PUT call, so Sync's request actually runs instead of waiting out the scan interval.
- A Sync home that cannot be created, or a home folder that cannot hold the lock file, says what is wrong and what to do next. It does not open a second window, and it does not say Leasegrid Sync is already running.
- A synced folder whose directory was removed shows Missing, with a next step, until that directory is back. It does not stay Idle or Up to date. A note written after that Missing line stays.
- A folder list that cannot be reached shows the error and the next step. The next refresh that lists folders clears that error. A note written after it, and a credit pause, stay on screen.
- Joining still opens Folders when the Tahoe config is not a settings file. The share link stays empty until an introducer is configured, instead of the window aborting.
- Android recovery import: a file name in the recovery extra is read from the app files folder. A path that leaves that folder (including `../`, an absolute path outside it, or a link that points outside) is refused, and the outside file is not read. A full path inside the app files folder still loads ([#26](https://github.com/themark-net/leasegrid-c/issues/26)).
- Android list and remove errors no longer say "download". A folder list that cannot reach storage says it could not load folders. A remove that cannot reach storage says it could not remove this file ([#85](https://github.com/themark-net/leasegrid-c/issues/85)).
- Android join paste: a soft hyphen (U+00AD) is dropped like the other invisible paste marks, so the link still joins. A right-to-left override, a plus sign, or a second @ in the link is reported as incomplete ([#85](https://github.com/themark-net/leasegrid-c/issues/85)).
- Android Join: Retry after a failure that is not a bad link or an unreachable computer joins the text in the field now. The tap itself still joins the text from that tap if the field changes before the join starts ([#85](https://github.com/themark-net/leasegrid-c/issues/85)).
- Android Import: the system Back button cancels the import, the same as Cancel and the back arrow ([#85](https://github.com/themark-net/leasegrid-c/issues/85)).
- Android list, download and remove give up after about 25 seconds when storage cannot be reached, and show the error card then. They used to wait out a timeout on every share.
- Desktop recovery import rejects a file over 1 MiB before parsing. Export refuses to write a key over that cap and leaves any file already there. A cut-off file, or one whose numbers are not numbers, fails with the import sentence and a next step.
- sync-ui.log drops furls, invite codes, capabilities, and passphrase values (the rest of that line) before they are written. The exception class stays.
- A folder that already has files on disk shows Syncing until Magic Folder lists them. An empty folder stays Idle. A conflict stays Conflict.
- On Linux and macOS, a second Ctrl-C, SIGTERM, or SIGHUP while a refused second launch is already closing is ignored, so that launch still exits 0. The first signal still closes the box. Windows is unchanged.
- Clearing the Join field while a replace question is open, then handing a new invite, drops the older pending invite. A later Yes cannot apply it.
- Android: when Join fails because the computer could not be reached, the next line no longer says to paste the join link. Paste advice stays on a link that is empty, cut off, or not a join link ([#82](https://github.com/themark-net/leasegrid-c/issues/82)).
- A lock written on another computer is not taken over while it is younger than 30 seconds, and that refusal returns at once. A same-host lock whose process is already dead is still reclaimed. A lock path that is a directory, or a lock file with no permissions, says what is wrong and what to do next instead of opening a second window.
- A quit signal during startup stops the Tahoe or Magic Folder process this launch started. The next launch stops a leftover daemon for this node directory only.
- The public log filter redacts an underscore-joined secret in one piece, so a digit fragment on the other side of `_` is not left in the CI log.

## 0.1.10 (2026-11-02)

- Android Invite: a paste of about 100 KB that is almost a short code shows "That isn't a join link." instead of failing, and Retry after fixing the field joins the corrected link ([#78](https://github.com/themark-net/leasegrid-c/issues/78)).
- Android join link checks: invisible marks (U+200B, U+200C, U+200D, U+2060, U+FEFF) are dropped anywhere in the paste; a link with control characters, a space, a short swissnum, an empty tub id or no address is reported as incomplete or asks for the address, and learn() is not called ([#78](https://github.com/themark-net/leasegrid-c/issues/78), [#80](https://github.com/themark-net/leasegrid-c/issues/80)).
- Android recovery import fails closed: a file over 1 MiB, nested deeper than 32, with scrypt settings over the caps, or with bad share counts shows the import card with Retry. Cancel and back on the import screen stop a running import and save nothing ([#80](https://github.com/themark-net/leasegrid-c/issues/80)).
- Android error cards and next lines no longer show an exception class, `pb://` or `Errno`; the class goes to the log. Retry runs the action once per tap, and a cancelled job no longer clears a newer job's busy state ([#80](https://github.com/themark-net/leasegrid-c/issues/80), [#84](https://github.com/themark-net/leasegrid-c/issues/84)).
- Android phone copy says "shared folder" instead of "friendnet"; the copy guard also reads AppModel.kt and MainActivity.kt and sees hidden spellings ([#80](https://github.com/themark-net/leasegrid-c/issues/80)).
- Desktop app unchanged apart from the version.

## 0.1.9 (2026-10-29)

- Android Invite asks for the desktop's full join link: on the computer, click Share invite and tick Show full join link (advanced), then paste it on the phone. Short codes and web links get a plain explanation instead of a raw error ([#50](https://github.com/themark-net/leasegrid-c/issues/50)).
- Android join, refresh and recovery-import failures say "Couldn't reach your computer." with one next step; an import that saved but could not finish says "Saved on this phone. Couldn't reach your computer to finish." A link cut inside an escape is reported as incomplete. The Join button reads "Join a shared folder" and stays off until a link is pasted (#50).
- Desktop app unchanged apart from the version.

## 0.1.8 (2026-10-20)

- Handing a running app the invite that is already in its Join field now drops an older pending replacement, so a later Yes cannot apply the stale invite (latest wins). A different invite still asks first; a replacement still needs Yes and then Join friendnet.
- On Linux and macOS, closing a refused second launch with Ctrl-C, SIGTERM or SIGHUP while the "already running" box is open now closes the box and exits 0 instead of being killed by the signal. Windows is unchanged.
