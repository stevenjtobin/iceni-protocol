"""Smoke test: the full trust dance + offline rendering, isolated to a temp home."""
import json
import os
import tempfile

import pytest


@pytest.fixture()
def home(monkeypatch):
    d = tempfile.mkdtemp(prefix="iceni-test-")
    monkeypatch.setenv("ICENI_HOME", d)
    yield d


def test_create_resolve_verify_render(home):
    from iceni.intent import Intent
    from iceni.store import aliases, db

    conn = db.connect()
    intent = Intent(
        goal="Review code for bugs, edge cases, security.",
        inputs=["{{code}}"],
        constraints=["be concise", "cite line numbers"],
        outputs={"format": "issues, severity"},
        style_hints={"claude": "use XML tags", "gpt": "markdown list"},
    )
    cid, content_hash = aliases.create_alias(conn, "review", intent)
    assert cid.startswith("aip:key:ed25519:")
    assert len(content_hash) == 64  # sha256 hex

    cid2, av = aliases.resolve(conn, "review")
    assert cid2 == cid
    assert aliases.verify(conn, cid, av) is True  # signature valid

    # tamper → signature must fail
    bad = dict(av)
    conn.execute("UPDATE alias_versions SET intent_json=? WHERE content_hash=?",
                 ('{"goal":"evil"}', content_hash))
    conn.commit()
    _, av2 = aliases.resolve(conn, "review")
    assert aliases.verify(conn, cid, av2) is False

    conn.close()


def test_per_model_render_differs(home):
    from iceni import calibration
    from iceni.intent import Intent

    intent = Intent(goal="Summarize this", outputs={"format": "bullets"})
    claude = calibration.render(intent, "claude")
    gpt = calibration.render(intent, "gpt")
    kimi = calibration.render(intent, "kimi")
    assert claude != gpt != kimi
    assert "<task>" in claude  # Claude gets XML
    assert "**Task:**" in gpt  # GPT gets markdown


def test_content_hash_is_deterministic(home):
    from iceni.intent import Intent

    a = Intent(goal="x", constraints=["a", "b"])
    b = Intent(goal="x", constraints=["a", "b"])
    assert a.content_hash() == b.content_hash()


def test_benchmark_offline(home, tmp_path):
    from iceni import benchmark

    tasks = {"tasks": [{
        "name": "summarize",
        "intent": {"goal": "Summarize this text", "outputs": {"format": "bullets"},
                   "style_hints": {"claude": "XML", "gpt": "markdown"}},
        "baseline": "Please write a very thorough and detailed summary of the following text, "
                    "covering every point in depth and leaving nothing out whatsoever.",
    }]}
    f = tmp_path / "tasks.json"
    f.write_text(json.dumps(tasks), encoding="utf-8")

    results, meta = benchmark.run(str(f), ["kimi", "claude", "gpt"], {"models": {}}, execute=False)
    assert len(results) == 1
    assert len(results[0].cells) == 3
    # kimi's concise render should use fewer tokens than the verbose baseline
    kimi = next(c for c in results[0].cells if c.model == "kimi")
    assert kimi.in_tok_iceni < kimi.in_tok_base
    report = benchmark.render_report(results, meta)
    assert "ICENI Benchmark Report" in report and "Verdict" in report
