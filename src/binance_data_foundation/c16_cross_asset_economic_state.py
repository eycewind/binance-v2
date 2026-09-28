"""C16 frozen cross-asset economic-state characterization (no policy/P&L optimization)."""
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
from . import c14_post_t2_economic_state as c14

CONTRACT_SHA256 = "a0ff7b1bcba21d3e646b12335e4b7e38fcde491931f2e4f9672ac4a0d424a274"
CONTRACT_REL = "contracts/C16_cross_asset_economic_state_CONTRACT.md"
OUTPUT_REL = "artifacts/c16_cross_asset_economic_state"
SEED = 20260928
HORIZONS = (5, 30, 60)
FAMILIES = {
    "leader_returns": tuple(f"{s.lower()}_return_{h}m" for s in ("BTC", "ETH") for h in HORIZONS),
    "market_return": tuple(f"market_return_{h}m" for h in HORIZONS),
    "breadth": tuple(f"market_breadth_{h}m" for h in HORIZONS),
    "relative_strength": tuple(x for h in HORIZONS for x in (f"relative_btc_{h}m", f"relative_market_{h}m")),
    "dispersion": tuple(f"dispersion_{h}m" for h in HORIZONS),
    "volatility": ("market_abs_vol_30m", "market_abs_vol_60m"),
    "btc_co_movement": ("btc_corr_60m", "btc_self_indicator"),
}
CROSS_FEATURES = tuple(x for names in FAMILIES.values() for x in names)
ALL_FEATURES = c11.NAMES + CROSS_FEATURES

def reject_2026(path):
    if any("2026" in x for x in os.fspath(path).replace("\\", "/").lower().split("/")):
        raise PermissionError("C16 prohibits 2026 data or metadata access")

def sha(path: Path) -> str:
    reject_2026(path); h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1<<20), b""): h.update(b)
    return h.hexdigest()

def write(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False)+"\n")

def cross_asset_features(symbol: str, t: int, markets: dict) -> dict | None:
    """Features at t use minute bars whose close timestamps are <= t."""
    end = t-c10.MINUTE
    idx={s:m.index(end) for s,m in markets.items()}
    if any(i is None for i in idx.values()): return None
    returns={}
    for h in HORIZONS:
        vals={}
        for s,m in markets.items():
            i=idx[s]; j=m.index(t-(h+1)*c10.MINUTE)
            if j is None or i-j != h: return None
            vals[s]=float(m.close[i]/m.close[j]-1)
        returns[h]=vals
    out={}
    for leader in ("BTCUSDT", "ETHUSDT"):
        for h in HORIZONS: out[f"{leader[:3].lower()}_return_{h}m"]=returns[h][leader]
    for h in HORIZONS:
        a=np.asarray([returns[h][s] for s in c10.SYMBOLS])
        mean=float(a.mean())
        out[f"market_return_{h}m"]=mean
        out[f"market_breadth_{h}m"]=float(np.mean(a>0))
        out[f"relative_btc_{h}m"]=returns[h][symbol]-returns[h]["BTCUSDT"]
        out[f"relative_market_{h}m"]=returns[h][symbol]-mean
        out[f"dispersion_{h}m"]=float(np.std(a, ddof=0))
    # Fixed before evaluation: mean absolute equal-weight 1m return.
    for window in (30,60):
        series=[]
        for k in range(window):
            minute=[]
            for s,m in markets.items():
                i=m.index(end-k*c10.MINUTE); j=m.index(end-(k+1)*c10.MINUTE)
                if i is None or j is None: return None
                minute.append(float(m.close[i]/m.close[j]-1))
            series.append(float(np.mean(minute)))
        out[f"market_abs_vol_{window}m"]=float(np.mean(np.abs(series)))
    if symbol=="BTCUSDT":
        out["btc_corr_60m"],out["btc_self_indicator"]=0.0,1.0
    else:
        own=[];btc=[]
        for k in range(60):
            for s,target in ((symbol,own),("BTCUSDT",btc)):
                m=markets[s];i=m.index(end-k*c10.MINUTE);j=m.index(end-(k+1)*c10.MINUTE)
                if i is None or j is None:return None
                target.append(float(m.close[i]/m.close[j]-1))
        sd=float(np.std(own)*np.std(btc))
        out["btc_corr_60m"]=0.0 if sd==0 else float(np.corrcoef(own,btc)[0,1])
        out["btc_self_indicator"]=0.0
    return out if set(out)==set(CROSS_FEATURES) and all(math.isfinite(x) for x in out.values()) else None

def build_rows(repo: Path):
    data=c12.generate_frozen_panel(repo)
    manifest=json.loads((repo/"artifacts/c7_full_population_t2_exit_overlay/population_manifest.json").read_text())
    source={x["trade_id"]:x for x in manifest["rows"]}; trades={t["trade_id"]:t for t in data["trades"]}
    rows=[]; excluded=Counter()
    for row in data["binary_rows"]:
        tr=trades[row["trade_id"]]
        target=c14.target_for_snapshot(row,tr,data["markets"][row["symbol"]],float(source[row["trade_id"]]["p0_raw_exit_price"]))
        if not target["eligible"]: excluded[target["reason"]]+=1; continue
        cross=cross_asset_features(row["symbol"],row["state_ms"],data["markets"])
        if cross is None: excluded["CROSS_ASSET_ALIGNMENT"]+=1; continue
        rows.append(row|target|{"label":int(target["delta_v"]>0),"event_label":tr["terminal"],"p0_ms":tr["p0_ms"],"features":row["features"]|cross})
    return data,rows,excluded

def fit(rows,names): return c14.fit_logistic(rows,names)
def predict(model,rows): return c14.predict_logistic(model,rows)

def metrics(rows,p):
    if not rows:return None
    return c8.metrics(rows,np.asarray(p)) | {"calibration":c9.reliability(rows,np.asarray(p))}

def evaluate_2024(rows,names=ALL_FEATURES):
    pooled=[]; pred=defaultdict(list); definitions={}; models=[]
    for fold,bounds in c10.FOLDS.items():
        train,valid=c10.split_fold(rows,fold); w=c10.trade_weights(train);y=np.asarray([r["label"] for r in train])
        fitted={"M1":fit(train,c10.CONTEXT_FEATURES),"M2":fit(train,c11.NAMES),"M3":fit(train,names)}
        pooled.extend(valid);pred["M0"].extend(np.full(len(valid),float(w@y/w.sum())))
        for k,m in fitted.items():pred[k].extend(predict(m,valid))
        models.append(fitted["M3"])
        definitions[fold]={"bounds_ms":list(bounds),"training_rows":len(train),"training_trades":len({r['trade_id'] for r in train}),"validation_rows":len(valid),"validation_trades":len({r['trade_id'] for r in valid}),"whole_trades":True,"training_before_validation":max(r['entry_ms'] for r in train)<min(r['entry_ms'] for r in valid),"preprocessing_training_only":True}
    pp={k:np.asarray(v) for k,v in pred.items()}
    return pooled,pp,{k:metrics(pooled,v) for k,v in pp.items()},definitions,models

def evaluate_2025(rows24,rows25):
    w=c10.trade_weights(rows24);y=np.asarray([r["label"] for r in rows24]); fitted={"M1":fit(rows24,c10.CONTEXT_FEATURES),"M2":fit(rows24,c11.NAMES),"M3":fit(rows24,ALL_FEATURES)}
    pp={"M0":np.full(len(rows25),float(w@y/w.sum()))}|{k:predict(m,rows25) for k,m in fitted.items()}
    return pp,{k:metrics(rows25,v) for k,v in pp.items()},fitted

def subset(rows,pp,event="DETERIORATION_FIRST"):
    ix=np.asarray([r["event_label"]==event for r in rows]); rr=[r for r in rows if r["event_label"]==event]
    return {k:metrics(rr,v[ix]) for k,v in pp.items() if k in ("M2","M3")}

def comparisons(m):
    return {x:{"M2":m["M2"][x],"M3":m["M3"][x],"M3_minus_M2":m["M3"][x]-m["M2"][x],"improved":m["M3"][x]<m["M2"][x] if x in ("brier","log_loss") else m["M3"][x]>m["M2"][x]} for x in ("brier","log_loss","auc")}

def classify_trades(rows):
    by=defaultdict(list)
    for r in rows:by[r["trade_id"]].append(r)
    classes={}
    for tid,rr in by.items():
        rate=np.mean([r["label"] for r in rr]); classes[tid]="PREDOMINANTLY_HOLD" if rate>.8 else "PREDOMINANTLY_EXIT" if rate<.2 else "MIXED"
    def counts(group,key):return dict(sorted(Counter(key(r) for tid,rr in by.items() for r in [rr[0]] if classes[tid]==group).items()))
    summary={g:{"count":sum(v==g for v in classes.values()),"year":counts(g,lambda r:str(r["year"])),"symbol":counts(g,lambda r:r["symbol"]),"event":counts(g,lambda r:r["event_label"])} for g in ("PREDOMINANTLY_HOLD","PREDOMINANTLY_EXIT","MIXED")}
    return classes,summary,by

def t2_context(classes,by):
    first=[]
    for tid,rr in by.items():first.append((classes[tid],min(rr,key=lambda r:r["state_ms"])))
    allx={n:np.asarray([r["features"][n] for _,r in first]) for n in CROSS_FEATURES}
    out={}
    for g in ("PREDOMINANTLY_HOLD","PREDOMINANTLY_EXIT","MIXED"):
        ix=np.asarray([c==g for c,_ in first]);out[g]={}
        for n in CROSS_FEATURES:
            x=allx[n]; sd=float(x.std(ddof=0)); vals=x[ix]
            out[g][n]={"n":len(vals),"mean":float(vals.mean()),"median":float(np.median(vals)),"standardized_difference_vs_all":0.0 if sd==0 else float((vals.mean()-x.mean())/sd)}
    return {"definition":"first eligible post-T2 snapshot; standardized difference=(class mean-overall mean)/overall population SD","groups":out}

def symbol_metrics(rows,pp):
    out={}
    for s in c10.SYMBOLS:
        ix=np.asarray([r["symbol"]==s for r in rows]);rr=[r for r in rows if r["symbol"]==s]
        out[s]={k:metrics(rr,pp[k][ix]) for k in ("M2","M3")}
    return out

def run(repo: Path):
    reject_2026(repo)
    if os.environ.get("CONDA_DEFAULT_ENV")!="binance-v2-research":raise RuntimeError("conda environment must be binance-v2-research")
    contract=repo/CONTRACT_REL
    if sha(contract)!=CONTRACT_SHA256:raise RuntimeError("C16 contract changed after prospective freeze")
    c14.assert_feature_firewall(ALL_FEATURES+c10.SYMBOL_FEATURES)
    data,rows,excluded=build_rows(repo); rows24=[r for r in rows if r["year"]==2024];rows25=[r for r in rows if r["year"]==2025]
    pooled,pp24,m24,folds,fold_models=evaluate_2024(rows24);pp25,m25,models=evaluate_2025(rows24,rows25)
    d24=subset(pooled,pp24);d25=subset(rows25,pp25);comp24=comparisons(m24);comp25=comparisons(m25)
    classes,class_summary,by=classify_trades(rows);context=t2_context(classes,by)
    ablation={}
    for family,names in FAMILIES.items():
        _,_,mm,_,_=evaluate_2024(rows24,tuple(n for n in ALL_FEATURES if n not in names));ablation[family]={"removed":list(names),"metrics":mm["M3"],"versus_full_M3":{x:mm["M3"][x]-m24["M3"][x] for x in ("brier","log_loss","auc")}}
    sym24=symbol_metrics(pooled,pp24);sym25=symbol_metrics(rows25,pp25)
    # Full-development standardized coefficients, grouped prospectively.
    coef=models["M3"]["model"]["coef"]; names=["intercept"]+list(ALL_FEATURES)+list(c10.SYMBOL_FEATURES)
    assoc={"warning":"predictive associations only; no causal interpretation","groups":{"intercept":[{"feature":"intercept","coefficient":float(coef[0])}],"existing_local_context":[],"existing_1m_state":[],**{k:[] for k in FAMILIES},"symbol":[]}}
    for n,v in zip(names[1:],coef[1:]):
        group="existing_local_context" if n in c10.CONTEXT_FEATURES else "existing_1m_state" if n in c10.FAST_FEATURES else "symbol" if n in c10.SYMBOL_FEATURES else next(k for k,a in FAMILIES.items() if n in a)
        assoc["groups"][group].append({"feature":n,"coefficient":float(v)})
    proper_both=lambda c:all(c[x]["improved"] for x in ("brier","log_loss"))
    auc_both=comp24["auc"]["improved"] and comp25["auc"]["improved"]
    slopes_positive=m24["M3"]["calibration"]["slope"]>0 and m25["M3"]["calibration"]["slope"]>0
    symbol_not_one=sum(sym24[s]["M3"]["brier"]<sym24[s]["M2"]["brier"] and sym25[s]["M3"]["brier"]<sym25[s]["M2"]["brier"] for s in c10.SYMBOLS)>1
    supported=proper_both(comp24) and proper_both(comp25) and auc_both and slopes_positive and symbol_not_one
    weak=(any(comp24[x]["improved"] for x in ("brier","log_loss")) and any(comp25[x]["improved"] for x in ("brier","log_loss"))) or (proper_both(comp24) and any(comp25[x]["improved"] for x in ("brier","log_loss"))) or (proper_both(comp25) and any(comp24[x]["improved"] for x in ("brier","log_loss")))
    label="CROSS_ASSET_SIGNAL_SUPPORTED" if supported else "WEAK_CROSS_ASSET_SIGNAL" if weak else "NO_USEFUL_CROSS_ASSET_SIGNAL"
    rec={"source_first_t2_trades":845,"binary_source_trades":843,"causal_physical_snapshots":len(data["binary_rows"]),"eligible_aligned_snapshots":len(rows),"eligible_aligned_trades":len(by),"by_year":dict(Counter(str(r["year"]) for r in rows)),"excluded":dict(excluded)}
    schema={"frozen_before_evaluation":True,"families":{k:list(v) for k,v in FAMILIES.items()},"volatility_formula":"mean absolute equal-weight universe 1-minute return over trailing 30/60 completed minutes","dispersion_formula":"population standard deviation (ddof=0) of five horizon returns","btc_self":{"correlation":0.0,"indicator":1.0},"horizons_minutes":list(HORIZONS)}
    align={"status":"PASS","state_timestamp_semantics":"all inputs are closes of bars completed by t","last_permitted_bar_open":"t-60000","all_symbols_exact_timestamp_required":True,"gap_policy":"fail closed","feature_rows":len(rows)}
    out=repo/OUTPUT_REL;out.mkdir(parents=True,exist_ok=True)
    artifacts={
      "run_manifest":{"version":"C16_RUN_V1","contract_sha256":CONTRACT_SHA256,"seed":SEED,"python":sys.version,"numpy":np.__version__,"platform":platform.platform(),"conda_environment":os.environ.get("CONDA_DEFAULT_ENV")},
      "provenance":{"contract_sha256":CONTRACT_SHA256,"dependencies":{"c7_population":sha(repo/"artifacts/c7_full_population_t2_exit_overlay/population_manifest.json"),"c11_final":sha(repo/"artifacts/c11_dynamic_post_t2_state/final_summary.json"),"c14_final":sha(repo/"artifacts/c14_post_t2_economic_state/final_summary.json"),"c15_final":sha(repo/"artifacts/c15_economic_state_temporal_structure/final_summary.json")},"no_2026_access":True},
      "leakage_firewall":{"status":"PASS","features_checked":list(ALL_FEATURES),"target_builder_separate":True,"completed_bars_only":True,"future_bars":False,"target_derived_features":False},
      "population_reconciliation":rec,"cross_asset_feature_schema":schema,"feature_alignment_audit":align,"trade_class_summary":class_summary,"t2_context_summary":context,"fold_definitions":folds,
      "model_metrics_2024":m24,"calibration_2024":{k:v["calibration"] for k,v in m24.items()},"deterioration_subset_2024":d24,"family_ablation_2024":ablation,
      "frozen_model_procedure":{"models":{"M0":"training prevalence","M1":list(c10.CONTEXT_FEATURES),"M2":list(c11.NAMES),"M3":list(ALL_FEATURES)},"fixed_L2_penalty":1.0,"search":False,"trade_weight_total":1.0,"training_only_preprocessing":True},
      "model_metrics_2025":m25,"calibration_2025":{k:v["calibration"] for k,v in m25.items()},"deterioration_subset_2025":d25,"symbol_metrics":{"2024_OOF":sym24,"2025":sym25},"feature_associations":assoc,
      "interpretation_predicates":{"classification":label,"criteria":{"proper_scores_both_years":proper_both(comp24) and proper_both(comp25),"auc_both_years":auc_both,"positive_M3_calibration_slope_both_years":slopes_positive,"not_solely_one_symbol":symbol_not_one},"comparison_2024":comp24,"comparison_2025":comp25},
    }
    artifacts["final_summary"]={"contract_sha256":CONTRACT_SHA256,"population":rec,"alignment":align,"trade_classes":class_summary,"t2_context":context,"feature_schema":schema,"metrics_2024":m24,"comparison_2024":comp24,"deterioration_2024":d24,"ablation_2024":ablation,"metrics_2025":m25,"comparison_2025":comp25,"deterioration_2025":d25,"symbol_robustness":artifacts["symbol_metrics"],"feature_associations":assoc,"classification":label,"cross_asset_context_adds_useful_information":supported,"limitations":["observational predictive characterization, not causal evidence","snapshot dependence is controlled by unit trade weights","2024 OOF uses the frozen chronological cohorts","2025 evaluated once after procedure freeze"],"implication_for_c17":"C16 stops here; any C17 work requires a separately frozen prospective contract.","confirmations":{"policy_or_pnl_optimization":False,"model_feature_or_horizon_search":False,"accessed_2026":False,"started_c17":False}}
    for name,value in artifacts.items():write(out/f"{name}.json",value)
    hashes={p.name:sha(p) for p in sorted(out.glob("*.json")) if p.name!="reproducibility_hashes.json"};write(out/"reproducibility_hashes.json",hashes)
    return artifacts["final_summary"]
