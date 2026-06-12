# Free subscription test suite — 10 task types, V1 rubric

**Design (GPT + Kimi agreed):** vary *task type* across all 10 aliases at realistic
input sizes (238–756 tok); hold the model constant (Claude, via subscription — £0);
score each ICENI-vs-baseline pair on Kimi's V1 rubric. Blind execution: each pair was
run by an isolated agent that answered both prompts independently.

**Scoring** (self-judged by Claude — see bias caveat): functional 40 / token 30 /
format 15 / semantic 15.

## Results

| # | Alias | Input tok | Overhead | ICENI | Baseline | Δ | Winner |
|---|-------|----------:|---------:|------:|---------:|----:|--------|
| t01 | review | 383 | +20.4% | 94 | 90 | +4 | ICENI |
| t02 | test-gen | 467 | +18.9% | 94 | 92 | +2 | ICENI |
| t03 | refactor | 476 | +18.3% | 94 | 92 | +2 | ICENI |
| t04 | docstring | 580 | +14.5% | 96.5 | 89 | +7.5 | ICENI |
| t05 | error-explain | 418 | +20.4% | 93 | 92 | +1 | ICENI |
| t06 | deploy-check | 327 | +26.3% | 92 | 91 | +1 | ICENI |
| t07 | dependency-audit | 238 | +38.4% | 89 | 95 | −6 | **Baseline** |
| t08 | api-review | 486 | +17.5% | 95 | 92 | +3 | ICENI |
| t09 | commit-message | 756 | +11.9% | 93 | 95 | −2 | **Baseline** |
| t10 | security-audit | 454 | +19.6% | 95 | 92 | +3 | ICENI |

**ICENI wins 8/10.** Average ICENI 93.6 vs baseline 92.0 — **margin only +1.55**.

## Gate check (Kimi's stop rule)

| Criterion | Threshold | Actual | Pass? |
|-----------|-----------|--------|-------|
| Win rate | ≥70% (7/10) | 80% (8/10) | ✅ |
| No alias baseline-wins by >5pts | none | dependency-audit −6 | ❌ |
| Avg V1 advantage | +5 to +10 | +1.55 | ❌ |

Win-count gate passes; the two quality gates do **not**. This is a *mixed* result.

## The load-bearing finding

ICENI's win is almost entirely the **format dimension** (15% weight: XML for Claude =
15, baseline prose = 8–9). On **functional quality** (40% weight) ICENI and baseline are
a near-tie — unsurprising, since the same model answers both. So the honest reading:

> ICENI does not make Claude *smarter*. It makes Claude's output **structured and
> machine-parseable at near-identical functional quality** and a modest token premium.

That is exactly the property a **swarm** (agent-to-agent routing/parsing) needs, and
exactly the property a **single human reader** does not (prose is arguably more readable).
The value case is inter-agent, not single-shot quality — consistent with the 46% routing
compression projection, not with "better answers."

## Weak task types (scope signal)

- **dependency-audit (−6):** input is token-light relative to the ~98-tok instruction
  block (+38% overhead even at 238 tok), and the requested artifact is literally a "risk
  table" — which baseline produces natively, so XML calibration adds little. Loses on
  token, ties on everything else.
- **commit-message (−2):** confirmed low structure-sensitivity (Kimi predicted this). A
  commit message is plain text; neither side uses XML, so ICENI's format edge vanishes and
  the (small) token overhead tips it to baseline.

ICENI's strength concentrates in **structure-heavy** tasks: docstring (+7.5), review (+4),
api-review (+3), security-audit (+3). It is weak-to-neutral on **table/plain-text** tasks.

## Recommendation

PROCEED to the £0.50 Claude-only `--execute --judge` run — but specifically to test the
above hypothesis: an *independent* judge scoring **task accomplishment** (not format) will
likely compress the +1.55 margin further, possibly to a tie. If the judge confirms ICENI
holds even a small functional edge, the swarm value case stands. If it shows a pure tie on
function, ICENI should be positioned honestly as a **structuring/transport layer**, not a
quality multiplier — and its scope narrowed to structure-heavy task types.
