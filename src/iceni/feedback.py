"""Phase III — live calibration from execution feedback.

The objective function is downstream-CONSUMER SUCCESS, not output style (GPT + Kimi,
unanimous): style is only the lever ICENI pulls; what we optimize is whether the next
agent/human can use the output — does it parse in the target shape, did the user accept
it, how much did they have to edit. `structure_ok` is the free, deterministic half of
that signal (no judge, no API key); acceptance + edit-distance come from real usage.

`iceni calibrate <alias>` reads these signals back per model and proposes the next
style-hint variant to try. Running the variants needs live execution (API keys, or
accumulated subscription usage via the MCP server) — this module scores whatever exists.
"""
from __future__ import annotations

import difflib
import re
import sqlite3
import xml.etree.ElementTree as ET

# Weights for the consumer-success objective (sum to 1.0).
W_PARSE, W_ACCEPT, W_EDIT = 0.4, 0.4, 0.2
_ACCEPT = {"accepted": 1.0, "edited": 0.5, "rejected": 0.0}


def structure_ok(text: str, model: str) -> bool:
    """Did the output land in the shape this model is calibrated to emit? Deterministic.

    The point of the per-model render is a predictable downstream contract:
    Claude→XML, GPT→markdown (table/bold/list), Kimi→concise prose. A consumer can
    rely on that shape only if the model actually produces it — that is the signal.
    """
    if not text or not text.strip():
        return False
    fam = model.lower()
    body = re.sub(r"^```[a-zA-Z]*\n|\n```$", "", text.strip()).strip()
    if "claude" in fam:
        for cand in (body, f"<root>{body}</root>"):
            try:
                root = ET.fromstring(cand)
                if len(root):  # has child elements, not just a bare tag
                    return True
            except ET.ParseError:
                continue
        return False
    if "gpt" in fam:
        has_table = bool(re.search(r"^\s*\|.*\|.*\|", text, re.M))
        has_bold = "**" in text
        has_list = bool(re.search(r"^\s*(?:[-*]|\d+[.)])\s", text, re.M))
        return has_table or has_bold or has_list
    if "kimi" in fam:  # concise: no XML, not markdown-table-heavy
        return "<" not in body or ">" not in body
    return True


def edit_ratio(rendered: str, final: str | None) -> float:
    """0.0 = user kept the output verbatim, 1.0 = rewrote it entirely."""
    if not final or not rendered:
        return 0.0
    return 1.0 - difflib.SequenceMatcher(None, rendered, final).ratio()


def outcome_score(parse_ok: bool | None, outcome: str | None, edit: float = 0.0) -> float:
    """Composite consumer-success score in [0,1]. Unknown signals score neutrally."""
    p = 1.0 if parse_ok else (0.5 if parse_ok is None else 0.0)
    a = _ACCEPT.get(outcome, 0.5)
    e = 1.0 - min(1.0, max(0.0, edit))
    return round(W_PARSE * p + W_ACCEPT * a + W_EDIT * e, 3)


def aggregate(conn: sqlite3.Connection, content_hash: str, model: str) -> dict:
    """Mean consumer-success score + counts over recorded executions for (alias, model)."""
    rows = conn.execute(
        "SELECT parse_ok, outcome, edit_distance FROM executions"
        " WHERE content_hash=? AND model=?",
        (content_hash, model),
    ).fetchall()
    if not rows:
        return {"n": 0, "score": None, "parse_rate": None, "accept_rate": None}
    # Re-scored from raw components every call, so changing the weights re-scores
    # all history with no rerun (GPT). Only edit_distance had no recompute path.
    scores, parses, accepts = [], [], []
    for r in rows:
        po = None if r["parse_ok"] is None else bool(r["parse_ok"])
        ed = r["edit_distance"] if r["edit_distance"] is not None else 0.0
        scores.append(outcome_score(po, r["outcome"], ed))
        if po is not None:
            parses.append(1.0 if po else 0.0)
        if r["outcome"]:
            accepts.append(_ACCEPT.get(r["outcome"], 0.5))
    return {
        "n": len(rows),
        "score": round(sum(scores) / len(scores), 3),
        "parse_rate": round(sum(parses) / len(parses), 3) if parses else None,
        "accept_rate": round(sum(accepts) / len(accepts), 3) if accepts else None,
    }


# Candidate style-hint palette — the search space a calibration run A/B-tests.
_VARIANTS = {
    "claude": [
        "XML tags with severity attributes on each element",
        "nested XML: <finding> elements with cwe and severity attributes",
        "a single flat XML list, one self-closing element per item",
    ],
    "gpt": [
        "prioritized markdown table: column per field",
        "bold-led bullets grouped by severity",
        "numbered markdown list with inline CWE references",
    ],
    "kimi": [
        "terse bullet points, highest severity first, no markup",
        "one line per finding: SEVERITY — description → fix",
        "compact prose, no headers, no tables",
    ],
}


def propose_variants(model: str, current: str | None = None) -> list[str]:
    """Next style-hint experiments to run for this model (skips the current one)."""
    fam = next((k for k in _VARIANTS if k in model.lower()), None)
    if not fam:
        return []
    return [v for v in _VARIANTS[fam] if v.strip().lower() != (current or "").strip().lower()]
