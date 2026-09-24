# Shell polish → DevBot / Build handoff (#38 includes #32)

**Status:** Design DoD 2026-09-23 PT (~11:26pm PT) — ready for PM RELEASE implement  
**Cite:** [#38](https://github.com/themark-net/leasegrid-c/issues/38) · [#32](https://github.com/themark-net/leasegrid-c/issues/32) · tip ≥ **`f46ab7c`** (`f46ab7ca423b72d7e5422ac46ccb2143ae881cfb`) · #27 @ `639163a` · #34 @ `442b76e`  
**Design refs:** [45](45-SHELL-POLISH-JOURNEY.md) · [46](46-SHELL-POLISH-IA.md) · [47](47-SHELL-POLISH-WIREFRAMES.md) · [48](48-SHELL-POLISH-NON-GOALS.md) · pointer `docs/09-ui-track-SHELL-POLISH-POINTER.md`  
**Lane:** DevBot **Build-first on nimo** (Cursor only if Build blocked).  
**Do not:** implement in the Design pass; contact Mark; ship WUI; promote Credit tab; dump raw FURL as primary invite; rewrite `10`–`44` bodies.

---

## Product DoD (implement must prove)

1. **Lead journey coherent:** Join → Storage servers → Offer/store (Folders + Offer pie) → Credit (via More) feels intentional — fewer awkward hops; primary CTAs obvious.  
2. **Visual cleanup:** Spacing / hierarchy / primary button weight on lead-journey CTAs — not a Marketing rebrand.  
3. **#32 Invite share:** Primary share UI shows **short human code + QR + Copy** on Offer/share path (Servers → Add → Invite and/or Folders/More Invite entry).  
4. **No raw FURL primary:** Introducer `pb://…` is **not** the default visible share string or sole Copy target. Advanced join-link disclosure OK; storage-furl paste (#27 Path B) remains separate.  
5. **#32 Join accept:** Join continues to accept short code / join link / QR payload; placeholder/copy does not push raw FURL as the normal path.  
6. **Servers primary preserved:** Roster list / status / Add / Disconnect; Join/Add always reachable; empty Join-first on clean home (#27).  
7. **Credit secondary under More:** #34 XMR top-up unchanged; no new payment rails; Credit not elevated to primary tab.  
8. **Operate-or-FAIL:** Bad invite / bad furl / share-before-join → in-app FAIL + Retry (no WUI). Operator copy only.  
9. **Folders-first + Offer pie** preserved.  
10. Tip base ≥ **`f46ab7c`**.

---

## Suggested files / areas to touch (from Sync tree @ tip `f46ab7c`)

| Area | Likely paths | Why |
|------|--------------|-----|
| Shell chrome / places | `src/leasegrid_sync/app.py` (`_build_main_page`, folders/servers chrome, More menu) | Hierarchy, CTAs, Invite entry, spacing |
| Join accept | `app.py` `_build_join_page`; `invite.py` `parse_invite` | Short-code-first copy; FAIL in-window |
| Invite share | `app.py` Settings share box (~Invite others); Add dialog `on_copy_invite`; `invite.py` (`share_url_for_nodedir`, `qr_png`, wormhole/short code) | Promote short code + QR + Copy; demote long-URL-only / raw FURL |
| Servers / Add | `app.py` Add dialog; `servers.py` | Embed W5 invite card on Invite path; keep paste furl |
| Credit | `app.py` More → Credit; `credit.py` | Leave under More; #34 flow intact |
| Tests | `tests/` | Invite share has code+QR+Copy; no primary raw FURL; chrome ranks |

Stack remains Gridsync-class PyQt Sync — **no** Electron rewrite, **no** Tahoe WUI.

---

## Recommended implement order

1. Invite share card (short code + QR + Copy) — replace Settings-only long URL dump as primary  
2. Wire card into Servers → Add → Invite (and Folders/More entry)  
3. Join copy/placeholder: short-code-first; keep accept kinds  
4. Chrome hierarchy / spacing / primary CTA weight on Folders + Servers  
5. Confirm Credit remains under More; unpaid cue only  
6. Regression: #27 roster / both Add paths / honest Disconnect; #34 top-up  
7. Dogfood on nimo AppImage / lab friendnet  

---

## Dogfood steps (nimo)

| # | Step | PASS |
|---|------|------|
| 1 | Fresh home launch | Join-only; no Online-N |
| 2 | Join with **short code** | Folders primary |
| 3 | Open Storage servers; Add → Invite | **Short code + QR + Copy** visible; no raw FURL primary |
| 4 | Copy code; second machine Join via code or QR | Peer joins / Offers; appears on Servers |
| 5 | Folders: Offer pie + Add folder | Store path works |
| 6 | More → Credit → Top up (lab) | #34 path still works; Credit not a primary tab |
| 7 | Add → Paste bad storage furl | In-app FAIL |
| 8 | Disconnect a server | Honest local-only copy |
| 9 | Relaunch joined home | Servers + Add + Invite still reachable |

---

## Operate-or-FAIL examples

| Case | Banner spirit | Next |
|------|---------------|------|
| Bad short code | could not join… | Retry / fresh invite |
| Share before join | join a friendnet first… | Join, then Invite |
| Bad storage furl | could not add this storage server… | Retry |
| QR unavailable | QR unavailable + still Copy code | Use code / link |

---

## Explicit rejects

- Raw introducer FURL as primary share / sole Copy  
- Credit promoted to primary tab beside Folders/Servers  
- New payment rails / mainnet  
- #28 / #33 / #26 / #30 work in this slice  
- Join-once-and-gone / Servers demotion  
- Tahoe WUI Next  
- Marketing rebrand masquerading as polish  
- Mark drip from implement bots  

---

## Exit checklist (DevBot reports)

- [ ] Tip ≥ `f46ab7c`  
- [ ] Lead journey screenshots: Join → Servers → Offer/store → Credit(More)  
- [ ] Invite share: short code + QR + Copy (screenshot); no raw FURL primary  
- [ ] Join accepts short code  
- [ ] Servers primary + both Add paths + honest Disconnect  
- [ ] Credit still under More; #34 top-up intact  
- [ ] Visual cleanup evident (hierarchy/CTA/spacing) without rebrand claim  
- [ ] FAIL in-window; no WUI  
- [ ] Folders + Offer pie preserved  

**#38 implement FAIL examples:** invite still raw-FURL-first; Credit tab promoted; Servers buried; polish-only CSS with #32 omitted; payment-rail changes; Mark contacted.

---

## One-liner

> Implement #38 on tip ≥ `f46ab7c`: shell polish on Join→Servers→Offer/store→Credit; #32 invite = short code + QR + Copy (no raw FURL primary); preserve #27 Servers + #34 Credit-under-More; Build-first on nimo.
