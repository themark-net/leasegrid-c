# P4 Android Slice A — Non-goals

**Status:** Design DoD 2026-09-22 PT  
**Cite:** issue [#23](https://github.com/themark-net/leasegrid-c/issues/23) · tip ≥ `7837ef8`

---

## Hard rejects for Slice A Design / implement

| Non-goal | Why |
|----------|-----|
| **Full Magic Folder write sync on Android** | Slice B — follow-on only; must not block Slice A Design PASS |
| **Making Slice B a Design PASS gate** | #23 Slice A is read-first MVP |
| **iOS app** | Explicitly out of Slice A |
| **Play Store listing / store assets** | Sideload / CI APK artifact is enough for implement dogfood |
| **Tahoe WUI as product UI** | Founder lock — including WebView wrapping WUI as the product |
| **Electron-on-Android as product** | Rejected stack path |
| **Requiring desktop running for every open** | After join/import, phone must fetch/open without “go to desktop” as sole Next |
| **Inventing a second recovery format** | Reuse U4 `*.leasegrid-recovery` |
| **Demoting desktop Sync** | Desktop (U0–U4 + AppImage) stays primary |
| **Operator Node kit on Android** | Buyer read companion only |
| **U5 / mainnet XMR / payment lecture for read** | Unpaid default; payment not required for Slice A |
| **Offer pie as phone primary chrome** | Folders-first; Offer N/A or hidden on Slice A |
| **Credit panel as gate before download** | N/A or deep-secondary |
| **Rewriting U0–U4 design bodies (`10`–`34`)** | P4-A adds `35`–`39` only |
| **Mark drip / SendToUser / git commit from Design** | Parent/PM owns commit & Mark contact |
| **Silent download “success” without bytes** | Operate-or-FAIL; verify local write before success copy |

---

## Stack rejects (Design decision — see handoff)

| Reject | Why |
|--------|-----|
| Shipping Tahoe WUI in WebView as product | Forbidden product surface |
| Electron-on-Android | Heavy, wrong fit for read-first MVP |
| Requiring desktop for every open | Breaks phone companion promise |
| Second recovery format / rootcap-paste-as-buyer-path | U4 file is the path; raw caps not product chrome |

---

## Stretch (optional, not Design exit)

| Item | Note |
|------|------|
| In-app rich preview (PDF/image) | System viewer enough |
| Phone-side recovery key **export** | Desktop export remains home for Slice A |
| Biometric lock for local secrets | Nice; OS app lock OK |
| Full offline tree cache | On-demand download is enough |
| Slice B wireframes beyond park note | Not required for Design PASS |

---

## In-scope reminder

Slice A **does** include: join with threat HITL; import U4 recovery key; folders-first list; folder drill-in; download/open on device; operate-or-FAIL; stack recommendation + reject list; APK artifact path; emulator dogfood steps for **And**; honesty that desktop stays primary and Slice B is later.
