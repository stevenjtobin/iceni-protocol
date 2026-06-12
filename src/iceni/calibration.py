"""Render a model-agnostic Intent into a per-model prompt.

v0.1 uses a deterministic, offline template renderer keyed on model family and
the intent's own style_hints. This deliberately needs NO API call, so `compare`
and `run --preview` demonstrate cross-model calibration (value-case V1) even
without keys. v0.2 swaps in an LLM-backed calibrator (PromptBridge-style) behind
the same `render()` signature.
"""
from __future__ import annotations

from .intent import Intent

KNOWN_MODELS = ("claude", "gpt", "kimi")


def render(intent: Intent, model: str) -> str:
    fam = model.lower()
    if "claude" in fam:
        return _claude(intent)
    if "gpt" in fam:
        return _gpt(intent)
    if "kimi" in fam:
        return _kimi(intent)
    return _generic(intent)


def _hint(intent: Intent, model_family: str) -> str:
    return str(intent.style_hints.get(model_family, "")).strip()


def _claude(i: Intent) -> str:
    # Claude responds well to XML-structured instructions.
    parts = [f"<task>{i.goal}</task>"]
    if i.inputs:
        parts.append("<inputs>\n" + "\n".join(f"  <input>{x}</input>" for x in i.inputs) + "\n</inputs>")
    if i.constraints:
        parts.append("<constraints>\n" + "\n".join(f"  <constraint>{c}</constraint>" for c in i.constraints) + "\n</constraints>")
    if i.outputs:
        fmt = i.outputs.get("format") or ", ".join(i.outputs.keys())
        parts.append(f"<output_format>{fmt}</output_format>")
    extra = _hint(i, "claude")
    if extra:
        parts.append(f"<note>{extra}</note>")
    return "\n".join(parts)


def _gpt(i: Intent) -> str:
    # GPT works well with concise markdown.
    lines = [f"**Task:** {i.goal}", ""]
    if i.inputs:
        lines += ["**Inputs:**"] + [f"- {x}" for x in i.inputs] + [""]
    if i.constraints:
        lines += ["**Requirements:**"] + [f"- {c}" for c in i.constraints] + [""]
    if i.outputs:
        fmt = i.outputs.get("format") or ", ".join(i.outputs.keys())
        lines += [f"**Output:** {fmt}"]
    extra = _hint(i, "gpt")
    if extra:
        lines += ["", extra]
    return "\n".join(lines).strip()


def _kimi(i: Intent) -> str:
    # Kimi: direct, compact imperative.
    seg = [i.goal.rstrip(".") + "."]
    if i.inputs:
        seg.append("Inputs: " + "; ".join(i.inputs) + ".")
    if i.constraints:
        seg.append("Constraints: " + "; ".join(i.constraints) + ".")
    if i.outputs:
        fmt = i.outputs.get("format") or ", ".join(i.outputs.keys())
        seg.append(f"Return: {fmt}.")
    extra = _hint(i, "kimi")
    if extra:
        seg.append(extra)
    return " ".join(seg)


def _generic(i: Intent) -> str:
    out = [i.goal]
    if i.inputs:
        out.append("Inputs: " + "; ".join(i.inputs))
    if i.constraints:
        out.append("Constraints: " + "; ".join(i.constraints))
    if i.outputs:
        out.append("Output: " + (i.outputs.get("format") or ", ".join(i.outputs.keys())))
    return "\n".join(out)
