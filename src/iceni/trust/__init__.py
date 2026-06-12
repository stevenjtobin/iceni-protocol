"""Trust spine: the two load-bearing primitives.

  * Ed25519 key  -> anti-forgery  (sign.py, identity.py)
  * local petname -> anti-mimicry  (resolved in store/aliases.py; never synced)

v0.1 ships the cheap half (keys + petnames + signing). KERI rotation/revocation
and any decentralized registry are deferred to v0.2 (OQ1 = option C, unanimous).
"""
