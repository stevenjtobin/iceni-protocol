# iceni — your best prompts, one word away

**Save your best AI instructions once and use them everywhere.** ICENI turns the prompts you retype constantly into one-word commands (`/review`, `/security-audit`) that produce structured, consistent output — calibrated per model, on Claude, GPT, or Kimi.

The honest pitch: it won't make the model smarter (+1.55 avg on our own benchmark). It saves you the ~60-word instruction block every single time, gets the answer right the *first* time (re-runs avoided is the real cost saving), and produces output other tools — and other agents — can parse deterministically (100% vs 0% in the SFS test). Full evidence: `site/index.html`.

## 60-second start

```bash
pip install -e .                   # 1. install (from this dir; PyPI later)
iceni connect-desktop              # 2. wire into Claude Desktop automatically
iceni pack install code-quality   # 3. five proven aliases, one command
```
Restart Claude Desktop → type **`/iceni`** → your workflows appear in one branded menu. Pick by name or number, paste your content, done. The top three workflows (`/review`, `/security-audit`, `/api-review`) also work directly for one-shot use. No API keys needed.

`iceni pack list` shows what's available. `iceni stats` shows your accumulated savings.

## Share an alias with your team

```bash
iceni export review            # → review.iceni  (signed, portable)
iceni import review.iceni      # on their machine — signature verified before install
```
One developer's `review` becomes the team's standard. The Ed25519 signature travels with the file, so a tampered alias is rejected at import — this is the trust model doing its job across machines.

## The trust chain (for the technical reader)

```
"review"  →  local petname  →  aip:key:ed25519:…  →  signed, content-addressed intent  →  per-model render
(human)      (anti-mimicry)     (anti-forgery)         (sha256, Ed25519)                   (Claude/GPT/Kimi)
```
The human-readable name is **not** the trust anchor. Trust rides on the Ed25519 signature over a content-addressed intent.

## Install (development)

```bash
cd iceni
pip install -e .            # core (CLI + crypto) — runs offline
pip install -e ".[models]"  # add to call live Claude / GPT / Kimi
pip install -e ".[mcp]"     # Claude Desktop integration
```

## Use (works offline, no API keys)

```bash
iceni init
iceni create review \
  --goal "Review this code for bugs, edge cases, and security issues." \
  --input "{{code}}" --constraint "be concise" --constraint "cite line numbers" \
  --output-format "issues, severity" \
  --hint "claude=use XML tags" --hint "gpt=prioritized markdown list"

iceni list
iceni show review                      # intent + signature check + per-model renderings
iceni compare review                   # side-by-side Kimi/Claude/GPT renderings + token estimates
iceni run review examples/buggy_example.py --preview --model kimi
iceni benchmark benchmarks/tasks.10-task.json  # 10-task V1 benchmark (Kimi's rubric)
iceni benchmark benchmarks/tasks.sample.json   # 3-task sample (quick check)
iceni doctor                           # config + which model keys are set
```

To call live models, set keys and add `--execute`:
```bash
$env:ANTHROPIC_API_KEY="…"; $env:OPENAI_API_KEY="…"; $env:MOONSHOT_API_KEY="…"
iceni compare review --execute         # logs tokens/cost per model → value-case V1/V2
iceni benchmark benchmarks/tasks.sample.json --execute --judge claude --report out.md
                                       # full cost/quality/speed verdict vs thresholds
```

The benchmark is **the experiment** (see `../build-plan/benchmark-spec.md`): does ICENI beat a plain prompt?

Offline 10-task run (`benchmarks/report-10task-offline.md`): **100% format-fit** across all 30 task-model pairs; **46% inter-agent routing compression** (swarm projection). Input-token delta is dominated by Claude's XML overhead for small inputs — the real signal is **cost-per-quality** from `--execute --judge`. Kimi pricing corrected to $1.5/$7.5 / Mtok (verify at platform.moonshot.cn).

## Layout

```
src/iceni/
  cli.py            commands: init create list show run compare evolve benchmark discover mcp doctor
  config.py         ~/.iceni layout + model config (TOML)
  intent.py         model-agnostic intent (JSON) + content hash    [OQ4=A]
  calibration.py    offline per-model renderer (Claude/GPT/Kimi)
  discovery.py      Phase II: cluster recurring prompts → candidate aliases  [OQ3=HDBSCAN+binary]
  mcp_server.py     expose aliases as Claude Desktop prompts (no API key)
  trust/            sign.py · identity.py (aip:key:ed25519) · keystore.py   [OQ1=C spine]
  store/            db.py (migrations) · aliases.py (the trust dance)
  providers/        base · anthropic (Claude) · openai_compat (GPT + Kimi)
  benchmark.py      value-case harness: tokens/cost/latency/quality, baseline vs ICENI
  sql/0001_init.sql the schema
benchmarks/         tasks.10-task.json · sfs_test.py (Structure Fidelity) · free-tests/
tests/              test_smoke.py (trust+render+hash+benchmark) · test_discovery.py (Phase II)
```

## Phase II — auto-discovery (built)

```bash
iceni discover                         # cluster recurring prompts in ~/.claude/projects
iceni discover --min-cluster-size 4    # raise for higher precision
iceni discover --create                # mint signed aliases from the candidates
```

Two-stage precision over real logs: (1) noise filters drop harness wrappers, injected
image blocks, and pasted terminal sessions; (2) a **cohesion gate** (mean-to-centroid
cosine) rejects HDBSCAN's low-cohesion blobs. On an 803-prompt corpus this took raw
clusters from ~15% useful to all-survivors-genuine-near-duplicates (cohesion ≥0.88),
including a cross-project recurring intent. Discovery only *proposes* — nothing is signed
until you accept, then the normal trust spine mints identity + signs the intent. Cold-start
backend is TF-IDF + HDBSCAN (no torch); sentence-transformers is a later upgrade behind `[discovery]`.

## What's next (per build plan)

Phase III live LLM calibration (fill per-model style hints from real execution feedback),
Phase IV drift (directional metric → ADWIN) + evolution. Phase V MCP server is **done**
(`iceni mcp` → Claude Desktop). Decisions locked by unanimous vote — see `../build-plan/open-decisions.md`.
