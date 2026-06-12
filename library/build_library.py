"""Build the ICENI starter library — 100 chat + 100 Claude Code workflows.

Each use case becomes a real, signed-on-install alias. Goals + output shapes are
written here; per-model style hints get a sensible default per pack kind (refine
the winners later with `iceni calibrate <alias> --apply`). Run:

    python library/build_library.py

Writes one pack JSON per theme into src/iceni/packs/ and a human-readable
library/CATALOG.md. Install any pack with:  iceni pack install <pack-name>
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKS_DIR = ROOT / "src" / "iceni" / "packs"
CATALOG = ROOT / "library" / "CATALOG.md"

HINTS = {
    "prose": {"claude": "clear sections, XML tags where structure aids parsing",
              "gpt": "clean markdown with headers and bullets",
              "kimi": "concise, no preamble"},
    "table": {"claude": "XML rows with attributes",
              "gpt": "markdown table",
              "kimi": "compact list, highest-priority first"},
    "code": {"claude": "XML-tagged sections around fenced code blocks",
             "gpt": "markdown with fenced code blocks",
             "kimi": "code first, minimal prose"},
}
CONSTRAINTS = {
    "prose": ["be specific and actionable", "no filler or preamble"],
    "table": ["one row per item", "rank by importance"],
    "code": ["be concise", "cite line numbers where relevant"],
}

# pack = (name, description, kind, input_placeholder, [(petname, goal, output), ...])
CHAT_PACKS = [
    ("writing-pro", "Polish and reshape any piece of writing.", "prose", "{{input}}", [
        ("proofread", "Proofread this text for grammar, spelling, punctuation and clarity.", "corrected text then a change list"),
        ("rewrite-tone", "Rewrite this text in a specified tone (ask which if unclear).", "rewritten text"),
        ("summarize", "Summarize this text.", "tight summary, 3-5 sentences"),
        ("expand", "Expand this terse note into full, well-structured prose.", "expanded text"),
        ("simplify", "Rewrite this so a non-expert understands it.", "plain-English version"),
        ("headline", "Write 8 headline options for this.", "numbered headline list"),
        ("hook", "Write 5 opening hooks that make a reader keep going.", "numbered hooks"),
        ("tighten", "Cut this text by ~40% without losing meaning.", "tightened text + word-count delta"),
        ("paraphrase", "Paraphrase this to avoid repetition while keeping meaning.", "paraphrased text"),
        ("active-voice", "Convert passive constructions to active voice.", "revised text"),
        ("bulletize", "Turn this prose into scannable bullet points.", "bulleted list"),
        ("title-ideas", "Generate 10 title ideas for this piece.", "numbered titles"),
        ("grammar-fix", "Fix only grammar and punctuation, change nothing else.", "corrected text"),
        ("plain-english", "Remove jargon and corporate-speak; say it plainly.", "de-jargoned text"),
    ]),
    ("email-comms", "Draft and sharpen professional messages.", "prose", "{{input}}", [
        ("email-reply", "Draft a reply to this email.", "ready-to-send reply"),
        ("follow-up", "Write a polite follow-up to a message that got no response.", "short follow-up"),
        ("cold-email", "Write a concise cold outreach email for this goal.", "subject + body"),
        ("decline", "Politely decline this request while keeping the relationship.", "declining reply"),
        ("apology-email", "Write a sincere, non-grovelling apology email.", "apology email"),
        ("intro-email", "Write a warm double-opt-in introduction email.", "intro email"),
        ("nudge", "Write a friendly nudge that creates urgency without pressure.", "short nudge"),
        ("thank-you", "Write a specific, genuine thank-you message.", "thank-you note"),
        ("status-update", "Turn these notes into a crisp stakeholder status update.", "status update"),
        ("ooo", "Write an out-of-office auto-reply.", "OOO message"),
        ("negotiation-email", "Draft a firm-but-fair negotiation email.", "negotiation email"),
        ("escalation-email", "Write a measured escalation email stating impact and ask.", "escalation email"),
    ]),
    ("research-analysis", "Think through a topic rigorously.", "prose", "{{input}}", [
        ("compare", "Compare these options across the dimensions that matter.", "comparison table + recommendation"),
        ("pros-cons", "List the strongest pros and cons of this.", "pros/cons lists + verdict"),
        ("eli5", "Explain this like I'm five.", "simple explanation"),
        ("steelman", "Make the strongest possible case for this position.", "steelmanned argument"),
        ("devils-advocate", "Argue the opposite of this to stress-test it.", "counter-arguments"),
        ("assumptions", "Surface the hidden assumptions in this.", "assumption list with risk"),
        ("second-order", "Trace the second- and third-order consequences of this.", "consequence chain"),
        ("key-takeaways", "Extract the key takeaways from this.", "numbered takeaways"),
        ("gap-analysis", "Find what's missing or unaddressed here.", "gap list"),
        ("fact-frame", "Separate the claims here into facts, opinions, and unknowns.", "three grouped lists"),
        ("summarize-source", "Summarize this source and note its likely bias.", "summary + bias note"),
        ("contrarian", "Give the smart contrarian take on this.", "contrarian analysis"),
        ("swot-quick", "Do a quick SWOT on this.", "SWOT quadrants"),
    ]),
    ("business-strategy", "Sharpen the commercial thinking.", "prose", "{{input}}", [
        ("business-model", "Sketch a business model for this idea.", "model summary"),
        ("pricing-tiers", "Propose pricing tiers for this product.", "tier table with rationale"),
        ("competitor-scan", "List likely competitors and how to differentiate.", "competitor list + edge"),
        ("elevator-pitch", "Write a 30-second elevator pitch for this.", "pitch"),
        ("value-prop", "Write a sharp value proposition for this.", "one-sentence value prop + support"),
        ("positioning", "Write a positioning statement (for X who Y, we are Z).", "positioning statement"),
        ("go-to-market", "Outline a lean go-to-market plan.", "GTM steps"),
        ("risk-register", "List the top business risks and mitigations.", "risk table"),
        ("okrs", "Draft OKRs for this goal.", "objective + 3 key results"),
        ("lean-canvas", "Fill a lean canvas for this idea.", "canvas sections"),
        ("moat-analysis", "Assess what defensible moat this could build.", "moat analysis"),
        ("persona", "Write a sharp customer persona for this.", "persona profile"),
    ]),
    ("marketing-content", "Produce on-brief marketing content.", "prose", "{{input}}", [
        ("blog-outline", "Outline an SEO-aware blog post on this.", "H2/H3 outline"),
        ("seo-brief", "Write a content brief: intent, keywords, angle, structure.", "content brief"),
        ("social-post", "Write 3 social posts for this, platform-appropriate.", "numbered posts"),
        ("ad-copy", "Write 5 ad-copy variations for this.", "numbered variations"),
        ("product-desc", "Write a benefit-led product description.", "product description"),
        ("email-campaign", "Draft a 3-email nurture sequence for this.", "3 emails"),
        ("landing-copy", "Write landing-page copy: headline, subhead, bullets, CTA.", "landing sections"),
        ("cta-ideas", "Write 10 call-to-action options.", "numbered CTAs"),
        ("content-calendar", "Draft a 2-week content calendar for this theme.", "calendar table"),
        ("newsletter", "Draft a newsletter issue from these notes.", "newsletter draft"),
        ("video-script", "Write a 60-second video script for this.", "script with shot notes"),
        ("hashtags", "Suggest relevant, non-spammy hashtags.", "grouped hashtag list"),
        ("hook-lines", "Write 8 scroll-stopping first lines.", "numbered hooks"),
    ]),
    ("learning-explain", "Learn or teach a concept fast.", "prose", "{{input}}", [
        ("explain-concept", "Explain this concept clearly with one good example.", "explanation + example"),
        ("study-notes", "Turn this into structured study notes.", "headed notes"),
        ("quiz-me", "Write 8 quiz questions (with answers) on this.", "Q&A list"),
        ("analogy", "Give 3 analogies that make this click.", "numbered analogies"),
        ("flashcards", "Make flashcards (front/back) for this.", "card list"),
        ("prerequisites", "List what I should understand before this.", "ordered prerequisite list"),
        ("worked-example", "Show a fully worked example of this.", "step-by-step example"),
        ("common-mistakes", "List the common mistakes people make with this.", "mistake list with fixes"),
        ("mnemonic", "Create a memorable mnemonic for this.", "mnemonic + how it maps"),
        ("summary-tree", "Give a hierarchical summary (topic → subpoints).", "indented tree"),
        ("teach-back", "Explain this, then ask me 3 questions to check I got it.", "explanation + questions"),
        ("glossary-build", "Build a glossary of the key terms here.", "term: definition list"),
    ]),
    ("decisions-planning", "Decide and plan with structure.", "table", "{{input}}", [
        ("decision-matrix", "Build a weighted decision matrix for these options.", "scored matrix + winner"),
        ("weekly-plan", "Turn these goals into a realistic weekly plan.", "day-by-day plan"),
        ("prioritize", "Prioritize these items (impact vs effort).", "ranked list with reasoning"),
        ("risk-list", "List the risks here with likelihood and mitigation.", "risk table"),
        ("checklist", "Turn this process into a checklist.", "checklist"),
        ("meeting-agenda", "Draft a tight, timeboxed meeting agenda.", "agenda with times"),
        ("retro", "Run a retro on this: went well / didn't / try next.", "three lists"),
        ("next-actions", "Extract concrete next actions with owners.", "action list"),
        ("mind-map", "Outline a mind map for this topic.", "indented branches"),
        ("goal-breakdown", "Break this goal into milestones and tasks.", "milestone tree"),
        ("timeboxing", "Timebox these tasks into a focused day.", "schedule blocks"),
        ("tradeoff-table", "Lay out the tradeoffs of this decision.", "tradeoff table"),
    ]),
    ("document-data", "Wrangle documents and messy text.", "table", "{{input}}", [
        ("extract-fields", "Extract the structured fields from this text as JSON.", "JSON object"),
        ("table-from-text", "Turn this unstructured text into a table.", "markdown table"),
        ("meeting-notes", "Turn this transcript into clean meeting notes.", "notes + decisions + actions"),
        ("action-items", "Pull just the action items from this.", "owner: action list"),
        ("summarize-thread", "Summarize this long thread into the gist + decisions.", "summary + decisions"),
        ("redact-pii", "Redact personal/sensitive info from this text.", "redacted text"),
        ("translate", "Translate this, preserving tone and formatting.", "translation"),
        ("format-clean", "Clean up the formatting and whitespace of this.", "cleaned text"),
        ("faq-from-doc", "Generate an FAQ from this document.", "Q&A list"),
        ("outline-from-notes", "Turn these rough notes into a clean outline.", "outline"),
        ("compare-docs", "Compare these two texts and list the differences.", "difference list"),
        ("timeline", "Extract a chronological timeline from this.", "dated timeline"),
    ]),
]

CODE_PACKS = [
    ("code-quality-plus", "Deep code-quality reviews (the proven structure-heavy winners + more).", "code", "{{code}}", [
        ("review", "Review this code for bugs, edge cases, and security issues.", "issues grouped by severity"),
        ("security-audit", "Perform a security audit of this code.", "findings with CWE, severity, remediation"),
        ("perf-review", "Review this code for performance problems.", "hotspots ranked by impact + fixes"),
        ("complexity-check", "Flag the most complex/hard-to-follow parts.", "complexity hotspots + simplifications"),
        ("readability", "Review this for readability and naming clarity.", "readability issues + suggestions"),
        ("naming-review", "Critique the names here and suggest better ones.", "old -> new name table"),
        ("dead-code", "Find dead, unreachable, or unused code.", "dead-code list with line refs"),
        ("error-handling", "Review the error handling for gaps.", "gap list + fixes"),
        ("concurrency-review", "Review for race conditions and concurrency bugs.", "concurrency issues + fixes"),
        ("api-misuse", "Flag misuse of stdlib/framework APIs.", "misuse list + correct usage"),
        ("magic-numbers", "Find magic numbers/strings that should be named constants.", "list with suggested names"),
        ("input-validation", "Check that external inputs are validated.", "unvalidated-input list + fixes"),
    ]),
    ("testing", "Generate and review tests.", "code", "{{code}}", [
        ("test-gen", "Write unit tests for this function.", "runnable pytest code"),
        ("edge-cases", "List the edge cases this code must handle.", "edge-case list"),
        ("test-plan", "Write a test plan for this module.", "test plan"),
        ("mock-gen", "Write the mocks/fixtures needed to test this.", "mock code"),
        ("coverage-gaps", "Identify what this test suite fails to cover.", "uncovered-behavior list"),
        ("property-tests", "Suggest property-based tests for this.", "property list + hypothesis code"),
        ("fixture-gen", "Write pytest fixtures for this code's dependencies.", "fixture code"),
        ("assertion-review", "Review these assertions for weak or missing checks.", "assertion critique"),
        ("flaky-fix", "Diagnose why this test is flaky and propose a fix.", "cause + fix"),
        ("integration-test", "Write an integration test for this flow.", "integration test code"),
        ("regression-guard", "Write a regression test that pins this bug fixed.", "regression test"),
        ("test-naming", "Suggest clearer names for these tests.", "old -> new names"),
        ("snapshot-review", "Review whether snapshot testing is appropriate here.", "recommendation"),
    ]),
    ("refactoring", "Restructure code safely.", "code", "{{code}}", [
        ("refactor", "Refactor this code for clarity, safety, and maintainability.", "refactored code + change summary"),
        ("extract-function", "Extract well-named functions from this long block.", "refactored code"),
        ("rename-suggest", "Suggest clearer identifiers throughout.", "rename table"),
        ("dedupe", "Find and collapse duplicated logic.", "dedupe plan + code"),
        ("simplify-logic", "Simplify this tangled conditional logic.", "simplified code"),
        ("guard-clauses", "Rewrite nested ifs as early-return guard clauses.", "refactored code"),
        ("split-module", "Propose how to split this oversized module.", "split plan"),
        ("pure-function", "Refactor this to separate pure logic from side effects.", "refactored code"),
        ("remove-globals", "Eliminate global state here.", "refactored code"),
        ("add-types", "Add complete, accurate type hints.", "typed code"),
        ("early-return", "Flatten this with early returns.", "refactored code"),
        ("comprehension", "Replace these loops with comprehensions where it reads better.", "refactored code"),
        ("decompose", "Break this god-function into smaller pieces.", "decomposed code"),
    ]),
    ("documentation", "Write the docs nobody wants to write.", "code", "{{code}}", [
        ("docstring", "Write a Google-style docstring for this function.", "docstring only"),
        ("readme", "Draft a README for this project/module.", "README markdown"),
        ("api-docs", "Document this module's public API.", "API reference"),
        ("changelog", "Write a changelog entry for this change.", "changelog entry"),
        ("comment-why", "Add comments that explain WHY, not what.", "annotated code"),
        ("architecture-doc", "Write a short architecture overview of this.", "architecture doc"),
        ("onboarding-doc", "Write onboarding notes for a new dev on this code.", "onboarding doc"),
        ("examples-gen", "Write usage examples for this code.", "example snippets"),
        ("code-glossary", "Build a glossary of domain terms used here.", "term: meaning list"),
        ("usage-snippet", "Write a minimal copy-paste usage snippet.", "snippet"),
        ("module-header", "Write a clear module-level docstring/header.", "header docstring"),
    ]),
    ("debugging", "Find and fix what's broken.", "code", "{{input}}", [
        ("error-explain", "Explain this error and give the exact fix.", "root cause + corrected code"),
        ("stack-trace", "Read this stack trace and pinpoint the cause.", "cause + fix location"),
        ("root-cause", "Do a root-cause analysis of this bug.", "5-whys + root cause"),
        ("repro-steps", "Derive minimal reproduction steps for this bug.", "numbered repro steps"),
        ("hypotheses", "List ranked hypotheses for this bug and how to test each.", "hypothesis table"),
        ("log-points", "Suggest where to add logging to diagnose this.", "log-point list"),
        ("minimal-repro", "Reduce this to a minimal reproducible example.", "minimal code"),
        ("fix-verify", "Given this fix, list how to verify it actually works.", "verification checklist"),
        ("bisect-plan", "Plan a git bisect to find where this broke.", "bisect plan"),
        ("heisenbug", "Reason about why this bug disappears when observed.", "analysis + approach"),
        ("off-by-one", "Check this loop/index logic for off-by-one errors.", "findings + fix"),
    ]),
    ("git-workflow", "Everything around the commit.", "code", "{{input}}", [
        ("commit-message", "Write a conventional commit message for this git diff.", "subject + optional body"),
        ("pr-description", "Write a PR description from this diff.", "PR description"),
        ("review-checklist", "Generate a review checklist for this change.", "checklist"),
        ("branch-name", "Suggest a good branch name for this work.", "branch name options"),
        ("release-notes", "Write release notes from these merged changes.", "release notes"),
        ("conflict-explain", "Explain this merge conflict and how to resolve it.", "explanation + resolution"),
        ("squash-summary", "Write one clean commit message summarizing these commits.", "commit message"),
        ("gitignore-suggest", "Suggest .gitignore entries for this project.", "gitignore lines"),
        ("revert-plan", "Plan a safe revert of this change.", "revert steps"),
        ("changelog-entry", "Write a Keep-a-Changelog entry for this.", "changelog entry"),
        ("pr-title", "Write a clear, conventional PR title.", "PR title options"),
    ]),
    ("architecture-design", "Review and shape designs.", "code", "{{input}}", [
        ("design-review", "Review this design for soundness and risks.", "issues + recommendations"),
        ("api-design", "Review this API design for consistency and ergonomics.", "issue list + fixes"),
        ("schema-review", "Review this database schema.", "issues ranked by severity"),
        ("tradeoffs", "Lay out the tradeoffs of this technical choice.", "tradeoff table"),
        ("data-model", "Critique this data model and suggest improvements.", "critique + revised model"),
        ("interface-design", "Review this interface/contract for clarity.", "issues + suggestions"),
        ("pattern-suggest", "Suggest design patterns that fit this problem.", "pattern + why"),
        ("scalability-review", "Identify scalability bottlenecks in this design.", "bottleneck list"),
        ("boundary-check", "Review the module boundaries and coupling here.", "coupling issues"),
        ("dependency-review", "Review this dependency graph for problems.", "issues + fixes"),
        ("coupling-check", "Flag tight coupling and suggest decoupling.", "coupling list + fixes"),
    ]),
    ("devops-deploy", "Ship safely.", "code", "{{input}}", [
        ("deploy-check", "Check this code for production readiness before deployment.", "PASS/FAIL/WARN checklist"),
        ("dockerfile-review", "Review this Dockerfile for security and size.", "issue list + fixes"),
        ("ci-review", "Review this CI config for gaps and slowness.", "issues + improvements"),
        ("env-audit", "Audit environment/config handling for problems.", "findings"),
        ("secrets-scan", "Scan this for hardcoded secrets and credentials.", "secret findings"),
        ("k8s-review", "Review this Kubernetes manifest.", "issues ranked by severity"),
        ("rollback-plan", "Write a rollback plan for this deployment.", "rollback steps"),
        ("healthcheck-design", "Design health/readiness checks for this service.", "check spec"),
        ("observability-review", "Review logging/metrics/tracing coverage.", "gaps + suggestions"),
        ("iac-review", "Review this infrastructure-as-code for risks.", "issue list"),
    ]),
    ("lang-tools", "Targeted language and tooling helpers.", "code", "{{input}}", [
        ("regex-explain", "Explain this regex and flag any bugs.", "explanation + issues"),
        ("sql-review", "Review this SQL for correctness, performance, and injection.", "issues + optimized query"),
        ("async-review", "Review this async code for await/concurrency bugs.", "issues + fixes"),
        ("null-safety", "Find null/None-safety gaps in this code.", "gap list + fixes"),
        ("lint-explain", "Explain these linter errors and how to fix them.", "error: fix list"),
        ("import-cleanup", "Suggest cleanups for these imports.", "cleaned imports"),
        ("config-review", "Review this config file for mistakes.", "issue list"),
        ("migration-plan", "Plan a safe migration for this change.", "migration steps"),
    ]),
]


def build():
    PACKS_DIR.mkdir(parents=True, exist_ok=True)
    lines = ["# ICENI starter library\n",
             "100 chat + 100 Claude Code workflows. Install a pack with "
             "`iceni pack install <name>`.\n"]
    totals = {"chat": 0, "code": 0}
    for group, packs in (("chat", CHAT_PACKS), ("code", CODE_PACKS)):
        lines.append(f"\n## {group.upper()} packs\n")
        for name, desc, kind, inp, items in packs:
            aliases = []
            for petname, goal, output in items:
                aliases.append({"petname": petname, "intent": {
                    "goal": goal, "inputs": [inp],
                    "constraints": CONSTRAINTS[kind],
                    "outputs": {"format": output},
                    "style_hints": HINTS[kind]}})
            (PACKS_DIR / f"{name}.json").write_text(
                json.dumps({"name": name, "description": desc, "aliases": aliases}, indent=2),
                encoding="utf-8")
            totals[group] += len(items)
            lines.append(f"\n### {name} ({len(items)}) — {desc}")
            for petname, goal, _ in items:
                lines.append(f"- `{petname}` — {goal}")
    lines.insert(2, f"\n**{totals['chat']} chat · {totals['code']} code · "
                    f"{totals['chat'] + totals['code']} total**\n")
    CATALOG.write_text("\n".join(lines), encoding="utf-8")
    print(f"chat={totals['chat']} code={totals['code']} "
          f"total={totals['chat'] + totals['code']}")
    print(f"packs written to {PACKS_DIR}")
    print(f"catalog -> {CATALOG}")


if __name__ == "__main__":
    build()
