"""C8 bounded pre-T2 timescale adequacy study.

No economic fields are loaded.  All market data access is restricted to the
accepted 2023--2025 C2 minute histories; the 2023 tail supplies causal context.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import math
import os
import platform
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

CONTRACT_SHA256 = "cee5a359d7e8f3c9ee95e8e1b227cbd59ddcb08b1e9e5b93bf69b919ab5e6ae7"
SEED = 20260928
REPLICATES = 2000
MINUTE = 60_000
DAY = 86_400_000
SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT")
ARCHITECTURES = {
    "A": (30, 5), "B": (60, 5), "C": (120, 5),
    "D": (60, 10), "E": (60, 15),
}
FOLDS = {
    "fold_A": (1704067200000, 1719792000000, 1727740800000),
    "fold_B": (1704067200000, 1727740800000, 1735689600000),
}
SLOW_FEATURES = (
    "slow_return_1", "slow_return_3", "slow_return_6",
    "slow_volatility_12", "slow_range_ratio", "slow_activity_ratio",
    "slow_close_vs_sma12", "slow_sma12_slope",
)
FAST_FEATURES = (
    "fast_return_1", "fast_return_3", "fast_return_6",
    "fast_volatility_12", "fast_range_ratio", "fast_activity_ratio",
    "path_efficiency", "current_return", "running_mfe",
    "drawdown_from_running_peak", "distance_to_t2_barrier",
    "elapsed_log1p_minutes", "fast_slow_agreement",
)
SYMBOL_FEATURES = tuple("symbol_" + s for s in SYMBOLS[1:])


def reject_2026(path: str | Path) -> None:
    parts = os.fspath(path).replace("\\", "/").lower().split("/")
    if any("2026" in p for p in parts):
        raise PermissionError("C8 prohibits 2026 path access")


def sha256_file(path: Path) -> str:
    reject_2026(path)
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n")


@dataclass
class Market:
    ms: np.ndarray
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    quote_volume: np.ndarray
    trade_count: np.ndarray

    @property
    def start(self): return int(self.ms[0])
    @property
    def end(self): return int(self.ms[-1] + MINUTE)

    def index(self, timestamp: int) -> int | None:
        i = int((timestamp - self.start) // MINUTE)
        return i if 0 <= i < len(self.ms) and int(self.ms[i]) == timestamp else None


@dataclass
class Bars:
    minutes: int
    end_ms: np.ndarray
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    volume: np.ndarray

    def at(self, end: int) -> int | None:
        i = int(np.searchsorted(self.end_ms, end))
        return i if i < len(self.end_ms) and int(self.end_ms[i]) == end else None


def load_market(path: Path) -> Market:
    reject_2026(path)
    cols = defaultdict(list)
    with gzip.open(path, "rt", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            ms = int(row["open_time_ms"])
            if ms >= 1767225600000:  # exclusive 2026 boundary
                raise PermissionError("minute source crosses prohibited boundary")
            cols["ms"].append(ms)
            for x in ("open", "high", "low", "close", "quote_volume"):
                cols[x].append(float(row[x]))
            cols["trade_count"].append(float(row["trade_count"]))
    ms = np.asarray(cols["ms"], dtype=np.int64)
    if len(ms) < 2 or np.any(np.diff(ms) != MINUTE):
        raise ValueError(f"non-contiguous minute source: {path}")
    return Market(ms, *(np.asarray(cols[x], dtype=float) for x in
        ("open", "high", "low", "close", "quote_volume", "trade_count")))


def aggregate(m: Market, minutes: int) -> Bars:
    """UTC-aligned, fully completed aggregation; partial edges are omitted."""
    width = minutes * MINUTE
    first_start = ((m.start + width - 1) // width) * width
    last_end = (m.end // width) * width
    starts = np.arange(first_start, last_end, width, dtype=np.int64)
    n = len(starts)
    out = {x: np.empty(n) for x in ("open", "high", "low", "close", "volume")}
    valid = np.ones(n, dtype=bool)
    for j, start in enumerate(starts):
        i = m.index(int(start))
        if i is None or i + minutes > len(m.ms) or int(m.ms[i + minutes - 1]) != start + width - MINUTE:
            valid[j] = False; continue
        sl = slice(i, i + minutes)
        out["open"][j] = m.open[i]
        out["high"][j] = np.max(m.high[sl])
        out["low"][j] = np.min(m.low[sl])
        out["close"][j] = m.close[i + minutes - 1]
        out["volume"][j] = np.sum(m.quote_volume[sl])
    return Bars(minutes, starts[valid] + width, *(out[x][valid] for x in
        ("open", "high", "low", "close", "volume")))


def load_trades(repo: Path) -> list[dict]:
    entries = {}
    path = repo / "artifacts/c2_asymmetric_exit_experiment/frozen_entries.csv"
    reject_2026(path)
    with path.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            y = datetime.fromtimestamp(int(r["entry_execution_ms"]) / 1000, timezone.utc).year
            if y not in (2024, 2025): raise ValueError("unexpected entry year")
            entries[r["trade_id"]] = {
                "trade_id": r["trade_id"], "symbol": r["symbol"],
                "entry_ms": int(r["entry_execution_ms"]), "entry_price": float(r["entry_price"]),
                "year": y,
            }
    p0 = repo / "artifacts/c2_asymmetric_exit_experiment/common_horizons_p0.csv"
    reject_2026(p0)
    with p0.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["trade_id"] not in entries: raise ValueError("P0 identity mismatch")
            entries[r["trade_id"]]["p0_ms"] = int(r["p0_execution_ms"])
    out = sorted(entries.values(), key=lambda r: (r["entry_ms"], r["symbol"], r["trade_id"]))
    if len(out) != 2199 or Counter(r["year"] for r in out) != {2024: 1093, 2025: 1106}:
        raise ValueError("frozen population mismatch")
    return out


def terminal_for_trade(trade: dict, market: Market) -> dict:
    """Exact C7 landmark/execution semantics, returning prognosis terminal."""
    entry, p0, price = trade["entry_ms"], trade["p0_ms"], trade["entry_price"]
    i0, i1 = market.index(entry), market.index(p0 - MINUTE)
    if i0 is None or i1 is None: raise ValueError("trade path unavailable")
    peak = price
    first_end = ((entry + 5 * MINUTE - 1) // (5 * MINUTE)) * (5 * MINUTE)
    if first_end - 5 * MINUTE < entry: first_end += 5 * MINUTE
    next_boundary = first_end
    for i in range(i0, i1 + 1):
        peak = max(peak, float(market.high[i]))
        boundary = int(market.ms[i] + MINUTE)
        if boundary != next_boundary: continue
        if boundary >= p0: break
        start_i = market.index(boundary - 5 * MINUTE)
        fill_i = market.index(boundary)
        if start_i is None or start_i < i0 or fill_i is None:
            next_boundary += 5 * MINUTE; continue
        close = float(market.close[i])
        if peak / price - 1 >= .01 and close / price - 1 > 0 and close > (price + peak) / 2:
            return {"terminal_ms": boundary, "label": 1, "terminal": "T2_FIRST"}
        next_boundary += 5 * MINUTE
    return {"terminal_ms": p0, "label": 0, "terminal": "P0_FIRST"}


def _bar_features(b: Bars, t: int, prefix: str) -> dict | None:
    i = b.at(t)
    if i is None or i < 13: return None
    c = b.close
    rets = c[i-11:i+1] / c[i-12:i] - 1
    ranges = (b.high[i-12:i+1] - b.low[i-12:i+1]) / b.open[i-12:i+1]
    rmed = float(np.median(ranges[:-1])); vmed = float(np.median(b.volume[i-12:i]))
    if rmed <= 0 or vmed <= 0: return None
    vals = {
        f"{prefix}_return_1": c[i] / c[i-1] - 1,
        f"{prefix}_return_3": c[i] / c[i-3] - 1,
        f"{prefix}_return_6": c[i] / c[i-6] - 1,
        f"{prefix}_volatility_12": float(np.std(rets, ddof=1)),
        f"{prefix}_range_ratio": ranges[-1] / rmed,
        f"{prefix}_activity_ratio": b.volume[i] / vmed,
    }
    if prefix == "slow":
        now, prior = float(np.mean(c[i-11:i+1])), float(np.mean(c[i-12:i]))
        vals.update({"slow_close_vs_sma12": c[i] / now - 1,
                     "slow_sma12_slope": now / prior - 1})
    return vals if all(math.isfinite(float(x)) for x in vals.values()) else None


def feature_row(trade: dict, t: int, market: Market, slow: Bars, fast: Bars) -> dict | None:
    """Pure causal row builder; label and terminal are not accepted arguments."""
    # Context is the most recently fully completed slow bar, which need not end
    # on every fast-state boundary.
    slow_end = (t // (slow.minutes * MINUTE)) * (slow.minutes * MINUTE)
    s = _bar_features(slow, slow_end, "slow"); f = _bar_features(fast, t, "fast")
    if s is None or f is None: return None
    fi = fast.at(t); assert fi is not None
    entry, price = trade["entry_ms"], trade["entry_price"]
    i0, i1 = market.index(entry), market.index(t - MINUTE)
    if i0 is None or i1 is None or i1 < i0: return None
    peak = max(price, float(np.max(market.high[i0:i1+1])))
    first_end = ((entry + fast.minutes * MINUTE - 1) // (fast.minutes * MINUTE)) * (fast.minutes * MINUTE)
    if first_end - fast.minutes * MINUTE < entry: first_end += fast.minutes * MINUTE
    pi = fast.at(first_end)
    if pi is None or pi > fi: return None
    path = fast.close[pi:fi+1]
    denom = float(np.sum(np.abs(path[1:] / path[:-1] - 1))) if len(path) > 1 else 0.0
    current = float(fast.close[fi] / price - 1)
    if denom == 0 and current != 0: return None
    f.update({
        "path_efficiency": 0.0 if denom == 0 else current / denom,
        "current_return": current,
        "running_mfe": peak / price - 1,
        "drawdown_from_running_peak": fast.close[fi] / peak - 1,
        "distance_to_t2_barrier": fast.close[fi] / ((price + peak) / 2) - 1,
        "elapsed_log1p_minutes": math.log1p((t - entry) / MINUTE),
        "fast_slow_agreement": float(np.sign(f["fast_return_3"]) * np.sign(s["slow_return_3"])),
    })
    out = s | f
    return out if all(math.isfinite(float(x)) for x in out.values()) else None


def snapshots(trades: list[dict], markets: dict, bars: dict, arch: str) -> list[dict]:
    slow_m, fast_m = ARCHITECTURES[arch]; result = []
    width = fast_m * MINUTE
    for tr in trades:
        terminal = tr["terminal_ms"]
        t = ((tr["entry_ms"] + width - 1) // width) * width
        if t <= tr["entry_ms"]: t += width
        while t < terminal:
            feat = feature_row(tr, t, markets[tr["symbol"]], bars[(tr["symbol"], slow_m)], bars[(tr["symbol"], fast_m)])
            if feat is not None:
                result.append({"trade_id": tr["trade_id"], "symbol": tr["symbol"],
                    "entry_ms": tr["entry_ms"], "terminal_ms": terminal, "state_ms": t,
                    "year": tr["year"], "label": tr["label"], "features": feat})
            t += width
    return result


def trade_weights(rows: list[dict]) -> np.ndarray:
    counts = Counter(r["trade_id"] for r in rows)
    w = np.asarray([1 / counts[r["trade_id"]] for r in rows], dtype=float)
    sums = defaultdict(float)
    for r, x in zip(rows, w): sums[r["trade_id"]] += float(x)
    if max(abs(x - 1) for x in sums.values()) > 1e-12: raise AssertionError("trade weights")
    return w


def fit_scaler(rows: list[dict], names: tuple[str, ...], weights: np.ndarray) -> dict:
    w = weights / weights.sum(); out = {}
    for name in names:
        x = np.asarray([r["features"][name] for r in rows])
        mean = float(np.sum(w*x)); sd = float(np.sqrt(np.sum(w*(x-mean)**2)))
        if not sd > 0: raise ValueError(f"zero training scale: {name}")
        out[name] = {"mean": mean, "sd": sd}
    return out


def design(rows: list[dict], names: tuple[str, ...], scaler: dict) -> np.ndarray:
    x = np.empty((len(rows), 1 + len(names) + len(SYMBOL_FEATURES)))
    x[:, 0] = 1
    for j, name in enumerate(names, 1):
        x[:, j] = [(r["features"][name] - scaler[name]["mean"]) / scaler[name]["sd"] for r in rows]
    for j, sf in enumerate(SYMBOL_FEATURES, 1 + len(names)):
        x[:, j] = [r["symbol"] == sf[7:] for r in rows]
    return x


def _objective(x, y, w, beta, penalty):
    z = np.clip(x @ beta, -40, 40)
    return float(np.sum(w * (np.logaddexp(0, z) - y*z)) + .5*np.sum(penalty*beta*beta))


def fit_logistic(x, y, weights, C=1.0, max_iter=1000, tol=1e-9):
    """Deterministic limited-memory BFGS for the frozen binary objective."""
    w = weights / weights.sum(); penalty = np.ones(x.shape[1]) / C; penalty[0] = 0
    beta = np.zeros(x.shape[1]); history = []; converged = False
    for iteration in range(1, max_iter + 1):
        z = np.clip(x @ beta, -40, 40); p = 1 / (1 + np.exp(-z))
        grad = x.T @ (w*(p-y)) + penalty*beta
        if np.max(np.abs(grad)) <= tol: converged = True; break
        q = grad.copy()
        alpha = []
        for s, yy, rho in reversed(history):
            a = rho*np.dot(s, q); alpha.append(a); q -= a*yy
        scale = 1.0 if not history else np.dot(history[-1][0], history[-1][1]) / np.dot(history[-1][1], history[-1][1])
        direction = scale*q
        for (s, yy, rho), a in zip(history, reversed(alpha)):
            direction += s*(a - rho*np.dot(yy, direction))
        direction = -direction
        old = _objective(x, y, w, beta, penalty); gd = float(np.dot(grad, direction)); step = 1.0
        for _ in range(40):
            candidate = beta + step*direction
            if _objective(x, y, w, candidate, penalty) <= old + 1e-4*step*gd: break
            step *= .5
        new_beta = beta + step*direction
        nz = np.clip(x @ new_beta, -40, 40); npred = 1/(1+np.exp(-nz))
        new_grad = x.T @ (w*(npred-y)) + penalty*new_beta
        s, yy = new_beta-beta, new_grad-grad; sy = float(np.dot(s, yy))
        if sy > 1e-14:
            history.append((s, yy, 1/sy)); history = history[-10:]
        beta = new_beta
    return {"coef": beta, "converged": converged, "iterations": iteration,
            "gradient_max": float(np.max(np.abs(grad)))}


def predict(model, x):
    z = np.clip(x @ model["coef"], -40, 40)
    return 1 / (1 + np.exp(-z))


def losses(rows, probs):
    y = np.asarray([r["label"] for r in rows], float)
    p = np.clip(np.asarray(probs), 1e-15, 1-1e-15)
    return (p-y)**2, -(y*np.log(p)+(1-y)*np.log(1-p))


def trade_mean(rows, values) -> float:
    by = defaultdict(list)
    for r, v in zip(rows, values): by[r["trade_id"]].append(float(v))
    return float(np.mean([np.mean(x) for x in by.values()]))


def metrics(rows, probs) -> dict:
    b, ll = losses(rows, probs); w = trade_weights(rows); wn = w/w.sum()
    y = np.asarray([r["label"] for r in rows], bool)
    return {"brier": float(np.sum(wn*b)), "log_loss": float(np.sum(wn*ll)),
            "auc": weighted_auc(y, probs, w), "rows": len(rows),
            "trades": len(set(r["trade_id"] for r in rows)),
            "prevalence": float(np.sum(wn*y))}


def weighted_auc(y, score, weight):
    order = np.argsort(np.asarray(score), kind="mergesort")
    y=np.asarray(y,bool)[order]; score=np.asarray(score)[order]; weight=np.asarray(weight)[order]
    pos, neg = weight[y].sum(), weight[~y].sum()
    if pos == 0 or neg == 0: return None
    concordant=before=0.; i=0
    while i < len(y):
        j=i+1
        while j<len(y) and score[j]==score[i]: j+=1
        wp,wn=weight[i:j][y[i:j]].sum(),weight[i:j][~y[i:j]].sum()
        concordant += wp*(before+.5*wn); before += wn; i=j
    return float(concordant/(pos*neg))


def calibration(rows, probs):
    y=np.asarray([r["label"] for r in rows],float); p=np.clip(probs,1e-9,1-1e-9)
    w=trade_weights(rows); w/=w.sum(); z=np.log(p/(1-p)); x=np.column_stack((np.ones(len(z)),z))
    beta=np.array([0.,1.]); estimable=True
    try:
        for _ in range(100):
            q=1/(1+np.exp(-np.clip(x@beta,-35,35)))
            g=x.T@(w*(q-y)); h=x.T@(x*(w*q*(1-q))[:,None])
            step=np.linalg.solve(h+np.eye(2)*1e-12,g); beta-=step
            if np.max(np.abs(step))<1e-9: break
        if not np.all(np.isfinite(beta)) or np.max(np.abs(beta))>100: estimable=False
    except np.linalg.LinAlgError: estimable=False
    bins=[]
    for lo in np.arange(0,1,.1):
        ix=(p>=lo)&(p<(lo+.1) if lo<.9 else p<=1)
        if np.any(ix):
            ww=w[ix]/w[ix].sum(); bins.append({"lower":float(lo),"rows":int(ix.sum()),
                "trades":len({rows[i]["trade_id"] for i in np.flatnonzero(ix)}),
                "mean_probability":float(np.sum(ww*p[ix])),"observed":float(np.sum(ww*y[ix]))})
    return {"intercept":float(beta[0]) if estimable else None,
            "slope":float(beta[1]) if estimable else None,"estimable":estimable,"bins":bins}


def moving_block_samples(rows, seed=SEED, replicates=REPLICATES):
    by_trade={}
    for r in rows: by_trade[r["trade_id"]]=r["entry_ms"]
    dates={t:datetime.fromtimestamp(ms/1000,timezone.utc).date() for t,ms in by_trade.items()}
    lo=min(dates.values()); lo-=timedelta(days=lo.weekday()); hi=max(dates.values()); hi-=timedelta(days=hi.weekday())
    span=(hi-lo).days//7+1; at=defaultdict(list)
    for t,d in dates.items(): at[(d-lo).days//7].append(t)
    blocks=[range(i,i+4) for i in range(span-3)]
    rng=np.random.Generator(np.random.PCG64(seed)); out=[]
    for _ in range(replicates):
        positions=[]
        while len(positions)<span: positions.extend(blocks[int(rng.integers(len(blocks)))])
        out.append([t for pos in positions[:span] for t in sorted(at[pos])])
    return out


def paired_uncertainty(rows, pa, pb, samples=None):
    ba,la=losses(rows,pa); bb,lb=losses(rows,pb); samples=samples or moving_block_samples(rows)
    by={}
    for name, arr in (("brier",ba-bb),("log_loss",la-lb)):
        vals=defaultdict(list)
        for r,v in zip(rows,arr): vals[r["trade_id"]].append(float(v))
        tm={t:float(np.mean(v)) for t,v in vals.items()}; reps=np.asarray([np.mean([tm[t] for t in sample]) for sample in samples])
        by[name]={"point":float(np.mean(list(tm.values()))),
            "ci95":[float(x) for x in np.quantile(reps,[.025,.975],method="linear")],
            "replicate_sha256":hashlib.sha256(reps.astype("<f8").tobytes()).hexdigest()}
    return by


def summarize_rows(rows):
    counts=Counter(r["trade_id"] for r in rows); arr=np.asarray(list(counts.values()))
    trade_label={r["trade_id"]:r["label"] for r in rows}
    return {"rows":len(rows),"unique_trades":len(counts),
        "event_trades":sum(trade_label.values()),"non_event_trades":len(trade_label)-sum(trade_label.values()),
        "rows_per_trade":{"min":int(arr.min()),"p25":float(np.quantile(arr,.25)),"median":float(np.median(arr)),
            "p75":float(np.quantile(arr,.75)),"max":int(arr.max()),"mean":float(np.mean(arr))}}


def split_fold(rows, fold):
    start, cut, end=FOLDS[fold]
    train=[r for r in rows if start<=r["entry_ms"]<cut and r["terminal_ms"]<cut]
    valid=[r for r in rows if cut<=r["entry_ms"]<end]
    return train,valid


def fit_fold(train, valid):
    tw=trade_weights(train); y=np.asarray([r["label"] for r in train],float)
    base=float(np.sum(tw*y)/tw.sum()); predictions={"M0":np.full(len(valid),base)}; details={"M0":{"base_rate":base}}
    for model,names in (("M1",SLOW_FEATURES),("M2",SLOW_FEATURES+FAST_FEATURES)):
        scale=fit_scaler(train,names,tw); fit=fit_logistic(design(train,names,scale),y,tw)
        predictions[model]=predict(fit,design(valid,names,scale))
        details[model]={"converged":fit["converged"],"iterations":fit["iterations"],
            "gradient_max":fit["gradient_max"],"scaler":scale,"coef":[float(x) for x in fit["coef"]]}
    return predictions,details


def slice_stability(rows, p1, p2):
    b1,l1=losses(rows,p1); b2,l2=losses(rows,p2); out={}
    elapsed=np.asarray([(r["state_ms"]-r["entry_ms"])/MINUTE for r in rows]); cuts=np.quantile(elapsed,[.25,.5,.75])
    groups={f"symbol:{s}":[i for i,r in enumerate(rows) if r["symbol"]==s] for s in SYMBOLS}
    groups.update({f"elapsed_q{q+1}":np.flatnonzero(np.searchsorted(cuts,elapsed,side="right")==q).tolist() for q in range(4)})
    for key,ix in groups.items():
        rr=[rows[i] for i in ix]; out[key]={"trades":len({r["trade_id"] for r in rr}),
            "brier_improvement":trade_mean(rr,(b1-b2)[ix]),"log_loss_improvement":trade_mean(rr,(l1-l2)[ix])}
    return out


def category(unc):
    b,l=unc["brier"],unc["log_loss"]
    if b["point"]>0 and l["point"]>0 and b["ci95"][0]>0 and l["ci95"][0]>0: return "CLEARLY_USEFUL"
    if b["point"]>0 and l["point"]>0 and b["ci95"][1]>=0 and l["ci95"][1]>=0: return "DIRECTIONALLY_USEFUL"
    if (b["point"]<0 and b["ci95"][1]<0) or (l["point"]<0 and l["ci95"][1]<0) or (b["point"]<0 and l["point"]<0): return "COUNTS_AGAINST"
    return "NO_CLEAR_INCREMENTAL_VALUE"


def evaluate_architecture(rows):
    all_valid=[]; foldout={}; pred={m:[] for m in ("M0","M1","M2")}
    for fold in FOLDS:
        train,valid=split_fold(rows,fold); pp,fit=fit_fold(train,valid)
        foldout[fold]={"train":summarize_rows(train),"validation":summarize_rows(valid),
            "models":{m:metrics(valid,pp[m]) for m in pp},"fit":fit}
        all_valid.extend(valid)
        for m in pred: pred[m].extend(pp[m].tolist())
    # Fold validation windows are disjoint, so concatenation is legitimate OOF order.
    result={"folds":foldout,"oof":{m:metrics(all_valid,pred[m]) for m in pred}}
    samples=moving_block_samples(all_valid)
    result["uncertainty"]={"M1_minus_M0":paired_uncertainty(all_valid,pred["M0"],pred["M1"],samples),
        "M2_minus_M1":paired_uncertainty(all_valid,pred["M1"],pred["M2"],samples)}
    result["incremental_category"]=category(result["uncertainty"]["M2_minus_M1"])
    result["calibration"]={m:calibration(all_valid,np.asarray(pred[m])) for m in pred}
    result["stability_M2_vs_M1"]=slice_stability(all_valid,np.asarray(pred["M1"]),np.asarray(pred["M2"]))
    result["oof_predictions"]=(all_valid,pred)
    return result


def select_architecture(results, architecture_trade_counts, population_2024=1093):
    best_b=min(x["oof"]["M2"]["brier"] for x in results.values()); best_l=min(x["oof"]["M2"]["log_loss"] for x in results.values())
    eligible={}
    for a,x in results.items():
        cal=x["calibration"]["M2"]; st=x["stability_M2_vs_M1"]
        fold_ok=all(x["folds"][f]["models"]["M1"]["brier"]>x["folds"][f]["models"]["M2"]["brier"] and x["folds"][f]["models"]["M1"]["log_loss"]>x["folds"][f]["models"]["M2"]["log_loss"] for f in FOLDS)
        symbol_ok=sum(st[f"symbol:{s}"]["brier_improvement"]>=0 for s in SYMBOLS)>=4
        elapsed_ok=all(not (st[f"elapsed_q{i}"]["brier_improvement"]<0 and st[f"elapsed_q{i}"]["log_loss_improvement"]<0) for i in range(1,5))
        useful=x["incremental_category"] in ("CLEARLY_USEFUL","DIRECTIONALLY_USEFUL")
        competitive=x["oof"]["M2"]["brier"]<=best_b+.001 and x["oof"]["M2"]["log_loss"]<=best_l+.005
        cal_ok=cal["estimable"] and -.25<=cal["intercept"]<=.25 and .5<=cal["slope"]<=1.5
        # Coverage is an architecture data-adequacy property. OOF folds cover
        # only Q3/Q4 by design and therefore cannot be divided by the full-year
        # population for this gate.
        complete=architecture_trade_counts[a]>=.95*population_2024
        eligible[a]={"eligible":all((useful,competitive,cal_ok,symbol_ok,elapsed_ok,complete,fold_ok)),
            "checks":{"useful":useful,"competitive":competitive,"calibration":cal_ok,"symbol_breadth":symbol_ok,
                "elapsed_breadth":elapsed_ok,"completeness":complete,"both_folds":fold_ok}}
    choices=[a for a in ARCHITECTURES if eligible[a]["eligible"]]
    selected=None; reason="no_candidate_satisfies_all_prospective_criteria"
    if "B" in choices:
        selected="B"; reason="baseline_retained_under_prospective_tolerance_rule"
        for a in choices:
            if (results["B"]["oof"]["M2"]["brier"]-results[a]["oof"]["M2"]["brier"]>=.001 and
                results["B"]["oof"]["M2"]["log_loss"]-results[a]["oof"]["M2"]["log_loss"]>=.005):
                selected=a; reason="candidate_materially_improves_both_scores_over_baseline"; break
    elif choices:
        selected=min(choices,key=lambda a:(results[a]["oof"]["M2"]["brier"],results[a]["oof"]["M2"]["log_loss"],a)); reason="best_eligible_candidate_baseline_ineligible"
    if selected is None: selected="B"; reason += ";baseline_B_reported_adequate_without_clear_winner"
    return {"selected":selected,"clear_preferred":any(v["eligible"] for v in eligible.values()),"reason":reason,"eligibility":eligible}


def fit_full_predict(train, valid):
    tw=trade_weights(train); y=np.asarray([r["label"] for r in train],float); base=float(np.sum(tw*y)/tw.sum())
    pp={"M0":np.full(len(valid),base)}; fits={"M0":{"base_rate":base}}
    for model,names in (("M1",SLOW_FEATURES),("M2",SLOW_FEATURES+FAST_FEATURES)):
        scale=fit_scaler(train,names,tw); fit=fit_logistic(design(train,names,scale),y,tw)
        pp[model]=predict(fit,design(valid,names,scale)); fits[model]={"converged":fit["converged"],"iterations":fit["iterations"],"gradient_max":fit["gradient_max"]}
    return pp,fits


def examples(rows, probs):
    by=defaultdict(list)
    for i,r in enumerate(rows): by[r["trade_id"]].append(i)
    counts={t:len(ix) for t,ix in by.items()}; labels={t:rows[ix[0]]["label"] for t,ix in by.items()}
    chosen=[]
    for label in (1,0):
        cohort=[t for t in by if labels[t]==label]; med=float(np.median([counts[t] for t in cohort]))
        chosen.append(min(cohort,key=lambda t:(abs(counts[t]-med),t)))
    trade_prob={t:float(np.mean([probs[i] for i in ix])) for t,ix in by.items()}
    correct=[t for t in by if (trade_prob[t]>=.5)==bool(labels[t])]
    wrong=[t for t in by if (trade_prob[t]>=.5)!=bool(labels[t])]
    if correct: chosen.append(min(correct,key=lambda t:(-(trade_prob[t] if labels[t] else 1-trade_prob[t]),t)))
    if wrong: chosen.append(min(wrong,key=lambda t:(-(trade_prob[t] if not labels[t] else 1-trade_prob[t]),t)))
    out=[]
    roles=("outcome_median_T2","outcome_median_P0","high_confidence_correct","high_confidence_incorrect")
    for role,t in zip(roles,chosen):
        ix=by[t]; out.append({"role":role,"trade_id":t,"symbol":rows[ix[0]]["symbol"],"label":labels[t],
            "trajectory":[{"elapsed_minutes":int((rows[i]["state_ms"]-rows[i]["entry_ms"])/MINUTE),"probability":float(probs[i])} for i in ix]})
    return out


def artifact_hashes(directory: Path, exclude=("reproducibility_hashes.json",)):
    return {p.name:sha256_file(p) for p in sorted(directory.iterdir()) if p.is_file() and p.name not in exclude}


def run(repo: Path) -> dict:
    reject_2026(repo); artifact=repo/"artifacts/c8_pre_t2_timescale_adequacy"
    contract=repo/"contracts/C8_pre_t2_timescale_adequacy_CONTRACT.md"
    if sha256_file(contract)!=CONTRACT_SHA256: raise RuntimeError("C8 contract changed after freeze")
    inputs=[repo/"artifacts/c2_asymmetric_exit_experiment/frozen_entries.csv",repo/"artifacts/c2_asymmetric_exit_experiment/common_horizons_p0.csv"]+[repo/f"data/normalized/c2_history/{s}_1m.csv.gz" for s in SYMBOLS]
    provenance={str(p.relative_to(repo)):sha256_file(p) for p in inputs}
    trades=load_trades(repo); markets={}; bars={}
    for s in SYMBOLS:
        markets[s]=load_market(repo/f"data/normalized/c2_history/{s}_1m.csv.gz")
        for mins in (5,10,15,30,60,120): bars[(s,mins)]=aggregate(markets[s],mins)
    for tr in trades: tr.update(terminal_for_trade(tr,markets[tr["symbol"]]))
    reconciliation={"included":len(trades),"by_year":dict(Counter(str(r["year"]) for r in trades)),
        "outcomes":dict(Counter(r["terminal"] for r in trades))}
    if reconciliation["outcomes"]!={"T2_FIRST":845,"P0_FIRST":1354}: raise RuntimeError(f"T2 reconciliation failed: {reconciliation}")
    write_json(artifact/"source_provenance_manifest.json",{"contract_sha256":CONTRACT_SHA256,"inputs":provenance,"no_2026":True})
    all_rows={a:snapshots(trades,markets,bars,a) for a in ARCHITECTURES}
    summary={a:{"all":summarize_rows(rows),"2024":summarize_rows([r for r in rows if r["year"]==2024]),"2025":summarize_rows([r for r in rows if r["year"]==2025])} for a,rows in all_rows.items()}
    write_json(artifact/"dataset_summary.json",{"population_reconciliation":reconciliation,"architectures":summary})
    feature_schema={"slow_features":list(SLOW_FEATURES),"fast_state_features":list(FAST_FEATURES),"symbol_indicators":list(SYMBOL_FEATURES),
        "M0":"training trade-weighted prevalence","M1":list(SLOW_FEATURES)+list(SYMBOL_FEATURES),"M2":list(SLOW_FEATURES+FAST_FEATURES)+list(SYMBOL_FEATURES),
        "formulas":"contracts/C8_pre_t2_timescale_adequacy_CONTRACT.md"}
    write_json(artifact/"feature_schema.json",feature_schema)
    results={}
    for a,rows in all_rows.items(): results[a]=evaluate_architecture([r for r in rows if r["year"]==2024])
    serial={a:{k:v for k,v in x.items() if k!="oof_predictions"} for a,x in results.items()}
    write_json(artifact/"architecture_model_metrics_2024.json",{a:{"folds":x["folds"],"oof":x["oof"]} for a,x in serial.items()})
    write_json(artifact/"paired_uncertainty_2024.json",{a:{"uncertainty":x["uncertainty"],"incremental_category":x["incremental_category"]} for a,x in serial.items()})
    write_json(artifact/"calibration_summaries_2024.json",{a:x["calibration"] for a,x in serial.items()})
    write_json(artifact/"architecture_comparison_2024.json",{a:{"oof":x["oof"],"incremental_category":x["incremental_category"],"stability":x["stability_M2_vs_M1"]} for a,x in serial.items()})
    selection=select_architecture(results,{a:summary[a]["2024"]["unique_trades"] for a in ARCHITECTURES}); write_json(artifact/"selected_architecture.json",selection)
    selected=selection["selected"]; train=[r for r in all_rows[selected] if r["year"]==2024]; valid=[r for r in all_rows[selected] if r["year"]==2025]
    pp,fits=fit_full_predict(train,valid); stability={"architecture":selected,"train":summarize_rows(train),"evaluation":summarize_rows(valid),
        "models":{m:metrics(valid,p) for m,p in pp.items()},"calibration":{m:calibration(valid,p) for m,p in pp.items()},"fits":fits,
        "M2_vs_M1":paired_uncertainty(valid,pp["M1"],pp["M2"])}
    stability["direction"]="replicates_directionally" if all(stability["M2_vs_M1"][m]["point"]>0 for m in ("brier","log_loss")) else "reverses_or_weakens"
    write_json(artifact/"stability_2025.json",stability)
    baseline=None
    if selected!="B":
        bt=[r for r in all_rows["B"] if r["year"]==2024]; bv=[r for r in all_rows["B"] if r["year"]==2025]; bp,bf=fit_full_predict(bt,bv)
        baseline={"architecture":"B","models":{m:metrics(bv,p) for m,p in bp.items()},"M2_vs_M1":paired_uncertainty(bv,bp["M1"],bp["M2"]),"fits":bf}
    write_json(artifact/"baseline_B_2025.json",baseline)
    trajectory=examples(valid,pp["M2"]); write_json(artifact/"example_trajectories.json",{"descriptive_only":True,"architecture":selected,"examples":trajectory})
    folddefs={a:{f:{"train":x["folds"][f]["train"],"validation":x["folds"][f]["validation"],"bounds_ms":FOLDS[f]} for f in FOLDS} for a,x in serial.items()}
    write_json(artifact/"fold_definitions_2024.json",folddefs)
    final={"contract_sha256":CONTRACT_SHA256,"population":reconciliation,"architectures":ARCHITECTURES,"selection":selection,
        "metrics_2024":{a:x["oof"] for a,x in serial.items()},"incremental_2024":{a:{"category":x["incremental_category"],"uncertainty":x["uncertainty"]["M2_minus_M1"]} for a,x in serial.items()},
        "stability_2025":{"architecture":selected,"models":stability["models"],"M2_vs_M1":stability["M2_vs_M1"],"direction":stability["direction"]},
        "scientific_interpretation":"Timescale adequacy only; probabilities describe progression toward the frozen T2-first endpoint and are not trading actions.",
        "post_t2_note":"Post-T2 resolution adequacy should be studied separately because its dynamics may differ; it was not accessed here.",
        "confirmations":{"trading_economics":False,"c7_modified":False,"accessed_2026":False}}
    write_json(artifact/"final_summary.json",final)
    manifest={"version":"C8_RUN_V1","contract_sha256":CONTRACT_SHA256,"seed":SEED,"replicates":REPLICATES,
        "python":sys.version,"numpy":np.__version__,"platform":platform.platform(),"architectures":ARCHITECTURES}
    write_json(artifact/"run_manifest.json",manifest)
    hashes=artifact_hashes(artifact); write_json(artifact/"reproducibility_hashes.json",hashes)
    return final
