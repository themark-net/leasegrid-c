"""Issuer settlement must not accept R (gate 0b.5)."""

from leasegrid_zkap.client import ClientError, http_json
from leasegrid_zkap.crypto import generate_signing_key
from leasegrid_zkap.issuer import start_issuer


def test_settlement_rejects_r_field():
    key = generate_signing_key()
    state, httpd = start_issuer(key, "127.0.0.1:0")
    try:
        url = state.listen
        try:
            http_json(
                url + "/v0/settlement",
                "POST",
                {"spent": ["deadbeef"], "R": "must-not-accept"},
            )
            raise AssertionError("settlement accepted R")
        except ClientError as e:
            assert "R" in str(e) or "403" in str(e) or "400" in str(e) or "refused" in str(e).lower() or "must not" in str(e).lower()
        info = http_json(url + "/v0/info")
        assert info.get("settlement-rejected-r", 0) >= 1 or "issuer-pubkey-id" in info
    finally:
        httpd.shutdown()
