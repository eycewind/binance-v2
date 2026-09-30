from pathlib import Path
import inspect

import pytest

from binance_data_foundation import catchup_transition_representation_audit as base
from binance_data_foundation import catchup_transition_representation_audit_v3 as audit


def _hours(t, returns=None):
    returns = returns or {}
    out = {s: {} for s in base.SYMBOLS}
    for symbol in base.SYMBOLS:
        price = 100.0
        for u in range(t-16*base.HOUR, t+2*base.HOUR, base.HOUR):
            r = returns.get((symbol, u), returns.get(u, 0.0))
            out[symbol][u] = {"valid": True, "open": price, "close": price*(1+r), "count": 60,
                              "source_start_ms": u, "source_end_ms": u+59*base.MINUTE}
            price *= 1+r
    return out


def test_frozen_hashes_population_schema_universe_and_peers():
    assert audit.verify_frozen_documents(Path.cwd())["all_match"]
    entries, rec = base.reconcile_population(Path.cwd())
    assert len(entries) == 2199 and rec["semantic_sha256"] == base.ENTRY_SHA256
    assert rec["year_counts"] == {"2024": 1093, "2025": 1106}
    assert rec["symbol_counts"] == base.EXPECTED_SYMBOLS
    assert audit.PRIMARY == ("NEW_JOINER_FRACTION", "BASKET_ACCELERATION", "PRIOR_RELATIVE_DEFICIT", "RELATIVE_IMPROVEMENT", "DISPERSION_CHANGE", "MINUTES_SINCE_MARKET_EXPANSION_ONSET", "MINUTES_SINCE_CATCHUP_ONSET", "CATCHUP_ONSET_RELATIVE_IMPROVEMENT")
    assert all(len([p for p in base.SYMBOLS if p != s]) == 4 for s in base.SYMBOLS)


def test_formulae_states_leave_one_out_and_non_overlapping_intervals():
    t = 1_735_776_000_000
    prev = dict(zip(base.SYMBOLS, (.01, -.02, .03, .04, .05)))
    recent = dict(zip(base.SYMBOLS, (.02, .01, .06, .08, .10)))
    h = _hours(t, {(s, t-2*base.HOUR): prev[s] for s in base.SYMBOLS} | {(s, t-base.HOUR): recent[s] for s in base.SYMBOLS})
    x = base.state_at(h, "BTCUSDT", t); peers = [s for s in base.SYMBOLS if s != "BTCUSDT"]
    assert x["BASKET_PREV_RETURN"] == pytest.approx(sum(prev[s] for s in peers)/4)
    assert x["NEW_JOINER_FRACTION"] == pytest.approx(.2)
    assert x["BASKET_ACCELERATION"] == pytest.approx(x["BASKET_RECENT_RETURN"]-x["BASKET_PREV_RETURN"])
    assert x["PRIOR_RELATIVE_DEFICIT"] == pytest.approx(-(x["SUBJECT_PREV_RETURN"]-x["BASKET_PREV_RETURN"]))
    assert x["RELATIVE_IMPROVEMENT"] == pytest.approx(x["SUBJECT_RELATIVE_RECENT"]-x["SUBJECT_RELATIVE_PREVIOUS"])
    assert x["DISPERSION_CHANGE"] == pytest.approx(x["DISPERSION_RECENT"]-x["DISPERSION_PREVIOUS"])
    assert audit.catchup_state(x) == (x["PRIOR_RELATIVE_DEFICIT"] > 0 and x["RELATIVE_IMPROVEMENT"] > 0)
    assert audit.market_expansion_state(x) == (x["BREADTH_CHANGE"] > 0 and x["BREADTH_RECENT"] >= .6)


def test_transition_episode_semantics_for_both_states():
    cases = [([False, False], 0), ([False, True], 1), ([False, True, True], 1),
             ([False, True, False], 1), ([False, True, False, True], 2), ([True, True], 0)]
    for states, expected in cases:
        assert len(audit.transition_onsets(states, list(range(len(states))))) == expected
    transition, _, _ = audit.synthetic_tests()
    assert transition["status"] == "PASS" and transition["catchup"] == transition["market_expansion"]


def test_search_boundaries_recent_selection_magnitude_null_and_gap():
    t = 1_735_776_000_000; h = _hours(t)
    # Construct catch-up states at t-12h and t with false states immediately before each.
    subject = "ETHUSDT"
    for u in (t-12*base.HOUR, t):
        h[subject][u-2*base.HOUR]["close"] = h[subject][u-2*base.HOUR]["open"]*.98
        h[subject][u-base.HOUR]["close"] = h[subject][u-base.HOUR]["open"]*1.02
    row = audit.representation_row(h, subject, t)
    assert row["CATCHUP_ONSET_DETECTED_TS"] == t
    assert row["MINUTES_SINCE_CATCHUP_ONSET"] == 0
    assert row["CATCHUP_ONSET_RELATIVE_IMPROVEMENT"] > 0
    assert row["CATCHUP_ONSET_COUNT_12H"] >= 1
    blank = audit.representation_row(_hours(t), subject, t)
    assert blank["CATCHUP_ONSET_DETECTED_TS"] is None and blank["CATCHUP_ONSET_NULL_REASON"] == audit.NO_ONSET
    gap = _hours(t); gap["BTCUSDT"][t-15*base.HOUR]["valid"] = False
    failed = audit.representation_row(gap, subject, t)
    assert not failed["STATE_AWARE_VALID_ROW"] and failed["CATCHUP_ONSET_NULL_REASON"] == audit.SOURCE_FAILURE


def test_future_mutation_fill_independence_firewalls_and_determinism():
    transition, future, fill = audit.synthetic_tests()
    assert transition["status"] == future["status"] == fill["status"] == "PASS"
    with pytest.raises(PermissionError): base.reject_2026("forbidden/year=2026/x")
    with pytest.raises(PermissionError): base._firewall(["GROSS40_label"])
    source = inspect.getsource(audit)
    assert "sklearn" not in source and ".fit(" not in source
    rows = [{k: float(i+j) for j, k in enumerate(audit.PRIMARY)} for i in range(5)]
    assert audit._corr(rows) == audit._corr(rows)
    assert audit._duplicates(rows) == audit._duplicates(rows)
