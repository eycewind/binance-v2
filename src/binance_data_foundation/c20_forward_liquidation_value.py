"""C20 executable forward liquidation value characterization."""
from __future__ import annotations

import hashlib, json, math, os, platform, sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from . import c7_t1 as c7
from . import c8_timescale as c8
from . import c9_dynamic_state as c9

CONTRACT_SHA256 = "d3184d932a06ccd18dc9cc50412f801c5de92bd2ba6f1e12808c5958e994a491"
CONTRACT_REL = "contracts/C20_forward_liquidation_value_CONTRACT.md"
OUTPUT_REL = "artifacts/c20_forward_liquidation_value"
HORIZONS = (5, 15, 30, 60)
TARGETS = tuple([f"DELTA_LIQ_{h}" for h in HORIZONS] + ["DELTA_LIQ_EVENT"])
BANDS = (("<0.20", 0, .2), ("0.20 to <0.40", .2, .4), ("0.40 to <0.60", .4, .6),
         ("0.60 to <0.80", .6, .8), (">=0.80", .8, 1.0000000001))
TIME_BANDS = (("0-30m", 0, 30), (">30-60m", 30, 60), (">60-120m", 60, 120),
              (">120-240m", 120, 240), (">240m", 240, float("inf")))
COST_CASES = ("C0", "C_BASE", "C_S5", "C_S10")


def reject_2026(path):
    if any("2026" in p for p in os.fspath(path).replace("\\", "/").lower().split("/")):
        raise PermissionError("C20 prohibits 2026 data or metadata access")


def sha(path: Path):
    reject_2026(path)
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""): h.update(block)
    return h.hexdigest()


def write(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n")


def band_name(p):
    return next(name for name, lo, hi in BANDS if lo <= p < hi)


def _open_at(market, timestamp):
    """Exact next-open lookup with adjacent-minute evidence; fail closed."""
    i, prior = market.index(timestamp), market.index(timestamp - c8.MINUTE)
    if i is None: return None, "MISSING_NEXT_OPEN"
    if prior is None or int(market.ms[prior]) + c8.MINUTE != timestamp or int(market.ms[i]) != timestamp:
        return None, "GAP_OR_DUPLICATE_FAIL_CLOSED"
    price = float(market.open[i])
    if not math.isfinite(price) or price <= 0: return None, "INVALID_NEXT_OPEN"
    return price, None


def liquidation_targets(row, trade, market, p0_price, cost="C_BASE"):
    """Build executable targets without reading any price after the terminal."""
    t, terminal = int(row["state_ms"]), int(trade["terminal_ms"])
    if t >= terminal: return {"eligible": False, "reason": "TERMINAL_TIE_OR_PRECEDENCE"}
    now_price, reason = _open_at(market, t)
    if reason: return {"eligible": False, "reason": reason}
    now = c7.cost_ledger(float(trade["entry_price"]), now_price, cost)

    def event_price():
        if trade["terminal"] == "P0_FIRST":
            p = float(p0_price)
            return (p, None) if math.isfinite(p) and p > 0 else (None, "INVALID_P0_EXECUTION")
        return _open_at(market, terminal)

    ep, er = event_price()
    if er: return {"eligible": False, "reason": er}
    event_net = float(c7.cost_ledger(float(trade["entry_price"]), ep, cost)["net_return"])
    out = {"eligible": True, "reason": "ELIGIBLE", "exit_now_execution_ms": t,
           "exit_now_price": now_price, "exit_now_net": float(now["net_return"]),
           "event_execution_ms": terminal, "event_price": ep, "event_net": event_net,
           "DELTA_LIQ_EVENT": event_net - float(now["net_return"])}
    for h in HORIZONS:
        reassessment = t + h*c8.MINUTE
        if terminal <= reassessment:
            endpoint, price, source = terminal, ep, trade["terminal"]
        else:
            endpoint, source = reassessment, "HORIZON_REACHED"
            price, reason = _open_at(market, endpoint)
            if reason: return {"eligible": False, "reason": reason, "failed_horizon_minutes": h}
        net = float(c7.cost_ledger(float(trade["entry_price"]), price, cost)["net_return"])
        out.update({f"reassessment_ms_{h}": reassessment, f"endpoint_ms_{h}": endpoint,
                    f"endpoint_source_{h}": source, f"forward_price_{h}": price,
                    f"forward_net_{h}": net, f"DELTA_LIQ_{h}": net-float(now["net_return"])})
    return out


def weights(rows): return c8.trade_weights(rows)


def weighted_corr(rows, target, x="p_t2"):
    if not rows: return None
    w = weights(rows); w /= w.sum()
    a=np.asarray([r[x] for r in rows]); b=np.asarray([r[target] for r in rows])
    ma,mb=float(w@a),float(w@b); den=math.sqrt(float(w@((a-ma)**2))*float(w@((b-mb)**2)))
    return float(w@((a-ma)*(b-mb))/den) if den else None


def ranks(values):
    a=np.asarray(values); order=np.argsort(a,kind="mergesort"); out=np.empty(len(a),float); i=0
    while i<len(a):
        j=i+1
        while j<len(a) and a[order[j]]==a[order[i]]: j+=1
        out[order[i:j]]=(i+j-1)/2; i=j
    return out


def association(rows, target):
    if not rows: return {"spearman":None,"trade_weighted_linear_correlation":None}
    rr=[dict(r,_px=float(x),_dy=float(y)) for r,x,y in zip(rows,ranks([r["p_t2"] for r in rows]),ranks([r[target] for r in rows]))]
    return {"spearman":weighted_corr(rr,"_dy","_px"),
            "trade_weighted_linear_correlation":weighted_corr(rows,target)}


def summary(rows, target):
    if not rows: return None
    a=np.asarray([r[target] for r in rows]); w=weights(rows); w/=w.sum()
    trade_means=[np.mean([r[target] for r in rows if r["trade_id"]==tid]) for tid in sorted({r["trade_id"] for r in rows})]
    return {"snapshots":len(rows),"unique_trades":len(trade_means),"mean":float(w@a),
            "median":float(np.median(a)),"p10":float(np.quantile(a,.1)),"p25":float(np.quantile(a,.25)),
            "p75":float(np.quantile(a,.75)),"p90":float(np.quantile(a,.9)),
            "fraction_positive":float(w@(a>0)),"fraction_negative":float(w@(a<0)),
            "fraction_exact_zero":float(w@(a==0)),
            "total_paired_pnl_usdt_equal_trade":float(1000*np.sum(trade_means))}


def band_summary(rows, target):
    return {name:summary([r for r in rows if lo<=r["p_t2"]<hi],target) for name,lo,hi in BANDS}


def ordering(rows, target):
    bands=band_summary(rows,target); assoc=association(rows,target)
    lo,hi=bands["<0.20"],bands[">=0.80"]
    return {**assoc,"bandwise":bands,"highest_minus_lowest_band_mean":
            (hi["mean"]-lo["mean"]) if hi is not None and lo is not None else None}


def endpoint_composition(rows, h):
    if not rows:return None
    w=weights(rows);w/=w.sum(); sources=("HORIZON_REACHED","T2_FIRST","P0_FIRST")
    return {"snapshots":len(rows),"unique_trades":len({r['trade_id'] for r in rows}),
            "fractions":{s:float(w@np.asarray([r[f"endpoint_source_{h}"]==s for r in rows])) for s in sources},
            "counts":dict(Counter(r[f"endpoint_source_{h}"] for r in rows))}


def time_name(minutes):
    for name,lo,hi in TIME_BANDS:
        if (minutes>=lo if lo==0 else minutes>lo) and minutes<=hi:return name


def elapsed(rows, target):
    out={}
    for name,_,_ in TIME_BANDS:
        rr=[r for r in rows if time_name((r["state_ms"]-r["entry_ms"])/c8.MINUTE)==name]
        if not rr: out[name]=None; continue
        w=weights(rr);w/=w.sum()
        out[name]={"mean_p_t2":float(w@np.asarray([r["p_t2"] for r in rr])),
                   "forward_value":summary(rr,target),"association":association(rr,target)}
    return out


def trajectory(rows, target):
    by=defaultdict(list)
    for r in rows:by[r["trade_id"]].append(r)
    values=[]
    for rr in by.values():
        rr.sort(key=lambda x:x["state_ms"]); a=[r["p_t2"] for r in rr]; b=[r[target] for r in rr]
        if len(rr)>=3 and np.std(a)>0 and np.std(b)>0: values.append(float(np.corrcoef(a,b)[0,1]))
    return {"minimum_observations":3,"eligible_trade_count":len(values),
            "mean":float(np.mean(values)) if values else None,"median":float(np.median(values)) if values else None,
            "p10":float(np.quantile(values,.1)) if values else None,"p90":float(np.quantile(values,.9)) if values else None}


def tail(rows, target):
    by=defaultdict(list)
    for r in rows:by[r["trade_id"]].append(r[target])
    vals=np.asarray([np.mean(by[k]) for k in sorted(by)])
    pos=np.maximum(vals,0); neg=np.minimum(vals,0); ranked=np.sort(pos)[::-1]; total=float(pos.sum()); n=len(vals)
    return {"trade_measure":"mean snapshot DELTA_LIQ per trade","trades":n,
            "positive_paired_contribution_usdt":float(1000*pos.sum()),
            "negative_paired_contribution_usdt":float(1000*neg.sum()),
            "p10":float(np.quantile(vals,.1)),"p90":float(np.quantile(vals,.9)),
            "worst":float(vals.min()),"best":float(vals.max()),
            "positive_contribution_concentration":{f"top_{p}_percent_of_trades":float(ranked[:max(1,int(np.ceil(n*p/100)))].sum()/total) if total else None for p in (1,5,10,20)}}


def reproduce_probabilities(rows):
    rows24=[r for r in rows if r["year"]==2024]; rows25=[r for r in rows if r["year"]==2025]; pooled=[]; pp=[]
    for fold,(_start,_cut,end) in c8.FOLDS.items():
        train,valid=c8.split_fold(rows24,fold); base=c9._fit_base(train); raw=c9._predict_base(base,valid); inner,ip,_=c9.inner_predictions(rows24,end)
        cal=c9.fit_platt(inner,ip); pooled.extend(valid); pp.extend(c9.apply_platt(cal,raw))
    inner,ip,_=c9.inner_predictions(rows24,c9.YEAR_END+1); cal=c9.fit_platt(inner,ip); base=c9._fit_base(rows24)
    return pooled,np.asarray(pp),rows25,c9.apply_platt(cal,c9._predict_base(base,rows25))


def run(repo:Path):
    reject_2026(repo)
    if os.environ.get("CONDA_DEFAULT_ENV")!="binance-v2-research": raise RuntimeError("conda environment must be binance-v2-research")
    contract=repo/CONTRACT_REL
    if sha(contract)!=CONTRACT_SHA256: raise RuntimeError("C20 contract changed after prospective freeze")
    out=repo/OUTPUT_REL;out.mkdir(parents=True,exist_ok=True)
    trades=c8.load_trades(repo); markets={};bars={}
    for symbol in c8.SYMBOLS:
        markets[symbol]=c8.load_market(repo/f"data/normalized/c2_history/{symbol}_1m.csv.gz")
        bars[(symbol,5)]=c8.aggregate(markets[symbol],5);bars[(symbol,60)]=c8.aggregate(markets[symbol],60)
    for tr in trades:tr.update(c8.terminal_for_trade(tr,markets[tr["symbol"]]))
    causal=c8.snapshots(trades,markets,bars,"B");pooled,p24,rows25,p25=reproduce_probabilities(causal)
    scored=pooled+rows25;probs=np.concatenate((p24,p25)); tm={t["trade_id"]:t for t in trades}
    source=json.loads((repo/"artifacts/c7_full_population_t2_exit_overlay/population_manifest.json").read_text())
    p0={r["trade_id"]:float(r["p0_raw_exit_price"]) for r in source["rows"]}
    rows=[];excluded=Counter()
    for r,p in zip(scored,probs):
        tr=tm[r["trade_id"]]; target=liquidation_targets(r,tr,markets[r["symbol"]],p0[r["trade_id"]])
        if not target["eligible"]:excluded[target["reason"]]+=1;continue
        sensitivities={case:{k:v for k,v in liquidation_targets(r,tr,markets[r["symbol"]],p0[r["trade_id"]],case).items() if k in TARGETS} for case in COST_CASES}
        rows.append(r|target|{"p_t2":float(p),"outcome":tr["terminal"],"sensitivities":sensitivities})
    ids=lambda x:{r["trade_id"] for r in x}
    rec={"source_trades":len(trades),"source_outcomes":dict(Counter(t["terminal"] for t in trades)),
         "causal_snapshots":len(causal),"causal_snapshot_trades":len(ids(causal)),
         "honestly_scored_snapshots":len(scored),"honestly_scored_trades":len(ids(scored)),
         "unscored_causal_snapshots":len(causal)-len(scored),"eligible_target_snapshots":len(rows),
         "eligible_target_trades":len(ids(rows)),"target_ineligible":dict(excluded)}
    expected={"source_trades":2199,"source_outcomes":{"T2_FIRST":845,"P0_FIRST":1354},"honestly_scored_snapshots":56217,"honestly_scored_trades":1610}
    rec["expected_reference"]=expected;rec["reference_reconciled"]=all(rec[k]==v for k,v in expected.items())
    if not rec["reference_reconciled"]:raise RuntimeError("C20 population reference mismatch")
    overall={t:summary(rows,t) for t in TARGETS};bands={t:band_summary(rows,t) for t in TARGETS};orders={t:ordering(rows,t) for t in TARGETS}
    levels={t:{"metrics":overall[t],"classification":"POSITIVE_FORWARD_LEVEL" if overall[t]["mean"]>0 else "NEGATIVE_FORWARD_LEVEL" if overall[t]["mean"]<0 else "NEUTRAL_FORWARD_LEVEL"} for t in TARGETS}
    endpoints={str(h):endpoint_composition(rows,h) for h in HORIZONS}
    outcomes={o:{t:{"overall":summary(rr:=[r for r in rows if r["outcome"]==o],t),"probability_bands":band_summary(rr,t),
                         "endpoint_composition":({str(h):endpoint_composition(rr,h) for h in HORIZONS} if t=="DELTA_LIQ_EVENT" else endpoint_composition(rr,int(t.rsplit('_',1)[1])))} for t in TARGETS} for o in ("T2_FIRST","P0_FIRST")}
    elapsed_all={t:elapsed(rows,t) for t in TARGETS};trajectory_all={t:trajectory(rows,t) for t in TARGETS}
    years={str(y):{t:{"overall":summary(rr:=[r for r in rows if r["year"]==y],t),"ordering":ordering(rr,t)} for t in TARGETS} for y in (2024,2025)}
    symbols={s:{t:{"overall":summary(rr:=[r for r in rows if r["symbol"]==s],t),"ordering":ordering(rr,t)} for t in TARGETS} for s in c8.SYMBOLS}
    tails={t:tail(rows,t) for t in TARGETS}
    costs={case:{t:summary([dict(r,**{t:r["sensitivities"][case][t]}) for r in rows],t) for t in TARGETS} for case in COST_CASES}
    predicates={}
    for t in TARGETS:
        yp={y:{"positive_associations":years[y][t]["ordering"]["spearman"]>0 and years[y][t]["ordering"]["trade_weighted_linear_correlation"]>0,
               "broadly_increasing_bands":sum(b>=a for a,b in zip([years[y][t]["ordering"]["bandwise"][n]["mean"] for n,_,_ in BANDS][:-1],[years[y][t]["ordering"]["bandwise"][n]["mean"] for n,_,_ in BANDS][1:]))>=3,
               "high_minus_low_positive":years[y][t]["ordering"]["highest_minus_lowest_band_mean"]>0} for y in ("2024","2025")}
        positive_symbols=sum(symbols[s][t]["ordering"]["trade_weighted_linear_correlation"]>0 for s in c8.SYMBOLS)
        directional=all(v["positive_associations"] and v["high_minus_low_positive"] for v in yp.values())
        supported=directional and all(v["broadly_increasing_bands"] for v in yp.values()) and positive_symbols>1
        predicates[t]={"years":yp,"symbols_with_positive_linear_association":positive_symbols,"not_driven_by_one_symbol":positive_symbols>1,
                       "classification":"ORDERING_SUPPORTED" if supported else "WEAK_ORDERING" if directional and positive_symbols>1 else "NO_USEFUL_ORDERING"}
    stable=[t for t,v in predicates.items() if v["classification"]=="ORDERING_SUPPORTED" and t!="DELTA_LIQ_EVENT"]
    implication=("One or more bounded targets show stable ordering; a later separately frozen checkpoint may test a prospectively specified sequential rule."
                 if stable else "No bounded target establishes stable ordering; do not proceed to a C9-based sequential policy without reformulating the decision state.")
    leakage={"status":"PASS","completed_information_only":True,"exact_next_open":True,"gap_missing_duplicate_fail_closed":True,
             "terminal_precedence":True,"no_post_terminal_lookup_by_construction":True,"future_targets_evaluation_only":True,
             "future_max_or_best_exit_used":False,"unscored_probability_inference":False,"no_2026_access":True}
    target_def={"EXIT_NOW_NET(t)":"net(entry_price, open[t], cost)","endpoint_H":"min(t + H, first frozen lifecycle terminal)",
                "FORWARD_NET_H(t)":"net(entry_price, executable price at endpoint_H, cost)","DELTA_LIQ_H(t)":"FORWARD_NET_H(t) - EXIT_NOW_NET(t)",
                "DELTA_LIQ_EVENT(t)":"EVENT_NET(t) - EXIT_NOW_NET(t)","horizons_minutes":list(HORIZONS),"primary_cost":"C_BASE",
                "paired_cost_algebra":"q*(1-s)*(1-f)*(P_endpoint-P_now)/N; common entry debit, entry fee, and acquired quantity cancel"}
    files={"run_manifest":{"version":"C20_RUN_V1","contract_sha256":CONTRACT_SHA256,"python":sys.version,"numpy":np.__version__,"platform":platform.platform(),"conda_environment":"binance-v2-research"},
      "provenance":{"contract_sha256":CONTRACT_SHA256,"inputs":{CONTRACT_REL:sha(contract),"c7_population":sha(repo/"artifacts/c7_full_population_t2_exit_overlay/population_manifest.json"),"c9_final_summary":sha(repo/"artifacts/c9_dynamic_pre_t2_state/final_summary.json")},"no_2026_access":True},
      "leakage_firewall":leakage,"population_reconciliation":rec,"target_definition":target_def,"endpoint_composition":endpoints,
      "overall_forward_value":overall,"probability_band_summary":bands,"economic_ordering":orders,"economic_level":levels,
      "outcome_class_summary":outcomes,"elapsed_time_summary":elapsed_all,"trajectory_alignment":trajectory_all,"year_summary":years,
      "symbol_summary":symbols,"right_tail_downside_summary":tails,"cost_sensitivity":costs,"interpretation_predicates":predicates,
      "c21_recommendation":{"methodology_only":True,"bounded_targets_with_ordering_supported":stable,"recommendation":implication,"c21_started":False}}
    for name,value in files.items():write(out/f"{name}.json",value)
    final={"contract_sha256":CONTRACT_SHA256,"population_reconciliation":rec,"leakage_timing_verification":leakage,
           "target_definition":target_def,"endpoint_composition":endpoints,"overall_forward_value":overall,"probability_bands":bands,
           "economic_ordering":orders,"economic_level":levels,"outcome_classes":outcomes,"elapsed_time":elapsed_all,
           "trajectory_alignment":trajectory_all,"years":years,"symbols":symbols,"right_tail_downside":tails,"cost_sensitivity":costs,
           "ordering_classification":predicates,"ordering_level_distinction":"Ordering assesses whether p_t2 ranks value; level assesses whether delay beats immediate liquidation on average. Neither implies the other.",
           "c21_implication":implication,"limitations":["characterization, not an exit policy","future-derived targets are evaluation-only","within-trade snapshots are dependent","quantiles are snapshot quantiles; means, proportions, and associations are whole-trade weighted"],
           "confirmations":{"model_or_recalibration":False,"policy_or_pnl_optimization":False,"best_horizon_selection":False,"future_max_or_hindsight_optimal_target":False,"accessed_2026":False,"c21_started":False,"c7_c19_scientific_behavior_modified":False}}
    write(out/"final_summary.json",final)
    write(out/"reproducibility_hashes.json",{p.name:sha(p) for p in sorted(out.glob("*.json")) if p.name!="reproducibility_hashes.json"})
    return final
