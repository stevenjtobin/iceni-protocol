#!/usr/bin/env python3
"""
ICENI UserPromptSubmit hook (portable).

Fires on every Claude Code message. If the message looks like a task that maps
to a saved ICENI workflow, it injects the calibrated prompt as context so Claude
uses it automatically — no /iceni typing required.

This is the bundled, machine-independent version installed by `iceni connect-code`.
It uses the interpreter that runs it (sys.executable), so it works on Windows,
macOS, or a Linux VPS with no path edits.

SAFETY:
  * Fail-safe: ANY error → silent exit 0. The hook can never block your prompt.
  * Kill switch: env ICENI_HOOK_DISABLED=1, or create ~/.iceni/hook.disabled.
  * No untrusted execution: workflow names come from a fixed allow-list, never
    from raw user input — a crafted message cannot inject a command.
  * Bounded: short subprocess timeouts + a cap on injected output size.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# The Python that runs this hook is the one Claude Code was pointed at by
# `iceni connect-code`, so it already has `iceni` installed. Override with
# ICENI_PYTHON if you want a different interpreter.
PYTHON = os.environ.get("ICENI_PYTHON", sys.executable)
ICENI = [PYTHON, "-m", "iceni"]

MAX_INJECT_CHARS = 4000   # never dump more than this into the context

TASK_SIGNALS = [
    r"```",
    r"\bdef \b", r"\bclass \b",
    r"\bfunction\b", r"\bconst \b",
    r"\bimport \b", r"\bfrom \b",
    r"\.py\b", r"\.js\b", r"\.ts\b", r"\.go\b", r"\.rs\b", r"\.java\b",
    r"\bthis (code|function|class|file|module|script|api|endpoint)\b",
    r"\bmy (code|function|class|api|pr|commit|diff|test)\b",
    r"\bthe following\b", r"\bbelow[:\s]",
    r"\b(fix|debug|refactor|review|audit|test|document|deploy|commit)\b",
]

# Workflow → trigger keywords (order = priority). Workflow names are a FIXED
# allow-list — never taken from user input — so no command-injection surface.
TRIGGERS = [
    ("security-audit",  [r"\bsecurit", r"\bvulnerab", r"\bexploit", r"\binjection", r"\bxss\b", r"\bcsrf\b", r"\bauth\b.*\b(bug|issue|flaw)"]),
    ("api-review",      [r"\bapi\b", r"\bendpoint\b", r"\brest\b", r"\bgraphql\b", r"\bopenapi\b", r"\bswagger\b"]),
    ("test-gen",        [r"\b(write|generate|add|create)\b.{0,20}\btest", r"\bunit test", r"\bpytest\b", r"\bspec\b"]),
    ("refactor",        [r"\brefactor\b", r"\bclean.?up\b", r"\brestructur", r"\bsimplif", r"\bimprove.{0,15}\bcode\b"]),
    ("docstring",       [r"\bdocstring", r"\bdocument this\b", r"\badd (comments?|docs?)\b"]),
    ("debug",           [r"\bdebug\b", r"\bwhat'?s wrong\b", r"\btraceback\b", r"\berror\b.{0,30}\bcode\b", r"\bfix (this|the bug|it)\b"]),
    ("commit-message",  [r"\bcommit message\b", r"\bgit commit\b", r"\bwrite.{0,10}\bcommit\b"]),
    ("deploy-check",    [r"\bdocker", r"\bkubernetes\b", r"\bk8s\b", r"\byaml\b", r"\bci/cd\b", r"\bdeploy"]),
    ("review",          [r"\breview\b", r"\bcheck (my|this|the)\b", r"\blook at\b", r"\bfeedback\b", r"\bthoughts on\b"]),
    ("summarize",       [r"\bsummar", r"\btldr\b", r"\bkey points\b", r"\bbrief\b"]),
    ("email-reply",     [r"\breply to\b", r"\bresponse to\b", r"\bdraft.{0,15}\bemail\b"]),
    ("blog-outline",    [r"\bblog\b", r"\barticle\b", r"\bpost\b.{0,10}\babout\b"]),
    ("research-brief",  [r"\bresearch\b", r"\bliterature\b", r"\bsurvey\b"]),
]


def is_disabled() -> bool:
    if os.environ.get("ICENI_HOOK_DISABLED"):
        return True
    try:
        if (Path.home() / ".iceni" / "hook.disabled").exists():
            return True
    except Exception:
        pass
    return False


def has_task_signal(text: str) -> bool:
    return any(re.search(pat, text, re.IGNORECASE) for pat in TASK_SIGNALS)


def match_workflow(text: str):
    lower = text.lower()
    for workflow, patterns in TRIGGERS:
        for pat in patterns:
            if re.search(pat, lower, re.IGNORECASE):
                return workflow
    return None


def fetch_prompt(workflow: str):
    try:
        result = subprocess.run(
            ICENI + ["run", workflow, "--preview", "--model", "claude"],
            capture_output=True, text=True, timeout=8,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()[:MAX_INJECT_CHARS]
    except Exception:
        pass
    return None


def log_use(workflow: str) -> None:
    try:
        subprocess.run(ICENI + ["feedback", workflow], capture_output=True, timeout=5)
    except Exception:
        pass


def run() -> None:
    if is_disabled():
        return
    try:
        data = json.load(sys.stdin)
    except Exception:
        return

    prompt = data.get("prompt", "")
    if not prompt or not has_task_signal(prompt):
        return

    workflow = match_workflow(prompt)
    if not workflow:
        return

    rendered = fetch_prompt(workflow)
    if not rendered:
        return

    print(f"[ICENI auto: matched workflow '{workflow}' — using calibrated prompt below]")
    print(rendered)
    log_use(workflow)


def main() -> None:
    # Outermost guard: the hook must NEVER raise, hang, or disrupt prompt
    # submission. Swallow everything and exit clean.
    try:
        run()
    except Exception:
        pass
    sys.exit(0)


if __name__ == "__main__":
    main()
