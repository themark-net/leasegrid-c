"""SQLite voucher-store backup / restore (docs/07-payment.md §10).

Issuer state is one file. Restore the DB next to the view key and signing
key; subaddress indices stay valid because they are never reused.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path


class BackupError(Exception):
    pass


def backup_sqlite(src: str | Path, dest: str | Path) -> Path:
    src_p = Path(src).expanduser()
    dest_p = Path(dest).expanduser()
    if not src_p.is_file():
        raise BackupError("no issuer db at %s" % src_p)
    dest_p.parent.mkdir(parents=True, exist_ok=True)
    src_db = sqlite3.connect(str(src_p))
    dest_db = sqlite3.connect(str(dest_p))
    try:
        src_db.backup(dest_db)
    finally:
        dest_db.close()
        src_db.close()
    return dest_p


def restore_sqlite(src: str | Path, dest: str | Path, *, force: bool = False) -> Path:
    src_p = Path(src).expanduser()
    dest_p = Path(dest).expanduser()
    if not src_p.is_file():
        raise BackupError("no backup at %s" % src_p)
    if dest_p.exists() and not force:
        raise BackupError("refusing to overwrite %s (pass force=True)" % dest_p)
    dest_p.parent.mkdir(parents=True, exist_ok=True)
    src_db = sqlite3.connect(str(src_p))
    dest_db = sqlite3.connect(str(dest_p))
    try:
        src_db.backup(dest_db)
    finally:
        dest_db.close()
        src_db.close()
    return dest_p
