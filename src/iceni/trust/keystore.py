"""Local private-key storage (~/.iceni/keys/<canonical_id>.key).

v0.1: raw key bytes on disk, best-effort 0600. v0.2 candidate: OS keyring /
passphrase-wrapped. Private keys NEVER leave the local node.
"""
from __future__ import annotations

from .. import config


def _fname(canonical_id: str) -> str:
    return canonical_id.replace(":", "_").replace("/", "_") + ".key"


def save_private(canonical_id: str, private_raw: bytes) -> None:
    config.keys_dir().mkdir(parents=True, exist_ok=True)
    path = config.keys_dir() / _fname(canonical_id)
    path.write_bytes(private_raw)
    try:
        path.chmod(0o600)
    except OSError:
        pass  # Windows / unsupported FS — acceptable for v0.1


def load_private(canonical_id: str) -> bytes:
    return (config.keys_dir() / _fname(canonical_id)).read_bytes()
