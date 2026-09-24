# Leasegrid Sync — Design DoD index

**Status:** **#38 Shell polish — Design DoD ready** (includes #32) — 2026-09-23 PT (~11:26pm PT)  
**Owner:** Design Bot (executor staged on box)  
**Date:** 2026-09-23 PT  
**Product lock:** CEO/PM RELEASE Shell polish Design · issues [#38](https://github.com/themark-net/leasegrid-c/issues/38) · [#32](https://github.com/themark-net/leasegrid-c/issues/32) · tip ≥ **`f46ab7c`** (`f46ab7ca423b72d7e5422ac46ccb2143ae881cfb`) · #27 SHIPPED @ `639163a` · #34 SHIPPED @ `442b76e` · CrashPlan folders-first + Offer pie stand · Servers primary / Credit under More · Marketing silent  
**Install target (nimo):** `/home/mark/DEVELOP/leasegrid-c/docs/design/` (+ pointer beside `docs/09-ui-track.md`)  
**Brand (provisional):** **Leasegrid Sync** — CrashPlan is a UX metaphor, not a product rename.

---

## Design index (post-Fable + UI track)

| Slice | Status | Exit / cite |
|-------|--------|-------------|
| **U0** | Design DoD done (`10`–`14`) | Native Sync product lock; Join-first intent |
| **U1** | SHIP (Folders / Magic Folder / tray / join) | Preserve — no WUI |
| **U2** | Design/SHIP Credit (`15`–`19`) | Credit secondary; unpaid default |
| **U3** | Design DoD (`20`–`24`); AppImage path separate | Installer polish not blocking #38 |
| **P0** | CLEAR path on tip (do not re-claim here) | Honesty — cite separately if PASS |
| **P1** | Design/SHIP CrashPlan shell (`25`–`29`) | Folders-first + Offer pie; unpaid default |
| **U4** | Design/SHIP Recovery (`30`–`34`) | Threat HITL + recovery key export/import |
| **U5 / #34** | SHIP Credit XMR top-up @ `442b76e` | Credit stays under More — **no rail redesign in #38** |
| **P4-A** | Design DoD / Slice A shipped (`35`–`39`) | Android read-first — **leave bodies alone**; desktop Sync still primary |
| **P4-B** | Parked | Android write — not this slice |
| **#27 Buyer storage** | SHIP / Design DoD (`40`–`44`) | Empty Join-first + Storage servers Add/Disconnect — **locks stand** |
| **#38 Shell polish** (+ **#32**) | **Design DoD ready** (`45`–`49`) | Lead journey + visual cleanup + invite short code/QR/Copy |

**#38 one-liner:** Join → Servers → Offer/store → Credit coherent; polish chrome; #32 invite = short code + QR + Copy (no raw FURL primary); tip ≥ `f46ab7c`; preserve #27/#34.

---

## Artifact index — Shell polish #38 (this package)

| File | Contents |
|------|----------|
| [45-SHELL-POLISH-JOURNEY.md](45-SHELL-POLISH-JOURNEY.md) | Lead path Join→Servers→Offer/store→Credit; pain→target; #32 share; FAIL |
| [46-SHELL-POLISH-IA.md](46-SHELL-POLISH-IA.md) | Places; Servers primary; Credit under More; invite entry points |
| [47-SHELL-POLISH-WIREFRAMES.md](47-SHELL-POLISH-WIREFRAMES.md) | ASCII: shell cleanup + #32 invite (code/QR/Copy); anti-FURL |
| [48-SHELL-POLISH-NON-GOALS.md](48-SHELL-POLISH-NON-GOALS.md) | Out: #28/#33/#26/#30; no new rails; Marketing silent |
| [49-SHELL-POLISH-DEVBOT-HANDOFF.md](49-SHELL-POLISH-DEVBOT-HANDOFF.md) | Implement DoD; dogfood; tip ≥ `f46ab7c`; Build-first nimo |
| [09-ui-track-SHELL-POLISH-POINTER.md](../09-ui-track-SHELL-POLISH-POINTER.md) | Pointer beside `09-ui-track.md` |

---

## Prior design (preserve — do not rewrite)

| Slice | Files | Role for #38 |
|-------|-------|--------------|
| U0 | `10`–`14` | Join-first intent + threat baseline |
| P1 | `25`–`29` | Folders-first CrashPlan shell + Offer pie |
| U2 | `15`–`19` | Credit secondary place |
| U4 | `30`–`34` | Recovery |
| P4-A | `35`–`39` | Android — **untouched** |
| #27 | `40`–`44` | Servers roster + both Add paths + honest Disconnect |

#38 **adds** shell polish DoD (`45`–`49`). It does **not** replace prior artifact bodies (`10`–`44`).

---

## Binding constraints (#38)

| Lock | Rule |
|------|------|
| Tip | main ≥ **`f46ab7c`** |
| Issues | [#38](https://github.com/themark-net/leasegrid-c/issues/38) Design (+ [#32](https://github.com/themark-net/leasegrid-c/issues/32) invite) |
| Lead journey | Join → Servers → Offer/store → Credit |
| #32 | Short code + QR + Copy; **no raw FURL primary** |
| #27 | Servers primary; empty Join-first; Join/Add always; both Add paths; honest Disconnect |
| #34 | Credit XMR stays; Credit secondary under More; no payment-rail redesign |
| Visual | Cleanup spacing/hierarchy/CTAs — not Marketing rebrand |
| Out | #28 / #33 / #26 / #30; Mark ops; mainnet rails |
| Lane | Design PASS → PM RELEASES DevBot Build-first on nimo |

---

## Success check (#38 Design PASS)

- [x] Journey: lead path + pain→target + #32 share + FAIL  
- [x] IA: Servers primary; Credit under More; invite entry points  
- [x] Wireframes: shell cleanup + invite code/QR/Copy + anti-FURL  
- [x] Non-goals: #28/#33/#26/#30; no new rails; Marketing silent  
- [x] DevBot handoff: DoD checklist; tip ≥ `f46ab7c`; Build-first nimo  
- [x] No contradictions with #27/#34  
- [x] Prior `10`–`44` preserved (not rewritten)  
- [x] Package staged under `/workspace/leasegrid-shell-polish-out/`  

**#38 Design exit:** Artifacts under `docs/design/` + DevBot handoff → PM RELEASES DevBot Build-first on nimo.

---

## Related (not this slice)

- [#28](https://github.com/themark-net/leasegrid-c/issues/28) Offer → payment — out  
- [#33](https://github.com/themark-net/leasegrid-c/issues/33) introducer marketplace — out  
- [#26](https://github.com/themark-net/leasegrid-c/issues/26) / [#30](https://github.com/themark-net/leasegrid-c/issues/30) — out  

See [48-SHELL-POLISH-NON-GOALS.md](48-SHELL-POLISH-NON-GOALS.md).
