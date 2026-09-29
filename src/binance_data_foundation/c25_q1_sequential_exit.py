"""C25 frozen Q1 sequential full-exit policy experiment."""
from __future__ import annotations

import csv, hashlib, json, math, os, platform, sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from . import c7_t1 as c7
from . import c8_timescale as c8
from . import c20_forward_liquidation_value as c20
from . import c22_causal_decision_state as c22
from . import c23_incremental_c9_ablation as c23
from . import c24_probability_economic_ordering as c24

CONTRACT_SHA256 = "47dde2cd05f5b5ab5bf6a722b2ac4f2847f5459ab30d37de2500b86ca6a1d2c6"
CONTRACT_REL = "contracts/C25_q1_sequential_exit_CONTRACT.md"
OUTPUT_REL = "artifacts/c25_q1_sequential_exit"
TARGET = "DELTA_LIQ_5"
SEED = 20260929
REPLICATES = 2000
COSTS = ("C0", "C_BASE", "C_S5", "C_S10")
EXPECTED_BOUNDARIES = {"2024": 0.48865730936567864, "2025": 0.4818371318862759}
EXPECTED_Q1 = {"2024": (1192, 157), "2025": (4727, 541)}


def reject_2026(path) -> None:
    if any("2026" in p for p in os.fspath(path).replace("\\", "/").lower().split("/")):
        raise PermissionError("C25 prohibits 2026 data or metadata access")


def sha(path: Path) -> str:
    reject_2026(path); h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""): h.update(block)
    return h.hexdigest()


def write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n")


def q1(probability: float, boundary: float) -> bool:
    """C24 left assignment: Q1 includes values exactly equal to its upper cut."""
    return int(np.searchsorted(np.asarray([boundary]), float(probability), side="left")) == 0


def choose_model_exit(states, probabilities, boundary, terminal_ms, p0_ms, open_lookup):
    """Evaluate one irreversible policy, permitting reassessment only after failed fills."""
    failed = []; repeated = 0
    for row, probability in sorted(zip(states, probabilities), key=lambda x: int(x[0]["state_ms"])):
        t = int(row["state_ms"])
        if t >= terminal_ms:
            return None, failed, "REACHED_T2_BEFORE_MODEL_EXIT" if terminal_ms < p0_ms else "ELIGIBLE_NEVER_Q1", repeated
        if not q1(float(probability), boundary):
            repeated += 1; continue
        candidate = t  # open at t begins the minute strictly after the completed bar ending at t
        decision = {"decision_ms": t, "probability": float(probability), "candidate_ms": candidate}
        if terminal_ms <= candidate or p0_ms <= candidate:
            decision["precedence"] = "T2" if terminal_ms < p0_ms else "P0"
            return decision, failed, "Q1_SIGNAL_TERMINAL_PRECEDENCE", repeated
        price, reason = open_lookup(candidate)
        if reason:
            failed.append(decision | {"status": reason}); repeated += 1; continue
        return decision | {"actual_ms": candidate, "price": float(price), "precedence": "MODEL_EXIT", "status": "EXECUTED"}, failed, "MODEL_EXIT_EXECUTED", repeated
    if failed: return None, failed, "Q1_SIGNAL_FILL_UNAVAILABLE", repeated
    return None, failed, "REACHED_T2_BEFORE_MODEL_EXIT" if terminal_ms < p0_ms else "ELIGIBLE_NEVER_Q1", repeated


def paired_summary(rows, cost="C_BASE"):
    d=np.asarray([r["costs"][cost]["delta_return"] for r in rows],float)
    dp=np.asarray([r["costs"][cost]["delta_pnl"] for r in rows],float)
    p0=np.asarray([r["costs"][cost]["p0_return"] for r in rows],float)
    pol=np.asarray([r["costs"][cost]["c25_return"] for r in rows],float)
    return {"count":len(rows),"p0_total_pnl":float(1000*p0.sum()),"c25_total_pnl":float(1000*pol.sum()),
        "mean_p0_return":float(p0.mean()) if len(rows) else None,"mean_c25_return":float(pol.mean()) if len(rows) else None,
        "mean_paired_return_difference":float(d.mean()) if len(rows) else None,"median_paired_return_difference":float(np.median(d)) if len(rows) else None,
        "total_pnl_difference":float(dp.sum()),"wins":int((d>0).sum()),"losses":int((d<0).sum()),"ties":int((d==0).sum()),
        "changed_count":int((d!=0).sum()),"changed_fraction":float((d!=0).mean()) if len(rows) else None}


def bootstrap(rows, unit, seed=SEED, replicates=REPLICATES):
    labels=[]; groups=defaultdict(list)
    if unit == "whole_trade":
        labels=list(range(len(rows))); groups={i:[i] for i in labels}
        construction="resample complete original trades; pairing preserved"
    elif unit == "calendar_month":
        for i,r in enumerate(rows): groups[r["entry_month"]].append(i)
        labels=sorted(groups); construction="resample UTC entry calendar-month blocks; all symbols and trades retained"
    else: raise ValueError("unknown bootstrap unit")
    rng=np.random.Generator(np.random.PCG64(seed)); samples=[]
    for _ in range(replicates):
        ix=[i for j in rng.integers(len(labels),size=len(labels)) for i in groups[labels[int(j)]]]
        all_d=np.asarray([rows[i]["costs"]["C_BASE"]["delta_return"] for i in ix])
        cov=np.asarray([rows[i]["costs"]["C_BASE"]["delta_return"] for i in ix if rows[i]["covered"]])
        samples.append((float(all_d.mean()),float(cov.mean())))
    a=np.asarray(samples); names=("full_population_mean_paired_return_difference","model_covered_mean_paired_return_difference")
    return {"unit":unit,"construction":construction,"seed":seed,"generator":"PCG64","replicates":replicates,"pairing_preserved":True,
        "calendar_months":labels if unit=="calendar_month" else None,
        "intervals":{n:{"ci95":np.quantile(a[:,j],[.025,.975],method="linear").tolist(),"replicate_sha256":hashlib.sha256(a[:,j].astype("<f8").tobytes()).hexdigest()} for j,n in enumerate(names)}}


def _trade_rows(repo, causal_rows):
    trades={r["trade_id"]:r for r in c8.load_trades(repo)}
    markets={s:c8.load_market(repo/f"data/normalized/c2_history/{s}_1m.csv.gz") for s in c8.SYMBOLS}
    for tr in trades.values():
        terminal=c8.terminal_for_trade(tr,markets[tr["symbol"]]); tr.update(terminal)
    p0_price={}
    p=repo/"artifacts/c2_asymmetric_exit_experiment/common_horizons_p0.csv"; reject_2026(p)
    with p.open(newline="",encoding="utf-8") as f:
        for r in csv.DictReader(f): p0_price[r["trade_id"]]=float(r["p0_raw_exit_price"])
    by=defaultdict(list)
    for r in causal_rows: by[r["trade_id"]].append(r)
    return trades,markets,p0_price,by


def _cohort(rows, predicate): return [r for r in rows if predicate(r)]


def run(repo: Path) -> dict:
    repo=repo.resolve(); reject_2026(repo)
    if os.environ.get("CONDA_DEFAULT_ENV") != "binance-v2-research": raise RuntimeError("conda environment must be binance-v2-research")
    if sha(repo/CONTRACT_REL) != CONTRACT_SHA256: raise RuntimeError("C25 contract changed after prospective freeze")
    out=repo/OUTPUT_REL; out.mkdir(parents=True,exist_ok=True)
    rows,info=c22.build_causal_rows(repo); rows24=[r for r in rows if r["year"]==2024]; rows25=[r for r in rows if r["year"]==2025]
    train24,valid24=c8.split_fold(rows24,"fold_B")
    if (len(train24),len({r['trade_id'] for r in train24}),len(valid24),len({r['trade_id'] for r in valid24}),len(rows25),len({r['trade_id'] for r in rows25})) != (7970,256,8631,267,39616,1087): raise RuntimeError("honest population mismatch")
    datasets={"2024":(train24,valid24),"2025":(rows24,rows25)}; scored={}; boundaries={}; score_rec={}; q1_rec={}
    c23_metrics={y:json.loads((repo/c23.OUTPUT_REL/f"binary_metrics_{y}.json").read_text())[TARGET]["S+C9"] for y in datasets}
    for year,(training,valid) in datasets.items():
        pt=c23.fit_candidates(training,training,TARGET)[0]["S+C9"]["binary"]
        pv=c23.fit_candidates(training,valid,TARGET)[0]["S+C9"]["binary"]
        met=c22.binary_metrics(valid,TARGET,pv); exact=all(abs(met[k]-c23_metrics[year][k])<1e-14 for k in ("brier","log_loss","auc","prevalence"))
        pred_sha=c24._prediction_sha(pv); published=json.loads((repo/c24.OUTPUT_REL/"frozen_prediction_reconciliation.json").read_text())[year][TARGET]
        exact=exact and pred_sha==published["validation_prediction_sha256"]
        bd=c24.bin_boundaries(pt,training); boundary=float(bd["cut_values"][0]); bins=c24.assign_bins(pv,bd["cut_values"]); count=(int((bins==0).sum()),len({valid[i]["trade_id"] for i in np.flatnonzero(bins==0)}))
        boundary_ok=boundary==EXPECTED_BOUNDARIES[year] and count==EXPECTED_Q1[year]
        if not exact: raise RuntimeError("INSUFFICIENT_SCORE_REPRODUCTION")
        if not boundary_ok: raise RuntimeError("INSUFFICIENT_Q1_REPRODUCTION")
        boundaries[year]=boundary; scored[year]=(valid,pv); score_rec[year]={"status":"PASS","target":TARGET,"model":"S+C9 L2 logistic C=1.0","training_prediction_sha256":c24._prediction_sha(pt),"validation_prediction_sha256":pred_sha,"published_metrics_exact":True}
        q1_rec[year]={"status":"PASS","boundary":boundary,"comparison":"probability <= boundary (searchsorted side=left)","validation_q1_snapshots":count[0],"validation_q1_trades":count[1],"identical_values_never_split":True}
    trades,markets,p0_prices,by_all=_trade_rows(repo,rows); honest={}; probabilities={}
    for year,(rr,pp) in scored.items():
        for r,p in zip(rr,pp): honest.setdefault(r["trade_id"],[]).append(r); probabilities.setdefault(r["trade_id"],[]).append(float(p))
    training_ids={r["trade_id"] for r in train24}; ledger=[]; precedence=[]
    for tid,tr in sorted(trades.items(),key=lambda x:(x[1]["entry_ms"],x[1]["symbol"],x[0])):
        market=markets[tr["symbol"]]; states=honest.get(tid,[]); probs=probabilities.get(tid,[]); covered=bool(states)
        if tid in training_ids:
            decision,failed,path,repeated=None,[],"2024_TRAINING_ONLY_FALLBACK",0
        elif not covered:
            decision,failed,path,repeated=None,[],"NO_HONEST_MODEL_COVERAGE",0
        else:
            decision,failed,path,repeated=choose_model_exit(states,probs,boundaries[str(tr["year"])],tr["terminal_ms"],tr["p0_ms"],lambda t:c20._open_at(market,t))
        executed=path=="MODEL_EXIT_EXECUTED"; exit_ms=int(decision["actual_ms"]) if executed else tr["p0_ms"]; exit_price=float(decision["price"]) if executed else p0_prices[tid]
        costs={}
        for cost in COSTS:
            p0=c7.cost_ledger(tr["entry_price"],p0_prices[tid],cost); pol=c7.cost_ledger(tr["entry_price"],exit_price,cost)
            costs[cost]={"p0_return":float(p0["net_return"]),"c25_return":float(pol["net_return"]),"delta_return":float(pol["net_return"]-p0["net_return"]),"p0_pnl":float(1000*p0["net_return"]),"c25_pnl":float(1000*pol["net_return"]),"delta_pnl":float(1000*(pol["net_return"]-p0["net_return"]))}
        first=min(states,key=lambda r:r["state_ms"]) if states else None
        q1state=decision if decision and q1(decision["probability"],boundaries[str(tr["year"])]) else None
        row={"trade_id":tid,"symbol":tr["symbol"],"entry_timestamp_ms":tr["entry_ms"],"entry_month":datetime.fromtimestamp(tr["entry_ms"]/1000,timezone.utc).strftime("%Y-%m"),"year":tr["year"],
            "evaluation_status":"HONEST_POLICY_EVALUATION" if covered else "FALLBACK_ONLY","honest_policy_coverage_status":"COVERED" if covered else "NOT_COVERED","covered":covered,
            "first_eligible_score_timestamp_ms":int(first["state_ms"]) if first else None,"first_q1_timestamp_ms":q1state["decision_ms"] if q1state else None,"q1_probability":q1state["probability"] if q1state else None,
            "q1_boundary_provenance":f"C24 {tr['year']} {TARGET} training predictions" if covered else None,"candidate_fill_timestamp_ms":q1state["candidate_ms"] if q1state else None,
            "actual_model_fill_timestamp_ms":decision.get("actual_ms") if executed else None,"execution_price":exit_price if executed else None,"execution_status":decision.get("status") if decision else None,
            "precedence_outcome":decision.get("precedence") if decision else None,"policy_path_category":path,"frozen_lifecycle_class":tr["terminal"],"canonical_p0_exit_timestamp_ms":tr["p0_ms"],
            "c25_exit_timestamp_ms":exit_ms,"failed_execution_opportunities":len(failed),"reassessments_before_first_q1":repeated,"costs":costs,
            "canonical_p0_net_return":costs["C_BASE"]["p0_return"],"c25_net_return":costs["C_BASE"]["c25_return"],"paired_return_difference":costs["C_BASE"]["delta_return"],
            "p0_pnl":costs["C_BASE"]["p0_pnl"],"c25_pnl":costs["C_BASE"]["c25_pnl"],"paired_pnl_difference":costs["C_BASE"]["delta_pnl"]}
        ledger.append(row)
        if decision and decision.get("precedence") in ("T2","P0"): precedence.append({"trade_id":tid,**decision})
    if len(ledger)!=2199 or len({r["trade_id"] for r in ledger})!=2199: raise RuntimeError("population/P0 pairing fails")
    covered_rows=[r for r in ledger if r["covered"]]; full=paired_summary(ledger); covered_result=paired_summary(covered_rows)
    costs={c:paired_summary(ledger,c) for c in COSTS}; yearly={y:paired_summary(_cohort(ledger,lambda r,y=y:r["year"]==y and r["covered"])) for y in (2024,2025)}
    symbols={s:paired_summary(_cohort(ledger,lambda r,s=s:r["symbol"]==s))|{"policy_covered_count":sum(r["covered"] for r in ledger if r["symbol"]==s),"model_exit_count":sum(r["policy_path_category"]=="MODEL_EXIT_EXECUTED" for r in ledger if r["symbol"]==s)} for s in c8.SYMBOLS}
    lifecycle={x:paired_summary(_cohort(ledger,lambda r,x=x:r["frozen_lifecycle_class"]==x))|{"model_exit_count":sum(r["policy_path_category"]=="MODEL_EXIT_EXECUTED" for r in ledger if r["frozen_lifecycle_class"]==x)} for x in ("T2_FIRST","P0_FIRST")}
    tail={}
    for name,pred in ((">=+0.5%",lambda x:x>=.005),(">=+1%",lambda x:x>=.01),(">=+2%",lambda x:x>=.02),(">=+3%",lambda x:x>=.03),(">=+5%",lambda x:x>=.05),("<0",lambda x:x<0)):
        rr=[r for r in ledger if pred(r["canonical_p0_net_return"])]; tail[name]=paired_summary(rr)|{"c25_exit_count":sum(r["policy_path_category"]=="MODEL_EXIT_EXECUTED" for r in rr)}
    executed=[r for r in ledger if r["policy_path_category"]=="MODEL_EXIT_EXECUTED"]
    def impact(r):
        d,p=r["paired_return_difference"],r["canonical_p0_net_return"]
        return "TIE" if d==0 else "AVOIDED_LOSS" if d>0 and p<0 else "PRESERVED_GAIN" if d>0 else "SURRENDERED_UPSIDE" if p>0 else "DEEPENED_LOSS"
    impacts={k:{"count":sum(impact(r)==k for r in executed),"pnl_contribution":float(sum(r["paired_pnl_difference"] for r in executed if impact(r)==k))} for k in ("AVOIDED_LOSS","PRESERVED_GAIN","SURRENDERED_UPSIDE","DEEPENED_LOSS","TIE")}
    months={m:paired_summary([r for r in ledger if r["entry_month"]==m]) for m in sorted({r["entry_month"] for r in ledger})}
    wb=bootstrap(ledger,"whole_trade"); mb=bootstrap(ledger,"calendar_month")
    symbol_positive=sum(v["mean_paired_return_difference"]>0 for v in symbols.values()); right_tail=sum(v["total_pnl_difference"] for k,v in tail.items() if k==">=+5%")
    predicates={"full_population_mean_positive":full["mean_paired_return_difference"]>0,"2024_honest_mean_positive":yearly[2024]["mean_paired_return_difference"]>0,"2025_untouched_mean_positive":yearly[2025]["mean_paired_return_difference"]>0,
        "whole_trade_no_clear_negative":wb["intervals"]["full_population_mean_paired_return_difference"]["ci95"][1]>=0,"calendar_month_no_clear_negative":mb["intervals"]["full_population_mean_paired_return_difference"]["ci95"][1]>=0,
        "positive_symbols":symbol_positive,"not_obviously_one_symbol":symbol_positive>1,"profitable_tail_not_net_surrendered":right_tail>=0}
    supported=all(predicates[k] for k in ("full_population_mean_positive","2024_honest_mean_positive","2025_untouched_mean_positive","whole_trade_no_clear_negative","calendar_month_no_clear_negative","not_obviously_one_symbol","profitable_tail_not_net_surrendered"))
    classification="POLICY_ECONOMIC_SIGNAL_SUPPORTED" if supported else "NO_USEFUL_POLICY_ECONOMIC_SIGNAL" if (not predicates["full_population_mean_positive"] or not predicates["2025_untouched_mean_positive"]) else "WEAK_POLICY_ECONOMIC_SIGNAL"
    paths=dict(Counter(r["policy_path_category"] for r in ledger)); q1_rows=[r for r in ledger if r["first_q1_timestamp_ms"] is not None]
    entry_to_q1=[(r["first_q1_timestamp_ms"]-r["entry_timestamp_ms"])/60000 for r in q1_rows]
    signal_to_fill=[(r["actual_model_fill_timestamp_ms"]-r["first_q1_timestamp_ms"])/60000 for r in executed]
    path_report={"counts":paths,"q1_decisions":len(q1_rows)+sum(r["failed_execution_opportunities"] for r in ledger),"unique_trades_with_q1":len(q1_rows),"executed_exits":len(executed),"failed_execution_opportunities":sum(r["failed_execution_opportunities"] for r in ledger),"fallback_p0_trades":len(ledger)-len(executed),
        "time_entry_to_first_q1_minutes":{"mean":float(np.mean(entry_to_q1)) if entry_to_q1 else None,"median":float(np.median(entry_to_q1)) if entry_to_q1 else None,"min":float(np.min(entry_to_q1)) if entry_to_q1 else None,"max":float(np.max(entry_to_q1)) if entry_to_q1 else None},
        "time_q1_signal_to_actual_fill_minutes":{"mean":float(np.mean(signal_to_fill)) if signal_to_fill else None,"median":float(np.median(signal_to_fill)) if signal_to_fill else None,"min":float(np.min(signal_to_fill)) if signal_to_fill else None,"max":float(np.max(signal_to_fill)) if signal_to_fill else None},
        "reassessments_before_first_q1":{"total":sum(r["reassessments_before_first_q1"] for r in q1_rows),"mean":float(np.mean([r["reassessments_before_first_q1"] for r in q1_rows])) if q1_rows else None}}
    population=info|{"original_entries":len(ledger),"paired_p0":len(ledger),"years":dict(Counter(str(r["year"]) for r in ledger)),"lifecycle_classes":dict(Counter(r["frozen_lifecycle_class"] for r in ledger)),"exact_reconciliation":len(ledger)==2199}
    honest_pop={"2024_training_rows":7970,"2024_training_trades":256,"2024_validation_rows":8631,"2024_validation_trades":267,"2025_evaluation_rows":39616,"2025_evaluation_trades":1087,"covered_trades":len(covered_rows),"training_only_fallback_trades":paths.get("2024_TRAINING_ONLY_FALLBACK",0),"no_honest_coverage_trades":paths.get("NO_HONEST_MODEL_COVERAGE",0)}
    provenance={"contract_sha256":CONTRACT_SHA256,"c23_source_sha256":sha(repo/"src/binance_data_foundation/c23_incremental_c9_ablation.py"),"c24_source_sha256":sha(repo/"src/binance_data_foundation/c24_probability_economic_ordering.py"),"c23_artifact_hashes_sha256":sha(repo/c23.OUTPUT_REL/"reproducibility_hashes.json"),"c24_artifact_hashes_sha256":sha(repo/c24.OUTPUT_REL/"reproducibility_hashes.json"),"no_2026_access":True}
    files={"run_manifest":{"version":"C25_RUN_V1","contract_sha256":CONTRACT_SHA256,"seed":SEED,"replicates":REPLICATES,"generator":"PCG64","python":sys.version,"numpy":np.__version__,"platform":platform.platform(),"conda_environment":"binance-v2-research"},"provenance":provenance,"population_reconciliation":population,"honest_policy_population":honest_pop,"score_reproduction":score_rec,"q1_boundary_reproduction":q1_rec,
        "decision_timing_audit":{"status":"PASS","decision":"after completed five-minute state","execution":"open at state-end timestamp, the next one-minute interval","same_bar_fill":False,"sole_score":TARGET},"execution_contract":{"full_exit":True,"reentry":False,"partial_exit":False,"missing_fill":"fail closed then later honest reassessment","costs":list(COSTS)},"lifecycle_precedence_audit":{"rule":"T2 or P0 at or before candidate fill wins","cases":precedence},"policy_path_counts":path_report,"policy_trade_ledger":ledger,"full_population_results":full,"covered_population_results":covered_result,"yearly_results":yearly,"symbol_results":symbols,"lifecycle_class_results":lifecycle,"right_tail_results":tail,"avoided_loss_surrendered_upside":impacts,"cost_robustness":costs,"calendar_month_results":months,"whole_trade_bootstrap":wb,"calendar_month_bootstrap":mb,"interpretation_predicates":predicates|{"classification":classification}}
    for name,value in files.items(): write(out/f"{name}.json",value)
    final={"contract_sha256":CONTRACT_SHA256,"population_reconciliation":population,"honest_policy_population":honest_pop,"score_reproduction":score_rec,"q1_boundary_reproduction":q1_rec,"policy_path_counts":path_report,"C_BASE_full_population":full,"C_BASE_covered_population":covered_result,"yearly_results":yearly,"cost_robustness":costs,"lifecycle_class_results":lifecycle,"right_tail_results":tail,"avoided_loss_surrendered_upside":impacts,"symbol_results":symbols,"calendar_month_results":months,"whole_trade_bootstrap":wb,"calendar_month_bootstrap":mb,"classification":classification,"interpretation_predicates":predicates,"limitations":["historical paired policy experiment, not deployment evidence","one honest 2024 validation block","five symbols are not independent replications","unchanged trades dilute full-population effect by design"],"implication_for_C26":"C26 not started; no authorization follows from C25.","confirmations":{"sole_policy":"first honest pre-T2 Q1 DELTA_LIQ_5 S+C9 signal, irreversible full next-open exit","alternate_threshold_persistence_horizon_model_search":False,"pnl_optimization":False,"accessed_2026":False,"C26_started":False,"staged_committed_or_pushed":False}}
    write(out/"final_summary.json",final); write(out/"reproducibility_hashes.json",{p.name:sha(p) for p in sorted(out.glob("*.json")) if p.name!="reproducibility_hashes.json"})
    return final


if __name__ == "__main__": run(Path.cwd())
