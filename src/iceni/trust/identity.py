"""Mint canonical identifiers.

v0.1 mints self-certifying key identifiers (AIP `aip:key:ed25519:<multibase>`)
where the identifier literally IS the public key — zero resolution, no registry.
Durable `aip:web:<domain>` identifiers come in v0.2.
"""
from __future__ import annotations

import base64

from . import sign as _sign


def _multibase_b64url(data: bytes) -> str:
    # multibase prefix 'u' == base64url (no padding)
    return "u" + base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def mint_key_identity() -> tuple[str, bytes, bytes]:
    """Return (canonical_id, private_raw, public_raw)."""
    priv, pub = _sign.generate_keypair()
    canonical_id = "aip:key:ed25519:" + _multibase_b64url(pub)
    return canonical_id, priv, pub
