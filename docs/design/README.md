# Leasegrid Sync — Design DoD index

**Status:** **U4 Recovery — Design DoD ready** — 2026-09-21 PT  
**Owner:** Design Bot (executor staged on box)  
**Date:** 2026-09-21 PT  
**Product lock:** CEO/PM RELEASE U4 Design + [`docs/09-ui-track.md`](../09-ui-track.md) U4 · issue [#15](https://github.com/themark-net/leasegrid-c/issues/15) · tip **`4e1e6bd`** (P0+P1 CrashPlan shell)  
**Install target (nimo):** `/home/mark/DEVELOP/leasegrid-c/docs/design/`  
**Brand (provisional):** **Leasegrid Sync** — CrashPlan is a UX metaphor, not a product rename.

---

## Design index (post-Fable + UI track)

| Slice | Status | Exit / cite |
|-------|--------|-------------|
| **U0** | Design DoD done (`10`–`14`) | Native Sync product lock; five surfaces wireframed |
| **U1** | SHIP (Folders / Magic Folder / tray / join) | Preserve — no WUI |
| **U2** | Design/SHIP Credit (`15`–`19`) | Credit secondary; unpaid default |
| **U3** | Design DoD (`20`–`24`); AppImage **waived** for P0 CLEAR path | Installer polish not blocking |
| **P0** | CLEAR path on tip (do not re-claim in U4 notes) | Honesty — cite separately if PASS |
| **P1** | Design/SHIP CrashPlan shell (`25`–`29`) @ `4e1e6bd` | Folders-first + Offer pie; unpaid default |
| **U4** | **Design DoD ready** (`30`–`34`) | Threat HITL + recovery key export/import; non-expert walkthrough PASS |
| **U5** | Deferred | Faucet → XMR when 0c PASS |

**U4 one-liner:** Recovery-copy UX on CrashPlan shell — first-run threat HITL, dual-ACK recovery key export, import-on-new-device restore to Folders — without Tahoe WUI or payment lecture.

---

## Artifact index — U4 (this package)

| File | Contents |
|------|----------|
| [30-U4-RECOVERY-JOURNEY.md](30-U4-RECOVERY-JOURNEY.md) | Threat → join → export; import → Folders restore; FAIL paths |
| [31-U4-IA-RECOVERY.md](31-U4-IA-RECOVERY.md) | IA: Folders primary; Recovery under More; CTA ranks; copy layers |
| [32-U4-WIREFRAMES.md](32-U4-WIREFRAMES.md) | ASCII: threat Join; Recovery place; export gate; import; FAIL |
| [33-U4-NON-GOALS.md](33-U4-NON-GOALS.md) | WUI; reset-password; payment lecture; AppImage/U5 claims; rewrite 10–29 |
| [34-U4-DEVBOT-HANDOFF.md](34-U4-DEVBOT-HANDOFF.md) | Tight DoD + tests; cite #15 + tip `4e1e6bd`; operate-or-FAIL |
| [09-ui-track-U4-POINTER.md](09-ui-track-U4-POINTER.md) | Optional one-line pointer beside `09-ui-track.md` |
| [INSTALL-ON-NIMO.sh](INSTALL-ON-NIMO.sh) | Extract/copy into nimo `docs/design/` (preserves U0–P1 bodies) |
| [PARENT-INSTALL.md](PARENT-INSTALL.md) | CopyFromBox recipe for parent Design Bot |
| [phase-u4-design.tar.gz](phase-u4-design.tar.gz) | Tar of README + 30–34 (+ pointer) |

---

## Prior design (preserve — do not rewrite)

| Slice | Files | Role for U4 |
|-------|-------|-------------|
| U0 | `10`–`14` | Threat + Recovery baseline surfaces |
| U2 | `15`–`19` | Credit secondary; wallet may ride in recovery key |
| U3 | `20`–`24` | Installer must not claim recovery “done” until U4 PASS |
| P1 | `25`–`29` | Folders-first chrome; Recovery under More; unpaid default |

U4 **adds** recovery-copy DoD (`30`–`34`). It does **not** replace U0–P1 artifact bodies.

---

## Binding constraints (U4)

| Lock | Rule |
|------|------|
| Tip | main @ `4e1e6bd` (P0+P1 CrashPlan shell) |
| Issue | [#15](https://github.com/themark-net/leasegrid-c/issues/15) Design DoD |
| Threat HITL | First-run Join ACK required |
| Recovery chrome | More → Recovery (secondary); Folders stay primary |
| Export | Dual ACK + optional passphrase + plaintext warning + verified write |
| Import | Join + Recovery entry; restore → Folders |
| Operate-or-FAIL | In-window FAIL + Next |
| No Tahoe WUI | Not product UI |
| Unpaid default | No payment lecture on export/import |
| Honesty | Do not claim AppImage (#12) or U5/mainnet done |

---

## Success check (U4 Design PASS)

- [x] Recovery journey documented (export + import + threat HITL)  
- [x] IA fits CrashPlan shell (Folders primary; Recovery under More)  
- [x] Wireframes: threat Join; export gate; import; FAIL  
- [x] Non-goals explicit (WUI, reset-password, payment lecture, AppImage/U5)  
- [x] DevBot handoff cites #15 + tip `4e1e6bd`  
- [x] Operate-or-FAIL on journey + handoff  
- [x] U0–P1 bodies preserved (not rewritten)  
- [x] Package staged under `/workspace/leasegrid-u4-out/`  

**U4 Design exit:** Artifacts under `docs/design/` + DevBot handoff ready for implement / walkthrough PASS.

---

## Explicit non-goals (summary)

Tahoe WUI · “reset password” · rootcap paste as buyer path · payment lecture on unpaid export/import · Recovery as post-join primary · AppImage (#12) · U5/mainnet XMR · rewriting `10`–`29` · Mark drip from Design.

See [33-U4-NON-GOALS.md](33-U4-NON-GOALS.md).

---

## P4 Android Slice A (added — `10`–`34` unchanged)

**Status:** implement handoff landed. Design bodies `35`–`39` are the Design PASS package. This section only points at them.

| File | Role |
|------|------|
| [35-P4-ANDROID-A-JOURNEY.md](35-P4-ANDROID-A-JOURNEY.md) | Join or import → folders → download/open; FAIL |
| [36-P4-ANDROID-A-IA.md](36-P4-ANDROID-A-IA.md) | Places; Slice B parked |
| [37-P4-ANDROID-A-WIREFRAMES.md](37-P4-ANDROID-A-WIREFRAMES.md) | M1–M8 |
| [38-P4-ANDROID-A-NON-GOALS.md](38-P4-ANDROID-A-NON-GOALS.md) | WUI, Electron-on-Android, format v2, Play/iOS, Slice B writes |
| [39-P4-ANDROID-A-DEVBOT-HANDOFF.md](39-P4-ANDROID-A-DEVBOT-HANDOFF.md) | Binding implement handoff · issue #23 · tip ≥ `7837ef8` |
| [09-ui-track-P4-ANDROID-POINTER.md](09-ui-track-P4-ANDROID-POINTER.md) | Pointer beside the UI track |
| [../ops/p4-android-dogfood.md](../ops/p4-android-dogfood.md) | And emulator install path |

Module: `android/`. Debug APK: `android/app/build/outputs/apk/debug/app-debug.apk`. Application id: `net.themark.leasegrid.sync`. CI artifact: `leasegrid-sync-android-slice-a-debug.apk`.
