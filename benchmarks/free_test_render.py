"""Render ICENI + baseline prompt pairs for the free subscription test suite.

Implements the GPT+Kimi agreed design: vary TASK TYPE across all 10 aliases at
realistic input sizes; score manually on the V1 rubric at zero API cost.

Usage:  python benchmarks/free_test_render.py
Writes: benchmarks/free-tests/rendered/tNN_a.txt (ICENI) + tNN_b.txt (baseline)
"""
from pathlib import Path

from iceni import calibration
from iceni.benchmark import _apply_input, estimate_tokens
from iceni.intent import Intent
from iceni.store import aliases as store_aliases
from iceni.store import db

HERE = Path(__file__).parent
INPUTS = HERE / "free-tests" / "inputs"
RENDERED = HERE / "free-tests" / "rendered"

TESTS = [
    ("t01", "review", "t01_review_module.py"),
    ("t02", "test-gen", "t02_testgen_settings_view.py"),
    ("t03", "refactor", "t03_refactor_callbacks.py"),
    ("t04", "docstring", "t04_docstring_ml_pipeline.py"),
    ("t05", "error-explain", "t05_error_traceback.txt"),
    ("t06", "deploy-check", "t06_deploy_k8s.yaml"),
    ("t07", "dependency-audit", "t07_deps_requirements.txt"),
    ("t08", "api-review", "t08_api_fastapi_router.py"),
    ("t09", "commit-message", "t09_commit_diff.patch"),
    ("t10", "security-audit", "t10_security_middleware.py"),
]


def main() -> None:
    RENDERED.mkdir(parents=True, exist_ok=True)
    conn = db.connect()
    print(f"{'id':<5}{'alias':<18}{'input':>6}{'iceni':>7}{'base':>6}{'overhead':>10}")
    for tid, petname, fname in TESTS:
        resolved = store_aliases.resolve(conn, petname)
        if not resolved:
            raise SystemExit(f"alias '{petname}' not found — run the create commands first")
        intent = Intent.from_json(resolved[1]["intent_json"])
        src = (INPUTS / fname).read_text(encoding="utf-8")
        iceni_prompt = _apply_input(calibration.render(intent, "claude"), src)
        base_prompt = intent.goal + "\n\n" + src
        (RENDERED / f"{tid}_a.txt").write_text(iceni_prompt, encoding="utf-8")
        (RENDERED / f"{tid}_b.txt").write_text(base_prompt, encoding="utf-8")
        it, ic, ba = estimate_tokens(src), estimate_tokens(iceni_prompt), estimate_tokens(base_prompt)
        print(f"{tid:<5}{petname:<18}{it:>6}{ic:>7}{ba:>6}{(ic - ba) / ba * 100:>9.1f}%")
    conn.close()
    print(f"\nrendered pairs -> {RENDERED}")


if __name__ == "__main__":
    main()
