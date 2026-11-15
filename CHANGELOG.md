# Changelog

## Unreleased

- Android recovery import: a file name in the recovery extra is read from the app files folder. A relative path that leaves that folder (including `../` or a link that points outside) is refused, and the outside file is not read. An absolute path is still used as given ([#26](https://github.com/themark-net/leasegrid-c/issues/26)).
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
