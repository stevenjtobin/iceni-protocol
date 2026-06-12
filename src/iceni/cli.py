"""ICENI command-line interface.

Offline by default — create/list/show/compare/run --preview need no API keys and
prove the architecture (petname -> signed intent -> per-model render). Add
--execute (with keys in env) to call live models and log value-case telemetry.
"""
from __future__ import annotations

import json
from pathlib import Path

import click

from . import benchmark, calibration, config
from .intent import Intent
from .providers.base import ProviderUnavailable, get_provider
from .store import aliases as store_aliases
from .store import db


def _intent_table(intent: Intent) -> str:
    lines = [f"goal        {intent.goal}"]
    if intent.inputs:
        lines.append(f"inputs      {', '.join(intent.inputs)}")
    if intent.constraints:
        lines.append("constraints " + "; ".join(intent.constraints))
    if intent.outputs:
        lines.append(f"outputs     {json.dumps(intent.outputs)}")
    if intent.style_hints:
        lines.append(f"style_hints {json.dumps(intent.style_hints)}")
    return "\n".join(lines)


def _apply_input(prompt: str, text: str) -> str:
    for ph in ("{{file}}", "{{code}}", "{{input}}", "{{context}}"):
        if ph in prompt:
            return prompt.replace(ph, text)
    return prompt + "\n\n" + text


@click.group(help="ICENI — cross-model, self-evolving prompt aliases.")
@click.version_option(package_name="iceni")
def cli() -> None:
    pass


@cli.command()
def init() -> None:
    """Initialize ~/.iceni (config + database)."""
    conn = db.connect()
    conn.close()
    click.echo(f"Initialized {config.home()}")
    click.echo(f"  config  {config.config_path()}")
    click.echo(f"  db      {config.db_path()}")


@cli.command()
@click.argument("petname")
@click.option("--goal", help="What the alias does (required unless --from-file).")
@click.option("--input", "inputs", multiple=True, help="Input placeholder, repeatable (e.g. {{code}}).")
@click.option("--constraint", "constraints", multiple=True, help="A requirement, repeatable.")
@click.option("--output-format", help="Desired output shape (e.g. 'issues, severity').")
@click.option("--hint", "hints", multiple=True, help="Per-model hint 'model=text', repeatable.")
@click.option("--from-file", type=click.Path(exists=True, dir_okay=False), help="Load intent JSON from a file.")
def create(petname, goal, inputs, constraints, output_format, hints, from_file) -> None:
    """Create an alias from a model-agnostic intent."""
    if from_file:
        intent = Intent.from_json(Path(from_file).read_text(encoding="utf-8"))
    else:
        if not goal:
            raise click.UsageError("provide --goal (or --from-file)")
        style = {}
        for h in hints:
            if "=" in h:
                k, v = h.split("=", 1)
                style[k.strip()] = v.strip()
        outputs = {"format": output_format} if output_format else {}
        intent = Intent(goal=goal, inputs=list(inputs), constraints=list(constraints),
                        outputs=outputs, style_hints=style)

    conn = db.connect()
    try:
        cid, content_hash = store_aliases.create_alias(conn, petname, intent)
    except store_aliases.PetnameExists as exc:
        raise click.ClickException(str(exc))
    finally:
        conn.close()
    click.echo(f"Created alias '{petname}'")
    click.echo(f"  canonical_id  {cid}")
    click.echo(f"  content_hash  sha256:{content_hash[:16]}…  (signed, v1.0.0)")


@cli.command(name="list")
def list_cmd() -> None:
    """List aliases with usage counts."""
    conn = db.connect()
    rows = store_aliases.list_aliases(conn)
    conn.close()
    if not rows:
        click.echo("No aliases yet. Try: iceni create review --goal '…'")
        return
    click.echo(f"{'PETNAME':<16}{'VER':<8}{'RUNS':<6}{'CANONICAL ID':<44}HASH")
    for r in rows:
        click.echo(f"{r['petname']:<16}{r['semver']:<8}{r['runs']:<6}{r['canonical_id']:<44}{r['content_hash'][:12]}")


@cli.command()
@click.argument("petname")
def show(petname) -> None:
    """Show an alias: intent, signature status, per-model renderings, stats."""
    conn = db.connect()
    resolved = store_aliases.resolve(conn, petname)
    if not resolved:
        conn.close()
        raise click.ClickException(f"unknown alias '{petname}'")
    cid, av = resolved
    intent = Intent.from_json(av["intent_json"])
    ok = store_aliases.verify(conn, cid, av)
    conn.close()

    click.echo(f"alias '{petname}'  (v{av['semver']})")
    click.echo(f"  canonical_id  {cid}")
    click.echo(f"  content_hash  sha256:{av['content_hash'][:16]}…")
    click.echo(f"  signature     {'✓ valid' if ok else '✗ INVALID'}  (trust rides on this, not the name)")
    click.echo("\nintent:")
    click.echo("  " + _intent_table(intent).replace("\n", "\n  "))
    click.echo("\nper-model renderings:")
    for m in calibration.KNOWN_MODELS:
        rendered = calibration.render(intent, m)
        approx = max(1, len(rendered) // 4)
        click.echo(f"\n  ── {m}  (≈{approx} tok) ─────────────")
        click.echo("  " + rendered.replace("\n", "\n  "))


@cli.command()
@click.argument("petname")
@click.argument("file", required=False, type=click.Path(exists=True, dir_okay=False))
@click.option("--model", default=None, help="Model key (default: config default_model).")
@click.option("--execute/--preview", default=False, help="Call the live model (needs API key) vs print the prompt.")
def run(petname, file, model, execute) -> None:
    """Render an alias for a model and (optionally) execute it."""
    cfg = config.load()
    model = model or cfg.get("default_model", "claude")
    conn = db.connect()
    resolved = store_aliases.resolve(conn, petname)
    if not resolved:
        conn.close()
        raise click.ClickException(f"unknown alias '{petname}'")
    cid, av = resolved
    intent = Intent.from_json(av["intent_json"])
    prompt = calibration.render(intent, model)
    if file:
        prompt = _apply_input(prompt, Path(file).read_text(encoding="utf-8"))

    if not execute:
        click.echo(f"# rendered for {model} (preview — add --execute to run):\n")
        click.echo(prompt)
        conn.close()
        return

    try:
        provider = get_provider(model, cfg)
        result = provider.complete(prompt)
    except ProviderUnavailable as exc:
        conn.close()
        raise click.ClickException(f"{model}: {exc}")
    from . import feedback
    parse_ok = feedback.structure_ok(result.text, model)
    store_aliases.record_execution(conn, av["content_hash"], model, outcome="accepted",
                                   tokens_in=result.tokens_in, tokens_out=result.tokens_out,
                                   parse_ok=parse_ok)
    conn.close()
    click.echo(result.text)
    fit = "structure ✓" if parse_ok else "structure ✗"
    click.echo(f"\n[{model}: {result.tokens_in} in / {result.tokens_out} out tokens · "
               f"{fit} — logged]", err=True)


@cli.command()
@click.argument("petname")
@click.option("--execute", is_flag=True, help="Call every model live (needs keys) and show outputs.")
@click.option("--models", default=None, help="Comma list (default: kimi,claude,gpt).")
def compare(petname, execute, models) -> None:
    """Side-by-side cross-model renderings (value-case V1) + token estimates (V2)."""
    cfg = config.load()
    model_keys = [m.strip() for m in (models.split(",") if models else ["kimi", "claude", "gpt"])]
    conn = db.connect()
    resolved = store_aliases.resolve(conn, petname)
    if not resolved:
        conn.close()
        raise click.ClickException(f"unknown alias '{petname}'")
    cid, av = resolved
    intent = Intent.from_json(av["intent_json"])

    for m in model_keys:
        rendered = calibration.render(intent, m)
        approx = max(1, len(rendered) // 4)
        click.echo(f"\n══ {m}  (≈{approx} tok) ══════════════════════")
        click.echo(rendered)
        if execute:
            try:
                provider = get_provider(m, cfg)
                result = provider.complete(rendered)
                store_aliases.record_execution(conn, av["content_hash"], m, outcome="accepted",
                                               tokens_in=result.tokens_in, tokens_out=result.tokens_out)
                click.echo(f"\n→ {m} output ({result.tokens_in}/{result.tokens_out} tok):\n{result.text}")
            except ProviderUnavailable as exc:
                click.echo(f"\n→ {m}: skipped ({exc})")
    conn.close()


@cli.command()
@click.argument("petname")
def evolve(petname) -> None:
    """[v0.1 stub] Propose an intent improvement from recent execution edits (human-gated)."""
    conn = db.connect()
    resolved = store_aliases.resolve(conn, petname)
    if not resolved:
        conn.close()
        raise click.ClickException(f"unknown alias '{petname}'")
    cid, av = resolved
    edits = conn.execute(
        "SELECT COUNT(*) c FROM executions WHERE content_hash=? AND outcome='edited'",
        (av["content_hash"],),
    ).fetchone()["c"]
    conn.close()
    click.echo(f"evolve '{petname}': {edits} edited execution(s) on record.")
    click.echo("v0.1 stub — SCOPE-style θ_{t+1}=θ_t⊕g_t synthesis lands in Phase IV (Week 10–11).")
    click.echo("Evolution will be manual-approve by default with a diff + rollback.")


@cli.command(name="benchmark")
@click.argument("tasks_file", type=click.Path(exists=True, dir_okay=False))
@click.option("--execute", is_flag=True, help="Call live models (needs keys) for cost/quality/speed.")
@click.option("--judge", "judge_model", default=None, help="Model key to score output quality 0–100.")
@click.option("--models", default=None, help="Comma list (default: kimi,claude,gpt).")
@click.option("--report", "report_path", type=click.Path(), default=None, help="Write the markdown report here.")
def benchmark_cmd(tasks_file, execute, judge_model, models, report_path) -> None:
    """Run the value-case benchmark: natural-language baseline vs ICENI calibration."""
    cfg = config.load()
    model_keys = [m.strip() for m in (models.split(",") if models else ["kimi", "claude", "gpt"])]
    conn = db.connect()

    def resolver(petname):
        return store_aliases.resolve(conn, petname)

    try:
        results, meta = benchmark.run(tasks_file, model_keys, cfg, execute=execute,
                                      judge_model=judge_model, resolver=resolver)
    finally:
        conn.close()
    report = benchmark.render_report(results, meta)
    click.echo(report)
    if report_path:
        Path(report_path).write_text(report, encoding="utf-8")
        click.echo(f"\n[report written to {report_path}]", err=True)


@cli.command(name="calibrate")
@click.argument("petname", required=False)
@click.option("--apply", "apply_", is_flag=True, help="Promote a style hint to a new signed version.")
@click.option("--hint", "hints", multiple=True, help="'model=text' to lock in (with --apply), repeatable.")
def calibrate_cmd(petname, apply_, hints) -> None:
    """Phase III: score executions by consumer success; no name = signal-density dashboard."""
    from . import feedback
    conn = db.connect()

    if not petname:  # dashboard: is the subscription flywheel producing enough signal?
        rows = store_aliases.list_aliases(conn)
        if not rows:
            conn.close()
            click.echo("No aliases yet.")
            return
        click.echo("calibration signal density (runs per alias · gate: ≥5 ready / 3-4 building / <5 sparse)\n")
        click.echo(f"  {'ALIAS':<18}{'claude':>8}{'gpt':>7}{'kimi':>7}{'total':>8}  verdict")
        for r in rows:
            counts = {m: feedback.aggregate(conn, r["content_hash"], m)["n"]
                      for m in calibration.KNOWN_MODELS}
            total = sum(counts.values())
            verdict = "ready" if min(counts.values()) >= 5 else (
                "building" if total >= 3 else "sparse")
            click.echo(f"  {r['petname']:<18}{counts.get('claude',0):>8}{counts.get('gpt',0):>7}"
                       f"{counts.get('kimi',0):>7}{total:>8}  {verdict}")
        conn.close()
        click.echo("\nUse aliases via Claude Desktop (MCP logs each one free). "
                   "Run `iceni calibrate <alias>` for per-model scores + variants.")
        return

    resolved = store_aliases.resolve(conn, petname)
    if not resolved:
        conn.close()
        raise click.ClickException(f"unknown alias '{petname}'")
    cid, av = resolved
    intent = Intent.from_json(av["intent_json"])

    if apply_:  # promote chosen style hint(s) into a new signed alias_version
        if not hints:
            conn.close()
            raise click.UsageError("--apply needs at least one --hint 'model=text' "
                                   "(auto-winner-from-data lands once executions accumulate)")
        new_hints = dict(intent.style_hints)
        for h in hints:
            if "=" not in h:
                conn.close()
                raise click.UsageError(f"bad --hint '{h}', expected 'model=text'")
            k, v = h.split("=", 1)
            old = new_hints.get(k.strip(), "—")
            new_hints[k.strip()] = v.strip()
            click.echo(f"  {k.strip()}: {old}\n       → {v.strip()}")
        new_intent = Intent(goal=intent.goal, inputs=intent.inputs, constraints=intent.constraints,
                            outputs=intent.outputs, style_hints=new_hints)
        try:
            new_hash, semver = store_aliases.add_version(conn, cid, new_intent, source="calibrated")
        except store_aliases.IntentUnchanged as exc:
            conn.close()
            raise click.ClickException(str(exc))
        conn.close()
        click.echo(f"\n✓ '{petname}' evolved to v{semver}  (signed, parent-linked)")
        click.echo(f"  content_hash  sha256:{new_hash[:16]}…")
        return

    click.echo(f"calibrate '{petname}'  (objective: downstream consumer success — "
               "parse-fit + acceptance + low edit)\n")
    any_data = False
    for m in calibration.KNOWN_MODELS:
        agg = feedback.aggregate(conn, av["content_hash"], m)
        current = intent.style_hints.get(m, "—")
        if agg["n"] == 0:
            click.echo(f"  {m:<7} no executions yet · hint: {current}")
            continue
        any_data = True
        click.echo(f"  {m:<7} score {agg['score']} over {agg['n']} run(s) "
                   f"(parse {agg['parse_rate']}, accept {agg['accept_rate']}) · hint: {current}")
        if agg["score"] is None or agg["score"] < 0.85:
            for v in feedback.propose_variants(m, current)[:2]:
                click.echo(f"           try: {v}")
    conn.close()
    if not any_data:
        click.echo("\nNo execution feedback yet. Gather it free via the MCP server "
                   "(use the alias in Claude Desktop), or `iceni run … --execute` with API keys.")
    else:
        click.echo("\nVariants are the next experiments — run them with --execute and "
                   "re-check; the winner becomes the calibrated style hint.")


@cli.group(name="pack")
def pack_group() -> None:
    """Curated alias packs — instant value, one command."""


def _packs_dir():
    from importlib.resources import files
    return files("iceni").joinpath("packs")


@pack_group.command(name="list")
def pack_list() -> None:
    """Show available packs and what's inside."""
    for f in sorted(_packs_dir().iterdir(), key=lambda p: p.name):
        if not f.name.endswith(".json"):
            continue
        data = json.loads(f.read_text(encoding="utf-8"))
        names = ", ".join(a["petname"] for a in data["aliases"])
        click.echo(f"  {data['name']:<14} {len(data['aliases'])} aliases — {names}")
        click.echo(f"  {'':<14} {data['description']}\n")
    click.echo("Install one:  iceni pack install code-quality")


@pack_group.command(name="install")
@click.argument("name")
def pack_install(name) -> None:
    """Install a pack's aliases (skips dupes). Use 'all' to install the whole library."""
    if name == "all":
        files = sorted(f for f in _packs_dir().iterdir() if f.name.endswith(".json"))
    else:
        f = _packs_dir().joinpath(f"{name}.json")
        if not f.is_file():
            raise click.ClickException(f"no pack named '{name}' — see: iceni pack list")
        files = [f]

    conn = db.connect()
    added, skipped = [], 0
    for src in files:
        data = json.loads(src.read_text(encoding="utf-8"))
        for a in data["aliases"]:
            try:
                store_aliases.create_alias(conn, a["petname"], Intent.from_dict(a["intent"]))
                added.append(a["petname"])
            except store_aliases.PetnameExists:
                skipped += 1
    conn.close()
    click.echo(f"✓ installed {len(added)} new alias(es)"
               + (f" across {len(files)} packs" if len(files) > 1 else "")
               + (f"  ({skipped} already present, skipped)" if skipped else "")
               + "  — each signed with its own identity")
    if name != "all" and added:
        click.echo("  " + ", ".join(added))
    click.echo("\nUse them in Claude Desktop (+ → Connectors → Add from iceni) or "
               "Claude Code (/iceni). Not connected? Run: iceni connect-desktop")


@cli.command(name="export")
@click.argument("petname")
@click.option("--out", type=click.Path(), default=None, help="Output file (default: <petname>.iceni)")
def export_cmd(petname, out) -> None:
    """Export a signed, portable alias file to share with your team."""
    conn = db.connect()
    try:
        data = store_aliases.export_alias(conn, petname)
    except ValueError as exc:
        raise click.ClickException(str(exc))
    finally:
        conn.close()
    path = Path(out) if out else Path(f"{petname}.iceni")
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    click.echo(f"✓ exported '{petname}' → {path}")
    click.echo("  Signed and content-addressed — the receiver verifies before installing.")
    click.echo(f"  They run:  iceni import {path.name}")


@cli.command(name="import")
@click.argument("file", type=click.Path(exists=True, dir_okay=False))
@click.option("--as", "as_name", default=None, help="Install under a different local petname.")
def import_cmd(file, as_name) -> None:
    """Install a shared .iceni alias file (signature verified first)."""
    data = json.loads(Path(file).read_text(encoding="utf-8"))
    conn = db.connect()
    try:
        name, cid, semver = store_aliases.import_alias(conn, data, petname=as_name)
    except (ValueError, store_aliases.PetnameExists) as exc:
        raise click.ClickException(str(exc))
    finally:
        conn.close()
    click.echo(f"✓ imported '{name}' v{semver}  — signature verified")
    click.echo(f"  canonical_id  {cid}")
    click.echo("  You hold no private key for it: use it freely, fork it to evolve it.")


@cli.command(name="connect-desktop")
def connect_desktop() -> None:
    """Wire ICENI into Claude Desktop automatically (edits claude_desktop_config.json)."""
    import os
    import shutil
    import sys
    if sys.platform == "win32":
        cfg_path = Path(os.environ["APPDATA"]) / "Claude" / "claude_desktop_config.json"
    elif sys.platform == "darwin":
        cfg_path = Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    else:
        raise click.ClickException("Claude Desktop runs on Windows/macOS — config not found for this OS")

    # Preflight: Desktop will launch THIS python — fail here with instructions,
    # not later with a silent "Server disconnected" in Desktop.
    try:
        import mcp  # noqa: F401
    except ImportError:
        raise click.ClickException(
            "the MCP SDK is missing from this Python, so Claude Desktop could not "
            "start the server.\n  Fix:  pip install mcp   — then re-run: iceni connect-desktop"
        )

    cfg = {}
    if cfg_path.exists():
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            raise click.ClickException(f"{cfg_path} exists but is not valid JSON — fix or remove it first")
        shutil.copy2(cfg_path, cfg_path.with_suffix(".json.bak"))
    else:
        cfg_path.parent.mkdir(parents=True, exist_ok=True)

    entry = {"command": sys.executable, "args": ["-m", "iceni", "mcp"]}
    already = cfg.get("mcpServers", {}).get("iceni") == entry
    cfg.setdefault("mcpServers", {})["iceni"] = entry
    cfg_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")

    click.echo(f"{'✓ already connected' if already else '✓ connected'}  ({cfg_path})")
    if cfg_path.with_suffix(".json.bak").exists():
        click.echo(f"  backup saved: {cfg_path.with_suffix('.json.bak').name}")
    click.echo("\nNow: quit Claude Desktop completely (system tray → quit) and reopen it.")
    click.echo("Then type /iceni in any conversation — all your workflows in one menu.")
    click.echo("(Your top 3 also work directly, e.g. /review.)")


@cli.command(name="stats")
def stats_cmd() -> None:
    """Per-alias adoption dashboard: uses · accepted/edited/rejected · parse-fit (observe, don't tune)."""
    conn = db.connect()
    rows = store_aliases.stats(conn)
    conn.close()
    if not rows:
        click.echo("No aliases yet. Try: iceni create review --goal '…'")
        return
    click.echo(f"{'ALIAS':<18}{'USES':>5}{'ACC':>5}{'EDIT':>5}{'REJ':>5}{'PARSE-FIT':>11}  LAST")
    total = 0
    for r in rows:
        total += r["uses"] or 0
        pf = (f"{round(100 * r['parse_fit'] / r['parse_known'])}%"
              if r["parse_known"] else "—")
        last = (r["last_used"] or "")[:10] or "—"
        click.echo(f"{r['petname']:<18}{r['uses'] or 0:>5}{r['accepted'] or 0:>5}"
                   f"{r['edited'] or 0:>5}{r['rejected'] or 0:>5}{pf:>11}  {last}")
    active = sum(1 for r in rows if (r["uses"] or 0) > 0)
    click.echo(f"\n{active}/{len(rows)} aliases used · {total} total invocations. "
               "Weekly-active is the metric that matters — let usage tell you what to calibrate.")
    if total:
        # Conservative, defensible numbers only (GPT): words + typing time, both
        # derived from the measured ~59-word baseline instruction block. No
        # avoided-failure or avoided-spend estimates — those aren't measured.
        click.echo(f"Est. saved so far: ~{total * 59:,} prompt-words of retyping "
                   f"(~{total} min)  · basis: ~59-word baseline instruction per use")


@cli.command(name="feedback")
@click.argument("petname")
@click.option("--outcome", type=click.Choice(["accepted", "edited", "rejected"]), default=None,
              help="Optional: used as-is / edited / discarded. Omit to log usage only.")
@click.option("--model", default="claude", help="Which model produced it (default: claude).")
@click.option("--output", type=click.Path(exists=True, dir_okay=False),
              help="File with the model's output — computes parse-fit automatically.")
@click.option("--edited", type=click.Path(exists=True, dir_okay=False),
              help="File with your edited version — computes edit distance vs --output.")
def feedback_cmd(petname, outcome, model, output, edited) -> None:
    """Record a real consumer-success signal for an alias (closes the free flywheel)."""
    from . import feedback as fb
    from pathlib import Path as _Path
    conn = db.connect()
    resolved = store_aliases.resolve(conn, petname)
    if not resolved:
        conn.close()
        raise click.ClickException(f"unknown alias '{petname}'")
    _, av = resolved
    parse_ok, edist = None, None
    if output:
        out_text = _Path(output).read_text(encoding="utf-8")
        parse_ok = fb.structure_ok(out_text, model)
        if edited:
            edist = round(fb.edit_ratio(out_text, _Path(edited).read_text(encoding="utf-8")), 3)
    store_aliases.record_execution(conn, av["content_hash"], model, outcome=outcome,
                                   parse_ok=parse_ok, edit_distance=edist)
    conn.close()
    bits = [f"outcome={outcome}" if outcome else "usage logged"]
    if parse_ok is not None:
        bits.append(f"parse={'fit' if parse_ok else 'miss'}")
    if edist is not None:
        bits.append(f"edit={edist}")
    click.echo(f"recorded feedback for '{petname}' ({model}): {', '.join(bits)}")


@cli.command(name="discover")
@click.option("--source", default=None, help="Logs root (default: ~/.claude/projects).")
@click.option("--min-cluster-size", "min_cluster_size", default=3,
              help="HDBSCAN min cluster size — raise for higher precision.")
@click.option("--limit", default=10, help="Max candidate aliases to show.")
@click.option("--create", is_flag=True, help="Mint signed aliases from the shown candidates.")
def discover_cmd(source, min_cluster_size, limit, create) -> None:
    """Auto-discover recurring prompt intents from your conversation logs (Phase II)."""
    from . import discovery
    conn = db.connect()
    existing = {r["petname"] for r in store_aliases.list_aliases(conn)}
    try:
        cands, scanned = discovery.discover(
            source, min_cluster_size=min_cluster_size, limit=limit, existing=existing)
    except RuntimeError as exc:
        conn.close()
        raise click.ClickException(str(exc))
    if not cands:
        conn.close()
        click.echo(f"Scanned {scanned} prompts — no recurring clusters at "
                   f"min-cluster-size={min_cluster_size}. Try a lower value.")
        return

    click.echo(f"Scanned {scanned} user prompts. Top {len(cands)} recurring intents:\n")
    for i, c in enumerate(cands, 1):
        span = f"{c.span_days:.0f}d" if c.span_days else "1 session"
        click.echo(f"  [{i}] {c.petname}  (score {c.score} · ×{c.size} over "
                   f"{len(c.projects)} project(s), {span}, cohesion {c.cohesion})")
        click.echo(f"      goal: {c.goal[:100]}")
        click.echo(f"      e.g.: {c.samples[0][:80]}")
        click.echo("")

    out = config.home() / "discovered.json"
    out.write_text(json.dumps([c.__dict__ for c in cands], indent=2), encoding="utf-8")
    click.echo(f"[candidates written to {out}]")

    if not create:
        click.echo("Re-run with --create to mint signed aliases from these candidates.")
        conn.close()
        return
    made = 0
    for c in cands:
        try:
            cid, ch = store_aliases.create_alias(conn, c.petname, discovery.candidate_to_intent(c))
            made += 1
            click.echo(f"  + created '{c.petname}'  (sha256:{ch[:12]}…)")
        except store_aliases.PetnameExists:
            click.echo(f"  · skipped '{c.petname}' (already exists)")
    conn.close()
    click.echo(f"\nMinted {made} signed alias(es). Refine with `iceni show <name>`; "
               "per-model style hints get filled by Phase III live calibration.")


@cli.command(name="mcp")
def mcp_cmd() -> None:
    """Start ICENI as an MCP server for Claude Desktop (no API key needed — uses subscription)."""
    from .mcp_server import serve
    serve()


@cli.command()
def doctor() -> None:
    """Show config / paths / model-key availability."""
    import os
    cfg = config.load()
    click.echo(f"home    {config.home()}  ({'exists' if config.home().exists() else 'missing'})")
    click.echo(f"db      {config.db_path()}  ({'exists' if config.db_path().exists() else 'missing'})")
    click.echo(f"default {cfg.get('default_model')}")
    click.echo("models:")
    for key, m in cfg.get("models", {}).items():
        env = m.get("api_key_env", "")
        has = "key set" if os.environ.get(env) else "no key"
        click.echo(f"  {key:<8}{m.get('provider'):<14}{m.get('model','?'):<18}[{env}: {has}]")


def main() -> None:
    import sys
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # robust on Windows pipes
        except Exception:
            pass
    cli()


if __name__ == "__main__":
    main()
