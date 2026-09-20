"""rsa-bssa-v1: RFC 9474 RSABSSA-SHA384-PSS-Deterministic + pk_tok binding.

Lab stays ristretto-v0. This module is the publicly verifiable scheme a
second operator needs (docs/07-payment.md §9 / ADR-0002). Nodes hold only
the RSA public key. Each token embeds a client Ed25519 key so a node that
saw a spend cannot re-bind it to a different R.
"""

from __future__ import annotations

import os
from base64 import b64encode
from hashlib import sha256, sha384
from typing import Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, padding, rsa
from cryptography.hazmat.primitives.asymmetric.rsa import (
    RSAPrivateNumbers,
    RSAPublicNumbers,
    rsa_crt_dmp1,
    rsa_crt_dmq1,
    rsa_crt_iqmp,
)

from .payment.topup import hkdf_expand

SCHEME = "rsa-bssa-v1"
INFO_TOKKEY = b"leasegrid/tokkey/v1"
INFO_TOKID = b"leasegrid/tokid/v1"
MSG_DOMAIN = b"leasegrid/tok/v1"
HASH = sha384
HLEN = 48
SLEN = 48  # RSABSSA-SHA384-PSS-Deterministic


class BssaError(Exception):
    pass


def generate_issuer_rsa() -> tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey]:
    sk = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return sk, sk.public_key()


def private_key_from_pqned(*, p: int, q: int, n: int, e: int, d: int) -> rsa.RSAPrivateKey:
    if p < q:
        p, q = q, p
    nums = RSAPrivateNumbers(
        p=p,
        q=q,
        d=d,
        dmp1=rsa_crt_dmp1(d, p),
        dmq1=rsa_crt_dmq1(d, q),
        iqmp=rsa_crt_iqmp(p, q),
        public_numbers=RSAPublicNumbers(e, n),
    )
    return nums.private_key()


def rsa_pubkey_id(pk: rsa.RSAPublicKey) -> str:
    der = pk.public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return sha256(der).hexdigest()


def rsa_public_spki_b64(pk: rsa.RSAPublicKey) -> str:
    der = pk.public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return b64encode(der).decode("ascii")


def load_rsa_public_spki(b64: str) -> rsa.RSAPublicKey:
    from base64 import b64decode

    key = serialization.load_der_public_key(b64decode(b64))
    if not isinstance(key, rsa.RSAPublicKey):
        raise BssaError("not an RSA public key")
    return key


def derive_tok_keypair(seed: bytes, vid: str, i: int) -> tuple[ed25519.Ed25519PrivateKey, bytes]:
    raw = hkdf_expand(seed, INFO_TOKKEY + bytes.fromhex(vid) + i.to_bytes(4, "big"), 32)
    sk = ed25519.Ed25519PrivateKey.from_private_bytes(raw)
    return sk, sk.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )


def token_id(seed: bytes, vid: str, i: int) -> bytes:
    return hkdf_expand(seed, INFO_TOKID + bytes.fromhex(vid) + i.to_bytes(4, "big"), 32)


def token_message(t: bytes, pk_tok: bytes) -> bytes:
    return sha256(MSG_DOMAIN + t + pk_tok).digest()


def sign_r(tok_sk: ed25519.Ed25519PrivateKey, r: bytes) -> bytes:
    return tok_sk.sign(r)


def _mgf1(seed: bytes, length: int) -> bytes:
    out = b""
    counter = 0
    while len(out) < length:
        out += HASH(seed + counter.to_bytes(4, "big")).digest()
        counter += 1
    return out[:length]


def emsa_pss_encode(msg: bytes, em_bits: int, salt: Optional[bytes] = None) -> bytes:
    em_len = (em_bits + 7) // 8
    if em_len < HLEN + SLEN + 2:
        raise BssaError("encoding error")
    mhash = HASH(msg).digest()
    if salt is None:
        salt = os.urandom(SLEN)
    if len(salt) != SLEN:
        raise BssaError("salt must be %d bytes" % SLEN)
    m_prime = b"\x00" * 8 + mhash + salt
    h = HASH(m_prime).digest()
    ps = b"\x00" * (em_len - SLEN - HLEN - 2)
    db = ps + b"\x01" + salt
    masked = bytes(a ^ b for a, b in zip(db, _mgf1(h, em_len - HLEN - 1)))
    leftover = 8 * em_len - em_bits
    if leftover:
        masked = bytes([masked[0] & (0xFF >> leftover)]) + masked[1:]
    return masked + h + b"\xbc"


def _pub_ne(pk: rsa.RSAPublicKey) -> tuple[int, int, int]:
    nums = pk.public_numbers()
    n, e = nums.n, nums.e
    k = (n.bit_length() + 7) // 8
    return n, e, k


def _i2osp(x: int, k: int) -> bytes:
    return x.to_bytes(k, "big")


def _os2ip(b: bytes) -> int:
    return int.from_bytes(b, "big")


def blind(
    pk: rsa.RSAPublicKey,
    msg: bytes,
    *,
    salt: Optional[bytes] = None,
    inv: Optional[int] = None,
    r: Optional[int] = None,
) -> tuple[bytes, int]:
    n, e, k = _pub_ne(pk)
    # RFC 8017 RSASSA-PSS-SIGN / EMSA-PSS-VERIFY use emBits = modBits - 1.
    # RFC 9474 §4.1 writes EMSA-PSS-ENCODE(msg, bit_len(n)), but the published
    # A.3 encoded_msg is the modBits-1 encoding (first byte 0x6e). bit_len(n)
    # on that 4096-bit n leaves the high bit set (0xee) so m >= n.
    encoded = emsa_pss_encode(msg, n.bit_length() - 1, salt=salt)
    m = _os2ip(encoded)
    if m >= n or gcd(m, n) != 1:
        raise BssaError("invalid input")
    if inv is not None:
        r_val = pow(int(inv), -1, n)
        inv_val = int(inv)
    else:
        if r is None:
            while True:
                r_val = int.from_bytes(os.urandom(k), "big") % n
                if 1 <= r_val < n and gcd(r_val, n) == 1:
                    break
        else:
            r_val = int(r)
        inv_val = pow(r_val, -1, n)
    x = pow(r_val, e, n)
    z = (m * x) % n
    return _i2osp(z, k), inv_val


def gcd(a: int, b: int) -> int:
    while b:
        a, b = b, a % b
    return a


def blind_sign(sk: rsa.RSAPrivateKey, blinded_msg: bytes) -> bytes:
    n, e, k = _pub_ne(sk.public_key())
    if len(blinded_msg) != k:
        raise BssaError("unexpected input size")
    m = _os2ip(blinded_msg)
    if not (0 <= m < n):
        raise BssaError("message representative out of range")
    d = sk.private_numbers().d
    s = pow(m, d, n)
    if pow(s, e, n) != m:
        raise BssaError("signing failure")
    return _i2osp(s, k)


def finalize(pk: rsa.RSAPublicKey, msg: bytes, blind_sig: bytes, inv: int) -> bytes:
    n, _e, k = _pub_ne(pk)
    if len(blind_sig) != k:
        raise BssaError("unexpected input size")
    z = _os2ip(blind_sig)
    s = (z * int(inv)) % n
    sig = _i2osp(s, k)
    verify(pk, msg, sig)
    return sig


def verify(pk: rsa.RSAPublicKey, msg: bytes, sig: bytes) -> None:
    try:
        pk.verify(
            sig,
            msg,
            padding.PSS(mgf=padding.MGF1(hashes.SHA384()), salt_length=SLEN),
            hashes.SHA384(),
        )
    except InvalidSignature as exc:
        raise BssaError("invalid signature") from exc


def issue(sk: rsa.RSAPrivateKey, pk: rsa.RSAPublicKey, msg: bytes) -> bytes:
    blinded, inv = blind(pk, msg)
    return finalize(pk, msg, blind_sign(sk, blinded), inv)


def verify_spend(
    pk: rsa.RSAPublicKey,
    t: bytes,
    pk_tok: bytes,
    sigma: bytes,
    r: bytes,
    sig_r: bytes,
) -> None:
    verify(pk, token_message(t, pk_tok), sigma)
    try:
        ed25519.Ed25519PublicKey.from_public_bytes(pk_tok).verify(sig_r, r)
    except InvalidSignature as exc:
        raise BssaError("pk_tok did not sign this R") from exc
