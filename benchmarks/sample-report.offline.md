# ICENI Benchmark Report

Tasks: 3 · Models: kimi, claude, gpt · Mode: offline (input-side only)

## Input-side (offline-measurable)

| task | model | base tok | iceni tok | Δtok | format | semantic |
|---|---|--:|--:|--:|:--:|:--:|
| review | kimi | 130 | 103 | +21% | ✓ | — |
| review | claude | 130 | 138 | -6% | ✓ | — |
| review | gpt | 130 | 113 | +13% | ✓ | — |
| testgen | kimi | 124 | 100 | +19% | ✓ | — |
| testgen | claude | 124 | 136 | -10% | ✓ | — |
| testgen | gpt | 124 | 109 | +12% | ✓ | — |
| security-audit | kimi | 133 | 106 | +20% | ✓ | — |
| security-audit | claude | 133 | 140 | -5% | ✓ | — |
| security-audit | gpt | 133 | 112 | +16% | ✓ | — |

## Verdict

- Input-token Δ (ICENI vs baseline): **+9%** (positive = ICENI uses fewer)
- Format-appropriateness: **100%** of renders match the model's preferred shape

### → run with `--execute` (+ API keys) for the cost/quality/speed verdict

_Honesty note: per-call input tokens may not drop — calibration can add structure. The stronger single-user signals are cross-model consistency and cost-per-quality._