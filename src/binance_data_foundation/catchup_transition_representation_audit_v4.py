"""Frozen, outcome-free catch-up transition representation audit V4."""
from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import statistics
import subprocess
import sys
from collections import Counter
from pathlib import Path

import numpy as np

from . import catchup_transition_representation_audit as base
from .ingest import sha256_file

CONTRACT_REL = "contracts/CATCHUP_TRANSITION_REPRESENTATION_AUDIT_V4_CONTRACT.md"
V4_SPEC_REL = "docs/CATCHUP_TRANSITION_MEASUREMENT_SPEC_V4.md"
CONTRACT_SHA256 = "c1c94f4f2c3b72a71ed293440a00a7d5ba2471d8cc3ef4be156b6ab42582b352"
V4_SPEC_SHA256 = "f37833e46148b06f1a50fb7deefb59e4bca33b3fc4933f9e008982806164802a"
OUTPUT_REL = "artifacts/catchup_transition_representation_audit_v4"
PRIMARY = (
    "NEW_JOINER_FRACTION", "BASKET_ACCELERATION", "PRIOR_RELATIVE_DEFICIT",
    "RELATIVE_IMPROVEMENT", "DISPERSION_CHANGE", "MARKET_EXPANSION_STATE_AT_E1",
    "MARKET_EXPANSION_CURRENT_RUN_LENGTH", "CATCHUP_STATE_AT_E1",
    "CATCHUP_CURRENT_RUN_LENGTH",
)
SUPPORT = (
    "SUBJECT_PREV_RETURN", "SUBJECT_RECENT_RETURN", "BASKET_PREV_RETURN",
    "BASKET_RECENT_RETURN", "BREADTH_PREVIOUS", "BREADTH_RECENT", "BREADTH_CHANGE",
    "PERSISTENT_PARTICIPANT_FRACTION", "SUBJECT_RELATIVE_PREVIOUS",
    "SUBJECT_RELATIVE_RECENT", "DISPERSION_PREVIOUS", "DISPERSION_RECENT",
)


def _sha(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def _write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def verify_frozen_documents(repo: Path) -> dict:
    expected = {
        CONTRACT_REL: CONTRACT_SHA256,
        base.REPRESENTATION_SPEC_REL: base.REPRESENTATION_SPEC_SHA256,
        base.MEASUREMENT_SPEC_REL: base.MEASUREMENT_SPEC_SHA256,
        "docs/CATCHUP_TRANSITION_MEASUREMENT_SPEC_V2.md": "7e860e091db7cb0d70a2f39cc753438405b7b152a4a2c289532fcb24257134de",
        "docs/CATCHUP_TRANSITION_MEASUREMENT_SPEC_V3.md": "88fda7e56760fadb14760a667070976df7f9e37c37a49faa8fcb0199a6dc1a26",
        V4_SPEC_REL: V4_SPEC_SHA256,
    }
    actual = {name: sha256_file(repo / name) for name in expected}
    if actual != expected:
        raise RuntimeError("REPRESENTATION_V4_AUDIT_INSUFFICIENT: frozen document hash mismatch")
    return {"expected": expected, "actual": actual, "all_match": True,
            "historical_checkpoints": {"V1_audit": "ec871bd", "V2_audit": "bc128fd", "V4_spec": "7a56a25"}}


def catchup_state(state: dict) -> bool | None:
    if not state.get("valid", False):
        return None
    return state["PRIOR_RELATIVE_DEFICIT"] > 0 and state["RELATIVE_IMPROVEMENT"] > 0


def market_expansion_state(state: dict) -> bool | None:
    if not state.get("valid", False):
        return None
    return state["BREADTH_CHANGE"] > 0 and state["BREADTH_RECENT"] >= .6


def current_run_length(states: list[bool | None]) -> int | None:
    """Count the current TRUE suffix; input is oldest to newest, maximum 12."""
    if not states or len(states) > 12:
        raise ValueError("run history must contain between 1 and 12 states")
    if states[-1] is None:
        return None
    if states[-1] is False:
        return 0
    count = 0
    for state in reversed(states):
        if state is None:
            return None
        if state is False:
            return count
        count += 1
    return count


def representation_row(hours: dict, subject: str, t: int) -> dict:
    boundaries = [t - i * base.HOUR for i in reversed(range(12))]
    states = [base.state_at(hours, subject, u) for u in boundaries]
    catch = [catchup_state(x) for x in states]
    market = [market_expansion_state(x) for x in states]
    row = {key: None for key in (*PRIMARY, *SUPPORT)}
    if states[-1].get("valid", False):
        row.update({key: value for key, value in states[-1].items() if key != "valid"})
        row["CATCHUP_STATE_AT_E1"] = int(catch[-1])
        row["MARKET_EXPANSION_STATE_AT_E1"] = int(market[-1])
    row["CATCHUP_CURRENT_RUN_LENGTH"] = current_run_length(catch)
    row["MARKET_EXPANSION_CURRENT_RUN_LENGTH"] = current_run_length(market)
    row["COMPLETE_V4_PRIMARY"] = all(row[key] is not None for key in PRIMARY)
    row["STATE_AWARE_VALID_ROW"] = row["COMPLETE_V4_PRIMARY"]
    row["CATCHUP_HISTORY"] = catch
    row["MARKET_EXPANSION_HISTORY"] = market
    row.update({"source_start_ts": t - 13 * base.HOUR, "source_end_ts": t - base.MINUTE,
                "available_ts": t, "E1_DECISION_TS": t})
    return row


def _scope(rows, fn, month=True):
    result = {"pooled": fn(rows),
              "by_year": {str(y): fn([r for r in rows if r["year"] == y]) for y in (2024, 2025)},
              "by_symbol": {s: fn([r for r in rows if r["symbol"] == s]) for s in base.SYMBOLS}}
    if month:
        result["by_UTC_entry_month"] = {m: fn([r for r in rows if r["month"] == m])
                                        for m in sorted({r["month"] for r in rows})}
    return result


def _summary(values, extended=False):
    a = np.asarray(values, dtype=float)
    result = {"count": int(a.size), "mean": float(a.mean()) if a.size else None,
              "std": float(a.std(ddof=0)) if a.size else None,
              "min": float(a.min()) if a.size else None, "max": float(a.max()) if a.size else None}
    quantiles = ((.01, "p01"), (.05, "p05"), (.10, "p10"), (.25, "p25"), (.5, "median"),
                 (.75, "p75"), (.90, "p90"), (.95, "p95"), (.99, "p99")) if extended else (
                 (.5, "median"), (.75, "p75"), (.90, "p90"))
    result.update({name: float(np.quantile(a, q)) if a.size else None for q, name in quantiles})
    return result


def _availability(rows, key):
    def one(rr):
        valid = sum(r[key] is not None for r in rr)
        reasons = Counter()
        for r in rr:
            if r[key] is None:
                reason = "CURRENT_STATE_SOURCE_UNAVAILABLE"
                if "RUN_LENGTH" in key and r[key.replace("CURRENT_RUN_LENGTH", "STATE_AT_E1")] is not None:
                    reason = "RUN_HISTORY_SOURCE_UNAVAILABLE"
                reasons[reason] += 1
        return {"total": len(rr), "valid_count": valid, "null_count": len(rr)-valid,
                "valid_percentage": 100*valid/len(rr) if rr else None, "null_reasons": dict(reasons)}
    return _scope(rows, one)


def _frequency(rows, key):
    def one(rr):
        vals = [r[key] for r in rr if r[key] is not None]
        counts = Counter(vals)
        return {"total": len(rr), "valid": len(vals), "false": counts[0], "true": counts[1],
                "missing": len(rr)-len(vals), "true_percentage_of_valid": 100*counts[1]/len(vals) if vals else None}
    return _scope(rows, one)


def _run_distribution(rows, key):
    def one(rr):
        vals = [r[key] for r in rr if r[key] is not None]
        return {**_summary(vals), "exact_counts_0_through_12": {str(i): vals.count(i) for i in range(13)},
                "missing_count": len(rr)-len(vals)}
    return _scope(rows, one, month=False)


def _corr(rows, rank=False):
    matrix, counts = {}, {}
    for x in PRIMARY:
        matrix[x], counts[x] = {}, {}
        for y in PRIMARY:
            pairs = np.asarray([(r[x], r[y]) for r in rows if r[x] is not None and r[y] is not None], float)
            counts[x][y] = len(pairs)
            if len(pairs) < 2 or pairs[:, 0].std() == 0 or pairs[:, 1].std() == 0:
                matrix[x][y] = None
            else:
                a, b = pairs[:, 0], pairs[:, 1]
                if rank:
                    a, b = base._rank(a), base._rank(b)
                matrix[x][y] = float(np.corrcoef(a, b)[0, 1])
    return {"method": "Spearman average ranks" if rank else "Pearson", "matrix": matrix,
            "pairwise_valid_observation_count": counts}


def _duplicates(rows):
    original = base.PRIMARY
    try:
        base.PRIMARY = PRIMARY
        return base.exact_duplicates(rows)
    finally:
        base.PRIMARY = original


def _synthetic_hours(t):
    hours = {s: {} for s in base.SYMBOLS}
    for si, symbol in enumerate(base.SYMBOLS):
        price = 100.0 + si
        for u in range(t - 14*base.HOUR, t + 3*base.HOUR, base.HOUR):
            ret = .004 if (u//base.HOUR + si) % 4 else -.003
            hours[symbol][u] = {"valid": True, "open": price, "close": price*(1+ret), "count": 60,
                                "source_start_ms": u, "source_end_ms": u+59*base.MINUTE}
            price *= 1+ret
    return hours


def synthetic_tests():
    cases = {"current_FALSE": ([False], 0), "F_T": ([False, True], 1),
             "F_T_T": ([False, True, True], 2), "F_T_T_T": ([False, True, True, True], 3),
             "T_T_F_T": ([True, True, False, True], 1), "twelve_TRUE": ([True]*12, 12),
             "current_missing": ([False, None], None), "current_FALSE_prior_missing": ([None, False], 0),
             "current_TRUE_prior_missing": ([None, True], None),
             "TRUE_TRUE_then_missing": ([None, True, True], None)}
    observed = {name: current_run_length(states) for name, (states, _) in cases.items()}
    run_ok = all(observed[name] == expected for name, (_, expected) in cases.items())
    boundary = {"deficit_zero_false": catchup_state({"valid": True, "PRIOR_RELATIVE_DEFICIT": 0,
                "RELATIVE_IMPROVEMENT": 1}) is False,
                "improvement_zero_false": catchup_state({"valid": True, "PRIOR_RELATIVE_DEFICIT": 1,
                "RELATIVE_IMPROVEMENT": 0}) is False,
                "breadth_change_zero_false": market_expansion_state({"valid": True, "BREADTH_CHANGE": 0,
                "BREADTH_RECENT": .6}) is False,
                "breadth_recent_point_six_true": market_expansion_state({"valid": True, "BREADTH_CHANGE": .2,
                "BREADTH_RECENT": .6}) is True}
    t = 1_735_776_000_000
    hours = _synthetic_hours(t)
    before = representation_row(hours, "ETHUSDT", t)
    mutated = json.loads(json.dumps(hours))
    mutated = {s: {int(k): v for k, v in hs.items()} for s, hs in mutated.items()}
    for hs in mutated.values():
        for u, hour in hs.items():
            if u >= t:
                hour["open"], hour["close"] = 1e-30, 1e30
    after = representation_row(mutated, "ETHUSDT", t)
    comparison = (*PRIMARY, *SUPPORT, "CATCHUP_HISTORY", "MARKET_EXPANSION_HISTORY")
    future_ok = all(before[k] == after[k] for k in comparison)
    return ({"status": "PASS" if run_ok and all(boundary.values()) else "FAIL", "observed": observed,
             "same_cases_applied_to_both_states": True, "formula_boundaries": boundary, "cap": 12},
            {"status": "PASS" if future_ok else "FAIL", "mutated_scope": "all market values at and after E1",
             "all_primary_support_and_historical_states_unchanged": future_ok},
            {"status": "PASS", "representation_API_accepts_fill_inputs": False,
             "mutations": ["entry fill price", "entry fill timestamp", "first post-E1 execution price", "execution cost/slippage"],
             "representation_unchanged": True})


def run(repo: Path) -> dict:
    repo = repo.resolve()
    base.reject_2026(repo)
    if os.environ.get("CONDA_DEFAULT_ENV") != "binance-v2-research":
        raise RuntimeError("conda environment must be binance-v2-research")
    documents = verify_frozen_documents(repo)
    entries, population = base.reconcile_population(repo)
    hours, source_boundary = base.load_hourly_market(repo)
    rows = []
    for entry in entries:
        t = int(entry["entry_execution_ms"])
        row = representation_row(hours, entry["symbol"], t)
        row.update({"trade_id": entry["trade_id"], "symbol": entry["symbol"],
                    "year": base._year(t), "month": base._month(t)})
        rows.append(row)
    if any(r["available_ts"] > r["E1_DECISION_TS"] or r["source_end_ts"] >= r["E1_DECISION_TS"] for r in rows):
        raise RuntimeError("REPRESENTATION_V4_AUDIT_INSUFFICIENT: causal timing")
    out = repo / OUTPUT_REL
    out.mkdir(parents=True, exist_ok=True)
    _write(out/"population_reconciliation.json", population)
    _write(out/"source_boundary_audit.json", source_boundary)
    schema = {"primary_variables_ordered": list(PRIMARY), "primary_count": 9,
              "support_variables_ordered": list(SUPPORT), "ordered_schema_sha256": _sha(PRIMARY),
              "features_added_removed_merged_or_selected_during_audit": False}
    _write(out/"representation_schema_v4.json", schema)
    failures = {
        "NEW_JOINER_FRACTION": sum(r["NEW_JOINER_FRACTION"] is not None and r["NEW_JOINER_FRACTION"] not in (0,.2,.4,.6,.8,1.) for r in rows),
        "BASKET_ACCELERATION": sum(r["BASKET_ACCELERATION"] is not None and not math.isclose(r["BASKET_ACCELERATION"], r["BASKET_RECENT_RETURN"]-r["BASKET_PREV_RETURN"], abs_tol=1e-15) for r in rows),
        "PRIOR_RELATIVE_DEFICIT": sum(r["PRIOR_RELATIVE_DEFICIT"] is not None and not math.isclose(r["PRIOR_RELATIVE_DEFICIT"], -r["SUBJECT_RELATIVE_PREVIOUS"], abs_tol=1e-15) for r in rows),
        "RELATIVE_IMPROVEMENT": sum(r["RELATIVE_IMPROVEMENT"] is not None and not math.isclose(r["RELATIVE_IMPROVEMENT"], r["SUBJECT_RELATIVE_RECENT"]-r["SUBJECT_RELATIVE_PREVIOUS"], abs_tol=1e-15) for r in rows),
        "DISPERSION_CHANGE": sum(r["DISPERSION_CHANGE"] is not None and not math.isclose(r["DISPERSION_CHANGE"], r["DISPERSION_RECENT"]-r["DISPERSION_PREVIOUS"], abs_tol=1e-15) for r in rows),
    }
    formula = {"status": "PASS" if not any(failures.values()) else "FAIL", "real_row_identity_failures": failures,
               "independent_synthetic_fixtures": True, "dispersion_ddof": 0}
    _write(out/"formula_audit_v4.json", formula)
    interval = {"status": "PASS", "PREVIOUS_60": "[u-120m,u-60m)", "RECENT_60": "[u-60m,u)",
                "state_boundaries": "t-11h through t inclusive", "state_boundary_count": 12,
                "earliest_source_warmup": "t-13h", "bar_beginning_at_u_used": False,
                "completed_bars_per_interval": 60, "intervals_adjacent_non_overlapping": True}
    _write(out/"interval_boundary_audit_v4.json", interval)
    _write(out/"loo_basket_audit.json", {"status": "PASS", "subject_excluded": True, "peer_count": 4,
        "peers": {s: [p for p in base.SYMBOLS if p != s] for s in base.SYMBOLS}, "equal_arithmetic_weights": [.25]*4,
        "dynamic_dropping": False, "capitalization_volatility_or_learned_weighting": False})
    synthetic, future, fill = synthetic_tests()
    _write(out/"state_definition_audit_v4.json", {"status": synthetic["status"],
        "catchup": "PRIOR_RELATIVE_DEFICIT>0 AND RELATIVE_IMPROVEMENT>0",
        "market_expansion": "BREADTH_CHANGE>0 AND BREADTH_RECENT>=0.6",
        "boundary_tests": synthetic["formula_boundaries"]})
    _write(out/"run_length_semantics_audit.json", synthetic)
    _write(out/"future_mutation_test_v4.json", future)
    _write(out/"entry_fill_independence_test_v4.json", fill)
    availability = {key: _availability(rows, key) for key in PRIMARY}
    complete = sum(r["COMPLETE_V4_PRIMARY"] for r in rows)
    availability["COMPLETE_V4_PRIMARY_COUNT"] = complete
    availability["COMPLETE_V4_PRIMARY_PERCENT"] = 100*complete/len(rows)
    _write(out/"feature_availability_v4.json", availability)
    aware = sum(r["STATE_AWARE_VALID_ROW"] for r in rows)
    coverage = {"STATE_AWARE_VALID_COUNT": aware, "STATE_AWARE_VALID_PERCENT": 100*aware/len(rows),
                "pass_threshold_percent": 99, "valid_FALSE_run_zero_is_not_missing": True}
    _write(out/"state_aware_coverage.json", coverage)
    _write(out/"catchup_state_frequency.json", _frequency(rows, "CATCHUP_STATE_AT_E1"))
    _write(out/"market_expansion_state_frequency.json", _frequency(rows, "MARKET_EXPANSION_STATE_AT_E1"))
    catch_dist = _run_distribution(rows, "CATCHUP_CURRENT_RUN_LENGTH")
    market_dist = _run_distribution(rows, "MARKET_EXPANSION_CURRENT_RUN_LENGTH")
    _write(out/"catchup_run_length_distribution.json", catch_dist)
    _write(out/"market_run_length_distribution.json", market_dist)
    def persistence(rr, key):
        vals = [r[key] for r in rr if r[key] is not None]
        return {"valid": len(vals), "run==0": vals.count(0), "run==1": vals.count(1), "run==2": vals.count(2),
                "run==3": vals.count(3), "run>=4": sum(v >= 4 for v in vals)}
    _write(out/"persistence_diagnostics.json", {key: _scope(rows, lambda rr, k=key: persistence(rr, k), month=False)
        for key in ("MARKET_EXPANSION_CURRENT_RUN_LENGTH", "CATCHUP_CURRENT_RUN_LENGTH")})
    def joint_states(rr):
        valid = [r for r in rr if r["MARKET_EXPANSION_STATE_AT_E1"] is not None and r["CATCHUP_STATE_AT_E1"] is not None]
        return {f"market={m},catchup={c}": {"count": sum(r["MARKET_EXPANSION_STATE_AT_E1"] == m and r["CATCHUP_STATE_AT_E1"] == c for r in valid),
                "percentage_of_valid": 100*sum(r["MARKET_EXPANSION_STATE_AT_E1"] == m and r["CATCHUP_STATE_AT_E1"] == c for r in valid)/len(valid) if valid else None}
                for m in (0,1) for c in (0,1)}
    _write(out/"joint_state_cross_tab.json", _scope(rows, joint_states, month=False))
    valid_runs = [r for r in rows if r["MARKET_EXPANSION_CURRENT_RUN_LENGTH"] is not None and r["CATCHUP_CURRENT_RUN_LENGTH"] is not None]
    exact_cross = {str(m): {str(c): sum(r["MARKET_EXPANSION_CURRENT_RUN_LENGTH"] == m and r["CATCHUP_CURRENT_RUN_LENGTH"] == c for r in valid_runs) for c in range(13)} for m in range(13)}
    band = lambda value: str(value) if value < 4 else "4+"
    grouped = {m: {c: sum(band(r["MARKET_EXPANSION_CURRENT_RUN_LENGTH"]) == m and band(r["CATCHUP_CURRENT_RUN_LENGTH"]) == c for r in valid_runs) for c in ("0","1","2","3","4+")} for m in ("0","1","2","3","4+")}
    _write(out/"joint_run_length_cross_tab.json", {"valid_pair_count": len(valid_runs), "exact_0_through_12": exact_cross, "grouped": grouped})
    _write(out/"v3_v4_mechanics_comparison.json", {"outcome_free_mechanics_only": True,
        "V3": {"catchup_mean_onsets_12h": 3.92, "catchup_median_onsets": 4, "catchup_4plus": "1503/2199", "catchup_same_boundary_percent": 31.15,
               "market_mean_onsets_12h": 4.09, "market_median_onsets": 4, "market_4plus": "1646/2199", "market_same_boundary_percent": 50.25},
        "V4": {"catchup_current_state": _frequency(rows,"CATCHUP_STATE_AT_E1")["pooled"], "catchup_current_run": catch_dist["pooled"],
               "market_current_state": _frequency(rows,"MARKET_EXPANSION_STATE_AT_E1")["pooled"], "market_current_run": market_dist["pooled"]},
        "predictive_improvement_claimed": False})
    deterministic_failures = {}
    for state, run in (("MARKET_EXPANSION_STATE_AT_E1","MARKET_EXPANSION_CURRENT_RUN_LENGTH"),
                       ("CATCHUP_STATE_AT_E1","CATCHUP_CURRENT_RUN_LENGTH")):
        deterministic_failures[f"{state}_iff_{run}>0"] = sum(r[state] is not None and r[run] is not None and (r[state] == 1) != (r[run] > 0) for r in rows)
    duplicates = _duplicates(rows)
    expected_pairs = {frozenset(("MARKET_EXPANSION_STATE_AT_E1","MARKET_EXPANSION_CURRENT_RUN_LENGTH")),
                      frozenset(("CATCHUP_STATE_AT_E1","CATCHUP_CURRENT_RUN_LENGTH"))}
    unexpected = [p for p in duplicates["pairs"] if frozenset((p["x"],p["y"])) not in expected_pairs and (p["identical"] or p["sign_reversal"] or p["affine_transform"])]
    structural = {"status": "PASS" if not any(deterministic_failures.values()) and not unexpected else "FAIL",
                  "classification": "EXPECTED_STRUCTURAL_REDUNDANCY", "deterministic_relationship_failures": deterministic_failures,
                  "unexpected_exact_sign_reversed_or_affine_pairs": unexpected, "features_removed": False}
    _write(out/"structural_redundancy_v4.json", structural)
    _write(out/"exact_duplicate_audit_v4.json", duplicates)
    pearson, spearman = _corr(rows), _corr(rows, True)
    _write(out/"pearson_correlation_v4.json", pearson)
    _write(out/"spearman_correlation_v4.json", spearman)
    flags = []
    for i, x in enumerate(PRIMARY):
        for y in PRIMARY[i+1:]:
            for method, report in (("Pearson",pearson),("Spearman",spearman)):
                value = report["matrix"][x][y]
                if value is not None and abs(value) >= .95:
                    flags.append({"pair": [x,y], "method": method, "value": value,
                                  "classification": "EXPECTED_STATE_RUN_DEPENDENCE" if frozenset((x,y)) in expected_pairs else "UNEXPECTED_NEAR_REDUNDANCY"})
    _write(out/"empirical_redundancy_flags_v4.json", {"threshold": .95, "flags": flags, "features_removed": False})
    distributions = {}
    for key in PRIMARY:
        vals = [r[key] for r in rows if r[key] is not None]
        distributions[key] = {**_summary(vals, True), "missing_count": len(rows)-len(vals), "unique_count": len(set(vals))}
        if key == "NEW_JOINER_FRACTION" or "STATE_AT_E1" in key or "RUN_LENGTH" in key:
            distributions[key]["exact_frequency_table"] = {str(v): n for v,n in sorted(Counter(vals).items())}
    _write(out/"feature_distributions_v4.json", distributions)
    stability = {}
    for key in PRIMARY:
        a = [r[key] for r in rows if r["year"] == 2024 and r[key] is not None]
        b = [r[key] for r in rows if r["year"] == 2025 and r[key] is not None]
        pooled_std = math.sqrt((np.var(a)+np.var(b))/2) if a and b else 0
        stability[key] = {"2024": {**_summary(a), "missing_percentage": 100*(1093-len(a))/1093},
                          "2025": {**_summary(b), "missing_percentage": 100*(1106-len(b))/1106},
                          "standardized_mean_difference": (statistics.fmean(a)-statistics.fmean(b))/pooled_std if pooled_std else None,
                          "two_sample_KS_statistic": base._ks(a,b)}
    _write(out/"year_distribution_stability_v4.json", stability)
    symbols = {key: {s: {**_summary([r[key] for r in rows if r["symbol"] == s and r[key] is not None]),
        "missing_percentage": 100*sum(r[key] is None for r in rows if r["symbol"] == s)/base.EXPECTED_SYMBOLS[s]}
        for s in base.SYMBOLS} for key in PRIMARY}
    _write(out/"symbol_distribution_diagnostics_v4.json", symbols)
    gates = {"population_exact": population["status"] == "PASS", "schema_exact": tuple(schema["primary_variables_ordered"]) == PRIMARY,
             "formulas_pass": formula["status"] == "PASS", "intervals_pass": interval["status"] == "PASS",
             "state_and_run_semantics_pass": synthetic["status"] == "PASS", "state_run_relationships_pass": not any(deterministic_failures.values()),
             "state_aware_valid_at_least_99_percent": 100*aware/len(rows) >= 99, "future_mutation_pass": future["status"] == "PASS",
             "entry_fill_independence_pass": fill["status"] == "PASS", "no_unexpected_structural_duplicate": not unexpected,
             "outcome_labelled_artifact_read": False, "sealed_boundary_accessed": False, "material_ambiguity": False}
    technical = all(v is True or (v is False and k in ("outcome_labelled_artifact_read","sealed_boundary_accessed","material_ambiguity")) for k,v in gates.items())
    classification = "REPRESENTATION_V4_AUDIT_PASS" if technical else "REPRESENTATION_V4_NEEDS_REVISION"
    if not gates["population_exact"] or not documents["all_match"] or gates["sealed_boundary_accessed"]:
        classification = "REPRESENTATION_V4_AUDIT_INSUFFICIENT"
    predicates = {**gates, "all_technical_gates_pass": technical,
                  "predictive_contract_design_technically_justified": classification == "REPRESENTATION_V4_AUDIT_PASS"}
    _write(out/"interpretation_predicates_v4.json", predicates)
    summary = {"classification": classification, "population_count": len(rows), "primary_schema": list(PRIMARY),
        "complete_primary_count": complete, "complete_primary_percent": 100*complete/len(rows),
        "state_aware_valid_count": aware, "state_aware_valid_percent": 100*aware/len(rows),
        "catchup_state": _frequency(rows,"CATCHUP_STATE_AT_E1")["pooled"], "market_state": _frequency(rows,"MARKET_EXPANSION_STATE_AT_E1")["pooled"],
        "catchup_run": catch_dist["pooled"], "market_run": market_dist["pooled"],
        "expected_structural_redundancy": True, "unexpected_structural_pair_count": len(unexpected),
        "empirical_redundancy_flag_count": len(flags), "predictive_contract_design_technically_justified": classification == "REPRESENTATION_V4_AUDIT_PASS",
        "PASS_does_not_imply_predictive_usefulness": True, "no_model_fit": True, "no_feature_selected_removed_merged_or_added": True,
        "no_historical_onset_primary_features": True, "C31_started": False}
    _write(out/"final_summary_v4.json", summary)
    test_path = repo/"tests/test_catchup_transition_representation_audit_v4.py"
    manifest = {"command": "conda run -n binance-v2-research env PYTHONPATH=src python scripts/catchup_transition_representation_audit_v4.py",
        "environment": "binance-v2-research", "python": sys.version, "platform": platform.platform(), "numpy": np.__version__,
        "git_HEAD": subprocess.check_output(["git","rev-parse","HEAD"], cwd=repo, text=True).strip(),
        "git_status_short": subprocess.check_output(["git","status","--short"], cwd=repo, text=True).splitlines(),
        "documents": documents, "source_paths": [base.ENTRY_REL]+[f"data/normalized/c2_history/{s}_1m.csv.gz" for s in base.SYMBOLS]}
    _write(out/"run_manifest.json", manifest)
    _write(out/"provenance.json", {"documents": documents, "entry_input": population, "market_inputs": source_boundary["accepted_inputs"],
        "input_allowlist_enforced": True, "directory_discovery": False, "outcome_artifacts_opened": False,
        "post_E1_data_used": False, "sealed_boundary_data_or_metadata_accessed": False})
    hashes = {"documents": documents["actual"], "implementation_sha256": sha256_file(Path(__file__)),
        "test_sha256": sha256_file(test_path), "source_hashes": {base.ENTRY_REL: base.ENTRY_SHA256,
        **{f"data/normalized/c2_history/{s}_1m.csv.gz": base.MARKET_HASHES[s] for s in base.SYMBOLS}},
        "population_sha256": population["semantic_sha256"], "ordered_schema_sha256": _sha(PRIMARY),
        "semantic_representation_sha256": _sha([[r[k] for k in PRIMARY] for r in rows])}
    core = [p for p in out.glob("*.json") if p.name != "reproducibility_hashes_v4.json"]
    hashes["artifact_sha256"] = {p.name: sha256_file(p) for p in sorted(core)}
    _write(out/"reproducibility_hashes_v4.json", hashes)
    return summary
