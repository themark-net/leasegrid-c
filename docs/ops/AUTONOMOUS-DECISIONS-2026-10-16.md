# Autonomous decisions — 2026-10-16

v0.1.2 bump PR on Mark approval (notes via body_path, SHA256SUMS for checksums); tag/release only after merge | hand-edit v0.1.1 release body | v0.1.1 stays as cut; next tag gets the tester notes
Docs tighten (release notes, TESTERS, README): short pages + long content moved to docs/TESTER-GUIDE.md and docs/OVERVIEW.md; add docs/release-notes/TEMPLATE.md (no workflow change; body_path still reads <tag>.md) | delete detail or edit the v0.1.2 release body by hand | no facts lost; published v0.1.2 body stays as cut until the next tag
list_folders rewrites ensure_running "folder not added." to "could not refresh folders."; #30 refresh copy uses SyncError.http_status == 500 | match the substring "HTTP 500", or change ensure_running's own sentences | a refresh is not an add; add-folder and recovery keep "folder not added."; text that mentions HTTP 500 without status 500 is not #30
Android invite failures ask for the desktop full join link; a pb:// furl and a join link still parse; a short code still fails on the phone | redeem a short code on the phone | #50 option 1 is copy only; the share card hides the raw furl under Show full join link (advanced)
