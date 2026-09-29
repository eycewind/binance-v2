"""C24 frozen probability-to-economic-value ordering audit."""
from __future__ import annotations

import hashlib, json, os, platform, sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from . import c8_timescale as c8
from . import c20_forward_liquidation_value as c20
from . import c21_between_within_covariance as c21
from . import c22_causal_decision_state as c22
from . import c23_incremental_c9_ablation as c23

CONTRACT_SHA256 = "59ff709a0cbbc0847a5f67ea5cb87abaaabbd262e58bc750767871953d20693e"
CONTRACT_REL = "contracts/C24_probability_economic_ordering_CONTRACT.md"
OUTPUT_REL = "artifacts/c24_probability_economic_ordering"
SEED = 20240924
REPLICATES = 2000


def reject_2026(path) -> None:
    if any("2026" in part for part in os.fspath(path).replace("\\", "/").lower().split("/")):
        raise PermissionError("C24 prohibits 2026 data or metadata access")


def sha(path: Path) -> str:
    reject_2026(path)
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n")


def weights(rows: list[dict]) -> np.ndarray:
    counts = defaultdict(int)
    for row in rows: counts[row["trade_id"]] += 1
    return np.asarray([1.0 / counts[row["trade_id"]] for row in rows])


def weighted_quantile(values, sample_weights, q: float) -> float:
    """Inverse weighted empirical CDF; ties are never split."""
    x, w = np.asarray(values, float), np.asarray(sample_weights, float)
    if len(x) == 0 or not 0 <= q <= 1 or np.any(w < 0) or not w.sum() > 0:
        raise ValueError("invalid weighted quantile input")
    order = np.argsort(x, kind="stable"); x, w = x[order], w[order]
    return float(x[min(int(np.searchsorted(np.cumsum(w), q*w.sum(), side="left")), len(x)-1)])


def bin_boundaries(training_probabilities, training_rows) -> dict:
    p, w = np.asarray(training_probabilities, float), weights(training_rows)
    cuts = [weighted_quantile(p, w, q) for q in (.2, .4, .6, .8)]
    bins = assign_bins(p, cuts)
    return {"cut_values": cuts, "assignment": "searchsorted(cut_values, p, side=left); identical values remain together",
        "training_only": True, "duplicate_values_never_split": True,
        "training_weighted_mass": {f"Q{i+1}": float(w[bins == i].sum()) for i in range(5)},
        "training_total_weight": float(w.sum())}


def assign_bins(probabilities, cuts) -> np.ndarray:
    return np.searchsorted(np.asarray(cuts, float), np.asarray(probabilities, float), side="left")


def weighted_mean(x, w) -> float:
    return float(np.average(np.asarray(x, float), weights=np.asarray(w, float)))


def weighted_ranks(x, w) -> np.ndarray:
    """Weighted mid-distribution ranks, with one rank for every tied value."""
    x, w = np.asarray(x, float), np.asarray(w, float)
    _, inverse = np.unique(x, return_inverse=True)
    mass = np.bincount(inverse, weights=w)
    midpoint = np.cumsum(mass) - mass/2
    return midpoint[inverse] / mass.sum()


def weighted_correlation(x, y, w) -> float:
    x, y, w = np.asarray(x, float), np.asarray(y, float), np.asarray(w, float)
    mx, my = np.average(x, weights=w), np.average(y, weights=w)
    cov = np.average((x-mx)*(y-my), weights=w)
    den = np.sqrt(np.average((x-mx)**2, weights=w)*np.average((y-my)**2, weights=w))
    return float(cov/den) if den > 0 else 0.0


def associations(probabilities, values, w) -> dict:
    return {"weighted_spearman": weighted_correlation(weighted_ranks(probabilities, w), weighted_ranks(values, w), w),
        "weighted_linear_correlation": weighted_correlation(probabilities, values, w)}


def bin_summaries(rows, target, probabilities, cuts) -> dict:
    p, y, w = np.asarray(probabilities, float), np.asarray([r[target] for r in rows], float), weights(rows)
    b = assign_bins(p, cuts); result = {}
    for j in range(5):
        take = b == j; xx, pp, ww = y[take], p[take], w[take]
        pos, neg = xx > 0, xx < 0
        def q(v): return weighted_quantile(xx, ww, v) if len(xx) else None
        lo = None if j == 0 else float(cuts[j-1]); hi = None if j == 4 else float(cuts[j])
        pc = float(np.sum(ww[pos]*xx[pos])); nc = float(np.sum(ww[neg]*xx[neg]))
        result[f"Q{j+1}"] = {"probability_boundary":{"lower_exclusive":lo,"upper_inclusive":hi},
            "weighted_mean_predicted_probability":weighted_mean(pp,ww),
            "weighted_median_predicted_probability":weighted_quantile(pp,ww,.5),
            "weighted_observed_positive_rate":weighted_mean(xx > 0,ww),
            "weighted_mean_delta_liq":weighted_mean(xx,ww), "weighted_median_delta_liq":q(.5),
            "weighted_p10_delta_liq":q(.1),"weighted_p25_delta_liq":q(.25),
            "weighted_p75_delta_liq":q(.75),"weighted_p90_delta_liq":q(.9),
            "weighted_mean_positive_delta_liq":weighted_mean(xx[pos],ww[pos]) if pos.any() else None,
            "weighted_mean_negative_delta_liq":weighted_mean(xx[neg],ww[neg]) if neg.any() else None,
            "positive_contribution":pc,"negative_contribution":nc,"net_contribution":pc+nc,
            "positive_to_absolute_negative_contribution_ratio":pc/abs(nc) if nc else None,
            "snapshot_count":int(take.sum()),"trade_count":len({rows[i]["trade_id"] for i in np.flatnonzero(take)}),
            "effective_whole_trade_weight":float(ww.sum())}
    return result


def ordering(rows, target, probabilities, summaries) -> dict:
    w = weights(rows); y = np.asarray([r[target] for r in rows], float)
    mean = [summaries[f"Q{i}"]["weighted_mean_delta_liq"] for i in range(1,6)]
    med = [summaries[f"Q{i}"]["weighted_median_delta_liq"] for i in range(1,6)]
    rate = [summaries[f"Q{i}"]["weighted_observed_positive_rate"] for i in range(1,6)]
    return associations(probabilities,y,w) | {"positive_rate_nondecreasing":all(a<=b for a,b in zip(rate,rate[1:])),
        "mean_delta_liq_nondecreasing":all(a<=b for a,b in zip(mean,mean[1:])),
        "median_delta_liq_nondecreasing":all(a<=b for a,b in zip(med,med[1:])),
        "Delta_mean_Q5_Q1":mean[4]-mean[0],"Delta_positive_rate_Q5_Q1":rate[4]-rate[0],
        "Delta_median_Q5_Q1":med[4]-med[0]}


def bootstrap(rows, target, probabilities, cuts, unit, seed=SEED, replicates=REPLICATES) -> dict:
    by_trade = defaultdict(list)
    for i,r in enumerate(rows): by_trade[r["trade_id"]].append(i)
    tids = sorted(by_trade); months = defaultdict(list)
    for tid in tids:
        r=rows[by_trade[tid][0]]; months[datetime.fromtimestamp(int(r["entry_ms"])/1000,timezone.utc).strftime("%Y-%m")].append(tid)
    labels = sorted(months) if unit == "calendar_month" else tids
    rng=np.random.Generator(np.random.PCG64(seed)); samples=[]
    rejected_empty_endpoint_draws=0
    for _ in range(replicates):
        while True:
            selected=[]
            for j in rng.integers(len(labels),size=len(labels)):
                label=labels[int(j)]; selected.extend(months[label] if unit=="calendar_month" else [label])
            # Each selected trade occurrence has total weight one, even when sampled repeatedly.
            ix=[]; ww=[]
            for tid in selected:
                group=by_trade[tid]; ix.extend(group); ww.extend([1/len(group)]*len(group))
            ix=np.asarray(ix,int); ww=np.asarray(ww,float); p=np.asarray(probabilities)[ix]
            y=np.asarray([rows[i][target] for i in ix]); b=assign_bins(p,cuts)
            if np.any(b==0) and np.any(b==4): break
            rejected_empty_endpoint_draws += 1
        def bm(j, value): return weighted_mean(value[b==j],ww[b==j])
        assoc=associations(p,y,ww)
        samples.append([assoc["weighted_spearman"],assoc["weighted_linear_correlation"],
            bm(4,y)-bm(0,y),bm(4,y>0)-bm(0,y>0),
            weighted_quantile(y[b==4],ww[b==4],.5)-weighted_quantile(y[b==0],ww[b==0],.5)])
    arr=np.asarray(samples); names=("weighted_spearman","weighted_linear_correlation","Delta_mean_Q5_Q1","Delta_positive_rate_Q5_Q1","Delta_median_Q5_Q1")
    return {"unit":unit,"construction":"paired UTC entry-calendar-month blocks; whole trades and all symbols retained" if unit=="calendar_month" else "paired whole trades with all snapshots retained",
        "predictions_and_outcomes_frozen":True,"models_refit_inside_replicates":False,"seed":seed,"generator":"PCG64","replicates":replicates,
        "rejected_empty_Q1_or_Q5_draws":rejected_empty_endpoint_draws,
        "calendar_months":labels if unit=="calendar_month" else None,"intervals":{n:{"ci95":np.quantile(arr[:,j],[.025,.975],method="linear").tolist(),"replicate_sha256":hashlib.sha256(arr[:,j].astype("<f8").tobytes()).hexdigest()} for j,n in enumerate(names)}}


def concentration(rows,target) -> dict:
    y=np.asarray([r[target] for r in rows],float); w=weights(rows); take=y>0; y,w=y[take],w[take]
    order=np.argsort(-y,kind="stable"); y,w=y[order],w[order]; total=float(np.sum(y*w)); mass=float(w.sum())
    out={}
    for pct in (1,5,10,20):
        limit=mass*pct/100; used=0.; contribution=0.
        for value,weight in zip(y,w):
            portion=min(weight,max(0.,limit-used)); contribution += value*portion; used += portion
            if used >= limit: break
        out[f"top_{pct}pct_positive_rows_share"] = contribution/total if total else None
    return out | {"definition":"descending positive DELTA_LIQ; percentages use whole-trade weighted positive-row mass; boundary weight fractionalized"}


def _prediction_sha(values) -> str:
    return hashlib.sha256(np.asarray(values,dtype="<f8").tobytes()).hexdigest()


def run(repo: Path) -> dict:
    repo=repo.resolve(); reject_2026(repo)
    if os.environ.get("CONDA_DEFAULT_ENV") != "binance-v2-research": raise RuntimeError("conda environment must be binance-v2-research")
    if sha(repo/CONTRACT_REL) != CONTRACT_SHA256: raise RuntimeError("C24 contract changed after prospective freeze")
    out=repo/OUTPUT_REL; out.mkdir(parents=True,exist_ok=True)
    rows,info=c22.build_causal_rows(repo); reproduction=c21.reproduce_c20(repo,rows,info)
    population=info|{"expected_scored_snapshots":56217,"expected_scored_trades":1610,"actual_scored_snapshots":len(rows),"actual_scored_trades":len({r['trade_id'] for r in rows})}
    population["exact_reconciliation"]=reproduction["status"]=="PASS" and (len(rows),population["actual_scored_trades"])==(56217,1610)
    if not population["exact_reconciliation"]: raise RuntimeError("frozen population mismatch")
    rows24=[r for r in rows if r["year"]==2024]; rows25=[r for r in rows if r["year"]==2025]; train24,valid24=c8.split_fold(rows24,"fold_B")
    if (len(train24),len({r['trade_id'] for r in train24}),len(valid24),len({r['trade_id'] for r in valid24}),len(rows25),len({r['trade_id'] for r in rows25})) != (7970,256,8631,267,39616,1087): raise RuntimeError("C23 evaluation population mismatch")
    datasets={"2024":(train24,valid24),"2025":(rows24,rows25)}; predictions={}; boundaries={}; summaries={}; economics={}; tails={}; conc={}; month={}; trade={}; symbols={}; reconcile={}
    c23_metrics={y:json.loads((repo/c23.OUTPUT_REL/f"binary_metrics_{y}.json").read_text()) for y in datasets}
    for year,(training,valid) in datasets.items():
        predictions[year]={};boundaries[year]={};summaries[year]={};economics[year]={};tails[year]={};conc[year]={};month[year]={};trade[year]={};reconcile[year]={}
        for target in c20.TARGETS:
            train_pred,_=c23.fit_candidates(training,training,target); valid_pred,_=c23.fit_candidates(training,valid,target)
            pt=train_pred["S+C9"]["binary"]; pv=valid_pred["S+C9"]["binary"]; predictions[year][target]=(pt,pv)
            reproduced=c22.binary_metrics(valid,target,pv)
            match=all(abs(reproduced[k]-c23_metrics[year][target]["S+C9"][k])<1e-14 for k in ("brier","log_loss","auc")) and abs(reproduced["prevalence"]-c23_metrics[year][target]["S+C9"]["prevalence"])<1e-14
            if not match: raise RuntimeError("frozen C23 probability reproduction failed")
            reconcile[year][target]={"training_prediction_sha256":_prediction_sha(pt),"validation_prediction_sha256":_prediction_sha(pv),"published_metric_reconciliation":True,"refit_reason":"C23 row-level predictions were not stored; exact frozen C23 procedure reproduced","model":"S+C9 L2 logistic C=1.0","recalibrated":False}
            bd=bin_boundaries(pt,training); boundaries[year][target]=bd; sm=bin_summaries(valid,target,pv,bd["cut_values"]); summaries[year][target]=sm
            economics[year][target]=ordering(valid,target,pv,sm); tails[year][target]={q:{k:v for k,v in cell.items() if k in ("weighted_mean_positive_delta_liq","weighted_mean_negative_delta_liq","positive_contribution","negative_contribution","net_contribution","positive_to_absolute_negative_contribution_ratio")} for q,cell in sm.items()}
            conc[year][target]=concentration(valid,target); month[year][target]=bootstrap(valid,target,pv,bd["cut_values"],"calendar_month"); trade[year][target]=bootstrap(valid,target,pv,bd["cut_values"],"whole_trade")
    for symbol in c8.SYMBOLS:
        symbols[symbol]={}
        for year,(_,valid) in datasets.items():
            symbols[symbol][year]={}
            for target in c20.TARGETS:
                pv=predictions[year][target][1]; ix=np.asarray([i for i,r in enumerate(valid) if r["symbol"]==symbol]); cell=[valid[i] for i in ix]; sm=bin_summaries(cell,target,pv[ix],boundaries[year][target]["cut_values"]); eco=ordering(cell,target,pv[ix],sm)
                symbols[symbol][year][target]={"positive_rate_by_bin":{q:x["weighted_observed_positive_rate"] for q,x in sm.items()},"mean_delta_liq_by_bin":{q:x["weighted_mean_delta_liq"] for q,x in sm.items()},"weighted_spearman":eco["weighted_spearman"],"Delta_mean_Q5_Q1":eco["Delta_mean_Q5_Q1"]}
    classes={}
    for target in c20.TARGETS:
        point=all(economics[y][target][k]>0 for y in datasets for k in ("weighted_spearman","Delta_mean_Q5_Q1","Delta_positive_rate_Q5_Q1"))
        reversed_both=any(all(s[y][target]["intervals"]["Delta_mean_Q5_Q1"]["ci95"][1]<0 for y in datasets) for s in (month,trade))
        symbol_counts={y:sum(symbols[s][y][target]["Delta_mean_Q5_Q1"]>0 for s in c8.SYMBOLS) for y in datasets}; broad=min(symbol_counts.values())>1
        tail_ok=all(tails[y][target]["Q5"]["net_contribution"] >= tails[y][target]["Q1"]["net_contribution"] for y in datasets)
        supported=point and not reversed_both and broad and tail_ok
        classification="ECONOMIC_ORDERING_SUPPORTED" if supported else "WEAK_ECONOMIC_ORDERING" if point else "NO_USEFUL_ECONOMIC_ORDERING"
        classes[target]={"classification":classification,"positive_required_point_estimates_both_years":point,"uncertainty_no_clear_reversal_both_years":not reversed_both,"positive_symbol_spreads_by_year":symbol_counts,"not_obviously_one_symbol":broad,"q5_net_not_worse_than_q1_both_years":tail_ok}
    label={"rule":"Y_H = 1 iff DELTA_LIQ_H > 0; Y_H = 0 iff DELTA_LIQ_H <= 0","exact_zero":0,"exact_zero_retained":True,"continuous_value":"V_H = DELTA_LIQ_H; no transformation"}
    bindef={"count":5,"labels":["Q1","Q2","Q3","Q4","Q5"],"source":"corresponding training S+C9 predictions only","weights":"1/n_i per eligible snapshot in trade i","quantiles":[.2,.4,.6,.8],"duplicate_rule":"inverse weighted empirical CDF cuts and left assignment; identical predictions never split","validation_boundaries_frozen":True,"threshold_or_bin_search":False}
    provenance={"contract_sha256":CONTRACT_SHA256,"C20_reproduction":reproduction,"C23_source_sha256":sha(repo/"src/binance_data_foundation/c23_incremental_c9_ablation.py"),"C23_artifact_hashes_sha256":sha(repo/c23.OUTPUT_REL/"reproducibility_hashes.json"),"prediction_source":"exact reproduction of frozen target-specific C23 S+C9 logistic predictions","no_recalibration":True,"no_2026_access":True}
    manifest={"version":"C24_RUN_V1","contract_sha256":CONTRACT_SHA256,"seed":SEED,"replicates":REPLICATES,"generator":"PCG64","python":sys.version,"numpy":np.__version__,"platform":platform.platform(),"conda_environment":"binance-v2-research"}
    files={"run_manifest":manifest,"provenance":provenance,"population_reconciliation":population,"frozen_prediction_reconciliation":reconcile,"binary_label_definition":label,"bin_definition":bindef,"bin_boundaries_2024":boundaries["2024"],"bin_boundaries_2025":boundaries["2025"],"bin_summaries_2024":summaries["2024"],"bin_summaries_2025":summaries["2025"],"economic_ordering_2024":economics["2024"],"economic_ordering_2025":economics["2025"],"tail_asymmetry_2024":tails["2024"],"tail_asymmetry_2025":tails["2025"],"concentration_2024":conc["2024"],"concentration_2025":conc["2025"],"calendar_month_bootstrap":month,"whole_trade_bootstrap":trade,"symbol_stability":symbols,"interpretation_predicates":classes}
    for name,value in files.items(): write(out/f"{name}.json",value)
    final={"contract_sha256":CONTRACT_SHA256,"population_reconciliation":population,"frozen_prediction_provenance":provenance,"binary_label_definition":label,"bin_definition":bindef,"bin_boundaries":boundaries,"bin_summaries":summaries,"economic_ordering":economics,"tail_asymmetry":tails,"concentration":conc,"calendar_month_uncertainty":month,"whole_trade_uncertainty":trade,"symbol_stability":symbols,"frozen_classification":classes,"interpretation":"C24 describes whether frozen S+C9 probabilities order executable forward value; positive-rate ordering and value-magnitude ordering are reported separately and do not define a policy.","limitations":["2024 has one honest chronological validation block","repeated snapshots are dependent; intervals use month and whole-trade clusters","five symbols are not independent replications","tail outcomes can separate probability ordering from economic magnitude ordering"],"implication_for_C25":"None selected: C24 stops without horizon selection or starting C25.","confirmations":{"model_training":"only exact reproduction strictly required because C23 row-level predictions were not stored","probability_recalibration":False,"threshold_or_bin_search":False,"horizon_selection":False,"policy_or_pnl_optimization":False,"accessed_2026":False,"C25_started":False,"staged_committed_or_pushed":False}}
    write(out/"final_summary.json",final); write(out/"reproducibility_hashes.json",{p.name:sha(p) for p in sorted(out.glob("*.json")) if p.name!="reproducibility_hashes.json"})
    return final
