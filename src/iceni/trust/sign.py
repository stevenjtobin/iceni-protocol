"""Ed25519 sign/verify. Backed by `cryptography`; raw 32-byte keys.

Kept deliberately tiny and swappable — the rest of the system depends only on
generate_keypair / sign / verify, so a pynacl or HSM backend can drop in later.
"""
from __future__ import annotations

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


def generate_keypair() -> tuple[bytes, bytes]:
    """Return (private_raw_32, public_raw_32)."""
    sk = Ed25519PrivateKey.generate()
    priv = sk.private_bytes(
        serialization.Encoding.Raw,
        serialization.PrivateFormat.Raw,
        serialization.NoEncryption(),
    )
    pub = sk.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    return priv, pub


def sign(private_raw: bytes, message: bytes) -> bytes:
    return Ed25519PrivateKey.from_private_bytes(private_raw).sign(message)


def verify(public_raw: bytes, message: bytes, signature: bytes) -> bool:
    try:
        Ed25519PublicKey.from_public_bytes(public_raw).verify(signature, message)
        return True
    except Exception:
        return False
