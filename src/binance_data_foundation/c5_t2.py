"""Frozen C5 T2 development-era economic replay.

Policy decisions are made before path evaluation.  This module deliberately has
no support for sealed inputs, threshold search, refitting, or T3 selection.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import math
import platform
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping

import numpy as np

from .c2_costs import COST_SCENARIOS, apply_round_trip_costs
from .c5_t1 import (ADDENDUM_SHA, AMENDMENT_SHA, BOOTSTRAP, COMPARISONS,
                    CONTRACT_SHA, POLICIES, SYMBOLS, concentration,
                    deployment_label, moving_block_bootstrap,
                    overall_classification, replay_population_gate, sha256,
                    state_score, symbol_strength, verify_governance)

T1_SHA = "8c63b9e39b0b5365014c05c74bc1c57907ad9072109d3dbc8c2c430c385f6b4a"
CUTOFFS = {
    "G1_Q75_EXIT_V1": 0.38599566214835807,
    "G1_Q90_EXIT_V1": 0.5437961868373885,
    "P1_Q75_EXIT_V1": 0.3962652238189601,
    "P1_Q90_EXIT_V1": 0.5665730461166496,
}
EXPECTED = {
    "pooled": {"trades": 439, "snapshots": 38745},
    "by_year": {"2024": {"trades": 155, "snapshots": 12275}, "2025": {"trades": 284, "snapshots": 26470}},
    "by_symbol": {"BTCUSDT": 74, "ETHUSDT": 85, "SOLUSDT": 106, "XRPUSDT": 87, "BNBUSDT": 87},
}
OUT_NAMES = ("replay_manifest.json", "population_summary.json", "trade_results.csv",
             "policy_summary.json", "cost_summary.json", "mfe_capture.json",
             "winner_truncation.json", "bootstrap_comparisons.json",
             "symbol_summary.json", "year_summary.json", "concentration.json",
             "interpretation.json")


def _json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def _load_csv(path: Path) -> list[dict]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def _authorized(repo: Path) -> tuple[list[dict], dict[str, dict[str, dict]]]:
    """Return exact whole-path rows and predictions without economic joins."""
    raw = []
    with (repo / "artifacts/c4_sequential_exit_state/local/t2_snapshots.csv").open(newline="") as handle:
        for r in csv.DictReader(handle):
            if r["target_eligible"] == "True" and r["snapshot_ts"][:4] in ("2024", "2025"):
                raw.append(r)
    raw_by_id = {r["row_id"]: r for r in raw}
    pred: dict[str, dict[str, dict]] = defaultdict(dict)
    sources = (("2024", repo / "artifacts/c4_sequential_exit_state/development_predictions_2024.csv"),
               ("2025", repo / "artifacts/c4_sequential_exit_state/locked_2025/predictions.csv"))
    for year, path in sources:
        with path.open(newline="") as handle:
            for r in csv.DictReader(handle):
                if r.get("target") == "T2" and r.get("model") in ("G1", "P1") and r["row_id"] in raw_by_id:
                    pred[r["row_id"]][r["model"]] = r
    paths: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in raw:
        paths[(r["snapshot_ts"][:4], r["trade_id"])].append(r)
    authorized = []
    for rows in paths.values():
        rows.sort(key=lambda x: (int(x["snapshot_ms"]), x["row_id"]))
        if all(set(pred[r["row_id"]]) == {"G1", "P1"} for r in rows):
            authorized.extend(rows)
    authorized.sort(key=lambda x: (int(x["entry_execution_ms"]), x["symbol"], x["trade_id"], int(x["snapshot_ms"]), x["row_id"]))
    return authorized, pred


def _minutes(repo: Path, needed: Mapping[str, tuple[int, int]]) -> dict[str, dict[int, dict]]:
    out = {}
    for symbol, (lo, hi) in needed.items():
        lookup = {}
        with gzip.open(repo / f"data/normalized/c2_history/{symbol}_1m.csv.gz", "rt", newline="") as handle:
            for r in csv.DictReader(handle):
                ts = int(r["open_time_ms"])
                if lo <= ts <= hi:
                    if ts in lookup:
                        raise RuntimeError(f"duplicate minute {symbol} {ts}")
                    vals = (float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"]))
                    if not all(math.isfinite(x) and x > 0 for x in vals):
                        raise RuntimeError(f"invalid minute {symbol} {ts}")
                    lookup[ts] = r
        out[symbol] = lookup
    return out


def _dist(values: Iterable[float | int | None]) -> dict:
    a = np.asarray([float(x) for x in values if x is not None], dtype=float)
    if not len(a):
        return {"count": 0, "mean": None, "median": None, "p05": None, "p10": None, "p90": None, "p95": None, "min": None, "max": None}
    return {"count": len(a), "mean": float(a.mean()), "median": float(np.median(a)),
            "p05": float(np.quantile(a, .05, method="linear")), "p10": float(np.quantile(a, .10, method="linear")),
            "p90": float(np.quantile(a, .90, method="linear")), "p95": float(np.quantile(a, .95, method="linear")),
            "min": float(a.min()), "max": float(a.max())}


def _union_seconds(rows: list[dict]) -> float:
    spans = sorted((int(r["entry_execution_ms"]), int(r["exit_execution_ms"])) for r in rows if r["executable"])
    total = 0
    if not spans:
        return 0.0
    start, end = spans[0]
    for a, b in spans[1:]:
        if a > end:
            total += end - start; start, end = a, b
        else:
            end = max(end, b)
    return (total + end - start) / 1000


def _summary(rows: list[dict]) -> dict:
    usable = [r for r in rows if r["executable"]]
    net = np.asarray([r["net_return"] for r in usable]); gross = np.asarray([r["gross_return"] for r in usable]); raw = np.asarray([r["raw_price_return"] for r in usable])
    q10 = float(np.quantile(net, .1, method="linear")); es = net[net <= q10]
    wins, losses = net[net > 0], net[net < 0]
    return {
        "number_of_trades": len(rows), "paired_comparison_trades": len(usable),
        "number_entering_t2_risk_set": len({r["trade_id"] for r in rows if r["t2_eligible"]}),
        "policy_triggered_exits": sum(r["triggered"] for r in rows), "unresolved_exits": len(rows)-len(usable),
        "exit_frequency": sum(r["triggered"] for r in rows)/len(rows), "raw_mean_return": float(raw.mean()),
        "gross_mean_return": float(gross.mean()), "net_mean_return": float(net.mean()),
        "gross_expectancy": float(gross.mean()), "net_expectancy": float(net.mean()),
        "median_net_return": float(np.median(net)), "fixed_notional_gross_pnl": float(gross.sum()*1000),
        "fixed_notional_net_pnl": float(net.sum()*1000), "win_rate": float(np.mean(net > 0)),
        "zero_rate": float(np.mean(net == 0)), "loss_rate": float(np.mean(net < 0)),
        "mean_win": float(wins.mean()) if len(wins) else None, "mean_loss": float(losses.mean()) if len(losses) else None,
        "downside_deviation": float(np.sqrt(np.mean(np.minimum(net, 0)**2))),
        "p05": float(np.quantile(net,.05,method="linear")), "p10": q10, "worst_trade": float(net.min()),
        "expected_shortfall_10": float(es.mean()), "average_holding_time_seconds": float(np.mean([r["holding_duration_seconds"] for r in usable])),
        "median_holding_time_seconds": float(np.median([r["holding_duration_seconds"] for r in usable])),
        "exposure_sum_seconds": float(sum(r["holding_duration_seconds"] for r in usable)), "exposure_union_seconds": _union_seconds(usable),
        "entry_fee": float(sum(r["entry_fee_quote"] for r in usable)), "exit_fee": float(sum(r["exit_fee_quote"] for r in usable)),
        "slippage": float(sum(r["slippage_cost_quote"] for r in usable)), "total_costs": float(sum(r["total_transaction_cost_quote"] for r in usable)),
    }


def _evaluation(row: dict, entry: dict, horizon: dict, minute: Mapping[int, dict]) -> dict:
    ep, xp = float(entry["entry_price"]), float(row["raw_exit_price"])
    ems, xms, hms = int(entry["entry_execution_ms"]), int(row["exit_execution_ms"]), int(horizon["p0_execution_ms"])
    held_highs = [float(r["high"]) for ts, r in minute.items() if ems < ts < xms] + [ep, xp]
    common_mfe = float(horizon["common_horizon_mfe"]); held_mfe = max(held_highs)/ep-1
    rawret = xp/ep-1; valid = common_mfe >= .005 - 1e-15; held_valid = held_mfe >= .005 - 1e-15
    future = [float(r["high"]) for ts, r in minute.items() if xms < ts < hms]
    if xms < hms: future.append(float(horizon["p0_raw_exit_price"]))
    future_max = max(future) if future else None
    out = {"common_mfe": common_mfe, "held_mfe": held_mfe, "common_capture_fraction": rawret/common_mfe if valid else None,
           "held_capture_fraction": rawret/held_mfe if held_valid else None, "common_capture_gap": common_mfe-rawret,
           "held_peak_surrender": held_mfe-rawret, "fraction_positive_mfe_surrendered": (common_mfe-rawret)/common_mfe if valid else None,
           "capture_denominator_reason": None if valid else "common_mfe_below_0_5pct", "green_to_red": held_mfe>0 and rawret<0,
           "common_green_to_red": common_mfe>0 and rawret<0, "preserved_at_least_half_peak": rawret >= .5*common_mfe if valid else None,
           "early_exit": xms < hms, "future_max_price_after_exit_to_H": future_max,
           "remaining_future_mfe_from_entry": future_max/ep-1 if future_max is not None else None,
           "opportunity_foregone": future_max/xp-1 if future_max is not None else None}
    for pct in (2,3,5): out[f"subsequent_plus_{pct}"] = future_max >= ep*(1+pct/100) if future_max is not None else None
    for pct in (.5,1,2,3,5): out[f"missed_exit_relative_{str(pct).replace('.','_')}pct"] = future_max >= xp*(1+pct/100) if future_max is not None else None
    return out


def _bootstrap(rows: list[dict], left: str, right: str, metric: str = "net_return", transform=None) -> dict:
    grouped: dict[str, dict[str, dict]] = defaultdict(dict)
    for r in rows:
        if r["cost_scenario"] == "C_BASE" and r["executable"]:
            grouped[r["trade_id"]][r["policy_id"]] = r
    values, weeks = {}, {}
    for trade, pair in grouped.items():
        if left in pair and right in pair:
            a, b = pair[left], pair[right]
            values[trade] = transform(a,b) if transform else float(a[metric])-float(b[metric])
            weeks[trade] = a["trade_entry_week"]
    result = moving_block_bootstrap(values, weeks)
    result.pop("replicates", None); result.pop("sampled_block_indices", None)
    result["comparison"] = f"{left}_minus_{right}"; result["metric"] = metric; result["paired_trades"] = len(values)
    return result


def _paired_stat_bootstrap(rows: list[dict], left: str, right: str, name: str, statistic) -> dict:
    """Block-bootstrap an arbitrary paired statistic, including nonlinear tails."""
    pair: dict[str, dict[str, dict]] = defaultdict(dict)
    for r in rows:
        if r["cost_scenario"] == "C_BASE" and r["executable"]:
            pair[r["trade_id"]][r["policy_id"]] = r
    pair = {t:p for t,p in pair.items() if left in p and right in p}
    if not pair:
        return {"available":False,"reason":"no_paired_trades","metric":name,"paired_trades":0}
    weeks = {t:datetime.fromisoformat(p[left]["trade_entry_week"]).date() for t,p in pair.items()}
    lo,hi=min(weeks.values()),max(weeks.values());lo=lo.fromordinal(lo.toordinal()-lo.weekday());hi=hi.fromordinal(hi.toordinal()-hi.weekday())
    span=(hi-lo).days//7+1
    if span<4:return {"available":False,"reason":"span_shorter_than_four_entry_weeks","metric":name,"paired_trades":len(pair)}
    at=defaultdict(list)
    for t,w in weeks.items():at[(w-lo).days//7].append(t)
    blocks=[list(range(i,i+4)) for i in range(span-3)]
    if sum(any(at[j] for j in b) for b in blocks)<2:return {"available":False,"reason":"fewer_than_two_nonempty_candidate_blocks","metric":name,"paired_trades":len(pair)}
    rng=np.random.Generator(np.random.PCG64(20240923));reps=[]
    for _ in range(2000):
        positions=[]
        while len(positions)<span:positions.extend(blocks[int(rng.integers(len(blocks)))])
        chosen=[t for j in positions[:span] for t in at[j]]
        reps.append(float(statistic([pair[t][left] for t in chosen],[pair[t][right] for t in chosen])))
    point=float(statistic([p[left] for p in pair.values()],[p[right] for p in pair.values()]))
    return {"available":True,"point_estimate":point,"ci95":np.quantile(reps,[.025,.975],method="linear").tolist(),"metric":name,"paired_trades":len(pair),"replicates":2000,"generator":"PCG64","seed":20240923,"block_length_entry_weeks":4,"multiplicity_preserved":True}


def _safety(rows: list[dict], scope_filter) -> dict:
    selected = [r for r in rows if scope_filter(r)]
    def es_delta(a,b):
        def es(x):
            v=np.asarray([r["net_return"] for r in x]);q=float(np.quantile(v,.1,method="linear"));return float(v[v<=q].mean())
        return es(a)-es(b)
    def early_mean_delta(key):
        def statistic(a,b):
            av=[float(r[key]) for r in a if r["early_exit"] and r[key] is not None];bv=[float(r[key]) for r in b if r["early_exit"] and r[key] is not None]
            return (float(np.mean(av)) if av else 0.0)-(float(np.mean(bv)) if bv else 0.0)
        return statistic
    metrics = {
        "expected_shortfall_10": _paired_stat_bootstrap(selected,"P1_Q75_EXIT_V1","G1_Q75_EXIT_V1","expected_shortfall_10",es_delta),
        "green_to_red": _bootstrap(selected,"P1_Q75_EXIT_V1","G1_Q75_EXIT_V1",transform=lambda a,b: float(a["green_to_red"])-float(b["green_to_red"])),
        "opportunity_foregone": _paired_stat_bootstrap(selected,"P1_Q75_EXIT_V1","G1_Q75_EXIT_V1","opportunity_foregone",early_mean_delta("opportunity_foregone")),
    }
    for p in (2,3,5):
        metrics[f"subsequent_plus_{p}"] = _paired_stat_bootstrap(selected,"P1_Q75_EXIT_V1","G1_Q75_EXIT_V1",f"subsequent_plus_{p}",early_mean_delta(f"subsequent_plus_{p}"))
    available = all(v.get("available") for v in metrics.values())
    breach = False
    if available:
        breach = metrics["expected_shortfall_10"]["ci95"][1] < 0 or any(v["ci95"][0] > 0 for k,v in metrics.items() if k != "expected_shortfall_10")
    return {"available": available, "unacceptable_safety_breach": breach, "intervals": metrics}


def run(repo: Path, output_dir: Path | None = None) -> dict:
    started=datetime.now(timezone.utc).isoformat()
    repo = repo.resolve(); out = output_dir or repo/"artifacts/c5_economic_exit_policy/t2"; out.mkdir(parents=True, exist_ok=True)
    verify_governance(repo)
    ready_path = repo/"artifacts/c5_economic_exit_policy/t1_readiness.json"
    if sha256(ready_path) != T1_SHA: raise RuntimeError("accepted T1 readiness hash mismatch")
    readiness = json.loads(ready_path.read_text())
    if readiness.get("T2_ready") is not True: raise RuntimeError("T2_ready must be true")
    gate = replay_population_gate(repo); layer = gate["layers"]["replay_authorized_complete_path"]
    if layer["pooled"] != EXPECTED["pooled"] or layer["by_year"] != EXPECTED["by_year"] or {s:layer["by_symbol"][s]["trades"] for s in SYMBOLS} != EXPECTED["by_symbol"]:
        raise RuntimeError("fail-closed replay population mismatch")
    authorized, predictions = _authorized(repo)
    if len(authorized) != 38745: raise RuntimeError("authorized row identity mismatch")
    paths: dict[str,list[dict]] = defaultdict(list)
    for r in authorized: paths[r["trade_id"]].append(r)
    horizons = {r["trade_id"]:r for r in _load_csv(repo/"artifacts/c2_asymmetric_exit_experiment/common_horizons_p0.csv")}
    entries = {r["trade_id"]:r for r in _load_csv(repo/"artifacts/c2_asymmetric_exit_experiment/frozen_entries.csv")}
    needed = {}
    for trade, rows in paths.items():
        e,h=entries[trade],horizons[trade]; s=e["symbol"]; lo,hi=int(e["entry_execution_ms"]),int(h["p0_execution_ms"])
        needed[s]=(min(lo,needed.get(s,(lo,hi))[0]),max(hi,needed.get(s,(lo,hi))[1]))
    minute = _minutes(repo,needed)
    base_rows=[]
    for trade, snaps in sorted(paths.items(),key=lambda x:(int(entries[x[0]]["entry_execution_ms"]),entries[x[0]]["symbol"],x[0])):
        e,h=entries[trade],horizons[trade]; symbol=e["symbol"]; hms=int(h["p0_execution_ms"]); ep=float(e["entry_price"])
        choices={"P0_HELD_V1":None}
        for policy,cutoff in CUTOFFS.items():
            model=policy[:2]; hit=None
            for s in snaps:
                score=state_score(predictions[s["row_id"]][model])
                if score >= cutoff and int(s["snapshot_ms"]) < hms:
                    hit=(s,score);break
            choices[policy]=hit
        for policy in POLICIES:
            hit=choices[policy]; xms=hms if hit is None else int(hit[0]["snapshot_ms"])
            executable=xms in minute[symbol] and xms < hms if hit is not None else True
            xp=float(h["p0_raw_exit_price"]) if hit is None else (float(minute[symbol][xms]["open"]) if executable else None)
            row={"trade_id":trade,"symbol":symbol,"year":e["entry_execution_ts"][:4],"trade_entry_week":snaps[0]["trade_entry_week"],
                 "entry_fixture_id":e["entry_fixture_id"],"entry_execution_ts":e["entry_execution_ts"],"entry_execution_ms":int(e["entry_execution_ms"]),
                 "raw_entry_price":ep,"policy_id":policy,"model_id":None if policy.startswith("P0") else policy[:2],
                 "rank_level":None if policy.startswith("P0") else policy[3:6],"score_cutoff":CUTOFFS.get(policy),
                 "trigger_row_id":hit[0]["row_id"] if hit else None,"trigger_snapshot_ts":hit[0]["snapshot_ts"] if hit else None,
                 "trigger_score":hit[1] if hit else None,"exit_decision_ts":hit[0]["snapshot_ts"] if hit else h["p0_decision_ts"],
                 "exit_execution_ts":hit[0]["snapshot_ts"] if hit else h["p0_execution_ts"],"exit_execution_ms":xms,
                 "raw_exit_price":xp,"exit_reason":"POLICY" if hit else "P0_FALLBACK","executable":executable,
                 "censor_reason":None if executable else "missing_immediate_next_1m_open","triggered":hit is not None,
                 "t2_eligible":True,"holding_duration_seconds":(xms-int(e["entry_execution_ms"]))/1000}
            if executable: row.update(_evaluation(row,e,h,minute[symbol]))
            base_rows.append(row)
    results=[]
    for row in base_rows:
        for case in COST_SCENARIOS:
            r=dict(row);r["cost_scenario"]=case.scenario_id;r["entry_fee_rate"]=case.fee_rate;r["exit_fee_rate"]=case.fee_rate;r["entry_slippage_rate"]=case.slippage_rate;r["exit_slippage_rate"]=case.slippage_rate
            if r["executable"]:
                c=apply_round_trip_costs(r["raw_entry_price"],r["raw_exit_price"],1000,case)
                r.update({"raw_price_return":c["raw_price_return"],"gross_return":c["gross_return"],"net_return":c["net_return"],
                          "entry_price_after_slippage":c["entry_price_after_slippage"],"exit_price_after_slippage":c["exit_price_after_slippage"],
                          "entry_executed_notional":1000.0,"exit_executed_notional":c["quantity"]*c["exit_price_after_slippage"],
                          "entry_fee_quote":c["entry_fee_usdt"],"exit_fee_quote":c["exit_fee_usdt"],
                          "entry_slippage_quote":c["quantity"]*(c["entry_price_after_slippage"]-r["raw_entry_price"]),
                          "exit_slippage_quote":c["quantity"]*(r["raw_exit_price"]-c["exit_price_after_slippage"]),
                          "slippage_cost_quote":c["slippage_usdt"],"total_transaction_cost_quote":c["fees_usdt"]+c["slippage_usdt"],
                          "fixed_replay_legs":2,"fixed_replay_notional":1000.0})
            results.append(r)
    results.sort(key=lambda r:(r["entry_execution_ms"],r["symbol"],r["trade_id"],POLICIES.index(r["policy_id"]),[x.scenario_id for x in COST_SCENARIOS].index(r["cost_scenario"])))
    fields=sorted({k for r in results for k in r});
    with (out/"trade_results.csv").open("w",newline="") as handle:
        w=csv.DictWriter(handle,fieldnames=fields,lineterminator="\n");w.writeheader();w.writerows(results)
    scopes={"pooled_trade_weighted":lambda r:True,**{s:(lambda r,s=s:r["symbol"]==s) for s in SYMBOLS},**{y:(lambda r,y=y:r["year"]==y) for y in ("2024","2025")}}
    policy_summary={}
    for scope,fn in scopes.items():
        policy_summary[scope]={}
        for p in POLICIES:
            policy_summary[scope][p]={c.scenario_id:_summary([r for r in results if fn(r) and r["policy_id"]==p and r["cost_scenario"]==c.scenario_id]) for c in COST_SCENARIOS}
    # Equal-weight symbols: average symbol-level metrics; additive totals remain trade-weighted and are labeled.
    policy_summary["pooled_equal_weight_symbol"]={}
    for p in POLICIES:
        policy_summary["pooled_equal_weight_symbol"][p]={}
        for c in COST_SCENARIOS:
            ss=[policy_summary[s][p][c.scenario_id] for s in SYMBOLS]
            policy_summary["pooled_equal_weight_symbol"][p][c.scenario_id]={k:float(np.mean([x[k] for x in ss])) if all(isinstance(x.get(k),(int,float)) for x in ss) else None for k in ss[0]}
    comparisons={}
    for scope,fn in scopes.items():
        comparisons[scope]={}
        for left,right in COMPARISONS:
            comparisons[scope][f"{left}_minus_{right}"]=_bootstrap([r for r in results if fn(r)],left,right)
    mfe_capture={}; trunc={}
    for scope,fn in scopes.items():
        mfe_capture[scope]={};trunc[scope]={}
        for p in POLICIES:
            rr=[r for r in results if fn(r) and r["policy_id"]==p and r["cost_scenario"]=="C_BASE" and r["executable"]]
            mfe_capture[scope][p]={k:_dist(r[k] for r in rr) for k in ("common_mfe","held_mfe","common_capture_fraction","held_capture_fraction","common_capture_gap","held_peak_surrender","fraction_positive_mfe_surrendered")}
            mfe_capture[scope][p].update({"green_to_red":{"count":sum(r["green_to_red"] for r in rr),"rate":float(np.mean([r["green_to_red"] for r in rr]))},"preserved_at_least_half_peak":{"defined":sum(r["preserved_at_least_half_peak"] is not None for r in rr),"rate":float(np.mean([r["preserved_at_least_half_peak"] for r in rr if r["preserved_at_least_half_peak"] is not None]))}})
            early=[r for r in rr if r["early_exit"]]
            trunc[scope][p]={"early_exit_count":len(early),"realized_exit_return":_dist(r["raw_price_return"] for r in early),"remaining_future_mfe":_dist(r["remaining_future_mfe_from_entry"] for r in early),"opportunity_foregone":_dist(r["opportunity_foregone"] for r in early),"policy_versus_p0_underperformance_rate":float(np.mean([r["raw_price_return"] < float(horizons[r["trade_id"]]["p0_raw_exit_price"])/r["raw_entry_price"]-1 for r in early])) if early else None,**{f"subsequent_plus_{x}":{"count":sum(r[f"subsequent_plus_{x}"] for r in early),"rate":float(np.mean([r[f"subsequent_plus_{x}"] for r in early])) if early else None} for x in (2,3,5)}}
    safety={scope:_safety(results,fn) for scope,fn in scopes.items()}
    eligible=EXPECTED["by_symbol"]
    symbol_summary={}
    for s in SYMBOLS:
        path=comparisons[s]["P1_Q75_EXIT_V1_minus_G1_Q75_EXIT_V1"]; practical=comparisons[s]["P1_Q75_EXIT_V1_minus_P0_HELD_V1"]
        symbol_summary[s]={"replay_authorized_complete_path_trades":eligible[s],"supported":eligible[s]>=50,"p1_q75_minus_g1_q75_c_base_net_expectancy":path["point_estimate"],"p1_q75_minus_p0_c_base_net_expectancy":practical["point_estimate"],"path_ci95":path["ci95"],"practical_ci95":practical["ci95"],"statistical_strength":symbol_strength(eligible[s],path["point_estimate"],tuple(path["ci95"]),practical["point_estimate"]),"safety":safety[s],"deployment_suitability":deployment_label(eligible[s],path["point_estimate"],practical["point_estimate"],tuple(path["ci95"]),tuple(practical["ci95"]),safety[s]["unacceptable_safety_breach"],safety[s]["available"]),"policy_economics":policy_summary[s]}
    cb=[r for r in results if r["cost_scenario"]=="C_BASE"]
    def contrib(left,right,s):
        a={r["trade_id"]:r for r in cb if r["symbol"]==s and r["policy_id"]==left and r["executable"]};b={r["trade_id"]:r for r in cb if r["symbol"]==s and r["policy_id"]==right and r["executable"]};return sum((a[t]["net_return"]-b[t]["net_return"])*1000 for t in sorted(a.keys()&b.keys()))
    cp0={s:contrib("P1_Q75_EXIT_V1","P0_HELD_V1",s) for s in SYMBOLS};cg1={s:contrib("P1_Q75_EXIT_V1","G1_Q75_EXIT_V1",s) for s in SYMBOLS}
    pooled_path=comparisons["pooled_trade_weighted"]["P1_Q75_EXIT_V1_minus_G1_Q75_EXIT_V1"];pooled_practical=comparisons["pooled_trade_weighted"]["P1_Q75_EXIT_V1_minus_P0_HELD_V1"]
    s5a=policy_summary["pooled_trade_weighted"]["P1_Q75_EXIT_V1"]["C_S5"]["net_expectancy"]-policy_summary["pooled_trade_weighted"]["G1_Q75_EXIT_V1"]["C_S5"]["net_expectancy"]
    s5b=policy_summary["pooled_trade_weighted"]["P1_Q75_EXIT_V1"]["C_S5"]["net_expectancy"]-policy_summary["pooled_trade_weighted"]["P0_HELD_V1"]["C_S5"]["net_expectancy"]
    pooled_supports=pooled_path["point_estimate"]>0 and pooled_practical["point_estimate"]>0 and pooled_path["ci95"][0]>0 and not safety["pooled_trade_weighted"]["unacceptable_safety_breach"] and safety["pooled_trade_weighted"]["available"] and s5a>0 and s5b>0
    conc=concentration(cp0,cg1,eligible,{s:tuple(symbol_summary[s]["path_ci95"]) for s in SYMBOLS},pooled_supports)
    label=overall_classification(True,pooled_path["point_estimate"],pooled_practical["point_estimate"],tuple(pooled_path["ci95"]),tuple(pooled_practical["ci95"]),safety["pooled_trade_weighted"]["unacceptable_safety_breach"],safety["pooled_trade_weighted"]["available"],s5a>0 and s5b>0,conc["classification"])
    identity=[{"row_id":r["row_id"],"trade_id":r["trade_id"],"symbol":r["symbol"],"snapshot_ms":int(r["snapshot_ms"])} for r in authorized]
    pop={"status":"PASS","counts":layer,"expected":EXPECTED,"replay_row_identity_sha256":hashlib.sha256(json.dumps(identity,sort_keys=True,separators=(",",":")).encode()).hexdigest(),"replay_trade_identity_sha256":hashlib.sha256(json.dumps(sorted(paths),separators=(",",":")).encode()).hexdigest()}
    manifest={"stage":"C5_T2_DEVELOPMENT_ECONOMIC_REPLAY","T2_ready_verified":True,"policies":list(POLICIES),"Q75_role":"PRIMARY","Q90_role":"SENSITIVITY_ONLY_CANNOT_RESCUE_Q75","cutoffs":CUTOFFS,"costs":{x.scenario_id:{"fee_per_leg":x.fee_rate,"adverse_slippage_per_leg":x.slippage_rate} for x in COST_SCENARIOS},"bootstrap":BOOTSTRAP,"sealed_confirmation_access":False,"T3_performed":False}
    interpretation={"overall_frozen_c5_interpretation":label,"Q75_determined_advancement":True,"Q90_cannot_rescue_Q75":True,"t3_policy_freeze_performed":False,"development_era_evidence":True,"pooled_primary":pooled_path,"pooled_practical":pooled_practical,"pooled_control":comparisons["pooled_trade_weighted"]["G1_Q75_EXIT_V1_minus_P0_HELD_V1"],"pooled_safety":safety["pooled_trade_weighted"],"c_s5_survival":{"p1_minus_g1":s5a,"p1_minus_p0":s5b,"survives":s5a>0 and s5b>0},"breadth_concentration":conc["classification"]}
    _json(out/"replay_manifest.json",manifest);_json(out/"population_summary.json",pop);_json(out/"policy_summary.json",policy_summary)
    _json(out/"cost_summary.json",{scope:{p:policy_summary[scope][p] for p in POLICIES} for scope in policy_summary});_json(out/"mfe_capture.json",mfe_capture);_json(out/"winner_truncation.json",trunc)
    _json(out/"bootstrap_comparisons.json",{"parameters":BOOTSTRAP,"comparisons":comparisons,"safety":safety});_json(out/"symbol_summary.json",symbol_summary);_json(out/"year_summary.json",{y:policy_summary[y] for y in ("2024","2025")});_json(out/"concentration.json",conc);_json(out/"interpretation.json",interpretation)
    hashes={name:sha256(out/name) for name in OUT_NAMES}
    config_hash=hashlib.sha256(json.dumps({"policies":POLICIES,"cutoffs":CUTOFFS,"costs":manifest["costs"],"bootstrap":BOOTSTRAP},sort_keys=True,separators=(",",":")).encode()).hexdigest()
    repro={"governance_hashes":{"contract":CONTRACT_SHA,"addendum":ADDENDUM_SHA,"prediction_population_amendment":AMENDMENT_SHA},"t1_readiness_sha256":T1_SHA,"population_identity_hashes":{"rows":pop["replay_row_identity_sha256"],"trades":pop["replay_trade_identity_sha256"]},"prediction_artifact_hashes":{"2024":sha256(repo/"artifacts/c4_sequential_exit_state/development_predictions_2024.csv"),"2025":sha256(repo/"artifacts/c4_sequential_exit_state/locked_2025/predictions.csv")},"economic_input_hashes":{"entries":sha256(repo/"artifacts/c2_asymmetric_exit_experiment/frozen_entries.csv"),"p0_horizons":sha256(repo/"artifacts/c2_asymmetric_exit_experiment/common_horizons_p0.csv")},"source_code_sha256":sha256(Path(__file__)),"configuration_sha256":config_hash,"policy_cutoffs":CUTOFFS,"cost_assumptions":manifest["costs"],"bootstrap_parameters":BOOTSTRAP,"python":platform.python_version(),"numpy":np.__version__,"output_hashes":hashes,"sealed_confirmation_access":False,"deterministic_core_outputs":True,"timestamp_bearing_manifests_nonsemantic":True}
    _json(out/"reproducibility.json",repro)
    _json(out/"attempt_ledger.json",{"attempts":[{"purpose":"authorized C5 T2 development-era economic replay","start_timestamp_utc":started,"end_timestamp_utc":datetime.now(timezone.utc).isoformat(),"status":"PASS","configuration_sha256":config_hash,"code_sha256":repro["source_code_sha256"],"input_manifest_sha256":hashlib.sha256(json.dumps(repro["population_identity_hashes"],sort_keys=True,separators=(",",":")).encode()).hexdigest(),"output_hashes":hashes}],"nonsemantic_timestamp_fields":["start_timestamp_utc","end_timestamp_utc"]})
    return {"interpretation":interpretation,"output_hashes":{**hashes,"reproducibility.json":sha256(out/"reproducibility.json")},"population":pop}


def main(argv: list[str] | None = None) -> int:
    args=sys.argv[1:] if argv is None else argv
    repo=Path(args[0]) if args else Path(".")
    print(json.dumps(run(repo),indent=2,sort_keys=True))
    return 0


if __name__ == "__main__": raise SystemExit(main())
