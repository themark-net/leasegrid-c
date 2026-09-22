# P4 Android Slice A → DevBot / Cursor handoff — **read-first APK**

**Status:** Design DoD 2026-09-22 PT  
**Implement against:** this `docs/design/` package (`35`–`38`) + issue [#23](https://github.com/themark-net/leasegrid-c/issues/23)  
**Cite tip:** main ≥ **`7837ef8`**  
**PM RELEASE:** CEO/PM RELEASED P4 Android **Design** (2026-09-22). After Design PASS, PM RELEASE Cursor/Build for **Slice A implement**.  
**Tester:** **And** (Android UI tester) — emulator dogfood after implement.  
**Do not:** ship Tahoe WUI; Electron-on-Android; invent second recovery format; demote desktop; block on Slice B; claim Play Store / iOS / U5; contact Mark; rewrite `10`–`34`.

---

## Track map

| Slice | Work | Owner |
|-------|------|-------|
| U0–U4 + AppImage | Desktop Sync primary | Preserve — **no regress** |
| **P4-A** | Android read-first APK (join/import → folders → download/open) | **Design → Cursor/Build** |
| P4-B | Write / Magic Folder–class sync on Android | Parked — follow-on only |
| U5 | Faucet → XMR | Deferred |

**This handoff = P4 Slice A Design → implement only.**

---

## Slice A DoD (tight) — mirrors issue #23

### Must prove

1. **Join path:** First-run threat HITL; Join disabled until ACK; unpaid invite join works.  
2. **Import path:** Import U4 `*.leasegrid-recovery` (same format as desktop); wrong passphrase / corrupt → FAIL + Next in-app; no half-created home.  
3. **Folders primary:** After join/import, Folders list is home; Offer/Credit not required.  
4. **Download/Open:** Operator can open a folder, download a file to device, and open it (system viewer OK).  
5. **Operate-or-FAIL:** Join / import / list / download either work or FAIL + Next **in-app** (no WUI Next; no terminal-only Next; no “only use desktop” as sole Next for a fetch the phone should do).  
6. **No Tahoe WUI:** Not embedded as product UI.  
7. **Desktop preserved:** Implement must not regress desktop Sync / AppImage paths on tip ≥ `7837ef8`.  
8. **Recovery honesty:** Loss = total loss copy present; no second recovery format.  
9. **APK artifact:** CI or documented local build produces installable APK at the path below.  
10. **Dogfood:** **And** can follow emulator steps and report PASS/FAIL.  
11. **Artifacts:** Design under `docs/design/` (`35`–`39`); implement cites this handoff + #23 + tip ≥ `7837ef8`.

### Explicitly out of Slice A implement

| Item | Where it lives |
|------|----------------|
| Write / Magic Folder sync on Android | Slice B (later) |
| iOS | Out |
| Play Store listing | Out |
| Tahoe WUI / WebView-as-product | Never product |
| Electron-on-Android | Rejected |
| Operator Node kit | Out |
| U5 / mainnet XMR | Deferred |
| Rewriting `10`–`34` | Forbidden |
| Demoting desktop Sync | Forbidden |

---

## Stack recommendation (Design decision)

### Recommend (lean Slice A)

**Kotlin + Jetpack Compose** Android app that:

- Speaks the **same friendnet / capability model** as desktop Leasegrid Sync (read caps from join or U4 recovery import).  
- Owns native UI (Welcome/Join, Folders, folder detail, download/open) — **not** a WUI wrapper.  
- Reuses U4 recovery decode semantics (`*.leasegrid-recovery` v1 envelope + optional passphrase) — port or share logic carefully; do **not** invent format v2 for phone.  
- May use a thin native or JNI/FFI bridge to existing Tahoe/Magic-Folder **read** client pieces **or** a purpose-built read client against the same caps — implementer choice, but must dogfood on emulator without requiring desktop for every open.  
- Targets recent Android API (document minSdk in implement notes; emulator API 34+ OK for And).

Rationale: lean, native, matches folders-first IA, avoids WebView-as-product, ships an APK And can install.

### Acceptable variants (must still meet DoD)

| Variant | Allowed if… |
|---------|-------------|
| Kotlin + XML Views | Same IA + no WUI; Compose preferred |
| Thin wrapper around a headless sync/read daemon | UI is still native Compose/Views; daemon is not WUI |
| Shared Rust/Go read core + Kotlin UI | Recovery format + caps stay U4-compatible |

### Reject list (binding)

| Reject | Why |
|--------|-----|
| **Shipping Tahoe WUI in WebView as the product** | Founder lock; #23 forbids WUI |
| **Electron-on-Android** | Wrong stack for phone MVP |
| **Requiring desktop Sync for every file open** | Breaks companion promise after join/import |
| **Inventing a second recovery format** | U4 file is the one path |
| **Play-Store-first / iOS-first diversion** | Out of Slice A |
| **Half-shipping Slice B write buttons that fail** | Hide write until Slice B |

---

## APK artifact path (binding for dogfood)

| Item | Path / rule |
|------|-------------|
| **Module (suggested)** | `android/` or `src/leasegrid_android/` at repo root (implementer may adjust — **document actual path in dogfood note**) |
| **Debug APK (default dogfood)** | `android/app/build/outputs/apk/debug/app-debug.apk` |
| **CI artifact name** | `leasegrid-sync-android-slice-a-debug.apk` (upload beside other CI artifacts) |
| **Install** | `adb install -r <apk>` |
| **ApplicationId (suggested)** | `net.themark.leasegrid.sync` (or `…sync.android`) — freeze in implement PR |

If the build layout differs, handoff still PASSes only when And’s dogfood note cites the **real** APK path used.

---

## Emulator dogfood steps (for **And**)

Prereqs: Android emulator API 34+ (or device); `adb`; friendnet invite **or** a U4 `*.leasegrid-recovery` from desktop Sync @ tip ≥ `7837ef8`; one known small file already on the grid.

1. `adb install -r` the Slice A debug APK from the artifact path above.  
2. Launch **Leasegrid Sync**; confirm **no** Tahoe WUI / browser chrome as the product.  
3. **Path Join:** Read threat copy → check ACK → paste invite → Join → land on **Folders**.  
   **— or — Path Import:** Tap **Import recovery key instead…** → pick `*.leasegrid-recovery` → passphrase if any → Import → land on **Folders**.  
4. Open one folder; confirm file list appears.  
5. Download/open one known file; confirm it opens on device (Gallery / Files / viewer).  
6. Toggle airplane mode and retry download → expect **FAIL + Next + Retry** in-app (not a silent hang).  
7. Confirm Offer/Credit are **not** required to complete steps 3–5.  
8. Confirm desktop Sync on tip still launches / is not broken by the Android PR (smoke: AppImage or `leasegrid-sync` as available on dogfood host).  
9. File a short dogfood note: PASS/FAIL, APK path, emulator image, tip SHA, issue #23 — **no** Mark drip; **no** Play Store / Slice B / U5 claims.

---

## Suggested build order

1. Skeleton Compose app + Folders empty / Welcome.  
2. Threat HITL + Join against lab friendnet.  
3. U4 recovery import (decode + join/read caps).  
4. Folder list + folder detail (read).  
5. Download to storage + Open with.  
6. FAIL banners for join/import/list/download.  
7. Wire CI APK artifact path.  
8. Hand to **And** for emulator dogfood.  
9. Fix FAIL gaps; report PASS to PM for Slice A implement exit.

---

## Design references (read before coding)

| Doc | Use |
|-----|-----|
| [35-P4-ANDROID-A-JOURNEY.md](35-P4-ANDROID-A-JOURNEY.md) | Happy paths + FAIL |
| [36-P4-ANDROID-A-IA.md](36-P4-ANDROID-A-IA.md) | Places + CTA ranks + Slice B park |
| [37-P4-ANDROID-A-WIREFRAMES.md](37-P4-ANDROID-A-WIREFRAMES.md) | ASCII mobile frames |
| [38-P4-ANDROID-A-NON-GOALS.md](38-P4-ANDROID-A-NON-GOALS.md) | Hard rejects |
| U4 `30`–`34` | Recovery import honesty + format |
| P1 `25`–`29` | Folders-first metaphor |
| `src/leasegrid_sync/recovery.py` | U4 envelope constants (do not fork format) |
| Issue [#23](https://github.com/themark-net/leasegrid-c/issues/23) | Binding Design DoD |
| Tip ≥ `7837ef8` | Base — no desktop regress |

---

## Slice A exit checklist (DevBot / And report PASS/FAIL)

- [ ] Tip / branch documented; cite ≥ `7837ef8` + issue #23  
- [ ] Threat HITL: Join blocked until ACK  
- [ ] Join path reaches Folders  
- [ ] Import U4 recovery key reaches Folders  
- [ ] Import FAIL (bad passphrase / corrupt) in-app; no partial home  
- [ ] Folders list primary; Offer/Credit not required  
- [ ] Download + open one file on emulator  
- [ ] Download FAIL path in-app with Next + Retry  
- [ ] No Tahoe WUI affordance  
- [ ] No second recovery format  
- [ ] APK path documented; And installed via adb  
- [ ] Desktop Sync smoke still OK (no regress)  
- [ ] Dogfood note for PM — **no** Play Store / iOS / Slice B-done / U5 claims  

---

## Operate-or-FAIL reminder

Every Slice A control (Join, Import, Refresh folders, Download, Open, Retry) either performs its action or shows buyer-visible **FAIL** with a concrete **Next** in-app. Silent failure is itself FAIL for this handoff.

---

## One-liner for PM

> **P4-A:** Ship a read-first Android APK — join or import U4 recovery → folders → download/open — Kotlin/Compose (no WUI / no Electron-on-Android), tip ≥ `7837ef8`, And emulator dogfood, without blocking on Slice B or demoting desktop Sync.
