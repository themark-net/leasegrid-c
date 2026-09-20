"""U4 recovery: bundle file format, Tahoe facts, offline Magic Folder read/create, restore flow."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from leasegrid_sync.backend import ConnectionStatus, MagicFolderCtl, SyncError, TahoeClient
from leasegrid_sync.credit import CreditCtl
from leasegrid_sync.recovery import (
    IMPORT_FAIL_MSG,
    FolderRecord,
    RecoveryBundle,
    RecoveryCtl,
    decode_recovery_file,
    encode_recovery_file,
    read_introducer_furl,
    read_shares,
)

FURL = "pb://hashhashhash@127.0.0.1:45001/swissnumswiss"
COLLECTIVE = "URI:DIR2:zeymwpndqvrsklpcvovfywvoie:bi6j4lmtwnteznypa3ihn4m7nxm3uavbvdzjl544srrhzhyvj3uq"
UPLOAD = "URI:DIR2:chob75vxeonzy43dca3icankum:oy4vcxdqlenb4p5c3s3hyoimpp3quz33wiaqxmagqflsi5rb2ena"
PERSONAL = "URI:DIR2:wxrpahbt7j7bim6hbdrzrnov6i:tkte6gb4vww3g4vhgoqbuyx7peci76vwekow2opfw2insbeiblgq"


def _bundle() -> RecoveryBundle:
    return RecoveryBundle(
        introducer_furl=FURL,
        shares=(2, 3, 3),
        nickname="nimo",
        issuer_url="http://127.0.0.1:8700",
        folders=[FolderRecord("Photos", COLLECTIVE, UPLOAD, "/home/x/Photos", 5, 5, "x")],
        wallet={"issuer-pubkey-id": "ab", "tokens": [{"t": "1", "W": "2"}]},
    )


def test_roundtrip_with_passphrase():
    data = encode_recovery_file(_bundle(), "correct horse")
    assert b"URI:DIR2" not in data
    assert b'"encrypted": true' in data
    back = decode_recovery_file(data, "correct horse")
    assert back.introducer_furl == FURL
    assert back.shares == (2, 3, 3)
    assert back.folders[0].collective_dircap == COLLECTIVE
    assert back.wallet["tokens"][0]["t"] == "1"


def test_wrong_passphrase_is_import_fail():
    data = encode_recovery_file(_bundle(), "correct horse")
    with pytest.raises(SyncError) as exc:
        decode_recovery_file(data, "wrong")
    assert IMPORT_FAIL_MSG in exc.value.banner()
    assert "FAIL" in exc.value.banner()


def test_roundtrip_without_passphrase_is_plaintext():
    data = encode_recovery_file(_bundle(), "")
    assert b"URI:DIR2" in data
    back = decode_recovery_file(data, "")
    assert back.folders[0].name == "Photos"


@pytest.mark.parametrize("blob", [b"", b"not json", b'{"leasegrid-recovery": 99}', b'{"x": 1}'])
def test_garbage_files_fail_closed(blob):
    with pytest.raises(SyncError):
        decode_recovery_file(blob, "")


def test_bundle_rejects_foreign_wallet_shape():
    b = _bundle()
    b.wallet = {"vouchers": ["opaque"]}
    back = RecoveryBundle.from_json(b.to_json())
    assert back.wallet is None


def test_read_tahoe_facts(tmp_path: Path):
    nodedir = tmp_path / "tahoe"
    (nodedir / "private").mkdir(parents=True)
    (nodedir / "tahoe.cfg").write_text(
        "[node]\nnickname = nimo\n[client]\nshares.needed = 2\nshares.happy = 3\n"
        "shares.total = 3\n",
        encoding="utf-8",
    )
    (nodedir / "private" / "introducers.yaml").write_text(
        "introducers:\n  default:\n    furl: %s\n" % FURL, encoding="utf-8"
    )
    assert read_introducer_furl(nodedir) == FURL
    assert read_shares(nodedir) == (2, 3, 3)


def test_read_furl_missing_is_clear_fail(tmp_path: Path):
    nodedir = tmp_path / "tahoe"
    nodedir.mkdir()
    (nodedir / "tahoe.cfg").write_text("[node]\n", encoding="utf-8")
    with pytest.raises(SyncError) as exc:
        read_introducer_furl(nodedir)
    assert "No introducer" in exc.value.message


@pytest.fixture
def mf_config(tmp_path: Path) -> Path:
    """A real (offline) magic-folder global config with one folder."""
    pytest.importorskip("magic_folder")
    from twisted.python.filepath import FilePath
    from magic_folder.config import create_global_configuration

    nodedir = tmp_path / "tahoe"
    nodedir.mkdir()
    (nodedir / "tahoe.cfg").write_text("[node]\n", encoding="utf-8")
    cfg = tmp_path / "mf"
    create_global_configuration(
        FilePath(str(cfg)), "tcp:19780:interface=127.0.0.1", FilePath(str(nodedir)),
        "tcp:127.0.0.1:19780",
    )
    return cfg


def test_offline_folder_create_and_read(mf_config: Path, tmp_path: Path):
    from leasegrid_sync.recovery import create_folder_from_caps, read_folder_records

    local = tmp_path / "Photos"
    local.mkdir()
    create_folder_from_caps(mf_config, "Photos", local, "me@box", COLLECTIVE, UPLOAD, 5, 7)
    recs = read_folder_records(mf_config)
    assert len(recs) == 1
    assert recs[0].name == "Photos"
    assert recs[0].collective_dircap == COLLECTIVE
    assert recs[0].upload_dircap == UPLOAD
    assert recs[0].magic_path == str(local)
    assert recs[0].poll_interval == 5 and recs[0].scan_interval == 7
    assert recs[0].author_name == "me@box"


def test_readonly_cap(mf_config: Path):
    from leasegrid_sync.recovery import readonly_cap

    ro = readonly_cap(UPLOAD)
    assert ro.startswith("URI:DIR2-RO:")


def test_restore_rejoins_as_new_participant(mf_config: Path, tmp_path: Path):
    """Restore must NOT reuse the old upload cap (Magic Folder would skip 'self')."""
    from leasegrid_sync.recovery import read_folder_records

    home = tmp_path / "home"
    home.mkdir()
    nodedir = tmp_path / "tahoe"
    key = tmp_path / "key.leasegrid-recovery"
    key.write_bytes(encode_recovery_file(_bundle(), "pw"))

    tahoe = TahoeClient(nodedir=nodedir, tahoe_bin="/bin/true", home=home)
    mf = MagicFolderCtl(config_dir=mf_config, nodedir=nodedir, mf_bin="/bin/true")
    credit = CreditCtl(home=home, issuer_url="http://127.0.0.1:1")
    ctl = RecoveryCtl(home, tahoe, mf, credit, folder_root=tmp_path / "Leasegrid")
    st = ConnectionStatus(state="Connected", detail="introducer up · 3 storage", introducer_ok=True)
    added = []
    with patch.object(tahoe, "join_invite", return_value=st), \
         patch.object(tahoe, "mkdir", return_value=PERSONAL), \
         patch.object(mf, "ensure_running", return_value=None), \
         patch.object(mf, "scan_local", return_value=None), \
         patch.object(mf, "add_participant", side_effect=lambda *a: added.append(a)):
        result = ctl.restore(key, "pw", progress=lambda t: None)

    assert result.folders == ["Photos"]
    assert result.skipped == []
    assert result.wallet_restored
    assert credit.wallet_path.is_file()
    assert (tmp_path / "Leasegrid" / "Photos").is_dir()
    recs = read_folder_records(mf_config)
    assert recs[0].collective_dircap == COLLECTIVE
    assert recs[0].upload_dircap == PERSONAL, "must be a fresh personal DMD, not the old one"
    assert recs[0].author_name == result.author_name
    assert len(added) == 1
    name, author, readcap = added[0]
    assert (name, author) == ("Photos", result.author_name)
    assert readcap.startswith("URI:DIR2-RO:")


def test_restore_wrong_passphrase_touches_nothing(mf_config: Path, tmp_path: Path):
    home = tmp_path / "home"
    nodedir = tmp_path / "tahoe"
    key = tmp_path / "key"
    key.write_bytes(encode_recovery_file(_bundle(), "pw"))
    tahoe = TahoeClient(nodedir=nodedir, tahoe_bin="/bin/true", home=home)
    mf = MagicFolderCtl(config_dir=mf_config, nodedir=nodedir, mf_bin="/bin/true")
    ctl = RecoveryCtl(home, tahoe, mf, CreditCtl(home=home, issuer_url="http://127.0.0.1:1"))
    with patch.object(tahoe, "join_invite") as join:
        with pytest.raises(SyncError):
            ctl.restore(key, "nope")
    assert not join.called


def test_export_records_last_export(tmp_path: Path, mf_config: Path):
    home = tmp_path / "home"
    home.mkdir()
    nodedir = tmp_path / "tahoe"
    (nodedir / "private").mkdir()
    (nodedir / "tahoe.cfg").write_text(
        "[node]\nnickname = nimo\n[client]\nshares.needed = 2\nshares.happy = 3\n"
        "shares.total = 3\n",
        encoding="utf-8",
    )
    (nodedir / "private" / "introducers.yaml").write_text(
        "introducers:\n  default:\n    furl: %s\n" % FURL, encoding="utf-8"
    )
    tahoe = TahoeClient(nodedir=nodedir, tahoe_bin="/bin/true", home=home)
    mf = MagicFolderCtl(config_dir=mf_config, nodedir=nodedir, mf_bin="/bin/true")
    ctl = RecoveryCtl(home, tahoe, mf, CreditCtl(home=home, issuer_url="http://127.0.0.1:1"))
    assert ctl.last_export() is None
    out = tmp_path / "keys" / "nimo.leasegrid-recovery"
    bundle = ctl.export(out, "pw")
    assert bundle.introducer_furl == FURL
    assert out.is_file()
    assert (out.stat().st_mode & 0o777) == 0o600
    assert ctl.last_export()["path"] == str(out)
    assert decode_recovery_file(out.read_bytes(), "pw").nickname == "nimo"
