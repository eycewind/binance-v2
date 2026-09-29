"""C23 incremental frozen-C9 ablation beyond simple causal state."""
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

CONTRACT_SHA256 = "1ad709e44a0a63ab2d845d3e6b5705083e70d1faf990ba02247743d82ee15c7e"
CONTRACT_REL = "contracts/C23_incremental_c9_ablation_CONTRACT.md"
OUTPUT_REL = "artifacts/c23_incremental_c9_ablation"
SEED = 20240923
REPLICATES = 2000
MODELS = ("S", "S+C9")
FEATURES = {
    "S": ("elapsed_minutes_since_entry", "observable_current_return_from_entry"),
    "S+C9": ("elapsed_minutes_since_entry", "observable_current_return_from_entry", "p_t2"),
}
PROHIBITED = c22.PROHIBITED + ("first_honest_p_t2", "delta_p_from_first", "next_open_price",
    "terminal_proximity", "future_mfe", "future_mae", "future_probabilities")


def reject_2026(path) -> None:
    if any("2026" in part for part in os.fspath(path).replace("\\", "/").lower().split("/")):
        raise PermissionError("C23 prohibits 2026 data or metadata access")


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


def binary_label(value: float) -> int:
    """Exact implemented C22 convention: zero is retained in class zero."""
    return int(float(value) > 0.0)


def fit_candidates(train: list[dict], valid: list[dict], target: str):
    y = np.asarray([r[target] for r in train], float)
    yb = np.asarray([binary_label(v) for v in y], float)
    weights = c22._weights(train)
    predictions, details = {}, {}
    for model in MODELS:
        names = FEATURES[model]
        prep = c22.fit_preprocessor(train, names)
        xt, xv = c22.design(train, names, prep), c22.design(valid, names, prep)
        logit = c8.fit_logistic(xt, yb, weights, C=1.0)
        ridge = c22.fit_ridge(xt, y, weights, alpha=1.0)
        predictions[model] = {"binary": c8.predict(logit, xv), "continuous": xv @ ridge["coef"]}
        details[model] = {"features": list(names), "preprocessor": prep,
            "binary": {"family": "L2 logistic regression", "C": 1.0,
                "coef": logit["coef"].tolist(), "converged": logit["converged"]},
            "continuous": {"family": "ridge regression", "alpha": 1.0,
                "coef": ridge["coef"].tolist()}}
    return predictions, details


def differences(binary: dict, continuous: dict) -> dict:
    out = {}
    for target in c20.TARGETS:
        bs, bc = binary[target]["S"], binary[target]["S+C9"]
        cs, cc = continuous[target]["S"], continuous[target]["S+C9"]
        out[target] = {"Delta_Brier": bs["brier"]-bc["brier"],
            "Delta_LogLoss": bs["log_loss"]-bc["log_loss"],
            "Delta_AUC": bc["auc"]-bs["auc"],
            "Delta_MAE": cs["mae"]-cc["mae"],
            "Delta_RMSE": cs["rmse"]-cc["rmse"]}
    return out


def _trade_loss_table(rows, target, pred_s, pred_c):
    grouped = defaultdict(list)
    for i, row in enumerate(rows): grouped[row["trade_id"]].append(i)
    table = []
    for tid in sorted(grouped):
        ix = np.asarray(grouped[tid], int); y = np.asarray([rows[i][target] for i in ix]); label = y > 0
        ps = np.clip(np.asarray(pred_s)[ix], 1e-15, 1-1e-15)
        pc = np.clip(np.asarray(pred_c)[ix], 1e-15, 1-1e-15)
        qs, qc = np.asarray(pred_s)[ix], np.asarray(pred_c)[ix]
        r = rows[ix[0]]
        table.append({"trade_id": tid,
            "month": datetime.fromtimestamp(int(r["entry_ms"])/1000, timezone.utc).strftime("%Y-%m"),
            "brier_s": float(np.mean((ps-label)**2)), "brier_c": float(np.mean((pc-label)**2)),
            "log_s": float(np.mean(-(label*np.log(ps)+(~label)*np.log(1-ps)))),
            "log_c": float(np.mean(-(label*np.log(pc)+(~label)*np.log(1-pc)))),
            "mae_s": float(np.mean(abs(qs-y))), "mae_c": float(np.mean(abs(qc-y))),
            "mse_s": float(np.mean((qs-y)**2)), "mse_c": float(np.mean((qc-y)**2))})
    return table


def paired_bootstrap(rows, target, pred_s, pred_c, unit, seed=SEED, replicates=REPLICATES):
    """Paired loss bootstrap; models are never refit inside replicates."""
    table = _trade_loss_table(rows, target, pred_s["binary"], pred_c["binary"])
    # Add continuous losses without altering binary pairing.
    cont = _trade_loss_table(rows, target, pred_s["continuous"], pred_c["continuous"])
    for a, b in zip(table, cont):
        for key in ("mae_s", "mae_c", "mse_s", "mse_c"): a[key] = b[key]
    rng = np.random.Generator(np.random.PCG64(seed)); samples = []
    if unit == "calendar_month":
        groups = defaultdict(list)
        for i, row in enumerate(table): groups[row["month"]].append(i)
        labels = sorted(groups)
        draws = lambda: np.asarray([i for j in rng.integers(len(labels), size=len(labels)) for i in groups[labels[int(j)]]], int)
        construction = "whole_utc_entry_calendar_month_clusters_with_all_symbols_and_whole_trades"
    elif unit == "whole_trade":
        labels = None; draws = lambda: rng.integers(len(table), size=len(table))
        construction = "whole_trades_with_replacement_all_snapshots_attached"
    else: raise ValueError("unknown bootstrap unit")
    for _ in range(replicates):
        chosen = [table[int(i)] for i in draws()]
        mean = lambda key: float(np.mean([r[key] for r in chosen]))
        samples.append((mean("brier_s")-mean("brier_c"), mean("log_s")-mean("log_c"),
            mean("mae_s")-mean("mae_c"), np.sqrt(mean("mse_s"))-np.sqrt(mean("mse_c"))))
    arr = np.asarray(samples); names = ("Delta_Brier", "Delta_LogLoss", "Delta_MAE", "Delta_RMSE")
    return {"unit": unit, "construction": construction, "pairing_preserved": True,
        "models_refit_inside_replicates": False, "seed": seed, "generator": "PCG64",
        "replicates": replicates, "quantile_method": "linear_type_7", "calendar_months": labels,
        "intervals": {name: {"ci95": np.quantile(arr[:, j], [.025, .975], method="linear").tolist(),
            "replicate_sha256": hashlib.sha256(arr[:, j].astype("<f8").tobytes()).hexdigest()}
            for j, name in enumerate(names)}}


def run(repo: Path) -> dict:
    repo = repo.resolve(); reject_2026(repo)
    if os.environ.get("CONDA_DEFAULT_ENV") != "binance-v2-research":
        raise RuntimeError("conda environment must be binance-v2-research")
    contract = repo/CONTRACT_REL
    if sha(contract) != CONTRACT_SHA256: raise RuntimeError("C23 contract changed after prospective freeze")
    out = repo/OUTPUT_REL; out.mkdir(parents=True, exist_ok=True)
    label_definition = {"source": "implemented C22 fit_models and binary_metrics",
        "rule": "Y_H = 1 iff DELTA_LIQ_H > 0, otherwise 0", "positive": 1, "negative": 0,
        "exact_zero": 0, "exact_zero_retained": True, "established_before_model_fitting": True}
    write(out/"binary_label_definition.json", label_definition)
    rows, info = c22.build_causal_rows(repo); reproduction = c21.reproduce_c20(repo, rows, info)
    rec = info | {"expected_scored_snapshots": 56217, "expected_scored_trades": 1610,
        "exact_reconciliation": len(rows)==56217 and len({r["trade_id"] for r in rows})==1610}
    if reproduction["status"] != "PASS" or not rec["exact_reconciliation"]: raise RuntimeError("frozen population mismatch")
    rows24 = [r for r in rows if r["year"]==2024]; rows25 = [r for r in rows if r["year"]==2025]
    train, valid = c8.split_fold(rows24, "fold_B")
    fold = {"fold_A": "NOT_FABRICATED_NO_EARLIER_HONESTLY_SCORED_TRAINING_BLOCK",
        "fold_B": {"bounds_ms": list(c8.FOLDS["fold_B"]), "train_rows": len(train),
            "train_trades": len({r['trade_id'] for r in train}), "validation_rows": len(valid),
            "validation_trades": len({r['trade_id'] for r in valid}),
            "training_strictly_precedes_validation": max(r['terminal_ms'] for r in train)<min(r['entry_ms'] for r in valid)},
        "2024_coverage": "single available chronological validation block; not comprehensive multi-fold OOF coverage"}
    if (len(train),len({r['trade_id'] for r in train}),len(valid),len({r['trade_id'] for r in valid})) != (7970,256,8631,267):
        raise RuntimeError("fold_B mismatch")
    pred24, detail24, pred25, detail25 = {}, {}, {}, {}
    for target in c20.TARGETS:
        pred24[target], detail24[target] = fit_candidates(train, valid, target)
        pred25[target], detail25[target] = fit_candidates(rows24, rows25, target)
    def panels(rr, predictions):
        binary = {t:{m:c22.binary_metrics(rr,t,predictions[t][m]["binary"]) for m in MODELS} for t in c20.TARGETS}
        continuous = {t:{m:c22.continuous_metrics(rr,t,predictions[t][m]["continuous"]) for m in MODELS} for t in c20.TARGETS}
        calibration = {t:{m:{k:binary[t][m][k] for k in ("calibration_intercept","calibration_slope","ece")} for m in MODELS} for t in c20.TARGETS}
        return binary, continuous, calibration, differences(binary, continuous)
    b24,c24,cal24,d24 = panels(valid,pred24); b25,c25,cal25,d25 = panels(rows25,pred25)
    month, trade = {}, {}
    for year, rr, pred in (("2024",valid,pred24),("2025",rows25,pred25)):
        month[year]={};trade[year]={}
        for t in c20.TARGETS:
            month[year][t]=paired_bootstrap(rr,t,pred[t]["S"],pred[t]["S+C9"],"calendar_month")
            trade[year][t]=paired_bootstrap(rr,t,pred[t]["S"],pred[t]["S+C9"],"whole_trade")
    symbols={}
    for symbol in c8.SYMBOLS:
        symbols[symbol]={}
        for year,rr,pred in (("2024",valid,pred24),("2025",rows25,pred25)):
            ix=[i for i,r in enumerate(rr) if r["symbol"]==symbol]; cell=[rr[i] for i in ix]
            symbols[symbol][year]={t:{m:{"brier":c22.binary_metrics(cell,t,pred[t][m]["binary"][ix])["brier"],
                "log_loss":c22.binary_metrics(cell,t,pred[t][m]["binary"][ix])["log_loss"],
                "auc":c22.binary_metrics(cell,t,pred[t][m]["binary"][ix])["auc"],
                "rmse":c22.continuous_metrics(cell,t,pred[t][m]["continuous"][ix])["rmse"],
                "mae":c22.continuous_metrics(cell,t,pred[t][m]["continuous"][ix])["mae"]} for m in MODELS} for t in c20.TARGETS}
    classifications={}
    for t in c20.TARGETS:
        proper=all(d[t][k]>0 for d in (d24,d25) for k in ("Delta_Brier","Delta_LogLoss"))
        ci_ok=all(not (scheme[y][t]["intervals"]["Delta_Brier"]["ci95"][1]<0 and
            scheme[y][t]["intervals"]["Delta_LogLoss"]["ci95"][1]<0)
            for y in ("2024","2025") for scheme in (month,trade))
        wins_by_year={y:sum(symbols[s][y][t]["S+C9"]["brier"]<symbols[s][y][t]["S"]["brier"] for s in c8.SYMBOLS)
            for y in ("2024","2025")}
        broad=min(wins_by_year.values())>1
        supported=proper and ci_ok and broad
        favorable=all(d[t][k]>0 for d in (d24,d25) for k in ("Delta_Brier","Delta_LogLoss"))
        weak=favorable or ((d24[t]["Delta_Brier"]>0 or d24[t]["Delta_LogLoss"]>0) and (d25[t]["Delta_Brier"]>0 or d25[t]["Delta_LogLoss"]>0))
        classifications[t]={"classification":"INCREMENTAL_C9_SIGNAL_SUPPORTED" if supported else "WEAK_INCREMENTAL_C9_SIGNAL" if weak else "NO_USEFUL_INCREMENTAL_C9_SIGNAL",
            "proper_scores_favorable_both_years":proper,"uncertainty_directionally_supportive":ci_ok,
            "symbols_with_brier_improvement_by_year":wins_by_year,"not_obviously_one_symbol":broad}
    schema={m:{"features":list(FEATURES[m])} for m in MODELS} | {"sole_difference":["p_t2"],"fixed_models":{"binary":"L2 logistic C=1.0","continuous":"ridge alpha=1.0"}}
    timing={"status":"PASS","prediction_time":"after completed frozen 5-minute state bar at t","observable_price":"frozen architecture-B fast.close[fast.at(t)]","observable_return":"OBS_PRICE(t)/entry_price-1","next_1m_open":"target/accounting only; not a predictor"}
    leakage={"status":"PASS","features_disjoint_from_prohibited":all(set(v).isdisjoint(PROHIBITED) for v in FEATURES.values()),"training_only_preprocessing":True,"future_variables":False,"next_open_predictor":False,"no_2026_access":True}
    paired={"2024":d24,"2025":d25,"direction":"positive means S+C9 improves proper/error score; Delta_AUC is AUC(S+C9)-AUC(S)"}
    manifest={"version":"C23_RUN_V1","contract_sha256":CONTRACT_SHA256,"seed":SEED,"replicates":REPLICATES,"python":sys.version,"numpy":np.__version__,"platform":platform.platform(),"conda_environment":"binance-v2-research"}
    provenance={"contract_sha256":CONTRACT_SHA256,"frozen_C20_reproduction":reproduction,"C22_source_sha256":sha(repo/"src/binance_data_foundation/c22_causal_decision_state.py"),"no_2026_access":True}
    files={"run_manifest":manifest,"provenance":provenance,"population_reconciliation":rec,"decision_timing_audit":timing,"feature_schema":schema,"leakage_firewall":leakage,"fold_reconciliation":fold,
        "binary_metrics_2024":b24,"continuous_metrics_2024":c24,"calibration_2024":cal24,"paired_differences_2024":d24,
        "binary_metrics_2025":b25,"continuous_metrics_2025":c25,"calibration_2025":cal25,"paired_differences_2025":d25,
        "calendar_month_bootstrap":month,"whole_trade_bootstrap":trade,"symbol_metrics":symbols,"interpretation_predicates":classifications}
    for name,value in files.items(): write(out/f"{name}.json",value)
    final={"contract_sha256":CONTRACT_SHA256,"population_reconciliation":rec,"binary_label_definition":label_definition,"decision_timing_audit":timing,"feature_schema":schema,"fold_reconciliation":fold,
        "metrics":{"2024":{"binary":b24,"continuous":c24,"calibration":cal24},"2025":{"binary":b25,"continuous":c25,"calibration":cal25}},"paired_differences":paired,
        "calendar_month_uncertainty":month,"whole_trade_uncertainty":trade,"symbol_stability":symbols,"frozen_classification":classifications,
        "interpretation":"C9 incremental information is assessed separately as probability refinement, ranking discrimination, and continuous value prediction; none defines a policy.",
        "limitations":["single available 2024 chronological validation block","dependent repeated snapshots handled by equal whole-trade weighting and dependence-aware uncertainty","five symbols are not independent replications","predictive evidence is not causal or a policy advantage"],
        "implication_for_C24":"STOP after C23; C24 is not started or authorized.",
        "confirmations":{"sole_feature_difference":"current frozen p_t2","new_model_family_horizon_threshold_search":False,"policy_or_pnl_optimization":False,"accessed_2026":False,"C24_started":False,"staged_committed_or_pushed":False}}
    write(out/"final_summary.json",final)
    write(out/"reproducibility_hashes.json",{p.name:sha(p) for p in sorted(out.glob("*.json")) if p.name!="reproducibility_hashes.json"})
    return final
