"""Recovery key export / import for Leasegrid Sync (U4).

A recovery key is one file holding what a new device needs to get the folders
back: the friendnet invite (introducer furl + encoding), each Magic Folder's
collective capability, and the credit wallet. It is encrypted with a passphrase
(scrypt -> Fernet) when one is given.

Restore does not clone the lost device. Magic Folder never downloads a
participant's own snapshots (it treats the DMD matching our upload cap as
"self"), so a restored device joins each collective as a *new participant*
with a fresh personal DMD. The old device's files then download normally, and
new edits upload under the new participant name. That is the standard
multi-device Magic Folder model.
"""

from __future__ import annotations

import base64
import configparser
import hashlib
import json
import os
import secrets
import socket
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from .backend import MagicFolderCtl, SyncError, TahoeClient, shares_config
from .credit import CreditCtl, is_leasegrid_wallet

RECOVERY_VERSION = 1
RECOVERY_SUFFIX = ".leasegrid-recovery"
SCRYPT_N = 2**15
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_MAXMEM = 256 * 1024 * 1024  # OpenSSL's default cap (32 MiB) is exactly what n=2^15 needs

RECOVERY_INTRO = (
    "A recovery key restores access to your folders if this device is lost. "
    "Store it offline (encrypted USB, printed QR, a safe)."
)
SCARY_LOSS = (
    "Loss of your recovery key and this device can mean TOTAL LOSS of access. "
    "There is no “reset password.” Leasegrid cannot recover it for you."
)
EXPORT_STOP = "STOP — read this."
EXPORT_WARN = (
    "Anyone with this key (and its passphrase, if set) can read and change your synced "
    "folders and spend your credit. If you lose the key and this computer, your data "
    "access can be gone forever. Leasegrid cannot reset it."
)
ACK_LOSS = "I understand: loss can mean total loss."
ACK_STORE = "I will store this file somewhere safe, offline."
EXPORT_FAIL_MSG = "recovery key was not written. Disk error, permission denied, or encrypt failed."
EXPORT_FAIL_NEXT = "pick another path; Retry. Do not assume you are safe until this succeeds."
IMPORT_FAIL_MSG = (
    "could not import this recovery key. Wrong passphrase, corrupt file, or incompatible grid."
)
IMPORT_FAIL_NEXT = "check the passphrase; try the file from your backup; Retry."
NO_PASSPHRASE_NOTE = (
    "No passphrase: the file is plaintext. Anyone who copies it has your folders."
)

Progress = Callable[[str], None]


@dataclass
class FolderRecord:
    name: str
    collective_dircap: str
    upload_dircap: str
    magic_path: str
    poll_interval: int = 5
    scan_interval: int = 5
    author_name: str = ""


@dataclass
class RecoveryBundle:
    introducer_furl: str
    shares: tuple[int, int, int]
    nickname: str = "leasegrid-sync"
    issuer_url: str = ""
    folders: list[FolderRecord] = field(default_factory=list)
    wallet: Optional[dict] = None
    created: float = field(default_factory=time.time)
    version: int = RECOVERY_VERSION

    def to_json(self) -> str:
        data = asdict(self)
        data["shares"] = list(self.shares)
        return json.dumps(data, indent=2, sort_keys=True)

    @classmethod
    def from_json(cls, text: str) -> "RecoveryBundle":
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise SyncError(IMPORT_FAIL_MSG, IMPORT_FAIL_NEXT) from exc
        if not isinstance(data, dict) or int(data.get("version", 0)) != RECOVERY_VERSION:
            raise SyncError(IMPORT_FAIL_MSG, IMPORT_FAIL_NEXT)
        furl = str(data.get("introducer_furl") or "")
        if not furl.startswith("pb://"):
            raise SyncError(IMPORT_FAIL_MSG, IMPORT_FAIL_NEXT)
        shares = data.get("shares") or []
        if len(shares) != 3:
            raise SyncError(IMPORT_FAIL_MSG, IMPORT_FAIL_NEXT)
        folders = []
        for item in data.get("folders") or []:
            if not isinstance(item, dict):
                raise SyncError(IMPORT_FAIL_MSG, IMPORT_FAIL_NEXT)
            try:
                folders.append(FolderRecord(**item))
            except TypeError as exc:
                raise SyncError(IMPORT_FAIL_MSG, IMPORT_FAIL_NEXT) from exc
        wallet = data.get("wallet")
        if wallet is not None and not is_leasegrid_wallet(wallet):
            wallet = None
        return cls(
            introducer_furl=furl,
            shares=(int(shares[0]), int(shares[1]), int(shares[2])),
            nickname=str(data.get("nickname") or "leasegrid-sync"),
            issuer_url=str(data.get("issuer_url") or ""),
            folders=folders,
            wallet=wallet,
            created=float(data.get("created") or 0),
        )


# -- Tahoe node facts --------------------------------------------------------


def read_introducer_furl(nodedir: Path) -> str:
    yaml_path = nodedir / "private" / "introducers.yaml"
    if yaml_path.is_file():
        # Tahoe writes a tiny, regular YAML; avoid a yaml dependency here.
        for line in yaml_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("furl:"):
                value = stripped[len("furl:"):].strip().strip("'\"")
                if value.startswith("pb://"):
                    return value
    cfg = configparser.ConfigParser()
    cfg.read(nodedir / "tahoe.cfg", encoding="utf-8")
    value = cfg.get("client", "introducer.furl", fallback="").strip()
    if value.startswith("pb://"):
        return value
    raise SyncError(
        "recovery key was not written. No introducer is configured for this Tahoe client.",
        "join a friendnet first, then export.",
    )


def read_shares(nodedir: Path) -> tuple[int, int, int]:
    cfg = configparser.ConfigParser()
    cfg.read(nodedir / "tahoe.cfg", encoding="utf-8")
    try:
        return (
            cfg.getint("client", "shares.needed"),
            cfg.getint("client", "shares.happy"),
            cfg.getint("client", "shares.total"),
        )
    except (configparser.Error, ValueError):
        return shares_config()


def read_nickname(nodedir: Path) -> str:
    cfg = configparser.ConfigParser()
    cfg.read(nodedir / "tahoe.cfg", encoding="utf-8")
    return cfg.get("node", "nickname", fallback="leasegrid-sync").strip() or "leasegrid-sync"


# -- Magic Folder config (offline, via the pinned magic-folder package) -------


def _mf_api():
    try:
        from twisted.python.filepath import FilePath
        from magic_folder.config import load_global_configuration
        from magic_folder.snapshot import create_local_author
        from magic_folder.util.capabilities import Capability
    except ImportError as exc:
        raise SyncError(
            "recovery needs the magic-folder package next to Sync.",
            "install with: pip install 'leasegrid-zkap-lab[sync,tahoe]'; Retry.",
        ) from exc
    return FilePath, load_global_configuration, create_local_author, Capability


def read_folder_records(config_dir: Path) -> list[FolderRecord]:
    if not (config_dir / "global.sqlite").is_file():
        return []
    FilePath, load_global_configuration, _, _ = _mf_api()
    config = load_global_configuration(FilePath(str(config_dir)))
    records = []
    for name in sorted(config.list_magic_folders()):
        mf = config.get_magic_folder(name)
        upload = mf.upload_dircap
        records.append(
            FolderRecord(
                name=name,
                collective_dircap=mf.collective_dircap.danger_real_capability_string(),
                upload_dircap=upload.danger_real_capability_string() if upload else "",
                magic_path=mf.magic_path.path,
                poll_interval=int(mf.poll_interval),
                scan_interval=int(mf.scan_interval or mf.poll_interval),
                author_name=mf.author.name,
            )
        )
    return records


def readonly_cap(cap: str) -> str:
    _, _, _, Capability = _mf_api()
    return Capability.from_string(cap).to_readonly().danger_real_capability_string()


def create_folder_from_caps(
    config_dir: Path,
    name: str,
    magic_path: Path,
    author_name: str,
    collective_dircap: str,
    upload_dircap: str,
    poll_interval: int,
    scan_interval: int,
) -> None:
    """Write a folder into an initialized (not running) Magic Folder config."""
    FilePath, load_global_configuration, create_local_author, Capability = _mf_api()
    config = load_global_configuration(FilePath(str(config_dir)))
    try:
        collective = Capability.from_string(collective_dircap)
        upload = Capability.from_string(upload_dircap)
    except ValueError as exc:
        raise SyncError(IMPORT_FAIL_MSG, IMPORT_FAIL_NEXT) from exc
    try:
        config.create_magic_folder(
            name,
            FilePath(str(magic_path)),
            create_local_author(author_name),
            collective,
            upload,
            int(poll_interval),
            int(scan_interval),
        )
    except Exception as exc:  # magic-folder raises its own APIError family
        raise SyncError(
            "could not restore folder %s: %s" % (name, exc),
            "if the folder already exists, leave it; otherwise Retry.",
        ) from exc


# -- file format --------------------------------------------------------------


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    return _derive_key_params(passphrase, salt, SCRYPT_N, SCRYPT_R, SCRYPT_P)


def _derive_key_params(passphrase: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    raw = hashlib.scrypt(
        passphrase.encode("utf-8"), salt=salt, n=n, r=r, p=p, dklen=32, maxmem=SCRYPT_MAXMEM
    )
    return base64.urlsafe_b64encode(raw)


def encode_recovery_file(bundle: RecoveryBundle, passphrase: str) -> bytes:
    plain = bundle.to_json().encode("utf-8")
    envelope: dict[str, Any] = {"leasegrid-recovery": RECOVERY_VERSION}
    if not passphrase:
        envelope["encrypted"] = False
        envelope["bundle"] = json.loads(plain)
        return (json.dumps(envelope, indent=2, sort_keys=True) + "\n").encode("utf-8")
    from cryptography.fernet import Fernet

    salt = secrets.token_bytes(16)
    token = Fernet(_derive_key(passphrase, salt)).encrypt(plain)
    envelope.update(
        {
            "encrypted": True,
            "kdf": {"name": "scrypt", "n": SCRYPT_N, "r": SCRYPT_R, "p": SCRYPT_P,
                    "salt": base64.b64encode(salt).decode("ascii")},
            "ciphertext": token.decode("ascii"),
        }
    )
    return (json.dumps(envelope, indent=2, sort_keys=True) + "\n").encode("utf-8")


def decode_recovery_file(data: bytes, passphrase: str) -> RecoveryBundle:
    try:
        envelope = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SyncError(IMPORT_FAIL_MSG, IMPORT_FAIL_NEXT) from exc
    if not isinstance(envelope, dict) or envelope.get("leasegrid-recovery") != RECOVERY_VERSION:
        raise SyncError(IMPORT_FAIL_MSG, IMPORT_FAIL_NEXT)
    if not envelope.get("encrypted"):
        return RecoveryBundle.from_json(json.dumps(envelope.get("bundle")))
    kdf = envelope.get("kdf") or {}
    if kdf.get("name") != "scrypt":
        raise SyncError(IMPORT_FAIL_MSG, IMPORT_FAIL_NEXT)
    from cryptography.fernet import Fernet, InvalidToken

    try:
        salt = base64.b64decode(str(kdf.get("salt") or ""))
        key = _derive_key_params(
            passphrase,
            salt,
            int(kdf.get("n", SCRYPT_N)),
            int(kdf.get("r", SCRYPT_R)),
            int(kdf.get("p", SCRYPT_P)),
        )
        plain = Fernet(key).decrypt(
            str(envelope.get("ciphertext") or "").encode("ascii")
        )
    except (InvalidToken, ValueError, TypeError) as exc:
        raise SyncError(IMPORT_FAIL_MSG, IMPORT_FAIL_NEXT) from exc
    return RecoveryBundle.from_json(plain.decode("utf-8"))


# -- controller ---------------------------------------------------------------


@dataclass
class RestoreResult:
    folders: list[str]
    skipped: list[str]
    wallet_restored: bool
    author_name: str
    grid: str


def restored_author_name() -> str:
    user = os.environ.get("USER") or os.environ.get("LOGNAME") or "leasegrid"
    host = socket.gethostname().split(".")[0] or "device"
    return "%s@%s-%s" % (user, host, secrets.token_hex(2))


class RecoveryCtl:
    def __init__(
        self,
        home: Path,
        tahoe: TahoeClient,
        mf: MagicFolderCtl,
        credit: CreditCtl,
        folder_root: Optional[Path] = None,
    ) -> None:
        self.home = Path(home)
        self.tahoe = tahoe
        self.mf = mf
        self.credit = credit
        self.folder_root = Path(folder_root) if folder_root else Path.home() / "Leasegrid"
        self.state_path = self.home / "recovery-state.json"

    # export

    def collect(self) -> RecoveryBundle:
        nodedir = self.tahoe.nodedir
        if not self.tahoe.has_nodedir():
            raise SyncError(
                "recovery key was not written. No friendnet joined yet.",
                "join a friendnet first, then export.",
            )
        wallet = None
        try:
            wallet = self.credit._read_wallet()
        except SyncError:
            wallet = None
        return RecoveryBundle(
            introducer_furl=read_introducer_furl(nodedir),
            shares=read_shares(nodedir),
            nickname=read_nickname(nodedir),
            issuer_url=self.credit.issuer_url,
            folders=read_folder_records(self.mf.config_dir),
            wallet=wallet,
        )

    def export(self, path: Path, passphrase: str) -> RecoveryBundle:
        bundle = self.collect()
        data = encode_recovery_file(bundle, passphrase)
        path = Path(path)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "wb") as f:
                f.write(data)
            # Read back: a half-written key is worse than a FAIL banner.
            decode_recovery_file(path.read_bytes(), passphrase)
        except OSError as exc:
            raise SyncError(EXPORT_FAIL_MSG, EXPORT_FAIL_NEXT) from exc
        self._record_export(path)
        return bundle

    def _record_export(self, path: Path) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(
            json.dumps({"last_export": time.time(), "path": str(path)}) + "\n", encoding="utf-8"
        )

    def last_export(self) -> Optional[dict]:
        if not self.state_path.is_file():
            return None
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return data if isinstance(data, dict) and data.get("last_export") else None

    # import

    def restore(
        self,
        path: Path,
        passphrase: str,
        progress: Optional[Progress] = None,
    ) -> RestoreResult:
        say = progress or (lambda _text: None)
        try:
            data = Path(path).read_bytes()
        except OSError as exc:
            raise SyncError(IMPORT_FAIL_MSG, IMPORT_FAIL_NEXT) from exc
        bundle = decode_recovery_file(data, passphrase)

        say("Joining the friendnet from the recovery key…")
        if not self.tahoe.has_nodedir():
            self.tahoe.create_client(bundle.introducer_furl, shares=bundle.shares)
        status = self.tahoe.join_invite(bundle.introducer_furl)

        say("Preparing Magic Folder…")
        self.mf.ensure_init()
        existing = {r.name for r in read_folder_records(self.mf.config_dir)}
        author = restored_author_name()
        restored: list[str] = []
        skipped: list[str] = []
        pending: list[tuple[str, str]] = []
        for rec in bundle.folders:
            if rec.name in existing:
                skipped.append(rec.name)
                continue
            say("Restoring folder %s…" % rec.name)
            local = self.folder_root / rec.name
            local.mkdir(parents=True, exist_ok=True)
            personal_dmd = self.tahoe.mkdir()
            create_folder_from_caps(
                self.mf.config_dir,
                rec.name,
                local,
                author,
                rec.collective_dircap,
                personal_dmd,
                rec.poll_interval,
                rec.scan_interval,
            )
            pending.append((rec.name, readonly_cap(personal_dmd)))
            restored.append(rec.name)

        if pending:
            say("Starting sync and announcing this device to your folders…")
            self.mf.ensure_running()
            for name, readcap in pending:
                self.mf.add_participant(name, author, readcap)
                try:
                    self.mf.scan_local(name)
                except SyncError:
                    pass

        wallet_restored = False
        if bundle.wallet and not self.credit.wallet_path.is_file():
            from leasegrid_zkap.client import save_wallet

            save_wallet(self.credit.wallet_path, bundle.wallet)
            wallet_restored = True

        return RestoreResult(
            folders=restored,
            skipped=skipped,
            wallet_restored=wallet_restored,
            author_name=author,
            grid=status.detail,
        )
