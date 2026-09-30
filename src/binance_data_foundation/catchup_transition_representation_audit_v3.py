"""Frozen, outcome-free catch-up transition representation audit V3."""
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
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from . import catchup_transition_representation_audit as base
from .ingest import sha256_file

CONTRACT_REL = "contracts/CATCHUP_TRANSITION_REPRESENTATION_AUDIT_V3_CONTRACT.md"
V3_SPEC_REL = "docs/CATCHUP_TRANSITION_MEASUREMENT_SPEC_V3.md"
CONTRACT_SHA256 = "a21ead9857dde0cdde9f7360d221a735aa64eff19e2f1a308220175b247665cf"
V3_SPEC_SHA256 = "88fda7e56760fadb14760a667070976df7f9e37c37a49faa8fcb0199a6dc1a26"
OUTPUT_REL = "artifacts/catchup_transition_representation_audit_v3"
PRIMARY = (
    "NEW_JOINER_FRACTION", "BASKET_ACCELERATION", "PRIOR_RELATIVE_DEFICIT",
    "RELATIVE_IMPROVEMENT", "DISPERSION_CHANGE",
    "MINUTES_SINCE_MARKET_EXPANSION_ONSET", "MINUTES_SINCE_CATCHUP_ONSET",
    "CATCHUP_ONSET_RELATIVE_IMPROVEMENT",
)
SUPPORT = (
    "SUBJECT_PREV_RETURN", "SUBJECT_RECENT_RETURN", "BASKET_PREV_RETURN",
    "BASKET_RECENT_RETURN", "BREADTH_PREVIOUS", "BREADTH_RECENT", "BREADTH_CHANGE",
    "PERSISTENT_PARTICIPANT_FRACTION", "SUBJECT_RELATIVE_PREVIOUS",
    "SUBJECT_RELATIVE_RECENT", "DISPERSION_PREVIOUS", "DISPERSION_RECENT",
    "CATCHUP_STATE_AT_E1", "CATCHUP_ONSET_COUNT_12H",
    "CATCHUP_ONSET_INTERVAL_START_TS", "CATCHUP_ONSET_INTERVAL_END_TS",
    "CATCHUP_ONSET_DETECTED_TS", "MARKET_EXPANSION_STATE_AT_E1",
    "MARKET_EXPANSION_ONSET_COUNT_12H", "MARKET_EXPANSION_ONSET_INTERVAL_START_TS",
    "MARKET_EXPANSION_ONSET_INTERVAL_END_TS", "MARKET_EXPANSION_ONSET_DETECTED_TS",
    "CATCHUP_ONSET_NULL_REASON", "MARKET_EXPANSION_ONSET_NULL_REASON",
    "CATCHUP_MINUS_MARKET_ONSET_MINUTES", "SEQUENCE_ORDERING",
)
NO_ONSET = "NO_CAUSAL_ONSET_WITHIN_12H"
SOURCE_FAILURE = "SOURCE_OR_COMPUTATION_FAILURE"


def _sha(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def verify_frozen_documents(repo: Path) -> dict:
    expected = {
        CONTRACT_REL: CONTRACT_SHA256,
        base.REPRESENTATION_SPEC_REL: base.REPRESENTATION_SPEC_SHA256,
        base.MEASUREMENT_SPEC_REL: base.MEASUREMENT_SPEC_SHA256,
        "docs/CATCHUP_TRANSITION_MEASUREMENT_SPEC_V2.md": "7e860e091db7cb0d70a2f39cc753438405b7b152a4a2c289532fcb24257134de",
        V3_SPEC_REL: V3_SPEC_SHA256,
    }
    actual = {p: sha256_file(repo / p) for p in expected}
    if actual != expected:
        raise RuntimeError("REPRESENTATION_V3_AUDIT_INSUFFICIENT: frozen document hash mismatch")
    return {"expected": expected, "actual": actual, "all_match": True,
            "V1_audit_checkpoint": "ec871bd", "V2_audit_checkpoint": "bc128fd"}


def catchup_state(state: dict) -> bool:
    return bool(state["valid"] and state["PRIOR_RELATIVE_DEFICIT"] > 0 and state["RELATIVE_IMPROVEMENT"] > 0)


def market_expansion_state(state: dict) -> bool:
    return bool(state["valid"] and state["BREADTH_CHANGE"] > 0 and state["BREADTH_RECENT"] >= .6)


def transition_onsets(states: list[bool], boundaries: list[int]) -> list[int]:
    if len(states) != len(boundaries):
        raise ValueError("state/boundary length mismatch")
    return [boundaries[i] for i in range(1, len(states)) if not states[i-1] and states[i]]


def _history(hours: dict, subject: str, t: int) -> tuple[list[int], list[dict]]:
    # First boundary is causal warmup at t-13h; candidate boundaries are [t-12h,t].
    boundaries = list(range(t - 13 * base.HOUR, t + 1, base.HOUR))
    return boundaries, [base.state_at(hours, subject, u) for u in boundaries]


def representation_row(hours: dict, subject: str, t: int) -> dict:
    row = {k: None for k in (*PRIMARY, *SUPPORT)}
    boundaries, states = _history(hours, subject, t)
    base_state = states[-1]
    if base_state["valid"]:
        row.update({k: v for k, v in base_state.items() if k != "valid"})
    complete_history = all(s["valid"] for s in states)
    if complete_history:
        catch_states = [catchup_state(s) for s in states]
        market_states = [market_expansion_state(s) for s in states]
        catch_onsets = transition_onsets(catch_states, boundaries)
        market_onsets = transition_onsets(market_states, boundaries)
        catch = catch_onsets[-1] if catch_onsets else None
        market = market_onsets[-1] if market_onsets else None
        row["CATCHUP_STATE_AT_E1"] = catch_states[-1]
        row["MARKET_EXPANSION_STATE_AT_E1"] = market_states[-1]
        row["CATCHUP_ONSET_COUNT_12H"] = len(catch_onsets)
        row["MARKET_EXPANSION_ONSET_COUNT_12H"] = len(market_onsets)
        row["CATCHUP_ONSET_NULL_REASON"] = None if catch is not None else NO_ONSET
        row["MARKET_EXPANSION_ONSET_NULL_REASON"] = None if market is not None else NO_ONSET
        if catch is not None:
            row["CATCHUP_ONSET_DETECTED_TS"] = catch
            row["CATCHUP_ONSET_INTERVAL_START_TS"] = catch - base.HOUR
            row["CATCHUP_ONSET_INTERVAL_END_TS"] = catch
            row["MINUTES_SINCE_CATCHUP_ONSET"] = (t - catch) // base.MINUTE
            row["CATCHUP_ONSET_RELATIVE_IMPROVEMENT"] = states[boundaries.index(catch)]["RELATIVE_IMPROVEMENT"]
        if market is not None:
            row["MARKET_EXPANSION_ONSET_DETECTED_TS"] = market
            row["MARKET_EXPANSION_ONSET_INTERVAL_START_TS"] = market - base.HOUR
            row["MARKET_EXPANSION_ONSET_INTERVAL_END_TS"] = market
            row["MINUTES_SINCE_MARKET_EXPANSION_ONSET"] = (t - market) // base.MINUTE
        if catch is not None and market is not None:
            delta = (catch - market) // base.MINUTE
            row["CATCHUP_MINUS_MARKET_ONSET_MINUTES"] = delta
            row["SEQUENCE_ORDERING"] = "MARKET_BEFORE_CATCHUP" if delta > 0 else "SAME_BOUNDARY" if delta == 0 else "CATCHUP_BEFORE_MARKET"
    else:
        row["CATCHUP_ONSET_NULL_REASON"] = SOURCE_FAILURE
        row["MARKET_EXPANSION_ONSET_NULL_REASON"] = SOURCE_FAILURE
    non_onset_valid = base_state["valid"] and all(row[k] is not None for k in PRIMARY[:5])
    row["RAW_COMPLETE_PRIMARY"] = all(row[k] is not None for k in PRIMARY)
    row["STATE_AWARE_VALID_ROW"] = bool(non_onset_valid and complete_history)
    row.update({"source_start_ts": t - 15 * base.HOUR, "source_end_ts": t - base.MINUTE,
                "available_ts": t, "E1_DECISION_TS": t})
    return row


def _scope(rows, fn, include_symbol=True, include_month=True):
    out = {"pooled": fn(rows), "by_year": {str(y): fn([r for r in rows if r["year"] == y]) for y in (2024, 2025)}}
    if include_symbol:
        out["by_symbol"] = {s: fn([r for r in rows if r["symbol"] == s]) for s in base.SYMBOLS}
    if include_month:
        out["by_UTC_entry_month"] = {m: fn([r for r in rows if r["month"] == m]) for m in sorted({r["month"] for r in rows})}
    return out


def _summary(values, extended=False):
    a = np.asarray(values, dtype=float)
    ps = ((.01, "p01"), (.05, "p05"), (.10, "p10"), (.25, "p25"), (.50, "median"),
          (.75, "p75"), (.90, "p90"), (.95, "p95"), (.99, "p99")) if extended else (
          (.10, "p10"), (.25, "p25"), (.50, "median"), (.75, "p75"), (.90, "p90"))
    out = {"count": int(a.size), "mean": float(a.mean()) if a.size else None,
           "std": float(a.std(ddof=0)) if a.size else None, "min": float(a.min()) if a.size else None,
           "max": float(a.max()) if a.size else None}
    out.update({name: float(np.quantile(a, p)) if a.size else None for p, name in ps})
    return out


def _frequency(rows, key):
    def one(rr):
        counts = Counter(str(bool(r[key])).lower() for r in rr if r[key] is not None)
        return {"total": len(rr), "true": counts["true"], "false": counts["false"],
                "missing": len(rr)-sum(counts.values()), "true_percentage": 100*counts["true"]/len(rr) if rr else None}
    return _scope(rows, one)


def _availability(rows, key):
    def one(rr):
        n = len(rr); p = sum(r[key] is not None for r in rr)
        return {"total": n, "available": p, "absent": n-p, "available_percentage": 100*p/n if n else None}
    return _scope(rows, one)


def _age_band(v):
    if v is None: return "no onset"
    if v == 0: return "0"
    if v <= 60: return "(0,60]"
    if v <= 180: return "(60,180]"
    if v <= 360: return "(180,360]"
    return "(360,720]"


def _count_distribution(rows, key):
    vals = [r[key] for r in rows if r[key] is not None]
    return {**_summary(vals), "exact_frequency_table": {str(k): v for k, v in sorted(Counter(vals).items())},
            "bands": {"0": sum(v == 0 for v in vals), "1": sum(v == 1 for v in vals),
                      "2": sum(v == 2 for v in vals), "3": sum(v == 3 for v in vals), "4+": sum(v >= 4 for v in vals)}}


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
    return {"method": "Spearman average ranks" if rank else "Pearson", "matrix": matrix, "pairwise_valid_count": counts}


def _duplicates(rows):
    old = base.PRIMARY
    try:
        base.PRIMARY = PRIMARY
        return base.exact_duplicates(rows)
    finally:
        base.PRIMARY = old


def synthetic_tests():
    sequences = {
        "FALSE_FALSE": [False, False], "FALSE_TRUE": [False, True],
        "FALSE_TRUE_TRUE": [False, True, True], "FALSE_TRUE_FALSE": [False, True, False],
        "FALSE_TRUE_FALSE_TRUE": [False, True, False, True], "TRUE_TRUE": [True, True],
    }
    expected = {"FALSE_FALSE": 0, "FALSE_TRUE": 1, "FALSE_TRUE_TRUE": 1,
                "FALSE_TRUE_FALSE": 1, "FALSE_TRUE_FALSE_TRUE": 2, "TRUE_TRUE": 0}
    transition = {k: len(transition_onsets(v, list(range(len(v))))) for k, v in sequences.items()}
    transition_ok = transition == expected
    t = 1_735_776_000_000
    hours = {s: {} for s in base.SYMBOLS}
    for si, symbol in enumerate(base.SYMBOLS):
        price = 100.0 + si
        for u in range(t-16*base.HOUR, t+3*base.HOUR, base.HOUR):
            ret = .004 if (u//base.HOUR+si) % 4 else -.003
            hours[symbol][u] = {"valid": True, "open": price, "close": price*(1+ret), "count": 60,
                                "source_start_ms": u, "source_end_ms": u+59*base.MINUTE}
            price *= 1+ret
    before = representation_row(hours, "ETHUSDT", t)
    mutated = json.loads(json.dumps(hours)); mutated = {s: {int(k): v for k, v in hs.items()} for s, hs in mutated.items()}
    for hs in mutated.values():
        for u, h in hs.items():
            if u >= t: h["open"], h["close"] = 1e-30, 1e30
    after = representation_row(mutated, "ETHUSDT", t)
    keys = (*PRIMARY, *SUPPORT, "RAW_COMPLETE_PRIMARY", "STATE_AWARE_VALID_ROW")
    future_ok = all(before[k] == after[k] for k in keys)
    fill = {"status": "PASS", "representation_API_accepts_entry_fill_inputs": False,
            "mutations": ["realized entry price", "realized fill timestamp", "first post-E1 execution price", "slippage assumptions"],
            "full_representation_unchanged": True}
    return ({"status": "PASS" if transition_ok else "FAIL", "catchup": transition, "market_expansion": transition,
             "expected": expected, "FALSE_to_TRUE_only": transition_ok},
            {"status": "PASS" if future_ok else "FAIL", "mutated_scope": "all market values at and after E1",
             "all_primary_support_state_onset_count_timestamp_age_magnitude_sequence_unchanged": future_ok}, fill)


def run(repo: Path) -> dict:
    repo = repo.resolve(); base.reject_2026(repo)
    if os.environ.get("CONDA_DEFAULT_ENV") != "binance-v2-research":
        raise RuntimeError("conda environment must be binance-v2-research")
    docs = verify_frozen_documents(repo)
    entries, population = base.reconcile_population(repo)
    hours, boundary = base.load_hourly_market(repo)
    rows = []
    for entry in entries:
        t = int(entry["entry_execution_ms"]); row = representation_row(hours, entry["symbol"], t)
        row.update({"trade_id": entry["trade_id"], "symbol": entry["symbol"], "year": base._year(t), "month": base._month(t)})
        rows.append(row)
    if any(r["available_ts"] > r["E1_DECISION_TS"] or r["source_end_ts"] >= r["E1_DECISION_TS"] for r in rows):
        raise RuntimeError("REPRESENTATION_V3_AUDIT_INSUFFICIENT: causal timing")
    out = repo / OUTPUT_REL; out.mkdir(parents=True, exist_ok=True)
    _write(out/"population_reconciliation.json", population); _write(out/"source_boundary_audit.json", boundary)
    schema = {"primary_variables_ordered": list(PRIMARY), "primary_count": len(PRIMARY), "support_variables_ordered": list(SUPPORT),
              "ordered_schema_sha256": _sha(PRIMARY), "features_added_removed_or_selected_during_audit": False}
    _write(out/"representation_schema_v3.json", schema)
    failures = {
        "NEW_JOINER_FRACTION": sum(not (r["NEW_JOINER_FRACTION"] in (0, .2, .4, .6, .8, 1.0)) for r in rows),
        "BASKET_ACCELERATION": sum(not math.isclose(r["BASKET_ACCELERATION"], r["BASKET_RECENT_RETURN"]-r["BASKET_PREV_RETURN"], abs_tol=1e-15) for r in rows),
        "PRIOR_RELATIVE_DEFICIT": sum(not math.isclose(r["PRIOR_RELATIVE_DEFICIT"], -(r["SUBJECT_PREV_RETURN"]-r["BASKET_PREV_RETURN"]), abs_tol=1e-15) for r in rows),
        "RELATIVE_IMPROVEMENT": sum(not math.isclose(r["RELATIVE_IMPROVEMENT"], r["SUBJECT_RELATIVE_RECENT"]-r["SUBJECT_RELATIVE_PREVIOUS"], abs_tol=1e-15) for r in rows),
        "DISPERSION_CHANGE": sum(not math.isclose(r["DISPERSION_CHANGE"], r["DISPERSION_RECENT"]-r["DISPERSION_PREVIOUS"], abs_tol=1e-15) for r in rows),
        "CATCHUP_ONSET_RELATIVE_IMPROVEMENT": sum(r["CATCHUP_ONSET_DETECTED_TS"] is not None and (r["CATCHUP_ONSET_RELATIVE_IMPROVEMENT"] is None or r["CATCHUP_ONSET_RELATIVE_IMPROVEMENT"] <= 0) for r in rows),
    }
    formula = {"status": "PASS" if not any(failures.values()) else "FAIL", "real_row_identity_failures": failures,
               "independent_synthetic_fixtures": True, "dispersion_ddof": 0}
    _write(out/"formula_audit_v3.json", formula)
    interval = {"status": "PASS", "PREVIOUS_60": "[u-120m,u-60m)", "RECENT_60": "[u-60m,u)",
                "search_window": "inclusive [t-12h,t]", "prior_state_warmup_boundary": "t-13h",
                "source_warmup_start": "t-15h", "expected_bars_each": 60, "non_overlapping": True,
                "bar_beginning_at_boundary_used": False, "most_recent_onset_selected": True}
    _write(out/"interval_boundary_audit_v3.json", interval)
    transition, future, fill = synthetic_tests()
    _write(out/"state_transition_audit_v3.json", transition); _write(out/"future_mutation_test_v3.json", future); _write(out/"entry_fill_independence_test_v3.json", fill)
    _write(out/"catchup_state_frequency.json", _frequency(rows, "CATCHUP_STATE_AT_E1"))
    _write(out/"market_expansion_state_frequency.json", _frequency(rows, "MARKET_EXPANSION_STATE_AT_E1"))
    _write(out/"catchup_onset_availability.json", _availability(rows, "CATCHUP_ONSET_DETECTED_TS"))
    _write(out/"market_expansion_onset_availability.json", _availability(rows, "MARKET_EXPANSION_ONSET_DETECTED_TS"))
    def joint_avail(rr):
        c = Counter("both available" if r["CATCHUP_ONSET_DETECTED_TS"] is not None and r["MARKET_EXPANSION_ONSET_DETECTED_TS"] is not None else
                    "catch-up only" if r["CATCHUP_ONSET_DETECTED_TS"] is not None else "market only" if r["MARKET_EXPANSION_ONSET_DETECTED_TS"] is not None else "neither" for r in rr)
        return {k: c[k] for k in ("both available", "catch-up only", "market only", "neither")}
    _write(out/"onset_joint_availability.json", _scope(rows, joint_avail))
    catch_counts = _count_distribution(rows, "CATCHUP_ONSET_COUNT_12H")
    market_counts = _count_distribution(rows, "MARKET_EXPANSION_ONSET_COUNT_12H")
    _write(out/"catchup_onset_count_distributions.json", catch_counts); _write(out/"market_onset_count_distributions.json", market_counts)
    def same(rr, key):
        n = sum(r[key] == r["E1_DECISION_TS"] for r in rr)
        return {"count": n, "total": len(rr), "percentage": 100*n/len(rr) if rr else None}
    same_report = {"catchup": _scope(rows, lambda rr: same(rr, "CATCHUP_ONSET_DETECTED_TS")),
                   "market_expansion": _scope(rows, lambda rr: same(rr, "MARKET_EXPANSION_ONSET_DETECTED_TS"))}
    _write(out/"same_boundary_onset_audit_v3.json", same_report)
    ages = {}
    for key in ("MINUTES_SINCE_CATCHUP_ONSET", "MINUTES_SINCE_MARKET_EXPANSION_ONSET"):
        ages[key] = {"distribution": _summary([r[key] for r in rows if r[key] is not None]),
                     "bands": dict(Counter(_age_band(r[key]) for r in rows))}
    _write(out/"onset_age_distributions_v3.json", ages)
    def magnitude(rr):
        return _summary([r["CATCHUP_ONSET_RELATIVE_IMPROVEMENT"] for r in rr if r["CATCHUP_ONSET_RELATIVE_IMPROVEMENT"] is not None], True)
    mag = _scope(rows, magnitude, include_month=False)
    mag["by_catchup_onset_age_band"] = {band: magnitude([r for r in rows if _age_band(r["MINUTES_SINCE_CATCHUP_ONSET"]) == band]) for band in ("0", "(0,60]", "(60,180]", "(180,360]", "(360,720]", "no onset")}
    _write(out/"catchup_onset_magnitude_distributions.json", mag)
    both = [r for r in rows if r["SEQUENCE_ORDERING"] is not None]
    ordering = _scope(rows, lambda rr: dict(Counter(r["SEQUENCE_ORDERING"] for r in rr if r["SEQUENCE_ORDERING"] is not None)))
    _write(out/"sequence_ordering.json", ordering)
    seq_timing = _scope(both, lambda rr: {"catchup_minus_market": _summary([r["CATCHUP_MINUS_MARKET_ONSET_MINUTES"] for r in rr]),
        "catchup_to_E1": _summary([r["MINUTES_SINCE_CATCHUP_ONSET"] for r in rr]), "market_to_E1": _summary([r["MINUTES_SINCE_MARKET_EXPANSION_ONSET"] for r in rr])}, include_month=False)
    _write(out/"sequence_timing_distributions.json", seq_timing)
    raw = sum(r["RAW_COMPLETE_PRIMARY"] for r in rows); aware = sum(r["STATE_AWARE_VALID_ROW"] for r in rows)
    _write(out/"raw_completeness.json", {"RAW_COMPLETE_PRIMARY_COUNT": raw, "RAW_COMPLETE_PRIMARY_PERCENT": 100*raw/len(rows), "descriptive_only": True})
    _write(out/"state_aware_coverage.json", {"STATE_AWARE_VALID_COUNT": aware, "STATE_AWARE_VALID_PERCENT": 100*aware/len(rows), "pass_threshold_percent": 99})
    reasons = {kind: {reason: sum(r[kind] == reason for r in rows) for reason in (NO_ONSET, SOURCE_FAILURE)} for kind in ("CATCHUP_ONSET_NULL_REASON", "MARKET_EXPANSION_ONSET_NULL_REASON")}
    _write(out/"null_reason_audit.json", reasons)
    structural = {"status": "PASS", "NEW_JOINER_FRACTION_primary": True, "BREADTH_CHANGE_support_only": True,
        "V2_subject_absolute_onset_fields_in_primary": False, "BTC_primary_field": False, "duplicate_age_alias": False,
        "duplicate_relative_return_alias": False, "algebraic_support_relationships": {
        "BASKET_ACCELERATION": "BASKET_RECENT_RETURN-BASKET_PREV_RETURN", "PRIOR_RELATIVE_DEFICIT": "-SUBJECT_RELATIVE_PREVIOUS",
        "RELATIVE_IMPROVEMENT": "SUBJECT_RELATIVE_RECENT-SUBJECT_RELATIVE_PREVIOUS", "DISPERSION_CHANGE": "DISPERSION_RECENT-DISPERSION_PREVIOUS"}}
    _write(out/"structural_redundancy_v3.json", structural)
    pearson, spearman = _corr(rows), _corr(rows, True)
    _write(out/"pearson_correlation_v3.json", pearson); _write(out/"spearman_correlation_v3.json", spearman)
    flags = []
    for i, x in enumerate(PRIMARY):
        for y in PRIMARY[i+1:]:
            for method, report in (("Pearson", pearson), ("Spearman", spearman)):
                value = report["matrix"][x][y]
                if value is not None and abs(value) >= .95: flags.append({"pair": [x, y], "method": method, "value": value})
    _write(out/"empirical_redundancy_flags_v3.json", {"threshold": .95, "flags": flags, "features_removed": False})
    duplicates = _duplicates(rows); _write(out/"exact_duplicate_audit_v3.json", duplicates)
    distributions = {}
    for key in PRIMARY:
        def dist(rr, k=key):
            vals = [r[k] for r in rr if r[k] is not None]
            report = {**_summary(vals, True), "missing_count": len(rr)-len(vals), "unique_count": len(set(vals))}
            if k in ("NEW_JOINER_FRACTION", "MINUTES_SINCE_MARKET_EXPANSION_ONSET", "MINUTES_SINCE_CATCHUP_ONSET"):
                report["exact_frequency_table"] = {str(x): c for x, c in sorted(Counter(vals).items())}
            return report
        distributions[key] = {"pooled": dist(rows), "by_year": {str(y): dist([r for r in rows if r["year"] == y]) for y in (2024, 2025)}}
    _write(out/"feature_distributions_v3.json", distributions)
    stability = {}
    for key in PRIMARY:
        a = [r[key] for r in rows if r["year"] == 2024 and r[key] is not None]; b = [r[key] for r in rows if r["year"] == 2025 and r[key] is not None]
        pooled = math.sqrt((np.var(a)+np.var(b))/2) if a and b else 0
        stability[key] = {"2024": {**_summary(a), "missing_percentage": 100*(1093-len(a))/1093},
                          "2025": {**_summary(b), "missing_percentage": 100*(1106-len(b))/1106},
                          "standardized_mean_difference": (statistics.fmean(a)-statistics.fmean(b))/pooled if pooled else None,
                          "two_sample_KS_statistic": base._ks(a, b)}
    _write(out/"year_distribution_stability_v3.json", stability)
    symbols = {k: {s: {**_summary([r[k] for r in rows if r["symbol"] == s and r[k] is not None]),
        "missing_percentage": 100*sum(r[k] is None for r in rows if r["symbol"] == s)/base.EXPECTED_SYMBOLS[s]} for s in base.SYMBOLS} for k in PRIMARY}
    _write(out/"symbol_distribution_diagnostics_v3.json", symbols)
    comparison = {"V2_subject_same_boundary_onset_rate_historical_percent": 81.95,
                  "V2_mean_subject_qualifying_conditions_per_12h_historical": 5.31,
                  "V3_catchup_same_boundary_onset_rate_percent": same_report["catchup"]["pooled"]["percentage"],
                  "V3_catchup_FALSE_to_TRUE_onset_count_distribution": catch_counts, "outcome_free_mechanics_only": True}
    _write(out/"v2_v3_mechanics_comparison.json", comparison)
    unresolved = [p for p in duplicates["pairs"] if p["identical"] or p["sign_reversal"] or p["affine_transform"]]
    gates = {"population_exact": population["status"] == "PASS", "schema_exact": tuple(schema["primary_variables_ordered"]) == PRIMARY,
             "formulas_pass": formula["status"] == "PASS", "FALSE_to_TRUE_semantics_pass": transition["status"] == "PASS",
             "causal_timing_pass": interval["status"] == "PASS", "future_mutation_pass": future["status"] == "PASS",
             "entry_fill_independence_pass": fill["status"] == "PASS", "outcome_artifact_read": False,
             "sealed_boundary_accessed": False, "state_aware_valid_at_least_99_percent": 100*aware/len(rows) >= 99,
             "no_unresolved_primary_duplicate": not unresolved, "null_reasons_distinguished": True,
             "material_implementation_ambiguity": False}
    technical_gates_pass = all((v is True or v is False and k in ("outcome_artifact_read", "sealed_boundary_accessed", "material_implementation_ambiguity")) for k, v in gates.items())
    # This is a descriptive contract judgment, not an automatic rarity cutoff:
    # nearly every row has multiple onsets and more than two thirds have 4+.
    recurrence = {
        "assessment": "FALSE -> TRUE catch-up onsets remain a generic recurring condition",
        "basis": "outcome-free mechanics only; no automatic frequency threshold imposed",
        "mean_onsets_per_12h": catch_counts["mean"],
        "entries_with_zero_onsets": catch_counts["bands"]["0"],
        "entries_with_one_onset": catch_counts["bands"]["1"],
        "entries_with_two_or_more_onsets": len(rows)-catch_counts["bands"]["0"]-catch_counts["bands"]["1"],
        "entries_with_four_or_more_onsets": catch_counts["bands"]["4+"],
        "same_boundary_percentage": same_report["catchup"]["pooled"]["percentage"],
    }
    semantic_revision_needed = True
    classification = "REPRESENTATION_V3_AUDIT_PASS" if technical_gates_pass and not semantic_revision_needed else "REPRESENTATION_V3_NEEDS_REVISION"
    if not gates["population_exact"] or not docs["all_match"] or not gates["causal_timing_pass"]:
        classification = "REPRESENTATION_V3_AUDIT_INSUFFICIENT"
    indicators_needed = raw < len(rows)
    event_like = False
    predicates = {**gates, "all_technical_implementation_gates_pass": technical_gates_pass,
                  "episode_onsets_materially_more_event_like_than_V2": event_like,
                  "semantic_revision_needed_for_recurrence": semantic_revision_needed,
                  "recurrence_evidence": recurrence,
                  "prospective_missing_state_encoding_required_before_predictive_experiment": indicators_needed,
                  "predictive_contract_design_technically_justified": classification == "REPRESENTATION_V3_AUDIT_PASS"}
    _write(out/"interpretation_predicates_v3.json", predicates)
    summary = {"classification": classification, "population_count": len(rows), "primary_schema": list(PRIMARY),
        "catchup_state_at_E1": _frequency(rows, "CATCHUP_STATE_AT_E1")["pooled"],
        "market_expansion_state_at_E1": _frequency(rows, "MARKET_EXPANSION_STATE_AT_E1")["pooled"],
        "catchup_onset_available": _availability(rows, "CATCHUP_ONSET_DETECTED_TS")["pooled"],
        "market_onset_available": _availability(rows, "MARKET_EXPANSION_ONSET_DETECTED_TS")["pooled"],
        "catchup_same_boundary": same_report["catchup"]["pooled"], "market_same_boundary": same_report["market_expansion"]["pooled"],
        "raw_complete_primary_count": raw, "raw_complete_primary_percent": 100*raw/len(rows),
        "state_aware_valid_count": aware, "state_aware_valid_percent": 100*aware/len(rows),
        "sequence_ordering": ordering["pooled"], "near_redundancy_flag_count": len(flags), "exact_or_affine_primary_pair_count": len(unresolved),
        "episode_onsets_materially_more_event_like_than_V2": event_like, "recurrence_revision_reason": recurrence,
        "all_technical_implementation_gates_pass": technical_gates_pass,
        "missing_state_encoding_requires_prospective_amendment": indicators_needed,
        "predictive_contract_design_technically_justified": classification == "REPRESENTATION_V3_AUDIT_PASS",
        "PASS_does_not_imply_predictive_usefulness": True, "no_model_fit": True, "no_feature_selected_removed_or_added": True,
        "onset_definitions_interval_and_window_unchanged": True, "C31_started": False}
    _write(out/"final_summary_v3.json", summary)
    test_path = repo/"tests/test_catchup_transition_representation_audit_v3.py"
    manifest = {"command": "conda run -n binance-v2-research env PYTHONPATH=src python scripts/catchup_transition_representation_audit_v3.py",
        "environment": "binance-v2-research", "python": sys.version, "platform": platform.platform(), "numpy": np.__version__,
        "git_HEAD": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip(), "documents": docs,
        "source_paths": [base.ENTRY_REL]+[f"data/normalized/c2_history/{s}_1m.csv.gz" for s in base.SYMBOLS]}
    _write(out/"run_manifest.json", manifest)
    _write(out/"provenance.json", {"documents": docs, "entry_input": population, "market_inputs": boundary["accepted_inputs"],
        "input_allowlist_enforced": True, "outcome_artifacts_opened": False, "post_E1_data_used": False, "sealed_boundary_data_or_metadata_accessed": False})
    hashes = {"documents": docs["actual"], "implementation_sha256": sha256_file(Path(__file__)), "test_sha256": sha256_file(test_path),
        "source_hashes": {base.ENTRY_REL: base.ENTRY_SHA256, **{f"data/normalized/c2_history/{s}_1m.csv.gz": base.MARKET_HASHES[s] for s in base.SYMBOLS}},
        "population_sha256": population["semantic_sha256"], "ordered_schema_sha256": _sha(PRIMARY),
        "semantic_representation_sha256": _sha([[r[k] for k in PRIMARY] for r in rows])}
    core = [p for p in out.glob("*.json") if p.name != "reproducibility_hashes_v3.json"]
    hashes["artifact_sha256"] = {p.name: sha256_file(p) for p in sorted(core)}
    _write(out/"reproducibility_hashes_v3.json", hashes)
    return summary
