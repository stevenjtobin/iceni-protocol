"""Phase III: the consumer-success objective function and feedback aggregation."""
from iceni import feedback


def test_structure_ok_per_model():
    assert feedback.structure_ok("<issues><issue severity='high'>x</issue></issues>", "claude")
    assert not feedback.structure_ok("Just some prose, no tags here.", "claude")
    assert feedback.structure_ok("| sev | cwe |\n| high | 79 |", "gpt")
    assert feedback.structure_ok("- **High**: something\n- **Low**: other", "gpt")
    assert feedback.structure_ok("high: sql injection; low: missing header", "kimi")
    assert not feedback.structure_ok("<finding>too much markup</finding>", "kimi")
    assert not feedback.structure_ok("", "claude")


def test_outcome_score_rewards_consumer_success():
    best = feedback.outcome_score(parse_ok=True, outcome="accepted", edit=0.0)
    worst = feedback.outcome_score(parse_ok=False, outcome="rejected", edit=1.0)
    middling = feedback.outcome_score(parse_ok=None, outcome=None, edit=0.0)
    assert best == 1.0
    assert worst == 0.0
    assert worst < middling < best


def test_edit_ratio_bounds():
    assert feedback.edit_ratio("hello world", "hello world") == 0.0
    assert feedback.edit_ratio("aaaa", "zzzz") > 0.9
    assert feedback.edit_ratio("anything", None) == 0.0


def test_propose_variants_excludes_current():
    cur = "XML tags with severity attributes on each element"
    variants = feedback.propose_variants("claude", current=cur)
    assert variants and cur not in variants
    assert feedback.propose_variants("unknown-model") == []


def test_add_version_evolves_under_same_identity(tmp_path, monkeypatch):
    monkeypatch.setenv("ICENI_HOME", str(tmp_path / ".iceni"))
    import pytest
    from iceni.intent import Intent
    from iceni.store import aliases, db

    conn = db.connect()
    cid, h1 = aliases.create_alias(conn, "review", Intent(goal="Review.",
                                   style_hints={"claude": "use XML"}))
    # Evolve: same identity, new signed version with a refined hint.
    h2, semver = aliases.add_version(conn, cid, Intent(goal="Review.",
                                     style_hints={"claude": "use XML with severity attributes"}))
    assert h2 != h1 and semver == "1.1.0"

    # resolve() now returns the new version, and its signature still verifies.
    rcid, av = aliases.resolve(conn, "review")
    assert rcid == cid                       # same identity, not a new mint
    assert av["content_hash"] == h2
    assert av["parent_hash"] == h1           # DAG-linked to its parent
    assert aliases.verify(conn, cid, av)     # trust rides on the signature

    # Re-applying the identical intent is a no-op error, not a silent duplicate.
    with pytest.raises(aliases.IntentUnchanged):
        aliases.add_version(conn, cid, Intent(goal="Review.",
                            style_hints={"claude": "use XML with severity attributes"}))
    conn.close()


def test_aggregate_reads_recorded_executions(tmp_path, monkeypatch):
    # Point ICENI at a throwaway home so we never touch the real DB.
    monkeypatch.setenv("ICENI_HOME", str(tmp_path / ".iceni"))
    from iceni.intent import Intent
    from iceni.store import aliases, db

    conn = db.connect()
    # migration 0002 must have added the consumer-success columns
    cols = {r[1] for r in conn.execute("PRAGMA table_info(executions)").fetchall()}
    assert {"parse_ok", "quality"} <= cols

    _, ch = aliases.create_alias(conn, "t", Intent(goal="Do a thing."))
    aliases.record_execution(conn, ch, "claude", outcome="accepted", parse_ok=True)
    aliases.record_execution(conn, ch, "claude", outcome="edited", parse_ok=True)
    agg = feedback.aggregate(conn, ch, "claude")
    assert agg["n"] == 2
    assert agg["parse_rate"] == 1.0
    assert 0.0 < agg["score"] <= 1.0

    # stats dashboard: outcome breakdown + parse-fit
    aliases.record_execution(conn, ch, "gpt", outcome="rejected", parse_ok=False)
    rows = {r["petname"]: r for r in aliases.stats(conn)}
    conn.close()
    assert rows["t"]["uses"] == 3
    assert rows["t"]["accepted"] == 1
    assert rows["t"]["edited"] == 1
    assert rows["t"]["rejected"] == 1
    assert rows["t"]["parse_fit"] == 2  # two parse_ok=True, one False
