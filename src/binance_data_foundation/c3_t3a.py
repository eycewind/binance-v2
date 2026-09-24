"""C3 T3-A: sealed, chronological 2024 predictive development only.

This module intentionally consumes only the accepted T1/T2 CSV artifacts.  It
does not discover market files and its scoring API rejects 2025 and later rows.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import platform
import random
import statistics
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

from .c3_milestone import FEATURE_COLUMNS, OUTCOME_COLUMNS, PROVENANCE_COLUMNS
from .ingest import sha256_file

T3A_END_MS = 1_735_689_600_000  # 2025-01-01T00:00:00Z
FOLDS = {
    "fold_a": {"train": (1_704_067_200_000, 1_719_792_000_000), "validation": (1_719_792_000_000, 1_727_740_800_000)},
    "fold_b": {"train": (1_704_067_200_000, 1_727_740_800_000), "validation": (1_727_740_800_000, T3A_END_MS)},
}
C_GRID = (0.1, 1.0, 10.0)
SEED = 20240923
BOOTSTRAP_REPLICATIONS = 2000
BOOTSTRAP_QUANTILES = (0.025, 0.975)
SOLVER_TOLERANCE = 1e-10
SOLVER_MAX_ITERATIONS = 100
METRIC_PROBABILITY_EPSILON = 1e-15
SYMBOL_ORDER = ("BNBUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT")
CALENDAR_COLUMNS = ("sin_month", "cos_month")
B2_FEATURES = ("time_from_entry_seconds", "local_return_15m", "realized_volatility_last6_5m",
               "distance_from_h1_sma24", "btc_minus_subject_return_15m")
LOCAL_FEATURES = FEATURE_COLUMNS[:27]
CONTEXT_FEATURES = FEATURE_COLUMNS[27:]
L0_FEATURES = ("realized_volatility_last6_5m", "distance_from_h1_sma24")
EXPECTED_T1T2 = {
    "input_manifest.json": "cb5dd90fdffaca618a1b504e686206012d73b725d21e83ee1ff1091155e9fd3f",
    "reproducibility_manifest.json": "c72dbc290f16281cfa145a55715688c4a0baf57008491a056602d13d3520e292",
    "feature_schema.json": "1259d04b31364f157108fa7cda737dc7de6d7c8c63bc8af6252d641fe4c41347",
    "m1_audit.csv": "9d709e18553493c14ec5546cd9c6fcf8755d718c2901a3971fc9e0b39cac499a",
    "m1_features.csv": "5797f8c58029017fea8bd2025f0732a97220c9093362e2e18c6267e1238af1c8",
    "m1_feature_row_keys.csv": "fc275669e6341c5906c004355f73f6307b10499a1a8478449ba1b5394968b628",
    "m1_outcomes.csv": "97c81994b97d714dd25f01c643b627608fd346ebe8942fd54395e05791fba427",
    "m2_audit.csv": "978d79c9393ed4551a4b314e047b53d777c48e4c207f28a3be4c9dbbf2072635",
    "m2_features.csv": "5cd591770642a25e159e13459140c53bf5d4326ed943714f01b5fb0eeebf4a17",
    "m2_feature_row_keys.csv": "faeb18b58f9a35a5e67bc4933edcbde23f59cdfc3d0e58839d8aca59f5e9ea00",
    "m2_outcomes.csv": "eae1c7a1d7a089234e0500f0ead4596d7e8e24fabefe1c13d95ab8324b6f63b3",
}


def canonical_hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _read_csv(path: Path) -> tuple[tuple[str, ...], list[dict]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return tuple(reader.fieldnames or ()), list(reader)


def assert_feature_matrix(columns) -> None:
    columns = tuple(columns)
    if columns != FEATURE_COLUMNS:
        extras = sorted(set(columns) & (set(PROVENANCE_COLUMNS) | set(OUTCOME_COLUMNS)))
        raise ValueError(f"model matrix must be exact ordered 35 FEATURE_COLUMNS; forbidden={extras}")


def guard_development_timestamp(timestamp_ms: object) -> int:
    value = int(timestamp_ms)
    if value >= T3A_END_MS:
        raise ValueError("T3-A refuses to score milestone timestamp >= 2025-01-01T00:00:00Z")
    return value


def _calendar_values(milestone_ts: str) -> tuple[float, float]:
    month = int(milestone_ts[5:7])
    return math.sin(2 * math.pi * month / 12), math.cos(2 * math.pi * month / 12)


def _row_key_hash(rows: list[dict]) -> str:
    keys = [[r["trade_id"], r["milestone_id"]] for r in rows]
    return canonical_hash(keys)


def load_accepted_t1t2(repo: Path) -> tuple[dict, dict]:
    root = repo / "artifacts/c3_milestone_state_continuation"
    verified = {}
    for name, expected in EXPECTED_T1T2.items():
        actual = sha256_file(root / name)
        if actual != expected:
            raise ValueError(f"accepted T1/T2 hash mismatch: {name}")
        verified[name] = actual
    contract = repo / "contracts/C3_milestone_state_continuation_CONTRACT.md"
    if sha256_file(contract) != "d1df751c1005995e27f93d04d7f7dc7c40180862870dfa5727e7b708546d3f2d":
        raise ValueError("C3 contract hash mismatch")
    verified["contracts/C3_milestone_state_continuation_CONTRACT.md"] = sha256_file(contract)
    accepted_c2 = {
        "artifacts/c2_asymmetric_exit_experiment/frozen_entries.csv":"6885678a43b0d2f40b34e65adf15247072cdec2bbc8437cafd8cb69d8fba5da3",
        "artifacts/c2_asymmetric_exit_experiment/common_horizons_p0.csv":"81e57cfa46f8d39a0448ab6dee2f445c9212f6a29230fe7009c860a580666b7f",
        "artifacts/c2_asymmetric_exit_experiment/c2a_paired_trade_records.csv":"43de8894095963bda5aee47d8d24f6dec34a3b9cc7def1eec80256156baff5f1",
    }
    for relative, expected in accepted_c2.items():
        if sha256_file(repo/relative) != expected: raise ValueError(f"accepted C2 hash mismatch: {relative}")
        verified[relative] = expected
    schema = json.loads((root / "feature_schema.json").read_text(encoding="utf-8"))
    assert_feature_matrix(schema["model_matrix_columns"])
    datasets = {}
    for target in ("m1", "m2"):
        with (root / f"{target}_features.csv").open(newline="", encoding="utf-8") as handle:
            feature_header = tuple(csv.DictReader(handle).fieldnames or ())
        with (root / f"{target}_feature_row_keys.csv").open(newline="", encoding="utf-8") as handle:
            key_header = tuple(csv.DictReader(handle).fieldnames or ())
        assert_feature_matrix(feature_header)
        if key_header != ("model_row_index", "trade_id", "milestone_id"):
            raise ValueError("invalid accepted feature row-key artifact")
        # Gate on milestone time before touching feature or outcome fields.  The
        # accepted files are hash-verified, but 2025 values remain opaque.
        audit_by_key = {}
        with (root / f"{target}_audit.csv").open(newline="", encoding="utf-8") as handle:
            for audit in csv.DictReader(handle):
                identity = (audit["trade_id"], audit["milestone_id"])
                milestone = int(audit["milestone_interval_start_ms"])
                if milestone < T3A_END_MS:
                    audit_by_key[identity] = {"symbol":audit["symbol"], "milestone_ms":milestone,
                                              "milestone_ts":audit["milestone_interval_start_ts"]}
        outcome_by_key = {}
        with (root / f"{target}_outcomes.csv").open(newline="", encoding="utf-8") as handle:
            for outcome in csv.DictReader(handle):
                identity = (outcome["trade_id"], outcome["milestone_id"])
                if identity in audit_by_key:  # boundary gate precedes outcome access
                    outcome_by_key[identity] = {"label":outcome["label"], "label_resolution_ms":outcome["label_resolution_ms"]}
        rows = []
        # Stream keys and literal feature rows together.  The temporal identity
        # gate is evaluated before any feature field is converted or accessed.
        with (root / f"{target}_features.csv").open(newline="", encoding="utf-8") as feature_handle, \
             (root / f"{target}_feature_row_keys.csv").open(newline="", encoding="utf-8") as key_handle:
            feature_reader, key_reader = csv.DictReader(feature_handle), csv.DictReader(key_handle)
            count = 0
            for index, (feature, key) in enumerate(zip(feature_reader, key_reader)):
                count += 1
                if int(key["model_row_index"]) != index:
                    raise ValueError("non-contiguous accepted model row index")
                identity = (key["trade_id"], key["milestone_id"])
                if identity not in audit_by_key:
                    continue  # sealed row: no feature field is semantically materialized
                audit, outcome = audit_by_key[identity], outcome_by_key[identity]
                row = {"trade_id": identity[0], "milestone_id": identity[1], "symbol": audit["symbol"],
                       "milestone_ms": audit["milestone_ms"], "milestone_ts": audit["milestone_ts"],
                       "label_resolution_ms_raw": outcome["label_resolution_ms"], "label_raw": outcome["label"],
                       "features": {name: float(feature[name]) for name in FEATURE_COLUMNS}}
                rows.append(row)
            if next(feature_reader, None) is not None or next(key_reader, None) is not None:
                raise ValueError("accepted feature/key row-count mismatch")
        datasets[target.upper()] = rows
    return datasets, verified


def chronological_split(rows: list[dict], fold: str) -> tuple[list[dict], list[dict], dict]:
    spec = FOLDS[fold]
    selected, purged = {}, {}
    for role in ("train", "validation"):
        start, end = spec[role]
        candidates = [r for r in rows if start <= r["milestone_ms"] < end]
        clean = []; null_label = boundary = 0
        for row in candidates:
            guard_development_timestamp(row["milestone_ms"])
            if row["label_raw"] not in ("0", "1"):
                null_label += 1
                continue
            # Resolution is consumed only for a 2024 candidate and only to enforce its fold boundary.
            resolution = int(row["label_resolution_ms_raw"])
            if resolution >= end:
                boundary += 1
                continue
            label = int(row["label_raw"])
            clean.append({**row, "label": label, "month": row["milestone_ts"][:7],
                          "quarter": row["milestone_ts"][:4] + "-Q" + str((int(row["milestone_ts"][5:7])-1)//3+1)})
        selected[role], purged[role] = clean, {"null_label":null_label,"boundary_resolution":boundary,"total":len(candidates)-len(clean)}
    return selected["train"], selected["validation"], purged


def final_2024_training_rows(rows: list[dict]) -> list[dict]:
    selected = []
    for row in rows:
        if not FOLDS["fold_b"]["train"][0] <= row["milestone_ms"] < T3A_END_MS:
            continue
        guard_development_timestamp(row["milestone_ms"])
        if row["label_raw"] not in ("0", "1"):
            continue
        if int(row["label_resolution_ms_raw"]) >= T3A_END_MS:
            continue
        selected.append({**row, "label": int(row["label_raw"]), "month": row["milestone_ts"][:7],
                         "quarter": row["milestone_ts"][:4] + "-Q" + str((int(row["milestone_ts"][5:7])-1)//3+1)})
    return selected


def _quantile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    if not ordered: return math.nan
    pos = (len(ordered) - 1) * q; lo = int(pos); hi = min(lo + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo)


def fit_preprocessor(rows: list[dict], feature_names: tuple[str, ...]) -> dict:
    continuous = {}
    for name in feature_names:
        values = [r["features"][name] for r in rows]
        median = statistics.median(values); iqr = _quantile(values, .75) - _quantile(values, .25)
        continuous[name] = {"median": median, "iqr": iqr, "zero_iqr": iqr == 0}
    calendar = {}
    calendar_matrix = [_calendar_values(r["milestone_ts"]) for r in rows]
    for index, name in enumerate(CALENDAR_COLUMNS):
        values = [v[index] for v in calendar_matrix]
        median = statistics.median(values); iqr = _quantile(values, .75) - _quantile(values, .25)
        calendar[name] = {"median": median, "iqr": iqr, "zero_iqr": iqr == 0}
    symbols = [symbol for symbol in SYMBOL_ORDER if symbol in {r["symbol"] for r in rows}]
    spec = {"continuous_order": list(feature_names), "continuous": continuous, "categorical": {"symbol": symbols},
            "calendar_order": list(CALENDAR_COLUMNS), "calendar": calendar, "imputation": None,
            "rules": "training median center and training IQR scale for frozen continuous and calendar controls; zero-IQR center only; training-only one-hot symbol"}
    spec["sha256"] = canonical_hash(spec)
    return spec


def transform(rows: list[dict], spec: dict) -> list[list[float]]:
    vectors = []
    for row in rows:
        guard_development_timestamp(row["milestone_ms"])
        vector = []
        for name in spec["continuous_order"]:
            rule = spec["continuous"][name]; value = row["features"][name] - rule["median"]
            vector.append(value if rule["zero_iqr"] else value / rule["iqr"])
        if row["symbol"] not in spec["categorical"]["symbol"]:
            raise ValueError("validation category absent from training encoding")
        vector.extend(float(row["symbol"] == symbol) for symbol in spec["categorical"]["symbol"])
        calendar_values = _calendar_values(row["milestone_ts"])
        for name, raw in zip(spec["calendar_order"], calendar_values):
            rule = spec["calendar"][name]; value = raw - rule["median"]
            vector.append(value if rule["zero_iqr"] else value / rule["iqr"])
        vectors.append(vector)
    return vectors


def _solve(a: list[list[float]], b: list[float]) -> list[float]:
    n = len(b); m = [a[i][:] + [b[i]] for i in range(n)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[pivot][col]) < 1e-12: m[pivot][col] += 1e-8
        m[col], m[pivot] = m[pivot], m[col]
        divisor = m[col][col]
        for j in range(col, n + 1): m[col][j] /= divisor
        for i in range(n):
            if i == col: continue
            factor = m[i][col]
            if factor:
                for j in range(col, n + 1): m[i][j] -= factor * m[col][j]
    return [m[i][n] for i in range(n)]


def fit_logistic(x: list[list[float]], y: list[int], c: float, max_iter: int = SOLVER_MAX_ITERATIONS, *, enforce_grid: bool = True) -> dict:
    if enforce_grid and c not in C_GRID: raise ValueError("C outside fixed grid")
    design = [[1.0] + row for row in x]; p = len(design[0]); beta = [0.0] * p
    converged = False
    for iteration in range(max_iter):
        probs = [1/(1+math.exp(-max(-35, min(35, sum(b*v for b,v in zip(beta,row)))))) for row in design]
        penalty = 0 if math.isinf(c) else 1/c
        grad = [sum((pr-yi)*row[j] for row, yi, pr in zip(design,y,probs)) + (0 if j == 0 else beta[j]*penalty) for j in range(p)]
        hess = [[sum(pr*(1-pr)*row[j]*row[k] for row,pr in zip(design,probs)) + (penalty if j==k and j else 0) for k in range(p)] for j in range(p)]
        step = _solve(hess, grad); candidate = [b-s for b,s in zip(beta,step)]
        if max(abs(s) for s in step) < SOLVER_TOLERANCE: beta=candidate; converged=True; break
        beta = candidate
    return {"coefficients": beta, "C": c, "iterations": iteration+1, "converged": converged,
            "implementation": "c3-pure-python-newton-l2-v2-calendar-scaled", "solver": "Newton/IRLS with deterministic Gaussian elimination",
            "tolerance": SOLVER_TOLERANCE, "max_iterations": max_iter,
            "objective": "sum_log_loss + ||beta_nonintercept||^2/(2C)"}


def predict_logistic(model: dict, x: list[list[float]], timestamps: list[int]) -> list[float]:
    for ts in timestamps: guard_development_timestamp(ts)
    beta=model["coefficients"]
    return [1/(1+math.exp(-max(-35,min(35,beta[0]+sum(b*v for b,v in zip(beta[1:],row)))))) for row in x]


def auc_roc(y, p):
    pos=sum(y); neg=len(y)-pos
    if not pos or not neg: return None
    pairs=sorted(zip(p,y)); rank_sum=0.; i=0
    while i<len(pairs):
        j=i+1
        while j<len(pairs) and pairs[j][0]==pairs[i][0]: j+=1
        rank=(i+1+j)/2; rank_sum += rank*sum(v for _,v in pairs[i:j]); i=j
    return (rank_sum-pos*(pos+1)/2)/(pos*neg)


def auc_pr(y, p):
    pos=sum(y)
    if not pos: return None
    ordered=sorted(zip(p,y), reverse=True); tp=fp=0; prev_recall=0.; area=0.; i=0
    while i < len(ordered):
        j=i+1
        while j<len(ordered) and ordered[j][0]==ordered[i][0]: j+=1
        labels=[label for _,label in ordered[i:j]]; tp += sum(labels); fp += len(labels)-sum(labels)
        recall=tp/pos; precision=tp/(tp+fp)
        area += (recall-prev_recall)*precision; prev_recall=recall
        i=j
    return area


def _calibration(y, p):
    if len(set(y))<2: return (None,None)
    logits=[[math.log(max(1e-15,min(1-1e-15,v))/(1-max(1e-15,min(1-1e-15,v))))] for v in p]
    model=fit_logistic(logits,list(y),math.inf,enforce_grid=False)
    return model["coefficients"][0],model["coefficients"][1]


def training_bin_edges(values: list[float]) -> list[float]:
    return [_quantile(values, q/5) for q in range(1,5)]


def _bin(value, edges): return sum(value > edge for edge in edges)


def evaluate(y, p, b0, edges):
    eps=METRIC_PROBABILITY_EPSILON; losses=[-(yi*math.log(max(eps,min(1-eps,pi)))+(1-yi)*math.log(max(eps,min(1-eps,1-pi)))) for yi,pi in zip(y,p)]
    briers=[(pi-yi)**2 for yi,pi in zip(y,p)]; b0_brier=sum((b0-yi)**2 for yi in y)/len(y)
    intercept,slope=_calibration(y,p); bins=[]
    for index in range(5):
        ids=[i for i,v in enumerate(p) if _bin(v,edges)==index]
        bins.append({"bin":index+1,"n":len(ids),"mean_probability":statistics.fmean(p[i] for i in ids) if ids else None,
                     "observed_continuation":statistics.fmean(y[i] for i in ids) if ids else None,
                     "lift_vs_b0":statistics.fmean(y[i] for i in ids)-b0 if ids else None})
    pred=[v>=.5 for v in p]; tp=sum(a and b for a,b in zip(pred,y)); fp=sum(a and not b for a,b in zip(pred,y));
    tn=sum(not a and not b for a,b in zip(pred,y)); fn=sum(not a and b for a,b in zip(pred,y))
    return {"n":len(y),"positive":sum(y),"negative":len(y)-sum(y),"base_rate":statistics.fmean(y),
            "roc_auc":auc_roc(y,p),"pr_auc":auc_pr(y,p),"log_loss":statistics.fmean(losses),
            "brier":statistics.fmean(briers),"brier_skill_vs_b0":1-statistics.fmean(briers)/b0_brier if b0_brier else None,
            "calibration_intercept":intercept,"calibration_slope":slope,"reliability":bins,
            "threshold_0_5":{"tp":tp,"fp":fp,"tn":tn,"fn":fn,"accuracy":(tp+tn)/len(y)},
            "row_log_loss":losses,"row_brier":briers}


def block_bootstrap(rows, losses_a, losses_b, brier_a, brier_b, seed=SEED, replications=BOOTSTRAP_REPLICATIONS):
    groups=defaultdict(list)
    for i,row in enumerate(rows): groups[row["month"]].append(i)
    months=sorted(groups); rng=random.Random(seed); ll=[]; br=[]; sampled_integrity=True
    for _ in range(replications):
        chosen=[rng.choice(months) for __ in months]; indices=[i for m in chosen for i in groups[m]]
        sampled_integrity &= all(set(groups[m]).issubset(set(indices)) for m in set(chosen))
        ll.append(statistics.fmean(losses_a[i]-losses_b[i] for i in indices))
        br.append(statistics.fmean(brier_a[i]-brier_b[i] for i in indices))
    return {"comparison_direction":"first_minus_second; negative favors first","seed":seed,"replications":replications,
            "block":"UTC calendar month; all symbols/events retained","quantile_rule":"linear type-7",
            "month_block_integrity":sampled_integrity,
            "log_loss":{"mean":statistics.fmean(ll),"q025":_quantile(ll,.025),"q975":_quantile(ll,.975)},
            "brier":{"mean":statistics.fmean(br),"q025":_quantile(br,.025),"q975":_quantile(br,.975)}}


def _group_metrics(rows,y,p,b0):
    result={}
    for grouping,keyfn in (("symbol",lambda r:r["symbol"]),("month",lambda r:r["month"]),("quarter",lambda r:r["quarter"])):
        groups=defaultdict(list)
        for i,row in enumerate(rows): groups[keyfn(row)].append(i)
        result[grouping]={}
        for key,ids in sorted(groups.items()):
            yy=[y[i] for i in ids]; pp=[p[i] for i in ids]
            result[grouping][key]={"n":len(ids),"positive":sum(yy),"base_rate":statistics.fmean(yy),
                "roc_auc":auc_roc(yy,pp),"pr_auc":auc_pr(yy,pp),
                "log_loss":statistics.fmean(-(a*math.log(max(1e-15,b))+(1-a)*math.log(max(1e-15,1-b))) for a,b in zip(yy,pp)),
                "brier":statistics.fmean((a-b)**2 for a,b in zip(yy,pp))}
    return result


def _fit_and_score(model_name,c,features,train,valid,b0):
    prep=fit_preprocessor(train,features); tx=transform(train,prep); vx=transform(valid,prep); ty=[r["label"] for r in train]; vy=[r["label"] for r in valid]
    model=fit_logistic(tx,ty,c); train_p=predict_logistic(model,tx,[r["milestone_ms"] for r in train]); p=predict_logistic(model,vx,[r["milestone_ms"] for r in valid])
    edges=training_bin_edges(train_p); metrics=evaluate(vy,p,b0,edges)
    names=["intercept"]+list(features)+["symbol="+s for s in prep["categorical"]["symbol"]]+list(CALENDAR_COLUMNS)
    coefficients=[{"name":n,"coefficient":v,"sign":"positive" if v>0 else "negative" if v<0 else "zero"} for n,v in zip(names,model["coefficients"])]
    robust=[]
    for j,name in enumerate(features):
        vals=sorted(row[j] for row in tx); low=_quantile(vals,.1); high=_quantile(vals,.9); base=[0.]*len(tx[0]);
        lo=base[:]; hi=base[:]; lo[j]=low; hi[j]=high
        probs=predict_logistic(model,[lo,hi],[train[0]["milestone_ms"]]*2)
        robust.append({"feature":name,"training_standardized_q10":low,"training_standardized_q90":high,"probability_change":probs[1]-probs[0]})
    artifact={"model":model_name,"preprocessing":prep,"model_spec":model,"coefficient_names":names}
    artifact["sha256"]=canonical_hash(artifact)
    return artifact,p,metrics,coefficients,robust


def _fit_final_model(model_name: str, c: float, features: tuple[str, ...], rows: list[dict], row_hash: str) -> tuple[dict, dict]:
    prep = fit_preprocessor(rows, features)
    x = transform(rows, prep); y = [r["label"] for r in rows]
    model = fit_logistic(x, y, c)
    if not model["converged"]:
        raise RuntimeError(f"final {model_name} failed convergence")
    names = ["intercept"] + list(features) + ["symbol=" + s for s in prep["categorical"]["symbol"]] + list(CALENDAR_COLUMNS)
    artifact = {"model": model_name, "target_training_row_hash": row_hash, "training_rows": len(rows),
                "coefficient_names": names, "model_spec": model}
    artifact["sha256"] = canonical_hash(artifact)
    return prep, artifact


def _b2(train,valid,feature,b0):
    values=[r["features"][feature] for r in train]; edges=training_bin_edges(values); ty=[r["label"] for r in train]
    global_rate=statistics.fmean(ty); rates=[]
    for b in range(5):
        labels=[y for r,y in zip(train,ty) if _bin(r["features"][feature],edges)==b]
        rates.append(statistics.fmean(labels) if labels else global_rate)
    p=[rates[_bin(r["features"][feature],edges)] for r in valid]; train_p=[rates[_bin(r["features"][feature],edges)] for r in train]
    return {"feature":feature,"training_quintile_edges":edges,"training_bin_rates":rates},p,evaluate([r["label"] for r in valid],p,b0,training_bin_edges(train_p))


def run_t3a(repo: Path, output: Path) -> dict:
    datasets, verified=load_accepted_t1t2(repo); output.mkdir(parents=True,exist_ok=True)
    ledger=[]; predictions=[]; metrics_rows=[]; preprocessors={}; models={}; coefficients={}; robust_changes={}; comparisons={}; folds_summary={}
    selected={}; all_config_metrics={t:{"L1":defaultdict(list),"L2":defaultdict(list)} for t in datasets}
    for target,rows in datasets.items():
        folds_summary[target]={}; comparisons[target]={}
        for fold in FOLDS:
            train,valid,purged=chronological_split(rows,fold); ty=[r["label"] for r in train]; vy=[r["label"] for r in valid]; b0=statistics.fmean(ty)
            folds_summary[target][fold]={"train":{"n":len(train),"positive":sum(ty),"negative":len(ty)-sum(ty),"base_rate":b0},"validation":{"n":len(valid),"positive":sum(vy),"negative":len(vy)-sum(vy),"base_rate":statistics.fmean(vy)},"purged":purged}
            attempt_base={"target":target,"fold":fold,"seed":SEED}
            b0p=[b0]*len(valid); b0m=evaluate(vy,b0p,b0,training_bin_edges([b0]*len(train)))
            ledger.append({**attempt_base,"baseline_model":"B0","C":None,"feature_specification":"training continuation fraction","preprocessing_hash":None,"fit_status":"success","metrics":{k:v for k,v in b0m.items() if not k.startswith('row_')},"model_artifact_hash":canonical_hash({"p":b0})})
            metrics_rows.append({"target":target,"fold":fold,"model":"B0","C":None,"metrics":b0m})
            predictions.append({"target":target,"fold":fold,"model":"B0","C":None,"probabilities":b0p,"row_keys":[r["trade_id"] for r in valid]})
            b1={"always_continuation":{"tp":sum(vy),"fp":len(vy)-sum(vy),"tn":0,"fn":0,"accuracy":statistics.fmean(vy)},"always_fallback":{"tp":0,"fp":0,"tn":len(vy)-sum(vy),"fn":sum(vy),"accuracy":1-statistics.fmean(vy)}}
            ledger.append({**attempt_base,"baseline_model":"B1","C":None,"feature_specification":"constant confusion/accuracy only","preprocessing_hash":None,"fit_status":"success","metrics":b1,"model_artifact_hash":canonical_hash(b1)})
            for feature in B2_FEATURES:
                spec,p,m=_b2(train,valid,feature,b0); metrics_rows.append({"target":target,"fold":fold,"model":"B2","feature":feature,"C":None,"metrics":m,"group_metrics":_group_metrics(valid,vy,p,b0)})
                ledger.append({**attempt_base,"baseline_model":"B2","C":None,"feature_specification":feature,"preprocessing_hash":canonical_hash(spec),"fit_status":"success","metrics":{k:v for k,v in m.items() if not k.startswith('row_')},"model_artifact_hash":canonical_hash(spec)})
            fold_models={"B0":b0m}
            for model_name,c,features in [("L0",1.0,L0_FEATURES)]+[(m,c,LOCAL_FEATURES if m=="L1" else FEATURE_COLUMNS) for m in ("L1","L2") for c in C_GRID]:
                artifact,p,m,coef,robust=_fit_and_score(model_name,c,features,train,valid,b0); key=f"{target}_{fold}_{model_name}_C{c:g}"
                preprocessors[key]=artifact["preprocessing"]; models[key]=artifact; coefficients[key]=coef; robust_changes[key]=robust
                metrics_rows.append({"target":target,"fold":fold,"model":model_name,"C":c,"metrics":m,"group_metrics":_group_metrics(valid,vy,p,b0)})
                predictions.append({"target":target,"fold":fold,"model":model_name,"C":c,"probabilities":p,"row_keys":[r["trade_id"] for r in valid]})
                ledger.append({**attempt_base,"baseline_model":model_name,"C":c,"feature_specification":list(features),"preprocessing_hash":artifact["preprocessing"]["sha256"],"fit_status":"success" if artifact["model_spec"]["converged"] else "success_max_iterations","metrics":{k:v for k,v in m.items() if not k.startswith('row_')},"model_artifact_hash":artifact["sha256"]})
                fold_models[f"{model_name}_{c:g}"]=m
                if model_name in ("L1","L2"): all_config_metrics[target][model_name][c].append((m["log_loss"],m["brier"]))
            def compare(first,second,label):
                a=fold_models[first]; b=fold_models[second]
                comparisons[target][f"{fold}_{label}"]=block_bootstrap(valid,a["row_log_loss"],b["row_log_loss"],a["row_brier"],b["row_brier"])
            for c in C_GRID: compare(f"L1_{c:g}","L0_1",f"L1_C{c:g}_minus_L0")
            for c in C_GRID: compare(f"L2_{c:g}",f"L1_{c:g}",f"L2_C{c:g}_minus_L1_C{c:g}")
        selected[target]={}
        for model_name in ("L1","L2"):
            ranking=[]
            for c,values in all_config_metrics[target][model_name].items(): ranking.append((statistics.fmean(v[0] for v in values),statistics.fmean(v[1] for v in values),c))
            ranking.sort(); selected[target][model_name]={"C":ranking[0][2],"selection_ranking":[{"mean_log_loss":a,"mean_brier":b,"C":c} for a,b,c in ranking]}
    final_training={}; final_preprocessing={}; final_models={}
    for target, rows in datasets.items():
        final_rows = final_2024_training_rows(rows); row_hash = _row_key_hash(final_rows)
        labels = [r["label"] for r in final_rows]
        final_training[target] = {"interval_start_ms": FOLDS["fold_b"]["train"][0], "interval_end_ms_exclusive": T3A_END_MS,
            "label_resolution_end_ms_exclusive": T3A_END_MS, "n": len(final_rows), "positive": sum(labels),
            "negative": len(labels)-sum(labels), "ordered_row_key_sha256": row_hash,
            "ordered_row_keys": [[r["trade_id"], r["milestone_id"]] for r in final_rows]}
        for model_name, c, features in (("L0", 1.0, L0_FEATURES),
                                        ("L1", selected[target]["L1"]["C"], LOCAL_FEATURES),
                                        ("L2", selected[target]["L2"]["C"], FEATURE_COLUMNS)):
            key=f"{target}_{model_name}"
            prep, model = _fit_final_model(model_name,c,features,final_rows,row_hash)
            final_preprocessing[key]=prep; final_models[key]=model
    freeze={}
    schema_hash=json.loads((repo/"artifacts/c3_milestone_state_continuation/feature_schema.json").read_text())["schema_sha256"]
    revision=subprocess.run(["git","rev-parse","HEAD"],cwd=repo,text=True,capture_output=True,check=True).stdout.strip()
    source_paths = ("src/binance_data_foundation/c3_t3a.py", "src/binance_data_foundation/c3_t3a_cli.py",
                    "tests/test_c3_t3a.py", "artifacts/c3_milestone_state_continuation/feature_schema.json",
                    "contracts/C3_milestone_state_continuation_CONTRACT.md")
    source_hashes = {path: sha256_file(repo/path) for path in source_paths}
    config_identity = canonical_hash({"folds":FOLDS,"C_grid":C_GRID,"seed":SEED,"bootstrap_replications":BOOTSTRAP_REPLICATIONS,
        "bootstrap_quantiles":BOOTSTRAP_QUANTILES,"features":FEATURE_COLUMNS,"local_features":LOCAL_FEATURES,
        "symbols":SYMBOL_ORDER,"calendar":CALENDAR_COLUMNS,"solver_tolerance":SOLVER_TOLERANCE,
        "solver_max_iterations":SOLVER_MAX_ITERATIONS,"metric_epsilon":METRIC_PROBABILITY_EPSILON})
    for target in datasets:
        final_keys=[f"{target}_{name}" for name in ("L0","L1","L2")]
        target_files = {name:digest for name,digest in verified.items() if not name.startswith("m1_") and not name.startswith("m2_") or name.startswith(target.lower()+"_")}
        freeze[target]={"freeze_version":"C3_T3A_SPECIFICATION_FREEZE_V2_CALENDAR_SCALED","target":target,
            "selected_L1_C":selected[target]["L1"]["C"],"selected_L2_C":selected[target]["L2"]["C"],
            "L0":{"C":1.0,"features":list(L0_FEATURES)},"L1_features_A_E":list(LOCAL_FEATURES),"L2_features_A_F":list(FEATURE_COLUMNS),
            "ordered_35_feature_schema":list(FEATURE_COLUMNS),"feature_schema_hash":schema_hash,
            "final_2024_training":{"milestone_interval":"[2024-01-01T00:00:00Z,2025-01-01T00:00:00Z)",
                "label_resolution_boundary":"strictly before 2025-01-01T00:00:00Z","feature_eligible":True,"non_null_label":True,**final_training[target]},
            "locked_2025_evaluation":{"milestone_interval":"[2025-01-01T00:00:00Z,2026-01-01T00:00:00Z)",
                "label_resolution_boundary":"strictly before 2026-01-01T00:00:00Z","feature_eligible":True,"non_null_label":True,
                "selection_rule":"milestone timestamp partitions rows; exclude null/censored/ambiguous and resolution at-or-after boundary",
                "contents_opened":False,"predictions_computed":False,"metrics_computed":False},
            "symbol_encoding":{"order":list(SYMBOL_ORDER),"convention":"five full one-hot indicators in stated order; intercept separately unpenalized; indicators penalized"},
            "calendar_controls":{"order":list(CALENDAR_COLUMNS),"formula":{"sin_month":"sin(2*pi*month/12)","cos_month":"cos(2*pi*month/12)"},
                "preprocessing":"training-only median center and IQR scale; zero-IQR center without scaling"},
            "continuous_preprocessing":{"rule":"training-only median center and divide by training IQR","zero_iqr":"center but do not scale","imputation":None,"feature_selection":None,"interactions":None},
            "model_implementation":{"library":"Python standard library","python_version":platform.python_version(),
                "implementation":"c3-pure-python-newton-l2-v2-calendar-scaled","intercept":"included and unpenalized","penalty":"L2 on every non-intercept coefficient",
                "C_semantics":"objective=sum_log_loss + squared_L2_norm/(2*C)","solver":"Newton/IRLS with deterministic Gaussian elimination",
                "tolerance":SOLVER_TOLERANCE,"maximum_iterations":SOLVER_MAX_ITERATIONS,"convergence_requirement":"required; final fit raises on non-convergence",
                "class_weighting":"none","probability":"raw logistic sigmoid with linear predictor clipped to [-35,35] before exp",
                "metric_probability_clipping_epsilon":METRIC_PROBABILITY_EPSILON,"calibrator":None},
            "random_seeds":{"bootstrap":SEED,"model_fit":None},
            "bootstrap":{"block":"UTC calendar month; all symbols/events together","replications":BOOTSTRAP_REPLICATIONS,
                "quantiles":list(BOOTSTRAP_QUANTILES),"quantile_rule":"linear type-7","paired_differences":"first model minus second"},
            "evaluation_metrics_2025":["row counts","continuation base rate","ROC AUC","PR AUC","log loss","Brier","Brier skill vs B0","calibration intercept","calibration slope","five-bin training-defined reliability","observed continuation and lift by bin","0.5 confusion/accuracy secondary","per-symbol/month/quarter summaries","calendar-month paired block bootstrap"],
            "final_artifacts":{key:{"model_sha256":final_models[key]["sha256"],"preprocessing_sha256":final_preprocessing[key]["sha256"],"C":final_models[key]["model_spec"]["C"],"coefficient_names":final_models[key]["coefficient_names"]} for key in final_keys},
            "dataset_hashes":target_files,"source_and_test_hashes":source_hashes,"repository_revision":revision,
            "repository_revision_contains_t3a":False,"dirty_untracked_source_hashes_required":True,"configuration_sha256":config_identity,
            "split_definitions":FOLDS,"selection":selected[target],"threshold_action_mapping":None,"2025_opened":False,"2026_accessed":False}
        freeze[target]["sha256"]=canonical_hash(freeze[target])
    for attempt in ledger: attempt.setdefault("failure", None)
    payloads={"fold_summary.json":folds_summary,"metrics.json":metrics_rows,"predictions.json":predictions,"preprocessing.json":preprocessors,"models.json":models,"coefficients.json":coefficients,"robust_probability_changes.json":robust_changes,"comparisons.json":comparisons,"attempt_ledger.json":ledger,"final_training.json":final_training,"final_preprocessing.json":final_preprocessing,"final_models.json":final_models,"freeze_specifications.json":freeze}
    for name,value in payloads.items(): write_json(output/name,value)
    ledger_jsonl=output/"attempt_ledger.jsonl"
    ledger_jsonl.write_text("".join(json.dumps(x,sort_keys=True,separators=(",",":"),allow_nan=False)+"\n" for x in ledger),encoding="utf-8")
    hashes={name:sha256_file(output/name) for name in payloads}
    hashes["attempt_ledger.jsonl"]=sha256_file(ledger_jsonl)
    manifest={"version":"C3_T3A_REPRODUCIBILITY_V1","repository":{"branch":subprocess.run(["git","branch","--show-current"],cwd=repo,text=True,capture_output=True).stdout.strip(),"head":revision,"remote":subprocess.run(["git","remote","get-url","origin"],cwd=repo,text=True,capture_output=True).stdout.strip()},
        "environment":{"conda":os.environ.get("CONDA_DEFAULT_ENV",""),"python":platform.python_version(),"interpreter":sys.executable},"verified_t1t2_hashes":verified,"core_hashes":hashes,
        "feature_eligible_totals":{"M1":806,"M2":546},"development_rows_loaded":{"M1":len(datasets["M1"]),"M2":len(datasets["M2"])},"limitations":{"M1":"fastest excluded arrivals are under 10 minutes","M2":"fastest excluded arrivals are within 5 minutes","path_efficiency_5m":"unchanged; no imputation"},
        "attempt_count":len(ledger),"expected_attempt_count":56,"attempt_ledger_semantics":"immutable complete per-run ledger; cumulative research-history ledger not produced","configuration_sha256":config_identity,"source_and_test_hashes":source_hashes,"bootstrap":{"seed":SEED,"replications":BOOTSTRAP_REPLICATIONS,"quantiles":BOOTSTRAP_QUANTILES,"rule":"linear type-7","block":"calendar month"},
        "seals":{"2025_scored":False,"2025_predictive_outcomes_inspected":False,"2026_paths_enumerated":False,"2026_data_accessed":False},"economic_analysis_run":False}
    write_json(output/"reproducibility_manifest.json",manifest)
    return manifest


def verify_rebuild(repo: Path, output: Path) -> dict:
    published_manifest = json.loads((output/"reproducibility_manifest.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="c3_t3a_rebuild_a_") as first_name, tempfile.TemporaryDirectory(prefix="c3_t3a_rebuild_b_") as second_name:
        a=run_t3a(repo,Path(first_name)); b=run_t3a(repo,Path(second_name))
    same=a["core_hashes"]==b["core_hashes"]
    published_same=a["core_hashes"]==published_manifest["core_hashes"]
    result={"version":"C3_T3A_INDEPENDENT_REBUILD_V2","run_a_core_hashes":a["core_hashes"],"run_b_core_hashes":b["core_hashes"],
        "run_a_equals_run_b":same,"published_core_hashes":published_manifest["core_hashes"],"rebuild_equals_published":published_same,
        "environment":published_manifest["environment"],"configuration_sha256":published_manifest["configuration_sha256"],
        "seed_and_config":{"bootstrap":published_manifest["bootstrap"],"C_grid":list(C_GRID),"solver_tolerance":SOLVER_TOLERANCE,"solver_max_iterations":SOLVER_MAX_ITERATIONS}}
    result["evidence_sha256"]=canonical_hash(result)
    write_json(output/"independent_rebuild.json",result)
    if not same or not published_same: raise AssertionError("T3-A rebuild differs")
    return result
