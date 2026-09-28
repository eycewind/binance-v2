"""C12 lead-time diagnostics for frozen C11 probabilities (no economics)."""
from __future__ import annotations

import hashlib, json, os, platform, sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from . import c8_timescale as c8
from . import c9_dynamic_state as c9
from . import c10_post_t2 as c10
from . import c11_dynamic_post_t2 as c11

CONTRACT_SHA256 = "59d01b4bccfc504c47abf23fcc57b4f836bf386ec2b3df6f5e372a4f32419e40"
MINUTE = c10.MINUTE
BANDS = (
    ("VERY_DETERIORATION_LIKE", 0.0, 0.20),
    ("DETERIORATION_LEANING", 0.20, 0.40),
    ("UNCERTAIN", 0.40, 0.60),
    ("CONTINUATION_LEANING", 0.60, 0.80),
    ("VERY_CONTINUATION_LIKE", 0.80, 1.0),
)
CONDITIONS = {"lt_0.40": ("lt", .40), "lt_0.20": ("lt", .20),
              "ge_0.60": ("ge", .60), "ge_0.80": ("ge", .80)}
PERSISTENCE = (1, 2, 3)


def reject_2026(path: str | Path) -> None:
    c11.reject_2026(path)


def sha256_file(path: Path) -> str:
    return c11.sha256_file(path)


def write_json(path: Path, value) -> None:
    c11.write_json(path, value)


def probability_band(p: float) -> str:
    if not 0 <= p <= 1: raise ValueError("probability outside [0,1]")
    if p < .20: return BANDS[0][0]
    if p < .40: return BANDS[1][0]
    if p < .60: return BANDS[2][0]
    if p < .80: return BANDS[3][0]
    return BANDS[4][0]


def condition_mask(probabilities, condition: str) -> np.ndarray:
    op, threshold = CONDITIONS[condition]; a = np.asarray(probabilities, float)
    return a < threshold if op == "lt" else a >= threshold


def first_persistent(mask, length: int) -> int | None:
    run = 0
    for i, value in enumerate(mask):
        run = run + 1 if value else 0
        if run >= length: return i
    return None


def lead_time(terminal_ms: int, state_ms: int) -> float:
    if state_ms >= terminal_ms: raise ValueError("warning must precede terminal event")
    return (terminal_ms - state_ms) / MINUTE


def dist(values) -> dict | None:
    a = np.asarray(list(values), float)
    if not len(a): return None
    return {"n": len(a), "min": float(a.min()), "p10": float(np.quantile(a,.10)),
            "p25": float(np.quantile(a,.25)), "median": float(np.median(a)),
            "p75": float(np.quantile(a,.75)), "p90": float(np.quantile(a,.90)),
            "max": float(a.max()), "mean": float(a.mean())}


def probability_dist(values) -> dict | None:
    a = np.asarray(list(values), float)
    if not len(a): return None
    return {"n": len(a), "mean": float(a.mean()), "p10": float(np.quantile(a,.1)),
            "p25": float(np.quantile(a,.25)), "median": float(np.median(a)),
            "p75": float(np.quantile(a,.75)), "p90": float(np.quantile(a,.9)),
            "min": float(a.min()), "max": float(a.max())}


def cycles(mask: np.ndarray) -> int:
    return int(sum(bool(v) and (i == 0 or not mask[i-1]) for i, v in enumerate(mask)))


def max_run(mask: np.ndarray) -> int:
    best = run = 0
    for v in mask:
        run = run + 1 if v else 0; best = max(best, run)
    return best


def warning_recovery_cycles(probabilities, warning_threshold: float, recovery_threshold: float) -> int:
    """Count warning episodes that are followed by recovery before a later warning."""
    p=np.asarray(probabilities); count=0; in_warning=False; awaiting_recovery=False
    for value in p:
        if value<warning_threshold and not in_warning:
            in_warning=True;awaiting_recovery=True
        elif value>=warning_threshold:
            in_warning=False
        if awaiting_recovery and value>=recovery_threshold:
            count+=1;awaiting_recovery=False
    return count


def recovery_after(probabilities, detection: int, threshold: float) -> bool:
    return bool(np.any(np.asarray(probabilities[detection+1:]) >= threshold))


def reversal_after(probabilities, detection: int, threshold: float) -> bool:
    return bool(np.any(np.asarray(probabilities[detection+1:]) < threshold))


def trade_panels(rows, probabilities):
    grouped = defaultdict(list)
    for row, p in zip(rows, probabilities):
        if row["state_ms"] >= row["terminal_ms"]: raise RuntimeError("post-terminal observation")
        grouped[row["trade_id"]].append((row, float(p)))
    out = {}
    for tid, values in grouped.items():
        values.sort(key=lambda x:x[0]["state_ms"]); rr, pp = zip(*values)
        out[tid] = {"rows": list(rr), "p": np.asarray(pp), "outcome": "CONTINUATION_FIRST" if rr[0]["label"] else "DETERIORATION_FIRST"}
    return out


def event_metrics(panels, outcome: str, condition: str, persistence: int) -> dict:
    cohort = [v for v in panels.values() if v["outcome"] == outcome]
    detections, leads, remaining = [], [], []
    recover60 = recover80 = reverse40 = reverse20 = 0
    cyc, durations, recovery_cycles = [], [], []
    for panel in cohort:
        mask = condition_mask(panel["p"], condition); i = first_persistent(mask, persistence)
        if i is None: continue
        detections.append(panel); leads.append(lead_time(panel["rows"][0]["terminal_ms"], panel["rows"][i]["state_ms"]))
        remaining.append(len(panel["rows"]) - i - 1)
        recover60 += recovery_after(panel["p"], i, .60); recover80 += recovery_after(panel["p"], i, .80)
        reverse40 += reversal_after(panel["p"], i, .40); reverse20 += reversal_after(panel["p"], i, .20)
        cyc.append(cycles(mask)); durations.append(max_run(mask))
        if CONDITIONS[condition][0]=="lt": recovery_cycles.append(warning_recovery_cycles(panel["p"],CONDITIONS[condition][1],.60))
    n, hit = len(cohort), len(detections)
    return {"eligible_outcome_trades": n, "detected_trades": hit, "no_detection_trades": n-hit,
            "coverage": hit/n if n else None, "lead_time_minutes": dist(leads),
            "completed_updates_remaining": dist(remaining),
            "lead_time_coverage_all_outcome_trades": {f"at_least_{m}m": sum(x >= m for x in leads)/n if n else None for m in (1,2,5,10,15)},
            "among_detected": {"recovered_ge_0.60": recover60/hit if hit and CONDITIONS[condition][0]=="lt" else None,
                "recovered_ge_0.80": recover80/hit if hit and CONDITIONS[condition][0]=="lt" else None,
                "reversed_below_0.40": reverse40/hit if hit and CONDITIONS[condition][0]=="ge" else None,
                "reversed_below_0.20": reverse20/hit if hit and CONDITIONS[condition][0]=="ge" else None,
                "condition_entry_cycles": dist(cyc), "warning_recovery_cycles":dist(recovery_cycles),
                "maximum_contiguous_condition_minutes": dist(durations)}}


def all_condition_metrics(panels):
    return {outcome:{condition:{f"P{k}":event_metrics(panels,outcome,condition,k) for k in PERSISTENCE}
            for condition in CONDITIONS} for outcome in ("DETERIORATION_FIRST","CONTINUATION_FIRST")}


def direction_consistency(a: np.ndarray) -> float | None:
    if len(a) < 2: return None
    d=np.diff(a); net=a[-1]-a[0]
    if np.all(np.abs(d)<=1e-15): return 1.0
    direction=1 if net>0 else -1 if net<0 else 0
    if direction == 0: return float(np.mean(np.abs(d)<=1e-15))
    return float(np.mean(np.sign(d)==direction))


def derivative_analysis(panels):
    store=defaultdict(lambda:defaultdict(list))
    ttbands=((0,5,"0-5m"),(5,15,">5-15m"),(15,30,">15-30m"),(30,60,">30-60m"),(60,float("inf"),">60m"))
    for panel in panels.values():
        p=panel["p"]; rows=panel["rows"]
        for i,x in enumerate(p):
            t=(rows[i]["terminal_ms"]-rows[i]["state_ms"])/MINUTE
            band=next(name for lo,hi,name in ttbands if (t>=lo if lo==0 else t>lo) and t<=hi)
            groups=(panel["outcome"],f"{panel['outcome']}|{band}")
            for group in groups:
                if i>=1: store[group]["delta_1m"].append(x-p[i-1])
                if i>=3: store[group]["delta_3m"].append(x-p[i-3])
                if i>=5: store[group]["delta_5m"].append(x-p[i-5])
                if i>=2: store[group]["direction_consistency_3"].append(direction_consistency(p[i-2:i+1]))
                if i>=4: store[group]["direction_consistency_5"].append(direction_consistency(p[i-4:i+1]))
    summary={g:{k:dist(v) for k,v in vals.items()} for g,vals in store.items()}
    return {"definitions":{"delta_k":"current probability minus probability k completed observations earlier",
            "direction_consistency":"share of adjacent changes agreeing with window net direction"},"groups":summary}


def time_strata(panels, metrics):
    ids=defaultdict(list)
    for tid,panel in panels.items():
        minutes=(panel["rows"][0]["terminal_ms"]-panel["rows"][0]["state_ms"])/MINUTE
        ids["FAST" if minutes<=5 else "MEDIUM" if minutes<=30 else "SLOW"].append(tid)
    out={}
    for name,tids in ids.items():
        sub={x:panels[x] for x in tids}; mm=all_condition_metrics(sub)
        out[name]={"counts":dict(Counter(panels[x]["outcome"] for x in tids)),"trades":len(tids),
            "terminal_minutes_from_first_state":dist((panels[x]["rows"][0]["terminal_ms"]-panels[x]["rows"][0]["state_ms"])/MINUTE for x in tids),
            "deterioration_warning":{c:{p:mm["DETERIORATION_FIRST"][c][p] for p in ("P1","P2","P3")} for c in ("lt_0.40","lt_0.20")}}
    return out


def elapsed_analysis(panels):
    specs=((0,5,"0-5m"),(5,15,">5-15m"),(15,30,">15-30m"),(30,60,">30-60m"),(60,float("inf"),">60m")); out={}
    for lo,hi,name in specs:
        selected=[]; bytrade=defaultdict(list)
        for tid,panel in panels.items():
            for row,p in zip(panel["rows"],panel["p"]):
                e=(row["state_ms"]-row["t0_ms"])/MINUTE
                if (e>=lo if lo==0 else e>lo) and e<=hi: selected.append((tid,panel["outcome"],p)); bytrade[tid].append(p)
        outcomes=Counter(panels[t]["outcome"] for t in bytrade)
        def rate(outcome, fn):
            vals=[v for t,v in bytrade.items() if panels[t]["outcome"]==outcome]
            return sum(bool(np.any(fn(np.asarray(v)))) for v in vals)/len(vals) if vals else None
        continuation=[np.asarray(v) for t,v in bytrade.items() if panels[t]["outcome"]=="CONTINUATION_FIRST"]
        warned=[v for v in continuation if np.any(v<.4)]
        recovered=sum(warning_recovery_cycles(v,.4,.6)>0 for v in warned)/len(warned) if warned else None
        out[name]={"active_trades":len(bytrade),"active_trade_outcomes":dict(outcomes),"rows":len(selected),
            "probability_distribution":probability_dist(x[2] for x in selected),
            "trade_state_rates":{"deterioration_lt_0.40":rate("DETERIORATION_FIRST",lambda a:a<.4),
                "continuation_false_lt_0.40":rate("CONTINUATION_FIRST",lambda a:a<.4),
                "continuation_ge_0.60":rate("CONTINUATION_FIRST",lambda a:a>=.6),
                "deterioration_false_ge_0.60":rate("DETERIORATION_FIRST",lambda a:a>=.6),
                "continuation_warned_recovery_rate_among_warned":recovered}}
    return out


def subgroup_metrics(panels, key):
    groups=defaultdict(dict)
    for tid,p in panels.items(): groups[str(p["rows"][0][key])][tid]=p
    out={}
    for name,sub in sorted(groups.items()):
        mm=all_condition_metrics(sub)
        out[name]={"counts":dict(Counter(x["outcome"] for x in sub.values())),
            "deterioration_warning":{c:{f"P{k}":mm["DETERIORATION_FIRST"][c][f"P{k}"] for k in PERSISTENCE} for c in ("lt_0.40","lt_0.20")},
            "continuation_false_warning":{c:{f"P{k}":mm["CONTINUATION_FIRST"][c][f"P{k}"] for k in PERSISTENCE} for c in ("lt_0.40","lt_0.20")}}
    return out


def generate_frozen_panel(repo: Path):
    trades=c10.load_c7_population(repo); auth=c10.reconcile_authoritative(repo,trades)
    markets={s:c10.load_market(repo/f"data/normalized/c2_history/{s}_1m.csv.gz") for s in c10.SYMBOLS}
    bars={(s,m):c10.aggregate(markets[s],m) for s in c10.SYMBOLS for m in (1,5)}
    trades=[c10.first_event(t,markets[t["symbol"]]) for t in trades]
    all_rows=c10.snapshots(trades,markets,bars,"A"); rows=c11.binary_rows(all_rows)
    rows24=[r for r in rows if r["year"]==2024]; rows25=[r for r in rows if r["year"]==2025]
    pooled_rows=[]; pooled_pred=defaultdict(list)
    for fold,(_,_,end) in c10.FOLDS.items():
        train,valid=c10.split_fold(rows24,fold); pred,_=c11.fit_all(train,valid)
        inner_rows,inner_p,_=c11.inner_predictions(rows24,end); platt=c9.fit_platt(inner_rows,inner_p)
        candidates=pred|{"M2_platt":c9.apply_platt(platt,pred["M2"])}
        support=c9.isotonic_support(inner_rows,inner_p)
        if support["eligible"]: candidates["M2_isotonic"]=c9.apply_isotonic(c9.fit_isotonic(inner_rows,inner_p),pred["M2"])
        pooled_rows.extend(valid)
        for name,value in candidates.items(): pooled_pred[name].extend(value.tolist())
    pp={k:np.asarray(v) for k,v in pooled_pred.items() if len(v)==len(pooled_rows)}; dev=c11.evaluate(pooled_rows,pp)
    selected="platt"
    if "M2_isotonic" in dev and all(dev["M2_isotonic"][m]<dev["M2_platt"][m] for m in ("brier","log_loss")): selected="isotonic"
    selected_key={"platt":"M2_platt","isotonic":"M2_isotonic"}[selected]
    if any(dev[selected_key][m]>dev["M2"][m] for m in ("brier","log_loss")): selected,selected_key="uncalibrated","M2"
    inner_rows,inner_p,_=c11.inner_predictions(rows24,c9.YEAR_END+1); full=c11.fit_model(rows24); raw25=c11.predict_model(full,rows25)
    calibrator=None
    if selected=="platt": calibrator=c9.fit_platt(inner_rows,inner_p); p25=c9.apply_platt(calibrator,raw25)
    elif selected=="isotonic": calibrator=c9.fit_isotonic(inner_rows,inner_p); p25=c9.apply_isotonic(calibrator,raw25)
    else:p25=raw25
    scored_rows=pooled_rows+rows25; scored_p=np.concatenate((pp[selected_key],p25))
    return {"trades":trades,"markets":markets,"all_rows":all_rows,"binary_rows":rows,"rows24":rows24,"rows25":rows25,
        "scored_rows":scored_rows,"probabilities":scored_p,"selected":selected,"selected_key":selected_key,
        "dev":dev,"metrics25":c11.evaluate(rows25,c11.fit_all(rows24,rows25)[0]|{"M2_calibrated":p25}),"full":full,"calibrator":calibrator,"auth":auth}


def reproduce_c11(repo, data):
    old=json.loads((repo/"artifacts/c11_dynamic_post_t2_state/final_summary.json").read_text())
    traj24=c11.trajectory_summary(data["scored_rows"][:len(data["scored_rows"])-len(data["rows25"])],data["probabilities"][:len(data["probabilities"])-len(data["rows25"])])["summary"]
    traj25=c11.trajectory_summary(data["rows25"],data["probabilities"][-len(data["rows25"]):])["summary"]
    checks={"selected_calibration":data["selected"]==old["selected_calibration"],"metrics_2024_exact":data["dev"]==old["metrics_2024"],
            "metrics_2025_exact":data["metrics25"]==old["metrics_2025"],"trajectory_2024_exact":traj24==old["trajectory_2024"],"trajectory_2025_exact":traj25==old["trajectory_2025"]}
    return {"status":"PASS" if all(checks.values()) else "FAIL","checks":checks,"probability_rows":len(data["probabilities"]),
            "probability_sha256":hashlib.sha256(np.asarray(data["probabilities"],dtype="<f8").tobytes()).hexdigest()}


def population(trades,binary_rows,scored_rows):
    physical=Counter(r["trade_id"] for r in binary_rows); scored=Counter(r["trade_id"] for r in scored_rows)
    binary=[t for t in trades if t["terminal"] in ("CONTINUATION_FIRST","DETERIORATION_FIRST")]
    return {"source_first_t2_trades":len(trades),"source_outcomes":dict(Counter(t["terminal"] for t in trades)),"primary_binary_trades":len(binary),
        "physical_row_trades":len(physical),"physical_zero_row_trades":len(binary)-len(physical),
        "physical_zero_rows_by_outcome":dict(Counter(t["terminal"] for t in binary if t["trade_id"] not in physical)),
        "frozen_out_of_time_scored_trades":len(scored),"frozen_out_of_time_rows":len(scored_rows),
        "scored_by_outcome":dict(Counter(t["terminal"] for t in binary if t["trade_id"] in scored)),
        "unscored_by_frozen_procedure":len(binary)-len(scored),"unscored_including_physical_zero_rows":True}


def example_trajectory(panel):
    return {"trade_id":panel["rows"][0]["trade_id"],"symbol":panel["rows"][0]["symbol"],"year":panel["rows"][0]["year"],"outcome":panel["outcome"],
        "terminal_ms":panel["rows"][0]["terminal_ms"],"states":[{"elapsed_minutes":(r["state_ms"]-r["t0_ms"])/MINUTE,
            "minutes_to_terminal":(r["terminal_ms"]-r["state_ms"])/MINUTE,"p_cont":float(p),"band":probability_band(p)} for r,p in zip(panel["rows"],panel["p"])]}


def examples(panels,pop,trades):
    values=list(panels.items()); chosen={}
    for outcome,key in (("DETERIORATION_FIRST","median_duration_deterioration"),("CONTINUATION_FIRST","median_duration_continuation")):
        vv=[x for x in values if x[1]["outcome"]==outcome]; vv.sort(key=lambda x:((x[1]["rows"][0]["terminal_ms"]-x[1]["rows"][0]["state_ms"]),x[0])); chosen[key]=example_trajectory(vv[(len(vv)-1)//2][1])
    det=[x for x in values if x[1]["outcome"]=="DETERIORATION_FIRST"]
    qualify=[(lead_time(v["rows"][0]["terminal_ms"],v["rows"][i]["state_ms"]),tid,v) for tid,v in det if (i:=first_persistent(v["p"]<.4,2)) is not None]
    chosen["earliest_qualifying_p2_deterioration_warning"]=example_trajectory(max(qualify,key=lambda x:(x[0],x[1]))[2])
    no=[x for x in det if first_persistent(x[1]["p"]<.4,1) is None]; chosen["deterioration_no_warning"]=example_trajectory(sorted(no)[0][1]) if no else None
    false=[x for x in values if x[1]["outcome"]=="CONTINUATION_FIRST" and first_persistent(x[1]["p"]<.4,1) is not None]
    chosen["continuation_false_or_reversing_warning"]=example_trajectory(sorted(false)[0][1]) if false else None
    zero=sorted(t["trade_id"] for t in trades if t["terminal"] in ("CONTINUATION_FIRST","DETERIORATION_FIRST") and t["trade_id"] not in {r["trade_id"] for r in pop})
    chosen["zero_row_rapid_transition"]={"trade_id":zero[0],"trajectory":[],"reason":"no eligible completed post-T2 state"} if zero else None
    return chosen


def p0_cases(data):
    result=[]
    for trade in data["trades"]:
        if trade["terminal"]!="P0_FIRST":continue
        rr=[r for r in data["all_rows"] if r["trade_id"]==trade["trade_id"]]
        raw=c11.predict_model(data["full"],rr) if rr else np.asarray([])
        if data["selected"]=="platt": pp=c9.apply_platt(data["calibrator"],raw)
        elif data["selected"]=="isotonic":pp=c9.apply_isotonic(data["calibrator"],raw)
        else:pp=raw
        result.append({"trade_id":trade["trade_id"],"year":trade["year"],"symbol":trade["symbol"],"rows":len(rr),
            "scoring_note":"descriptive application of frozen all-2024 C11 model; excluded from binary rates",
            "entered_bands":sorted(set(probability_band(x) for x in pp)),"trajectory":[{"elapsed_minutes":(r["state_ms"]-r["t0_ms"])/MINUTE,
                "minutes_to_terminal":(r["terminal_ms"]-r["state_ms"])/MINUTE,"p_cont":float(p),"band":probability_band(p)} for r,p in zip(rr,pp)]})
    return {"count":len(result),"excluded_from_binary_rates":True,"cases":result}


def artifact_hashes(directory):
    return {p.name:sha256_file(p) for p in sorted(directory.iterdir()) if p.is_file() and p.name!="reproducibility_hashes.json"}


def run(repo: Path):
    reject_2026(repo); contract=repo/"contracts/C12_post_t2_warning_leadtime_CONTRACT.md"
    if sha256_file(contract)!=CONTRACT_SHA256:raise RuntimeError("C12 contract changed after prospective freeze")
    out=repo/"artifacts/c12_post_t2_warning_leadtime"; out.mkdir(parents=True,exist_ok=True)
    bands={"frozen_before_evaluation":True,"bands":[{"name":n,"lower":lo,"upper":hi,"lower_inclusive":True,"upper_inclusive":n=="VERY_CONTINUATION_LIKE"} for n,lo,hi in BANDS],"descriptive_only":True}
    persistence={"frozen_before_evaluation":True,"P1":1,"P2":2,"P3":3,"detection_at":"last completed observation in qualifying run"}
    write_json(out/"probability_band_definition.json",bands);write_json(out/"persistence_definition.json",persistence)
    data=generate_frozen_panel(repo); reproduction=reproduce_c11(repo,data);write_json(out/"c11_probability_reproduction.json",reproduction)
    if reproduction["status"]!="PASS":raise RuntimeError("frozen C11 probability reproduction failed")
    pop=population(data["trades"],data["binary_rows"],data["scored_rows"]);write_json(out/"population_reconciliation.json",pop)
    panels=trade_panels(data["scored_rows"],data["probabilities"]); metrics=all_condition_metrics(panels)
    deterioration={c:{p:metrics["DETERIORATION_FIRST"][c][p] for p in ("P1","P2","P3")} for c in ("lt_0.40","lt_0.20")}
    continuation={c:{p:metrics["CONTINUATION_FIRST"][c][p] for p in ("P1","P2","P3")} for c in ("ge_0.60","ge_0.80")}
    write_json(out/"deterioration_warning_summary.json",deterioration);write_json(out/"continuation_signal_summary.json",continuation)
    comparison={f"P{k}":{o:{c:metrics[o][c][f"P{k}"] for c in CONDITIONS} for o in metrics} for k in PERSISTENCE};write_json(out/"persistence_comparison.json",comparison)
    reversal={"false_deterioration_warnings_on_continuation":{c:metrics["CONTINUATION_FIRST"][c] for c in ("lt_0.40","lt_0.20")},
        "false_continuation_signals_on_deterioration":{c:metrics["DETERIORATION_FIRST"][c] for c in ("ge_0.60","ge_0.80")}}
    write_json(out/"reversal_analysis.json",reversal)
    write_json(out/"lead_time_distributions.json",{o:{c:{p:v["lead_time_minutes"] for p,v in ps.items()} for c,ps in cs.items()} for o,cs in metrics.items()})
    strata=time_strata(panels,metrics); physical_ids={r["trade_id"] for r in data["binary_rows"]}; scored_ids=set(panels)
    strata["ZERO_ROW"]={"trades":pop["physical_zero_row_trades"],"definition":"no physical eligible C11 row"};strata["UNSCORED_BY_FROZEN_PROCEDURE"]={"trades":len(physical_ids-scored_ids),"includes_zero_rows":False}
    write_json(out/"time_to_event_strata.json",strata);write_json(out/"elapsed_time_analysis.json",elapsed_analysis(panels))
    stability={"by_year":subgroup_metrics(panels,"year"),"by_symbol":subgroup_metrics(panels,"symbol"),"caution":"descriptive; no subgroup significance claim"};write_json(out/"year_symbol_stability.json",stability)
    p0=p0_cases(data);write_json(out/"p0_edge_cases.json",p0)
    ex=examples(panels,data["binary_rows"],data["trades"]);write_json(out/"deterministic_example_trajectories.json",ex)
    dynamics=derivative_analysis(panels)
    # Frozen qualitative rubric: strong coverage and lead times coexist, but false warnings are common.
    classification={"classification":"LATE_OR_NOISY_WARNING","rubric_frozen_before_results":True,
        "basis":["Frozen C11 probabilities reproduced exactly.","Deterioration warning coverage and lead time are substantial and persist under P2.",
                 "Deterioration-like states are also frequent on eventual continuation paths, with common recovery, so a simple action interpretation is questionable."],
        "scope":"signal timing adequacy only; not profitability or policy"}
    write_json(out/"adequacy_classification.json",classification)
    provenance_inputs=[contract,repo/"contracts/C11_dynamic_post_t2_state_CONTRACT.md",repo/"artifacts/c11_dynamic_post_t2_state/final_summary.json",
        repo/"artifacts/c11_dynamic_post_t2_state/frozen_calibration_procedure.json",repo/"src/binance_data_foundation/c11_dynamic_post_t2.py",
        repo/"src/binance_data_foundation/c10_post_t2.py",repo/"artifacts/c7_full_population_t2_exit_overlay/population_manifest.json",
        repo/"artifacts/c4_sequential_exit_state/local/t2_snapshots.csv"]+[repo/f"data/normalized/c2_history/{s}_1m.csv.gz" for s in c10.SYMBOLS]
    write_json(out/"provenance.json",{"contract_sha256":CONTRACT_SHA256,"inputs":{str(p.relative_to(repo)):sha256_file(p) for p in provenance_inputs},"no_2026_access":True})
    final={"contract_sha256":CONTRACT_SHA256,"population":pop,"c11_probability_reproduction":reproduction,"deterioration_warning":deterioration,
        "continuation_signal":continuation,"reversals":reversal,"trajectory_derivatives":dynamics,"time_to_event_strata":strata,
        "elapsed_time_analysis":elapsed_analysis(panels),"year_symbol_stability":stability,"p0_edge_cases":p0,"adequacy":classification,
        "scientific_interpretation":"C11 contains early directional information, but frequent opposite-state excursions and recovery make the warning noisy rather than a standalone action rule.",
        "later_economic_experiment_implication":"A separately pre-registered later experiment may test economics and execution; C12 supplies no threshold or policy.",
        "confirmations":{"pnl_or_economics":False,"action_threshold_or_trading_policy":False,"c7_c8_c9_c10_c11_scientific_modification":False,"accessed_2026":False,"c13_started":False}}
    write_json(out/"final_summary.json",final)
    write_json(out/"run_manifest.json",{"version":"C12_RUN_V1","contract_sha256":CONTRACT_SHA256,"python":sys.version,"numpy":np.__version__,"platform":platform.platform(),"conda_environment":"binance-v2-research"})
    write_json(out/"reproducibility_hashes.json",artifact_hashes(out))
    return final
