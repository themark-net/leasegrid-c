"""#28: disk Used is not hosted-for-others. Settlement is real data or honest empty/missing/FAIL."""

from __future__ import annotations

from collections import namedtuple
from pathlib import Path
from unittest.mock import patch

import pytest

from leasegrid_sync.backend import (
    SyncError,
    format_hosted_strip,
    read_disk_offer,
    read_hosted_shares,
    read_local_accepted,
)
from leasegrid_sync.credit import (
    format_host_settlement,
    load_host_settlement,
    per_node_settled,
)
from leasegrid_zkap.client import ClientError


def _offering(nodedir: Path, extra: str = "") -> None:
    nodedir.mkdir(parents=True, exist_ok=True)
    (nodedir / "tahoe.cfg").write_text(
        "[storage]\nenabled = true\n" + extra, encoding="utf-8"
    )


def test_hosted_bytes_are_share_files_not_disk_used(tmp_path: Path):
    nodedir = tmp_path / "tahoe"
    home = tmp_path / "home"
    home.mkdir()
    _offering(nodedir, "reserved_space = 100\n")
    share = nodedir / "storage" / "shares" / "aa"
    share.mkdir(parents=True)
    (share / "0").write_bytes(b"x" * 12)
    usage = namedtuple("usage", "total used free")(1000, 400, 600)
    with patch("leasegrid_sync.backend.shutil.disk_usage", return_value=usage):
        slices = read_disk_offer(nodedir, home)
    hosted = read_hosted_shares(nodedir)
    assert slices.used == 400
    assert slices.kept == 100
    assert slices.offered == 500
    assert hosted.bytes_hosted == 12
    assert hosted.files == 1
    assert hosted.bytes_hosted != slices.used
    text = format_hosted_strip(hosted)
    assert text.startswith("Hosting 12 B for the friendnet")
    assert "400" not in text
    assert "disk used" not in text.lower()
    assert "Used" not in text


def test_hosted_empty_is_not_fail_or_earnings(tmp_path: Path):
    nodedir = tmp_path / "tahoe"
    _offering(nodedir)
    assert read_hosted_shares(nodedir).bytes_hosted == 0
    text = format_hosted_strip(read_hosted_shares(nodedir))
    assert text.startswith("Nothing hosted for others yet.")
    assert "FAIL" not in text
    assert "XMR" not in text
    assert "Earned" not in text
    assert "0.00" not in text


def test_hosted_accounting_fail_when_shares_path_is_not_a_directory(tmp_path: Path):
    nodedir = tmp_path / "tahoe"
    root = nodedir / "storage" / "shares"
    root.parent.mkdir(parents=True)
    root.write_text("not-a-directory", encoding="utf-8")
    with pytest.raises(SyncError) as exc:
        read_hosted_shares(nodedir)
    assert "how much you are hosting" in exc.value.message
    assert "pie still work" in exc.value.next_hint


def test_global_ledger_is_not_this_hosts_settlement(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("LEASEGRID_ISSUER_URL", raising=False)
    monkeypatch.delenv("LEASEGRID_GATED", raising=False)
    nodedir = tmp_path / "tahoe"
    _offering(nodedir)
    ledger = {
        "epochs": {"0": {"tokens_settled": 99, "tokens_issued": 100}},
        "settlement_conflicts": 0,
    }
    assert per_node_settled(ledger, "node-a") is None

    def fetch(_url):
        raise AssertionError("unpaid offer must not call the issuer")

    row = load_host_settlement(nodedir, issuer_url="http://127.0.0.1:8700", fetch=fetch)
    assert row.kind == "missing"
    text = format_host_settlement(row)
    assert "not available on this network yet" in text
    assert "99" not in text
    assert "Settled on ledger" not in text
    assert "Pending: none" not in text
    assert "XMR" not in text
    assert "Earned" not in text


def test_settlement_fail_when_configured_issuer_does_not_answer(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("LEASEGRID_ISSUER_URL", raising=False)
    monkeypatch.delenv("LEASEGRID_GATED", raising=False)
    nodedir = tmp_path / "tahoe"
    _offering(
        nodedir,
        "\n[storageserver.plugins.leasegrid-zkap-v0]\n"
        "issuer-url = http://127.0.0.1:9\n"
        "nodeid = node-a\n",
    )

    def fetch(_url):
        raise ClientError("unreachable")

    row = load_host_settlement(nodedir, issuer_url="http://127.0.0.1:8700", fetch=fetch)
    assert row.kind == "fail"
    text = format_host_settlement(row)
    assert "FAIL" in text
    assert "could not load settlement status" in text
    assert "do not assume you were paid" in text.lower()
    assert "XMR" not in text
    assert "Earned" not in text
    assert "0.12" not in text


def test_settlement_data_is_spent_set_and_per_node_ledger_only(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("LEASEGRID_GATED", raising=False)
    nodedir = tmp_path / "tahoe"
    spent = tmp_path / "spent.json"
    spent.write_text(
        '{"spent": ['
        '{"t": "dG9rZW4x", "token_epoch": 0},'
        '{"t": "dG9rZW4y", "token_epoch": 0}'
        "]}\n",
        encoding="utf-8",
    )
    _offering(
        nodedir,
        "\n[storageserver.plugins.leasegrid-zkap-v0]\n"
        "spent-set-path = %s\n"
        "issuer-url = http://issuer.example\n"
        "nodeid = node-a\n" % spent,
    )
    assert read_local_accepted(nodedir) == (2, True)
    ledger = {
        "epochs": {"0": {"tokens_settled": 99}},
        "nodes": {"node-a": {"tokens_settled": 2}, "other": {"tokens_settled": 97}},
    }
    row = load_host_settlement(
        nodedir, issuer_url="http://127.0.0.1:8700", fetch=lambda _url: ledger
    )
    assert row.kind == "data"
    assert row.accepted == 2
    assert row.settled == 2
    assert row.pending == 0
    text = format_host_settlement(row)
    assert "Accepted toward settlement (this epoch): 2 tokens" in text
    assert "Settled on ledger: 2 · Pending: none" in text
    assert "Payout: out-of-band (not shown in Sync)." in text
    assert "99" not in text
    assert "97" not in text
    assert "XMR" not in text
    assert "Earned" not in text


def test_corrupt_spent_set_is_fail_not_zero_paid(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("LEASEGRID_ISSUER_URL", raising=False)
    monkeypatch.delenv("LEASEGRID_GATED", raising=False)
    nodedir = tmp_path / "tahoe"
    spent = nodedir / "spent.json"
    _offering(
        nodedir,
        "\n[storageserver.plugins.leasegrid-zkap-v0]\nspent-set-path = spent.json\n",
    )
    spent.write_text("{", encoding="utf-8")
    with pytest.raises(SyncError):
        read_local_accepted(nodedir)
    row = load_host_settlement(nodedir, issuer_url="http://127.0.0.1:8700", fetch=lambda _url: {})
    assert row.kind == "fail"
    text = format_host_settlement(row)
    assert "Pending: none" not in text
    assert "Settled on ledger: 0" not in text
    assert "Earned" not in text


def test_host_settlement_hidden_when_not_offering(tmp_path: Path):
    nodedir = tmp_path / "tahoe"
    nodedir.mkdir()
    (nodedir / "tahoe.cfg").write_text("[node]\n", encoding="utf-8")
    row = load_host_settlement(nodedir, issuer_url="http://127.0.0.1:8700", fetch=lambda _url: {
        "nodes": {"node-a": {"tokens_settled": 5}}
    })
    assert row.kind == "hidden"
    assert format_host_settlement(row) == ""
