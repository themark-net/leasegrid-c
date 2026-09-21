# P1 dogfood — CrashPlan shell

**Cite:** issue #11 · Design PASS nimo `docs/design/` README + 25–29 (`29-P1-DEVBOT-HANDOFF.md`) · plan `docs/10-post-fable-plan.md` @ `f06ef01` · base `c308b958`  
**Not:** Tahoe WUI. Not AppImage ([#12](https://github.com/themark-net/leasegrid-c/issues/12)).

## What this proves

Unpaid join lands on the **folder list**. The same page shows an **Offer pie** of this disk: used, free, and offered, plus **% of this disk**. Credit and Settings are under **More**. The XMR / Top up lecture stays hidden unless `LEASEGRID_GATED=1`. Add folder on an unpaid grid does not ask for Credit.

## Steps

```bash
scripts/dev-grid.sh
LEASEGRID_ISSUER_URL=http://127.0.0.1:8700 leasegrid-sync
```

1. Paste the invite. Leave **Offer disk on this device** checked. **Join friendnet** is the only primary button.
2. The window is Folders. The pie reads **Offering N% of this disk**, with Used, Free, and Offered. Release the Offer slider: **Saved**, or **FAIL** plus **Next** in the window.
3. **Add folder**. It must not open Credit.
4. **More** lists Recovery and Settings. Credit is not in that menu.
5. Quit. Start again with `LEASEGRID_GATED=1` on a gated grid. **More → Credit** opens the balance. Settings shows the payment lecture. Add folder with an empty wallet **FAIL**s in the window with **Open Credit**.

Magic Folder, join, and the tray stay. Do not open the Tahoe web UI.
