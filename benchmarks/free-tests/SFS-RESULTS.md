# Structure Fidelity Score (SFS) — the parse-success test

**Why this test:** GPT + Kimi both concluded the quality judge measures the wrong thing.
ICENI's claim is *inter-agent machine-readability*, not better answers. So we measure
whether a downstream agent can recover structured fields from ICENI XML vs baseline prose.
Two layers: deterministic (code, free) and LLM-parser (realistic swarm consumer).

5 finding-list tasks (review, deploy-check, dependency-audit, api-review, security-audit).
Outputs regenerated blind to disk, then copied to neutrally-named files (`p01`–`p10`) so the
parser agents could not tell which variant they were reading.

## Layer 1 — deterministic parse (zero LLM, `benchmarks/sfs_test.py`)

Three generic parser strategies (XML / markdown-table / prose-regex) applied to each output;
"det-parseable" = code can split it into discrete records without any model call.

| Task | ICENI | Baseline |
|------|-------|----------|
| review | ✅ XML | ❌ prose |
| deploy-check | ✅ XML | ❌ prose |
| dependency-audit | ✅ XML | ❌ prose* |
| api-review | ✅ XML | ❌ prose |
| security-audit | ✅ XML | ❌ prose |
| **Total** | **5/5 parseable for free** | **0/5** |

\* *In an earlier blind run the same dependency-audit baseline came out as a markdown table
(parseable); this run it came out as prose (not). Baseline shape is **non-deterministic** —
a consumer cannot code against it. ICENI is XML every time.*

## Layer 2 — LLM parser (the realistic swarm consumer)

10 blind agents, neutral filenames, each told it is a downstream agent extracting findings
to a strict JSON schema {severity, location, description, fix}. Metric = fraction of records
with all four fields populated.

| Task | ICENI fields | Baseline fields |
|------|-------------:|----------------:|
| review | 10/10 | 12/12 |
| deploy-check | 15/15 | 11/13 |
| dependency-audit | 36/36 | 33/33 |
| api-review | 10/10 | 9/9 |
| security-audit | 7/7 | 6/7 |
| **Total** | **78/78 = 100%** | **71/74 = 95.9%** |

## What this proves (and disproves)

1. **When the consumer is an LLM, prose parses almost as well as XML** — 96% vs 100%. An LLM
   is good at reading prose. ICENI's accuracy edge here is small (+4pts). This *disproves* any
   "ICENI is required for parseable swarms" overclaim.
2. **When the consumer is code, ICENI parses for free (5/5) and baseline does not (0/5).** This
   is the real, measured value: baseline forces an **LLM parse call at every hop**; ICENI lets
   the next agent extract fields deterministically at zero cost — and guarantees a stable shape,
   which baseline does not (it varied table↔prose across runs).

## The honest one-line value case

> ICENI doesn't make answers better and barely improves LLM-parsing accuracy. Its measured
> value is **cost and determinism**: downstream agents parse ICENI output for free with a
> guaranteed schema, instead of paying an LLM call per hop to parse unstructured prose of
> non-deterministic shape. That compounds at swarm scale (N agents × M messages) — the same
> place the 46% routing-compression saving lives.

This is a transport/cost argument, not an intelligence argument — and now it has numbers.
