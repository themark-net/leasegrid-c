# Leasegrid Sync — Design DoD index

**Status:** **P4 Android Slice A — Design DoD ready** — 2026-09-22 PT  
**Owner:** Design Bot (executor staged on box)  
**Date:** 2026-09-22 PT  
**Product lock:** CEO/PM RELEASE P4 Android Design · issue [#23](https://github.com/themark-net/leasegrid-c/issues/23) · tip **`7837ef8`** · roadmap Phase 4 (mobile read, then write) · desktop Sync (U0–U4 + AppImage) stays **primary**  
**Install target (nimo):** `/home/mark/DEVELOP/leasegrid-c/docs/design/`  
**Brand (provisional):** **Leasegrid Sync** — CrashPlan is a UX metaphor, not a product rename. Phone app name: **Leasegrid Sync (Android)** / short **Sync Mobile**.

---

## Design index (post-Fable + UI track)

| Slice | Status | Exit / cite |
|-------|--------|-------------|
| **U0** | Design DoD done (`10`–`14`) | Native Sync product lock; five surfaces wireframed |
| **U1** | SHIP (Folders / Magic Folder / tray / join) | Preserve — no WUI |
| **U2** | Design/SHIP Credit (`15`–`19`) | Credit secondary; unpaid default |
| **U3** | Design DoD (`20`–`24`); AppImage path separate | Installer polish not blocking P4 |
| **P0** | CLEAR path on tip (do not re-claim here) | Honesty — cite separately if PASS |
| **P1** | Design/SHIP CrashPlan shell (`25`–`29`) | Folders-first + Offer pie; unpaid default |
| **U4** | Design/SHIP Recovery (`30`–`34`) | Threat HITL + recovery key export/import |
| **U5** | Deferred | Faucet → XMR when 0c PASS — **not** P4 Slice A |
| **P4-A** | **Design DoD ready** (`35`–`39`) | Android read-first APK: join/import → folders → download/open |
| **P4-B** | Parked (follow-on only) | Write / Magic Folder–class sync on Android — does **not** block Slice A Design PASS |

**P4-A one-liner:** Read-first Android APK — join friendnet **or** import U4 recovery key → folders list → download/open files on device — operate-or-FAIL in-app, no Tahoe WUI, no desktop regress.

---

## Artifact index — P4 Android Slice A (this package)

| File | Contents |
|------|----------|
| [35-P4-ANDROID-A-JOURNEY.md](35-P4-ANDROID-A-JOURNEY.md) | Join/import → folders → download/open; FAIL paths |
| [36-P4-ANDROID-A-IA.md](36-P4-ANDROID-A-IA.md) | Phone IA; folders-first; Offer/Credit N/A or secondary; Slice B park |
| [37-P4-ANDROID-A-WIREFRAMES.md](37-P4-ANDROID-A-WIREFRAMES.md) | ASCII mobile frames |
| [38-P4-ANDROID-A-NON-GOALS.md](38-P4-ANDROID-A-NON-GOALS.md) | Write sync, iOS, Play Store, WUI, desktop regress, U5, Slice B blocking |
| [39-P4-ANDROID-A-DEVBOT-HANDOFF.md](39-P4-ANDROID-A-DEVBOT-HANDOFF.md) | Stack + rejects; APK path; emulator dogfood for And; tip ≥ `7837ef8` |
| [09-ui-track-P4-ANDROID-POINTER.md](09-ui-track-P4-ANDROID-POINTER.md) | Pointer beside `09-ui-track.md` |
| [INSTALL-ON-NIMO.sh](INSTALL-ON-NIMO.sh) | Extract/copy into nimo `docs/design/` (preserves U0–U4 bodies) |
| [PARENT-INSTALL.md](PARENT-INSTALL.md) | CopyFromBox recipe for parent Design Bot |
| [phase-p4-android-a-design.tar.gz](phase-p4-android-a-design.tar.gz) | Tar of README + 35–39 (+ pointer) |

---

## Prior design (preserve — do not rewrite)

| Slice | Files | Role for P4-A |
|-------|-------|---------------|
| U0 | `10`–`14` | Threat + Recovery baseline |
| U2 | `15`–`19` | Credit secondary — phone: N/A or deep-secondary |
| P1 | `25`–`29` | Folders-first metaphor → phone folders list primary |
| U4 | `30`–`34` | Recovery import path + honesty copy — **reuse**, do not invent a second format |

P4-A **adds** Android read-first DoD (`35`–`39`). It does **not** replace U0–U4 artifact bodies (`10`–`34`).

---

## Binding constraints (P4 Slice A)

| Lock | Rule |
|------|------|
| Tip | main ≥ **`7837ef8`** |
| Issue | [#23](https://github.com/themark-net/leasegrid-c/issues/23) Design DoD |
| Primary product | Desktop Sync (U0–U4 + AppImage) — **no regress** |
| Slice A MVP | Read-only / restore: join **or** import recovery → folders → download/open |
| Slice B | Document only; **must not** block Slice A Design PASS |
| IA | Folders-first; Offer/Credit secondary or N/A on phone |
| Payment / XMR | Not required for Slice A; unpaid default |
| Recovery | Same `*.leasegrid-recovery` as U4; loss = total loss |
| Operate-or-FAIL | In-app FAIL + Next (no WUI Next; no “use desktop only” as sole Next for open) |
| No Tahoe WUI | Not product UI (including WebView-as-product) |
| Honesty | Do not claim Play Store, iOS, write sync, or U5/mainnet done |
| Tester | **And** (Android UI tester) dogfoods after implement |

---

## Success check (P4-A Design PASS)

- [x] Journey documented (join/import → folders → download/open + FAIL)  
- [x] Phone IA folders-first; Offer/Credit N/A or secondary; Slice B parked  
- [x] Mobile ASCII wireframes  
- [x] Non-goals explicit (write sync, iOS, Play Store, WUI, desktop regress, U5, Slice B blocking)  
- [x] DevBot handoff: stack + reject list, APK path, emulator steps for And, tip ≥ `7837ef8`  
- [x] Operate-or-FAIL on journey + handoff  
- [x] U0–U4 rows preserved (not rewritten)  
- [x] Package staged under `/workspace/leasegrid-p4-android-out/`  

**P4-A Design exit:** Artifacts under `docs/design/` + DevBot handoff → PM RELEASE Cursor/Build for Slice A implement.

---

## Explicit non-goals (summary)

Full Magic Folder write sync · iOS · Play Store listing · Tahoe WUI / WebView-as-product · Electron-on-Android · requiring desktop for every open · inventing a second recovery format · operator Node kit · demoting desktop · U5/mainnet XMR · making Slice B block Slice A Design PASS · rewriting `10`–`34` · Mark drip from Design.

See [38-P4-ANDROID-A-NON-GOALS.md](38-P4-ANDROID-A-NON-GOALS.md).
