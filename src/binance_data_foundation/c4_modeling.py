from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import platform
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from .c2_common import STUDY_END_MS, SYMBOLS, write_json
from .c4_adequacy import (
    ACCEPTED_CORE_HASHES, ADEQUACY_THRESHOLDS, BOOTSTRAP_CONFIG, FIVE_MINUTES,
    HOUR, MINUTE, T1, T2, _json_hash, load_inputs,
)
from .ingest import sha256_file

CONTRACT_HASH = "f9350da6b17c58de3bca4c0831bcaccf4838449575fe693dc573db72eb40bc39"
ADEQUACY_DECISION_HASH = "f4555db6dbccd9cb6b1506e642b49b6d21dd015d6737b76bd4534612bf32ffe7"
THRESHOLD_PANEL_HASH = "49aa5664c7361ad8049bedaee089adbabfe696e8e3a9122ab9d0feb4c7226d60"
BOOTSTRAP_DETAIL_HASH = "24391dca71c0a9b997bdfa3c06804ed3c4195ce18c521d87c2afc551dbabc359"
MODEL_VERSION = "C4_2024_MULTINOMIAL_LOGIT_V1"
CLASSES = {
    "T1": ("continuation", "adverse_reversal", "no_event_60m"),
    "T2": ("renewed_peak", "substantial_giveback", "no_event_60m"),
}
FOLDS = {
    "fold_A": (1704067200000, 1719792000000, 1727740800000),
    "fold_B": (1704067200000, 1727740800000, 1735689600000),
}
SOLVER = {
    "name": "numpy_reference_class_damped_newton",
    "penalty": "l2_continuous_and_symbol_coefficients_intercept_unpenalized",
    "class_handling": "multinomial_reference_last_class",
    "max_iter": 60,
    "gradient_tolerance": 1e-8,
    "step_halving_max": 25,
    "hessian_ridge": 1e-10,
    "random_state": None,
}

G0_CONTINUOUS = (
    "elapsed_log1p_5m", "current_unrealized_return", "realized_volatility_12",
    "calendar_month_sin", "calendar_month_cos", "btc_return_60m",
)
G1_EXTRA = {
    "T1": ("drawdown_from_running_peak", "peak_gain_retained_fraction"),
    "T2": ("drawdown_from_running_peak", "peak_gain_retained_fraction",
           "t2_upper_distance", "t2_lower_distance"),
}
P1_EXTRA = (
    "running_mae", "path_efficiency", "recent_return_5m", "recent_return_15m",
    "recent_return_30m", "momentum_acceleration", "positive_5m_count_6",
    "negative_5m_count_6", "zero_5m_count_6", "volatility_expansion_ratio",
    "range_ratio_5m", "quote_volume_ratio_5m", "trade_count_ratio_5m",
    "h1_close_distance_sma24", "h1_sma24_slope",
)


def semantic_hash(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
        allow_nan=False).encode()).hexdigest()


def _pre_value_2024(row: dict) -> None:
    """Reject predictive rows by timestamp metadata before feature values are read."""
    entry = int(row["entry_execution_ms"])
    snap = int(row["snapshot_ms"])
    if not (1704067200000 <= entry < 1735689600000):
        raise ValueError("C4 predictive checkpoint accepts 2024 entries only")
    if snap >= 1735689600000:
        raise ValueError("C4 predictive checkpoint accepts 2024 snapshots only")
    if snap >= STUDY_END_MS:
        raise ValueError("sealed-boundary rejection before predictive values")


def load_accepted_2024_rows(path: Path, expected_hash: str) -> list[dict]:
    if sha256_file(path) != expected_hash:
        raise ValueError(f"accepted core snapshot hash mismatch: {path}")
    out = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for raw in reader:
            # Timestamp/partition metadata is checked before numeric market values.
            if not raw["temporal_partition"].startswith("2024_"):
                continue
            _pre_value_2024(raw)
            if raw["target_eligible"] != "True" or raw["resolved"] != "True":
                continue
            row = dict(raw)
            for name in ("entry_execution_ms", "snapshot_ms", "common_horizon_end_ms",
                         "forward_start_ms", "forward_end_ms", "elapsed_5m_bars"):
                row[name] = int(float(row[name]))
            for name in ("entry_price", "snapshot_close", "elapsed_minutes", "upper_barrier",
                         "lower_barrier", "running_peak", "running_mfe", "current_return",
                         "drawdown_from_running_peak", "peak_gain_retained_fraction"):
                row[name] = float(row[name]) if row[name] != "" else math.nan
            out.append(row)
    return out


def _bar(series, start: int, minutes: int) -> dict | None:
    bars = [series.get(start + i * MINUTE) for i in range(minutes)]
    if any(x is None for x in bars):
        return None
    return {
        "open": bars[0]["open"], "high": max(x["high"] for x in bars),
        "low": min(x["low"] for x in bars), "close": bars[-1]["close"],
        "quote_volume": sum(x["quote_volume"] for x in bars),
        "trade_count": sum(x["trade_count"] for x in bars),
    }


def _sample_std(values) -> float:
    return float(np.std(np.asarray(values, dtype=float), ddof=1))


def causal_feature_row(row: dict, series, btc_series) -> dict | None:
    """Materialize features using intervals ending no later than snapshot t."""
    _pre_value_2024(row)
    t, entry = row["snapshot_ms"], row["entry_execution_ms"]
    five = {}
    # 26 completed bars cover range/activity medians and volatility evolution.
    for k in range(0, 26):
        end = t - k * FIVE_MINUTES
        b = _bar(series, end - FIVE_MINUTES, 5)
        if b is None:
            return None
        five[k] = b
    closes = [five[k]["close"] for k in range(25, -1, -1)]
    rets = [closes[i] / closes[i - 1] - 1 for i in range(1, len(closes))]
    latest12 = rets[-12:]
    latest6, prior6 = rets[-6:], rets[-12:-6]
    prior_ranges = [(five[k]["high"] - five[k]["low"]) / five[k]["open"] for k in range(1, 13)]
    current_range = (five[0]["high"] - five[0]["low"]) / five[0]["open"]
    qmed = float(np.median([five[k]["quote_volume"] for k in range(1, 13)]))
    tmed = float(np.median([five[k]["trade_count"] for k in range(1, 13)]))
    rmed = float(np.median(prior_ranges))
    pv = _sample_std(prior6)
    if pv == 0 or qmed == 0 or tmed == 0 or rmed == 0:
        return None

    # Post-entry, wholly completed 5m path sequence.
    first_end = ((entry + FIVE_MINUTES - 1) // FIVE_MINUTES) * FIVE_MINUTES
    if first_end - FIVE_MINUTES < entry:
        first_end += FIVE_MINUTES
    path_closes, path_lows = [], []
    end = first_end
    while end <= t:
        b = _bar(series, end - FIVE_MINUTES, 5)
        if b is None:
            return None
        path_closes.append(b["close"]); path_lows.append(b["low"])
        end += FIVE_MINUTES
    if len(path_closes) < 7:
        return None
    path_returns = [path_closes[i] / path_closes[i - 1] - 1 for i in range(1, len(path_closes))]
    abs_sum = float(np.sum(np.abs(path_returns)))
    if abs_sum == 0:
        return None

    # Latest completed hour is the hour ending at floor(t/hour)*hour.
    hour_end = (t // HOUR) * HOUR
    hourly = []
    for k in range(25, 0, -1):
        b = _bar(series, hour_end - k * HOUR, 60)
        if b is None:
            return None
        hourly.append(b["close"])
    sma_now = float(np.mean(hourly[-24:]))
    sma_prev = float(np.mean(hourly[-25:-1]))
    if sma_now == 0 or sma_prev == 0:
        return None

    btc_now = btc_series.get(t - MINUTE)
    btc_old = btc_series.get(t - 61 * MINUTE)
    if btc_now is None or btc_old is None:
        return None
    # Explicitly verify every intervening completed BTC minute.
    if any(btc_series.get(m) is None for m in range(t - 61 * MINUTE, t, MINUTE)):
        return None
    month = datetime.fromtimestamp(t / 1000, timezone.utc).month
    recent6 = path_returns[-6:]
    recent15 = path_closes[-1] / path_closes[-4] - 1
    prior15 = path_closes[-4] / path_closes[-7] - 1
    result = {
        "elapsed_log1p_5m": math.log1p(row["elapsed_minutes"] / 5),
        "current_unrealized_return": row["current_return"],
        "realized_volatility_12": _sample_std(latest12),
        "calendar_month_sin": math.sin(2 * math.pi * month / 12),
        "calendar_month_cos": math.cos(2 * math.pi * month / 12),
        "btc_return_60m": btc_now["close"] / btc_old["close"] - 1,
        "drawdown_from_running_peak": row["drawdown_from_running_peak"],
        "peak_gain_retained_fraction": row["peak_gain_retained_fraction"],
        "t2_upper_distance": (row["upper_barrier"] - row["snapshot_close"]) / row["snapshot_close"],
        "t2_lower_distance": (row["snapshot_close"] - row["lower_barrier"]) / row["snapshot_close"],
        "running_mae": min(path_lows) / row["entry_price"] - 1,
        "path_efficiency": row["current_return"] / abs_sum,
        "recent_return_5m": path_closes[-1] / path_closes[-2] - 1,
        "recent_return_15m": recent15,
        "recent_return_30m": path_closes[-1] / path_closes[-7] - 1,
        "momentum_acceleration": recent15 - prior15,
        "positive_5m_count_6": sum(x > 0 for x in recent6),
        "negative_5m_count_6": sum(x < 0 for x in recent6),
        "zero_5m_count_6": sum(x == 0 for x in recent6),
        "volatility_expansion_ratio": _sample_std(latest6) / pv,
        "range_ratio_5m": current_range / rmed,
        "quote_volume_ratio_5m": five[0]["quote_volume"] / qmed,
        "trade_count_ratio_5m": five[0]["trade_count"] / tmed,
        "h1_close_distance_sma24": hourly[-1] / sma_now - 1,
        "h1_sma24_slope": sma_now / sma_prev - 1,
    }
    if not all(math.isfinite(float(v)) for v in result.values()):
        return None
    return result


def feature_manifest(target: str) -> dict:
    symbols = tuple(f"symbol_{s}" for s in SYMBOLS[1:])
    g0 = symbols + G0_CONTINUOUS
    g1 = g0 + G1_EXTRA[target]
    p1 = g1 + P1_EXTRA
    families = ({x: "basic control" for x in g0} |
                {x: "geometry/current state" for x in G1_EXTRA[target]} |
                {x: "genuine path history" for x in P1_EXTRA})
    return {"G0": list(g0), "G1": list(g1), "P1": list(p1),
            "families": families, "strict_nesting": set(g0) < set(g1) < set(p1)}


def weighted_quantile(values, weights, row_ids, p):
    order = sorted(range(len(values)), key=lambda i: (float(values[i]), row_ids[i]))
    total = float(sum(weights)); cumulative = 0.0
    for i in order:
        cumulative += float(weights[i]) / total
        if cumulative >= p:
            return float(values[i])
    return float(values[order[-1]])


def trade_weights(rows) -> np.ndarray:
    counts = Counter(r["trade_id"] for r in rows)
    w = np.asarray([1.0 / counts[r["trade_id"]] for r in rows])
    sums = defaultdict(float)
    for r, x in zip(rows, w): sums[r["trade_id"]] += float(x)
    if max(abs(x - 1) for x in sums.values()) > 1e-12:
        raise AssertionError("equal-trade raw weights failed")
    return w


def fit_preprocessing(rows, features, columns, weights):
    row_ids = [r["row_id"] for r in rows]; params = {}; kept = []
    for col in columns:
        if col.startswith("symbol_"):
            kept.append(col); continue
        vals = np.asarray([features[r["row_id"]][col] for r in rows])
        med = weighted_quantile(vals, weights, row_ids, .5)
        q25 = weighted_quantile(vals, weights, row_ids, .25)
        q75 = weighted_quantile(vals, weights, row_ids, .75)
        iqr = q75 - q25
        params[col] = {"median": med, "q25": q25, "q75": q75, "iqr": iqr,
                       "excluded_zero_iqr": iqr == 0}
        if iqr != 0: kept.append(col)
    return params, kept


def matrix(rows, features, columns, preprocessing):
    x = np.empty((len(rows), len(columns)), dtype=float)
    for j, col in enumerate(columns):
        if col.startswith("symbol_"):
            x[:, j] = [r["symbol"] == col[7:] for r in rows]
        else:
            p = preprocessing[col]
            x[:, j] = [(features[r["row_id"]][col] - p["median"]) / p["iqr"] for r in rows]
    return np.column_stack((np.ones(len(rows)), x))


@dataclass
class MultinomialFit:
    coef: np.ndarray
    converged: bool
    iterations: int
    gradient_max: float
    objective: float


def _softmax_ref(x, coef):
    eta = x @ coef
    eta = np.column_stack((eta, np.zeros(len(x))))
    eta -= np.max(eta, axis=1, keepdims=True)
    e = np.exp(eta)
    return e / np.sum(e, axis=1, keepdims=True)


def fit_multinomial(x, y, weights, classes, C) -> MultinomialFit:
    n, p = x.shape; k = len(classes); coef = np.zeros((p, k - 1))
    penalty = np.ones(p); penalty[0] = 0
    w = weights * (n / weights.sum())
    def objective(b):
        prob = np.clip(_softmax_ref(x, b), 1e-15, 1)
        return float(-np.sum(w * np.log(prob[np.arange(n), y])) / n +
                     .5 * np.sum((b * penalty[:, None]) ** 2) / C)
    converged = False; grad_max = math.inf
    for iteration in range(1, SOLVER["max_iter"] + 1):
        prob = _softmax_ref(x, coef)
        yy = np.eye(k)[y][:, :k-1]
        grad = x.T @ (w[:, None] * (prob[:, :k-1] - yy)) / n
        grad += coef * penalty[:, None] / C
        grad_max = float(np.max(np.abs(grad)))
        if grad_max <= SOLVER["gradient_tolerance"]:
            converged = True; break
        h = np.empty((p * (k-1), p * (k-1)))
        for a in range(k-1):
            for b in range(k-1):
                q = w * prob[:, a] * ((1 if a == b else 0) - prob[:, b]) / n
                block = x.T @ (x * q[:, None])
                if a == b: block += np.diag(penalty / C)
                h[a*p:(a+1)*p, b*p:(b+1)*p] = block
        h.flat[::len(h)+1] += SOLVER["hessian_ridge"]
        # Hessian is class-major; transpose coefficient vector accordingly.
        step = np.linalg.solve(h, grad.T.reshape(-1)).reshape(k-1, p).T
        old = objective(coef); scale = 1.0
        for _ in range(SOLVER["step_halving_max"]):
            candidate = coef - scale * step
            if objective(candidate) < old:
                coef = candidate; break
            scale *= .5
        else:
            break
    return MultinomialFit(coef, converged, iteration, grad_max, objective(coef))


def predict(fit: MultinomialFit, x): return _softmax_ref(x, fit.coef)


def b0_probabilities(rows, target, weights):
    classes = CLASSES[target]; total = float(weights.sum())
    return np.asarray([sum(w for r, w in zip(rows, weights) if r["event_class"] == c) / total for c in classes])


def proper_scores(rows, probs, target, weights):
    classes = CLASSES[target]; y = np.asarray([classes.index(r["event_class"]) for r in rows])
    wn = weights / weights.sum()
    ll = float(np.sum(wn * -np.log(np.clip(probs[np.arange(len(rows)), y], 1e-15, 1))))
    one = np.eye(len(classes))[y]
    brier = float(np.sum(wn * np.sum((probs - one) ** 2, axis=1)))
    return {"trade_weighted_log_loss": ll, "trade_weighted_brier": brier}


def _calibration(rows, probs, target, weights, train_probs, train_rows, train_weights):
    classes = CLASSES[target]; output = {}
    for ci, cls in enumerate(classes):
        cuts = [weighted_quantile(train_probs[:, ci], train_weights,
            [r["row_id"] for r in train_rows], q) for q in (.2, .4, .6, .8)]
        cuts = sorted(set(cuts)); bins = []
        indices = np.searchsorted(cuts, probs[:, ci], side="right")
        for bi in range(len(cuts)+1):
            ix = np.flatnonzero(indices == bi)
            if not len(ix): continue
            trades = {rows[i]["trade_id"] for i in ix}
            event_trades = {rows[i]["trade_id"] for i in ix if rows[i]["event_class"] == cls}
            ww = weights[ix] / weights[ix].sum()
            bins.append({"bin": bi, "snapshots": len(ix), "unique_resolved_trades": len(trades),
                "unique_event_trades": len(event_trades), "mean_predicted": float(np.sum(ww*probs[ix,ci])),
                "observed": float(np.sum(ww*np.asarray([rows[i]["event_class"] == cls for i in ix]))),
                "supported": len(trades) >= 30, "unstable": len(event_trades) < 10})
        event_trade_count = len({r["trade_id"] for r in rows if r["event_class"] == cls})
        cal = None
        if event_trade_count >= 50:
            z=np.log(np.clip(probs[:,ci],1e-12,1-1e-12)/np.clip(1-probs[:,ci],1e-12,1))
            design=np.column_stack((np.ones(len(rows)),z)); outcome=np.asarray([r['event_class']==cls for r in rows],float)
            beta=np.array([0.,1.]); wn=weights/weights.sum()
            cal_converged=False
            for _ in range(50):
                eta=np.clip(design@beta,-35,35); fitted=1/(1+np.exp(-eta))
                grad=design.T@(wn*(fitted-outcome)); h=design.T@(design*(wn*fitted*(1-fitted))[:,None])
                step=np.linalg.solve(h+np.eye(2)*1e-12,grad); beta-=step
                if np.max(np.abs(step))<1e-10: cal_converged=True; break
            if cal_converged and np.all(np.isfinite(beta)) and np.max(np.abs(beta))<100:
                cal={"intercept":float(beta[0]),"slope":float(beta[1]),"estimable":True}
            else:
                cal={"intercept":None,"slope":None,"estimable":False,"reason":"numerical_separation_or_nonconvergence"}
        output[cls] = {"training_cut_points": cuts, "bins": bins,
            "intercept_slope_supported": event_trade_count >= 50,
            "calibration_intercept_slope": cal,
            "unique_event_trades": event_trade_count,
            "expected_incidence": float(np.sum(weights/weights.sum()*probs[:,ci])),
            "observed_incidence": float(np.sum(weights/weights.sum()*np.asarray([r["event_class"]==cls for r in rows])))}
    return output


def _bootstrap_delta(rows, loss_a, loss_b, detail):
    by_trade = defaultdict(list)
    for r, a, b in zip(rows, loss_a, loss_b): by_trade[r["trade_id"]].append(float(a-b))
    means = {t: float(np.mean(v)) for t, v in by_trade.items()}
    vector = []
    for multiplicities in detail["trade_multiplicities"]:
        vals = [means[t] for t, mult in multiplicities.items() for _ in range(mult) if t in means]
        if not vals: raise AssertionError("frozen bootstrap contains no evaluation trades")
        vector.append(float(np.mean(vals)))
    arr = np.asarray(vector)
    return {"sign_convention": "first_minus_second; negative_is_better_for_first",
            "point_estimate": float(np.mean([np.mean(v) for v in by_trade.values()])),
            "ci95": [float(np.quantile(arr,.025,method="linear")), float(np.quantile(arr,.975,method="linear"))],
            "replicate_vector_sha256": hashlib.sha256(arr.astype("<f8").tobytes()).hexdigest(),
            "replicates": vector}


def _loss_vectors(rows, probs, target):
    classes=CLASSES[target]; y=np.asarray([classes.index(r["event_class"]) for r in rows]); one=np.eye(3)[y]
    return -np.log(np.clip(probs[np.arange(len(rows)),y],1e-15,1)), np.sum((probs-one)**2,axis=1)


def _fold_report(rows):
    return {"trades":len({r['trade_id'] for r in rows}),"snapshots":len(rows),
        "class_snapshots":dict(Counter(r['event_class'] for r in rows)),
        "class_unique_trades":{c:len({r['trade_id'] for r in rows if r['event_class']==c}) for c in sorted({r['event_class'] for r in rows})},
        "entry_weeks":len({r['trade_entry_week'] for r in rows}),"symbols":sorted({r['symbol'] for r in rows}),
        "censor_ambiguity_exclusions":"excluded before accepted resolved-row modeling population"}


def _stability(rows, pa, pb, target):
    la,ba=_loss_vectors(rows,pa,target); lb,bb=_loss_vectors(rows,pb,target)
    result={}
    for dim,key in (("symbol",lambda r:r['symbol']),("month",lambda r:r['snapshot_month']),("quarter",lambda r:r['snapshot_quarter'])):
        groups=defaultdict(list)
        for i,r in enumerate(rows): groups[key(r)].append(i)
        vals=[]
        for group,ix in sorted(groups.items()):
            rs=[rows[i] for i in ix]; w=trade_weights(rs); wn=w/w.sum(); ii=np.asarray(ix)
            vals.append({"group":group,"trades":len({r['trade_id'] for r in rs}),"snapshots":len(rs),
                "log_loss_delta":float(np.sum(wn*(la[ii]-lb[ii]))),"brier_delta":float(np.sum(wn*(ba[ii]-bb[ii])))})
        result[dim]={"groups":vals,"same_direction_improvement_count":sum(v['log_loss_delta']<0 and v['brier_delta']<0 for v in vals),"group_count":len(vals)}
    return result


def verify_gate(repo: Path):
    if os.environ.get("PYTHONPATH") is not None: raise RuntimeError("PYTHONPATH must be unset")
    if os.environ.get("CONDA_DEFAULT_ENV") != "binance-v2-research": raise RuntimeError("wrong conda environment")
    if sys.version_info[:3] != (3,11,16) or np.__version__ != "2.4.6": raise RuntimeError("environment version mismatch")
    checks = {
        repo/"contracts/C4_sequential_exit_state_CONTRACT.md": CONTRACT_HASH,
        repo/"artifacts/c4_sequential_exit_state/adequacy_decision.json": ADEQUACY_DECISION_HASH,
        repo/"artifacts/c4_sequential_exit_state/local/bootstrap_structure_details.json": BOOTSTRAP_DETAIL_HASH,
        repo/"artifacts/c4_sequential_exit_state/local/t1_snapshots.csv": ACCEPTED_CORE_HASHES["T1"],
        repo/"artifacts/c4_sequential_exit_state/local/t2_snapshots.csv": ACCEPTED_CORE_HASHES["T2"],
    }
    for path, expected in checks.items():
        if sha256_file(path) != expected: raise RuntimeError(f"gate hash mismatch: {path}")
    decision=json.loads((repo/"artifacts/c4_sequential_exit_state/adequacy_decision.json").read_text())
    if decision["target_decisions"] != {"T1":"ADEQUATE FOR MODELING","T2":"ADEQUATE FOR MODELING"}: raise RuntimeError("adequacy decision mismatch")
    if decision["threshold_panel_sha256"] != THRESHOLD_PANEL_HASH or _json_hash(decision["threshold_panel"]) != THRESHOLD_PANEL_HASH: raise RuntimeError("threshold panel mismatch")
    manifest=json.loads((repo/"artifacts/c4_sequential_exit_state/input_manifest.json").read_text())
    for item in manifest["explicit_allowlist"]:
        if sha256_file(repo/item["path"]) != item["sha256"]: raise RuntimeError(f"input mismatch: {item['path']}")
    c3=repo/"artifacts/c3_milestone_state_continuation/input_manifest.json"
    if sha256_file(c3) != manifest["predecessor_hashes"]["C3_input_manifest_hash"]: raise RuntimeError("C3 predecessor mismatch")
    return {str(p.relative_to(repo)):h for p,h in checks.items()} | {item['path']:item['sha256'] for item in manifest['explicit_allowlist']}


def build_feature_table(repo, rows):
    _,_,minutes,_=load_inputs(repo); features={}; retained=[]
    grouped=defaultdict(list)
    for row in rows: grouped[(row['symbol'],row['trade_id'])].append(row)
    # Cache market aggregates by (symbol, completed boundary); values never extend past t.
    five_cache={}; hour_cache={}
    needed_five=set(); needed_hours=set()
    for row in rows:
        t=row['snapshot_ms']; symbol=row['symbol']
        for k in range(26): needed_five.add((symbol,t-k*FIVE_MINUTES))
        he=(t//HOUR)*HOUR
        for k in range(1,26): needed_hours.add((symbol,he-k*HOUR))
    for symbol,end in sorted(needed_five): five_cache[(symbol,end)]=_bar(minutes[symbol],end-FIVE_MINUTES,5)
    for symbol,start in sorted(needed_hours):
        b=_bar(minutes[symbol],start,60); hour_cache[(symbol,start)]=None if b is None else b['close']
    for (symbol,trade),trade_rows in sorted(grouped.items()):
        trade_rows.sort(key=lambda r:r['snapshot_ms']); entry=trade_rows[0]['entry_execution_ms']
        first_end=((entry+FIVE_MINUTES-1)//FIVE_MINUTES)*FIVE_MINUTES
        if first_end-FIVE_MINUTES<entry: first_end+=FIVE_MINUTES
        path_closes=[]; path_lows=[]; path_abs=0.0; cursor=first_end
        for row in trade_rows:
            t=row['snapshot_ms']; _pre_value_2024(row)
            path_ok=True
            while cursor<=t:
                b=five_cache.get((symbol,cursor))
                if b is None:
                    b=_bar(minutes[symbol],cursor-FIVE_MINUTES,5)
                    five_cache[(symbol,cursor)]=b
                if b is None: path_ok=False; break
                if path_closes: path_abs+=abs(b['close']/path_closes[-1]-1)
                path_closes.append(b['close']); path_lows.append(b['low']); cursor+=FIVE_MINUTES
            if not path_ok or len(path_closes)<7 or path_abs==0: continue
            bars=[five_cache.get((symbol,t-k*FIVE_MINUTES)) for k in range(26)]
            if any(b is None for b in bars): continue
            closes=[bars[k]['close'] for k in range(25,-1,-1)]
            rets=[closes[i]/closes[i-1]-1 for i in range(1,len(closes))]
            latest12,latest6,prior6=rets[-12:],rets[-6:],rets[-12:-6]
            pv=_sample_std(prior6)
            prior_ranges=[(bars[k]['high']-bars[k]['low'])/bars[k]['open'] for k in range(1,13)]
            rmed=float(np.median(prior_ranges)); qmed=float(np.median([bars[k]['quote_volume'] for k in range(1,13)])); tmed=float(np.median([bars[k]['trade_count'] for k in range(1,13)]))
            he=(t//HOUR)*HOUR; hourly=[hour_cache.get((symbol,he-k*HOUR)) for k in range(25,0,-1)]
            btc_now=minutes['BTCUSDT'].get(t-MINUTE); btc_old=minutes['BTCUSDT'].get(t-61*MINUTE)
            if pv==0 or rmed==0 or qmed==0 or tmed==0 or any(x is None for x in hourly) or btc_now is None or btc_old is None: continue
            if any(minutes['BTCUSDT'].get(m) is None for m in range(t-61*MINUTE,t,MINUTE)): continue
            sma_now=float(np.mean(hourly[-24:])); sma_prev=float(np.mean(hourly[-25:-1])); month=datetime.fromtimestamp(t/1000,timezone.utc).month
            path_returns=[path_closes[i]/path_closes[i-1]-1 for i in range(1,len(path_closes))]
            recent6=path_returns[-6:]; recent15=path_closes[-1]/path_closes[-4]-1; prior15=path_closes[-4]/path_closes[-7]-1
            f={
                'elapsed_log1p_5m':math.log1p(row['elapsed_minutes']/5),'current_unrealized_return':row['current_return'],'realized_volatility_12':_sample_std(latest12),
                'calendar_month_sin':math.sin(2*math.pi*month/12),'calendar_month_cos':math.cos(2*math.pi*month/12),'btc_return_60m':btc_now['close']/btc_old['close']-1,
                'drawdown_from_running_peak':row['drawdown_from_running_peak'],'peak_gain_retained_fraction':row['peak_gain_retained_fraction'],
                't2_upper_distance':(row['upper_barrier']-row['snapshot_close'])/row['snapshot_close'],'t2_lower_distance':(row['snapshot_close']-row['lower_barrier'])/row['snapshot_close'],
                'running_mae':min(path_lows)/row['entry_price']-1,'path_efficiency':row['current_return']/path_abs,
                'recent_return_5m':path_closes[-1]/path_closes[-2]-1,'recent_return_15m':recent15,'recent_return_30m':path_closes[-1]/path_closes[-7]-1,'momentum_acceleration':recent15-prior15,
                'positive_5m_count_6':sum(x>0 for x in recent6),'negative_5m_count_6':sum(x<0 for x in recent6),'zero_5m_count_6':sum(x==0 for x in recent6),
                'volatility_expansion_ratio':_sample_std(latest6)/pv,'range_ratio_5m':((bars[0]['high']-bars[0]['low'])/bars[0]['open'])/rmed,
                'quote_volume_ratio_5m':bars[0]['quote_volume']/qmed,'trade_count_ratio_5m':bars[0]['trade_count']/tmed,
                'h1_close_distance_sma24':hourly[-1]/sma_now-1,'h1_sma24_slope':sma_now/sma_prev-1,
            }
            if all(math.isfinite(float(v)) for v in f.values()): features[row['row_id']]=f; retained.append(row)
    return retained,features


def run(repo: Path, artifact: Path):
    gate=verify_gate(repo); artifact.mkdir(parents=True,exist_ok=True)
    accepted=repo/'artifacts/c4_sequential_exit_state'
    all_results={}; all_predictions=[]; all_metrics=[]; all_attempts=[]; final_models={}; final_pre={}; populations={}; bootout={}; stability={}; calibrations={}
    details=json.loads((accepted/'local/bootstrap_structure_details.json').read_text())['targets']
    for target in ('T1','T2'):
        raw=load_accepted_2024_rows(accepted/'local'/f'{target.lower()}_snapshots.csv',ACCEPTED_CORE_HASHES[target])
        rows,features=build_feature_table(repo,raw)
        rows.sort(key=lambda r:(r['snapshot_ms'],r['symbol'],r['trade_id']))
        manifests=feature_manifest(target)
        populations[target]={"raw_resolved_2024_rows":len(raw),"complete_case_rows":len(rows),"trades":len({r['trade_id'] for r in rows}),"row_ids":sorted(r['row_id'] for r in rows),"trade_ids":sorted({r['trade_id'] for r in rows})}
        populations[target]['row_id_sha256']=semantic_hash(populations[target]['row_ids']); populations[target]['trade_id_sha256']=semantic_hash(populations[target]['trade_ids'])
        fold_cache={}
        for fold,(start,valid_start,end) in FOLDS.items():
            train=[r for r in rows if start <= r['entry_execution_ms'] < valid_start and (r['resolution_ts'] < datetime.fromtimestamp(valid_start/1000,timezone.utc).isoformat())]
            valid=[r for r in rows if valid_start <= r['entry_execution_ms'] < end and r['resolution_ts'] < datetime.fromtimestamp(end/1000,timezone.utc).isoformat()]
            if {r['trade_id'] for r in train}&{r['trade_id'] for r in valid}: raise AssertionError('trade crossed fold')
            tw,vw=trade_weights(train),trade_weights(valid); y=np.asarray([CLASSES[target].index(r['event_class']) for r in train])
            fold_cache[fold]={"train":train,"valid":valid,"train_report":_fold_report(train),"validation_report":_fold_report(valid)}
            predictions={}; fitted={}; preps={}
            bprob=b0_probabilities(train,target,tw); predictions['B0']=np.tile(bprob,(len(valid),1)); fitted['B0']={"probabilities":bprob.tolist()}; preps['B0']={}
            all_attempts.append({"target":target,"fold":fold,"model":"B0","C":None,"columns":[],"zero_iqr_excluded":[],"converged":True,"iterations":0,"gradient_max":0.0,**proper_scores(valid,predictions['B0'],target,vw)})
            for model in ('G0','G1','P1'):
                candidates=(1.0,) if model=='G0' else (.1,1.0,10.0)
                for C in candidates:
                    prep,cols=fit_preprocessing(train,features,manifests[model],tw)
                    xtr=matrix(train,features,cols,prep); xv=matrix(valid,features,cols,prep)
                    fit=fit_multinomial(xtr,y,tw,CLASSES[target],C); pv=predict(fit,xv)
                    metrics=proper_scores(valid,pv,target,vw)
                    attempt={"target":target,"fold":fold,"model":model,"C":C,"columns":cols,"zero_iqr_excluded":[c for c,p in prep.items() if p['excluded_zero_iqr']],"converged":fit.converged,"iterations":fit.iterations,"gradient_max":fit.gradient_max,**metrics}
                    all_attempts.append(attempt)
                    fold_cache[fold].setdefault('candidate_predictions',{})[(model,C)]=(pv,fit,prep,cols)
            # Selection is performed after both folds below.
        selected={"G0":1.0}
        for model in ('G1','P1'):
            summary=[]
            for C in (.1,1.0,10.0):
                a=[x for x in all_attempts if x['target']==target and x['model']==model and x['C']==C]
                summary.append((sum(x['trade_weighted_log_loss'] for x in a)/2,sum(x['trade_weighted_brier'] for x in a)/2,C))
            selected[model]=min(summary)[2]
        for fold,fc in fold_cache.items():
            train,valid=fc['train'],fc['valid']; tw,vw=trade_weights(train),trade_weights(valid)
            chosen={'B0':(np.tile(b0_probabilities(train,target,tw),(len(valid),1)),None,None,None)}
            for model in ('G0','G1','P1'): chosen[model]=fc['candidate_predictions'][(model,selected[model])]
            for model,(pv,fit,prep,cols) in chosen.items():
                metric=proper_scores(valid,pv,target,vw); metric.update({'target':target,'fold':fold,'model':model,'C':None if model=='B0' else selected[model]}); all_metrics.append(metric)
                for r,p in zip(valid,pv): all_predictions.append({'target':target,'fold':fold,'model':model,'row_id':r['row_id'],'trade_id':r['trade_id'],'event_class':r['event_class'],**{f'p_{c}':float(x) for c,x in zip(CLASSES[target],p)}})
            calibrations[f'{target}_{fold}']=_calibration(valid,chosen['P1'][0],target,vw,chosen['P1'][0] if False else predict(fc['candidate_predictions'][('P1',selected['P1'])][1],matrix(train,features,fc['candidate_predictions'][('P1',selected['P1'])][3],fc['candidate_predictions'][('P1',selected['P1'])][2])),train,tw)
            bootout[f'{target}_{fold}']={}
            for first,second in (('G1','G0'),('P1','G1')):
                la,ba=_loss_vectors(valid,chosen[first][0],target); lb,bb=_loss_vectors(valid,chosen[second][0],target)
                detail=details[target][f'{fold}_validate']
                bootout[f'{target}_{fold}'][f'{first}-{second}']={'log_loss':_bootstrap_delta(valid,la,lb,detail),'brier':_bootstrap_delta(valid,ba,bb,detail)}
            stability[f'{target}_{fold}']={'G1-G0':_stability(valid,chosen['G1'][0],chosen['G0'][0],target),'P1-G1':_stability(valid,chosen['P1'][0],chosen['G1'][0],target)}
        # Final fit only after selection has been frozen from both chronological folds.
        fw=trade_weights(rows); fy=np.asarray([CLASSES[target].index(r['event_class']) for r in rows]); final_models[target]={"selected_C":selected,"models":{}}
        final_models[target]['models']['B0']={"probabilities":b0_probabilities(rows,target,fw).tolist()}
        for model in ('G0','G1','P1'):
            prep,cols=fit_preprocessing(rows,features,manifests[model],fw); fit=fit_multinomial(matrix(rows,features,cols,prep),fy,fw,CLASSES[target],selected[model])
            final_pre[f'{target}_{model}']={"columns":cols,"parameters":prep}
            final_models[target]['models'][model]={"C":selected[model],"columns":cols,"coefficients":fit.coef.tolist(),"converged":fit.converged,"iterations":fit.iterations,"gradient_max":fit.gradient_max,"coefficient_sha256":hashlib.sha256(fit.coef.astype('<f8').tobytes()).hexdigest()}
        all_results[target]={"feature_manifest":manifests,"selected_C":selected,"folds":{f:{k:v for k,v in x.items() if k in ('train_report','validation_report')} for f,x in fold_cache.items()}}
    # Compact, deterministic artifacts; bootstrap vectors are retained because they are required reproducibility evidence.
    schema={"version":"C4_2024_FEATURE_SCHEMA_V1","targets":{t:all_results[t]['feature_manifest'] for t in all_results}}
    write_json(artifact/'feature_schema.json',schema); write_json(artifact/'modeling_population_2024.json',populations); write_json(artifact/'fold_counts_2024.json',{t:all_results[t]['folds'] for t in all_results}); write_json(artifact/'development_attempts_2024.json',all_attempts)
    _write_csv(artifact/'development_metrics_2024.csv',all_metrics); _write_csv(artifact/'development_predictions_2024.csv',all_predictions)
    write_json(artifact/'bootstrap_comparisons_2024.json',bootout); write_json(artifact/'stability_2024.json',stability); write_json(artifact/'calibration_2024.json',calibrations)
    write_json(artifact/'final_models_2024.json',final_models); write_json(artifact/'final_preprocessing_2024.json',final_pre)
    interpretations={}
    for target in ('T1','T2'):
        panels=[bootout[f'{target}_{fold}']['P1-G1'] for fold in ('fold_A','fold_B')]
        points=[p[m]['point_estimate'] for p in panels for m in ('log_loss','brier')]
        intervals=[p[m]['ci95'] for p in panels for m in ('log_loss','brier')]
        if all(x<0 for x in points) and all(ci[1]<0 for ci in intervals): decision='SUPPORTS SEQUENTIAL PATH-STATE SIGNAL'
        elif all(x>0 for x in points) and all(ci[0]>0 for ci in intervals): decision='COUNTS AGAINST'
        else: decision='MIXED'
        interpretations[target]={"decision":decision,"basis":"P1-versus-G1 proper scores, frozen whole-trade block intervals, fold and subgroup stability, and calibration","fold_point_deltas":points,"all_intervals_exclude_zero_in_improving_direction":all(ci[1]<0 for ci in intervals)}
    write_json(artifact/'c4_2024_interpretation.json',interpretations)
    source_files=(repo/'src/binance_data_foundation/c4_modeling.py',repo/'src/binance_data_foundation/c4_modeling_cli.py',repo/'tests/test_c4_modeling.py',repo/'environment.yml',repo/'requirements-dev.txt')
    freeze={"version":"C4_2024_FREEZE_V1","model_version":MODEL_VERSION,"contract_sha256":CONTRACT_HASH,"adequacy_decision_sha256":ADEQUACY_DECISION_HASH,"threshold_panel_sha256":THRESHOLD_PANEL_HASH,"bootstrap_structure_sha256":BOOTSTRAP_DETAIL_HASH,"source_test_hashes":{str(p.relative_to(repo)):sha256_file(p) for p in source_files},"gate_hashes":gate,"populations":{t:{k:v for k,v in p.items() if k not in ('row_ids','trade_ids')} for t,p in populations.items()},"row_trade_ids":{t:{"row_ids":p['row_ids'],"trade_ids":p['trade_ids']} for t,p in populations.items()},"feature_schema_sha256":sha256_file(artifact/'feature_schema.json'),"fold_counts_sha256":sha256_file(artifact/'fold_counts_2024.json'),"preprocessing_sha256":sha256_file(artifact/'final_preprocessing_2024.json'),"models_sha256":sha256_file(artifact/'final_models_2024.json'),"interpretation_sha256":sha256_file(artifact/'c4_2024_interpretation.json'),"solver":SOLVER,"interpretation":{"G1-G0":"current-state/geometry only","P1-G1":"genuine historical path beyond strong geometry","target_decisions":interpretations},"seals":{"2025_predictive_scoring":"NOT PERFORMED","2026_access":False,"economic_or_stage_B_analysis":False}}
    write_json(artifact/'c4_2024_freeze.json',freeze)
    return freeze


def _write_csv(path, rows):
    columns=sorted({k for r in rows for k in r})
    with path.open('w',newline='',encoding='utf-8') as h:
        w=csv.DictWriter(h,fieldnames=columns,lineterminator='\n'); w.writeheader(); w.writerows(rows)


def verify_two_rebuilds(repo: Path, artifact: Path):
    import tempfile
    core_names=('feature_schema.json','modeling_population_2024.json','fold_counts_2024.json','development_attempts_2024.json','development_metrics_2024.csv','development_predictions_2024.csv','bootstrap_comparisons_2024.json','stability_2024.json','calibration_2024.json','final_models_2024.json','final_preprocessing_2024.json','c4_2024_interpretation.json','c4_2024_freeze.json')
    first={n:sha256_file(artifact/n) for n in core_names}
    with tempfile.TemporaryDirectory(prefix='c4-2024-modeling-') as d:
        second_dir=Path(d); run(repo,second_dir)
        second={n:sha256_file(second_dir/n) for n in core_names}
    result={"independent_offline_rebuilds":2,"exact_reproduction":first==second,"first_hashes":first,"second_hashes":second,"2025_predictive_scoring":"NOT PERFORMED","2026_access":False}
    write_json(artifact/'c4_2024_reproducibility.json',result)
    if first != second: raise AssertionError('C4 2024 exact rebuild failed')
    return result
