# Changelog

## Unreleased

## 0.1.8 (2026-10-20)

- A newer invite handed to a running app replaces an older pending one (latest wins).
- Closing a refused second launch with Ctrl-C, SIGTERM or SIGHUP while the "already running" box is open now exits cleanly (exit 0) instead of crashing.
