# Desktop UI additions (v0.1.6, join hand-off in v0.1.7)

**Status:** shipped. Settings, invite close, folder open, and window geometry in v0.1.6. The second-launch invite hand-off in v0.1.7.
**Cite:** `docs/TESTER-GUIDE.md` · `docs/HANDOFF-v0.1.6.md`

A path a person sees or copies uses the home-relative form (`~/…`, or `~\…` on Windows). Files on disk keep the real path.

## Settings buttons

**Purpose:** open the logs and copy a short bug report without browsing the Sync home.

| Control | String | Default | Failure |
|---------|--------|---------|---------|
| Open logs folder | `Open logs folder` | creates `<Sync home>/logs` if needed and opens it | the Settings status line shows the home-relative logs path |
| Copy bug-report details | `Copy bug-report details` | copies the scrubbed report | status line: `Copied. Paste it into your bug report.` |

The report is About, platform, chip, joined yes/no, folder summary, and `Logs:`. Invite codes, furls, recovery keys, and wallets are not copied. The status line is selectable.

## Invite close and tray Quit

**Purpose:** closing the window, or tray **Quit**, must not cancel a live invite by accident.

**Question:** `An invite is still open. Quit and cancel it?`
**Default:** `Keep open` (also Esc). **Other button:** `Quit`.
No invite running: quit with no dialog. Keep open leaves the window and the invite. Quit cancels the invite and exits. A service stop (SIGTERM, SIGINT, SIGHUP; on Windows SIGINT and SIGBREAK) quits without waiting on this dialog.

## Folder open

**Purpose:** double-click a folder row, or right-click **Open folder**, to open that directory.

| Case | What the person sees | Next |
|------|----------------------|------|
| Missing | `That folder is not on this computer any more: <path>` | `Add the folder again if you still want it.` |
| A file | `That path is not a folder: <path>` | same next step |
| Empty path | nothing | the row is ignored |
| A directory | the system file manager | a failed open is silent |

## Already running, and a second `--join`

**Purpose:** one window per Sync home. A second launch must not drop an invite.

**No socket, or no invite:** `Leasegrid Sync is already running. Use the open window.` The second process does not start a window.

**Hand-off:** the first instance listens on a per-home socket. The name is `leasegrid-sync-` plus the first 32 hex characters of the SHA-256 of the resolved home path. The invite is not part of the name and is never logged. The socket is an absolute path in a mode-0700 directory: `<Sync home>/run/` when that path is under 100 bytes, otherwise `$XDG_RUNTIME_DIR/leasegrid-sync/`, otherwise `$TMPDIR/leasegrid-sync-<uid>/` with a hashed socket name. A second launch calls the lock check before it connects. It connects only when the directory is a real directory owned by this user with no group or other permissions, and the path is a socket owned by this user. A free lock returns without connecting, and the normal join runs. On Windows the pipe is user-only (`UserAccessOption` before listen). The client cannot read the pipe owner, so the lock check plus that ACL is the defense. A second launch with `--join` sends only the invite text and exits 0. The open window comes forward, the Join field is filled, the acknowledgement stays unchecked, and nothing joins until the person clicks **Join friendnet**.

**Already joined:** there is no add-another-grid path. The window shows `Leasegrid Sync is already on a friendnet. This invite was not opened.` and drops the invite.

**Stale socket or an older instance:** the same already-running dialog as when there is no socket.

## Window geometry

**Purpose:** reopen where the person left the window. The default size is 920×620. The file is `window-geometry.json` in the Sync home.

Save and restore use the frame origin. A maximized window saves the normal size in that same origin, and the maximized flag. Un-maximize restores that normal size. Only a version 2 record is applied. Version 1 or 3, a bad field, or a failed read opens at the default, and the app still starts. A missing file is a first launch and is not logged. A size past the screen union becomes the default before Qt is asked to resize. A failed save leaves the previous file in place.
