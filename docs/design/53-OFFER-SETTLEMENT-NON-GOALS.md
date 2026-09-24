# Offer Used → settlement — non-goals (#28)

**Status:** Design DoD 2026-09-24 PT (~2:20am PT)  
**Cite:** [#28](https://github.com/themark-net/leasegrid-c/issues/28) · tip ≥ **`83b3e66`** (`83b3e66d4afdc7499619a43af82b78c54b6dd939`)

---

## Out of scope for this Design pack / implement slice

| Non-goal | Why |
|----------|-----|
| Implementing Sync product code in this Design pass | Design only → PM RELEASES DevBot Build-first on nimo |
| Contacting Mark / Mark drip / SendToUser | FOUNDER RULE — bots coordinate |
| **New payment rails** beyond tying Offer Used → settlement visibility on existing Credit/ZKAP path | CEO RELEASE constraint |
| Mainnet XMR / mainnet wallet UX | Stagenet only; mainnet refused (#34 lock) |
| Rewriting #34 Credit → Top up journey | Entry stays Credit → Top up |
| Promoting Credit to a primary tab beside Folders/Servers | #38 lock — Credit secondary under More |
| Phase 2 Leasegrid Node payout dashboard / operator address admin | Not Sync MVP; payout remains out-of-band per [`docs/07-payment.md`](../07-payment.md) §9 |
| Mint / issuer admin chrome in Sync | Issuer trust is not buyer UI |
| Fabricating host earnings / green “paid” without rail data | Honesty lock |
| Merging disk Used into Offer-consumed | Must stay distinct |
| [#33](https://github.com/themark-net/leasegrid-c/issues/33) introducer marketplace | Parked / out |
| [#26](https://github.com/themark-net/leasegrid-c/issues/26) Android EXTRA_RECOVERY | Parked / out |
| [#30](https://github.com/themark-net/leasegrid-c/issues/30) plant↔maximum MF HTTP 500 | Out |
| Android Slice B / write Offer settlement UI | Desktop Sync primary; P4-B parked |
| Marketing rebrand / silent Marketing push | Marketing silent |
| Rewriting U0–U4 / P1 / P4 / #27 / #38 artifact bodies (`10`–`49`) | Cite + supersede #27 pack `43` footnote only |
| Tahoe WUI / WebView-as-product | Hard reject |
| Merging docs PR from executor as required | Nimo land is enough; GitHub PR optional |
| Waiting on Mark for widget copy | Design decides; operator copy only |

---

## Explicitly **in** scope (do not misread as non-goals)

| In scope | Note |
|----------|------|
| Distinguish disk Used vs Offer consumed / hosted-for-others | Binding |
| Hosted strip on Offer surface | Settlement-relevant |
| Deep-link / chip to Credit under More | Reuse #34 surfaces |
| Honest empty / missing / FAIL | No fake green |
| Host settlement visibility **only** if existing rails expose it | Stagenet |
| Supersede #27 pack `43` footnote | #28 now full Design |

---

## Related (cite, do not expand)

- [#27](https://github.com/themark-net/leasegrid-c/issues/27) Servers / Join-first — locks stand  
- [#38](https://github.com/themark-net/leasegrid-c/issues/38) / [#32](https://github.com/themark-net/leasegrid-c/issues/32) shell + invite — locks stand  
- [#34](https://github.com/themark-net/leasegrid-c/issues/34) Credit XMR top-up — journey unchanged  
- [`docs/07-payment.md`](../07-payment.md) settlement §9 — vocabulary only  

---

## One-liner

> #28 Design: Offer Used→settlement visibility on existing Credit/ZKAP path. Not: new rails, mainnet, Credit tab promotion, #33/#26/#30, Marketing, Mark ops, implement in Design pass.
