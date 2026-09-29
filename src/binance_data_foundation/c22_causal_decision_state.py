"""C22 strictly causal decision-state prediction study."""
from __future__ import annotations

import hashlib, json, math, os, platform, sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from . import c8_timescale as c8
from . import c20_forward_liquidation_value as c20
from . import c21_between_within_covariance as c21

CONTRACT_SHA256 = "6899cce6a26682f80547ebef024d9b4fdd8f1aa16ba4d9e737239553edd377e0"
CONTRACT_REL = "contracts/C22_causal_decision_state_CONTRACT.md"
OUTPUT_REL = "artifacts/c22_causal_decision_state"
LAGS = (5, 15, 30)
RIDGE_ALPHA = 1.0
LOGISTIC_C = 1.0
MODELS = ("M0", "M1", "M2", "M3")
BASE = ("p_t2",)
PROGRESS = ("elapsed_minutes_since_entry", "observable_current_return_from_entry")
CONTEXT = ("first_honest_p_t2", "delta_p_from_first")
TRAJECTORY = tuple(x for lag in LAGS for x in (f"delta_p_{lag}m", f"delta_p_{lag}m_missing"))
FEATURES = {"M0": (), "M1": BASE, "M2": BASE + PROGRESS,
            "M3": BASE + PROGRESS + CONTEXT + TRAJECTORY}
PROHIBITED = ("exit_now_price", "exit_now_net", "event_price", "event_net", "forward_price_5",
              "forward_price_15", "forward_price_30", "forward_price_60", "forward_net_5",
              "forward_net_15", "forward_net_30", "forward_net_60", *c20.TARGETS,
              "outcome", "terminal_ms", "mean_p", "mean_v")


def reject_2026(path) -> None:
    if any("2026" in p for p in os.fspath(path).replace("\\", "/").lower().split("/")):
        raise PermissionError("C22 prohibits 2026 data or metadata access")


def sha(path: Path) -> str:
    reject_2026(path); h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""): h.update(block)
    return h.hexdigest()


def write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n")


def target_geometry_audit() -> dict:
    common = {
        "identity": "DELTA_LIQ_H(t) = FORWARD_NET_H(t) - EXIT_NOW_NET(t)",
        "paired_cost_form": "q_i*(1-s)*(1-f)*(P_endpoint,it-P_exec,it)/N_i",
        "mechanical_components": {
            "current_executable_liquidation_price": "negative term -B_i*P_exec,it",
            "fixed_or_horizon_event_endpoint_price": "positive term +B_i*P_endpoint,it",
            "trade_specific_quantity_cost_scaling": "B_i=q_i*(1-s)*(1-f)/N_i"},
        "predictor_status": "TARGET_ACCOUNTING_ONLY"}
    targets = {}
    for target in c20.TARGETS:
        targets[target] = dict(common, endpoint=("frozen lifecycle event price" if target == "DELTA_LIQ_EVENT"
            else "price at min(t+H, frozen lifecycle terminal)"))
    targets["DELTA_LIQ_EVENT"].update({
        "explicit_form": "V_it = A_i - B_i P_exec,it",
        "A_i": "B_i * P_event,i (trade-fixed event endpoint contribution)",
        "B_i": "q_i*(1-s)*(1-f)/N_i (positive trade-specific scale)"})
    return {"status": "PASS", "completed_before_model_fitting": True, "targets_unchanged": True,
            "targets": targets,
            "interpretation": ["Target geometry can induce within-trade relationships.",
                "Retrospectively removing price-related variation does not demonstrate a predictive mechanism.",
                "Incremental predictive value is determined only by frozen out-of-sample model evaluation."]}


def build_causal_rows(repo: Path) -> tuple[list[dict], dict]:
    """Reuse the exact C20/C21 population and add only completed-state features."""
    rows, info = c21.build_frozen_rows(repo)
    by = defaultdict(list)
    for r in rows: by[r["trade_id"]].append(r)
    out = []
    for tid in sorted(by):
        history = sorted(by[tid], key=lambda x: x["state_ms"])
        first = float(history[0]["p_t2"])
        for r in history:
            t = int(r["state_ms"]); p = float(r["p_t2"])
            # C9 architecture B's completed 5m close is already represented exactly by current_return.
            feat = {"p_t2": p,
                "elapsed_minutes_since_entry": (t-int(r["entry_ms"]))/c8.MINUTE,
                "observable_current_return_from_entry": float(r["features"]["current_return"]),
                "first_honest_p_t2": first, "delta_p_from_first": p-first}
            for lag in LAGS:
                cutoff = t-lag*c8.MINUTE
                past = [x for x in history if int(x["state_ms"]) <= cutoff]
                if past:
                    feat[f"delta_p_{lag}m"] = p-float(past[-1]["p_t2"])
                    feat[f"delta_p_{lag}m_missing"] = 0.0
                else:
                    feat[f"delta_p_{lag}m"] = None
                    feat[f"delta_p_{lag}m_missing"] = 1.0
            out.append(r | {"causal_features": feat})
    return out, info


def _weights(rows): return c8.trade_weights(rows)


def fit_preprocessor(rows: list[dict], names: tuple[str, ...]) -> dict:
    w = _weights(rows); w /= w.sum(); result = {}
    for name in names:
        raw = [r["causal_features"][name] for r in rows]
        present = np.asarray([x is not None for x in raw])
        vals = np.asarray([float(x) for x in raw if x is not None])
        wp = w[present]; order = np.argsort(vals, kind="mergesort"); vals, wp = vals[order], wp[order]
        impute = float(vals[np.searchsorted(np.cumsum(wp)/wp.sum(), .5)]) if len(vals) else 0.0
        x = np.asarray([impute if v is None else float(v) for v in raw])
        mean = float(w@x); sd = float(np.sqrt(w@((x-mean)**2)))
        result[name] = {"imputation": "training_weighted_median", "impute_value": impute,
                        "mean": mean, "sd": sd if sd > 0 else 1.0}
    return result


def design(rows: list[dict], names: tuple[str, ...], prep: dict) -> np.ndarray:
    x = np.ones((len(rows), 1+len(names)))
    for j, name in enumerate(names, 1):
        p=prep[name]; raw=[r["causal_features"][name] for r in rows]
        x[:,j]=[(p["impute_value"] if v is None else float(v)-p["mean"])/p["sd"] for v in raw]
        # Parentheses matter when imputing.
        x[:,j]=np.asarray([(p["impute_value"] if v is None else float(v)) for v in raw])
        x[:,j]=(x[:,j]-p["mean"])/p["sd"]
    return x


def fit_ridge(x, y, weights, alpha=RIDGE_ALPHA):
    w=weights/weights.sum(); penalty=np.eye(x.shape[1])*alpha; penalty[0,0]=0
    coef=np.linalg.solve(x.T@(x*w[:,None])+penalty, x.T@(w*y))
    return {"coef":coef,"alpha":alpha}


def fit_models(train, valid, target):
    y=np.asarray([r[target] for r in train]); yb=(y>0).astype(float); w=_weights(train); pred={}; detail={}
    mean=float((w/w.sum())@y); prevalence=float((w/w.sum())@yb)
    pred["M0"]={"binary":np.full(len(valid),prevalence),"continuous":np.full(len(valid),mean)}
    detail["M0"]={"training_prevalence":prevalence,"training_weighted_mean":mean}
    for model in MODELS[1:]:
        names=FEATURES[model]; prep=fit_preprocessor(train,names); xt=design(train,names,prep); xv=design(valid,names,prep)
        logit=c8.fit_logistic(xt,yb,w,C=LOGISTIC_C); ridge=fit_ridge(xt,y,w)
        pred[model]={"binary":c8.predict(logit,xv),"continuous":xv@ridge["coef"]}
        detail[model]={"features":list(names),"preprocessor":prep,
            "binary":{"regularization_C":LOGISTIC_C,"coef":logit["coef"].tolist(),"converged":logit["converged"]},
            "continuous":{"ridge_alpha":RIDGE_ALPHA,"coef":ridge["coef"].tolist()}}
    return pred,detail


def binary_metrics(rows, target, p):
    y=np.asarray([r[target]>0 for r in rows]); pp=np.clip(np.asarray(p),1e-15,1-1e-15); w=_weights(rows); wn=w/w.sum()
    proxy=[dict(r,label=int(v)) for r,v in zip(rows,y)]
    cal=c8.calibration(proxy,pp); bins=cal["bins"]
    for b in bins: b["absolute_gap"]=abs(b["mean_probability"]-b["observed"])
    ece=sum((sum(wn[i] for i,q in enumerate(pp) if q>=b["lower"] and q<(b["lower"]+.1 if b["lower"]<.9 else 1.00001)))*b["absolute_gap"] for b in bins)
    return {"rows":len(rows),"trades":len({r['trade_id'] for r in rows}),"prevalence":float(wn@y),
        "brier":float(wn@((pp-y)**2)),"log_loss":float(wn@(-(y*np.log(pp)+(~y)*np.log(1-pp)))),
        "auc":c8.weighted_auc(y,pp,w),"calibration_intercept":cal["intercept"],
        "calibration_slope":cal["slope"],"ece":float(ece)}


def continuous_metrics(rows,target,p):
    y=np.asarray([r[target] for r in rows]); q=np.asarray(p); w=_weights(rows); wn=w/w.sum()
    my,mq=float(wn@y),float(wn@q); den=math.sqrt(float(wn@((y-my)**2))*float(wn@((q-mq)**2)))
    return {"rows":len(rows),"trades":len({r['trade_id'] for r in rows}),"mae":float(wn@np.abs(q-y)),
        "rmse":float(np.sqrt(wn@((q-y)**2))),"correlation":float(wn@((q-mq)*(y-my))/den) if den else None,
        "sign_accuracy":float(wn@(np.sign(q)==np.sign(y)))}


def diagnostic_association(rows,x,target):
    rr=[r for r in rows if r["causal_features"].get(x) is not None]
    if not rr:return None
    w=_weights(rr); w/=w.sum(); a=np.asarray([r["causal_features"][x] for r in rr]); b=np.asarray([r[target] for r in rr]); ma,mb=w@a,w@b
    den=math.sqrt(float(w@((a-ma)**2))*float(w@((b-mb)**2)))
    return {"rows":len(rr),"trades":len({r['trade_id'] for r in rr}),"correlation":float(w@((a-ma)*(b-mb))/den) if den else None}


def _comparisons(binary, continuous):
    out={}
    for target in c20.TARGETS:
        out[target]={}
        for pair in (("M2","M1"),("M3","M1"),("M3","M2")):
            a,b=pair; out[target][f"{a}_vs_{b}"]={
                "brier_improvement":binary[target][b]["brier"]-binary[target][a]["brier"],
                "log_loss_improvement":binary[target][b]["log_loss"]-binary[target][a]["log_loss"],
                "auc_change":binary[target][a]["auc"]-binary[target][b]["auc"],
                "mae_improvement":continuous[target][b]["mae"]-continuous[target][a]["mae"],
                "rmse_improvement":continuous[target][b]["rmse"]-continuous[target][a]["rmse"]}
    return out


def grouped_coefficients(details, families):
    """Materialize standardized coefficients by the frozen feature families."""
    out={}
    for scope, targets in details.items():
        out[scope]={}
        for target, models in targets.items():
            out[scope][target]={}
            for model in MODELS[1:]:
                names=models[model]["features"]
                out[scope][target][model]={kind:{family:{name:float(models[model][kind]["coef"][1+names.index(name)]) for name in members if name in names} for family,members in families.items()} for kind in ("binary","continuous")}
    return out


def run(repo: Path) -> dict:
    repo=repo.resolve(); reject_2026(repo)
    if os.environ.get("CONDA_DEFAULT_ENV") != "binance-v2-research": raise RuntimeError("conda environment must be binance-v2-research")
    contract=repo/CONTRACT_REL
    if sha(contract)!=CONTRACT_SHA256: raise RuntimeError("C22 contract changed after prospective freeze")
    out=repo/OUTPUT_REL; out.mkdir(parents=True,exist_ok=True)
    # Mandatory pre-fit audit is materialized and checked before any fitting call.
    geometry=target_geometry_audit(); write(out/"target_geometry_audit.json",geometry)
    if geometry["status"]!="PASS" or not geometry["completed_before_model_fitting"]: raise RuntimeError("target geometry audit failed")
    rows,info=build_causal_rows(repo); reproduction=c21.reproduce_c20(repo,rows,info)
    if reproduction["status"]!="PASS": raise RuntimeError("frozen C20 reproduction failed")
    rec=info|{"expected_scored_snapshots":56217,"expected_scored_trades":1610,
              "exact_reconciliation":len(rows)==56217 and len({r['trade_id'] for r in rows})==1610}
    if not rec["exact_reconciliation"]: raise RuntimeError("C22 population mismatch")
    rows24=[r for r in rows if r["year"]==2024]; rows25=[r for r in rows if r["year"]==2025]
    predictions24={t:{m:[] for m in MODELS} for t in c20.TARGETS}; scored24=[]; folds={}; details24={}
    # The exact honest C9 panel starts at fold_A validation, so fold_A has no
    # legally scored predecessor training states.  fold_B is the sole honest
    # expanding 2024 development split: earlier scored block -> later block.
    for fold in ("fold_B",):
        train,valid=c8.split_fold(rows24,fold); folds[fold]={"bounds_ms":list(c8.FOLDS[fold]),"train_rows":len(train),"train_trades":len({r['trade_id'] for r in train}),"validation_rows":len(valid),"validation_trades":len({r['trade_id'] for r in valid}),"training_strictly_precedes_validation":max(r['terminal_ms'] for r in train)<min(r['entry_ms'] for r in valid)}
        scored24.extend(valid); details24[fold]={}
        for target in c20.TARGETS:
            pred,detail=fit_models(train,valid,target);details24[fold][target]=detail
            for m in MODELS:predictions24[target][m].extend([{ "binary":float(a),"continuous":float(b)} for a,b in zip(pred[m]["binary"],pred[m]["continuous"])])
    finalpred={};details25={}
    for target in c20.TARGETS:
        finalpred[target],details25[target]=fit_models(rows24,rows25,target)
    b24={t:{m:binary_metrics(scored24,t,[x["binary"] for x in predictions24[t][m]]) for m in MODELS} for t in c20.TARGETS}
    c24={t:{m:continuous_metrics(scored24,t,[x["continuous"] for x in predictions24[t][m]]) for m in MODELS} for t in c20.TARGETS}
    b25={t:{m:binary_metrics(rows25,t,finalpred[t][m]["binary"]) for m in MODELS} for t in c20.TARGETS}
    c25={t:{m:continuous_metrics(rows25,t,finalpred[t][m]["continuous"]) for m in MODELS} for t in c20.TARGETS}
    comp24,comp25=_comparisons(b24,c24),_comparisons(b25,c25)
    symbols={}
    for symbol in c8.SYMBOLS:
        ix=[i for i,r in enumerate(rows25) if r["symbol"]==symbol]; rr=[rows25[i] for i in ix]
        symbols[symbol]={t:{m:{"binary":binary_metrics(rr,t,finalpred[t][m]["binary"][ix]),"continuous":continuous_metrics(rr,t,finalpred[t][m]["continuous"][ix])} for m in MODELS[1:]} for t in c20.TARGETS}
    families={"current_probability":list(BASE),"elapsed_current_observable_price_progress":list(PROGRESS),"initial_trade_context":list(CONTEXT),"probability_trajectory":list(TRAJECTORY)}
    associations={"families":families,
        "standardized_coefficients_2024":grouped_coefficients(details24,families),
        "standardized_coefficients_2025":grouped_coefficients({"full_2024_training":details25},families),
        "fit_details_2024":details24,"fit_details_2025":details25,
        "interpretation":"standardized predictive associations only; no causal claim"}
    trajectory={x:{t:diagnostic_association(rows,x,t) for t in c20.TARGETS} for x in ("delta_p_from_first","delta_p_5m","delta_p_15m","delta_p_30m")}
    by=defaultdict(list)
    for r in rows:by[r["trade_id"]].append(r)
    trade_diag={t:diagnostic_association([dict(rr[0],average_realized_forward_value=float(np.mean([x[t] for x in rr]))) for rr in by.values()],"first_honest_p_t2","average_realized_forward_value") for t in c20.TARGETS}
    classifications={}
    for t in c20.TARGETS:
        a24,a25=comp24[t]["M3_vs_M1"],comp25[t]["M3_vs_M1"]
        symbol_wins=sum(symbols[s][t]["M3"]["binary"]["brier"]<symbols[s][t]["M1"]["binary"]["brier"] for s in c8.SYMBOLS)
        full=(a24["brier_improvement"]>0 and a24["log_loss_improvement"]>0 and a24["auc_change"]>0 and a25["brier_improvement"]>0 and a25["log_loss_improvement"]>0 and a25["auc_change"]>0 and (a24["rmse_improvement"]>0 or a24["mae_improvement"]>0) and (a25["rmse_improvement"]>0 or a25["mae_improvement"]>0) and c24[t]["M3"]["correlation"]>0 and c25[t]["M3"]["correlation"]>0 and symbol_wins>1)
        weak=((a24["brier_improvement"]>0 or a24["log_loss_improvement"]>0) and (a25["brier_improvement"]>0 or a25["log_loss_improvement"]>0)) or ((a24["rmse_improvement"]>0 or a24["mae_improvement"]>0) and (a25["rmse_improvement"]>0 or a25["mae_improvement"]>0))
        classifications[t]={"classification":"CAUSAL_STATE_SIGNAL_SUPPORTED" if full else "WEAK_CAUSAL_STATE_SIGNAL" if weak else "NO_USEFUL_CAUSAL_STATE_SIGNAL","symbols_with_M3_brier_improvement":symbol_wins,"not_dependent_on_one_symbol":symbol_wins>1}
    folds["availability_note"]="fold_A cannot be fit from the exact honestly scored C9 population because it has no earlier scored training block; no unscored probabilities were inferred"
    schema={"M0":{"features":[],"definition":"target-specific training prevalence/weighted mean"},**{m:{"features":list(FEATURES[m])} for m in MODELS[1:]},"prohibited_predictors":list(PROHIBITED),"fixed_regularization":{"logistic_C":LOGISTIC_C,"ridge_alpha":RIDGE_ALPHA}}
    timing={"status":"PASS","state_t":"after completion of the 5-minute state bar ending at t","prediction_information_cutoff":"<= t","execution_if_later_policy":"next valid 1-minute open after t","next_open_predictor":False}
    price={"field":"features.current_return reconstructed by C9/C8 feature_row","OBS_PRICE_formula":"frozen architecture-B fast.close[fast.at(t)]","bar_semantics":"close of completed 5-minute bar ending at t; underlying final minute is t-60000","return_formula":"OBS_PRICE(t)/entry_price-1","distinct_from_C20_exit_now":"C20 target accounting uses 1-minute open[t]"}
    leakage={"status":"PASS","feature_names_disjoint_from_prohibited":all(not set(FEATURES[m])&set(PROHIBITED) for m in MODELS),"next_open_predictor":False,"future_probability_access":False,"full_trade_mean_predictor":False,"preprocessing_training_only":True,"whole_trade_folds":True,"no_2026_access":True}
    files={"run_manifest":{"version":"C22_RUN_V1","contract_sha256":CONTRACT_SHA256,"python":sys.version,"numpy":np.__version__,"platform":platform.platform(),"conda_environment":"binance-v2-research"},"provenance":{"contract_sha256":CONTRACT_SHA256,"c20_reproduction":reproduction,"no_2026_access":True},"population_reconciliation":rec,"decision_timing_audit":timing,"observable_price_definition":price,"feature_schema":schema,"leakage_firewall":leakage,"fold_definitions":folds,"model_metrics_binary_2024":b24,"model_metrics_continuous_2024":c24,"calibration_2024":{t:{m:{k:b24[t][m][k] for k in ("calibration_intercept","calibration_slope","ece")} for m in MODELS} for t in c20.TARGETS},"model_metrics_binary_2025":b25,"model_metrics_continuous_2025":c25,"calibration_2025":{t:{m:{k:b25[t][m][k] for k in ("calibration_intercept","calibration_slope","ece")} for m in MODELS} for t in c20.TARGETS},"symbol_metrics":symbols,"feature_associations":associations,"trade_context_diagnostic":{"role":"DIAGNOSTIC_ONLY","full_trade_average_is_not_a_feature":True,"associations":trade_diag},"trajectory_diagnostic":{"descriptive_only":True,"associations":trajectory},"interpretation_predicates":classifications}
    for name,value in files.items():write(out/f"{name}.json",value)
    implication="A later separately frozen checkpoint may define a policy using only supported variables." if any(v["classification"]=="CAUSAL_STATE_SIGNAL_SUPPORTED" for v in classifications.values()) else "Do not define a policy; C23 was not started."
    final={"contract_sha256":CONTRACT_SHA256,"population_reconciliation":rec,"target_geometry_audit":geometry,"decision_timing_audit":timing,"observable_price_definition":price,"feature_schema":schema,"leakage_firewall":leakage,"metrics":{"2024":{"binary":b24,"continuous":c24,"comparisons":comp24},"2025":{"binary":b25,"continuous":c25,"comparisons":comp25}},"symbol_robustness":symbols,"feature_family_associations":associations,"trade_context_diagnostic":trade_diag,"trajectory_diagnostic":trajectory,"evidence_classification":classifications,"implication_for_C23":implication,"limitations":["predictive characterization, not a policy experiment","dependent repeated snapshots within trades","future-derived targets are evaluation-only","coefficients are predictive associations, not causal effects"],"confirmations":{"next_open_price_was_never_a_predictor":True,"full_trajectory_means_diagnostic_only":True,"policy_or_pnl_optimization":False,"horizon_model_or_regularization_search":False,"accessed_2026":False,"C23_started":False,"staged_committed_or_pushed":False}}
    write(out/"final_summary.json",final)
    write(out/"reproducibility_hashes.json",{p.name:sha(p) for p in sorted(out.glob("*.json")) if p.name!="reproducibility_hashes.json"})
    return final
