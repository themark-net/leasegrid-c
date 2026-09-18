"""Ristretto Privacy Pass (challenge-bypass-ristretto), ZKAPAuthorizer family."""

from __future__ import annotations

import os
from hashlib import sha256
from pathlib import Path

from challenge_bypass_ristretto import (
    BatchDLEQProof,
    BlindedToken,
    PublicKey,
    RandomToken,
    SignedToken,
    SigningKey,
    TokenPreimage,
    UnblindedToken,
    VerificationSignature,
    random_signing_key,
)

from .constants import DENOMINATION, DOMAIN, TOKEN_EPOCH_V0


class CryptoError(Exception):
    pass


class InvalidPass(CryptoError):
    """MAC_K(R) did not verify, or token could not be rederived."""


def _b64(value) -> bytes:
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        return value.encode("ascii")
    raise TypeError("expected base64 bytes or str")


def pubkey_id_from_public_key(pk: PublicKey) -> str:
    """Stable hex id for operator logs (not a secret)."""
    return sha256(pk.encode_base64()).hexdigest()


def generate_signing_key() -> SigningKey:
    return random_signing_key()


def save_signing_key(path: str | os.PathLike, key: SigningKey) -> None:
    path = Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = key.encode_base64()
    if not isinstance(encoded, (bytes, bytearray)):
        encoded = str(encoded).encode("ascii")
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(fd, encoded + b"\n")
    finally:
        os.close(fd)


def load_signing_key(path: str | os.PathLike) -> SigningKey:
    raw = Path(path).expanduser().read_bytes().strip()
    return SigningKey.decode_base64(raw)


def public_key_b64(key: SigningKey) -> bytes:
    return PublicKey.from_signing_key(key).encode_base64()


def issuer_info(key: SigningKey) -> dict:
    pk = PublicKey.from_signing_key(key)
    pk_b64 = pk.encode_base64()
    if isinstance(pk_b64, bytes):
        pk_s = pk_b64.decode("ascii")
    else:
        pk_s = str(pk_b64)
    return {
        "domain": DOMAIN,
        "denomination": DENOMINATION,
        "token-epoch": TOKEN_EPOCH_V0,
        "public-key": pk_s,
        "issuer-pubkey-id": pubkey_id_from_public_key(pk),
        "name": "leasegrid-zkap-lab",
    }


def client_tokens(count: int) -> tuple[list[RandomToken], list[BlindedToken]]:
    tokens = [RandomToken.create() for _ in range(count)]
    blinded = [t.blind() for t in tokens]
    return tokens, blinded


def sign_blinded(key: SigningKey, blinded_b64: list[str | bytes]) -> dict:
    blinded = [BlindedToken.decode_base64(_b64(b)) for b in blinded_b64]
    signed = [key.sign(b) for b in blinded]
    proof = BatchDLEQProof.create(key, blinded, signed)
    pk = PublicKey.from_signing_key(key)
    def _s(x) -> str:
        v = x.encode_base64()
        return v.decode("ascii") if isinstance(v, bytes) else str(v)

    return {
        "signed-tokens": [_s(s) for s in signed],
        "proof": _s(proof),
        "public-key": _s(pk),
        "issuer-pubkey-id": pubkey_id_from_public_key(pk),
        "token-epoch": TOKEN_EPOCH_V0,
        "denomination": DENOMINATION,
    }


def unblind_batch(
    tokens: list[RandomToken],
    blinded: list[BlindedToken],
    signed_b64: list[str | bytes],
    proof_b64: str | bytes,
    public_key_b64: str | bytes,
) -> list[UnblindedToken]:
    signed = [SignedToken.decode_base64(_b64(s)) for s in signed_b64]
    proof = BatchDLEQProof.decode_base64(_b64(proof_b64))
    pk = PublicKey.decode_base64(_b64(public_key_b64))
    out = proof.invalid_or_unblind(tokens, blinded, signed, pk)
    if not out:
        raise CryptoError("DLEQ proof invalid or unblind failed")
    return list(out)


def wallet_record(unblinded: UnblindedToken) -> dict:
    t = unblinded.preimage().encode_base64()
    w = unblinded.encode_base64()
    return {
        "t": t.decode("ascii") if isinstance(t, bytes) else str(t),
        "W": w.decode("ascii") if isinstance(w, bytes) else str(w),
    }


def load_unblinded(record: dict) -> UnblindedToken:
    return UnblindedToken.decode_base64(_b64(record["W"]))


def mac_k_r(unblinded: UnblindedToken, r: bytes) -> bytes:
    vk = unblinded.derive_verification_key_sha512()
    sig = vk.sign_sha512(r)
    out = sig.encode_base64()
    return out if isinstance(out, bytes) else str(out).encode("ascii")


def verify_mac(signing_key: SigningKey, t_b64: str | bytes, r: bytes, mac_b64: str | bytes) -> None:
    """Storage-side: rederive W from t using issuer signing key, check MAC_K(R)."""
    try:
        pre = TokenPreimage.decode_base64(_b64(t_b64))
        unblinded = signing_key.rederive_unblinded_token(pre)
        vk = unblinded.derive_verification_key_sha512()
        sig = VerificationSignature.decode_base64(_b64(mac_b64))
    except Exception as e:
        raise InvalidPass("token decode/rederive failed") from e
    if vk.invalid_sha512(sig, r):
        raise InvalidPass("MAC_K(R) invalid")
