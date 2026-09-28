"""C18 descriptive alignment of frozen C9 prognosis with pre-T2 economic value."""
from __future__ import annotations

import hashlib, json, math, os, platform, sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from . import c7_t1 as c7
from . import c8_timescale as c8
from . import c9_dynamic_state as c9

CONTRACT_SHA256 = "127c47d767b3ecdeac89108a21125b9996f6155ae61c463036af2b62f3193c0a"
CONTRACT_REL = "contracts/C18_pre_t2_economic_value_CONTRACT.md"
OUTPUT_REL = "artifacts/c18_pre_t2_economic_value"
BANDS = (("<0.20", 0, .2), ("0.20 to <0.40", .2, .4), ("0.40 to <0.60", .4, .6),
         ("0.60 to <0.80", .6, .8), (">=0.80", .8, 1.0000000001))
TIME_BANDS = (("0-30m", 0, 30), (">30-60m", 30, 60), (">60-120m", 60, 120),
              (">120-240m", 120, 240), (">240m", 240, float("inf")))
PROHIBITED = ("delta_v", "exit_now", "hold_to_p0", "future_mfe", "future_mae", "future_t2",
              "future_p0", "recovery", "future_path")

def reject_2026(path):
    if any("2026" in p for p in os.fspath(path).replace("\\", "/").lower().split("/")):
        raise PermissionError("C18 prohibits 2026 data or metadata access")

def sha(path: Path):
    reject_2026(path); h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""): h.update(block)
    return h.hexdigest()

def write(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n")

def assert_feature_firewall(names):
    bad = [n for n in names if any(x in n.lower() for x in PROHIBITED)]
    if bad: raise ValueError("future/target-derived feature prohibited: " + ", ".join(bad))

def target_for_snapshot(row, trade, market, p0_price, cost="C_BASE"):
    """Evaluation-only target; feature values cannot enter this function."""
    t, p0 = int(row["state_ms"]), int(trade["p0_ms"])
    if t >= p0: return {"eligible": False, "reason": "P0_TIE_OR_PRECEDENCE"}
    i, prior = market.index(t), market.index(t - c8.MINUTE)
    if i is None: return {"eligible": False, "reason": "MISSING_NEXT_OPEN"}
    if prior is None or int(market.ms[prior]) + c8.MINUTE != t or int(market.ms[i]) != t:
        return {"eligible": False, "reason": "GAP_FAIL_CLOSED"}
    price = float(market.open[i])
    if not math.isfinite(price) or price <= 0: return {"eligible": False, "reason": "INVALID_NEXT_OPEN"}
    now = c7.cost_ledger(float(trade["entry_price"]), price, cost)
    hold = c7.cost_ledger(float(trade["entry_price"]), float(p0_price), cost)
    delta = float(hold["net_return"] - now["net_return"])
    return {"eligible": True, "reason": "ELIGIBLE", "execution_ms": t, "exit_now_price": price,
            "exit_now_net": float(now["net_return"]), "hold_to_p0_net": float(hold["net_return"]),
            "delta_v": delta, "economic_state": "HOLD_BETTER" if delta > 0 else "EXIT_BETTER" if delta < 0 else "EXACT_ZERO"}

def weights(rows): return c8.trade_weights(rows)

def weighted_corr(rows, x="p_t2", y="delta_v"):
    if not rows: return None
    w = weights(rows); w /= w.sum(); a = np.asarray([r[x] for r in rows]); b = np.asarray([r[y] for r in rows])
    ma, mb = float(w @ a), float(w @ b); den = math.sqrt(float(w @ ((a-ma)**2)) * float(w @ ((b-mb)**2)))
    return float(w @ ((a-ma)*(b-mb)) / den) if den else None

def ranks(a):
    a=np.asarray(a); order=np.argsort(a, kind="mergesort"); out=np.empty(len(a), float); i=0
    while i<len(a):
        j=i+1
        while j<len(a) and a[order[j]]==a[order[i]]: j+=1
        out[order[i:j]]=(i+j-1)/2; i=j
    return out

def spearman(rows):
    if not rows: return None
    rr=[dict(r, _rx=float(x), _ry=float(y)) for r,x,y in zip(rows,ranks([r["p_t2"] for r in rows]),ranks([r["delta_v"] for r in rows]))]
    return weighted_corr(rr,"_rx","_ry")

def summary(rows):
    if not rows: return None
    a=np.asarray([r["delta_v"] for r in rows]); w=weights(rows); w/=w.sum()
    return {"snapshots":len(rows),"unique_trades":len({r['trade_id'] for r in rows}),"mean_delta_v_pre":float(w@a),
            "median_delta_v_pre":float(np.median(a)),"p10":float(np.quantile(a,.1)),"p25":float(np.quantile(a,.25)),
            "p75":float(np.quantile(a,.75)),"p90":float(np.quantile(a,.9)),"fraction_hold_better":float(w@(a>0)),
            "fraction_exit_better":float(w@(a<0)),"fraction_exact_zero":float(w@(a==0))}

def band_name(p):
    return next(name for name,lo,hi in BANDS if lo <= p < hi)

def band_summary(rows): return {name:summary([r for r in rows if lo<=r["p_t2"]<hi]) for name,lo,hi in BANDS}

def association(rows): return {"spearman":spearman(rows),"trade_weighted_correlation":weighted_corr(rows)}

def time_name(minutes):
    for name,lo,hi in TIME_BANDS:
        if (minutes>=lo if lo==0 else minutes>lo) and minutes<=hi:return name

def p_dist(rows):
    if not rows:return None
    a=np.asarray([r["p_t2"] for r in rows]); w=weights(rows);w/=w.sum()
    return {"mean":float(w@a),"median":float(np.median(a)),"p10":float(np.quantile(a,.1)),"p90":float(np.quantile(a,.9))}

def elapsed_summary(rows):
    out={"since_entry":{},"remaining_to_p0":{}}
    for name,_,_ in TIME_BANDS:
        for mode,calc in (("since_entry",lambda r:(r["state_ms"]-r["entry_ms"])/c8.MINUTE),
                          ("remaining_to_p0",lambda r:(r["p0_ms"]-r["state_ms"])/c8.MINUTE)):
            rr=[r for r in rows if time_name(calc(r))==name]
            out[mode][name]={"p_t2_distribution":p_dist(rr),"economic_value":summary(rr),"association":association(rr)}
    return out

def trajectories(rows):
    by=defaultdict(list)
    for r in rows:by[r["trade_id"]].append(r)
    for rr in by.values():rr.sort(key=lambda x:x["state_ms"])
    return dict(sorted(by.items()))

def trajectory_alignment(rows):
    stats=[]; rise=[]; fall=[]
    for tid,rr in trajectories(rows).items():
        dp=np.diff([r["p_t2"] for r in rr]); dv=np.diff([r["delta_v"] for r in rr])
        corr=float(np.corrcoef([r["p_t2"] for r in rr],[r["delta_v"] for r in rr])[0,1]) if len(rr)>=3 and np.std([r["p_t2"] for r in rr])>0 and np.std([r["delta_v"] for r in rr])>0 else None
        if np.any(dp>0):rise.append(float(np.mean(dv[dp>0]>0)))
        if np.any(dp<0):fall.append(float(np.mean(dv[dp<0]<0)))
        stats.append({"trade_id":tid,"observations":len(rr),"within_trade_correlation":corr})
    cs=[x["within_trade_correlation"] for x in stats if x["within_trade_correlation"] is not None]
    return {"deterministic_aggregation":"equal mean of within-trade proportions/correlations","trades":len(stats),
            "rising_p_coincides_improving_delta_v":float(np.mean(rise)) if rise else None,
            "falling_p_coincides_deteriorating_delta_v":float(np.mean(fall)) if fall else None,
            "within_trade_correlation":{"eligible_trades":len(cs),"mean":float(np.mean(cs)) if cs else None,"median":float(np.median(cs)) if cs else None,
            "p10":float(np.quantile(cs,.1)) if cs else None,"p90":float(np.quantile(cs,.9)) if cs else None}}

def persistence(rows):
    ts=[]; by=trajectories(rows)
    for tid,rr in by.items():
        s=[r["economic_state"] for r in rr]; trans=sum(a!=b for a,b in zip(s,s[1:]));ts.append({"trade_id":tid,"transitions":trans,"monostate":len(set(s))==1})
    horizons={}
    for mins in (5,15,30):
        vals=[]
        for rr in by.values():
            lookup={r["state_ms"]:r for r in rr}; pairs=[(r,lookup.get(r["state_ms"]+mins*c8.MINUTE)) for r in rr];pairs=[x for x in pairs if x[1] is not None]
            if pairs:vals.append(float(np.mean([a["economic_state"]==b["economic_state"] for a,b in pairs])))
        horizons[str(mins)]={"eligible_trades":len(vals),"same_state_persistence":float(np.mean(vals)) if vals else None}
    tv=np.asarray([x["transitions"] for x in ts])
    return {"transitions_per_trade":{"mean":float(tv.mean()),"median":float(np.median(tv)),"p10":float(np.quantile(tv,.1)),"p90":float(np.quantile(tv,.9)),"min":int(tv.min()),"max":int(tv.max())},
            "fraction_monostate":float(np.mean([x["monostate"] for x in ts])),"horizons_minutes":horizons}

def right_tail(rows):
    vals=[]; extrema=[]
    for tid,rr in trajectories(rows).items():
        vals.append(sum(max(0,r["delta_v"]) for r in rr));extrema.append((max([0.0]+[r["delta_v"] for r in rr]),min(r["delta_v"] for r in rr)))
    desc=np.sort(vals)[::-1];asc=np.sort(vals);total=float(np.sum(vals));n=len(vals)
    shares={f"top_{p}_percent":float(np.sum(desc[:max(1,int(np.ceil(n*p/100)))])/total) if total else None for p in (1,5,10,20)}
    gini=float(2*np.sum(np.arange(1,n+1)*asc)/(n*total)-(n+1)/n) if total else None
    return {"trade_measure":"sum of positive snapshot DELTA_V_PRE within trade","trades":n,"cumulative_contribution":shares,"gini":gini,
            "maximum_positive_delta_v_per_trade":summary_extrema([x[0] for x in extrema]),"minimum_delta_v_per_trade":summary_extrema([x[1] for x in extrema])}

def summary_extrema(values):
    a=np.asarray(values);return {"mean":float(a.mean()),"median":float(np.median(a)),"min":float(a.min()),"max":float(a.max())}

def reproduce_probabilities(rows):
    rows24=[r for r in rows if r["year"]==2024];rows25=[r for r in rows if r["year"]==2025]
    pooled=[];pp=[]
    for fold,(_start,_cut,end) in c8.FOLDS.items():
        train,valid=c8.split_fold(rows24,fold);base=c9._fit_base(train);raw=c9._predict_base(base,valid);inner,ip,_defs=c9.inner_predictions(rows24,end)
        cal=c9.fit_platt(inner,ip);pred=c9.apply_platt(cal,raw);pooled.extend(valid);pp.extend(pred)
    inner,ip,_=c9.inner_predictions(rows24,c9.YEAR_END+1);cal=c9.fit_platt(inner,ip);base=c9._fit_base(rows24);p25=c9.apply_platt(cal,c9._predict_base(base,rows25))
    return pooled,np.asarray(pp),rows25,p25

def run(repo:Path):
    reject_2026(repo)
    if os.environ.get("CONDA_DEFAULT_ENV")!="binance-v2-research":raise RuntimeError("conda environment must be binance-v2-research")
    contract=repo/CONTRACT_REL
    if sha(contract)!=CONTRACT_SHA256:raise RuntimeError("C18 contract changed after prospective freeze")
    assert_feature_firewall(c8.SLOW_FEATURES+c8.FAST_FEATURES+c8.SYMBOL_FEATURES)
    out=repo/OUTPUT_REL;out.mkdir(parents=True,exist_ok=True)
    trades=c8.load_trades(repo);markets={};bars={}
    for symbol in c8.SYMBOLS:
        market=c8.load_market(repo/f"data/normalized/c2_history/{symbol}_1m.csv.gz");markets[symbol]=market
        bars[(symbol,5)]=c8.aggregate(market,5);bars[(symbol,60)]=c8.aggregate(market,60)
    for tr in trades:tr.update(c8.terminal_for_trade(tr,markets[tr["symbol"]]))
    causal=c8.snapshots(trades,markets,bars,"B");pooled,p24,rows25,p25=reproduce_probabilities(causal)
    scored=pooled+rows25;probs=np.concatenate((p24,p25))
    frozen=json.loads((repo/"artifacts/c9_dynamic_pre_t2_state/final_summary.json").read_text())
    reproduced={"2024":c9.evaluate(pooled,{"calibrated":p24})["calibrated"],"2025":c9.evaluate(rows25,{"calibrated":p25})["calibrated"]}
    expected={"2024":frozen["development_2024"]["metrics"]["platt"],"2025":frozen["stability_2025"]["metrics"]["calibrated"]}
    diffs={y:max(abs(reproduced[y][k]-expected[y][k]) for k in ("brier","log_loss","auc")) for y in expected}
    c9rep={"status":"PASS" if max(diffs.values())<1e-12 else "FAIL","selected_calibration":"platt","metrics":reproduced,"frozen_metrics":expected,"max_abs_core_metric_difference":diffs,"refit_or_recalibrated":False}
    if c9rep["status"]!="PASS":raise RuntimeError("frozen C9 probability reproduction failed")
    source=json.loads((repo/"artifacts/c7_full_population_t2_exit_overlay/population_manifest.json").read_text());p0={r["trade_id"]:float(r["p0_raw_exit_price"]) for r in source["rows"]};tm={t["trade_id"]:t for t in trades}
    rows=[];excluded=Counter()
    for r,p in zip(scored,probs):
        tr=tm[r["trade_id"]];target=target_for_snapshot(r,tr,markets[r["symbol"]],p0[r["trade_id"]])
        if not target["eligible"]:excluded[target["reason"]]+=1;continue
        sens={cost:target_for_snapshot(r,tr,markets[r["symbol"]],p0[r["trade_id"]],cost)["delta_v"] for cost in c7.COSTS}
        rows.append(r|target|{"p_t2":float(p),"outcome":"T2_FIRST" if r["label"] else "P0_FIRST","p0_ms":tr["p0_ms"],"sensitivities":sens})
    eligible_ids={r["trade_id"] for r in causal};scored_ids={r["trade_id"] for r in scored};target_ids={r["trade_id"] for r in rows}
    rec={"source_trades":len(trades),"source_outcomes":dict(Counter(t["terminal"] for t in trades)),"causal_snapshots":len(causal),"causal_snapshot_trades":len(eligible_ids),
         "no_eligible_causal_snapshot_trades":len(trades)-len(eligible_ids),"honestly_scored_snapshots":len(scored),"honestly_scored_trades":len(scored_ids),
         "unscored_causal_snapshots":len(causal)-len(scored),"eligible_target_snapshots":len(rows),"eligible_target_trades":len(target_ids),"target_ineligible":dict(excluded)}
    overall=summary(rows);bands=band_summary(rows);mono={"bands":bands,**association(rows)}
    outcomes={x:{"overall":summary([r for r in rows if r["outcome"]==x]),"probability_bands":band_summary([r for r in rows if r["outcome"]==x]),"elapsed_time":elapsed_summary([r for r in rows if r["outcome"]==x])} for x in ("T2_FIRST","P0_FIRST")}
    elapsed=elapsed_summary(rows);traj=trajectory_alignment(rows);persist=persistence(rows);tail=right_tail(rows)
    years={str(y):{"overall":summary(rr:= [r for r in rows if r["year"]==y]),"probability_bands":band_summary(rr),"association":association(rr)} for y in (2024,2025)}
    symbols={s:{"overall":summary(rr:=[r for r in rows if r["symbol"]==s]),"probability_bands":band_summary(rr),"association":association(rr)} for s in c8.SYMBOLS}
    def increasing(d,key):
        vals=[d[n][key] for n,_,_ in BANDS if d[n] is not None];return len(vals)==5 and all(b>=a for a,b in zip(vals,vals[1:]))
    ypred={y:{"mean_directional":increasing(years[y]["probability_bands"],"mean_delta_v_pre"),"hold_fraction_directional":increasing(years[y]["probability_bands"],"fraction_hold_better"),
              "positive_association":years[y]["association"]["trade_weighted_correlation"]>0 and years[y]["association"]["spearman"]>0,
              "high_minus_low_mean":years[y]["probability_bands"][">=0.80"]["mean_delta_v_pre"]-years[y]["probability_bands"]["<0.20"]["mean_delta_v_pre"]} for y in ("2024","2025")}
    positive_symbols=sum(v["association"]["trade_weighted_correlation"]>0 for v in symbols.values())
    supported=all(v["mean_directional"] and v["hold_fraction_directional"] and v["positive_association"] and v["high_minus_low_mean"]>0 for v in ypred.values()) and positive_symbols>1
    weak=all(v["positive_association"] and v["high_minus_low_mean"]>0 for v in ypred.values()) and positive_symbols>1
    label="ECONOMIC_ALIGNMENT_SUPPORTED" if supported else "WEAK_ECONOMIC_ALIGNMENT" if weak else "NO_USEFUL_ECONOMIC_ALIGNMENT"
    predicates={"year_predicates":ypred,"symbols_with_positive_association":positive_symbols,"not_driven_by_one_symbol":positive_symbols>1,"classification":label}
    target_summary={"C_BASE":overall,"cost_sensitivity":{cost:summary([dict(r,delta_v=r["sensitivities"][cost]) for r in rows]) for cost in c7.COSTS}}
    leakage={"status":"PASS","causal_builder":"frozen C8 feature_row/snapshots","probability_builder":"frozen C9 only","evaluation_target_builder":"target_for_snapshot receives no feature object","feature_schema_checked":True,"prohibited_predictors":list(PROHIBITED)}
    implication={"ECONOMIC_ALIGNMENT_SUPPORTED":"C18 supports a prospectively frozen early failure-recognition policy experiment in a later checkpoint.","WEAK_ECONOMIC_ALIGNMENT":"Identify the stable portion of the relationship before any policy test.","NO_USEFUL_ECONOMIC_ALIGNMENT":"Do not use C9 probability directly as an economic exit signal; revisit the pre-T2 economic target/state formulation."}[label]
    files={"run_manifest":{"version":"C18_RUN_V1","contract_sha256":CONTRACT_SHA256,"python":sys.version,"numpy":np.__version__,"platform":platform.platform(),"conda_environment":"binance-v2-research"},
      "provenance":{"contract_sha256":CONTRACT_SHA256,"inputs":{CONTRACT_REL:sha(contract),"c9_final_summary":sha(repo/"artifacts/c9_dynamic_pre_t2_state/final_summary.json"),"c7_population":sha(repo/"artifacts/c7_full_population_t2_exit_overlay/population_manifest.json")},"no_2026_access":True},
      "leakage_firewall":leakage,"population_reconciliation":rec,"target_definition":{"primary":"DELTA_V_PRE = HOLD_TO_P0_NET - EXIT_NOW_NET","primary_cost":"C_BASE","execution":"immediate next available 1-minute open after completed state","P0_wins_ties":True,"gap_fail_closed":True,"evaluation_only":True},
      "target_summary":target_summary,"probability_band_summary":bands,"economic_monotonicity":mono,"outcome_class_summary":outcomes,"elapsed_time_summary":elapsed,
      "trajectory_alignment":traj,"economic_state_persistence":persist,"c9_reproduction":c9rep,"right_tail_concentration":tail,"year_summary":years,"symbol_summary":symbols,"interpretation_predicates":predicates}
    for name,value in files.items():write(out/f"{name}.json",value)
    final={"contract_sha256":CONTRACT_SHA256,"population":rec,"leakage_firewall_status":leakage["status"],"c9_reproduction_status":c9rep["status"],"target":target_summary,"probability_bands":bands,"monotonicity":{"spearman":mono["spearman"],"trade_weighted_correlation":mono["trade_weighted_correlation"]},
           "outcome_classes":{k:v["overall"] for k,v in outcomes.items()},"trajectory_alignment":traj,"economic_state_persistence":persist,"right_tail":tail,"years":{k:{"overall":v["overall"],"association":v["association"]} for k,v in years.items()},"symbols":{k:{"overall":v["overall"],"association":v["association"]} for k,v in symbols.items()},
           "interpretation":label,"implication":implication,"limitations":["descriptive realized future-derived target, not a trading policy","2024 honest probabilities cover only frozen chronological validation cohorts","snapshot quantiles are row quantiles while means, proportions, and associations are whole-trade weighted","within-trade observations are dependent"],
           "confirmations":{"new_model_or_recalibration":False,"exit_policy_or_pnl_optimization":False,"threshold_horizon_or_symbol_search":False,"accessed_2026":False,"c19_started":False,"c7_c17_scientific_behavior_modified":False}}
    write(out/"final_summary.json",final);write(out/"reproducibility_hashes.json",{p.name:sha(p) for p in sorted(out.glob("*.json")) if p.name!="reproducibility_hashes.json"})
    return final
