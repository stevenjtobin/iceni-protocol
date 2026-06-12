"""The value-case benchmark (ChatGPT + Kimi's unanimous next step).

Compares, per task and per model, a natural-language BASELINE prompt against the
ICENI per-model calibrated render. Offline it measures input tokens, format fit,
and semantic preservation; with --execute it adds output tokens, cost, latency,
LLM-scored task quality, and a cost-per-quality breakdown. Prints an honest
verdict vs the agreed thresholds — including PIVOT if ICENI merely ties baseline.

Swarm projection (always offline): models how inter-agent routing tokens compare
when aliases compress the instruction set to ≈3 tokens vs full-prompt relay.
"""
from __future__ import annotations

import json
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import calibration
from .intent import Intent
from .providers.base import ProviderUnavailable, get_provider

# $/Mtok — override per-task-file via "pricing". Verify at provider pricing pages.
# Kimi = moonshot-v1-32k (June 2026). Claude = sonnet-4-6. GPT = gpt-4o.
PRICING_DEFAULT = {
    "claude": {"in": 3.0,  "out": 15.0},
    "gpt":    {"in": 2.5,  "out": 10.0},
    "kimi":   {"in": 1.5,  "out": 7.5},   # moonshot-v1-32k — was $0.6/$2.5 (cheaper tier)
}

# Thresholds (GPT). Any one met => proceed.
THRESH = {"token_reduction": 0.20, "quality_gain": 0.15, "speed_gain": 0.25}
# V1 rubric weights (Kimi).
V1_WEIGHTS = {"functional": 0.40, "token": 0.30, "format": 0.15, "semantic": 0.15}
# Tokens for alias petname in inter-agent messages (e.g. "review" ≈ 1-3 tok).
ALIAS_ROUTING_TOKENS = 3


def estimate_tokens(text: str) -> int:
    """Consistent token estimate. Uses tiktoken if present, else ~4 chars/token."""
    try:
        import tiktoken
        return len(tiktoken.get_encoding("o200k_base").encode(text))
    except Exception:
        return max(1, round(len(text) / 4))


def format_score(prompt: str, model: str) -> float:
    """Does the render use the model's preferred shape? 1.0 = yes."""
    fam = model.lower()
    if "claude" in fam:
        return 1.0 if "<" in prompt and ">" in prompt else 0.0
    if "gpt" in fam:
        return 1.0 if "**" in prompt or prompt.lstrip().startswith("-") else 0.0
    if "kimi" in fam:
        return 1.0 if ("**" not in prompt and "<" not in prompt) else 0.0
    return 0.5


def semantic_similarity(a: str, b: str):
    """Cosine between two renders (sentence-transformers). None if unavailable."""
    try:
        from sentence_transformers import SentenceTransformer, util
        m = SentenceTransformer("all-MiniLM-L6-v2")
        emb = m.encode([a, b])
        return float(util.cos_sim(emb[0], emb[1]).item())
    except Exception:
        return None


def _apply_input(prompt: str, text: str) -> str:
    for ph in ("{{file}}", "{{code}}", "{{input}}", "{{context}}"):
        if ph in prompt:
            return prompt.replace(ph, text)
    return prompt + "\n\n" + text


@dataclass
class Cell:
    model: str
    in_tok_base: int
    in_tok_iceni: int
    fmt: float
    semantic: float | None = None
    input_tok: int = 0          # tokens in raw input alone (for swarm projection)
    out_tok_base: int = 0
    out_tok_iceni: int = 0
    cost_base: float = 0.0
    cost_iceni: float = 0.0
    latency_base: float = 0.0
    latency_iceni: float = 0.0
    quality_base: float | None = None
    quality_iceni: float | None = None


@dataclass
class TaskResult:
    name: str
    cells: list[Cell] = field(default_factory=list)


def _intent_for(task: dict, resolver) -> Intent:
    if "intent" in task:
        return Intent.from_dict(task["intent"])
    if "petname" in task and resolver is not None:
        resolved = resolver(task["petname"])
        if resolved:
            return Intent.from_json(resolved[1]["intent_json"])
    raise ValueError(f"task '{task.get('name')}' needs an 'intent' or resolvable 'petname'")


def _judge(provider, goal: str, output: str) -> float | None:
    prompt = (f"Task: {goal}\n\nA model produced this output:\n---\n{output[:4000]}\n---\n"
              "Score 0-100 how well the output accomplishes the task. Reply with ONLY the integer.")
    try:
        import re
        txt = provider.complete(prompt).text
        m = re.search(r"\d{1,3}", txt)
        return float(m.group()) if m else None
    except Exception:
        return None


def run(tasks_path: str, models: list[str], cfg: dict, *, execute: bool = False,
        judge_model: str | None = None, resolver=None) -> tuple[list[TaskResult], dict]:
    data = json.loads(Path(tasks_path).read_text(encoding="utf-8"))
    pricing = {**PRICING_DEFAULT, **data.get("pricing", {})}
    base_dir = Path(tasks_path).parent
    judge_provider = None
    if execute and judge_model:
        try:
            judge_provider = get_provider(judge_model, cfg)
        except ProviderUnavailable:
            judge_provider = None

    results: list[TaskResult] = []
    for task in data.get("tasks", []):
        intent = _intent_for(task, resolver)
        baseline = task.get("baseline") or intent.goal

        # Resolve input: file takes priority, then inline "input" field
        inp = ""
        if task.get("input_file"):
            p = Path(task["input_file"])
            if not p.is_absolute():
                p = base_dir / p
            inp = p.read_text(encoding="utf-8") if p.exists() else ""
        elif task.get("input"):
            inp = task["input"]
        input_tok = estimate_tokens(inp) if inp else 0

        tr = TaskResult(name=task.get("name", intent.goal[:24]))
        for model in models:
            iceni_prompt = calibration.render(intent, model)
            base_prompt = baseline
            if inp:
                iceni_prompt = _apply_input(iceni_prompt, inp)
                base_prompt = _apply_input(base_prompt, inp)

            cell = Cell(
                model=model,
                in_tok_base=estimate_tokens(base_prompt),
                in_tok_iceni=estimate_tokens(iceni_prompt),
                fmt=format_score(iceni_prompt, model),
                semantic=semantic_similarity(base_prompt, iceni_prompt),
                input_tok=input_tok,
            )
            if execute:
                try:
                    prov = get_provider(model, cfg)
                    price = pricing.get(model, {"in": 0.0, "out": 0.0})
                    for variant, prompt in (("base", base_prompt), ("iceni", iceni_prompt)):
                        t0 = time.perf_counter()
                        comp = prov.complete(prompt)
                        dt = time.perf_counter() - t0
                        out_tok = comp.tokens_out or estimate_tokens(comp.text)
                        in_tok = comp.tokens_in or estimate_tokens(prompt)
                        cost = (in_tok * price["in"] + out_tok * price["out"]) / 1_000_000
                        q = _judge(judge_provider, intent.goal, comp.text) if judge_provider else None
                        if variant == "base":
                            cell.out_tok_base, cell.cost_base, cell.latency_base, cell.quality_base = out_tok, cost, dt, q
                        else:
                            cell.out_tok_iceni, cell.cost_iceni, cell.latency_iceni, cell.quality_iceni = out_tok, cost, dt, q
                except ProviderUnavailable:
                    pass
            tr.cells.append(cell)
        results.append(tr)

    return results, {"executed": execute, "judged": judge_provider is not None,
                     "models": models, "pricing": pricing}


def _pct(base: float, new: float) -> float | None:
    if not base:
        return None
    return (base - new) / base


def _swarm_projection(results: list[TaskResult], pricing: dict) -> list[str]:
    """
    Project inter-agent routing token savings at swarm scale.
    Traditional: each hop relays the full instruction+input.
    ICENI: each hop sends alias name (≈3 tok) + raw input only.
    """
    hop_data = []
    for tr in results:
        for c in tr.cells:
            trad = c.in_tok_base
            iceni = c.input_tok + ALIAS_ROUTING_TOKENS
            if trad > 0 and trad > iceni:
                hop_data.append((tr.name, c.model, trad, iceni,
                                 pricing.get(c.model, {"in": 3.0})["in"]))

    if not hop_data:
        return []

    avg_trad = statistics.mean(h[2] for h in hop_data)
    avg_iceni = statistics.mean(h[3] for h in hop_data)
    compression = (avg_trad - avg_iceni) / avg_trad if avg_trad else 0

    lines = ["## Swarm Scale Projection ⚠ HYPOTHESIS — NOT YET MEASURED", ""]
    lines.append(
        f"> **Assumptions (unverified):** (1) agents relay intent to the next hop; "
        f"(2) ICENI path sends alias name (≈{ALIAS_ROUTING_TOKENS} tok) + raw input only; "
        f"(3) traditional path sends the full instruction set + input every hop. "
        f"**This has not been tested in a real multi-agent setup.** "
        f"The model below is a theoretical projection to motivate the multi-agent benchmark."
    )
    lines.append("")
    lines.append(
        f"Theoretical per-hop: traditional **{avg_trad:.0f} tokens** · "
        f"ICENI **{avg_iceni:.0f} tokens** → **{compression*100:.0f}% routing compression**."
    )
    lines.append("")
    lines.append("| agents | msgs/agent/day | trad routing tok (projected) | ICENI routing tok (projected) | projected savings |")
    lines.append("|--:|--:|--:|--:|--:|")
    for n_agents in (5, 10, 25, 50, 100):
        for msgs_per_agent in (100, 1000):
            trad_total = n_agents * msgs_per_agent * avg_trad
            iceni_total = n_agents * msgs_per_agent * avg_iceni
            pct = (trad_total - iceni_total) / trad_total if trad_total else 0
            lines.append(
                f"| {n_agents} | {msgs_per_agent} "
                f"| {trad_total:,.0f} | {iceni_total:,.0f} | {pct*100:.0f}% |"
            )
    lines.append("")
    lines.append(
        "_To validate: build a multi-agent harness where Agent A passes intent to Agent B — _\n"
        "_compare full-prompt relay vs alias-name relay. That data replaces this projection._"
    )
    return lines


def render_report(results: list[TaskResult], meta: dict) -> str:
    cells = [c for tr in results for c in tr.cells]
    pricing = meta.get("pricing", PRICING_DEFAULT)
    lines = ["# ICENI Benchmark Report", ""]
    lines.append(f"Tasks: {len(results)} · Models: {', '.join(meta['models'])} · "
                 f"Mode: {'EXECUTE' if meta['executed'] else 'offline (input-side only)'}"
                 + (" · judged" if meta.get("judged") else ""))
    lines.append("")

    # Per-task input-side table
    lines.append("## Input-side (offline-measurable)")
    lines.append("")
    lines.append("| task | model | base tok | iceni tok | Δtok | format | semantic |")
    lines.append("|---|---|--:|--:|--:|:--:|:--:|")
    for tr in results:
        for c in tr.cells:
            d = _pct(c.in_tok_base, c.in_tok_iceni)
            dstr = f"{d*100:+.0f}%" if d is not None else "n/a"
            sem = f"{c.semantic:.2f}" if c.semantic is not None else "—"
            lines.append(f"| {tr.name} | {c.model} | {c.in_tok_base} | {c.in_tok_iceni} | {dstr} "
                         f"| {'✓' if c.fmt >= 1 else '·'} | {sem} |")
    lines.append("")

    if meta["executed"]:
        lines.append("## Execution (live)")
        lines.append("")
        lines.append("| task | model | out base→iceni | cost base→iceni ($) | latency (s) | quality 0-100 |")
        lines.append("|---|---|--:|--:|--:|--:|")
        for tr in results:
            for c in tr.cells:
                q = (f"{c.quality_base:.0f}→{c.quality_iceni:.0f}"
                     if c.quality_base is not None and c.quality_iceni is not None else "—")
                lines.append(f"| {tr.name} | {c.model} | {c.out_tok_base}→{c.out_tok_iceni} "
                             f"| {c.cost_base:.5f}→{c.cost_iceni:.5f} "
                             f"| {c.latency_base:.2f}→{c.latency_iceni:.2f} | {q} |")
        lines.append("")

        # Cost-per-quality (GPT's key metric: pay less, get more)
        cpq_rows = [
            (c.model,
             c.quality_base / c.cost_base if c.cost_base and c.quality_base else None,
             c.quality_iceni / c.cost_iceni if c.cost_iceni and c.quality_iceni else None)
            for c in cells
            if c.quality_base and c.quality_iceni and c.cost_base and c.cost_iceni
        ]
        if cpq_rows:
            lines.append("## Cost per Quality Point (GPT's metric)")
            lines.append("")
            lines.append("Quality points per dollar — higher = better value. "
                         "ICENI wins if it delivers more quality for the same cost even if tokens go up.")
            lines.append("")
            lines.append("| model | quality/$ base | quality/$ iceni | Δ |")
            lines.append("|---|--:|--:|--:|")
            by_model: dict[str, list] = {}
            for model, base_cpq, iceni_cpq in cpq_rows:
                by_model.setdefault(model, []).append((base_cpq, iceni_cpq))
            for model, pairs in sorted(by_model.items()):
                valid = [(b, i) for b, i in pairs if b and i]
                if not valid:
                    continue
                avg_b = statistics.mean(b for b, _ in valid)
                avg_i = statistics.mean(i for _, i in valid)
                delta = _pct(avg_b, avg_i)
                delta_str = f"{-delta*100:+.0f}%" if delta is not None else "n/a"
                lines.append(f"| {model} | {avg_b:,.0f} | {avg_i:,.0f} | {delta_str} |")
            lines.append("")

    # ---- aggregates + verdict ----
    in_deltas = [d for c in cells if (d := _pct(c.in_tok_base, c.in_tok_iceni)) is not None]
    fmt_ok = statistics.mean([c.fmt for c in cells]) if cells else 0.0
    sem_vals = [c.semantic for c in cells if c.semantic is not None]

    lines.append("## Verdict")
    lines.append("")
    avg_in_delta = statistics.mean(in_deltas) if in_deltas else None
    if avg_in_delta is not None:
        lines.append(f"- Input-token Δ (ICENI vs baseline): **{avg_in_delta*100:+.0f}%** "
                     f"(positive = ICENI uses fewer)")
    lines.append(f"- Format-appropriateness: **{fmt_ok*100:.0f}%** of renders match the model's preferred shape")
    if sem_vals:
        lines.append(f"- Semantic preservation (render↔baseline): **{statistics.mean(sem_vals):.2f}** "
                     f"(target ≥ 0.90)")

    proceed = False
    if meta["executed"]:
        cost_deltas = [d for c in cells if (d := _pct(c.cost_base, c.cost_iceni)) is not None]
        speed_deltas = [d for c in cells if (d := _pct(c.latency_base, c.latency_iceni)) is not None]
        if cost_deltas:
            lines.append(f"- Cost Δ: **{statistics.mean(cost_deltas)*100:+.0f}%**")
        if speed_deltas:
            lines.append(f"- Speed Δ: **{statistics.mean(speed_deltas)*100:+.0f}%**")
        iceni_q = [c.quality_iceni for c in cells if c.quality_iceni is not None]
        if len(iceni_q) > 1:
            lines.append(f"- Cross-model quality spread (ICENI): **±{statistics.pstdev(iceni_q):.1f}** "
                         f"(lower = more consistent across models)")
        tok_hit = avg_in_delta is not None and avg_in_delta >= THRESH["token_reduction"]
        cost_hit = bool(cost_deltas and statistics.mean(cost_deltas) >= THRESH["token_reduction"])
        speed_hit = bool(speed_deltas and statistics.mean(speed_deltas) >= THRESH["speed_gain"])
        proceed = tok_hit or cost_hit or speed_hit
        lines.append("")
        lines.append(f"### → {'PROCEED' if proceed else 'WEAK / PIVOT'} "
                     f"(GPT thresholds: ≥20% token or cost, or ≥25% speed)")
    else:
        lines.append("")
        lines.append("### → run with `--execute` (+ API keys) for the cost/quality/speed verdict")

    lines.append("")
    lines.append("_Honesty note: Claude XML renders cost more input tokens but may return higher quality. "
                 "The definitive metric is cost-per-quality-point, not raw token count._")
    lines.append("")

    # Swarm projection (always shown — pure math, no API calls)
    swarm_lines = _swarm_projection(results, pricing)
    if swarm_lines:
        lines.extend(swarm_lines)

    return "\n".join(lines)
