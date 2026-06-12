"""Phase II discovery: the pipeline finds recurring intents and rejects noise."""
import json
from pathlib import Path

import pytest

from iceni import discovery


def _write_log(dirpath: Path, rows: list[dict]) -> None:
    lines = []
    for r in rows:
        lines.append(json.dumps({"type": "user", "message": {"role": "user", "content": r["text"]}}))
    (dirpath / "session.jsonl").write_text("\n".join(lines), encoding="utf-8")


def test_iter_user_prompts_filters_noise(tmp_path):
    proj = tmp_path / "proj-a"
    proj.mkdir()
    _write_log(proj, [
        {"text": "Summarize the following article into three short bullet points."},
        {"text": "<command-name>/clear</command-name>"},          # harness noise
        {"text": "[Image: original 1920x2153, multiply coordinates]"},  # injected image
        {"text": "steven@host:~$ sudo systemctl restart nginx"},   # pasted shell
        {"text": "ok"},                                            # too short / filler
    ])
    prompts = discovery.iter_user_prompts(str(tmp_path))
    texts = [p.text for p in prompts]
    assert any("Summarize" in t for t in texts)
    assert all("<command-name>" not in t for t in texts)
    assert all(not t.startswith("[Image") for t in texts)
    assert all("@host:~$" not in t for t in texts)


def test_discover_finds_recurring_cluster_and_gates_blob(tmp_path):
    pytest.importorskip("hdbscan")
    pytest.importorskip("sklearn")
    proj = tmp_path / "proj"
    proj.mkdir()
    rows = []
    for _ in range(5):
        rows.append({"text": "Summarize the following article into three short bullet points."})
        rows.append({"text": "Translate the following paragraph into formal French."})
    # unrelated singletons that must NOT form a confident cluster
    rows += [{"text": "What is the capital of Australia today?"},
             {"text": "Explain quantum entanglement to a child."}]
    _write_log(proj, rows)

    cands, scanned = discovery.discover(str(tmp_path), min_cluster_size=3, limit=10)
    assert scanned >= 10
    assert cands, "expected at least one recurring-intent candidate"
    # every surviving candidate must clear the cohesion gate
    assert all(c.cohesion >= 0.34 for c in cands)
    goals = " ".join(c.goal.lower() for c in cands)
    assert "summarize" in goals or "translate" in goals


def test_cross_project_intent_outranks_single_project_burst(tmp_path):
    pytest.importorskip("hdbscan")
    pytest.importorskip("sklearn")
    # Project A: a high-frequency single-session burst (project-local noise).
    a = tmp_path / "proj-a"; a.mkdir()
    _write_log(a, [{"text": "Regenerate the fixture file for the parser test again."}
                   for _ in range(8)])
    # Two other projects share a lower-frequency but portable intent.
    for name in ("proj-b", "proj-c"):
        d = tmp_path / name; d.mkdir()
        _write_log(d, [{"text": "Audit these dependencies for known security vulnerabilities."}
                       for _ in range(3)])

    cands, _ = discovery.discover(str(tmp_path), min_cluster_size=3, limit=10)
    assert len(cands) >= 2
    top = cands[0]
    # The cross-project intent must rank above the bigger single-project burst.
    assert len(top.projects) >= 2, f"top candidate was single-project: {top.petname}"
    assert "audit" in top.goal.lower()


def test_candidate_to_intent_is_signable(tmp_path):
    c = discovery.Candidate(petname="summ", goal="Summarize the article", size=5, cohesion=0.9)
    intent = discovery.candidate_to_intent(c)
    assert intent.goal.endswith(".")
    assert intent.content_hash()  # deterministic, hashable → can be signed by the trust spine
