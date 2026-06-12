"""The alias lifecycle: create / resolve / verify / list.

`create_alias` performs the whole trust dance in one transaction:
  mint identity -> save private key -> record inception key-event ->
  sign the canonical intent -> store the content-addressed alias_version ->
  bind the LOCAL petname.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone

from ..intent import Intent
from ..trust import identity as _id
from ..trust import keystore as _ks
from ..trust import sign as _sign


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class PetnameExists(Exception):
    pass


def create_alias(conn: sqlite3.Connection, petname: str, intent: Intent, scope: str = "user") -> tuple[str, str]:
    """Return (canonical_id, content_hash)."""
    existing = conn.execute(
        "SELECT 1 FROM petnames WHERE petname=? AND scope=?", (petname, scope)
    ).fetchone()
    if existing:
        raise PetnameExists(f"petname '{petname}' already exists in scope '{scope}'")

    cid, priv, pub = _id.mint_key_identity()
    _ks.save_private(cid, priv)
    now = _now()

    conn.execute(
        "INSERT INTO identities(canonical_id, kind, public_key, created_at, meta_json) VALUES (?,?,?,?,?)",
        (cid, "key", pub, now, None),
    )
    # inception key-event: sign the public key, hash-chain root
    digest = hashlib.sha256(pub).hexdigest()
    conn.execute(
        "INSERT INTO key_events(canonical_id, seq, event_type, prior_digest, digest, signature, created_at)"
        " VALUES (?,?,?,?,?,?,?)",
        (cid, 0, "inception", None, digest, _sign.sign(priv, pub), now),
    )
    # alias_version: sign the canonical intent; content-address it
    canonical = intent.canonical_json()
    content_hash = intent.content_hash()
    conn.execute(
        "INSERT INTO alias_versions(content_hash, canonical_id, semver, intent_json, parent_hash,"
        " vclock_json, signature, created_at) VALUES (?,?,?,?,?,?,?,?)",
        (content_hash, cid, "1.0.0", canonical, None, json.dumps({cid: 1}),
         _sign.sign(priv, canonical.encode("utf-8")), now),
    )
    conn.execute("INSERT INTO petnames(petname, canonical_id, scope, created_at) VALUES (?,?,?,?)",
                 (petname, cid, scope, now))
    conn.execute("INSERT OR IGNORE INTO drift_state(canonical_id) VALUES (?)", (cid,))
    conn.commit()
    return cid, content_hash


class IntentUnchanged(Exception):
    pass


def _bump_semver(semver: str, part: str = "minor") -> str:
    try:
        major, minor, patch = (int(x) for x in semver.split("."))
    except (ValueError, AttributeError):
        major, minor, patch = 1, 0, 0
    if part == "major":
        return f"{major + 1}.0.0"
    if part == "patch":
        return f"{major}.{minor}.{patch + 1}"
    return f"{major}.{minor + 1}.0"


def add_version(conn: sqlite3.Connection, canonical_id: str, new_intent: Intent, *,
                bump: str = "minor", source: str = "evolved") -> tuple[str, str]:
    """Append a new signed alias_version under an EXISTING identity (evolution).

    Same canonical_id + same private key; the new intent is content-addressed,
    Ed25519-signed, DAG-linked to its parent and SemVer-bumped. This is the
    write-half shared by Phase III calibration (--apply a winning hint) and
    Phase IV evolution. Returns (new_content_hash, new_semver).
    """
    cur = conn.execute(
        "SELECT content_hash, semver, vclock_json FROM alias_versions"
        " WHERE canonical_id=? AND deleted_at IS NULL ORDER BY created_at DESC LIMIT 1",
        (canonical_id,),
    ).fetchone()
    if cur is None:
        raise ValueError(f"no existing version for {canonical_id}")
    new_hash = new_intent.content_hash()
    if new_hash == cur["content_hash"]:
        raise IntentUnchanged("intent is identical to the current version — nothing to evolve")

    priv = _ks.load_private(canonical_id)
    canonical = new_intent.canonical_json()
    semver = _bump_semver(cur["semver"], bump)
    try:
        vclock = json.loads(cur["vclock_json"])
    except (TypeError, json.JSONDecodeError):
        vclock = {}
    vclock[canonical_id] = vclock.get(canonical_id, 0) + 1
    conn.execute(
        "INSERT INTO alias_versions(content_hash, canonical_id, semver, intent_json, parent_hash,"
        " vclock_json, signature, created_at) VALUES (?,?,?,?,?,?,?,?)",
        (new_hash, canonical_id, semver, canonical, cur["content_hash"],
         json.dumps(vclock), _sign.sign(priv, canonical.encode("utf-8")), _now()),
    )
    conn.commit()
    return new_hash, semver


def resolve(conn: sqlite3.Connection, petname: str, scope: str = "user"):
    """petname -> (canonical_id, latest alias_version row) or None."""
    row = conn.execute(
        "SELECT canonical_id FROM petnames WHERE petname=? AND scope=?", (petname, scope)
    ).fetchone()
    if not row:
        return None
    cid = row["canonical_id"]
    av = conn.execute(
        "SELECT * FROM alias_versions WHERE canonical_id=? AND deleted_at IS NULL"
        " ORDER BY created_at DESC LIMIT 1",
        (cid,),
    ).fetchone()
    return cid, av


def verify(conn: sqlite3.Connection, canonical_id: str, alias_version: sqlite3.Row) -> bool:
    """Re-check the Ed25519 signature over the stored intent. Trust = signature, not name."""
    idrow = conn.execute(
        "SELECT public_key FROM identities WHERE canonical_id=?", (canonical_id,)
    ).fetchone()
    if not idrow or idrow["public_key"] is None:
        return False
    return _sign.verify(idrow["public_key"], alias_version["intent_json"].encode("utf-8"),
                        alias_version["signature"])


def list_aliases(conn: sqlite3.Connection):
    return conn.execute(
        """
        SELECT p.petname, p.scope, p.canonical_id, a.semver, a.content_hash, a.created_at,
               (SELECT COUNT(*) FROM executions e WHERE e.content_hash = a.content_hash) AS runs
        FROM petnames p
        JOIN alias_versions a
          ON a.canonical_id = p.canonical_id AND a.deleted_at IS NULL
        WHERE a.created_at = (
            SELECT MAX(a2.created_at) FROM alias_versions a2
            WHERE a2.canonical_id = p.canonical_id AND a2.deleted_at IS NULL
        )
        ORDER BY p.petname
        """
    ).fetchall()


def export_alias(conn: sqlite3.Connection, petname: str, scope: str = "user") -> dict:
    """Portable, signed alias file — the protocol's first wire format.

    Carries the canonical identity (public key only — private keys never leave
    the node), the canonical intent, and the original Ed25519 signature, so the
    receiver verifies BEFORE trusting. Petname stays a local suggestion.
    """
    import base64
    resolved = resolve(conn, petname, scope)
    if not resolved:
        raise ValueError(f"unknown alias '{petname}'")
    cid, av = resolved
    idrow = conn.execute(
        "SELECT kind, public_key FROM identities WHERE canonical_id=?", (cid,)
    ).fetchone()
    return {
        "iceni_export": 1,
        "petname": petname,
        "identity": {
            "canonical_id": cid,
            "kind": idrow["kind"],
            "public_key": base64.b64encode(idrow["public_key"]).decode("ascii"),
        },
        "alias_version": {
            "content_hash": av["content_hash"],
            "semver": av["semver"],
            "intent_json": av["intent_json"],
            "vclock_json": av["vclock_json"],
            "signature": base64.b64encode(av["signature"]).decode("ascii"),
            "created_at": av["created_at"],
        },
    }


def import_alias(conn: sqlite3.Connection, data: dict, petname: str | None = None,
                 scope: str = "user") -> tuple[str, str, str]:
    """Install a shared alias — but only after the crypto checks out.

    Three gates, in order: the intent must be canonical (byte-identical to its
    canonical serialization), its sha256 must match the claimed content hash,
    and the Ed25519 signature must verify against the carried public key. Any
    failure rejects the file — this is the Alias Injection defense at the door.
    The importer gets no private key, so the alias can be USED but not evolved.
    """
    import base64
    if data.get("iceni_export") != 1:
        raise ValueError("not an ICENI export file")
    ident, av = data["identity"], data["alias_version"]
    pub = base64.b64decode(ident["public_key"])
    sig = base64.b64decode(av["signature"])

    intent = Intent.from_json(av["intent_json"])
    if intent.canonical_json() != av["intent_json"]:
        raise ValueError("intent_json is not canonical — file was modified")
    if intent.content_hash() != av["content_hash"]:
        raise ValueError("content hash mismatch — file was modified")
    if not _sign.verify(pub, av["intent_json"].encode("utf-8"), sig):
        raise ValueError("signature INVALID — rejecting import (tampered file or wrong key)")

    name = petname or data.get("petname") or "imported"
    if conn.execute("SELECT 1 FROM petnames WHERE petname=? AND scope=?",
                    (name, scope)).fetchone():
        raise PetnameExists(f"petname '{name}' already exists — re-run with --as <other-name>")

    now = _now()
    cid = ident["canonical_id"]
    conn.execute(
        "INSERT OR IGNORE INTO identities(canonical_id, kind, public_key, created_at, meta_json)"
        " VALUES (?,?,?,?,?)",
        (cid, ident.get("kind", "key"), pub, now, json.dumps({"imported": True})),
    )
    conn.execute(
        "INSERT OR IGNORE INTO alias_versions(content_hash, canonical_id, semver, intent_json,"
        " parent_hash, vclock_json, signature, created_at) VALUES (?,?,?,?,?,?,?,?)",
        (av["content_hash"], cid, av["semver"], av["intent_json"], None,
         av.get("vclock_json") or json.dumps({}), sig, av.get("created_at", now)),
    )
    conn.execute("INSERT INTO petnames(petname, canonical_id, scope, created_at) VALUES (?,?,?,?)",
                 (name, cid, scope, now))
    conn.execute("INSERT OR IGNORE INTO drift_state(canonical_id) VALUES (?)", (cid,))
    conn.commit()
    return name, cid, av["semver"]


def stats(conn: sqlite3.Connection):
    """Per-alias adoption: uses + outcome breakdown + parse-fit, across all versions.

    Pure observability for Product Mode — what people actually use repeatedly
    (GPT's Weekly-Active-Aliases lens), not a protocol capability.
    """
    return conn.execute(
        """
        SELECT p.petname,
               COUNT(e.id) AS uses,
               SUM(CASE WHEN e.outcome='accepted' THEN 1 ELSE 0 END) AS accepted,
               SUM(CASE WHEN e.outcome='edited'   THEN 1 ELSE 0 END) AS edited,
               SUM(CASE WHEN e.outcome='rejected' THEN 1 ELSE 0 END) AS rejected,
               SUM(CASE WHEN e.parse_ok=1 THEN 1 ELSE 0 END)         AS parse_fit,
               SUM(CASE WHEN e.parse_ok IS NOT NULL THEN 1 ELSE 0 END) AS parse_known,
               MAX(e.created_at) AS last_used
        FROM petnames p
        LEFT JOIN alias_versions a ON a.canonical_id = p.canonical_id
        LEFT JOIN executions e      ON e.content_hash = a.content_hash
        GROUP BY p.petname
        ORDER BY uses DESC, p.petname
        """
    ).fetchall()


def record_execution(conn, content_hash, model, *, outcome=None, user_edit=None,
                     tokens_in=None, tokens_out=None, embedding=None,
                     parse_ok=None, quality=None, edit_distance=None) -> None:
    conn.execute(
        "INSERT INTO executions(content_hash, model, outcome, user_edit, tokens_in, tokens_out,"
        " embedding, parse_ok, quality, edit_distance, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (content_hash, model, outcome, user_edit, tokens_in, tokens_out, embedding,
         None if parse_ok is None else int(parse_ok), quality, edit_distance, _now()),
    )
    conn.commit()
