"""C30 frozen fixed-endpoint opportunity prediction evaluation.

The eight labels are executable C0 returns at fixed endpoints.  They are not
threshold-touch, path, take-profit, or MFE labels.  This module implements one
prespecified causal feature matrix and one fixed L2 logistic model.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import platform
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from . import c29_opportunity_prevalence as c29
from .c2_common import iter_gzip_csv
from .c2_entries import hourly_sma24
from .ingest import sha256_file

CONTRACT_REL = "contracts/C30_opportunity_prediction_CONTRACT.md"
CONTRACT_SHA256 = "c4ea08332831f7deebd9c8cacfadf8b0d9ba3230e444be05ca510652ee38d64f"
OUTPUT_REL = "artifacts/c30_opportunity_prediction"
TASKS = tuple(f"H{h}_{label}" for h in c29.HORIZONS for label in c29.HURDLES)
VALIDATION_START_2024 = 1719792000000  # 2024-07-01 00:00:00 UTC
VALIDATION_START_2025 = 1735689600000  # 2025-01-01 00:00:00 UTC
SEED = 20260929
REPLICATES = 2000
SYMBOLS = tuple(sorted(c29.EXPECTED_SYMBOLS))

LOCAL_FEATURES = (
    "local_close_over_sma24", "local_sma24_slope", "local_return_1h",
    "local_return_3h", "local_return_6h", "local_return_12h", "local_return_24h",
    "local_realized_volatility_6h", "local_realized_volatility_12h",
    "local_realized_volatility_24h", "cross_previous_close_over_sma24",
    "cross_current_close_over_sma24", "cross_geometry_change",
)
BTC_FEATURES = (
    "btc_return_1h", "btc_return_3h", "btc_return_6h", "btc_return_12h",
    "btc_return_24h", "btc_realized_volatility_6h", "btc_realized_volatility_24h",
    "btc_close_over_sma24", "btc_sma24_slope",
)
RELATIVE_FEATURES = tuple(f"relative_to_btc_return_{h}h" for h in (1, 3, 6, 12, 24))
CROSS_ASSET_FEATURES = (
    "universe_positive_return_fraction_1h", "universe_positive_return_fraction_3h",
    "universe_positive_return_fraction_6h", "universe_above_sma24_fraction",
    "universe_mean_return_1h", "universe_mean_return_3h", "universe_mean_return_6h",
)
FEATURES = LOCAL_FEATURES + BTC_FEATURES + RELATIVE_FEATURES + CROSS_ASSET_FEATURES
MODEL_SPEC = {"estimator": "LogisticRegression", "penalty": "l2", "C": 1.0,
              "solver": "lbfgs", "max_iter": 10000, "class_weight": None,
              "random_state": None, "tol": 1e-6}


class StandardScaler:
    def fit(self, x):
        x=np.asarray(x,float); self.mean_=x.mean(0); self.scale_=x.std(0); self.scale_[self.scale_==0]=1.; return self
    def transform(self, x): return (np.asarray(x,float)-self.mean_)/self.scale_


class LogisticRegression:
    """Binary L2 logistic regression with deterministic L-BFGS."""
    def __init__(self, penalty="l2", C=1., solver="lbfgs", max_iter=10000, class_weight=None, random_state=None, tol=1e-6):
        if (penalty,solver,class_weight)!=("l2","lbfgs",None): raise ValueError("frozen model specification violated")
        self.C=float(C); self.max_iter=int(max_iter); self.tol=float(tol)
    @staticmethod
    def _fg(theta,x,y,C):
        z=np.clip(theta[0]+x@theta[1:],-40,40); p=1/(1+np.exp(-z)); n=len(y)
        value=float(np.mean(np.logaddexp(0,z)-y*z)+np.dot(theta[1:],theta[1:])/(2*C*n))
        residual=(p-y)/n; grad=np.r_[residual.sum(),x.T@residual+theta[1:]/(C*n)]
        return value,grad
    def fit(self,x,y):
        x=np.asarray(x,float); y=np.asarray(y,float); theta=np.zeros(x.shape[1]+1); history=[]; converged=False
        value,grad=self._fg(theta,x,y,self.C)
        for iteration in range(1,self.max_iter+1):
            q=grad.copy(); alphas=[]
            for s,yy,rho in reversed(history):
                a=rho*np.dot(s,q); alphas.append(a); q-=a*yy
            gamma=(np.dot(history[-1][0],history[-1][1])/max(np.dot(history[-1][1],history[-1][1]),1e-30)) if history else 1.
            direction=-gamma*q
            for (s,yy,rho),a in zip(history,reversed(alphas)):
                b=rho*np.dot(yy,direction); direction+=s*(a-b)
            if np.dot(direction,grad)>=0: direction=-grad
            step=1.; directional=np.dot(grad,direction)
            while step>1e-14:
                candidate=theta+step*direction; new_value,new_grad=self._fg(candidate,x,y,self.C)
                if new_value <= value+1e-4*step*directional: break
                step*=.5
            s=candidate-theta; yy=new_grad-grad; curvature=np.dot(s,yy)
            if curvature>1e-14: history=(history+[(s,yy,1/curvature)])[-10:]
            theta,value,grad=candidate,new_value,new_grad
            if np.max(np.abs(grad))<self.tol or np.max(np.abs(s))<1e-10: converged=True; break
        self.intercept_=np.asarray([theta[0]]); self.coef_=theta[1:][None,:]; self.n_iter_=np.asarray([iteration]); self.converged_=converged; self.gradient_max_=float(np.max(np.abs(grad)))
        return self
    def predict_proba(self,x):
        z=np.clip(self.intercept_[0]+np.asarray(x)@self.coef_[0],-40,40); p=1/(1+np.exp(-z)); return np.column_stack((1-p,p))


def _average_ranks(values):
    values=np.asarray(values); order=np.argsort(values,kind="mergesort"); ranks=np.empty(len(values),float); i=0
    while i<len(values):
        j=i+1
        while j<len(values) and values[order[j]]==values[order[i]]: j+=1
        ranks[order[i:j]]=(i+j-1)/2+1; i=j
    return ranks


def roc_auc_score(y,p):
    y=np.asarray(y,int); ranks=_average_ranks(p); n1=y.sum(); n0=len(y)-n1
    return float((ranks[y==1].sum()-n1*(n1+1)/2)/(n1*n0))


def average_precision_score(y,p):
    y=np.asarray(y,int); ys=y[np.argsort(-np.asarray(p),kind="mergesort")]; positives=ys.sum()
    return float(np.sum((ys==1)*np.cumsum(ys)/(np.arange(len(ys))+1))/positives)


def _spearman(a,b):
    ra,rb=_average_ranks(a),_average_ranks(b)
    return None if np.std(ra)==0 or np.std(rb)==0 else float(np.corrcoef(ra,rb)[0,1])


def reject_prohibited_path(path: os.PathLike | str) -> None:
    """Reject market-data paths containing a prohibited post-study year."""
    if any(part == "2026" or part.startswith("2026-") for part in os.fspath(path).replace("\\", "/").lower().split("/")):
        raise PermissionError("C30 prohibits post-2025 market data access")


def _write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _iso(ms: int | None) -> str | None:
    return datetime.fromtimestamp(ms / 1000, timezone.utc).isoformat() if ms is not None else None


def _sha(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _quantile(values, q):
    return float(np.quantile(np.asarray(values, float), q, method="linear")) if len(values) else None


def _load_hourly(repo: Path) -> dict[str, list[dict]]:
    result = {}
    for symbol in SYMBOLS:
        path = repo / "data/normalized/c2_frozen_inputs" / f"{symbol}_1h.csv.gz"
        reject_prohibited_path(path)
        rows = [r for r in iter_gzip_csv(path) if int(r["open_time_ms"]) < c29.END_MS]
        if any(int(r["available_at_ms"]) != int(r["open_time_ms"]) + 3_600_000 for r in rows):
            raise RuntimeError("non-causal hourly availability")
        result[symbol] = rows
    return result


def _hour_states(hourly: dict[str, list[dict]]) -> dict[str, dict[int, dict]]:
    """Index causal states by completed-bar availability timestamp."""
    output = {}
    for symbol, rows in hourly.items():
        closes = np.asarray([float(r["close"]) for r in rows])
        smas = hourly_sma24(rows)
        states = {}
        for i, row in enumerate(rows):
            if i < 24 or smas[i] is None or smas[i - 1] is None:
                continue
            rets = {h: float(closes[i] / closes[i-h] - 1) for h in (1, 3, 6, 12, 24)}
            hourly_returns = closes[1:i+1] / closes[:i] - 1
            vols = {h: float(np.std(hourly_returns[-h:], ddof=0)) for h in (6, 12, 24)}
            current = float(closes[i] / smas[i] - 1)
            previous = float(closes[i-1] / smas[i-1] - 1)
            states[int(row["available_at_ms"])] = {
                "returns": rets, "volatility": vols, "close_over_sma24": current,
                "sma24_slope": float(smas[i] / smas[i-1] - 1),
                "previous_close_over_sma24": previous, "geometry_change": current - previous,
                "source_open_ms": int(row["open_time_ms"]), "available_at_ms": int(row["available_at_ms"]),
            }
        output[symbol] = states
    return output


def build_feature_rows(entries: list[dict], states: dict[str, dict[int, dict]]) -> tuple[list[dict], dict]:
    rows, missing = [], []
    for entry in entries:
        ms, symbol = int(entry["entry_execution_ms"]), entry["symbol"]
        local = states[symbol].get(ms); btc = states["BTCUSDT"].get(ms)
        universe = [states[s].get(ms) for s in SYMBOLS]
        if local is None or btc is None or any(s is None for s in universe):
            missing.append({"trade_id": entry["trade_id"], "entry_ms": ms, "reason": "required_completed_history_unavailable"})
            continue
        f = {
            "local_close_over_sma24": local["close_over_sma24"], "local_sma24_slope": local["sma24_slope"],
            **{f"local_return_{h}h": local["returns"][h] for h in (1, 3, 6, 12, 24)},
            **{f"local_realized_volatility_{h}h": local["volatility"][h] for h in (6, 12, 24)},
            "cross_previous_close_over_sma24": local["previous_close_over_sma24"],
            "cross_current_close_over_sma24": local["close_over_sma24"],
            "cross_geometry_change": local["geometry_change"],
            **{f"btc_return_{h}h": btc["returns"][h] for h in (1, 3, 6, 12, 24)},
            "btc_realized_volatility_6h": btc["volatility"][6],
            "btc_realized_volatility_24h": btc["volatility"][24],
            "btc_close_over_sma24": btc["close_over_sma24"], "btc_sma24_slope": btc["sma24_slope"],
            **{f"relative_to_btc_return_{h}h": local["returns"][h] - btc["returns"][h] for h in (1, 3, 6, 12, 24)},
            **{f"universe_positive_return_fraction_{h}h": sum(s["returns"][h] > 0 for s in universe) / 5 for h in (1, 3, 6)},
            "universe_above_sma24_fraction": sum(s["close_over_sma24"] > 0 for s in universe) / 5,
            **{f"universe_mean_return_{h}h": statistics.fmean(s["returns"][h] for s in universe) for h in (1, 3, 6)},
        }
        if tuple(f) != FEATURES or not all(np.isfinite(list(f.values()))):
            raise RuntimeError("frozen feature schema violation")
        rows.append({"trade_id": entry["trade_id"], "symbol": symbol, "entry_ms": ms,
                     "entry_month": datetime.fromtimestamp(ms/1000, timezone.utc).strftime("%Y-%m"),
                     "features": f, "max_source_available_at_ms": max(s["available_at_ms"] for s in universe),
                     "max_source_bar_open_ms": max(s["source_open_ms"] for s in universe)})
    return rows, {"source_entries": len(entries), "complete_feature_rows": len(rows),
                  "excluded_rows": len(missing), "exclusions": missing}


def attach_outcomes(feature_rows: list[dict], horizon_rows: dict[int, list[dict]]) -> tuple[list[dict], dict]:
    lookup = {(h, r["trade_id"]): r for h, rr in horizon_rows.items() for r in rr}
    rows = []
    for base in feature_rows:
        r = dict(base); r["tasks"] = {}
        for h in c29.HORIZONS:
            endpoint = lookup.get((h, base["trade_id"]))
            for label in c29.HURDLES:
                task = f"H{h}_{label}"
                r["tasks"][task] = None if endpoint is None else {
                    "label": int(endpoint["labels"][label]), "resolution_ms": endpoint["exit_fill_ms"],
                    "returns": {k: endpoint["returns"][k] for k in ("C0", "DESIGN_BNB", "C_BASE")},
                }
        rows.append(r)
    reconciliation = {}
    for task in TASKS:
        h = int(task.split("_")[0][1:]); label = task.split("_", 1)[1]
        rr = [r for r in rows if r["tasks"][task] is not None]
        expected = horizon_rows[h]
        exact = (len(rr) == len(expected) and all(r["tasks"][task]["label"] == int(lookup[(h, r["trade_id"])]["labels"][label]) for r in rr))
        reconciliation[task] = {"valid_count": len(rr), "c29_valid_count": len(expected), "exact": exact,
            "positive_count": sum(r["tasks"][task]["label"] for r in rr),
            "fixed_endpoint_only": True, "threshold": c29.HURDLES[label]}
    return rows, reconciliation


def make_folds(rows: list[dict]) -> tuple[dict, dict]:
    folds, reports = {}, {}
    for task in TASKS:
        folds[task], reports[task] = {}, {}
        eligible = [r for r in rows if r["tasks"][task] is not None]
        for year, start, end in ((2024, VALIDATION_START_2024, VALIDATION_START_2025),
                                 (2025, VALIDATION_START_2025, c29.END_MS)):
            train = [r for r in eligible if r["entry_ms"] < start and r["tasks"][task]["resolution_ms"] < start]
            if year == 2025:
                train = [r for r in train if datetime.fromtimestamp(r["entry_ms"]/1000, timezone.utc).year == 2024]
            else:
                train = [r for r in train if datetime.fromtimestamp(r["entry_ms"]/1000, timezone.utc).year == 2024]
            valid = [r for r in eligible if start <= r["entry_ms"] < end]
            if len({r["tasks"][task]["label"] for r in train}) < 2:
                raise RuntimeError(f"INSUFFICIENT_TASK_TRAINING: {task} {year}")
            folds[task][year] = (train, valid)
            reports[task][str(year)] = {
                "training_rows": len(train), "validation_rows": len(valid),
                "training_positive_prevalence": statistics.fmean(r["tasks"][task]["label"] for r in train),
                "validation_positive_prevalence": statistics.fmean(r["tasks"][task]["label"] for r in valid),
                "earliest_training_entry": _iso(min(r["entry_ms"] for r in train)),
                "latest_training_entry": _iso(max(r["entry_ms"] for r in train)),
                "latest_training_label_resolution": _iso(max(r["tasks"][task]["resolution_ms"] for r in train)),
                "earliest_validation_entry": _iso(min(r["entry_ms"] for r in valid)),
                "latest_validation_entry": _iso(max(r["entry_ms"] for r in valid)),
                "validation_start": _iso(start), "all_training_labels_resolved_strictly_before_start": True,
            }
    return folds, reports


def _calibration(y: np.ndarray, p: np.ndarray) -> dict:
    bins = []
    for i in range(10):
        lo, hi = i / 10, (i + 1) / 10
        ix = np.flatnonzero((p >= lo) & ((p < hi) if i < 9 else (p <= hi)))
        bins.append({"bin": i + 1, "lower": lo, "upper": hi, "count": int(len(ix)),
                     "prediction_mean": float(np.mean(p[ix])) if len(ix) else None,
                     "actual_prevalence": float(np.mean(y[ix])) if len(ix) else None})
    ece = sum(b["count"] / len(y) * abs(b["prediction_mean"] - b["actual_prevalence"]) for b in bins if b["count"])
    z = np.log(np.clip(p, 1e-12, 1-1e-12) / np.clip(1-p, 1e-12, 1))
    x = np.column_stack((np.ones(len(y)), z)); beta = np.array([0., 1.]); converged = False
    for _ in range(100):
        q = 1 / (1 + np.exp(-np.clip(x @ beta, -35, 35)))
        grad = x.T @ (q-y); hess = x.T @ (x * (q*(1-q))[:, None])
        step = np.linalg.solve(hess + np.eye(2)*1e-12, grad); beta -= step
        if np.max(np.abs(step)) < 1e-10: converged = True; break
    return {"prediction_mean": float(np.mean(p)), "actual_prevalence": float(np.mean(y)),
            "calibration_intercept": float(beta[0]) if converged and np.max(np.abs(beta)) < 100 else None,
            "calibration_slope": float(beta[1]) if converged and np.max(np.abs(beta)) < 100 else None,
            "diagnostic_only_no_recalibration": True, "ece_10_equal_width_bins": float(ece), "bins": bins}


def metric_values(y, p, baseline) -> dict:
    y=np.asarray(y, int); p=np.clip(np.asarray(p, float), 1e-15, 1-1e-15); b=np.full(len(y), baseline)
    bm=float(np.mean((b-y)**2)); mm=float(np.mean((p-y)**2))
    bl=float(np.mean(-(y*np.log(b)+(1-y)*np.log(1-b)))); ml=float(np.mean(-(y*np.log(p)+(1-y)*np.log(1-p))))
    return {"brier_baseline": bm, "brier_model": mm, "delta_brier": bm-mm,
            "log_loss_baseline": bl, "log_loss_model": ml, "delta_logloss": bl-ml,
            "roc_auc": float(roc_auc_score(y,p)) if len(set(y)) == 2 else None,
            "pr_auc": float(average_precision_score(y,p)) if len(set(y)) == 2 else None}


def probability_boundaries(train_predictions: np.ndarray) -> dict:
    """Training-only equal-count intent; equal values are assigned together."""
    values = np.sort(np.unique(train_predictions))
    cuts = []
    for q in (.2, .4, .6, .8):
        target = float(np.quantile(train_predictions, q, method="higher"))
        candidates = values[values >= target]
        cut = float(candidates[0] if len(candidates) else values[-1])
        if not cuts or cut > cuts[-1]: cuts.append(cut)
    if len(cuts) != 4:
        raise RuntimeError("training predictions cannot support five unsplit groups")
    return {"cut_points_upper_inclusive_for_lower_group": cuts, "groups": ["P1", "P2", "P3", "P4", "P5"],
            "learned_from_training_predictions_only": True, "ties_never_split": True}


def assign_groups(predictions, boundary: dict) -> list[str]:
    cuts = boundary["cut_points_upper_inclusive_for_lower_group"]
    return [f"P{int(np.searchsorted(cuts, p, side='left'))+1}" for p in predictions]


def fit_all(folds: dict) -> tuple[dict, dict, dict, dict, dict]:
    predictions, metrics, calibration, boundaries, coefficients = {}, {}, {}, {}, {}
    for task in TASKS:
        predictions[task] = {}; metrics[task] = {}; calibration[task] = {}; boundaries[task] = {}; coefficients[task] = {}
        for year in (2024, 2025):
            train, valid = folds[task][year]
            xt=np.asarray([[r["features"][f] for f in FEATURES] for r in train]); xv=np.asarray([[r["features"][f] for f in FEATURES] for r in valid])
            yt=np.asarray([r["tasks"][task]["label"] for r in train]); yv=np.asarray([r["tasks"][task]["label"] for r in valid])
            scaler=StandardScaler().fit(xt); model=LogisticRegression(**{k:v for k,v in MODEL_SPEC.items() if k != "estimator"}).fit(scaler.transform(xt),yt)
            if not model.converged_: raise RuntimeError(f"logistic model did not converge: {task} {year}, iterations={model.n_iter_[0]}, gradient={model.gradient_max_}")
            pt=model.predict_proba(scaler.transform(xt))[:,1]; pv=model.predict_proba(scaler.transform(xv))[:,1]
            baseline=float(np.mean(yt)); boundary=probability_boundaries(pt); groups=assign_groups(pv,boundary)
            predictions[task][year] = [{"trade_id":r["trade_id"], "symbol":r["symbol"], "entry_ms":r["entry_ms"], "entry_month":r["entry_month"],
                "label":int(y), "probability":float(p), "baseline":baseline, "group":g, "returns":r["tasks"][task]["returns"]}
                for r,y,p,g in zip(valid,yv,pv,groups)]
            metrics[task][str(year)] = {"training_prevalence_baseline":baseline, **metric_values(yv,pv,baseline)}
            calibration[task][str(year)] = _calibration(yv,pv)
            boundaries[task][str(year)] = boundary | {"training_prediction_count":len(pt), "training_group_counts":dict(Counter(assign_groups(pt,boundary)))}
            coefficients[task][str(year)] = {"intercept":float(model.intercept_[0]), "standardized_coefficients":dict(zip(FEATURES,map(float,model.coef_[0]))),
                "scaler_training_means":dict(zip(FEATURES,map(float,scaler.mean_))), "scaler_training_scales":dict(zip(FEATURES,map(float,scaler.scale_))),
                "iterations":int(model.n_iter_[0]), "converged":True}
    return predictions, metrics, calibration, boundaries, coefficients


def _distribution(rr: list[dict], cost: str, include_opportunity: bool) -> dict:
    values=[r["returns"][cost] for r in rr]; pos=[x for x in values if x>0]; neg=[x for x in values if x<0]
    out={"trade_count":len(rr), "mean":statistics.fmean(values) if values else None, "median":statistics.median(values) if values else None,
         "p10":_quantile(values,.1), "positive_fraction":len(pos)/len(values) if values else None,
         "negative_fraction":len(neg)/len(values) if values else None,
         "mean_positive_return":statistics.fmean(pos) if pos else None, "mean_negative_return":statistics.fmean(neg) if neg else None,
         "total_positive_contribution":float(sum(pos)), "total_negative_contribution":float(sum(neg)), "net_contribution":float(sum(values))}
    if cost == "C0": out.update({"p25":_quantile(values,.25),"p75":_quantile(values,.75),"p90":_quantile(values,.9)})
    if include_opportunity: out.update({"opportunity_positive_count":sum(r["label"] for r in rr), "opportunity_rate":statistics.fmean(r["label"] for r in rr) if rr else None})
    if cost != "C0": out["mean_loss_among_negative_return_trades"] = statistics.fmean(neg) if neg else None
    return out


def economic_documents(predictions: dict) -> tuple[dict, dict, dict, dict]:
    docs={c:{} for c in ("C0","DESIGN_BNB","C_BASE")}; ordering={}
    for task in TASKS:
        ordering[task]={}
        for c in docs: docs[c][task]={}
        for year in (2024,2025):
            rr=predictions[task][year]
            grouped={g:[r for r in rr if r["group"]==g] for g in ("P1","P2","P3","P4","P5")}
            for c in docs: docs[c][task][str(year)]={g:_distribution(x,c,c=="C0") for g,x in grouped.items()}
            def rho(c): return _spearman([r["probability"] for r in rr],[r["returns"][c] for r in rr])
            p1,p5=grouped["P1"],grouped["P5"]
            ordering[task][str(year)]={"spearman_probability_C0":rho("C0"),"spearman_probability_DESIGN_BNB":rho("DESIGN_BNB"),
                "groups":{g:{"count":len(x),"opportunity_rate":statistics.fmean(r["label"] for r in x),
                    **{f"mean_{c}":statistics.fmean(r["returns"][c] for r in x) for c in ("C0","DESIGN_BNB","C_BASE")}} for g,x in grouped.items()},
                "P5_minus_P1":{"opportunity_rate":statistics.fmean(r["label"] for r in p5)-statistics.fmean(r["label"] for r in p1),
                    **{f"mean_{c}":statistics.fmean(r["returns"][c] for r in p5)-statistics.fmean(r["returns"][c] for r in p1) for c in ("C0","DESIGN_BNB","C_BASE")}}}
    return docs["C0"],docs["DESIGN_BNB"],docs["C_BASE"],ordering


def _replicate_metrics(rr, indices):
    sample=[rr[i] for i in indices]; y=[r["label"] for r in sample]; p=[r["probability"] for r in sample]; baseline=rr[0]["baseline"]
    return metric_values(y,p,baseline)


def bootstrap_documents(predictions: dict, unit: str) -> tuple[dict, dict]:
    predictive, economic = {}, {}
    for year in (2024,2025):
        # One joint universe and one draw sequence preserves all tasks together.
        universe=sorted({r["trade_id"] for t in TASKS for r in predictions[t][year]})
        month={r["trade_id"]:r["entry_month"] for t in TASKS for r in predictions[t][year]}
        keys=universe if unit=="whole_trade" else sorted(set(month.values()))
        rng=np.random.Generator(np.random.PCG64(SEED+year+(0 if unit=="whole_trade" else 10000)))
        draws=[rng.integers(len(keys),size=len(keys)) for _ in range(REPLICATES)]
        predictive[str(year)]={}; economic[str(year)]={}
        for task in TASKS:
            rr=predictions[task][year]; by_trade={r["trade_id"]:i for i,r in enumerate(rr)}
            groups=defaultdict(list)
            for i,r in enumerate(rr): groups[r["trade_id"] if unit=="whole_trade" else r["entry_month"]].append(i)
            metric_samples={k:[] for k in ("delta_brier","delta_logloss","roc_auc","pr_auc")}; econ_samples={k:[] for k in ("opportunity_rate","mean_C0","mean_DESIGN_BNB","mean_C_BASE")}
            for draw in draws:
                sampled=[]
                for j in draw:
                    key=keys[int(j)]
                    if unit=="whole_trade":
                        if key in by_trade: sampled.append(by_trade[key])
                    else: sampled.extend(groups.get(key,[]))
                m=_replicate_metrics(rr,sampled)
                for k in metric_samples:
                    if m[k] is not None: metric_samples[k].append(m[k])
                sample=[rr[i] for i in sampled]; p1=[r for r in sample if r["group"]=="P1"]; p5=[r for r in sample if r["group"]=="P5"]
                if p1 and p5:
                    econ_samples["opportunity_rate"].append(statistics.fmean(r["label"] for r in p5)-statistics.fmean(r["label"] for r in p1))
                    for c in ("C0","DESIGN_BNB","C_BASE"): econ_samples[f"mean_{c}"].append(statistics.fmean(r["returns"][c] for r in p5)-statistics.fmean(r["returns"][c] for r in p1))
            predictive[str(year)][task]={k:{"ci95":[_quantile(v,.025),_quantile(v,.975)],"valid_replicates":len(v),"replicate_sha256":hashlib.sha256(np.asarray(v,dtype="<f8").tobytes()).hexdigest()} for k,v in metric_samples.items()}
            economic[str(year)][task]={k:{"ci95":[_quantile(v,.025),_quantile(v,.975)],"valid_replicates":len(v),"replicate_sha256":hashlib.sha256(np.asarray(v,dtype="<f8").tobytes()).hexdigest()} for k,v in econ_samples.items()}
    header={"unit":unit,"replicates":REPLICATES,"generator":"PCG64","predictions_frozen_before_bootstrap":True,"model_refit":False,"joint_task_draws":True}
    return header|{"results":predictive},header|{"results":economic}


def symbol_diagnostics(predictions: dict) -> dict:
    out={}
    for task in TASKS:
        out[task]={}
        for year in (2024,2025):
            out[task][str(year)]={}
            for s in SYMBOLS:
                rr=[r for r in predictions[task][year] if r["symbol"]==s]; y=[r["label"] for r in rr]; p=[r["probability"] for r in rr]
                item={"count":len(rr),"prevalence":statistics.fmean(y),"mean_predicted_probability":statistics.fmean(p),**metric_values(y,p,rr[0]["baseline"])}
                p1=[r for r in rr if r["group"]=="P1"]; p5=[r for r in rr if r["group"]=="P5"]
                item["P5_minus_P1_opportunity_rate"]=(statistics.fmean(r["label"] for r in p5)-statistics.fmean(r["label"] for r in p1)) if p1 and p5 else None
                out[task][str(year)][s]=item
    return out


def interpretation(metrics, ordering, whole_boot, month_boot, economics_design, symbols) -> dict:
    both_brier=[t for t in TASKS if all(metrics[t][str(y)]["delta_brier"]>0 for y in (2024,2025))]
    both_log=[t for t in TASKS if all(metrics[t][str(y)]["delta_logloss"]>0 for y in (2024,2025))]
    enrich=[t for t in TASKS if all(ordering[t][str(y)]["P5_minus_P1"]["opportunity_rate"]>0 for y in (2024,2025))]
    material=[t for t in TASKS if whole_boot["results"]["2025"][t]["delta_brier"]["ci95"][1]<0 or whole_boot["results"]["2025"][t]["delta_logloss"]["ci95"][1]<0]
    supportive=sum(month_boot["results"][str(y)][t][k]["ci95"][0]>0 for y in (2024,2025) for t in TASKS for k in ("delta_brier","delta_logloss")) >= 16
    downside_ok=True
    for t in TASKS:
        for y in (2024,2025):
            p1=economics_design[t][str(y)]["P1"]["mean_loss_among_negative_return_trades"]
            p5=economics_design[t][str(y)]["P5"]["mean_loss_among_negative_return_trades"]
            if p1 is not None and p5 is not None and abs(p5)>1.5*abs(p1): downside_ok=False
    symbol_ok=all(sum(symbols[t]["2025"][s]["delta_brier"]>0 for s in SYMBOLS)>=3 for t in both_brier)
    criteria={"brier_positive_both_years_count":len(both_brier),"logloss_positive_both_years_count":len(both_log),
        "materially_negative_2025_tasks":material,"dependence_aware_majority_directionally_supportive":supportive,
        "P5_P1_positive_both_years_count":len(enrich),"no_dramatically_worse_P5_negative_mean_1_5x_rule":downside_ok,
        "not_obviously_one_symbol_2025_at_least_3_positive_symbol_deltas":symbol_ok}
    supported=len(both_brier)>=6 and len(both_log)>=6 and len(material)<=1 and supportive and len(enrich)>=6 and downside_ok and symbol_ok
    generally_positive=sum(metrics[t][str(y)]["delta_brier"]>0 and metrics[t][str(y)]["delta_logloss"]>0 for t in TASKS for y in (2024,2025))>=8
    classification="OPPORTUNITY_PREDICTION_SUPPORTED" if supported else ("WEAK_OPPORTUNITY_PREDICTION_SIGNAL" if generally_positive or len(enrich)>=4 else "NO_USEFUL_OPPORTUNITY_PREDICTION_SIGNAL")
    return {"classification":classification,"criteria":criteria,"materially_negative_definition":"whole-trade 95% CI upper bound below zero for either proper-score improvement",
        "directionally_supportive_definition":"at least half of 32 task/year/proper-score calendar-month CI lower bounds exceed zero",
        "dramatically_worse_downside_definition":"P5 absolute DESIGN_BNB mean loss exceeds 1.5 times P1", "predicates_frozen_in_implementation_before_results":True}


def run(repo: Path) -> dict:
    repo=repo.resolve(); reject_prohibited_path(repo)
    if os.environ.get("CONDA_DEFAULT_ENV") != "binance-v2-research": raise RuntimeError("conda environment must be binance-v2-research")
    if sha256_file(repo/CONTRACT_REL) != CONTRACT_SHA256: raise RuntimeError("C30 contract changed after prospective freeze")
    entries,population,opens=c29._load_and_reconcile(repo); horizon_rows,coverage=c29.build_rows(entries,opens)
    hourly=_load_hourly(repo); states=_hour_states(hourly); feature_rows,feature_summary=build_feature_rows(entries,states)
    rows,label_rec=attach_outcomes(feature_rows,horizon_rows)
    if not all(x["exact"] for x in label_rec.values()): raise RuntimeError("INSUFFICIENT_RECONCILIATION")
    folds,fold_report=make_folds(rows); predictions,metrics,calibration,boundaries,coefficients=fit_all(folds)
    econ0,econbnb,econbase,ordering=economic_documents(predictions)
    whole,econwhole=bootstrap_documents(predictions,"whole_trade"); month,econmonth=bootstrap_documents(predictions,"UTC_entry_calendar_month")
    symbols=symbol_diagnostics(predictions); predicates=interpretation(metrics,ordering,whole,month,econbnb,symbols)
    schema={"features":list(FEATURES),"feature_count":len(FEATURES),"identical_for_all_tasks":True,"no_additional_features":True,
        "families":{"local":list(LOCAL_FEATURES),"btc_context":list(BTC_FEATURES),"relative_to_btc":list(RELATIVE_FEATURES),"cross_asset_confirmation":list(CROSS_ASSET_FEATURES)}}
    timing={"decision_time":"completed E1 hourly bar available_at_ms","feature_source":"completed 1h bars only","latest_feature_timestamp_lte_entry_decision":all(r["max_source_available_at_ms"]<=r["entry_ms"] for r in rows),
        "latest_source_bar_open_strictly_before_entry":all(r["max_source_bar_open_ms"]<r["entry_ms"] for r in rows),"entry_fill_future_used":False,"future_minute_bars_used":False,"MFE_used":False,
        "P0_or_T2_used":False,"future_cross_asset_movement_used":False,"validation_labels_used":False,"realized_volatility_ddof":0}
    chronology={"validation_start_2024":_iso(VALIDATION_START_2024),"validation_start_2025":_iso(VALIDATION_START_2025),"training_rule":"entry before validation start AND task label resolution strictly before validation start",
        "2025_training":"eligible 2024 only","2025_refit":False,"rolling_retraining":False,"task_specific_resolution":True}
    baseline={t:{str(y):{"training_prevalence":metrics[t][str(y)]["training_prevalence_baseline"],"constant_validation_probability":True,"validation_labels_used":False} for y in (2024,2025)} for t in TASKS}
    label_doc={"tasks":list(TASKS),"reconciliation":label_rec,"coverage":coverage,"semantics":"1 iff executable C0 return at the fixed endpoint is >= hurdle; equality is positive","threshold_touch_or_MFE":False}
    final={"contract_sha256":CONTRACT_SHA256,"population_reconciliation":population,"label_reconciliation":label_doc,"feature_matrix_summary":feature_summary,"fold_reconciliation":fold_report,
        "task_metrics_2024":{t:metrics[t]["2024"] for t in TASKS},"task_metrics_2025":{t:metrics[t]["2025"] for t in TASKS},"interpretation_predicates":predicates,"classification":predicates["classification"],
        "eight_tasks_correlated":"Tasks share entries and regimes; hurdles are nested within horizon and horizons share overlapping future paths. Results are not independent replications.",
        "later_policy_research_scientifically_justified":predicates["classification"] != "NO_USEFUL_OPPORTUNITY_PREDICTION_SIGNAL",
        "confirmations":{"no_horizon_hurdle_probability_cutoff_model_feature_subset_or_strategy_selected":True,"no_profitability_or_deployment_claim":True,"no_model_feature_or_regularization_search":True,"no_PnL_optimization":True,"no_post_2025_access":True,"C31_started":False},
        "limitations":["observational historical evaluation","correlated tasks","fixed five-symbol universe","economic groups are descriptive and not policies"]}
    files={"run_manifest":{"version":"C30_RUN_V1","contract_sha256":CONTRACT_SHA256,"seed":SEED,"replicates":REPLICATES,"generator":"PCG64","python":sys.version,"numpy":np.__version__,"logistic_implementation":"local deterministic L-BFGS","platform":platform.platform(),"conda_environment":"binance-v2-research"},
        "provenance":{"contract_sha256":CONTRACT_SHA256,"frozen_entry_sha256":c29.ENTRY_SHA256,"C29_contract_sha256":c29.CONTRACT_SHA256,"C29_fixed_endpoint_accounting_reused":True,"no_post_2025_access":True},
        "population_reconciliation":population,"label_reconciliation":label_doc,"feature_schema":schema,"feature_timing_audit":timing,"feature_matrix_summary":feature_summary,"chronology_definition":chronology,"fold_reconciliation":fold_report,
        "training_prevalence_baselines":baseline,"model_specification":MODEL_SPEC|{"same_all_eight_tasks":True,"scaling":"StandardScaler fit on training only"},
        "task_metrics_2024":{t:metrics[t]["2024"] for t in TASKS},"task_metrics_2025":{t:metrics[t]["2025"] for t in TASKS},"calibration_results":calibration,
        "probability_group_boundaries":boundaries,"probability_group_results":{t:{str(y):ordering[t][str(y)]["groups"] for y in (2024,2025)} for t in TASKS},
        "economic_companion_c0":econ0,"economic_companion_design_bnb":econbnb,"economic_companion_cbase":econbase,"economic_ordering":ordering,
        "whole_trade_bootstrap":whole,"calendar_month_bootstrap":month,"economic_whole_trade_bootstrap":econwhole,"economic_calendar_month_bootstrap":econmonth,
        "symbol_diagnostics":symbols,"coefficients":coefficients,"interpretation_predicates":predicates,"final_summary":final}
    out=repo/OUTPUT_REL; out.mkdir(parents=True,exist_ok=True)
    for name,value in files.items(): _write(out/f"{name}.json",value)
    hashes={p.name:sha256_file(p) for p in sorted(out.glob("*.json")) if p.name!="reproducibility_hashes.json"}
    _write(out/"reproducibility_hashes.json",hashes)
    return final|{"artifact_hashes":hashes}


if __name__ == "__main__":
    result=run(Path.cwd())
    print(json.dumps({"classification":result["classification"],"contract_sha256":result["contract_sha256"]},sort_keys=True))
