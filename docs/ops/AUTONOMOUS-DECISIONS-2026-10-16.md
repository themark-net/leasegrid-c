# Autonomous decisions — 2026-10-16

v0.1.2 bump PR on Mark approval (notes via body_path, SHA256SUMS for checksums); tag/release only after merge | hand-edit v0.1.1 release body | v0.1.1 stays as cut; next tag gets the tester notes
Only Linux generates release notes when docs/release-notes/<tag>.md is missing; macOS and Windows pass an empty body_path and generate_release_notes false | keep generate==true on all three tag jobs | softprops v2 appends generated notes onto the stub, so the later jobs replace Linux's body. The notes file is still body_path on every job. Real check is the v0.1.3 tag (not cut here)
