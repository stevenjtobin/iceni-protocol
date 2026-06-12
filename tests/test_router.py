"""/iceni router: resolution rules, stable numbering, hybrid top-3, menu copy."""
from iceni.mcp_server import TAGLINE, _menu, _resolve, _top_direct


def E(name, runs=0, goal="do the thing"):
    return {"petname": name, "goal": goal, "runs": runs,
            "content_hash": "x", "intent_json": "{}"}


ENTRIES = sorted(  # alphabetical, as _entries() guarantees
    [E("api-review"), E("dependency-audit"), E("deploy-check"),
     E("docstring"), E("refactor"), E("review", runs=4), E("security-audit")],
    key=lambda e: e["petname"],
)


def test_exact_match_beats_prefix():
    entry, err = _resolve("review", ENTRIES)
    assert err is None and entry["petname"] == "review"  # not refactor via 're'


def test_number_selection_is_stable_alphabetical():
    entry, err = _resolve("1", ENTRIES)
    assert err is None and entry["petname"] == "api-review"
    # usage changing does NOT shift numbers — order is alphabetical, not by runs
    entry2, _ = _resolve("1", [dict(e, runs=e["runs"] + 50) for e in ENTRIES])
    assert entry2["petname"] == "api-review"


def test_ambiguous_prefix_is_an_error_not_a_guess():
    entry, err = _resolve("de", ENTRIES)
    assert entry is None
    assert "ambiguous" in err and "dependency-audit" in err and "deploy-check" in err


def test_unambiguous_prefix_resolves():
    entry, err = _resolve("sec", ENTRIES)
    assert err is None and entry["petname"] == "security-audit"


def test_unknown_and_out_of_range_give_helpful_errors():
    _, err = _resolve("zzz", ENTRIES)
    assert "no workflow called" in err
    _, err2 = _resolve("99", ENTRIES)
    assert "no workflow #99" in err2


def test_top_direct_uses_seed_order_before_data_then_usage():
    cold = [dict(e, runs=0) for e in ENTRIES]
    assert [e["petname"] for e in _top_direct(cold)] == ["review", "security-audit", "api-review"]
    hot = [dict(e, runs=(30 if e["petname"] == "docstring" else 0)) for e in ENTRIES]
    assert _top_direct(hot)[0]["petname"] == "docstring"  # real usage overrides the seed


def test_menu_has_value_prop_numbering_and_cli_tip():
    text = _menu(ENTRIES)
    assert TAGLINE in text
    assert "1. api-review" in text and "7. security-audit" in text
    assert "(4x)" in text                # usage shown without changing order
    assert "iceni create" in text        # manage actions point to the CLI, not fake flags
    assert "--create" not in text and "--stats" not in text


def test_empty_menu_points_to_pack_install():
    text = _menu([])
    assert "pack install code-quality" in text
