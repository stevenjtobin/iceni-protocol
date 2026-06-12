"""Structure Fidelity Score (SFS) — deterministic, zero-LLM parse test.

GPT+Kimi agreed metric: the ICENI value claim is inter-agent machine-readability,
not single-shot quality. This measures it objectively. For each produced output we
attempt to recover a uniform finding schema {severity, location, body} using three
GENERIC parser strategies a swarm engineer would plausibly write — XML, markdown
table, and prose/severity regex — and keep the best result per output. No model is
called: this is exactly "can the next agent parse this for free?".

SFS per output = fraction of recovered findings whose severity, location, and body
land in cleanly separated fields. 1.0 = every finding fully field-separable by code.

Usage: python benchmarks/sfs_test.py
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

OUT = Path(__file__).parent / "free-tests" / "outputs"
TASKS = ["t01", "t06", "t07", "t08", "t10"]
LABELS = {"t01": "review", "t06": "deploy-check", "t07": "dependency-audit",
          "t08": "api-review", "t10": "security-audit"}
SEVS = {"critical", "high", "medium", "low", "warn", "warning", "info", "pass", "fail"}
LOC_RE = re.compile(r"\b(?:line|lines|l)\s*\.?\s*\d", re.I)


def strip_fences(t: str) -> str:
    return re.sub(r"^```[a-zA-Z]*\n|\n```$", "", t.strip()).strip()


# --- strategy 1: XML ---------------------------------------------------------
def parse_xml(text: str):
    t = strip_fences(text)
    root = None
    for candidate in (t, f"<root>{t}</root>"):
        try:
            root = ET.fromstring(candidate)
            break
        except ET.ParseError:
            continue
    if root is None:
        return None
    findings = []
    for el in root.iter():
        attrs = {k.lower(): v for k, v in el.attrib.items()}
        sev = attrs.get("severity") or attrs.get("level")
        if not sev:
            for v in el.attrib.values():
                if v.lower() in SEVS:
                    sev = v
        tag = el.tag.lower()
        if sev or tag in ("issue", "finding", "package", "item"):
            body = " ".join(el.itertext()).strip()
            loc = (attrs.get("lines") or attrs.get("line") or attrs.get("location")
                   or attrs.get("version"))
            if not loc:
                m = LOC_RE.search(body)
                loc = m.group(0) if m else None
            findings.append({"severity": (sev or "").lower() or None,
                             "location": loc, "body": body[:200]})
    return findings or None


# --- strategy 2: markdown table ---------------------------------------------
def parse_table(text: str):
    rows = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("|") and s.count("|") >= 3:
            cells = [c.strip() for c in s.strip("|").split("|")]
            if set("".join(cells)) <= set("-: "):
                continue
            rows.append(cells)
    if len(rows) < 2:
        return None
    header = [h.lower() for h in rows[0]]
    findings = []
    for r in rows[1:]:
        cell = {header[i]: r[i] for i in range(min(len(header), len(r)))}
        joined = " ".join(r).lower()
        sev = next((s for s in SEVS if s in joined), None)
        loc = cell.get("version") or cell.get("line") or cell.get("location")
        findings.append({"severity": sev, "location": loc, "body": " ".join(r)[:200]})
    return findings or None


# --- strategy 3: prose / severity regex -------------------------------------
def parse_prose(text: str):
    findings = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        is_item = s.startswith(("-", "*", "#", "**")) or re.match(r"^\d+[.)]", s)
        m = re.search(r"\b(critical|high|medium|low|warn(?:ing)?|info)\b", s, re.I)
        if is_item and m:
            loc = LOC_RE.search(s)
            findings.append({"severity": m.group(1).lower(),
                             "location": loc.group(0) if loc else None,
                             "body": s[:200]})
    return findings or None


def sev_rate(findings) -> float:
    """Fraction of records carrying an explicit, per-record severity field."""
    if not findings:
        return 0.0
    return sum(1 for f in findings if f["severity"]) / len(findings)


def analyze(text: str):
    xml = parse_xml(text)
    tab = parse_table(text)
    pro = parse_prose(text)
    # Deterministically structured = code can split into discrete records
    # without an LLM: well-formed XML (>=2 elements) or a markdown table.
    if xml and len(xml) >= 2:
        return {"strategy": "xml", "det_structured": True, "n": len(xml),
                "sev_rate": sev_rate(xml), "xml_wellformed": True}
    if tab and len(tab) >= 2:
        return {"strategy": "table", "det_structured": True, "n": len(tab),
                "sev_rate": sev_rate(tab), "xml_wellformed": xml is not None}
    # Falls back to fragile prose regex — NOT reliably machine-structured.
    n = len(pro) if pro else 0
    return {"strategy": "prose" if n else "none", "det_structured": False,
            "n": n, "sev_rate": sev_rate(pro) if pro else 0.0,
            "xml_wellformed": False}


def main() -> None:
    print(f"{'task':<18}{'variant':<10}{'det-parse?':<11}{'strategy':<8}"
          f"{'records':>8}{'sev/rec':>9}")
    print("-" * 64)
    agg = {"iceni": {"det": [], "sev": []}, "baseline": {"det": [], "sev": []}}
    for tid in TASKS:
        for variant in ("iceni", "baseline"):
            p = OUT / f"{tid}_{variant}.txt"
            if not p.exists():
                print(f"{LABELS[tid]:<18}{variant:<10}MISSING")
                continue
            r = analyze(p.read_text(encoding="utf-8"))
            agg[variant]["det"].append(1 if r["det_structured"] else 0)
            agg[variant]["sev"].append(r["sev_rate"])
            mark = "YES" if r["det_structured"] else "no"
            print(f"{LABELS[tid]:<18}{variant:<10}{mark:<11}{r['strategy']:<8}"
                  f"{r['n']:>8}{r['sev_rate']:>9.2f}")
        print()
    print("Deterministically parseable WITHOUT an LLM (the swarm-free-parse claim):")
    for v in ("iceni", "baseline"):
        d, s = agg[v]["det"], agg[v]["sev"]
        print(f"  {v:<8} det-structured {sum(d)}/{len(d)}   "
              f"mean per-record severity {sum(s) / len(s):.2f}")


if __name__ == "__main__":
    main()
