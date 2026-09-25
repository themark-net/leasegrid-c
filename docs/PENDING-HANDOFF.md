# leasegrid-c — pending handoff (CEO pause 2026-09-24 ~11:20pm PT)

**Purpose:** Freeze current queue + design map so another model/harness can take over without bot chat history.

**Repo tip:** `main` @ `83b3e66` (Shell polish #38 / invite #32 shipped). Nimo checkout: `~/DEVELOP/leasegrid-c` (canonical; lab secrets under `lab-private/` if present).

**Org posture:** PAUSED. No auto RELEASE / Build / Cursor implement until founder says go. **Public marketing / loud v\* HOLD** (quiet F&F `v0.1.0` already cut). Marketing silent.

---

## Source of truth

| Kind | Where |
|------|--------|
| Work items | **GitHub issues** (this repo) |
| Designs | `docs/design/` — start at [`docs/design/README.md`](design/README.md) |
| Product / rails | `docs/00-decision.md` … `docs/08-lab.md`, `docs/07-payment.md` |
| UI track pointers | `docs/09-ui-track*.md` |
| Roadmap | `docs/03-roadmap.md` |

---

## Open GitHub issues (pending)

| # | Title | Posture |
|---|--------|---------|
| [#26](https://github.com/themark-net/leasegrid-c/issues/26) | Android relative `EXTRA_RECOVERY_FILE` residual | Non-blocking residual (abs path PASS) |
| [#30](https://github.com/themark-net/leasegrid-c/issues/30) | plant↔maximum Magic Folder HTTP 500 (glibc22) | Residual multi-host; does not block buyer UX |
| [#33](https://github.com/themark-net/leasegrid-c/issues/33) | Vision: discoverable introducers / LeaseGrid as introducer | Exploratory only — **no build** |

## Recently closed (shipped / complete — keep designs)

| # | Note |
|---|------|
| [#27](https://github.com/themark-net/leasegrid-c/issues/27) | Buyer Servers + Join reachable — SHIPPED; design pack `40`–`44` |
| [#28](https://github.com/themark-net/leasegrid-c/issues/28) | Offer Used → settlement — issue closed completed; Design DoD `50`–`54` on main (confirm tip implements Hosted strip before re-opening) |
| [#32](https://github.com/themark-net/leasegrid-c/issues/32) | Invite short code + QR + Copy — SHIPPED inside #38; design pack `45`–`49` |
| [#34](https://github.com/themark-net/leasegrid-c/issues/34) / [#35](https://github.com/themark-net/leasegrid-c/issues/35) | XMR Credit top-up / gate 0d — SHIPPED |
| [#38](https://github.com/themark-net/leasegrid-c/issues/38) | Sync shell polish — SHIPPED @ `83b3e66` |

Open PRs at pause: **none**.

---

## Design export map (`docs/design/`)

Full index is already in [`design/README.md`](design/README.md). Summary:

| Slice | Files | Status |
|-------|-------|--------|
| U0 buyer journey | `10`–`14` | Design DoD |
| U2 Credit | `15`–`19` | Design / SHIP |
| U4 Recovery | `30`–`34` | SHIP |
| P4-A Android read | `35`–`39` | Design / Slice A; **P4-B write parked** |
| #27 Buyer storage | `40`–`44` | SHIP |
| #38 Shell polish (+ #32) | `45`–`49` | SHIP @ `83b3e66` |
| #28 Offer → settlement | `50`–`54` | Design DoD ready; implement lane was Build-first on nimo |

Pointers beside `docs/09-ui-track.md`: `09-ui-track-*-POINTER.md`.

---

## Next implement candidates (only after founder RELEASE)

1. Confirm #28 Hosted-for-others strip is on tip vs Design DoD `54`; if missing, implement from `54-OFFER-SETTLEMENT-DEVBOT-HANDOFF.md`.
2. Optional residual #30 (plant↔maximum MF 500) if capacity.
3. Android P4-B write — parked until Design RELEASE.
4. #33 vision — never auto-start.

---

## Standing product locks

- CrashPlan-simple Sync metaphor (folders-first + Offer pie); no Tahoe WUI as product front door.
- Join-first empty home until invite; Servers roster dynamic add/remove (#27).
- Credit secondary under More; unpaid default; stagenet until Mark says otherwise.
- No Mark ops drip from bots; Namecheap/Epik/DNS out of this repo.

---

## Done when this handoff is useful

Next agent reads this file + `docs/design/README.md`, picks an **open** issue (#26/#30/#33) or waits for RELEASE, and does not invent public marketing or #33 implement.
