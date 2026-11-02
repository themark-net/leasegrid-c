# Changelog

## Unreleased

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
