"""C15 descriptive temporal structure of the frozen C14 DELTA_V target."""
from __future__ import annotations

import hashlib, json, os, platform, sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from . import c7_t1 as c7
from . import c10_post_t2 as c10
from . import c12_post_t2_warning as c12
from . import c14_post_t2_economic_state as c14

CONTRACT_SHA256 = "b0e71b449e0c9c4958a1e49e3aad4477cff0f1791a05281045235683930f67b0"
CONTRACT_REL = "contracts/C15_economic_state_temporal_structure_CONTRACT.md"
OUTPUT_REL = "artifacts/c15_economic_state_temporal_structure"
HORIZONS = (1, 2, 5, 10, 15, 30, 60)
TIME_BANDS = c14.TIME_BANDS
STATES = ("HOLD_BETTER", "EXIT_BETTER")

def reject_2026(path):
    if any("2026" in part for part in os.fspath(path).replace("\\", "/").lower().split("/")):
        raise PermissionError("C15 prohibits 2026 data or metadata access")

def sha(path: Path) -> str:
    reject_2026(path); h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""): h.update(block)
    return h.hexdigest()

def write(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n")

def state(delta):
    return "HOLD_BETTER" if delta > 0 else "EXIT_BETTER" if delta < 0 else "EXACT_ZERO"

def magnitude_band(value):
    x = abs(value)
    if x < .001: return "<0.10%"
    if x < .0025: return "0.10% to <0.25%"
    if x < .005: return "0.25% to <0.50%"
    if x < .01: return "0.50% to <1.00%"
    return ">=1.00%"

def dist(values):
    a = np.asarray(list(values), float)
    if not len(a): return None
    return {"count": len(a), "mean": float(a.mean()), "median": float(np.median(a)),
            "p10": float(np.quantile(a, .1)), "p25": float(np.quantile(a, .25)),
            "p75": float(np.quantile(a, .75)), "p90": float(np.quantile(a, .9)),
            "min": float(a.min()), "max": float(a.max())}

def trajectories(rows):
    out = defaultdict(list)
    for r in rows: out[r["trade_id"]].append(r)
    for rr in out.values(): rr.sort(key=lambda x: x["state_ms"])
    return dict(sorted(out.items()))

def dwell_data(rr):
    signs = [r["economic_state"] for r in rr if r["economic_state"] in STATES]
    runs = defaultdict(list)
    if signs:
        current, n = signs[0], 1
        for x in signs[1:]:
            if x == current: n += 1
            else: runs[current].append(n); current, n = x, 1
        runs[current].append(n)
    return runs

def trade_summary(rows):
    result = []
    for tid, rr in trajectories(rows).items():
        signs = [r["economic_state"] for r in rr if r["economic_state"] in STATES]
        he = sum(a == "HOLD_BETTER" and b == "EXIT_BETTER" for a, b in zip(signs, signs[1:]))
        eh = sum(a == "EXIT_BETTER" and b == "HOLD_BETTER" for a, b in zip(signs, signs[1:]))
        runs = dwell_data(rr); n = len(rr); nh = sum(r["economic_state"] == "HOLD_BETTER" for r in rr); ne = sum(r["economic_state"] == "EXIT_BETTER" for r in rr)
        transitions = he + eh
        category = "MONOSTATE" if transitions == 0 else "SINGLE_TRANSITION" if transitions == 1 else "LOW_OSCILLATION" if transitions <= 3 else "HIGH_OSCILLATION"
        result.append({"trade_id": tid, "year": rr[0]["year"], "symbol": rr[0]["symbol"], "event_label": rr[0]["event_label"],
            "eligible_snapshots": n, "hold_snapshots": nh, "exit_snapshots": ne, "exact_zero_snapshots": n-nh-ne,
            "fraction_hold": nh/n, "fraction_exit": ne/n, "hold_to_exit": he, "exit_to_hold": eh,
            "total_transitions": transitions, "initial_state": signs[0] if signs else "EXACT_ZERO",
            "final_state": signs[-1] if signs else "EXACT_ZERO", "longest_hold_run": max(runs["HOLD_BETTER"], default=0),
            "longest_exit_run": max(runs["EXIT_BETTER"], default=0),
            "median_hold_dwell": float(np.median(runs["HOLD_BETTER"])) if runs["HOLD_BETTER"] else None,
            "median_exit_dwell": float(np.median(runs["EXIT_BETTER"])) if runs["EXIT_BETTER"] else None,
            "path_category": category})
    return result

def summarize_trades(ts):
    fields = ("eligible_snapshots","hold_snapshots","exit_snapshots","fraction_hold","fraction_exit","hold_to_exit","exit_to_hold","total_transitions","longest_hold_run","longest_exit_run")
    return {"trades": len(ts), "distributions": {f: dist(t[f] for t in ts) for f in fields},
            "initial_states": dict(Counter(t["initial_state"] for t in ts)), "final_states": dict(Counter(t["final_state"] for t in ts)),
            "hold_dwell_trade_medians": dist(t["median_hold_dwell"] for t in ts if t["median_hold_dwell"] is not None),
            "exit_dwell_trade_medians": dist(t["median_exit_dwell"] for t in ts if t["median_exit_dwell"] is not None)}

def persistence(rows, horizons=HORIZONS):
    by_trade = trajectories(rows); out = {}
    for k in horizons:
        by_state = {}
        for s in STATES:
            trade_probs = []
            for rr in by_trade.values():
                lookup = {r["state_ms"]: r for r in rr}; pairs = [(r, lookup.get(r["state_ms"] + k*c10.MINUTE)) for r in rr if r["economic_state"] == s]
                pairs = [(a,b) for a,b in pairs if b is not None and b["economic_state"] in STATES]
                if pairs: trade_probs.append(sum(b["economic_state"] == s for _,b in pairs)/len(pairs))
            same = float(np.mean(trade_probs)) if trade_probs else None
            by_state[s] = {"eligible_trades": len(trade_probs), "whole_trade_weighted_same_state_probability": same,
                           "transition_probability": None if same is None else 1-same}
        out[str(k)] = by_state
    return {"weighting": "mean of within-trade conditional probabilities; each eligible trade has equal weight", "horizons_minutes": out}

def transition_events(rows):
    events=[]
    for tid,rr in trajectories(rows).items():
        for i in range(1,len(rr)):
            a,b=rr[i-1],rr[i]
            if a["economic_state"] in STATES and b["economic_state"] in STATES and a["economic_state"] != b["economic_state"]:
                events.append({"trade_id":tid,"index":i,"direction":a["economic_state"]+" -> "+b["economic_state"],"row":b,"trajectory":rr})
    return events

def transition_magnitudes(rows):
    offsets=(-5,-2,-1,0,1,2,5); out={}
    for direction in ("HOLD_BETTER -> EXIT_BETTER","EXIT_BETTER -> HOLD_BETTER"):
        ev=[e for e in transition_events(rows) if e["direction"]==direction]; vals={str(x):[] for x in offsets}
        for e in ev:
            lookup={r["state_ms"]:r for r in e["trajectory"]}; t=e["row"]["state_ms"]
            for x in offsets:
                if (r:=lookup.get(t+x*c10.MINUTE)) is not None: vals[str(x)].append(r["delta_v"])
        out[direction]={"transitions":len(ev),"offset_minutes":{x:dist(v) for x,v in vals.items()}}
    return out

def near_zero(rows):
    labels=("<0.10%","0.10% to <0.25%","0.25% to <0.50%","0.50% to <1.00%",">=1.00%")
    ev=transition_events(rows); counts=Counter(magnitude_band(e["row"]["delta_v"]) for e in ev)
    return {"transition_value":"DELTA_V at transition snapshot","transitions":len(ev),"bands":{x:{"count":counts[x],"fraction":counts[x]/len(ev) if ev else None} for x in labels}}

def positive_concentration(rows):
    totals=[]; extrema=[]
    for tid,rr in trajectories(rows).items():
        totals.append((tid,sum(max(0,r["delta_v"]) for r in rr)))
        extrema.append((max([0.0]+[r["delta_v"] for r in rr]),min(r["delta_v"] for r in rr)))
    values=np.sort(np.asarray([x[1] for x in totals],float))[::-1]; total=float(values.sum()); n=len(values)
    shares={f"top_{p}_percent":float(values[:max(1,int(np.ceil(n*p/100)))].sum()/total) if total else None for p in (1,5,10,20)}
    lorenz=[]
    asc=np.sort(values)
    for p in (0,1,5,10,20,25,50,75,80,90,95,99,100):
        count=int(np.ceil(n*p/100)); lorenz.append({"bottom_trade_percent":p,"cumulative_positive_delta_v_fraction":float(asc[:count].sum()/total) if total else None})
    gini=None if not total else float((2*np.sum((np.arange(1,n+1))*asc)/(n*total))-(n+1)/n)
    return {"trade_measure":"sum of positive snapshot DELTA_V within trade","trades":n,"total_positive_delta_v":total,
            "top_contribution":shares,"lorenz_style":lorenz,"gini":gini,
            "maximum_positive_delta_v_per_trade":dist(x[0] for x in extrema),"minimum_delta_v_per_trade":dist(x[1] for x in extrema)}

def band_name(minutes):
    for name,lo,hi in TIME_BANDS:
        if (minutes>=lo if lo==0 else minutes>lo) and minutes<=hi:return name

def temporal_metrics(rows, location=None):
    rr=rows if location is None else [r for r in rows if band_name(location(r)) is not None]
    p=persistence(rr,(5,))["horizons_minutes"]["5"]
    ev=transition_events(rr); possible=sum(max(0,len(x)-1) for x in trajectories(rr).values())
    vals=np.asarray([r["delta_v"] for r in rr],float)
    return {"trades":len({r["trade_id"] for r in rr}),"snapshots":len(rr),"transitions":len(ev),"transition_rate":len(ev)/possible if possible else None,
            "hold_persistence_5m":p["HOLD_BETTER"]["whole_trade_weighted_same_state_probability"],
            "exit_persistence_5m":p["EXIT_BETTER"]["whole_trade_weighted_same_state_probability"],
            "mean_delta_v":float(vals.mean()) if len(vals) else None,"median_delta_v":float(np.median(vals)) if len(vals) else None,
            "fraction_hold":float(np.mean(vals>0)) if len(vals) else None}

def grouped_summary(rows, key):
    return {str(v): temporal_metrics([r for r in rows if key(r)==v]) for v in sorted({key(r) for r in rows},key=str)}

def elapsed_summary(rows):
    out={"since_t2":{},"remaining_to_p0":{}}
    for name,_,_ in TIME_BANDS:
        a=[r for r in rows if band_name((r["state_ms"]-r["t0_ms"])/c10.MINUTE)==name]
        b=[r for r in rows if band_name((r["p0_ms"]-r["state_ms"])/c10.MINUTE)==name]
        out["since_t2"][name]=temporal_metrics(a);out["remaining_to_p0"][name]=temporal_metrics(b)
    return out

def category_distribution(ts, rows):
    by=trajectories(rows); out={}
    for cat in ("MONOSTATE","SINGLE_TRANSITION","LOW_OSCILLATION","HIGH_OSCILLATION"):
        tt=[t for t in ts if t["path_category"]==cat]; ids={t["trade_id"] for t in tt}; rr=[r for tid in ids for r in by[tid]]
        out[cat]={"trades":len(tt),"percentage":len(tt)/len(ts) if ts else None,"snapshots":len(rr),"delta_v":dist(r["delta_v"] for r in rr),
                  "year":dict(Counter(str(t["year"]) for t in tt)),"symbol":dict(Counter(t["symbol"] for t in tt)),"event_class":dict(Counter(t["event_label"] for t in tt))}
    return out

def reconstruct_rows(repo):
    data=c12.generate_frozen_panel(repo); manifest=json.loads((repo/"artifacts/c7_full_population_t2_exit_overlay/population_manifest.json").read_text())
    source={r["trade_id"]:r for r in manifest["rows"]}; trades={t["trade_id"]:t for t in data["trades"]}; rows=[]; excluded=Counter()
    for r in data["binary_rows"]:
        tr=trades[r["trade_id"]]; target=c14.target_for_snapshot(r,tr,data["markets"][r["symbol"]],float(source[r["trade_id"]]["p0_raw_exit_price"]),"C_BASE")
        if not target["eligible"]: excluded[target["reason"]]+=1; continue
        rows.append(r|target|{"event_label":tr["terminal"],"p0_ms":tr["p0_ms"]})
    return data,rows,excluded

def run(repo: Path):
    reject_2026(repo)
    if os.environ.get("CONDA_DEFAULT_ENV") != "binance-v2-research": raise RuntimeError("conda environment must be binance-v2-research")
    contract=repo/CONTRACT_REL
    if sha(contract)!=CONTRACT_SHA256: raise RuntimeError("C15 contract changed after prospective freeze")
    out=repo/OUTPUT_REL;out.mkdir(parents=True,exist_ok=True);data,rows,excluded=reconstruct_rows(repo);ts=trade_summary(rows)
    scored={(r["trade_id"],r["state_ms"]) for r in data["scored_rows"]}
    pop={"source_first_t2_trades":845,"binary_source_trades":843,"causal_physical_snapshots":len(data["binary_rows"]),"eligible_target_snapshots":len(rows),
         "eligible_target_trades":len(ts),"ineligible_snapshots":dict(excluded),"frozen_scored_snapshots":sum((r["trade_id"],r["state_ms"]) in scored for r in rows),
         "frozen_scored_trades":len({r["trade_id"] for r in rows if (r["trade_id"],r["state_ms"]) in scored}),"exact_zero_snapshots":sum(r["economic_state"]=="EXACT_ZERO" for r in rows),
         "outcomes":dict(Counter(t["event_label"] for t in ts))}
    persistence_all=persistence(rows); categories=category_distribution(ts,rows); tm=transition_magnitudes(rows); nz=near_zero(rows); tail=positive_concentration(rows); elapsed=elapsed_summary(rows)
    event=grouped_summary(rows,lambda r:r["event_label"]);year=grouped_summary(rows,lambda r:r["year"]);symbol=grouped_summary(rows,lambda r:r["symbol"])
    median_trans=float(np.median([t["total_transitions"] for t in ts])); both_years_low=any(all(year[str(y)][f"{s.lower().split('_')[0]}_persistence_5m"]<.6 for y in (2024,2025)) for s in STATES)
    repeated=categories["LOW_OSCILLATION"]["trades"]+categories["HIGH_OSCILLATION"]["trades"] > categories["MONOSTATE"]["trades"]+categories["SINGLE_TRANSITION"]["trades"]
    persistent=median_trans<=1 and all(persistence_all["horizons_minutes"]["5"][s]["whole_trade_weighted_same_state_probability"]>=.7 for s in STATES) and all(year[str(y)][f"{s.lower().split('_')[0]}_persistence_5m"]>=.7 for y in (2024,2025) for s in STATES)
    unstable=median_trans>=4 or both_years_low or repeated
    label="PERSISTENT_ECONOMIC_STATE" if persistent else "HIGHLY_UNSTABLE_ECONOMIC_STATE" if unstable else "MIXED_TEMPORAL_STRUCTURE"
    predicates={"median_trade_transitions":median_trans,"persistent":{"median_le_1":median_trans<=1,"both_states_5m_ge_70pct":all(persistence_all["horizons_minutes"]["5"][s]["whole_trade_weighted_same_state_probability"]>=.7 for s in STATES),"directionally_consistent_both_years":all(year[str(y)][f"{s.lower().split('_')[0]}_persistence_5m"]>=.7 for y in (2024,2025) for s in STATES)},"highly_unstable":{"median_ge_4":median_trans>=4,"either_state_below_60pct_in_both_years":any(all(year[str(y)][f"{s.lower().split('_')[0]}_persistence_5m"]<.6 for y in (2024,2025)) for s in STATES),"most_transitions_repeated_oscillations":repeated},"classification":label}
    implication={"PERSISTENT_ECONOMIC_STATE":"A: future checkpoint may investigate richer causal information","HIGHLY_UNSTABLE_ECONOMIC_STATE":"B: future checkpoint should investigate persistent/sequential economic value rather than feature expansion","MIXED_TEMPORAL_STRUCTURE":"C: identify which aspect is stable and which is unstable before choosing feature expansion or sequential-value modeling"}[label]
    files={"run_manifest":{"version":"C15_RUN_V1","contract_sha256":CONTRACT_SHA256,"python":sys.version,"numpy":np.__version__,"platform":platform.platform(),"conda_environment":"binance-v2-research"},
      "provenance":{"contract_sha256":CONTRACT_SHA256,"c14_target_builder":"binance_data_foundation.c14_post_t2_economic_state.target_for_snapshot","c14_contract_sha256":c14.CONTRACT_SHA256,"cost_model":"C_BASE","inputs":{CONTRACT_REL:sha(contract),c14.CONTRACT_REL:sha(repo/c14.CONTRACT_REL),"c7_population":sha(repo/"artifacts/c7_full_population_t2_exit_overlay/population_manifest.json")},"no_2026_access":True},
      "population_reconciliation":pop,"trade_transition_summary":{"per_trade":ts,"summary":summarize_trades(ts)},"transition_distribution":categories,
      "persistence_by_horizon":persistence_all,"transition_magnitude_summary":tm,"near_zero_transition_summary":nz,"right_tail_concentration":tail,
      "elapsed_time_summary":elapsed,"event_class_summary":event,"year_summary":year,"symbol_summary":symbol,"interpretation_predicates":predicates}
    for name,value in files.items():write(out/f"{name}.json",value)
    final={"contract_sha256":CONTRACT_SHA256,"population":pop,"transition_summary":summarize_trades(ts),"transition_distribution":categories,"persistence":persistence_all,
           "year_stability":year,"symbol_stability":symbol,"event_class_structure":event,"transition_magnitude":tm,"near_zero_transitions":nz,"right_tail":tail,"elapsed_time":elapsed,
           "interpretation":label,"c16_direction":implication,"limitations":["descriptive realized future-derived target; not a live feature or policy","physical causal panel excludes 51 binary source trades with no eligible snapshots","snapshot DELTA_V observations are dependent within trades; persistence uses whole-trade weighting","EXACT_ZERO is retained but excluded from binary sign transitions and conditional persistence"],
           "confirmations":{"model_trained":False,"policy_defined":False,"pnl_or_threshold_optimized":False,"horizon_searched":False,"c7_c14_scientific_behavior_modified":False,"accessed_2026":False,"c16_started":False}}
    write(out/"final_summary.json",final)
    hashes={p.name:sha(p) for p in sorted(out.glob("*.json")) if p.name!="reproducibility_hashes.json"};write(out/"reproducibility_hashes.json",hashes)
    return final
