from pathlib import Path
import inspect

import pytest

from binance_data_foundation import catchup_transition_representation_audit as base
from binance_data_foundation import catchup_transition_representation_audit_v4 as audit


def _hours(t, returns=None):
    returns = returns or {}
    out = {s: {} for s in base.SYMBOLS}
    for symbol in base.SYMBOLS:
        price = 100.0
        for u in range(t-14*base.HOUR, t+2*base.HOUR, base.HOUR):
            value = returns.get((symbol,u), returns.get(u, 0.0))
            out[symbol][u] = {"valid": True, "open": price, "close": price*(1+value), "count": 60,
                              "source_start_ms": u, "source_end_ms": u+59*base.MINUTE}
            price *= 1+value
    return out


def test_frozen_hashes_population_schema_and_peers():
    assert audit.verify_frozen_documents(Path.cwd())["all_match"]
    entries, rec = base.reconcile_population(Path.cwd())
    assert len(entries) == 2199 and rec["semantic_sha256"] == base.ENTRY_SHA256
    assert rec["year_counts"] == {"2024": 1093, "2025": 1106}
    assert rec["symbol_counts"] == base.EXPECTED_SYMBOLS
    assert audit.PRIMARY == ("NEW_JOINER_FRACTION", "BASKET_ACCELERATION", "PRIOR_RELATIVE_DEFICIT", "RELATIVE_IMPROVEMENT", "DISPERSION_CHANGE", "MARKET_EXPANSION_STATE_AT_E1", "MARKET_EXPANSION_CURRENT_RUN_LENGTH", "CATCHUP_STATE_AT_E1", "CATCHUP_CURRENT_RUN_LENGTH")
    assert {s: len([p for p in base.SYMBOLS if p != s]) for s in base.SYMBOLS} == {s: 4 for s in base.SYMBOLS}


def test_formula_state_boundaries_and_intervals():
    t = 1_735_776_000_000
    prev = dict(zip(base.SYMBOLS, (.01,-.02,.03,.04,.05)))
    recent = dict(zip(base.SYMBOLS, (.02,.01,.06,.08,.10)))
    h = _hours(t, {(s,t-2*base.HOUR): prev[s] for s in base.SYMBOLS} | {(s,t-base.HOUR): recent[s] for s in base.SYMBOLS})
    x = base.state_at(h, "BTCUSDT", t)
    peers = [s for s in base.SYMBOLS if s != "BTCUSDT"]
    assert x["BASKET_PREV_RETURN"] == pytest.approx(sum(prev[s] for s in peers)/4)
    assert x["NEW_JOINER_FRACTION"] == pytest.approx(.2)
    assert x["BASKET_ACCELERATION"] == pytest.approx(x["BASKET_RECENT_RETURN"]-x["BASKET_PREV_RETURN"])
    assert x["PRIOR_RELATIVE_DEFICIT"] == pytest.approx(-(x["SUBJECT_PREV_RETURN"]-x["BASKET_PREV_RETURN"]))
    assert x["RELATIVE_IMPROVEMENT"] == pytest.approx(x["SUBJECT_RELATIVE_RECENT"]-x["SUBJECT_RELATIVE_PREVIOUS"])
    assert x["DISPERSION_CHANGE"] == pytest.approx(x["DISPERSION_RECENT"]-x["DISPERSION_PREVIOUS"])
    assert audit.catchup_state({"valid": True, "PRIOR_RELATIVE_DEFICIT": 0, "RELATIVE_IMPROVEMENT": 1}) is False
    assert audit.market_expansion_state({"valid": True, "BREADTH_CHANGE": .2, "BREADTH_RECENT": .6}) is True


def test_run_length_and_missing_semantics_for_both_states():
    cases = [([False],0), ([False,True],1), ([False,True,True],2), ([False,True,True,True],3),
             ([True,True,False,True],1), ([True]*12,12), ([None],None), ([None,False],0),
             ([None,True],None), ([None,True,True],None)]
    for states, expected in cases:
        assert audit.current_run_length(states) == expected
    report, _, _ = audit.synthetic_tests()
    assert report["status"] == "PASS" and report["same_cases_applied_to_both_states"]


def test_representation_state_run_relationship_and_gap_handling():
    t = 1_735_776_000_000
    h = _hours(t)
    row = audit.representation_row(h, "ETHUSDT", t)
    assert row["CATCHUP_STATE_AT_E1"] == 0 and row["CATCHUP_CURRENT_RUN_LENGTH"] == 0
    assert row["MARKET_EXPANSION_STATE_AT_E1"] == 0 and row["MARKET_EXPANSION_CURRENT_RUN_LENGTH"] == 0
    h["BTCUSDT"][t-3*base.HOUR]["valid"] = False
    row = audit.representation_row(h, "ETHUSDT", t)
    assert row["CATCHUP_CURRENT_RUN_LENGTH"] == 0
    assert row["MARKET_EXPANSION_CURRENT_RUN_LENGTH"] == 0


def test_future_fill_firewalls_duplicates_and_determinism():
    _, future, fill = audit.synthetic_tests()
    assert future["status"] == fill["status"] == "PASS"
    with pytest.raises(PermissionError):
        base.reject_2026("forbidden/year=" + "20" + "26/x")
    with pytest.raises(PermissionError):
        base._firewall(["GROSS" + "40_label"])
    source = inspect.getsource(audit)
    assert "sklearn" not in source and ".fit(" not in source
    rows = [{k: float(i+j) for j,k in enumerate(audit.PRIMARY)} for i in range(5)]
    assert audit._corr(rows) == audit._corr(rows)
    assert audit._duplicates(rows) == audit._duplicates(rows)
