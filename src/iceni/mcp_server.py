"""ICENI MCP server — the /iceni router for Claude Desktop.

One branded entry point: /iceni lists and runs every workflow (two fields —
workflow name/number + your content). The top three workflows are ALSO
registered as direct one-shot prompts, so power users skip the menu while the
brand stays on everything. Trust, rendering and usage logging ride the same
spine as the CLI.

SETUP (one-time):
  1. pip install iceni            (MCP SDK included — no extras)
  2. iceni connect-desktop
  3. Restart Claude Desktop, then type /iceni in any conversation.
"""
from __future__ import annotations

import sys

TAGLINE = "Your best prompts, one word away."
# Seed order for the direct top-3 before usage data exists — the pack's proven
# structure-heavy winners. Real usage counts override this as they accumulate.
_PREFERRED = ["review", "security-audit", "api-review", "refactor", "docstring"]
_DIRECT_SLOTS = 3


def _entries(conn) -> list[dict]:
    """Menu entries, ALPHABETICAL so numbers never shift (muscle-memory safe)."""
    from .intent import Intent
    from .store import aliases as store_aliases
    out = []
    for r in store_aliases.list_aliases(conn):
        resolved = store_aliases.resolve(conn, r["petname"])
        if not resolved:
            continue
        _, av = resolved
        out.append({
            "petname": r["petname"],
            "goal": Intent.from_json(av["intent_json"]).goal,
            "runs": r["runs"] or 0,
            "content_hash": av["content_hash"],
            "intent_json": av["intent_json"],
        })
    out.sort(key=lambda e: e["petname"])
    return out


def _top_direct(entries: list[dict], n: int = _DIRECT_SLOTS) -> list[dict]:
    """Which aliases also get their own / command: usage first, seed order before data."""
    def rank(e):
        pref = _PREFERRED.index(e["petname"]) if e["petname"] in _PREFERRED else len(_PREFERRED)
        return (-e["runs"], pref, e["petname"])
    return sorted(entries, key=rank)[:n]


def _menu(entries: list[dict]) -> str:
    if not entries:
        return (
            f"ICENI — {TAGLINE}\n\n"
            "No workflows yet. In your terminal:\n"
            "  iceni pack install code-quality    (5 proven workflows)\n"
            "  iceni create <name> --goal \"...\"   (your own)"
        )
    lines = [
        f"ICENI — {TAGLINE}",
        "Turn long instructions into one-word workflows.",
        "",
        "Your workflows:",
    ]
    for i, e in enumerate(entries, 1):
        used = f"  ({e['runs']}x)" if e["runs"] else ""
        lines.append(f"  {i}. {e['petname']}{used} — {e['goal']}")
    lines += [
        "",
        "Run one: put its name or number in the workflow field and your content in the input field.",
        "Manage from your terminal: iceni create · iceni stats · iceni pack list",
    ]
    return "\n".join(lines)


def _resolve(query: str, entries: list[dict]) -> tuple[dict | None, str | None]:
    """(entry, error). Exact name → number → UNAMBIGUOUS prefix.

    Ambiguity is an error listing the matches — never a silent guess; a wrong
    workflow delivered confidently is how a tool loses trust.
    """
    q = (query or "").strip().lower()
    if not q:
        return None, None
    for e in entries:
        if e["petname"].lower() == q:
            return e, None
    if q.isdigit():
        i = int(q) - 1
        if 0 <= i < len(entries):
            return entries[i], None
        return None, f"there is no workflow #{q} — the menu lists {len(entries)}"
    matches = [e for e in entries if e["petname"].lower().startswith(q)]
    if len(matches) == 1:
        return matches[0], None
    if len(matches) > 1:
        names = ", ".join(m["petname"] for m in matches)
        return None, f"'{query}' is ambiguous ({names}) — use the full name or its number"
    return None, f"no workflow called '{query}'"


def _rendered(entry: dict, inp: str) -> str:
    from . import calibration
    from .intent import Intent
    rendered = calibration.render(Intent.from_json(entry["intent_json"]), "claude")
    if inp:
        from .benchmark import _apply_input
        return _apply_input(rendered, inp)
    return (rendered + "\n\n(No input was attached. Ask the user for the content "
            "to process, then perform the task above on it.)")


def serve() -> None:
    """Run the ICENI stdio MCP server."""
    try:
        from mcp.server import Server
        from mcp.server.stdio import stdio_server
        from mcp import types
    except ImportError:
        print(
            "MCP SDK not installed.\n"
            "Run: pip install mcp\n"
            "Then restart Claude Desktop.",
            file=sys.stderr,
        )
        sys.exit(1)

    from .store import aliases as store_aliases
    from .store import db

    server = Server("iceni")

    @server.list_prompts()
    async def list_prompts() -> list[types.Prompt]:
        conn = db.connect()
        entries = _entries(conn)
        conn.close()
        prompts = [
            types.Prompt(
                name="iceni",
                description=f"ICENI — {TAGLINE} ({len(entries)} workflows — leave fields empty to browse)",
                arguments=[
                    types.PromptArgument(
                        name="workflow",
                        description="Workflow name or menu number (empty = show the menu)",
                        required=False,
                    ),
                    types.PromptArgument(
                        name="input",
                        description="Your content — code, error, diff, anything",
                        required=False,
                    ),
                ],
            )
        ]
        for e in _top_direct(entries):
            prompts.append(
                types.Prompt(
                    name=e["petname"],
                    description=f"ICENI · {e['goal']}",
                    arguments=[
                        types.PromptArgument(
                            name="input",
                            description="Your content — code, error, diff, anything",
                            required=False,
                        )
                    ],
                )
            )
        return prompts

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        # ICENI is prompt-only; Claude Desktop probes tools/list regardless,
        # and an empty list keeps the log free of Method-not-found errors.
        return []

    @server.get_prompt()
    async def get_prompt(
        name: str, arguments: dict[str, str] | None = None
    ) -> types.GetPromptResult:
        args = arguments or {}
        conn = db.connect()
        entries = _entries(conn)

        if name == "iceni":
            wf = (args.get("workflow") or "").strip()
            if not wf:  # discovery moment — the branded menu
                conn.close()
                return types.GetPromptResult(
                    description=f"ICENI — {len(entries)} workflows",
                    messages=[types.PromptMessage(
                        role="user",
                        content=types.TextContent(type="text", text=_menu(entries)),
                    )],
                )
            entry, err = _resolve(wf, entries)
            if entry is None:
                conn.close()
                return types.GetPromptResult(
                    description="ICENI",
                    messages=[types.PromptMessage(
                        role="user",
                        content=types.TextContent(
                            type="text", text=f"ICENI: {err}.\n\n{_menu(entries)}"
                        ),
                    )],
                )
        else:  # direct top-3 prompt — name IS the petname
            entry, _ = _resolve(name, entries)
            if entry is None:
                conn.close()
                raise ValueError(f"Unknown alias: '{name}'")

        text = _rendered(entry, (args.get("input") or ""))
        # Usage signal: the subscription path feeds Phase III calibration for free.
        try:
            store_aliases.record_execution(conn, entry["content_hash"], "claude", outcome=None)
        except Exception:
            pass
        conn.close()
        return types.GetPromptResult(
            description=f"ICENI · {entry['petname']}",
            messages=[types.PromptMessage(
                role="user",
                content=types.TextContent(type="text", text=text),
            )],
        )

    import asyncio

    async def _run() -> None:
        async with stdio_server() as (read_stream, write_stream):
            from mcp.server.models import InitializationOptions

            # get_capabilities() only reads three flags off notification_options,
            # so if the class ever moves again a duck-typed namespace suffices.
            try:
                from mcp.server.lowlevel import NotificationOptions  # mcp 1.27.x
                notif = NotificationOptions()
            except ImportError:
                from types import SimpleNamespace
                notif = SimpleNamespace(
                    prompts_changed=False, resources_changed=False, tools_changed=False
                )

            await server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="iceni",
                    server_version="0.2.0",
                    capabilities=server.get_capabilities(
                        notification_options=notif,
                        experimental_capabilities={},
                    ),
                ),
            )

    asyncio.run(_run())
