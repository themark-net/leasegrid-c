# Autonomous decisions — 2026-10-16

v0.1.2 bump PR on Mark approval (notes via body_path, SHA256SUMS for checksums); tag/release only after merge | hand-edit v0.1.1 release body | v0.1.1 stays as cut; next tag gets the tester notes
Docs tighten (release notes, TESTERS, README): short pages + long content moved to docs/TESTER-GUIDE.md and docs/OVERVIEW.md; add docs/release-notes/TEMPLATE.md (no workflow change; body_path still reads <tag>.md) | delete detail or edit the v0.1.2 release body by hand | no facts lost; published v0.1.2 body stays as cut until the next tag
#63 tester follow-ups as a separate docs PR (not folded into PR E): log tables name the %APPDATA% fallback and the LEASEGRID_SYNC_HOME override; README gets back the macOS 15 Control-click line; README, TESTERS and the release-notes zip rows say leasegrid-sync-cli.exe is the console program | fold into PR E (#67) | E is a code fix with its own mutation proof; a docs-only diff reviews faster and merges independently
