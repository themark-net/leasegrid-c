# Leasegrid Sync — U0 Design DoD (native buyer app)

**Status:** U0 Design DoD ready — 2026-09-19 PT  
**Owner:** Design Bot (executor staged on box)  
**Date:** 2026-09-19 PT  
**Product lock:** CEO / founder RELEASE 2026-09-19 + `docs/09-ui-track.md`  
**Canonical source (box staging):** `/workspace/leasegrid-u0-src/` → `00-decision.md`, `03-roadmap.md`, `09-ui-track.md`  
**Install target (nimo):** `/home/mark/DEVELOP/leasegrid-c/docs/design/`  
**Brand (provisional):** **Leasegrid Sync** (buyer) · **Leasegrid Node** (operator Phase 2 — out of U0 wireframes except mention)

---

## Thesis (binding)

**Product = native Sync app + installer**, not Tahoe WUI, not web-first.

| Surface | Choice | Why |
|---------|--------|-----|
| Buyer app | Native desktop (Qt / Gridsync lineage) | Magic Folder sync, tray, invites, offline-capable; Dropbox-shaped |
| Buyer installer | First-class artifact | AppImage + .deb first; no “clone repo and pip” |
| Web UI | Optional later alt only | Must not block native |
| Operator UI | Leasegrid Node — Phase 2 | Separate package; not buyer MVP |

**Stack default:** Fork or tightly wrap **Gridsync** (PyQt) + Magic Folder daemon + Leasegrid ZKAP/credit plugins. Prefer reuse over greenfield Electron/Tauri unless Gridsync proves unforkable for ZKAP credit — then still **native**, not WUI.

**Architecture corner:** Paid friendnet = corner **C** (`docs/00-decision.md`). No PoRep, no slash, no public deals. UI must not pretend otherwise.

---

## Artifact index

| File | Contents |
|------|----------|
| [10-U0-BUYER-JOURNEY.md](10-U0-BUYER-JOURNEY.md) | Happy path first-run → folders → credit → recovery; FAIL paths |
| [11-U0-IA-NATIVE-SYNC.md](11-U0-IA-NATIVE-SYNC.md) | Window chrome, places, tray; what is NOT primary nav |
| [12-U0-WIREFRAMES.md](12-U0-WIREFRAMES.md) | ASCII wireframes for all **5** surfaces + empty/loading/error/needs-judgment |
| [13-U0-NON-GOALS.md](13-U0-NON-GOALS.md) | Explicit rejects (WUI, web-only MVP, etc.) |
| [14-U0-DEVBOT-HANDOFF.md](14-U0-DEVBOT-HANDOFF.md) | Tight DoD for **U1 Gridsync spike** only |
| [09-ui-track-U0-POINTER.md](09-ui-track-U0-POINTER.md) | One-line pointer for optional copy next to `09-ui-track.md` |
| [INSTALL-ON-NIMO.sh](INSTALL-ON-NIMO.sh) | Extract/copy into nimo `docs/design/` |
| [PARENT-INSTALL.md](PARENT-INSTALL.md) | One paragraph for parent Design Bot |
| [phase-u0-design.tar.gz](phase-u0-design.tar.gz) | Tar of README + 10–14 only |

---

## U0 surfaces (must wireframe — all five)

1. **First-run / invite** — join friendnet (invite code); honest threat-model copy on screen one  
2. **Folders** — Magic Folder list; sync status; add folder  
3. **Credit** — remaining GiB-share-months (plain language); Top up (faucet stub → XMR later)  
4. **Recovery** — export/import recovery key; scary “loss = total loss”  
5. **Settings** — autostart; transport policy note (Tor vs sync) as visible design flag  

---

## Binding constraints

| Lock | Rule |
|------|------|
| Product | Native Sync + installer only for U0–U5 buyer track |
| Stack | Gridsync wrap/fork + Magic Folder + Leasegrid credit |
| Platforms | Linux AppImage / .deb first |
| Operate-or-FAIL | Every control runs its action or shows FAIL + next **in-window** |
| Chrome | Operator/buyer copy only — no ADR theology dumps, no localhost board URLs, no Tahoe WUI embeds |
| Credit denomination | 1 token ≈ 1 GiB-share × 30 days on one node; UI translates without lying (expansion is real) |
| Threat copy | Issuer mint trust, no storage proofs, Tor vs sync — on screen one / Settings, not a hidden toggle |
| Opaque ZKAPs | Opaque ZKAP wallets do **not** convert in Credit UI |
| Sequencing | Do **not** wait for Phase 0 rails (0c/0d) to start UI; faucet until 0c |
| Cite | `docs/09-ui-track.md`; CEO U0 RELEASE 2026-09-19; founder product lock |

---

## Gridsync mental model (brief)

Gridsync presents **local folders linked to Magic Folders**, not a Tahoe capability browser. Primary objects = folders with sync status, history, and per-folder actions. System tray is first-class. Recovery Key restores grid connection + rootcap; restored folders appear remote-only until a local path is chosen. Leasegrid Sync inherits this metaphor and adds Credit + honest threat / transport flags — it is **not** a website landing page.

---

## Success check (U0 Design PASS)

- [x] Product lock reflected (native Sync, not WUI / web-first)  
- [x] All five buyer surfaces wireframed with empty / loading / error / needs-judgment  
- [x] Operate-or-FAIL columns on journeys and controls  
- [x] HITL threat copy blocks on first-run  
- [x] Credit faucet stub + denomination honesty  
- [x] Recovery scary gate  
- [x] Tor vs sync as visible design flag (Settings + first-run)  
- [x] U1 DevBot handoff cites `09-ui-track.md` U0–U5 and scopes spike only  
- [x] Non-goals explicit  
- [x] Package staged under `/workspace/leasegrid-u0-out/` for parent nimo install  

**U0 exit (per `09-ui-track.md`):** Founder ACK of this Design DoD + product lock in UI track.

---

## Explicit non-goals (summary)

Full Tahoe browse · mobile · sharing beyond invite codes · WUI embed · Electron default · waiting on Phase 0 rails for U0 · Leasegrid Node wireframes in U0 · ADR dumps in product chrome.

See [13-U0-NON-GOALS.md](13-U0-NON-GOALS.md).
