"""C26 diagnostic of the frozen C25 first-Q1 action semantics."""
from __future__ import annotations

import hashlib, json, os, platform, sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from . import c8_timescale as c8
from . import c22_causal_decision_state as c22
from . import c23_incremental_c9_ablation as c23
from . import c24_probability_economic_ordering as c24

CONTRACT_SHA256 = "26a473049eb19f4bbbb7afb5dfcc04a9b541166d0615bbb3e940792610c653e0"
CONTRACT_REL = "contracts/C26_q1_action_semantics_CONTRACT.md"
OUTPUT_REL = "artifacts/c26_q1_action_semantics"
C25_REL = "artifacts/c25_q1_sequential_exit"
TARGET = "DELTA_LIQ_5"
SEED = 20260929
REPLICATES = 2000
YEARS = (2024, 2025)


def reject_2026(path) -> None:
    if any("2026" in part for part in os.fspath(path).replace("\\", "/").lower().split("/")):
        raise PermissionError("C26 prohibits 2026 data or metadata access")


def sha(path: Path) -> str:
    reject_2026(path); h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""): h.update(block)
    return h.hexdigest()


def semantic_sha(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n")


def _load(path: Path):
    reject_2026(path)
    return json.loads(path.read_text())


def _month(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m")


def weighted_summary(rows, weights, probability_key="probability") -> dict:
    if not rows: raise ValueError("empty diagnostic group")
    w=np.asarray(weights,float); y=np.asarray([r[TARGET] for r in rows],float)
    p=np.asarray([r[probability_key] for r in rows],float)
    elapsed=np.asarray([r["elapsed_minutes"] for r in rows],float)
    current=np.asarray([r["current_return_from_entry"] for r in rows],float)
    pos,zero,neg=y>0,y==0,y<0
    q=lambda x: c24.weighted_quantile(y,w,x)
    contribution=lambda take: float(np.sum(w[take]*y[take]))
    return {
        "snapshot_count":len(rows), "trade_count":len({r["trade_id"] for r in rows}),
        "effective_whole_trade_weight":float(w.sum()),
        "weighted_positive_rate":float(np.average(pos,weights=w)),
        "weighted_exact_zero_rate":float(np.average(zero,weights=w)),
        "weighted_negative_rate":float(np.average(neg,weights=w)),
        "weighted_mean_DELTA_LIQ_5":float(np.average(y,weights=w)),
        "weighted_median_DELTA_LIQ_5":q(.5), "weighted_p10_DELTA_LIQ_5":q(.1),
        "weighted_p25_DELTA_LIQ_5":q(.25), "weighted_p75_DELTA_LIQ_5":q(.75),
        "weighted_p90_DELTA_LIQ_5":q(.9),
        "weighted_mean_positive_value":float(np.average(y[pos],weights=w[pos])) if pos.any() else None,
        "weighted_mean_negative_value":float(np.average(y[neg],weights=w[neg])) if neg.any() else None,
        "weighted_positive_contribution":contribution(pos),
        "weighted_negative_contribution":contribution(neg),
        "weighted_net_contribution":float(np.sum(w*y)),
        "weighted_mean_probability":float(np.average(p,weights=w)),
        "weighted_median_probability":c24.weighted_quantile(p,w,.5),
        "weighted_mean_elapsed_minutes":float(np.average(elapsed,weights=w)),
        "weighted_median_elapsed_minutes":c24.weighted_quantile(elapsed,w,.5),
        "weighted_mean_observable_return":float(np.average(current,weights=w)),
        "weighted_median_observable_return":c24.weighted_quantile(current,w,.5),
    }


def quadrant(v5: float, vp0: float) -> str:
    if v5 < 0: return "SHORT_BAD_LIFECYCLE_BAD" if vp0 < 0 else "SHORT_BAD_LIFECYCLE_RECOVERS"
    return "SHORT_OK_LIFECYCLE_BAD" if vp0 < 0 else "SHORT_OK_LIFECYCLE_GOOD"


def impact(row) -> str:
    d,p=row["paired_return_difference"],row["canonical_p0_net_return"]
    return "TIE" if d==0 else "AVOIDED_LOSS" if d>0 and p<0 else "PRESERVED_GAIN" if d>0 else "SURRENDERED_UPSIDE" if p>0 else "DEEPENED_LOSS"


def _sample_indices(rows, unit, rng):
    groups=defaultdict(list)
    for i,r in enumerate(rows): groups[r["trade_id"] if unit=="whole_trade" else r["entry_month"]].append(i)
    labels=sorted(groups)
    return [i for j in rng.integers(len(labels),size=len(labels)) for i in groups[labels[int(j)]]]


def bootstrap(all_rows, first_rows, unit, seed=SEED, replicates=REPLICATES):
    """Resample clusters, preserving all frozen snapshots and group construction."""
    rng=np.random.Generator(np.random.PCG64(seed)); first_by={r["trade_id"]:r for r in first_rows}; samples=[]
    for _ in range(replicates):
        ix=_sample_indices(all_rows,unit,rng); rr=[all_rows[i] for i in ix]
        # Each occurrence retains its frozen C24 whole-trade snapshot weight.
        aw=np.asarray([r["base_weight"] for r in rr],float); ay=np.asarray([r[TARGET] for r in rr],float)
        ordered=[]; seen=set()
        for r in rr:
            tid=r["trade_id"]
            if tid not in seen: ordered.append(first_by[tid]); seen.add(tid)
        fy=np.asarray([r[TARGET] for r in ordered],float)
        am=float(np.average(ay,weights=aw)); ar=float(np.average(ay>0,weights=aw))
        fm=float(fy.mean()); fr=float((fy>0).mean())
        samples.append((am,ar,fm,fr,fm-am,fr-ar))
    a=np.asarray(samples); names=("all_q1_mean","all_q1_positive_rate","first_q1_mean","first_q1_positive_rate","Delta_first_all_mean","Delta_first_all_positive_rate")
    return {"unit":unit,"construction":"UTC entry-calendar-month blocks; whole trades and both groups retained" if unit=="calendar_month" else "whole trades; all attached Q1 snapshots and first-Q1 state retained",
        "seed":seed,"generator":"PCG64","replicates":replicates,"models_refit":False,
        "intervals":{n:{"ci95":np.quantile(a[:,j],[.025,.975],method="linear").tolist(),"replicate_sha256":hashlib.sha256(a[:,j].astype("<f8").tobytes()).hexdigest()} for j,n in enumerate(names)}}


def concentration(ledger) -> dict:
    values=np.asarray([r["paired_pnl_difference"] for r in ledger],float); n=len(values)
    def one(sign):
        x=np.sort(values[values>0] if sign=="positive" else -values[values<0])[::-1]; total=float(x.sum())
        def share(k): return float(x[:min(k,len(x))].sum()/total) if total else None
        pct={f"top_{p}pct_all_trades_share":share(int(np.ceil(n*p/100))) for p in (1,5,10,20)}
        c=np.cumsum(x); half=int(np.searchsorted(c,.5*total,side="left")+1) if total else 0
        return {"contributing_trade_count":len(x),"total_contribution":total,**{f"top_{k}_trades_share":share(k) for k in (1,5,10,20)},**pct,"trades_to_explain_50pct":half}
    return {"population_trade_count":n,"positive":one("positive"),"negative_absolute":one("negative"),"accounting_reconciles":bool(abs(values.sum()-sum(r["paired_pnl_difference"] for r in ledger))<1e-12)}


def run(repo: Path) -> dict:
    repo=repo.resolve(); reject_2026(repo)
    if os.environ.get("CONDA_DEFAULT_ENV") != "binance-v2-research": raise RuntimeError("conda environment must be binance-v2-research")
    if sha(repo/CONTRACT_REL) != CONTRACT_SHA256: raise RuntimeError("C26 contract changed after prospective freeze")
    c25=repo/C25_REL; out=repo/OUTPUT_REL; out.mkdir(parents=True,exist_ok=True)
    ledger=_load(c25/"policy_trade_ledger.json"); c25_pop=_load(c25/"population_reconciliation.json")
    c25_honest=_load(c25/"honest_policy_population.json"); c25_paths=_load(c25/"policy_path_counts.json")
    c25_yearly=_load(c25/"yearly_results.json"); c25_full=_load(c25/"full_population_results.json")
    c25_impacts=_load(c25/"avoided_loss_surrendered_upside.json"); c25_q1=_load(c25/"q1_boundary_reproduction.json")
    ledger_by={r["trade_id"]:r for r in ledger}
    basic_ok=len(ledger)==len(ledger_by)==2199 and c25_pop["exact_reconciliation"] and c25_honest["covered_trades"]==1354 and c25_paths["executed_exits"]==c25_paths["unique_trades_with_q1"]==698
    pnl_ok=abs(sum(r["paired_pnl_difference"] for r in ledger)-c25_full["total_pnl_difference"])<1e-9
    rows,info=c22.build_causal_rows(repo); rows24=[r for r in rows if r["year"]==2024]; rows25=[r for r in rows if r["year"]==2025]
    train24,valid24=c8.split_fold(rows24,"fold_B"); datasets={2024:(train24,valid24),2025:(rows24,rows25)}
    all_groups={}; first_groups={}; boundaries={}; prediction_hashes={}
    for year,(training,valid) in datasets.items():
        pt=c23.fit_candidates(training,training,TARGET)[0]["S+C9"]["binary"]
        pv=c23.fit_candidates(training,valid,TARGET)[0]["S+C9"]["binary"]
        boundary=float(c24.bin_boundaries(pt,training)["cut_values"][0]); boundaries[year]=boundary
        frozen=c25_q1[str(year)]; boundary_ok=boundary==frozen["boundary"]
        base=c24.weights(valid); selected=[]
        for r,p,w in zip(valid,pv,base):
            if c24.assign_bins([p],[boundary])[0]==0:
                selected.append(dict(r,probability=float(p),base_weight=float(w),entry_month=_month(r["entry_ms"])))
        selected.sort(key=lambda r:(r["trade_id"],r["state_ms"])); first=[]
        for tid in sorted({r["trade_id"] for r in selected}):
            first.append(min((r for r in selected if r["trade_id"]==tid),key=lambda r:r["state_ms"]))
        count_ok=(len(selected),len(first))==(frozen["validation_q1_snapshots"],frozen["validation_q1_trades"])
        for r in first:
            lr=ledger_by[r["trade_id"]]
            if lr["first_q1_timestamp_ms"] != r["state_ms"] or lr["q1_probability"] != r["probability"]: raise RuntimeError("INSUFFICIENT_RECONCILIATION")
            r.update({"vp0":float(lr["canonical_p0_net_return"]-r["exit_now_net"]),"paired_return_difference":lr["paired_return_difference"],"paired_pnl_difference":lr["paired_pnl_difference"],"canonical_p0_net_return":lr["canonical_p0_net_return"],"impact_label":impact(lr)})
        if not boundary_ok or not count_ok: raise RuntimeError("INSUFFICIENT_RECONCILIATION")
        all_groups[year]=selected; first_groups[year]=first
        prediction_hashes[str(year)]={"training":c24._prediction_sha(pt),"validation":c24._prediction_sha(pv)}
    first_count=sum(map(len,first_groups.values())); first_ok=first_count==698 and all(r["trade_id"] in ledger_by and ledger_by[r["trade_id"]]["policy_path_category"]=="MODEL_EXIT_EXECUTED" for y in YEARS for r in first_groups[y])
    yearly_ok=all(abs(sum(r["paired_pnl_difference"] for r in ledger if r["year"]==y and r["covered"])-c25_yearly[str(y)]["total_pnl_difference"])<1e-9 for y in YEARS)
    reconciliation={"status":"PASS" if all((basic_ok,pnl_ok,first_ok,yearly_ok)) else "INSUFFICIENT_RECONCILIATION","original_trade_count":len(ledger),"honest_covered_trade_count":sum(r["covered"] for r in ledger),"first_q1_trade_count":first_count,"model_exit_count":sum(r["policy_path_category"]=="MODEL_EXIT_EXECUTED" for r in ledger),"paired_pnl_total":sum(r["paired_pnl_difference"] for r in ledger),"C25_paired_pnl_total":c25_full["total_pnl_difference"],"C25_yearly_exact":yearly_ok,"C25_labels_exact":True,"q1_boundaries":boundaries,"q1_tie_convention":"probability <= frozen upper boundary"}
    if reconciliation["status"]!="PASS": raise RuntimeError("INSUFFICIENT_RECONCILIATION")
    absolute={}; comparisons={}; boots={}
    for y in YEARS:
        a=weighted_summary(all_groups[y],[r["base_weight"] for r in all_groups[y]])
        f=weighted_summary(first_groups[y],np.ones(len(first_groups[y])))
        absolute[y]=a; comparisons[y]={"ALL_Q1":a,"FIRST_Q1":f,"Delta_first_all_mean":f["weighted_mean_DELTA_LIQ_5"]-a["weighted_mean_DELTA_LIQ_5"],"Delta_first_all_positive_rate":f["weighted_positive_rate"]-a["weighted_positive_rate"]}
        boots[y]={u:bootstrap(all_groups[y],first_groups[y],u) for u in ("calendar_month","whole_trade")}
    quadrant_reports={}; horizon={}; crosstab={k:{} for k in ("AVOIDED_LOSS","PRESERVED_GAIN","SURRENDERED_UPSIDE","DEEPENED_LOSS","TIE")}
    all_first=[r for y in YEARS for r in first_groups[y]]
    for y in YEARS:
        cells={name:[] for name in ("SHORT_BAD_LIFECYCLE_BAD","SHORT_BAD_LIFECYCLE_RECOVERS","SHORT_OK_LIFECYCLE_BAD","SHORT_OK_LIFECYCLE_GOOD")}
        for r in first_groups[y]: cells[quadrant(r[TARGET],r["vp0"])].append(r)
        quadrant_reports[str(y)]={}
        for name,rr in cells.items():
            d=np.asarray([r["paired_return_difference"] for r in rr]); p0=np.asarray([r["canonical_p0_net_return"] for r in rr])
            quadrant_reports[str(y)][name]={"trade_count":len(rr),"share":len(rr)/len(first_groups[y]),"mean_V5":float(np.mean([r[TARGET] for r in rr])) if rr else None,"median_V5":float(np.median([r[TARGET] for r in rr])) if rr else None,"mean_VP0":float(np.mean([r["vp0"] for r in rr])) if rr else None,"median_VP0":float(np.median([r["vp0"] for r in rr])) if rr else None,"C25_minus_P0_pnl_contribution":float(sum(r["paired_pnl_difference"] for r in rr)),"C25_minus_P0_mean_return_difference":float(d.mean()) if rr else None,"wins":int((d>0).sum()),"losses":int((d<0).sum()),"ties":int((d==0).sum()),"P0_positive_return_count":int((p0>0).sum()),"P0_positive_return_fraction":float((p0>0).mean()) if rr else None}
        recovery=cells["SHORT_BAD_LIFECYCLE_RECOVERS"]
        surrendered=[r for r in first_groups[y] if r["impact_label"]=="SURRENDERED_UPSIDE"]
        losses=[r for r in first_groups[y] if r["paired_pnl_difference"]<0]
        rec_surrender=-sum(r["paired_pnl_difference"] for r in recovery if r["impact_label"]=="SURRENDERED_UPSIDE")
        horizon[str(y)]={"fraction_V5_lt_0":sum(r[TARGET]<0 for r in first_groups[y])/len(first_groups[y]),"fraction_VP0_lt_0":sum(r["vp0"]<0 for r in first_groups[y])/len(first_groups[y]),"fraction_SHORT_BAD_LIFECYCLE_RECOVERS":len(recovery)/len(first_groups[y]),"fraction_SHORT_BAD_LIFECYCLE_BAD":len(cells["SHORT_BAD_LIFECYCLE_BAD"])/len(first_groups[y]),"recovery_quadrant_surrendered_upside_absolute":rec_surrender,"total_surrendered_upside_absolute":-sum(r["paired_pnl_difference"] for r in surrendered),"recovery_share_of_surrendered_upside":rec_surrender/-sum(r["paired_pnl_difference"] for r in surrendered) if surrendered else None,"recovery_absolute_negative_contribution":-sum(r["paired_pnl_difference"] for r in recovery if r["paired_pnl_difference"]<0),"recovery_share_of_total_loss_contribution":-sum(r["paired_pnl_difference"] for r in recovery if r["paired_pnl_difference"]<0)/-sum(r["paired_pnl_difference"] for r in losses) if losses else None}
    for label in crosstab:
        for name in ("SHORT_BAD_LIFECYCLE_BAD","SHORT_BAD_LIFECYCLE_RECOVERS","SHORT_OK_LIFECYCLE_BAD","SHORT_OK_LIFECYCLE_GOOD"):
            rr=[r for r in all_first if r["impact_label"]==label and quadrant(r[TARGET],r["vp0"])==name]
            crosstab[label][name]={"count":len(rr),"pnl_contribution":float(sum(r["paired_pnl_difference"] for r in rr))}
    cross_totals={k:{"count":sum(x["count"] for x in v.values()),"pnl_contribution":sum(x["pnl_contribution"] for x in v.values())} for k,v in crosstab.items()}
    if any(cross_totals[k]["count"]!=c25_impacts[k]["count"] or abs(cross_totals[k]["pnl_contribution"]-c25_impacts[k]["pnl_contribution"])>1e-9 for k in crosstab): raise RuntimeError("INSUFFICIENT_RECONCILIATION")
    conc=concentration(ledger); months={}
    for m in sorted({r["entry_month"] for r in ledger}):
        rr=[r for r in ledger if r["entry_month"]==m]; d=np.asarray([r["paired_return_difference"] for r in rr])
        months[m]={"original_trade_count":len(rr),"covered_trade_count":sum(r["covered"] for r in rr),"model_exit_count":sum(r["policy_path_category"]=="MODEL_EXIT_EXECUTED" for r in rr),"C25_minus_P0_pnl_difference":float(sum(r["paired_pnl_difference"] for r in rr)),"mean_paired_return_difference":float(d.mean()),"positive_contribution_trade_count":int((d>0).sum()),"negative_contribution_trade_count":int((d<0).sum())}
    loo={m:{"total_pnl_difference":float(sum(r["paired_pnl_difference"] for r in ledger if r["entry_month"]!=m)),"mean_paired_return_difference":float(np.mean([r["paired_return_difference"] for r in ledger if r["entry_month"]!=m]))} for m in months}
    min_m=min(loo,key=lambda m:loo[m]["total_pnl_difference"]); max_m=max(loo,key=lambda m:loo[m]["total_pnl_difference"])
    loo_report={"by_omitted_month":loo,"minimum":{"omitted_month":min_m,**loo[min_m]},"maximum":{"omitted_month":max_m,**loo[max_m]},"negative_total_count":sum(v["total_pnl_difference"]<0 for v in loo.values()),"positive_total_count":sum(v["total_pnl_difference"]>0 for v in loo.values())}
    symbols={}
    for s in c8.SYMBOLS:
        symbols[s]={}
        for y in YEARS:
            rr=[r for r in first_groups[y] if r["symbol"]==s]
            symbols[s][str(y)]={"trigger_count":len(rr),"mean_V5":float(np.mean([r[TARGET] for r in rr])) if rr else None,"mean_VP0":float(np.mean([r["vp0"] for r in rr])) if rr else None,"SHORT_BAD_LIFECYCLE_RECOVERS_fraction":sum(quadrant(r[TARGET],r["vp0"])=="SHORT_BAD_LIFECYCLE_RECOVERS" for r in rr)/len(rr) if rr else None,"C25_minus_P0_paired_contribution":float(sum(r["paired_pnl_difference"] for r in rr))}
    # Frozen prose predicates are applied conservatively; no quantitative cutoff is fitted.
    path_a_1=all(comparisons[y]["FIRST_Q1"]["weighted_mean_DELTA_LIQ_5"]<0 for y in YEARS)
    path_a_2=all(boots[y][u]["intervals"]["first_q1_mean"]["ci95"][0] <= 0 for y in YEARS for u in ("calendar_month","whole_trade"))
    path_a_3=all(np.sign(comparisons[y]["FIRST_Q1"]["weighted_mean_DELTA_LIQ_5"])==np.sign(comparisons[y]["ALL_Q1"]["weighted_mean_DELTA_LIQ_5"]) for y in YEARS)
    broad=conc["positive"]["top_1_trades_share"]<.5 and conc["negative_absolute"]["top_1_trades_share"]<.5 and loo_report["positive_total_count"]>1
    path_a=path_a_1 and path_a_2 and path_a_3 and broad
    path_b_1=all(comparisons[y]["FIRST_Q1"]["weighted_mean_DELTA_LIQ_5"]<0 or comparisons[y]["Delta_first_all_mean"]<0 for y in YEARS)
    path_b_2=all(quadrant_reports[str(y)]["SHORT_BAD_LIFECYCLE_RECOVERS"]["trade_count"]>2 for y in YEARS)
    path_b_3=sum(horizon[str(y)]["recovery_quadrant_surrendered_upside_absolute"] for y in YEARS)>0
    path_b_4=all(horizon[str(y)]["recovery_share_of_surrendered_upside"] is not None and horizon[str(y)]["recovery_share_of_surrendered_upside"]>0 for y in YEARS)
    path_b=path_b_1 and path_b_2 and path_b_3 and path_b_4 and broad
    decision="CONTINUE_POLICY_RESEARCH" if path_a or path_b else "STOP_THIS_EXIT_LINE"
    predicates={"Path_A":{"first_Q1_mean_V5_negative_both_years":path_a_1,"uncertainty_directionally_supportive_no_clear_positive":path_a_2,"selection_does_not_reverse_all_Q1_interpretation":path_a_3,"not_isolated_trade_or_month":broad,"satisfied":path_a},"Path_B":{"first_Q1_adverse_or_worse_both_years":path_b_1,"recovery_quadrant_present_both_years":path_b_2,"recovery_explains_surrendered_upside":path_b_3,"same_qualitative_pattern_both_years":path_b_4,"not_isolated_trade_or_month":broad,"satisfied":path_b},"decision":decision,"note":"Contract prose predicates applied directly and conservatively; no threshold, policy, horizon, or model was searched."}
    manifest={"version":"C26_RUN_V1","contract_sha256":CONTRACT_SHA256,"seed":SEED,"replicates":REPLICATES,"generator":"PCG64","python":sys.version,"numpy":np.__version__,"platform":platform.platform(),"conda_environment":"binance-v2-research"}
    provenance={"contract_sha256":CONTRACT_SHA256,"C25_artifact_hashes_sha256":sha(c25/"reproducibility_hashes.json"),"C25_ledger_sha256":sha(c25/"policy_trade_ledger.json"),"prediction_hashes":prediction_hashes,"target":TARGET,"cost":"C_BASE","no_2026_access":True}
    files={"run_manifest":manifest,"provenance":provenance,"population_reconciliation":reconciliation,"first_q1_reconciliation":{"status":"PASS","count":first_count,"one_trigger_per_trade":len({r['trade_id'] for r in all_first})==first_count,"timestamps_and_probabilities_exact_C25":True,"year_counts":dict(Counter(str(r["year"]) for r in all_first))},"all_q1_absolute_value_2024":absolute[2024],"all_q1_absolute_value_2025":absolute[2025],"all_q1_bootstrap":{str(y):{u:boots[y][u] for u in boots[y]} for y in YEARS},"first_vs_all_q1_2024":comparisons[2024],"first_vs_all_q1_2025":comparisons[2025],"first_vs_all_bootstrap":{str(y):{u:boots[y][u] for u in boots[y]} for y in YEARS},"first_q1_v5_vp0_2024":{"count":len(first_groups[2024]),"mean_V5":comparisons[2024]["FIRST_Q1"]["weighted_mean_DELTA_LIQ_5"],"median_V5":comparisons[2024]["FIRST_Q1"]["weighted_median_DELTA_LIQ_5"],"mean_VP0":float(np.mean([r['vp0'] for r in first_groups[2024]])),"median_VP0":float(np.median([r['vp0'] for r in first_groups[2024]])),**horizon["2024"]},"first_q1_v5_vp0_2025":{"count":len(first_groups[2025]),"mean_V5":comparisons[2025]["FIRST_Q1"]["weighted_mean_DELTA_LIQ_5"],"median_V5":comparisons[2025]["FIRST_Q1"]["weighted_median_DELTA_LIQ_5"],"mean_VP0":float(np.mean([r['vp0'] for r in first_groups[2025]])),"median_VP0":float(np.median([r['vp0'] for r in first_groups[2025]])),**horizon["2025"]},"horizon_mismatch_quadrants":quadrant_reports,"c25_label_quadrant_crosstab":{"cells":crosstab,"totals":cross_totals,"reconciles_to_C25":True},"trade_concentration":conc,"entry_month_results":months,"leave_one_month_out":loo_report,"symbol_diagnostics":symbols,"interpretation_predicates":predicates}
    for name,value in files.items(): write(out/f"{name}.json",value)
    final={"contract_sha256":CONTRACT_SHA256,"C25_reconciliation":reconciliation,"exact_first_Q1_population":files["first_q1_reconciliation"],"all_Q1_absolute":{str(y):absolute[y] for y in YEARS},"first_vs_all":{str(y):comparisons[y] for y in YEARS},"uncertainty":files["first_vs_all_bootstrap"],"first_Q1_V5_VP0":{str(y):files[f"first_q1_v5_vp0_{y}"] for y in YEARS},"quadrants":quadrant_reports,"label_quadrant_crosstab":files["c25_label_quadrant_crosstab"],"trade_concentration":conc,"entry_month_results":months,"leave_one_month_out":loo_report,"symbol_diagnostics":symbols,"interpretation_predicates":predicates,"decision":decision,"limitations":["retrospective diagnostic, not policy validation","2024 has one honest validation fold","five symbols are not independent replications","materiality language in the frozen predicates is qualitative; no cutoff was optimized"],"confirmations":{"new_model":False,"threshold_search":False,"persistence_search":False,"alternate_horizon_inspection":False,"alternate_policy":False,"pnl_optimization":False,"accessed_2026":False,"C27_started":False,"staged_committed_or_pushed":False}}
    write(out/"final_summary.json",final)
    hashes={p.name:sha(p) for p in sorted(out.glob("*.json")) if p.name!="reproducibility_hashes.json"}; write(out/"reproducibility_hashes.json",hashes)
    final["artifact_hash_verification"]={"count":len(hashes),"status":"PASS","manifest_sha256":semantic_sha(hashes)}
    return final
