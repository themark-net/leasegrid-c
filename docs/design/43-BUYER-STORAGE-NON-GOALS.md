# Buyer storage — non-goals

**Status:** Design DoD 2026-09-22 PT  
**Cite:** [#27](https://github.com/themark-net/leasegrid-c/issues/27) · tip ≥ **`5b752c7`** · Mark/CEO 2026-09-22

---

## Out of scope for this Design pack / implement slice

|| Non-goal | Why |
||----------|-----|
|| Implementing Sync product code in this Design pass | Design only → PM RELEASE implement |
|| Contacting Mark / SendToUser / Mark drip | FOUNDER RULE — bots coordinate |
|| Mainnet XMR / U5 payment rails | Separate track |
|| Android Slice B / write sync as this slice | P4-B parked; desktop Sync primary |
|| Baking a public friendnet into the AppImage | Empty Join-first; no pre-joined buyer artifact |
|| Demoting Folders / Offer pie / Credit rank | P1 locks stand |
|| Rewriting U0–U4 or P4 `10`–`39` bodies | Cite only; preserve |
|| Tahoe WUI / WebView-as-product | Hard reject |
|| Fake “remove forever from the grid” | Tahoe introducer honesty |
|| Wiping remote shares on Disconnect | Disconnect = this home’s used set only |
|| Operator Node kit / server admin console | Buyer Sync UX only |
|| Merging docs PR from executor | Optional stage payload; parent owns merge |
|| Waiting on Mark Invite-vs-paste widget | Do **not** block Design PASS — both Add paths are in Design |

---

## Explicitly **in** scope (do not misread as non-goals)

|| In scope | Note |
||----------|------|
|| Storage servers roster (list / status / Add / Disconnect) | **Primary** host UX — Mark 2026-09-22 |
|| Paste storage server furl Add path | Required in Design UX |
|| Invite-to-Offer Add path | Required in Design UX |
|| Empty Join-first on clean home | Binding |
|| Join/Add always reachable after connect | Binding — Join-once-and-gone is FAIL |

---

## One-liner

> Design #27: Servers roster + both Add paths + honest Disconnect + empty Join-first. Not: implement, Mark drip, forever-remove, WUI, mainnet, Android write, rewrite `10`–`39`.

---

## Related (out of slice)

[#28](https://github.com/themark-net/leasegrid-c/issues/28) — Offer usage eventually linked to payment. **Log-only for this pack; not in #27 Design/implement scope.**