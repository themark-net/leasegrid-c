# Buyer storage — information architecture

**Status:** Design DoD 2026-09-22 PT  
**Cite:** [#27](https://github.com/themark-net/leasegrid-c/issues/27) · tip ≥ **`5b752c7`** · Mark/CEO lock 2026-09-22  
**Preserve:** P1 Folders-first CrashPlan shell; Offer pie + Credit ranks; U0 Join surfaces.

---

## Places (desktop Sync)

|| Place | Rank | Role for #27 |
||-------|------|-------------|
|| **Welcome / Join** | Primary **only** when clean / never-joined | Threat HITL + invite paste. Sole surface until Join or recovery import succeeds for **this** home. |
|| **Folders** | Primary **after** join | CrashPlan shell: folder list + sync status + Offer pie. Entry to Storage servers. Glance chip OK after join. |
|| **Storage servers** ★ | First-class place (new / elevated) | **Where data is stored.** List hosts, status, **Add**, **Disconnect**. Replaces reliance on one-line “N computers storing files” as the only host UX. |
|| **Add server** (dialog / subflow) | Modal from Servers (also reachable via Folders CTA) | **Both** paths: invite-to-Offer **and** paste storage server furl. |
|| **Disconnect confirm** | Modal | Honest local disconnect copy. |
|| Offer disk pie | On Folders (unchanged) | Local disk % offered — do **not** demote. |
|| Credit | Secondary (unchanged) | U2 — do **not** demote or elevate for #27. |
|| Recovery | Secondary (U4) | Export/import — cite only. |
|| Settings | Secondary | Autostart / about — may host a link to Storage servers if needed; Servers itself is not buried. |
|| Tray | Persist | Open → Folders (after join) or Join (if clean). |

★ Mark 2026-09-22: Servers screen is primary host-management UX.

---

## CTA ranks (binding)

|| Rank | CTA | Notes |
||------|-----|-------|
|| 1 (clean home) | Join friendnet | Only primary |
|| 1 (post-join) | Folders / Add folder | CrashPlan primary |
|| 1b (post-join host control) | **Storage servers → Add / Disconnect** | Always reachable; not optional chrome |
|| 2 | Offer pie adjust | Unchanged |
|| 3 | Credit / Recovery / Settings | Unchanged secondary |

**FAIL:** Join/Add only on first-run and then disappear.  
**FAIL:** Host management only via status chip with no Servers list.

---

## Storage servers list — row model

|| Field | Buyer copy | Notes |
||-------|------------|-------|
|| Nickname / name | Display name | Prefer nickname; fallback short id — no raw Tahoe dumps in chrome |
|| Status | Connected / Connecting / Offline / Available / Disconnected | Map from connection + pin state |
|| Source | Joined via invite · Announced · Added by you | Honest provenance |
|| Actions | Disconnect (if in used/connected set); Add (global) | Confirm on Disconnect |

### List sections (recommended)

1. **Used by this home** — pinned / connected / preferred for new shares  
2. **Available** (optional) — introducer-announced but not pinned; buyer can Add/pin or ignore

If introducer re-announces a disconnected server → may reappear under Available with copy: “Seen again on the friendnet. Not used until you Add.”

---

## Add server — two paths (both in Design)

|| Path | Buyer action | System | MVP Design |
||------|--------------|--------|------------|
|| **A — Invite to Offer** | Start invite so a friend/host Offers disk (or paste friendnet invite when joining additional capacity via invite) | Existing U0/U1 invite / Offer share | **Required in UX** |
|| **B — Paste server link** | Paste `pb://…` **storage** furl into Add dialog | Validate; remember; use for share placement | **Required in UX** |

Implement may sequence A then B in code milestones; **Design shows both**. Both paths are required Design DoD.

Optional later: “Use announced servers” toggle / auto-list with pin — does not replace explicit Add.

---

## Introducer honesty (IA constraints)

|| UI may say | UI must not say |
||------------|-----------------|
|| “Connected to N storage servers” (after join, from real count) | “Lab grid ready” on clean home |
|| “Disconnect from this Sync home” | “Remove from the grid forever” |
|| “Introducer may show this server again” | “Permanently ejected for everyone” |
|| “Stops preferring for new files” | “Deletes all copies on that computer” |

Glance chip (`format_status_chip`: “Online — N computers storing files”) is **secondary status only after join**. Clicking it should deep-link to **Storage servers** when practical.

---

## Navigation (post-join)

```
Folders ──► Storage servers ──► Add (Invite | Paste link)
    │                │
    │                └──► Disconnect → Confirm
    │
    ├── Offer pie (same place)
    ├── Credit (secondary)
    ├── Recovery (secondary)
    └── Settings (secondary; optional link → Storage servers)
```

Also: Folders header or empty-hosts CTA → **Add storage server** when `N == 0` after join (operate clarity).

---

## Clean-home detection (IA rule)

|| State | Primary surface |
||-------|-----------------|
|| No nodedir / never successfully Joined this home | Welcome/Join only |
|| Recovery import in progress | U4 import flow |
|| Joined or recovered for this home | Folders primary + Storage servers reachable |

---

## Non-IA (explicit)

- No Tahoe WUI as product place  
- No demoting Folders or Offer  
- No baking public friendnet into AppImage IA  
- Android Slice B not in this IA (desktop Sync primary)