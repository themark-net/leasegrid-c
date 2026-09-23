# Leasegrid Sync — Design DoD index

**Status:** **#27 Buyer storage — Design DoD ready** — 2026-09-22 PT (~10:15pm PT)  
**Owner:** Design Bot (executor staged on box)  
**Date:** 2026-09-22 PT  
**Product lock:** CEO/PM RELEASE Buyer storage Design · issue [#27](https://github.com/themark-net/leasegrid-c/issues/27) · tip ≥ **`5b752c7`** (`5b752c70dda4f5b4857c97556ace8881a8fed8f1`) · Mark/CEO lock 2026-09-22 · CrashPlan folders-first + Offer pie stand · public v* HOLD until Design then implement  
**Install target (nimo):** `/home/mark/DEVELOP/leasegrid-c/docs/design/`  
**Brand (provisional):** **Leasegrid Sync** — CrashPlan is a UX metaphor, not a product rename.

---

## Design index (post-Fable + UI track)

|| Slice | Status | Exit / cite |
||-------|--------|-------------|
|| **U0** | Design DoD done (`10`–`14`) | Native Sync product lock; Join-first intent |
|| **U1** | SHIP (Folders / Magic Folder / tray / join) | Preserve — no WUI |
|| **U2** | Design/SHIP Credit (`15`–`19`) | Credit secondary; unpaid default |
|| **U3** | Design DoD (`20`–`24`); AppImage path separate | Installer polish not blocking #27 |
|| **P0** | CLEAR path on tip (do not re-claim here) | Honesty — cite separately if PASS |
|| **P1** | Design/SHIP CrashPlan shell (`25`–`29`) | Folders-first + Offer pie; unpaid default |
|| **U4** | Design/SHIP Recovery (`30`–`34`) | Threat HITL + recovery key export/import |
|| **U5** | Deferred | Faucet → XMR when 0c PASS — **not** #27 |
|| **P4-A** | Design DoD / Slice A shipped on tip (`35`–`39`) | Android read-first — **leave bodies alone**; desktop Sync still primary |
|| **P4-B** | Parked | Android write — not this slice |
|| **#27 Buyer storage** | **Design DoD ready** (`40`–`44`) | Empty Join-first + Storage servers Add/Disconnect |

**#27 one-liner:** Clean Sync home = Join-first empty; after join, **Storage servers** lists hosts with **Add** (invite-to-Offer **and** paste storage furl) and honest **Disconnect**; Join/Add always reachable; tip ≥ `5b752c7`.

---

## Artifact index — Buyer storage #27 (this package)

|| File | Contents |
||------|----------|
|| [40-BUYER-STORAGE-JOURNEY.md](40-BUYER-STORAGE-JOURNEY.md) | Empty→Join; Servers; Add (both paths); Disconnect; FAIL; founder problem cite |
|| [41-BUYER-STORAGE-IA.md](41-BUYER-STORAGE-IA.md) | Places; Storage servers list; CTA ranks; introducer honesty |
|| [42-BUYER-STORAGE-WIREFRAMES.md](42-BUYER-STORAGE-WIREFRAMES.md) | ASCII: empty Join; Folders; Servers; Add both paths; Disconnect; FAIL |
|| [43-BUYER-STORAGE-NON-GOALS.md](43-BUYER-STORAGE-NON-GOALS.md) | Non-goals + explicit in-scope (roster + both Add paths) |
|| [44-BUYER-STORAGE-DEVBOT-HANDOFF.md](44-BUYER-STORAGE-DEVBOT-HANDOFF.md) | Files/areas; dogfood; tip ≥ `5b752c7`; operate-or-FAIL |
|| [09-ui-track-BUYER-STORAGE-POINTER.md](09-ui-track-BUYER-STORAGE-POINTER.md) | Pointer beside `09-ui-track.md` |
|| [INSTALL-ON-NIMO.sh](INSTALL-ON-NIMO.sh) | Extract/copy into nimo `docs/design/` (preserves `10`–`39`) |
|| [PARENT-INSTALL.md](PARENT-INSTALL.md) | CopyFromBox recipe for parent Design Bot |
|| [phase-buyer-storage-design.tar.gz](phase-buyer-storage-design.tar.gz) | Tar of README + 40–44 (+ pointer) |

---

## Prior design (preserve — do not rewrite)

|| Slice | Files | Role for #27 |
||------|-------|--------------|
|| U0 | `10`–`14` | Join-first intent + threat baseline |
|| P1 | `25`–`29` | Folders-first CrashPlan shell + Offer pie |
|| U4 | `30`–`34` | Recovery import alternate path |
|| P4-A | `35`–`39` | Android — **untouched**; desktop Sync primary |

#27 **adds** buyer storage DoD (`40`–`44`). It does **not** replace U0–U4 or P4 artifact bodies (`10`–`39`).

---

## Binding constraints (#27)

|| Lock | Rule |
||------|------|
|| Tip | main ≥ **`5b752c7`** |
|| Issue | [#27](https://github.com/themark-net/leasegrid-c/issues/27) Design DoD |
|| Founder problem | Mark ~10:11pm PT: Online-N with no Join on already-joined home — rejects “comes populated”; needs host control |
|| Empty Join-first | Clean home → Join only; no Online-N before join; no pre-baked buyer lab home |
|| Servers screen ★ | Primary host UX: list / status / Add / Disconnect (Mark 2026-09-22) |
|| Join/Add always reachable | Post-connect; Join-once-and-gone = FAIL |
|| Add paths | **Both** in Design: invite-to-Offer **and** paste storage furl |
|| Disconnect | This home’s used set only; no forever-remove from grid |
|| IA | Folders-first; Offer/Credit rank unchanged; no WUI |
|| Public v* | HOLD until Design then implement |
|| Android | Slice B not this slice; P4-A bodies preserved |

---

## Success check (#27 Design PASS)

- [x] Journey: empty→Join; Add both paths; Disconnect; FAIL; founder cite  
- [x] IA: Storage servers place; CTA ranks; introducer honesty  
- [x] Wireframes: Join empty; Folders; Servers; Add both; Disconnect; FAIL  
- [x] Non-goals + in-scope roster/furl stated  
- [x] DevBot handoff: files, dogfood, tip ≥ `5b752c7`, operate-or-FAIL  
- [x] Both Add paths required in Design (invite + paste furl)  
- [x] U0–U4 + P4-A rows preserved (not rewritten)  
- [x] Package staged under `/workspace/leasegrid-buyer-storage-out/`  

**#27 Design exit:** Artifacts under `docs/design/` + DevBot handoff → PM RELEASE Cursor/Build implement.

---

## Related (not this slice)

Issue [#28](https://github.com/themark-net/leasegrid-c/issues/28) Offer usage ↔ payment — log only; **out of #27**.

## Explicit non-goals (summary)

Implement in Design pass · Mark drip · mainnet XMR · Android Slice B as this slice · baking public friendnet into AppImage · demoting Folders/Offer · waiting on Mark Invite-vs-paste widget to ship Design · rewriting `10`–`39` · Tahoe WUI · fake forever-remove.

See [43-BUYER-STORAGE-NON-GOALS.md](43-BUYER-STORAGE-NON-GOALS.md).