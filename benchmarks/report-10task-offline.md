# ICENI Benchmark Report

Tasks: 10 · Models: kimi, claude, gpt · Mode: offline (input-side only)

## Input-side (offline-measurable)

| task | model | base tok | iceni tok | Δtok | format | semantic |
|---|---|--:|--:|--:|:--:|:--:|
| code-review | kimi | 130 | 126 | +3% | ✓ | — |
| code-review | claude | 130 | 167 | -28% | ✓ | — |
| code-review | gpt | 130 | 136 | -5% | ✓ | — |
| test-gen | kimi | 125 | 115 | +8% | ✓ | — |
| test-gen | claude | 125 | 164 | -31% | ✓ | — |
| test-gen | gpt | 125 | 126 | -1% | ✓ | — |
| refactor | kimi | 118 | 125 | -6% | ✓ | — |
| refactor | claude | 118 | 170 | -44% | ✓ | — |
| refactor | gpt | 118 | 132 | -12% | ✓ | — |
| docstring | kimi | 124 | 123 | +1% | ✓ | — |
| docstring | claude | 124 | 163 | -31% | ✓ | — |
| docstring | gpt | 124 | 130 | -5% | ✓ | — |
| error-explain | kimi | 96 | 110 | -15% | ✓ | — |
| error-explain | claude | 96 | 154 | -60% | ✓ | — |
| error-explain | gpt | 96 | 120 | -25% | ✓ | — |
| deploy-check | kimi | 132 | 132 | +0% | ✓ | — |
| deploy-check | claude | 132 | 170 | -29% | ✓ | — |
| deploy-check | gpt | 132 | 143 | -8% | ✓ | — |
| dependency-audit | kimi | 115 | 113 | +2% | ✓ | — |
| dependency-audit | claude | 115 | 159 | -38% | ✓ | — |
| dependency-audit | gpt | 115 | 124 | -8% | ✓ | — |
| api-review | kimi | 118 | 120 | -2% | ✓ | — |
| api-review | claude | 118 | 161 | -36% | ✓ | — |
| api-review | gpt | 118 | 132 | -12% | ✓ | — |
| commit-message | kimi | 206 | 193 | +6% | ✓ | — |
| commit-message | claude | 206 | 238 | -16% | ✓ | — |
| commit-message | gpt | 206 | 202 | +2% | ✓ | — |
| security-audit | kimi | 133 | 122 | +8% | ✓ | — |
| security-audit | claude | 133 | 166 | -25% | ✓ | — |
| security-audit | gpt | 133 | 134 | -1% | ✓ | — |

## Verdict

- Input-token Δ (ICENI vs baseline): **-14%** (positive = ICENI uses fewer)
- Format-appropriateness: **100%** of renders match the model's preferred shape

### → run with `--execute` (+ API keys) for the cost/quality/speed verdict

_Honesty note: Claude XML renders cost more input tokens but may return higher quality. The definitive metric is cost-per-quality-point, not raw token count._

## Swarm Scale Projection

Per-hop: traditional relays **130 tokens** · ICENI relays **70 tokens** (alias ≈3 tok + raw input) → **46% compression** of inter-agent messages.

| agents | msgs/agent/day | trad routing tok | ICENI routing tok | savings |
|--:|--:|--:|--:|--:|
| 5 | 100 | 64,850 | 35,000 | 46% |
| 5 | 1000 | 648,500 | 350,000 | 46% |
| 10 | 100 | 129,700 | 70,000 | 46% |
| 10 | 1000 | 1,297,000 | 700,000 | 46% |
| 25 | 100 | 324,250 | 175,000 | 46% |
| 25 | 1000 | 3,242,500 | 1,750,000 | 46% |
| 50 | 100 | 648,500 | 350,000 | 46% |
| 50 | 1000 | 6,485,000 | 3,500,000 | 46% |
| 100 | 100 | 1,297,000 | 700,000 | 46% |
| 100 | 1000 | 12,970,000 | 7,000,000 | 46% |

_Note: routing tokens ≠ execution tokens. Each agent still calls the model with_
_the full rendered prompt — this projection measures only what passes between agents._