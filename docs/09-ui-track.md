# 09 — UI track (native buyer client + installers)

**Status:** Product lock 2026-09-19 (founder)  
**Owner ask:** Drive to a UI. Need an **installer** and a **native app UI**. Web may exist later as an alt; it is **not** the product. Tahoe WUI is forbidden as product UI.

Related: [`03-roadmap.md`](03-roadmap.md) Phase 1. Conditional Go / corner C rails unchanged.

---

## Decision

| Surface | Choice | Why |
|---------|--------|-----|
| **Buyer app** | **Native desktop** (Qt / Gridsync lineage) | Magic Folder sync, tray, invites, offline-capable; matches “Dropbox-shaped” goal. Gridsync already ships Linux/macOS/Windows binaries. |
| **Buyer installer** | First-class artifact | One-click or one-command install that brings Tahoe client + Magic Folder + Leasegrid credit UI — no “clone repo and pip.” |
| **Web UI** | Optional later alt | Browser cannot own tray sync, autostart, or local folder watch as cleanly. Do not block native on a web SPA. |
| **Operator UI** | Phase 2 native/packaged node kit | Separate installer; not the buyer MVP. |

**Stack default:** Fork or tightly wrap **Gridsync** (PyQt) + Magic Folder daemon + Leasegrid ZKAP/credit plugins. Prefer reuse over greenfield Electron/Tauri unless Gridsync proves unforkable for ZKAP credit — then still **native**, not WUI.

---

## Two installers (names provisional)

1. **`Leasegrid Sync`** (buyer) — Phase 1 MVP  
   - Installs: desktop app, local Tahoe client config, Magic Folder, credit/balance view, XMR top-up flow (when 0c ready; faucet stub until then).  
   - Platforms: **Linux AppImage + .deb first** (lab/friendnet on nimo); macOS/Windows when buyer demand says so.  
   - First-run wizard: join friendnet (invite code) → pick sync folder → see balance → recovery key export.

2. **`Leasegrid Node`** (operator) — Phase 2, **paid** kit  
   - Unpaid offering is already the Sync join path (`tahoe create-node` on the same invite).  
   - This installer is the later paid/gated operator surface: ZKAP gate, status dashboard, eject logs, payout.  
   - Not required to dogfood folder sync or to offer disk on an unpaid friendnet.

---

## Buyer app screens (MVP)

1. **First-run / invite** — join grid; honest threat-model copy on screen one.  
2. **Folders** — Magic Folder list; sync status; add folder.  
3. **Credit** — remaining GiB-share-months; Top up (faucet stub → XMR).  
4. **Recovery** — export/import recovery key; scary “loss = total loss.”  
5. **Settings** — autostart, transport policy note (Tor vs sync — design flag, not a hidden toggle).

Non-goals for MVP: full Tahoe browse, mobile, sharing beyond invite codes, WUI embed.

---

## Sequencing (parallel with Phase 0 rails)

Do **not** wait for 0c/0d PASS to start UI.

| Slice | Deliverable | Exit |
|-------|-------------|------|
| **U0** | Product lock in this doc + roadmap pointer; Design Bot wireframes for screens 1–5 | Founder ACK (this ask) |
| **U1** | Spike: Gridsync fork/wrap boots against existing friendnet; one Magic Folder syncs | Dogfood on nimo |
| **U2** | Credit panel wired to lab issuer/faucet (no mainnet XMR required) | Balance visible after faucet |
| **U3** | Linux installer (AppImage and/or .deb) that installs Sync without a shell tutorial | Fresh VM / second user install PASS |
| **U4** | Recovery key export + first-run threat copy | Non-expert walkthrough PASS |
| **U5** | Swap faucet for XMR top-up when gate 0c PASS — design: [`07-payment.md`](07-payment.md) §11 | Phase 1 exit with rails |

Rails owners keep 0c/0d. UI owners own U0–U5. Phase 1 exit still requires Phase 0 rails for real XMR; UI dogfood uses faucet until then.

---

## Mark-needed vs org-can-do

| Mark-needed | Org-can-do |
|-------------|------------|
| Confirm brand names (`Leasegrid Sync` / `Leasegrid Node`) or alternatives | U0–U5 implement; Design wireframes |
| Friendnet invite for dogfood; recovery-key accept | Gridsync fork spike; packaging CI |
| Later: macOS notarization / Windows signing if we ship those | Linux AppImage/.deb first |

---

## Explicit rejects

- Shipping Tahoe WUI / localhost web as the product.  
- “Web-only MVP then native later.”  
- Waiting for full Phase 0 before any UI work.  
- Electron as default without a Gridsync-blocker writeup.
