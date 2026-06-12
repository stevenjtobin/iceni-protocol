# ICENI Protocol

**Save your best AI instructions once. Use them everywhere — in one word.**

ICENI is a reusable-workflow system for AI assistants. You write an expert prompt once, give it a name (`review`, `security-audit`, `refactor`), and from then on that word is all you type. ICENI renders the right calibrated prompt for whichever model you're using — Claude, ChatGPT, or Kimi — and produces structured, consistent output every time.

It won't make the model smarter. It will save you from retyping the same 60-word instruction block a hundred times, get the answer right first time (no re-runs), and produce output that other tools and agents can parse reliably.

---

## Who is this for?

| Person | What ICENI does for them |
|---|---|
| **Developer** | `review`, `refactor`, `test-gen`, `security-audit` in every project — same structured output every time |
| **Writer / marketer** | `blog-outline`, `email-reply`, `summarize` with your house style baked in |
| **Analyst / researcher** | `research-brief`, `compare`, `decisions` with consistent format to feed into pipelines |
| **Team lead** | Export a signed alias, the whole team imports it — one standard, signature-verified |
| **Claude Code user** | `/iceni` inside Claude Code runs your full workflow library in the terminal |

---

## Which AI platforms are tested and working?

| Platform | Integration | Status |
|---|---|---|
| **Claude Desktop** | MCP server — workflows appear under `+` → Connectors → `iceni` | ✅ Tested |
| **Claude Code** | Skill (`/iceni`) + CLI via `python -m iceni` | ✅ Tested |
| **ChatGPT** | CLI with `--model gpt` (OpenAI API key required) | ✅ Tested |
| **Kimi (Moonshot)** | CLI with `--model kimi` (Moonshot API key required) | ✅ Tested |
| **Any OpenAI-compatible API** | Set `OPENAI_API_KEY` + base URL | Works offline, render only |
| **No AI at all** | `--preview` mode renders the prompt without calling any model | ✅ Works offline |

The core features — create, list, show, export, import — work **completely offline with no API keys**.

---

## Quickstart (5 minutes, no API key needed)

### Prerequisites

- Python 3.10+
- pip
- Claude Desktop (for the `+` → Connectors integration) **or** Claude Code (for `/iceni`)

### Step 1 — Install

```bash
git clone https://github.com/stevenjtobin/iceni-protocol.git
cd iceni-protocol
pip install -e .
```

Verify it works:
```bash
iceni --version
iceni doctor
```

### Step 2 — Initialise your library

```bash
iceni init
```

This creates a local store in `~/.iceni/` (never committed, never shared).

### Step 3 — Install a workflow pack

```bash
iceni pack list              # see all 19 packs (208 workflows)
iceni pack install code-quality-plus   # install one pack
iceni pack install all       # or install everything at once
iceni list                   # confirm they're there
```

### Step 4 — Connect to Claude Desktop (optional)

```bash
iceni connect-desktop
```

Restart Claude Desktop → click **`+`** (bottom-left) → **Connectors** → **`iceni`**. Your workflows appear. Pick one, paste your content, done.

> **Can't find it?** Make sure you restarted Claude Desktop after running `connect-desktop`. The `+` button is in the chat input bar, not the sidebar.

### Step 5 — Try your first workflow

**In the terminal (no AI key needed — preview only):**
```bash
iceni run review examples/buggy_example.py --preview --model claude
```

**In Claude Desktop:** Click `+` → Connectors → `iceni` → choose `security-audit` → paste any code.

**In Claude Code:** Type `/iceni` and pick a workflow from the menu.

---

## The 208-workflow library

ICENI ships with 19 themed packs covering the most common AI tasks:

**Code packs** — `code-quality-plus`, `testing`, `refactoring`, `documentation`, `debugging`, `git-workflow`, `architecture-design`, `devops-deploy`, `lang-tools`

**Chat / writing packs** — `writing-pro`, `email-comms`, `research-analysis`, `business-strategy`, `marketing-content`, `learning-explain`, `decisions-planning`, `document-data`

See the full list: [`library/CATALOG.md`](library/CATALOG.md)

```bash
iceni pack list              # browse all packs
iceni pack install testing   # install one
iceni list                   # see your installed workflows
iceni show review            # inspect a workflow + signature
```

---

## Create your own workflow

```bash
iceni create my-brief \
  --goal "Write a one-page project brief from bullet points." \
  --input "{{notes}}" \
  --constraint "plain English, no jargon" \
  --output-format "Problem / Approach / Outcome / Next steps" \
  --hint "claude=use XML sections" \
  --hint "gpt=use markdown headers"
```

Each workflow gets an Ed25519 signature. When you share it, the recipient's `iceni import` verifies the signature before installing — tampered aliases are rejected.

---

## Share with your team

```bash
iceni export review            # → review.iceni  (signed, portable)
# send review.iceni to a colleague
iceni import review.iceni      # verified + installed on their machine
```

---

## Key commands

```bash
iceni list                     # all installed workflows
iceni show <name>              # prompt text + signature status
iceni run <name> <file>        # render prompt for a file (--preview skips the API call)
iceni compare <name>           # side-by-side Claude / GPT / Kimi renderings
iceni stats                    # your accumulated savings (words saved, re-runs avoided)
iceni pack list                # browse all 19 packs
iceni pack install <name>      # add a pack
iceni export <name>            # portable signed alias file
iceni import <name>.iceni      # verified install from a file
iceni connect-desktop          # wire into Claude Desktop automatically
iceni mcp                      # start the MCP stdio server manually (for debugging)
iceni doctor                   # check config + which model keys are set
```

---

## Using API keys (live model calls)

ICENI works **without any API key** in `--preview` mode. To call models directly:

```bash
# Windows PowerShell
$env:ANTHROPIC_API_KEY = "sk-ant-..."
$env:OPENAI_API_KEY    = "sk-..."
$env:MOONSHOT_API_KEY  = "..."

iceni run review examples/buggy_example.py --execute --model claude
iceni compare review --execute
```

```bash
# macOS / Linux
export ANTHROPIC_API_KEY="sk-ant-..."
iceni run review examples/buggy_example.py --execute --model claude
```

---

## How the trust chain works

Every workflow carries a cryptographic signature so you always know who created it and that it hasn't been modified:

```
"review"  →  local petname  →  aip:key:ed25519:…  →  signed intent (sha256)  →  per-model render
(human)      (anti-mimicry)     (identity)             (Ed25519)                  (Claude/GPT/Kimi)
```

The human-readable name is **not** the trust anchor. Trust rides on the Ed25519 key. A tampered alias will be rejected at `iceni import`.

---

## Benchmark results (honest)

We ran a 10-task offline benchmark against plain prompts. Key findings:

- **100% structured output** (ICENI) vs **0%** (plain prompts) on the Structure-Fidelity Score test
- **+7 points functional quality** on real code tasks (320–577 token inputs)
- **−3 to −6 points on tiny inputs** (<200 tokens) — ICENI's instruction overhead outweighs the benefit
- **Average delta: +1.55** — the real value is consistency and re-runs avoided, not a quality leap

Full results: [`benchmarks/report-10task-offline.md`](benchmarks/report-10task-offline.md)

---

## Project layout

```
src/iceni/
  cli.py            all commands
  mcp_server.py     Claude Desktop / MCP integration
  calibration.py    per-model prompt renderer (Claude / GPT / Kimi)
  discovery.py      auto-discover recurring prompts from conversation logs
  feedback.py       outcome tracking + workflow evolution
  trust/            Ed25519 signing, identity, keystore
  store/            SQLite alias store + migrations
  providers/        Anthropic · OpenAI · Kimi (openai-compat)
  packs/            19 JSON packs, 208 workflows
benchmarks/         10-task benchmark, SFS test, offline results
examples/           intentionally-buggy demo code (for testing security-audit)
library/            CATALOG.md + pack builder
tests/              smoke, share, router, feedback, packs
site/               landing page (index.html)
```

---

## Roadmap

- [x] Core CLI (`init`, `create`, `list`, `show`, `run`, `compare`, `export`, `import`)
- [x] Trust chain (Ed25519 signatures, content-addressed intents)
- [x] MCP server (Claude Desktop `+` → Connectors integration)
- [x] Claude Code skill (`/iceni`)
- [x] 208-workflow library (19 packs)
- [x] Auto-discovery (cluster recurring prompts from conversation logs)
- [x] Outcome tracking + usage stats
- [ ] PyPI release (`pip install iceni`)
- [ ] GPT / Kimi auto-calibration from live execution feedback
- [ ] Drift detection (alert when a workflow's output style shifts)
- [ ] Pack marketplace

---

## License

MIT — see [LICENSE](LICENSE)

---

## Contributing

Issues and PRs welcome. If you build a workflow pack worth sharing, open a PR against `library/build_library.py`.
