# Autonomous decisions — 2026-10-16

v0.1.2 bump PR on Mark approval (notes via body_path, SHA256SUMS for checksums); tag/release only after merge | hand-edit v0.1.1 release body | v0.1.1 stays as cut; next tag gets the tester notes
list_folders rewrites ensure_running "folder not added." to "could not refresh folders."; #30 refresh copy uses SyncError.http_status == 500 | match the substring "HTTP 500", or change ensure_running's own sentences | a refresh is not an add; add-folder and recovery keep "folder not added."; text that mentions HTTP 500 without status 500 is not #30
