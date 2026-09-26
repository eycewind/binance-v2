"""Reporting-only completion for C5 T2.

This module reads the frozen canonical trade table.  It contains no prediction,
trigger, exit, execution-price, return, cost, or population construction code.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import numpy as np

CANONICAL_SHA = "094c81c306f1084146db55cee3c6f38178e58a0e72e55e056bb0dd1eb6c46884"
SEED = 20240923
REPLICATES = 2000
COMPARISONS = (
    ("P1_Q75_EXIT_V1", "G1_Q75_EXIT_V1"),
    ("P1_Q75_EXIT_V1", "P0_HELD_V1"),
    ("G1_Q75_EXIT_V1", "P0_HELD_V1"),
    ("P1_Q90_EXIT_V1", "G1_Q90_EXIT_V1"),
    ("P1_Q90_EXIT_V1", "P0_HELD_V1"),
    ("G1_Q90_EXIT_V1", "P0_HELD_V1"),
)
SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT")
BOOLS = {"True": True, "False": False, "": None}
NUMERIC = {
    "net_return", "common_capture_gap", "held_peak_surrender", "holding_duration_seconds",
    "opportunity_foregone", "entry_execution_ms",
}
INDICATORS = {"green_to_red", "preserved_at_least_half_peak", "early_exit",
              "subsequent_plus_2", "subsequent_plus_3", "subsequent_plus_5", "executable"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def load_canonical(path: Path) -> list[dict]:
    actual = sha256(path)
    if actual != CANONICAL_SHA:
        raise RuntimeError(f"canonical trade_results hash mismatch: expected={CANONICAL_SHA}, actual={actual}")
    rows=[]
    with path.open(newline="") as handle:
        for raw in csv.DictReader(handle):
            row=dict(raw)
            for key in NUMERIC:
                row[key]=float(row[key]) if row.get(key) not in (None,"") else None
            for key in INDICATORS:
                row[key]=BOOLS[row.get(key,"")]
            rows.append(row)
    return rows


def paired(rows: list[dict], left: str, right: str, cost: str) -> dict[str, tuple[dict,dict]]:
    by_trade=defaultdict(dict)
    for row in rows:
        if row["cost_scenario"]==cost and row["executable"]:
            by_trade[row["trade_id"]][row["policy_id"]]=row
    return {t:(p[left],p[right]) for t,p in by_trade.items() if left in p and right in p}


def week_plan(pairs: dict[str,tuple[dict,dict]]) -> dict:
    dates={t:datetime.fromisoformat(p[0]["trade_entry_week"]).date() for t,p in pairs.items()}
    lo,hi=min(dates.values()),max(dates.values());lo=lo.fromordinal(lo.toordinal()-lo.weekday());hi=hi.fromordinal(hi.toordinal()-hi.weekday())
    span=(hi-lo).days//7+1; at=defaultdict(list)
    for t,d in dates.items():at[(d-lo).days//7].append(t)
    for trades in at.values():trades.sort()
    blocks=[list(range(i,i+4)) for i in range(span-3)]
    if span<4 or sum(any(at[j] for j in b) for b in blocks)<2: return {"available":False,"reason":"insufficient_four_week_blocks"}
    rng=np.random.Generator(np.random.PCG64(SEED));draws=[];multiplicities=[]
    for _ in range(REPLICATES):
        positions=[];picked=[]
        while len(positions)<span:
            i=int(rng.integers(len(blocks)));picked.append(i);positions.extend(blocks[i])
        chosen=[t for j in positions[:span] for t in at[j]]
        draws.append(picked);multiplicities.append(dict(sorted(Counter(chosen).items())))
    return {"available":True,"construction":"noncircular_four_contiguous_entry_week_positions","span_positions":span,"candidate_blocks":blocks,"sampled_block_indices":draws,"trade_multiplicities":multiplicities}


def month_plan(pairs: dict[str,tuple[dict,dict]]) -> dict:
    months=sorted({p[0]["entry_execution_ts"][:7] for p in pairs.values()});at=defaultdict(list)
    for t,p in pairs.items():at[p[0]["entry_execution_ts"][:7]].append(t)
    for trades in at.values():trades.sort()
    rng=np.random.Generator(np.random.PCG64(SEED));draws=[];multiplicities=[]
    for _ in range(REPLICATES):
        picked=[int(rng.integers(len(months))) for _ in months]
        chosen=[t for i in picked for t in at[months[i]]]
        draws.append(picked);multiplicities.append(dict(sorted(Counter(chosen).items())))
    return {"available":True,"construction":"whole_utc_calendar_month_trade_clusters_with_replacement","month_labels":months,"sampled_month_indices":draws,"trade_multiplicities":multiplicities}


def _mean_delta(a: list[dict], b: list[dict], key: str) -> float:
    vals=[float(x[key])-float(y[key]) for x,y in zip(a,b) if x[key] is not None and y[key] is not None]
    return float(np.mean(vals))


def _rate_delta(a: list[dict], b: list[dict], key: str) -> float:
    av=[float(x[key]) for x in a if x[key] is not None];bv=[float(x[key]) for x in b if x[key] is not None]
    return float(np.mean(av)-np.mean(bv))


def _early_delta(a: list[dict], b: list[dict], key: str) -> float:
    av=[float(x[key]) for x in a if x["early_exit"] and x[key] is not None];bv=[float(x[key]) for x in b if x["early_exit"] and x[key] is not None]
    return float(np.mean(av)-np.mean(bv))


def _tail(values: list[float], kind: str) -> float:
    a=np.asarray(values,float)
    if kind=="expected_shortfall_10":
        q=float(np.quantile(a,.1,method="linear"));return float(a[a<=q].mean())
    if kind=="p05":return float(np.quantile(a,.05,method="linear"))
    if kind=="p10":return float(np.quantile(a,.10,method="linear"))
    if kind=="downside_deviation":return float(np.sqrt(np.mean(np.minimum(a,0)**2)))
    if kind=="worst_trade":return float(a.min())
    raise KeyError(kind)


def _tail_delta(a: list[dict], b: list[dict], kind: str) -> float:
    return _tail([x["net_return"] for x in a],kind)-_tail([x["net_return"] for x in b],kind)


METRICS: dict[str,Callable[[list[dict],list[dict]],float]] = {
    "mean_net_return":lambda a,b:_mean_delta(a,b,"net_return"),
    "mean_capture_gap":lambda a,b:_mean_delta(a,b,"common_capture_gap"),
    "mean_held_surrender":lambda a,b:_mean_delta(a,b,"held_peak_surrender"),
    "green_to_red_rate":lambda a,b:_rate_delta(a,b,"green_to_red"),
    "preservation_rate":lambda a,b:_rate_delta(a,b,"preserved_at_least_half_peak"),
    "mean_holding_duration_seconds":lambda a,b:_mean_delta(a,b,"holding_duration_seconds"),
    "mean_opportunity_foregone_after_early_exit":lambda a,b:_early_delta(a,b,"opportunity_foregone"),
    "subsequent_plus_2_rate_after_early_exit":lambda a,b:_early_delta(a,b,"subsequent_plus_2"),
    "subsequent_plus_3_rate_after_early_exit":lambda a,b:_early_delta(a,b,"subsequent_plus_3"),
    "subsequent_plus_5_rate_after_early_exit":lambda a,b:_early_delta(a,b,"subsequent_plus_5"),
    **{x:(lambda a,b,x=x:_tail_delta(a,b,x)) for x in ("expected_shortfall_10","p05","p10","downside_deviation","worst_trade")},
}


def evaluate(pairs: dict[str,tuple[dict,dict]], plan: dict) -> tuple[dict,dict]:
    ordered=sorted(pairs);left=[pairs[t][0] for t in ordered];right=[pairs[t][1] for t in ordered]
    results={};vectors={}
    for name,stat in METRICS.items():
        if ("after_early_exit" in name or name=="mean_opportunity_foregone_after_early_exit") and (not any(x["early_exit"] for x in left) or not any(x["early_exit"] for x in right)):
            results[name]={"available":False,"reason":"held_baseline_has_no_comparable_policy_triggered_early_exit_denominator","paired_trades":len(pairs)}
            vectors[name]=[]
            continue
        point=stat(left,right);reps=[]
        for multiplicity in plan["trade_multiplicities"]:
            a=[];b=[]
            for t,n in multiplicity.items():
                a.extend([pairs[t][0]]*n);b.extend([pairs[t][1]]*n)
            reps.append(stat(a,b))
        results[name]={"available":True,"point_estimate":point,"ci95":np.quantile(reps,[.025,.975],method="linear").tolist(),"paired_trades":len(pairs),"replicates":REPLICATES}
        vectors[name]=reps
    return results,vectors


def safety_from(metrics: dict) -> dict:
    keys=("expected_shortfall_10","green_to_red_rate","mean_opportunity_foregone_after_early_exit","subsequent_plus_2_rate_after_early_exit","subsequent_plus_3_rate_after_early_exit","subsequent_plus_5_rate_after_early_exit")
    adverse=[]
    if metrics["expected_shortfall_10"]["ci95"][1]<0:adverse.append("expected_shortfall_10")
    for key in keys[1:]:
        if metrics[key]["ci95"][0]>0:adverse.append(key)
    return {"available":True,"required_metrics":{k:metrics[k] for k in keys},"adverse_interval_metrics":adverse,"unacceptable_safety_breach":bool(adverse)}


def reconstructed_attempts(existing: dict) -> dict:
    latest=(existing.get("attempts") or [{}])[-1]
    unknown=None
    return {"reconstruction_basis":"Codex transcript; unavailable timestamps explicitly null; no attempt invented",
            "attempt_count":4,"attempts":[
        {"chronological_order":1,"purpose":"initial authorized historical replay","status":"PASS","economics_displayed":True,"implementation_state":"initial c5_t2 implementation; pre-T2-specific tests; safety ES used an incorrect per-trade proxy","start_timestamp_utc":unknown,"end_timestamp_utc":unknown},
        {"chronological_order":2,"purpose":"replay after nonlinear safety-bootstrap correction","status":"PASS","economics_displayed":True,"implementation_state":"ES and early-exit safety recomputed within moving-block replicates; focused tests added","start_timestamp_utc":unknown,"end_timestamp_utc":unknown},
        {"chronological_order":3,"purpose":"artifact regeneration after reproducibility/attempt-ledger additions","status":"PASS","economics_displayed":False,"implementation_state":"code/config/input hashes and attempt ledger added; command output redirected","start_timestamp_utc":unknown,"end_timestamp_utc":unknown},
        {"chronological_order":4,"purpose":"final replay after deterministic contribution-order fix","status":"PASS","economics_displayed":False,"implementation_state":"symbol contribution trade IDs sorted before floating-point summation; command output redirected","start_timestamp_utc":latest.get("start_timestamp_utc"),"end_timestamp_utc":latest.get("end_timestamp_utc"),"code_sha256":latest.get("code_sha256"),"configuration_sha256":latest.get("configuration_sha256"),"input_manifest_sha256":latest.get("input_manifest_sha256"),"output_hashes":latest.get("output_hashes")},
    ],"failed_historical_replays":0,"failed_test_runs":1,"failed_test_detail":"synthetic half-peak expectation corrected from true to false; replay logic unchanged"}


def run(repo: Path) -> dict:
    repo=repo.resolve();out=repo/"artifacts/c5_economic_exit_policy/t2";canonical=out/"trade_results.csv"
    rows=load_canonical(canonical)
    scopes={"pooled_trade_weighted":lambda r:True,**{s:(lambda r,s=s:r["symbol"]==s) for s in SYMBOLS},**{y:(lambda r,y=y:r["year"]==y) for y in ("2024","2025")}}
    interval_panel={};month_panel={};repro={"parameters":{"unit":"whole_trade","replicates":REPLICATES,"generator":"PCG64","seed":SEED,"interval":[.025,.975],"quantile_method":"linear_type_7"},"primary":{},"calendar_month_sensitivity":{}}
    for scope,predicate in scopes.items():
        selected=[r for r in rows if predicate(r)]
        interval_panel[scope]={};month_panel[scope]={};repro["primary"][scope]={};repro["calendar_month_sensitivity"][scope]={}
        for left,right in COMPARISONS:
            name=f"{left}_minus_{right}";pairs=paired(selected,left,right,"C_BASE")
            wp=week_plan(pairs);mp=month_plan(pairs);primary,vectors=evaluate(pairs,wp);monthly,mvectors=evaluate(pairs,mp)
            interval_panel[scope][name]=primary;month_panel[scope][name]=monthly
            repro["primary"][scope][name]={"sampled_block_indices":wp["sampled_block_indices"],"trade_multiplicities":wp["trade_multiplicities"],"replicate_vectors":vectors,"construction":{k:v for k,v in wp.items() if k not in ("sampled_block_indices","trade_multiplicities")}}
            repro["calendar_month_sensitivity"][scope][name]={"sampled_month_indices":mp["sampled_month_indices"],"trade_multiplicities":mp["trade_multiplicities"],"replicate_vectors":mvectors,"construction":{k:v for k,v in mp.items() if k not in ("sampled_month_indices","trade_multiplicities")}}
    c_s5_pairs=paired(rows,"P1_Q75_EXIT_V1","G1_Q75_EXIT_V1","C_S5");c_s5_plan=week_plan(c_s5_pairs);c_s5_metrics,c_s5_vectors=evaluate(c_s5_pairs,c_s5_plan);c_s5_safety=safety_from(c_s5_metrics)
    repro["c_s5_safety"]={"sampled_block_indices":c_s5_plan["sampled_block_indices"],"trade_multiplicities":c_s5_plan["trade_multiplicities"],"replicate_vectors":c_s5_vectors}
    existing_interpretation=json.loads((out/"interpretation.json").read_text());old=existing_interpretation["overall_frozen_c5_interpretation"]
    final="COUNTS AGAINST" if c_s5_safety["unacceptable_safety_breach"] else old
    existing_interpretation.update({"reporting_completion_version":"C5_T2_STATISTICAL_COMPLETION_V1","canonical_trade_results_sha256":CANONICAL_SHA,"c_s5_pooled_safety":c_s5_safety,"overall_frozen_c5_interpretation":final,"interpretation_change":{"previous":old,"current":final,"reason":"frozen C_S5 safety breach" if final!=old else "no C_S5 safety breach; primary C_BASE MIXED rule remains controlling"},"concentration_status_semantics":{"value":existing_interpretation.get("breadth_concentration"),"role":"INTERNAL_NON_ADVANCEMENT_STATUS_ONLY","scientific_classification":False,"overall_label":False,"meaning":"breadth/concentration classification is inapplicable because the pooled support preconditions were not satisfied"},"policy_trigger_replay_rerun":False})
    attempts=reconstructed_attempts(json.loads((out/"attempt_ledger.json").read_text()))
    eligibility={"source":"accepted C5 T1 readiness and replay-authorized complete-path population","inherited_not_recomputed":True,"canonical_trade_field_semantics":"t2_eligible=True records inherited upstream eligibility provenance; the completion pass does not independently recompute eligibility","population_changed":False,"policy_outcomes_recomputed":False}
    write_json(out/"paired_interval_panel.json",{"cost_scenario":"C_BASE","bootstrap":"four-entry-week moving-block","comparisons":interval_panel})
    write_json(out/"calendar_month_bootstrap.json",{"role":"SENSITIVITY_ONLY_NO_SELECTION_OR_TUNING","comparisons":month_panel})
    write_json(out/"c_s5_safety.json",c_s5_safety);write_json(out/"eligibility_provenance.json",eligibility);write_json(out/"attempt_ledger.json",attempts);write_json(out/"interpretation.json",existing_interpretation)
    compact=json.dumps(repro,sort_keys=True,separators=(",",":"),allow_nan=False).encode()
    with (out/"bootstrap_reproducibility.json.gz").open("wb") as raw:
        with gzip.GzipFile(filename="",mode="wb",fileobj=raw,mtime=0) as handle:handle.write(compact)
    produced=("paired_interval_panel.json","calendar_month_bootstrap.json","c_s5_safety.json","eligibility_provenance.json","attempt_ledger.json","interpretation.json","bootstrap_reproducibility.json.gz")
    hashes={n:sha256(out/n) for n in produced}
    completion={"version":"C5_T2_STATISTICAL_COMPLETION_V1","canonical_trade_results":{"path":"artifacts/c5_economic_exit_policy/t2/trade_results.csv","sha256":CANONICAL_SHA,"immutable":True},"concentration_status_governance":"NOT CLASSIFIED is internal/non-advancement only and is not a scientific or overall C5 label","policy_trigger_replay_invoked":False,"predictions_generated":False,"sealed_confirmation_access":False,"T3_performed":False,"thresholds_policies_costs_populations_changed":False,"output_hashes":hashes}
    write_json(out/"completion_manifest.json",completion);completion["output_hashes"]["completion_manifest.json"]=sha256(out/"completion_manifest.json")
    return {"completion":completion,"c_s5_safety":c_s5_safety,"final_interpretation":final}


if __name__=="__main__":
    import sys
    print(json.dumps(run(Path(sys.argv[1]) if len(sys.argv)>1 else Path(".")),indent=2,sort_keys=True))
