"""C14 bounded post-T2 economic-state characterization (no trading policy)."""
from __future__ import annotations

import hashlib, json, math, os, platform, sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from . import c7_t1 as c7
from . import c8_timescale as c8
from . import c9_dynamic_state as c9
from . import c10_post_t2 as c10
from . import c11_dynamic_post_t2 as c11
from . import c12_post_t2_warning as c12

CONTRACT_SHA256="0e2916068a679ce0b764f72327616fcd8c19aaf663bf6c3f5cb384ea41abaea7"
CONTRACT_REL="contracts/C14_post_t2_economic_state_CONTRACT.md"
OUTPUT_REL="artifacts/c14_post_t2_economic_state"
SEED=20260928
PROHIBITED=("delta_v","exit_now","hold_to_p0","future_mfe","future_mae","future_recovery","future_peak","eventual_p0_return","future_continuation","future_deterioration")
BANDS=(("<0.20",0,.2),("0.20-0.40",.2,.4),("0.40-0.60",.4,.6),("0.60-0.80",.6,.8),(">=0.80",.8,1.0000001))
TIME_BANDS=(("0-5m",0,5),(">5-15m",5,15),(">15-30m",15,30),(">30-60m",30,60),(">60m",60,float("inf")))

def reject_2026(path):
    if any("2026" in x for x in os.fspath(path).replace("\\","/").lower().split("/")):
        raise PermissionError("C14 prohibits 2026 data or metadata access")

def sha(path:Path)->str:
    reject_2026(path); h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1<<20),b""):h.update(b)
    return h.hexdigest()

def write(path:Path,value)->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+"\n")

def assert_feature_firewall(names)->None:
    bad=[n for n in names if any(x in n.lower() for x in PROHIBITED)]
    if bad: raise ValueError("future/target-derived feature prohibited: "+", ".join(bad))

def target_for_snapshot(row,trade,market,p0_price,cost="C_BASE"):
    """Future-side target builder; deliberately receives no feature object."""
    t=int(row["state_ms"]); p0=int(trade["p0_ms"])
    if t>=p0:return {"eligible":False,"reason":"P0_TIE_OR_PRECEDENCE"}
    i=market.index(t); prior=market.index(t-c10.MINUTE)
    if i is None:return {"eligible":False,"reason":"MISSING_NEXT_OPEN"}
    if prior is None or int(market.ms[prior])+c10.MINUTE!=t or int(market.ms[i])!=t:
        return {"eligible":False,"reason":"GAP_FAIL_CLOSED"}
    price=float(market.open[i])
    if not math.isfinite(price) or price<=0:return {"eligible":False,"reason":"INVALID_NEXT_OPEN"}
    now=c7.cost_ledger(float(trade["entry_price"]),price,cost)
    hold=c7.cost_ledger(float(trade["entry_price"]),float(p0_price),cost)
    delta=float(hold["net_return"]-now["net_return"])
    return {"eligible":True,"reason":"ELIGIBLE","execution_ms":t,"exit_now_price":price,
        "exit_now_net":now["net_return"],"hold_to_p0_net":hold["net_return"],"delta_v":delta,
        "economic_state":"HOLD_BETTER" if delta>0 else "EXIT_BETTER" if delta<0 else "EXACT_ZERO"}

def weights(rows):return c10.trade_weights(rows)

def qsummary(rows,field="delta_v"):
    if not rows:return None
    a=np.asarray([r[field] for r in rows],float); w=weights(rows); w/=w.sum()
    # Distribution quantiles remain transparent row quantiles; means/sign rates are trade-normalized.
    return {"snapshots":len(rows),"unique_trades":len({r["trade_id"] for r in rows}),
        "mean":float(w@a),"median":float(np.median(a)),"p10":float(np.quantile(a,.1)),"p25":float(np.quantile(a,.25)),
        "p75":float(np.quantile(a,.75)),"p90":float(np.quantile(a,.9)),
        "fraction_gt_zero":float(w@(a>0)),"fraction_lt_zero":float(w@(a<0)),"fraction_exact_zero":float(w@(a==0))}

def grouped(rows,key):return {str(k):qsummary([r for r in rows if key(r)==k]) for k in sorted({key(r) for r in rows},key=str)}

def characterize(rows):
    out={}
    for name,lo,hi in BANDS:
        rr=[r for r in rows if lo<=r["p_cont"]<hi]
        out[name]={"overall":qsummary(rr),"year":grouped(rr,lambda r:r["year"]),"symbol":grouped(rr,lambda r:r["symbol"])}
    return out

def crosstab(rows):
    w=weights(rows); total=float(w.sum()); cells={}
    for event in ("CONTINUATION_FIRST","DETERIORATION_FIRST"):
        den=float(sum(x for x,r in zip(w,rows) if r["event_label"]==event))
        for state in ("HOLD_BETTER","EXIT_BETTER","EXACT_ZERO"):
            ix=[i for i,r in enumerate(rows) if r["event_label"]==event and r["economic_state"]==state]
            mass=float(w[ix].sum()) if ix else 0.; cells[f"{event}|{state}"]={"snapshots":len(ix),"unique_trades":len({rows[i]["trade_id"] for i in ix}),
                "trade_weight_mass":mass,"proportion_within_event":mass/den if den else None,"proportion_overall":mass/total if total else None}
    return {"dependence_unit":"whole trade; proportions use per-trade-normalized snapshot weights","cells":cells}

def binary_metrics(rows,p):
    if not rows:return None
    base=c8.metrics(rows,np.asarray(p)); base["calibration"]=c9.reliability(rows,np.asarray(p)); return base

def fit_logistic(rows,names):
    w=weights(rows); scaler=c10.fit_scaler(rows,names,w); model=c8.fit_logistic(c10.design(rows,names,scaler),np.asarray([r["label"] for r in rows],float),w)
    return {"names":names,"scaler":scaler,"model":model}

def predict_logistic(model,rows):return c8.predict(model["model"],c10.design(rows,model["names"],model["scaler"]))

def fit_ridge(rows,names):
    w=weights(rows); scaler=c10.fit_scaler(rows,names,w); x=c10.design(rows,names,scaler); y=np.asarray([r["delta_v"] for r in rows]); wn=w/w.sum()
    penalty=np.eye(x.shape[1]);penalty[0,0]=0
    beta=np.linalg.solve(x.T@(wn[:,None]*x)+penalty,x.T@(wn*y))
    return {"names":names,"scaler":scaler,"coef":beta}

def predict_ridge(model,rows):return c10.design(rows,model["names"],model["scaler"])@model["coef"]

def continuous_metrics(rows,p):
    y=np.asarray([r["delta_v"] for r in rows]);p=np.asarray(p);w=weights(rows);w/=w.sum(); err=p-y
    my=float(w@y);mp=float(w@p); cov=float(w@((y-my)*(p-mp))); denom=math.sqrt(float(w@((y-my)**2))*float(w@((p-mp)**2)))
    return {"rows":len(rows),"trades":len({r["trade_id"] for r in rows}),"mae":float(w@np.abs(err)),"rmse":float(math.sqrt(w@(err**2))),
        "correlation":cov/denom if denom else None,"sign_accuracy":float(w@(np.sign(y)==np.sign(p))),"warning":"sign accuracy is not strategy profitability"}

def evaluate_folds(rows24):
    pooled=[];pred=defaultdict(list);ridge=[];defs={}
    for fold,bounds in c10.FOLDS.items():
        train,valid=c10.split_fold(rows24,fold)
        rate=float(weights(train)@np.asarray([r["label"] for r in train])/weights(train).sum())
        p0=np.full(len(valid),rate);m1=fit_logistic(train,c10.CONTEXT_FEATURES);m2=fit_logistic(train,c11.NAMES);rg=fit_ridge(train,c11.NAMES)
        pooled.extend(valid);pred["M0"].extend(p0);pred["M1"].extend(predict_logistic(m1,valid));pred["M2"].extend(predict_logistic(m2,valid));ridge.extend(predict_ridge(rg,valid))
        defs[fold]={"bounds_ms":list(bounds),"training_rows":len(train),"training_trades":len({r['trade_id'] for r in train}),"validation_rows":len(valid),"validation_trades":len({r['trade_id'] for r in valid}),"training_before_validation":max(r['entry_ms'] for r in train)<min(r['entry_ms'] for r in valid),"preprocessing_training_only":True}
    pp={k:np.asarray(v) for k,v in pred.items()}; metrics={k:binary_metrics(pooled,v) for k,v in pp.items()}
    det=[i for i,r in enumerate(pooled) if r["event_label"]=="DETERIORATION_FIRST"]
    return pooled,pp,np.asarray(ridge),defs,metrics,{k:binary_metrics([pooled[i] for i in det],v[det]) for k,v in pp.items()}

def evaluate_2025(rows24,rows25):
    rate=float(weights(rows24)@np.asarray([r["label"] for r in rows24])/weights(rows24).sum()); models={"M1":fit_logistic(rows24,c10.CONTEXT_FEATURES),"M2":fit_logistic(rows24,c11.NAMES)}
    pp={"M0":np.full(len(rows25),rate),**{k:predict_logistic(v,rows25) for k,v in models.items()}}; rg=fit_ridge(rows24,c11.NAMES); rp=predict_ridge(rg,rows25)
    det=[i for i,r in enumerate(rows25) if r["event_label"]=="DETERIORATION_FIRST"]
    return pp,rp,{k:binary_metrics(rows25,v) for k,v in pp.items()},{k:binary_metrics([rows25[i] for i in det],v[det]) for k,v in pp.items()},models,rg

def future_diagnostics(rows,trades,markets):
    by={t["trade_id"]:t for t in trades}; vals=[]
    for r in rows:
        tr=by[r["trade_id"]];m=markets[r["symbol"]]; i=m.index(r["state_ms"]); end=m.index(tr["p0_ms"]-c10.MINUTE)
        if i is None or end is None or end<i:continue
        entry=float(tr["entry_price"]); now=float(r["exit_now_price"]); highs=m.high[i:end+1];lows=m.low[i:end+1]
        hit=np.flatnonzero(highs>=tr["p0_t2"])
        vals.append({"trade_id":r["trade_id"],"delta_v":r["delta_v"],"future_mfe_from_snapshot":float(np.max(highs)/now-1),"future_mae_from_snapshot":float(np.min(lows)/now-1),
            "regains_first_t2_peak":bool(len(hit)),"new_post_t2_high":bool(np.max(highs)>tr["p0_t2"]),"time_to_recovery_minutes":float(hit[0]+1) if len(hit) else None,"eventual_p0_return_from_entry":float(r["hold_to_p0_net"]),"designation":"EVALUATION_ONLY"})
    def stat(key):return qsummary([{**x,"trade_id":x["trade_id"],"delta_v":x[key]} for x in vals if x[key] is not None])
    return {"designation":"EVALUATION_ONLY; never model features or state definitions","snapshots":len(vals),"future_mfe":stat("future_mfe_from_snapshot"),"future_mae":stat("future_mae_from_snapshot"),
        "regain_rate":float(np.mean([x["regains_first_t2_peak"] for x in vals])),"new_high_rate":float(np.mean([x["new_post_t2_high"] for x in vals])),"time_to_recovery":stat("time_to_recovery_minutes"),"eventual_p0_return":stat("eventual_p0_return_from_entry")}

def examples(rows,pred):
    groups=defaultdict(list)
    for i,r in enumerate(rows):groups[(r["year"],r["event_label"],r["economic_state"])].append(i)
    out=[]
    for key,ix in sorted(groups.items()):
        counts=Counter(rows[i]["trade_id"] for i in ix); med=float(np.median(list(counts.values())));tid=min(counts,key=lambda t:(abs(counts[t]-med),t)); jj=sorted([i for i in ix if rows[i]["trade_id"]==tid],key=lambda i:rows[i]["state_ms"])
        out.append({"year":key[0],"event_label":key[1],"economic_state":key[2],"trade_id":tid,"selection":"closest to median state count, then lexicographic trade_id","trajectory":[{"state_ms":rows[i]["state_ms"],"delta_v":rows[i]["delta_v"],"predicted_hold_better":float(pred[i])} for i in jj]})
    return out

def run(repo:Path):
    reject_2026(repo)
    if os.environ.get("CONDA_DEFAULT_ENV")!="binance-v2-research":raise RuntimeError("conda environment must be binance-v2-research")
    contract=repo/CONTRACT_REL
    if sha(contract)!=CONTRACT_SHA256:raise RuntimeError("C14 contract changed after prospective freeze")
    assert_feature_firewall(c11.NAMES+c10.SYMBOL_FEATURES)
    out=repo/OUTPUT_REL;out.mkdir(parents=True,exist_ok=True)
    data=c12.generate_frozen_panel(repo)
    if c12.reproduce_c11(repo,data)["status"]!="PASS":raise RuntimeError("frozen C11 probability reproduction failed")
    manifest=json.loads((repo/"artifacts/c7_full_population_t2_exit_overlay/population_manifest.json").read_text()); src={x["trade_id"]:x for x in manifest["rows"]}; trades={t["trade_id"]:t for t in data["trades"]}
    pmap={(r["trade_id"],r["state_ms"]):float(p) for r,p in zip(data["scored_rows"],data["probabilities"])}
    rows=[];ineligible=Counter()
    for row in data["binary_rows"]:
        tr=trades[row["trade_id"]]; base=target_for_snapshot(row,tr,data["markets"][row["symbol"]],float(src[row["trade_id"]]["p0_raw_exit_price"]))
        if not base["eligible"]:ineligible[base["reason"]]+=1;continue
        key=(row["trade_id"],row["state_ms"])
        sensitivities={c:target_for_snapshot(row,tr,data["markets"][row["symbol"]],float(src[row["trade_id"]]["p0_raw_exit_price"]),c)["delta_v"] for c in c7.COSTS}
        rows.append(row|base|{"label":int(base["delta_v"]>0),"event_label":tr["terminal"],"p_cont":pmap.get(key),"p0_ms":tr["p0_ms"],"sensitivities":sensitivities})
    scored=[r for r in rows if r["p_cont"] is not None]
    # C11 probabilities are needed only for the fixed-band characterization.
    # C14's own chronological folds train from every eligible causal target row.
    rows24=[r for r in rows if r["year"]==2024];rows25=[r for r in rows if r["year"]==2025]
    rec={"source_first_t2_trades":845,"source_outcomes":dict(Counter(t["terminal"] for t in trades.values())),"no_t2_trades_outside_scope":len(manifest["rows"])-845,"binary_source_trades":843,
        "causal_physical_snapshots":len(data["binary_rows"]),"eligible_target_snapshots":len(rows),"ineligible_snapshots":dict(ineligible),"eligible_target_trades":len({r['trade_id'] for r in rows}),
        "frozen_scored_snapshots":len(scored),"frozen_scored_trades":len({r['trade_id'] for r in scored}),"unscored_eligible_snapshots":len(rows)-len(scored),"zero_row_and_unavailable":c12.population(data["trades"],data["binary_rows"],data["scored_rows"])}
    target_summary={"C_BASE":qsummary(scored),"by_year":grouped(scored,lambda r:r["year"]),"by_symbol":grouped(scored,lambda r:r["symbol"]),"cost_sensitivity":{c:qsummary([{**r,"delta_v":r["sensitivities"][c]} for r in scored]) for c in c7.COSTS}}
    pband=characterize(scored);cross=crosstab(scored)
    elapsed={}
    for name,lo,hi in TIME_BANDS:
        take=lambda v:(v>=lo if lo==0 else v>lo) and v<=hi
        elapsed[name]={"since_t2":qsummary([r for r in scored if take((r['state_ms']-r['t0_ms'])/c10.MINUTE)]),"to_p0":qsummary([r for r in scored if take((r['p0_ms']-r['state_ms'])/c10.MINUTE)]),"to_c10_terminal_descriptive_only":qsummary([r for r in scored if take((r['terminal_ms']-r['state_ms'])/c10.MINUTE)])}
    pooled,pp24,rp24,folds,m24,d24=evaluate_folds(rows24); cont24=continuous_metrics(pooled,rp24)
    pp25,rp25,m25,d25,models,rg=evaluate_2025(rows24,rows25);cont25=continuous_metrics(rows25,rp25)
    predictable=all(m24["M2"][x]<m24["M0"][x] and m25["M2"][x]<m25["M0"][x] for x in ("brier","log_loss")) and all(x>0.5 for x in (m24["M2"]["auc"],m25["M2"]["auc"],d24["M2"]["auc"],d25["M2"]["auc"]))
    weak=(all(any(a["M2"][x]<a["M0"][x] for x in ("brier","log_loss")) for a in (m24,m25)) or all(x>0.5 for x in (m24["M2"]["auc"],m25["M2"]["auc"],d24["M2"]["auc"],d25["M2"]["auc"])))
    label="ECONOMIC_STATE_IS_PREDICTABLE" if predictable else "WEAK_ECONOMIC_STATE_SIGNAL" if weak else "NO_USEFUL_ECONOMIC_STATE_SIGNAL"
    schema={"frozen_before_evaluation":True,"M0":"trade-weighted training prevalence","M1":list(c10.CONTEXT_FEATURES)+list(c10.SYMBOL_FEATURES),"M2":list(c11.NAMES)+list(c10.SYMBOL_FEATURES),"ridge":list(c11.NAMES)+list(c10.SYMBOL_FEATURES),"prohibited":list(PROHIBITED),"firewall":"PASS"}
    assoc={"warning":"predictive associations, not causal effects","M2_standardized_coefficients":[{"feature":n,"coefficient":float(v)} for n,v in zip(["intercept"]+list(c11.NAMES)+list(c10.SYMBOL_FEATURES),models["M2"]["model"]["coef"])]}
    files={"run_manifest":{"version":"C14_RUN_V1","contract_sha256":CONTRACT_SHA256,"seed":SEED,"python":sys.version,"numpy":np.__version__,"platform":platform.platform(),"conda_environment":"binance-v2-research"},
      "provenance":{"contract_sha256":CONTRACT_SHA256,"c11_reproduction":c12.reproduce_c11(repo,data),"inputs":{CONTRACT_REL:sha(contract),"c7_population":sha(repo/"artifacts/c7_full_population_t2_exit_overlay/population_manifest.json"),"c11_final":sha(repo/"artifacts/c11_dynamic_post_t2_state/final_summary.json")},"no_2026_access":True},
      "leakage_firewall":{"status":"PASS","causal_builder":"frozen c10.feature_row/snapshots","future_target_builder":"target_for_snapshot receives no features","feature_schema_checked":True,"future_diagnostics_order":"after primary/model evaluation","synthetic_tests_required":True},
      "population_reconciliation":rec,"target_definition":{"primary":"DELTA_V = HOLD_TO_P0_NET - EXIT_NOW_NET","cost":"C_BASE","strict_signs":True,"deadband":False,"P0_wins_ties":True,"gap_fail_closed":True},"target_summary":target_summary,
      "p_cont_band_value_summary":pband,"continuation_deterioration_value_crosstab":cross,"elapsed_time_value_summary":elapsed,"feature_schema":schema,"fold_definitions":folds,
      "model_metrics_2024":m24|{"continuous_ridge":cont24},"calibration_2024":{k:v["calibration"] for k,v in m24.items()},"deterioration_subset_metrics_2024":d24,
      "frozen_model_procedure":{"models":["M0","M1 fixed L2 logistic","M2 fixed L2 logistic","fixed ridge penalty=1"],"search":False,"fit_2025_after_procedure_frozen":True,"feature_associations":assoc},
      "stability_2025":m25|{"continuous_ridge":cont25},"deterioration_subset_metrics_2025":d25}
    for name,value in files.items():write(out/f"{name}.json",value)
    future=future_diagnostics(scored,list(trades.values()),data["markets"]);write(out/"future_excursion_diagnostics.json",future)
    combined=pooled+rows25;combined_pred=np.concatenate((pp24["M2"],pp25["M2"]));write(out/"deterministic_examples.json",{"examples":examples(combined,combined_pred),"manual_selection":False})
    summary={"contract_sha256":CONTRACT_SHA256,"classification":label,"population":rec,"target":target_summary,"cross_tab":cross,"elapsed":elapsed,"metrics_2024":m24,"continuous_2024":cont24,"deterioration_2024":d24,"metrics_2025":m25,"continuous_2025":cont25,"deterioration_2025":d25,"future_diagnostics":future,"feature_associations":assoc,"limitations":["observational counterfactual characterization","snapshot dependence handled by trade weights but not a policy evaluation","2024 OOF covers frozen chronological validation cohorts","future diagnostics are descriptive only"],"confirmations":{"action_threshold_or_trading_policy":False,"future_excursions_as_features":False,"c7_c13f_scientific_modification":False,"accessed_2026":False,"c15_started":False}}
    write(out/"final_summary.json",summary)
    hashes={p.name:sha(p) for p in sorted(out.glob("*.json")) if p.name!="reproducibility_hashes.json"};write(out/"reproducibility_hashes.json",hashes)
    return summary
