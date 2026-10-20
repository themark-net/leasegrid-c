# Changelog

## Unreleased

## 0.1.8 (2026-10-20)

- Handing a running app the invite that is already in its Join field now drops an older pending replacement, so a later Yes cannot apply the stale invite (latest wins). A different invite still asks first; a replacement still needs Yes and then Join friendnet.
- On Linux and macOS, closing a refused second launch with Ctrl-C, SIGTERM or SIGHUP while the "already running" box is open now closes the box and exits 0 instead of being killed by the signal. Windows is unchanged.
