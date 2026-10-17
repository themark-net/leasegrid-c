# Handoff — Leasegrid Sync v0.1.7

The batch finish fills the rest of this file. The list below is the v0.1.5 leftovers. They are not implemented in v0.1.7.

## v0.1.8 candidates

- Log filter: separators other than `-` or space at 4 characters, and any separator every 5–7 characters.
- Log filter: percent-encoded base64 in URLs, and JSON-escaped `\/` base64.
- Log filter: secrets split across a line wrap into pieces under 20 characters.
- Log filter: lengths below each cutoff (base32 under 20, hex under 32, mixed-case under 32, base64url under 40). The short base32 fragment stays a strict xfail.
- Caveat guard misses 6 of 10 rewordings (for example "Coming soon", "available shortly after release", "may not work until CI publishes them").
- Base32-last ordering is an equivalent mutant kept as a backstop (0 leaks in every probe).
