# Changelog

## Unreleased

## 0.1.9 (2026-10-29)

- Android Invite asks for the desktop's full join link: on the computer, click Share invite and tick Show full join link (advanced), then paste it on the phone. Short codes and web links get a plain explanation instead of a raw error ([#50](https://github.com/themark-net/leasegrid-c/issues/50)).
- Android join, refresh and recovery-import failures say "Couldn't reach your computer." with one next step; an import that saved but could not finish says "Saved on this phone. Couldn't reach your computer to finish." A link cut inside an escape is reported as incomplete. The Join button reads "Join a shared folder" and stays off until a link is pasted (#50).
- Desktop app unchanged apart from the version.

## 0.1.8 (2026-10-20)

- Handing a running app the invite that is already in its Join field now drops an older pending replacement, so a later Yes cannot apply the stale invite (latest wins). A different invite still asks first; a replacement still needs Yes and then Join friendnet.
- On Linux and macOS, closing a refused second launch with Ctrl-C, SIGTERM or SIGHUP while the "already running" box is open now closes the box and exits 0 instead of being killed by the signal. Windows is unchanged.
