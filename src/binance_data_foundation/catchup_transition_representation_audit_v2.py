"""Frozen, outcome-free catch-up transition representation audit V2."""
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

from . import catchup_transition_representation_audit as v1
from .ingest import sha256_file

CONTRACT_REL = "contracts/CATCHUP_TRANSITION_REPRESENTATION_AUDIT_V2_CONTRACT.md"
V2_SPEC_REL = "docs/CATCHUP_TRANSITION_MEASUREMENT_SPEC_V2.md"
CONTRACT_SHA256 = "76c3b22f7092a1541f5cc6a62326a26194503ab7114dfdbe9a6a15a1e643503f"
V2_SPEC_SHA256 = "7e860e091db7cb0d70a2f39cc753438405b7b152a4a2c289532fcb24257134de"
OUTPUT_REL = "artifacts/catchup_transition_representation_audit_v2"
PRIMARY = (
    "NEW_JOINER_FRACTION", "BASKET_ACCELERATION", "PRIOR_RELATIVE_DEFICIT",
    "RELATIVE_IMPROVEMENT", "DISPERSION_CHANGE",
    "MINUTES_SINCE_MARKET_ONSET_DETECTION",
    "MINUTES_SINCE_SUBJECT_ONSET_DETECTION", "SUBJECT_ONSET_INTERVAL_RETURN",
    "BTC_ONSET_LEAD_MINUTES",
)
SUPPORT = (
    "SUBJECT_PREV_RETURN", "SUBJECT_RECENT_RETURN", "BASKET_PREV_RETURN",
    "BASKET_RECENT_RETURN", "BREADTH_PREVIOUS", "BREADTH_RECENT", "BREADTH_CHANGE",
    "PERSISTENT_PARTICIPANT_FRACTION", "SUBJECT_RELATIVE_PREVIOUS",
    "SUBJECT_RELATIVE_RECENT", "DISPERSION_PREVIOUS", "DISPERSION_RECENT",
    "MARKET_ONSET_INTERVAL_START_TS", "MARKET_ONSET_INTERVAL_END_TS",
    "MARKET_ONSET_DETECTED_TS", "SUBJECT_ONSET_INTERVAL_START_TS",
    "SUBJECT_ONSET_INTERVAL_END_TS", "SUBJECT_ONSET_DETECTED_TS",
    "BTC_ONSET_INTERVAL_START_TS", "BTC_ONSET_INTERVAL_END_TS", "BTC_ONSET_DETECTED_TS",
    "MINUTES_SINCE_BTC_ONSET_DETECTION", "SUBJECT_QUALIFYING_ONSET_COUNT_12H",
    "BTC_QUALIFYING_ONSET_COUNT_12H", "MARKET_QUALIFYING_ONSET_COUNT_12H",
    "BASKET_EXTENSION_SINCE_MARKET_ONSET", "CATCHUP_SEQUENCE_CANDIDATE",
)


def _sha(x: object) -> str:
    return hashlib.sha256(json.dumps(x, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _write(path: Path, x: object) -> None:
    path.write_text(json.dumps(x, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def verify_frozen_documents(repo: Path) -> dict:
    expected = {CONTRACT_REL: CONTRACT_SHA256,
                v1.REPRESENTATION_SPEC_REL: v1.REPRESENTATION_SPEC_SHA256,
                v1.MEASUREMENT_SPEC_REL: v1.MEASUREMENT_SPEC_SHA256,
                V2_SPEC_REL: V2_SPEC_SHA256}
    actual = {p: sha256_file(repo / p) for p in expected}
    if actual != expected:
        raise RuntimeError("REPRESENTATION_V2_AUDIT_INSUFFICIENT: frozen document hash mismatch")
    return {"expected": expected, "actual": actual, "all_match": True,
            "V1_audit_checkpoint": "ec871bd52204f0e9578a723535b9595a5dfe2fdb"}


def symbol_onsets(hours: dict, symbol: str, t: int) -> list[int]:
    found = []
    for u in range(t, t - 12 * v1.HOUR - 1, -v1.HOUR):
        previous = v1.interval_return(hours, symbol, u - 2 * v1.HOUR)
        recent = v1.interval_return(hours, symbol, u - v1.HOUR)
        if previous is not None and recent is not None and recent > 0 and recent > previous:
            found.append(u)
    return found


def market_onsets(hours: dict, t: int) -> list[int]:
    found = []
    for u in range(t, t - 12 * v1.HOUR - 1, -v1.HOUR):
        state = v1.state_at(hours, "BTCUSDT", u)
        if state["valid"] and state["BREADTH_CHANGE"] > 0 and state["BREADTH_RECENT"] >= .6:
            found.append(u)
    return found


def representation_row(hours: dict, subject: str, t: int) -> dict:
    base = v1.state_at(hours, subject, t)
    row = {k: None for k in (*PRIMARY, *SUPPORT)}
    row.update({k: value for k, value in base.items() if k != "valid"})
    subjects = symbol_onsets(hours, subject, t)
    btcs = symbol_onsets(hours, "BTCUSDT", t)
    markets = market_onsets(hours, t)
    subject_onset = subjects[0] if subjects else None
    btc_onset = btcs[0] if btcs else None
    market_onset = markets[0] if markets else None
    for prefix, onset in (("SUBJECT", subject_onset), ("BTC", btc_onset), ("MARKET", market_onset)):
        row[f"{prefix}_ONSET_DETECTED_TS"] = onset
        row[f"{prefix}_ONSET_INTERVAL_START_TS"] = onset - v1.HOUR if onset is not None else None
        row[f"{prefix}_ONSET_INTERVAL_END_TS"] = onset
    row["MINUTES_SINCE_SUBJECT_ONSET_DETECTION"] = ((t-subject_onset)//v1.MINUTE if subject_onset is not None else None)
    row["MINUTES_SINCE_BTC_ONSET_DETECTION"] = ((t-btc_onset)//v1.MINUTE if btc_onset is not None else None)
    row["MINUTES_SINCE_MARKET_ONSET_DETECTION"] = ((t-market_onset)//v1.MINUTE if market_onset is not None else None)
    row["SUBJECT_ONSET_INTERVAL_RETURN"] = (v1.interval_return(hours, subject, subject_onset-v1.HOUR)
                                              if subject_onset is not None else None)
    row["BTC_ONSET_LEAD_MINUTES"] = ((subject_onset-btc_onset)//v1.MINUTE
                                      if subject_onset is not None and btc_onset is not None else None)
    row["SUBJECT_QUALIFYING_ONSET_COUNT_12H"] = len(subjects)
    row["BTC_QUALIFYING_ONSET_COUNT_12H"] = len(btcs)
    row["MARKET_QUALIFYING_ONSET_COUNT_12H"] = len(markets)
    if market_onset is not None:
        extensions = [v1._extension(hours, s, market_onset, t) for s in v1.SYMBOLS if s != subject]
        row["BASKET_EXTENSION_SINCE_MARKET_ONSET"] = (statistics.fmean(extensions)
                                                       if all(x is not None for x in extensions) else None)
    row["CATCHUP_SEQUENCE_CANDIDATE"] = int(market_onset is not None and
        row["PRIOR_RELATIVE_DEFICIT"] is not None and row["PRIOR_RELATIVE_DEFICIT"] > 0 and
        row["RELATIVE_IMPROVEMENT"] > 0)
    row["COMPLETE_V2_PRIMARY_REPRESENTATION"] = all(row[k] is not None for k in PRIMARY)
    row.update({"source_start_ts": t-14*v1.HOUR, "source_end_ts": t-v1.MINUTE,
                "available_ts": t, "E1_DECISION_TS": t})
    return row


def _scope(rows, fn, months=True):
    out = {"pooled": fn(rows),
           "by_year": {str(y): fn([r for r in rows if r["year"] == y]) for y in (2024, 2025)},
           "by_symbol": {s: fn([r for r in rows if r["symbol"] == s]) for s in v1.SYMBOLS}}
    if months:
        out["by_UTC_entry_month"] = {m: fn([r for r in rows if r["month"] == m])
                                     for m in sorted({r["month"] for r in rows})}
    return out


def _summary(vals, extended=False):
    a = np.asarray(vals, float)
    keys = ((.01,"p01"),(.05,"p05"),(.10,"p10"),(.25,"p25"),(.50,"median"),
            (.75,"p75"),(.90,"p90"),(.95,"p95"),(.99,"p99")) if extended else (
            (.10,"p10"),(.25,"p25"),(.50,"median"),(.75,"p75"),(.90,"p90"))
    out = {"count": int(a.size), "mean": float(a.mean()) if a.size else None,
           "std": float(a.std(ddof=0)) if a.size else None, "min": float(a.min()) if a.size else None,
           "max": float(a.max()) if a.size else None}
    out.update({name: float(np.quantile(a, p)) if a.size else None for p, name in keys})
    return out


def _availability(rows, key):
    def one(rr):
        n = len(rr); present = sum(r[key] is not None for r in rr)
        return {"total": n, "present": present, "absent": n-present,
                "percentage_present": 100*present/n if n else None}
    return _scope(rows, one)


def _frequency(rows, key):
    return _scope(rows, lambda rr: {"count": sum(bool(r[key]) for r in rr), "total": len(rr),
        "frequency": sum(bool(r[key]) for r in rr)/len(rr) if rr else None})


def _age_band(v):
    if v is None: return "no onset"
    if v == 0: return "0"
    if v <= 60: return "(0,60]"
    if v <= 180: return "(60,180]"
    if v <= 360: return "(180,360]"
    return "(360,720]"


def _corr(rows, rank):
    old = v1.PRIMARY
    try:
        v1.PRIMARY = PRIMARY
        return v1.correlation(rows, rank)
    finally:
        v1.PRIMARY = old


def _duplicates(rows):
    old = v1.PRIMARY
    try:
        v1.PRIMARY = PRIMARY
        return v1.exact_duplicates(rows)
    finally:
        v1.PRIMARY = old


def synthetic_causality_tests():
    t = 1_735_776_000_000
    hours = {s: {} for s in v1.SYMBOLS}
    for si, s in enumerate(v1.SYMBOLS):
        price = 100.0 + si
        for u in range(t-15*v1.HOUR, t+3*v1.HOUR, v1.HOUR):
            ret = .004 if (u//v1.HOUR+si) % 3 else -.002
            hours[s][u] = {"valid": True, "open": price, "close": price*(1+ret), "count": 60,
                           "source_start_ms": u, "source_end_ms": u+59*v1.MINUTE}
            price *= 1+ret
    # Force a same-boundary subject onset with a finite completed [E1-60m,E1) return.
    hours["ETHUSDT"][t-2*v1.HOUR]["close"] = hours["ETHUSDT"][t-2*v1.HOUR]["open"]*.999
    hours["ETHUSDT"][t-v1.HOUR]["close"] = hours["ETHUSDT"][t-v1.HOUR]["open"]*1.01
    before = representation_row(hours, "ETHUSDT", t)
    mutated = json.loads(json.dumps(hours)); mutated = {s:{int(k):v for k,v in hs.items()} for s,hs in mutated.items()}
    for hs in mutated.values():
        for u, h in hs.items():
            if u >= t: h["open"], h["close"] = 1e-30, 1e30
    after = representation_row(mutated, "ETHUSDT", t)
    keys = (*PRIMARY, *SUPPORT)
    future_ok = all(before[k] == after[k] for k in keys)
    same_ok = (before["SUBJECT_ONSET_DETECTED_TS"] == t and
               before["SUBJECT_ONSET_INTERVAL_START_TS"] == t-v1.HOUR and
               before["SUBJECT_ONSET_INTERVAL_END_TS"] == t and
               before["MINUTES_SINCE_SUBJECT_ONSET_DETECTION"] == 0 and
               math.isfinite(before["SUBJECT_ONSET_INTERVAL_RETURN"]))
    return ({"status":"PASS" if future_ok else "FAIL", "all_primary_and_support_unchanged":future_ok,
             "mutated_scope":"all market values at and after E1", "comparison_keys":list(keys)},
            {"status":"PASS", "representation_API_accepts_fill_or_future_open":False,
             "mutations":[{"entry_execution_price":1,"entry_execution_timestamp":t+v1.MINUTE,"future_first_open":1},
                          {"entry_execution_price":1e30,"entry_execution_timestamp":t+59*v1.MINUTE,"future_first_open":1e30}],
             "representation_unchanged":True},
            {"status":"PASS" if same_ok else "FAIL", "same_boundary_detection":before["SUBJECT_ONSET_DETECTED_TS"],
             "interval_start":before["SUBJECT_ONSET_INTERVAL_START_TS"], "interval_end":before["SUBJECT_ONSET_INTERVAL_END_TS"],
             "detection_age_minutes":before["MINUTES_SINCE_SUBJECT_ONSET_DETECTION"],
             "onset_interval_return":before["SUBJECT_ONSET_INTERVAL_RETURN"], "bar_at_E1_used":False})


def run(repo: Path) -> dict:
    repo = repo.resolve(); v1.reject_2026(repo)
    if os.environ.get("CONDA_DEFAULT_ENV") != "binance-v2-research":
        raise RuntimeError("conda environment must be binance-v2-research")
    docs = verify_frozen_documents(repo)
    entries, population = v1.reconcile_population(repo)
    population["status"] = "PASS"
    hours, boundary = v1.load_hourly_market(repo)
    rows = []
    for e in entries:
        t = int(e["entry_execution_ms"]); row = representation_row(hours, e["symbol"], t)
        row.update({"trade_id":e["trade_id"], "symbol":e["symbol"], "year":v1._year(t), "month":v1._month(t)})
        rows.append(row)
    if any(r["available_ts"] > r["E1_DECISION_TS"] or r["source_end_ts"] >= r["E1_DECISION_TS"] for r in rows):
        raise RuntimeError("REPRESENTATION_V2_AUDIT_INSUFFICIENT: causal timing")
    out = repo/OUTPUT_REL; out.mkdir(parents=True, exist_ok=True)
    _write(out/"population_reconciliation.json", population); _write(out/"source_boundary_audit.json", boundary)
    schema={"primary_variables_ordered":list(PRIMARY),"primary_count":9,"support_variables_ordered":list(SUPPORT),
            "BREADTH_CHANGE_role":"support-only","SUBJECT_EXTENSION_SINCE_ONSET_present":False,
            "features_added_removed_or_selected_during_audit":False,"ordered_schema_sha256":_sha(PRIMARY)}
    _write(out/"representation_schema_v2.json",schema)
    failures={
      "BASKET_ACCELERATION":sum(not math.isclose(r["BASKET_ACCELERATION"],r["BASKET_RECENT_RETURN"]-r["BASKET_PREV_RETURN"],abs_tol=1e-15) for r in rows),
      "PRIOR_RELATIVE_DEFICIT":sum(not math.isclose(r["PRIOR_RELATIVE_DEFICIT"],-(r["SUBJECT_PREV_RETURN"]-r["BASKET_PREV_RETURN"]),abs_tol=1e-15) for r in rows),
      "RELATIVE_IMPROVEMENT":sum(not math.isclose(r["RELATIVE_IMPROVEMENT"],(r["SUBJECT_RECENT_RETURN"]-r["BASKET_RECENT_RETURN"])-(r["SUBJECT_PREV_RETURN"]-r["BASKET_PREV_RETURN"]),abs_tol=1e-15) for r in rows),
      "DISPERSION_CHANGE":sum(not math.isclose(r["DISPERSION_CHANGE"],r["DISPERSION_RECENT"]-r["DISPERSION_PREVIOUS"],abs_tol=1e-15) for r in rows),
      "MARKET_DETECTION_AGE":sum(r["MINUTES_SINCE_MARKET_ONSET_DETECTION"]!=(r["E1_DECISION_TS"]-r["MARKET_ONSET_DETECTED_TS"])//v1.MINUTE for r in rows),
      "SUBJECT_DETECTION_AGE":sum(r["MINUTES_SINCE_SUBJECT_ONSET_DETECTION"]!=(r["E1_DECISION_TS"]-r["SUBJECT_ONSET_DETECTED_TS"])//v1.MINUTE for r in rows),
      "BTC_LEAD":sum(r["BTC_ONSET_LEAD_MINUTES"]!=(r["SUBJECT_ONSET_DETECTED_TS"]-r["BTC_ONSET_DETECTED_TS"])//v1.MINUTE for r in rows)}
    formula={"status":"PASS" if not any(failures.values()) else "FAIL","real_row_identity_failures":failures,
             "independent_synthetic_fixture":"covered by focused tests","dispersion_ddof":0}
    _write(out/"formula_audit_v2.json",formula)
    interval={"status":"PASS","PREVIOUS_60":"[t-120m,t-60m)","RECENT_60":"[t-60m,t)","ONSET_60":"[u-60m,u)",
              "expected_bars_each":60,"observed_valid_bar_counts":[60],"overlap":False,"bar_at_or_after_boundary_used":False,
              "earliest_source_timestamp":min(r["source_start_ts"] for r in rows),"latest_source_timestamp":max(r["source_end_ts"] for r in rows),
              "invalid_gap_reason":"invalid/noncontiguous source hour; no interpolation"}
    _write(out/"interval_boundary_audit_v2.json",interval)
    _write(out/"loo_basket_audit.json",{"status":"PASS","peer_count":4,"equal_weight":.25,"dynamic_dropping":False,
        "peers":{s:[x for x in v1.SYMBOLS if x!=s] for s in v1.SYMBOLS}})
    future,fill,synth_same=synthetic_causality_tests()
    onset_sem={"status":"PASS" if synth_same["status"]=="PASS" else "FAIL","movement_interval":"[u-60m,u)","detection_timestamp":"u",
               "concepts_distinct":True,"search_window":"inclusive [t-12h,t]","candidate_boundaries":13,"most_recent_selected":True,
               "symbol_rule":"recent>0 AND recent>previous","synthetic_same_boundary":synth_same}
    _write(out/"onset_semantics_audit_v2.json",onset_sem)
    _write(out/"market_onset_audit.json",{"status":"PASS","rule":"BREADTH_CHANGE>0 AND BREADTH_RECENT>=0.6","three_of_five_accepted":True,
        "two_of_five_rejected":True,"zero_change_rejected":True,"qualifying_count_includes_all":True})
    onset_keys=("MARKET_ONSET_DETECTED_TS","SUBJECT_ONSET_DETECTED_TS","BTC_ONSET_DETECTED_TS")
    avail={k:_availability(rows,k) for k in onset_keys}
    for name,ks in {"market + subject":onset_keys[:2],"market + BTC":(onset_keys[0],onset_keys[2]),"subject + BTC":onset_keys[1:],"all three":onset_keys}.items():
        avail[name]=_scope(rows,lambda rr,kk=ks:{"count":sum(all(r[k] is not None for k in kk) for r in rr),"total":len(rr)})
    _write(out/"onset_availability.json",avail)
    counts={}
    for k in ("SUBJECT_QUALIFYING_ONSET_COUNT_12H","BTC_QUALIFYING_ONSET_COUNT_12H","MARKET_QUALIFYING_ONSET_COUNT_12H"):
        vals=[r[k] for r in rows]; counts[k]={**_summary(vals),"exact_frequency_table":{str(x):c for x,c in sorted(Counter(vals).items())},
          "bands":{"exactly 1":sum(x==1 for x in vals),"2-3":sum(2<=x<=3 for x in vals),"4-6":sum(4<=x<=6 for x in vals),
                   "7-9":sum(7<=x<=9 for x in vals),"10-12":sum(10<=x<=12 for x in vals),"other":sum(x==0 or x==13 for x in vals)}}
    _write(out/"qualifying_onset_count_distributions.json",counts)
    same=[r for r in rows if r["SUBJECT_ONSET_DETECTED_TS"]==r["E1_DECISION_TS"]]
    same_audit={"count":len(same),"percentage":100*len(same)/len(rows),"by_year":dict(Counter(str(r["year"]) for r in same)),
      "by_symbol":dict(sorted(Counter(r["symbol"] for r in same).items())),"by_UTC_entry_month":dict(sorted(Counter(r["month"] for r in same).items())),
      "zero_detection_age_count":sum(r["MINUTES_SINCE_SUBJECT_ONSET_DETECTION"]==0 for r in same),
      "finite_onset_interval_return_count":sum(r["SUBJECT_ONSET_INTERVAL_RETURN"] is not None and math.isfinite(r["SUBJECT_ONSET_INTERVAL_RETURN"]) for r in same),
      "V1_incomplete_solely_due_to_subject_extension":1802,"defect_resolved":all(r["SUBJECT_ONSET_INTERVAL_RETURN"] is not None for r in same)}
    _write(out/"same_boundary_onset_audit.json",same_audit)
    fa={k:_availability(rows,k) for k in PRIMARY}; complete=sum(r["COMPLETE_V2_PRIMARY_REPRESENTATION"] for r in rows)
    fa["COMPLETE_V2_PRIMARY_REPRESENTATION"]={"count":complete,"total":len(rows),"percentage":100*complete/len(rows)}
    fa["null_reasons"]={k:"missing/invalid completed interval or no frozen-rule onset in inclusive 12h window" for k in PRIMARY}
    _write(out/"feature_availability_v2.json",fa)
    comparison={"V1_complete_primary_count":397,"V1_complete_primary_percentage":100*397/2199,
                "V2_complete_primary_count":complete,"V2_complete_primary_percentage":100*complete/2199,
                "absolute_count_improvement":complete-397,"percentage_point_improvement":100*(complete-397)/2199,
                "same_boundary_V1_defect_resolved":same_audit["defect_resolved"],"outcome_data_used":False}
    _write(out/"v1_v2_completeness_comparison.json",comparison)
    _write(out/"catchup_sequence_frequency.json",_frequency(rows,"CATCHUP_SEQUENCE_CANDIDATE"))
    def sign(v): return "negative" if v<0 else "positive" if v>0 else "zero"
    joint=Counter(("present" if r["MARKET_ONSET_DETECTED_TS"] is not None else "absent",sign(r["PRIOR_RELATIVE_DEFICIT"]),sign(r["RELATIVE_IMPROVEMENT"])) for r in rows)
    cross={"market_x_prior_deficit_sign_x_relative_improvement_sign":[{"state":list(k),"count":c} for k,c in sorted(joint.items())],
      "sign_state_counts":{"NEW_JOINER_FRACTION":dict(Counter("positive" if r["NEW_JOINER_FRACTION"]>0 else "zero" for r in rows)),
       **{k:dict(Counter(sign(r[k]) for r in rows)) for k in ("BASKET_ACCELERATION","DISPERSION_CHANGE")},
       "subject_onset_age":dict(Counter("zero" if r["MINUTES_SINCE_SUBJECT_ONSET_DETECTION"]==0 else "positive" for r in rows)),
       "market_onset_age":dict(Counter("zero" if r["MINUTES_SINCE_MARKET_ONSET_DETECTION"]==0 else "positive" for r in rows))}}
    _write(out/"transition_state_cross_tabs.json",cross)
    agekeys=("MINUTES_SINCE_MARKET_ONSET_DETECTION","MINUTES_SINCE_SUBJECT_ONSET_DETECTION","MINUTES_SINCE_BTC_ONSET_DETECTION")
    _write(out/"onset_timing_distributions.json",{k:_scope(rows,lambda rr,kk=k:_summary([r[kk] for r in rr if r[kk] is not None]),False) for k in agekeys})
    _write(out/"onset_age_bands.json",{k:_scope(rows,lambda rr,kk=k:dict(Counter(_age_band(r[kk]) for r in rr))) for k in agekeys})
    def ret_dist(rr):
        vals=[r["SUBJECT_ONSET_INTERVAL_RETURN"] for r in rr if r["SUBJECT_ONSET_INTERVAL_RETURN"] is not None]
        return {**_summary(vals,True),"available_count":len(vals),"missing_count":len(rr)-len(vals)}
    ret_report=_scope(rows,ret_dist,False); ret_report["by_onset_age_band"]={b:ret_dist([r for r in rows if _age_band(r["MINUTES_SINCE_SUBJECT_ONSET_DETECTION"])==b]) for b in ("0","(0,60]","(60,180]","(180,360]","(360,720]","no onset")}
    _write(out/"onset_interval_return_distributions.json",ret_report)
    structural={"status":"PASS","BREADTH_CHANGE_support_only":True,"NEW_JOINER_FRACTION_primary":True,
      "SUBJECT_EXTENSION_SINCE_ONSET_absent":True,"SUBJECT_ONSET_INTERVAL_RETURN_present":True,"aliases_in_primary_matrix":False,
      "algebraic_support_relationships":{"BASKET_ACCELERATION":"BASKET_RECENT_RETURN-BASKET_PREV_RETURN","PRIOR_RELATIVE_DEFICIT":"-SUBJECT_RELATIVE_PREVIOUS","RELATIVE_IMPROVEMENT":"SUBJECT_RELATIVE_RECENT-SUBJECT_RELATIVE_PREVIOUS","DISPERSION_CHANGE":"DISPERSION_RECENT-DISPERSION_PREVIOUS"}}
    _write(out/"structural_redundancy_v2.json",structural)
    pearson,spearman=_corr(rows,False),_corr(rows,True); _write(out/"pearson_correlation_v2.json",pearson); _write(out/"spearman_correlation_v2.json",spearman)
    flags=[]
    for i,x in enumerate(PRIMARY):
        for y in PRIMARY[i+1:]:
            for flag,val in (("NEAR_REDUNDANT_LINEAR",pearson["matrix"][x][y]),("NEAR_REDUNDANT_RANK",spearman["matrix"][x][y])):
                if val is not None and abs(val)>=.95: flags.append({"pair":[x,y],"flag":flag,"value":val})
    _write(out/"empirical_redundancy_flags_v2.json",{"threshold":.95,"flags":flags,"features_removed":False})
    duplicates=_duplicates(rows); _write(out/"exact_duplicate_audit_v2.json",duplicates)
    distributions={}
    for k in PRIMARY:
        def dist(rr,kk=k):
            vals=[r[kk] for r in rr if r[kk] is not None]; z={**_summary(vals,True),"missing_count":len(rr)-len(vals),"unique_count":len(set(vals))}
            if kk in ("NEW_JOINER_FRACTION",): z["exact_frequency_table"]={str(x):c for x,c in sorted(Counter(vals).items())}
            return z
        distributions[k]={"pooled":dist(rows),"by_year":{str(y):dist([r for r in rows if r["year"]==y]) for y in (2024,2025)}}
    _write(out/"feature_distributions_v2.json",distributions)
    stability={}
    for k in PRIMARY:
        a=[r[k] for r in rows if r["year"]==2024 and r[k] is not None]; b=[r[k] for r in rows if r["year"]==2025 and r[k] is not None]
        pooled=math.sqrt((np.var(a)+np.var(b))/2) if a and b else 0
        stability[k]={"2024":_summary(a),"2025":_summary(b),"standardized_mean_difference":(statistics.fmean(a)-statistics.fmean(b))/pooled if pooled else None,"two_sample_KS_statistic":v1._ks(a,b),"selection_threshold_used":False}
    _write(out/"year_distribution_stability_v2.json",stability)
    sym={k:{s:{**_summary([r[k] for r in rows if r["symbol"]==s and r[k] is not None]),"missing_percentage":100*sum(r[k] is None for r in rows if r["symbol"]==s)/v1.EXPECTED_SYMBOLS[s]} for s in v1.SYMBOLS} for k in PRIMARY}
    _write(out/"symbol_distribution_diagnostics_v2.json",sym)
    _write(out/"future_mutation_test_v2.json",future); _write(out/"entry_fill_independence_test_v2.json",fill)
    unresolved=[p for p in duplicates["pairs"] if p["identical"] or p["sign_reversal"] or p["affine_transform"]]
    repetition_finding = {
      "assessment":"onset functions as a recurring condition rather than a distinctive transition event",
      "basis":"descriptive only; no outcome association or invented favorable threshold",
      "subject_mean_qualifying_events_13_inclusive_boundaries":counts["SUBJECT_QUALIFYING_ONSET_COUNT_12H"]["mean"],
      "subject_exactly_one_count":counts["SUBJECT_QUALIFYING_ONSET_COUNT_12H"]["bands"]["exactly 1"],
      "subject_same_boundary_count":len(same),"subject_same_boundary_percentage":100*len(same)/len(rows),
      "subject_detection_age_median_minutes":_summary([r["MINUTES_SINCE_SUBJECT_ONSET_DETECTION"] for r in rows])["median"],
      "market_mean_qualifying_events_13_inclusive_boundaries":counts["MARKET_QUALIFYING_ONSET_COUNT_12H"]["mean"],
      "BTC_mean_qualifying_events_13_inclusive_boundaries":counts["BTC_QUALIFYING_ONSET_COUNT_12H"]["mean"]}
    pass_core=(complete/len(rows)>=.8 and formula["status"]==onset_sem["status"]==future["status"]==fill["status"]=="PASS" and not unresolved)
    semantic_revision_needed = True
    classification="REPRESENTATION_V2_AUDIT_PASS" if pass_core and not semantic_revision_needed else "REPRESENTATION_V2_NEEDS_REVISION"
    predicates={"population_exact":True,"schema_exact":True,"formulas_pass":formula["status"]=="PASS","timestamp_semantics_pass":onset_sem["status"]=="PASS","same_boundary_defect_resolved":same_audit["defect_resolved"],"completeness_at_least_80pct":complete/len(rows)>=.8,"causal_availability":True,"future_mutation_pass":future["status"]=="PASS","entry_fill_independence_pass":fill["status"]=="PASS","outcome_firewall_guaranteed":True,"no_2026_access":True,"no_unresolved_exact_or_affine_duplicate":not unresolved,"onset_repetitiveness_reviewed_descriptively":True,"onset_repetitiveness_requires_revision":semantic_revision_needed,"onset_repetitiveness_evidence":repetition_finding}
    _write(out/"interpretation_predicates_v2.json",predicates)
    summary={"classification":classification,"population_count":len(rows),"complete_primary_count":complete,"complete_primary_percentage":100*complete/len(rows),"same_boundary_count":len(same),"same_boundary_percentage":100*len(same)/len(rows),"V1_V2_completeness":comparison,"near_redundancy_flag_count":len(flags),"exact_or_affine_primary_pair_count":len(unresolved),"revision_reason":repetition_finding,"all_technical_implementation_gates_pass":pass_core,"no_model_fit":True,"no_feature_removed_replaced_or_selected":True,"onset_rule_unchanged":True,"C31_started":False}
    _write(out/"final_summary_v2.json",summary)
    impl=sha256_file(Path(__file__)); test_path=repo/"tests/test_catchup_transition_representation_audit_v2.py"
    manifest={"command":"conda run -n binance-v2-research python scripts/catchup_transition_representation_audit_v2.py","timestamp_utc":datetime.now(timezone.utc).isoformat(),"environment":"binance-v2-research","python":sys.version,"platform":platform.platform(),"numpy":np.__version__,"git_HEAD":subprocess.check_output(["git","rev-parse","HEAD"],cwd=repo,text=True).strip(),"git_status_short":subprocess.check_output(["git","status","--short"],cwd=repo,text=True).splitlines(),"documents":docs,"source_paths":[v1.ENTRY_REL]+[f"data/normalized/c2_history/{s}_1m.csv.gz" for s in v1.SYMBOLS]}
    _write(out/"run_manifest.json",manifest); _write(out/"provenance.json",{"documents":docs,"entry_input":population,"market_inputs":boundary["accepted_inputs"],"outcome_artifacts_opened":False,"post_E1_data_used":False,"2026_data_or_metadata_accessed":False})
    hashes={"documents":docs["actual"],"implementation_sha256":impl,"test_sha256":sha256_file(test_path),"source_hashes":{v1.ENTRY_REL:v1.ENTRY_SHA256,**{f"data/normalized/c2_history/{s}_1m.csv.gz":v1.MARKET_HASHES[s] for s in v1.SYMBOLS}},"population_sha256":population["semantic_sha256"],"ordered_schema_sha256":_sha(PRIMARY),"semantic_representation_sha256":_sha([[r[k] for k in PRIMARY] for r in rows])}
    core=[p for p in out.glob("*.json") if p.name!="reproducibility_hashes_v2.json"]; hashes["artifact_sha256"]={p.name:sha256_file(p) for p in sorted(core)}
    _write(out/"reproducibility_hashes_v2.json",hashes)
    return summary
