"""C21 between-trade / within-trade covariance decomposition."""
from __future__ import annotations

import hashlib, json, math, os, platform, sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from . import c8_timescale as c8
from . import c20_forward_liquidation_value as c20

CONTRACT_SHA256 = "ba6158c4f3c58509cc67156833403b78db6d4e1dd53f5e33443197aa4323da98"
CONTRACT_REL = "contracts/C21_between_within_covariance_CONTRACT.md"
OUTPUT_REL = "artifacts/c21_between_within_covariance"
SEED = 20240923
REPLICATES = 2000
TOLERANCE = 1e-15
ADJUSTMENT_FIELDS = ("elapsed_minutes", "current_return_from_entry")


def reject_2026(path):
    if any("2026" in p for p in os.fspath(path).replace("\\", "/").lower().split("/")):
        raise PermissionError("C21 prohibits 2026 data or metadata access")


def sha(path: Path) -> str:
    reject_2026(path)
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""): h.update(block)
    return h.hexdigest()


def write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n")


def build_frozen_rows(repo: Path) -> tuple[list[dict], dict]:
    """Re-run C20's frozen population/probability/target construction unchanged."""
    reject_2026(repo)
    trades = c8.load_trades(repo); markets = {}; bars = {}
    for symbol in c8.SYMBOLS:
        markets[symbol] = c8.load_market(repo / f"data/normalized/c2_history/{symbol}_1m.csv.gz")
        bars[(symbol, 5)] = c8.aggregate(markets[symbol], 5)
        bars[(symbol, 60)] = c8.aggregate(markets[symbol], 60)
    for tr in trades: tr.update(c8.terminal_for_trade(tr, markets[tr["symbol"]]))
    causal = c8.snapshots(trades, markets, bars, "B")
    pooled, p24, rows25, p25 = c20.reproduce_probabilities(causal)
    scored = pooled + rows25; probs = np.concatenate((p24, p25)); tm = {t["trade_id"]: t for t in trades}
    source = json.loads((repo / "artifacts/c7_full_population_t2_exit_overlay/population_manifest.json").read_text())
    p0 = {r["trade_id"]: float(r["p0_raw_exit_price"]) for r in source["rows"]}
    rows = []; excluded = Counter()
    for r, p in zip(scored, probs):
        tr = tm[r["trade_id"]]
        target = c20.liquidation_targets(r, tr, markets[r["symbol"]], p0[r["trade_id"]])
        if not target["eligible"]:
            excluded[target["reason"]] += 1; continue
        rows.append(r | target | {"p_t2": float(p), "outcome": tr["terminal"],
                    "entry_price": float(tr["entry_price"]),
                    "elapsed_minutes": (int(r["state_ms"])-int(r["entry_ms"]))/c8.MINUTE,
                    "current_return_from_entry": float(target["exit_now_price"])/float(tr["entry_price"])-1.0})
    info = {"source_trades": len(trades), "causal_snapshots": len(causal),
            "honestly_scored_snapshots": len(scored), "honestly_scored_trades": len({r['trade_id'] for r in scored}),
            "eligible_target_snapshots": len(rows), "eligible_target_trades": len({r['trade_id'] for r in rows}),
            "target_ineligible": dict(excluded)}
    return rows, info


def trade_statistics(rows: list[dict], target: str) -> list[dict]:
    by = defaultdict(list)
    for r in rows: by[r["trade_id"]].append(r)
    out = []
    for tid in sorted(by):
        rr = by[tid]; p = np.asarray([r["p_t2"] for r in rr], float); v = np.asarray([r[target] for r in rr], float)
        mp, mv = float(p.mean()), float(v.mean())
        out.append({"trade_id": tid, "year": int(rr[0]["year"]), "symbol": rr[0]["symbol"],
                    "entry_ms": int(rr[0]["entry_ms"]), "snapshots": len(rr), "mean_p": mp, "mean_v": mv,
                    "within_covariance": float(np.mean((p-mp)*(v-mv))),
                    "within_correlation": (float(np.corrcoef(p, v)[0, 1]) if len(rr) >= 3 and np.std(p) > 0 and np.std(v) > 0 else None)})
    return out


def _corr(a: np.ndarray, b: np.ndarray) -> float | None:
    if len(a) < 2 or np.std(a) == 0 or np.std(b) == 0: return None
    return float(np.corrcoef(a, b)[0, 1])


def decomposition(rows: list[dict], target: str) -> dict:
    stats = trade_statistics(rows, target)
    a = np.asarray([x["mean_p"] for x in stats]); b = np.asarray([x["mean_v"] for x in stats])
    within = float(np.mean([x["within_covariance"] for x in stats]))
    between = float(np.mean((a-a.mean())*(b-b.mean())))
    p = np.asarray([r["p_t2"] for r in rows]); v = np.asarray([r[target] for r in rows]); w = c20.weights(rows); w /= w.sum()
    total = float(w @ ((p-float(w@p))*(v-float(w@v))))
    residual = total-between-within
    wc = np.asarray([x["within_correlation"] for x in stats if x["within_correlation"] is not None])
    opposing = between * within < 0
    shares = ({"between_share_of_total": between/total, "within_share_of_total": within/total}
              if abs(total) > TOLERANCE and not opposing else
              {"between_share_of_total": None, "within_share_of_total": None,
               "share_note": "not forced because total is near zero or component signs oppose"})
    if total > TOLERANCE and between > 0 and within < 0 and between > abs(within): label = "BETWEEN_DOMINANT_POSITIVE"
    elif between*within > 0: label = "SAME_SIGN_COMPONENTS"
    elif abs(within) > abs(between) and abs(total) > TOLERANCE: label = "WITHIN_DOMINANT"
    else: label = "MIXED_OR_NEAR_ZERO"
    return {"snapshots": len(rows), "trades": len(stats), "total_covariance": total,
            "between_trade_covariance": between, "within_trade_covariance_component": within,
            "reconstruction_residual": residual, **shares, "classification": label,
            "pooled_correlation": c20.weighted_corr(rows, target), "trade_mean_correlation": _corr(a, b),
            "within_trade_correlations": {"eligible_trades": len(wc), "mean": float(wc.mean()) if len(wc) else None,
                "median": float(np.median(wc)) if len(wc) else None, "p10": float(np.quantile(wc, .1)) if len(wc) else None,
                "p90": float(np.quantile(wc, .9)) if len(wc) else None}}


def _components_from_indices(stats: list[dict], indices: np.ndarray) -> tuple[float, float, float]:
    a=np.asarray([stats[i]["mean_p"] for i in indices]); b=np.asarray([stats[i]["mean_v"] for i in indices])
    within=float(np.mean([stats[i]["within_covariance"] for i in indices]))
    between=float(np.mean((a-a.mean())*(b-b.mean())))
    return between+within, between, within


def bootstrap(rows: list[dict], target: str, calendar_month: bool = False) -> dict:
    stats=trade_statistics(rows,target); rng=np.random.Generator(np.random.PCG64(SEED)); reps=[]
    if calendar_month:
        groups=defaultdict(list)
        for i,s in enumerate(stats): groups[datetime.fromtimestamp(s["entry_ms"]/1000,timezone.utc).strftime("%Y-%m")].append(i)
        labels=sorted(groups); construction="whole_utc_calendar_month_trade_clusters_with_replacement"
        for _ in range(REPLICATES):
            picked=rng.integers(len(labels),size=len(labels)); ix=np.asarray([i for j in picked for i in groups[labels[int(j)]]],int)
            reps.append(_components_from_indices(stats,ix))
    else:
        construction="whole_trades_with_replacement"
        for _ in range(REPLICATES): reps.append(_components_from_indices(stats,rng.integers(len(stats),size=len(stats))))
        labels=[]
    a=np.asarray(reps); point=decomposition(rows,target)
    keys=("total_covariance","between_trade_covariance","within_trade_covariance_component")
    return {"unit":"calendar_month_cluster_of_whole_trades" if calendar_month else "whole_trade",
            "construction":construction,"seed":SEED,"generator":"PCG64","replicates":REPLICATES,
            "quantile_method":"linear_type_7","calendar_months":labels or None,
            "components":{k:{"point_estimate":point[k],"ci95":np.quantile(a[:,j],[.025,.975],method="linear").tolist()} for j,k in enumerate(keys)}}


def causal_adjustment(rows: list[dict], target: str) -> dict:
    """Within-trade fixed-effect OLS and Frisch-Waugh residual covariance."""
    by=defaultdict(list)
    for i,r in enumerate(rows): by[r["trade_id"]].append(i)
    names=("p_t2", target)+ADJUSTMENT_FIELDS; centered={n:np.empty(len(rows)) for n in names}
    for ix in by.values():
        for n in names:
            x=np.asarray([rows[i][n] for i in ix],float); centered[n][ix]=x-x.mean()
    weights=c20.weights(rows); weights/=weights.sum(); p=centered["p_t2"]; v=centered[target]
    controls=np.column_stack([centered[n] for n in ADJUSTMENT_FIELDS]); sw=np.sqrt(weights)
    rp=p-controls@np.linalg.lstsq(controls*sw[:,None],p*sw,rcond=None)[0]
    rv=v-controls@np.linalg.lstsq(controls*sw[:,None],v*sw,rcond=None)[0]
    adjusted_cov=float(weights@(rp*rv)); unadjusted=float(weights@(p*v))
    design=np.column_stack((p,controls)); coef=np.linalg.lstsq(design*sw[:,None],v*sw,rcond=None)[0]
    change=(adjusted_cov-unadjusted); ratio=(adjusted_cov/unadjusted if abs(unadjusted)>TOLERANCE else None)
    sign_change=bool(np.sign(adjusted_cov)!=np.sign(unadjusted))
    material=sign_change or (ratio is not None and abs(abs(ratio)-1)>=.25)
    return {"unadjusted_within_trade_covariance":unadjusted,"adjusted_residual_covariance":adjusted_cov,
            "adjusted_p_t2_coefficient":float(coef[0]),"absolute_covariance_change":change,
            "adjusted_to_unadjusted_magnitude_ratio":abs(ratio) if ratio is not None else None,
            "sign_change":sign_change,"descriptive_material_change":material,
            "materiality_rule":"sign change or >=25% change in residual-covariance magnitude; descriptive implementation rule, not a predictive gate"}


def _max_difference(a, b) -> float:
    if isinstance(a,dict) and isinstance(b,dict): return max((_max_difference(a[k],b[k]) for k in a),default=0.0) if a.keys()==b.keys() else math.inf
    if isinstance(a,list) and isinstance(b,list): return max((_max_difference(x,y) for x,y in zip(a,b)),default=0.0) if len(a)==len(b) else math.inf
    if isinstance(a,(int,float)) and isinstance(b,(int,float)): return abs(float(a)-float(b))
    return 0.0 if a==b else math.inf


def reproduce_c20(repo: Path, rows: list[dict], info: dict) -> dict:
    frozen=lambda n:json.loads((repo/"artifacts/c20_forward_liquidation_value"/n).read_text())
    overall={t:c20.summary(rows,t) for t in c20.TARGETS}; ordering={t:c20.ordering(rows,t) for t in c20.TARGETS}
    years={str(y):{t:{"overall":c20.summary(rr:=[r for r in rows if r["year"]==y],t),"ordering":c20.ordering(rr,t)} for t in c20.TARGETS} for y in (2024,2025)}
    symbols={s:{t:{"overall":c20.summary(rr:=[r for r in rows if r["symbol"]==s],t),"ordering":c20.ordering(rr,t)} for t in c20.TARGETS} for s in c8.SYMBOLS}
    checks={"overall_forward_value":_max_difference(overall,frozen("overall_forward_value.json")),
            "economic_ordering":_max_difference(ordering,frozen("economic_ordering.json")),
            "year_summary":_max_difference(years,frozen("year_summary.json")),
            "symbol_summary":_max_difference(symbols,frozen("symbol_summary.json"))}
    pop=frozen("population_reconciliation.json")
    population_match=all(info[k]==pop[k] for k in ("source_trades","causal_snapshots","honestly_scored_snapshots","honestly_scored_trades","eligible_target_snapshots","eligible_target_trades","target_ineligible"))
    panel=[{k:r[k] for k in ("trade_id","symbol","year","entry_ms","state_ms","p_t2",*c20.TARGETS)} for r in rows]
    payload=json.dumps(panel,sort_keys=True,separators=(",",":"),allow_nan=False).encode()
    passed=population_match and all(x<=TOLERANCE for x in checks.values())
    return {"status":"PASS" if passed else "FAIL","tolerance":TOLERANCE,"population_match":population_match,
            "maximum_absolute_differences":checks,"snapshot_rows":len(rows),"trade_count":len({r['trade_id'] for r in rows}),
            "frozen_probability_target_panel_sha256":hashlib.sha256(payload).hexdigest(),
            "year_membership":dict(sorted(Counter(str(r["year"]) for r in {x['trade_id']:x for x in rows}.values()).items())),
            "symbol_membership":dict(sorted(Counter(r["symbol"] for r in {x['trade_id']:x for x in rows}.values()).items()))}


def run(repo: Path) -> dict:
    repo=repo.resolve(); reject_2026(repo)
    if os.environ.get("CONDA_DEFAULT_ENV")!="binance-v2-research": raise RuntimeError("conda environment must be binance-v2-research")
    contract=repo/CONTRACT_REL
    if sha(contract)!=CONTRACT_SHA256: raise RuntimeError("C21 contract changed after prospective freeze")
    rows,info=build_frozen_rows(repo); reproduction=reproduce_c20(repo,rows,info)
    if reproduction["status"]!="PASS": raise RuntimeError("C20 reproduction failed; C21 interpretation prohibited")
    pooled={t:decomposition(rows,t) for t in c20.TARGETS}
    years={str(y):{t:decomposition([r for r in rows if r["year"]==y],t) for t in c20.TARGETS} for y in (2024,2025)}
    symbols={s:{t:decomposition([r for r in rows if r["symbol"]==s],t) for t in c20.TARGETS} for s in c8.SYMBOLS}
    scopes={"pooled":rows,**{str(y):[r for r in rows if r["year"]==y] for y in (2024,2025)},**{s:[r for r in rows if r["symbol"]==s] for s in c8.SYMBOLS}}
    trade_unc={scope:{t:bootstrap(rr,t) for t in c20.TARGETS} for scope,rr in scopes.items()}
    calendar_unc={scope:{t:bootstrap(rr,t,True) for t in c20.TARGETS} for scope,rr in scopes.items()}
    adjustment={t:causal_adjustment(rows,t) for t in c20.TARGETS}
    out=repo/OUTPUT_REL; out.mkdir(parents=True,exist_ok=True)
    weighting={"snapshot_weight":"1 / n_i within the analyzed cell","global_normalization":"divide by number of eligible trades","trade_total_weight":1,
               "covariance_denominator":"population/equal-trade denominator","long_duration_dominance":False,"identical_to_C20":True}
    covdef={"identity":"Cov_total(p,V) = Cov_between(pbar_i,Vbar_i) + E_i[Cov_within_i(p_it,V_it)]",
            "within_mean":"arithmetic mean over each trade's eligible snapshots","between":"population covariance over equally weighted trade means","tolerance":TOLERANCE}
    corr={t:{k:pooled[t][k] for k in ("pooled_correlation","trade_mean_correlation","within_trade_correlations")} for t in c20.TARGETS}
    corr["statement"]="Average per-trade correlation is not the within-trade covariance component and cannot be averaged to reconstruct pooled correlation. Covariance decomposes additively under common centering; correlations use different variance normalizations."
    diagnostics={"role":"DIAGNOSTIC_ONLY_NOT_A_LIVE_FEATURE","full_trajectory":True,"live_feature_schema":[],
                 "prohibition":"pbar_i and Vbar_i use full observed trajectories and must never be predictors or production features."}
    predicates={t:{"classification":pooled[t]["classification"],"explanatory_only":True,"policy_value_implied":False} for t in c20.TARGETS}
    implication={"c22_started":False,"statement":"C21 supplies structural explanation only. Any C22 work requires a separate prospective contract; no horizon, model, state architecture, or policy is selected here."}
    adjustment_def={"method":"within-trade fixed-effects weighted OLS / Frisch-Waugh residualization","outcome":"each frozen C20 DELTA_LIQ target","exposure":"frozen C9 p_t2",
                    "controls":list(ADJUSTMENT_FIELDS),"elapsed_minutes":"(state_ms-entry_ms)/60000",
                    "current_return_from_entry":"current C20 executable open at t / frozen entry price - 1","causal_contemporaneous_only":True,
                    "prohibited_variables":["future terminal distance","future event proximity","eventual outcome class","future MFE/MAE","future P0 return","full-trajectory trade means"],"causal_proof":False}
    files={"run_manifest":{"version":"C21_RUN_V1","contract_sha256":CONTRACT_SHA256,"python":sys.version,"numpy":np.__version__,"platform":platform.platform(),"conda_environment":"binance-v2-research"},
           "provenance":{"contract_sha256":CONTRACT_SHA256,"inputs":{CONTRACT_REL:sha(contract),"c20_reproducibility_hashes":sha(repo/"artifacts/c20_forward_liquidation_value/reproducibility_hashes.json"),"c7_population":sha(repo/"artifacts/c7_full_population_t2_exit_overlay/population_manifest.json"),"c9_final_summary":sha(repo/"artifacts/c9_dynamic_pre_t2_state/final_summary.json")},"no_2026_access":True},
           "c20_reproduction":reproduction,"weighting_definition":weighting,"covariance_definition":covdef,"covariance_decomposition":pooled,
           "correlation_interpretation":corr,"year_decomposition":years,"symbol_decomposition":symbols,"uncertainty_trade_bootstrap":trade_unc,
           "uncertainty_calendar_block":calendar_unc,"causal_adjustment_definition":adjustment_def,"causal_adjustment_results":adjustment,
           "diagnostic_only_trade_means":diagnostics,"interpretation_predicates":predicates,"c22_implication":implication}
    for name,value in files.items(): write(out/f"{name}.json",value)
    final={"contract_sha256":CONTRACT_SHA256,"c20_reproduction":reproduction,"weighting":weighting,"covariance_identity":covdef,
           "pooled":pooled,"years":years,"symbols":symbols,"trade_bootstrap":trade_unc,"calendar_block_bootstrap":calendar_unc,
           "correlations":corr,"causal_adjustment_definition":adjustment_def,"causal_adjustment_results":adjustment,
           "diagnostic_trade_means":diagnostics,"frozen_interpretation":predicates,"c22_implication":implication,
           "limitations":["observed association, not an exit advantage, causal effect, policy profitability, or deployable predictive value","future liquidation targets are evaluation-only","symbol cells may have limited trade support"],
           "confirmations":{"model_trained_or_recalibrated":False,"exit_policy_defined_or_evaluated":False,"pnl_optimized":False,"horizon_selected_or_ranked":False,"future_diagnostic_promoted_to_predictor":False,"accessed_2026":False,"c22_started":False,"c7_c20_scientific_behavior_modified":False}}
    write(out/"final_summary.json",final)
    write(out/"reproducibility_hashes.json",{p.name:sha(p) for p in sorted(out.glob("*.json")) if p.name!="reproducibility_hashes.json"})
    return final
