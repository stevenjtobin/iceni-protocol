"""Alias packs: every bundled pack is valid, installable, and signed end-to-end."""
import json

import pytest


def _packs():
    from importlib.resources import files
    d = files("iceni").joinpath("packs")
    return [f for f in d.iterdir() if f.name.endswith(".json")]


def test_bundled_packs_are_valid_intents():
    from iceni.intent import Intent
    packs = _packs()
    assert len(packs) >= 2
    for f in packs:
        data = json.loads(f.read_text(encoding="utf-8"))
        assert data["name"] and data["description"]
        for a in data["aliases"]:
            intent = Intent.from_dict(a["intent"])
            assert intent.goal
            assert intent.content_hash()  # canonicalizes + hashes cleanly


def test_pack_install_creates_signed_aliases(tmp_path, monkeypatch):
    monkeypatch.setenv("ICENI_HOME", str(tmp_path / ".iceni"))
    from iceni.intent import Intent
    from iceni.store import aliases, db

    data = json.loads(_packs()[0].read_text(encoding="utf-8"))
    conn = db.connect()
    for a in data["aliases"]:
        aliases.create_alias(conn, a["petname"], Intent.from_dict(a["intent"]))
    rows = aliases.list_aliases(conn)
    assert len(rows) == len(data["aliases"])
    for r in rows:
        cid, av = aliases.resolve(conn, r["petname"])
        assert aliases.verify(conn, cid, av)  # signature valid for every pack alias
    # Re-install attempt raises PetnameExists (the CLI skips these gracefully).
    with pytest.raises(aliases.PetnameExists):
        aliases.create_alias(conn, data["aliases"][0]["petname"],
                             Intent.from_dict(data["aliases"][0]["intent"]))
    conn.close()
