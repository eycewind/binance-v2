"""Locked C3 T3-B 2025 evaluation using only accepted frozen T3-A artifacts."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import platform
import statistics
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

from .c3_milestone import FEATURE_COLUMNS
from .c3_t3a import (BOOTSTRAP_REPLICATIONS, CALENDAR_COLUMNS, CONTEXT_FEATURES,
                     L0_FEATURES, LOCAL_FEATURES, METRIC_PROBABILITY_EPSILON,
                     SEED, SYMBOL_ORDER, _bin, _calendar_values, _group_metrics,
                     _quantile, auc_pr, auc_roc, block_bootstrap, canonical_hash,
                     evaluate, sha256_file, training_bin_edges, write_json)

START_2025_MS = 1_735_689_600_000
END_2025_MS = 1_767_225_600_000
T3A_DIR = Path("artifacts/c3_milestone_state_continuation/t3a_2024")
INPUT_DIR = Path("artifacts/c3_milestone_state_continuation")
OUTPUT_FILES = (
    "predictions.csv", "metrics.json", "comparisons.json", "calibration.json",
    "stability.json", "interpretation.json", "selection_summary.json",
)


def _canonical_without_sha(value: dict) -> str:
    copy = dict(value); copy.pop("sha256", None)
    return canonical_hash(copy)


def verify_freeze(repo: Path) -> dict:
    root, t3a = repo / INPUT_DIR, repo / T3A_DIR
    freeze = json.loads((t3a / "freeze_specifications.json").read_text(encoding="utf-8"))
    models = json.loads((t3a / "final_models.json").read_text(encoding="utf-8"))
    preps = json.loads((t3a / "final_preprocessing.json").read_text(encoding="utf-8"))
    verified = {"freeze": {}, "files": {}, "models": {}, "preprocessing": {}}
    for target in ("M1", "M2"):
        spec = freeze[target]
        if _canonical_without_sha(spec) != spec["sha256"]:
            raise ValueError(f"{target} freeze specification hash mismatch")
        verified["freeze"][target] = spec["sha256"]
        if (spec["selected_L1_C"], spec["selected_L2_C"], spec["L0"]["C"]) != (.1, .1, 1.0):
            raise ValueError(f"{target} frozen model choices differ from locked T3-B")
        for name, expected in {**spec["dataset_hashes"], **spec["source_and_test_hashes"]}.items():
            path = repo / name if "/" in name else root / name
            actual = sha256_file(path)
            if actual != expected: raise ValueError(f"frozen file hash mismatch: {name}")
            verified["files"][name] = actual
        for model_name in ("L0", "L1", "L2"):
            key = f"{target}_{model_name}"; declared = spec["final_artifacts"][key]
            if _canonical_without_sha(models[key]) != declared["model_sha256"]:
                raise ValueError(f"frozen model hash mismatch: {key}")
            if _canonical_without_sha(preps[key]) != declared["preprocessing_sha256"]:
                raise ValueError(f"frozen preprocessing hash mismatch: {key}")
            if models[key]["sha256"] != declared["model_sha256"] or preps[key]["sha256"] != declared["preprocessing_sha256"]:
                raise ValueError(f"embedded frozen artifact hash mismatch: {key}")
            if models[key]["coefficient_names"] != declared["coefficient_names"]:
                raise ValueError(f"frozen coefficient order mismatch: {key}")
            verified["models"][key] = models[key]["sha256"]
            verified["preprocessing"][key] = preps[key]["sha256"]
    return {"freeze": freeze, "models": models, "preprocessing": preps, "verified": verified}


def _read_locked_rows(repo: Path, target: str) -> tuple[list[dict], list[dict], dict]:
    """Gate on accepted audit timestamps before consuming outcome/feature values."""
    root = repo / INPUT_DIR; prefix = target.lower(); audit = {}
    counts = Counter()
    with (root / f"{prefix}_audit.csv").open(newline="", encoding="utf-8") as handle:
        for raw in csv.DictReader(handle):
            raw_ms = raw["milestone_interval_start_ms"]
            if raw_ms in (None, ""): continue
            milestone_ms = int(raw_ms)
            if not (START_2025_MS <= milestone_ms < END_2025_MS): continue
            identity = (raw["trade_id"], raw["milestone_id"])
            audit[identity] = (raw["symbol"], milestone_ms, raw["milestone_interval_start_ts"])
            counts["candidate"] += 1
            if raw.get("feature_eligible") not in ("True", "true", "1", True): counts["feature_ineligible"] += 1
    outcomes = {}
    with (root / f"{prefix}_outcomes.csv").open(newline="", encoding="utf-8") as handle:
        for raw in csv.DictReader(handle):
            identity = (raw["trade_id"], raw["milestone_id"])
            if identity not in audit: continue
            label = raw["label"]
            if label not in ("0", "1"): counts["null_or_non_supervised_label"] += 1; continue
            resolution_raw = raw["label_resolution_ms"]
            if resolution_raw in (None, ""): counts["unresolved_at_2025_evaluation_boundary"] += 1; continue
            resolution = int(resolution_raw)
            if resolution >= END_2025_MS:
                counts["unresolved_at_2025_evaluation_boundary"] += 1; continue
            outcomes[identity] = int(label)
    rows = []
    with (root / f"{prefix}_features.csv").open(newline="", encoding="utf-8") as fh, \
         (root / f"{prefix}_feature_row_keys.csv").open(newline="", encoding="utf-8") as kh:
        fr, kr = csv.DictReader(fh), csv.DictReader(kh)
        if tuple(fr.fieldnames or ()) != FEATURE_COLUMNS: raise ValueError("exact frozen feature order violated")
        for index, (feature, key) in enumerate(zip(fr, kr)):
            if int(key["model_row_index"]) != index: raise ValueError("non-contiguous model row index")
            identity = (key["trade_id"], key["milestone_id"])
            if identity not in audit or identity not in outcomes: continue
            symbol, milestone_ms, milestone_ts = audit[identity]
            month = milestone_ts[:7]
            rows.append({"trade_id": identity[0], "milestone_id": identity[1], "symbol": symbol,
                         "milestone_ms": milestone_ms, "milestone_ts": milestone_ts, "label": outcomes[identity],
                         "month": month, "quarter": month[:4]+"-Q"+str((int(month[5:7])-1)//3+1),
                         "features": {name: float(feature[name]) for name in FEATURE_COLUMNS}})
        if next(fr, None) is not None or next(kr, None) is not None: raise ValueError("feature/key count mismatch")
    rows.sort(key=lambda r: (r["milestone_ms"], r["symbol"], r["trade_id"], r["milestone_id"]))
    counts["eligible_supervised"] = len(rows)
    return rows, list(audit), dict(counts)


def _read_final_training_rows(repo: Path, target: str, expected_keys: list[list[str]]) -> list[dict]:
    root=repo/INPUT_DIR; prefix=target.lower(); wanted={tuple(x) for x in expected_keys}; audit={}
    with (root/f"{prefix}_audit.csv").open(newline="",encoding="utf-8") as h:
        for r in csv.DictReader(h):
            key=(r["trade_id"],r["milestone_id"])
            if key in wanted: audit[key]=(r["symbol"],int(r["milestone_interval_start_ms"]),r["milestone_interval_start_ts"])
    labels={}
    with (root/f"{prefix}_outcomes.csv").open(newline="",encoding="utf-8") as h:
        for r in csv.DictReader(h):
            key=(r["trade_id"],r["milestone_id"])
            if key in wanted: labels[key]=int(r["label"])
    by_key={}
    with (root/f"{prefix}_features.csv").open(newline="",encoding="utf-8") as fh,(root/f"{prefix}_feature_row_keys.csv").open(newline="",encoding="utf-8") as kh:
        for f,k in zip(csv.DictReader(fh),csv.DictReader(kh)):
            key=(k["trade_id"],k["milestone_id"])
            if key in wanted:
                symbol,ms,ts=audit[key]; by_key[key]={"trade_id":key[0],"milestone_id":key[1],"symbol":symbol,"milestone_ms":ms,"milestone_ts":ts,"label":labels[key],"features":{n:float(f[n]) for n in FEATURE_COLUMNS}}
    rows=[by_key[tuple(k)] for k in expected_keys]
    if len(rows)!=len(expected_keys): raise ValueError("frozen final-training row set unavailable")
    return rows


def apply_frozen_preprocessor(rows: list[dict], spec: dict) -> list[list[float]]:
    vectors=[]
    if tuple(spec["categorical"]["symbol"]) != SYMBOL_ORDER: raise ValueError("frozen symbol encoding mismatch")
    if tuple(spec["calendar_order"]) != CALENDAR_COLUMNS: raise ValueError("frozen calendar encoding mismatch")
    for row in rows:
        if not (START_2025_MS <= row["milestone_ms"] < END_2025_MS) and row["milestone_ms"] >= END_2025_MS:
            raise ValueError("T3-B rejects timestamp at or after 2026 boundary")
        v=[]
        for name in spec["continuous_order"]:
            rule=spec["continuous"][name]; centered=row["features"][name]-rule["median"]
            v.append(centered if rule["zero_iqr"] else centered/rule["iqr"])
        if row["symbol"] not in spec["categorical"]["symbol"]: raise ValueError("unknown frozen symbol")
        v.extend(float(row["symbol"]==s) for s in spec["categorical"]["symbol"])
        for name,raw in zip(spec["calendar_order"],_calendar_values(row["milestone_ts"])):
            rule=spec["calendar"][name]; centered=raw-rule["median"]
            v.append(centered if rule["zero_iqr"] else centered/rule["iqr"])
        vectors.append(v)
    return vectors


def score_frozen(rows: list[dict], prep: dict, model: dict) -> list[float]:
    x=apply_frozen_preprocessor(rows,prep); beta=model["model_spec"]["coefficients"]
    if len(beta) != len(model["coefficient_names"]): raise ValueError("frozen coefficient vector mismatch")
    if len(beta) != (len(x[0])+1 if x else len(beta)): raise ValueError("frozen feature order/width mismatch")
    return [1/(1+math.exp(-max(-35,min(35,beta[0]+sum(a*b for a,b in zip(beta[1:],row)))))) for row in x]


def _strip_rows(metrics: dict) -> dict: return {k:v for k,v in metrics.items() if not k.startswith("row_")}


def _dominance(rows, metrics_by_model):
    out={}
    for grouping in ("symbol","month","quarter"):
        counts=Counter(r[grouping] for r in rows); total=len(rows); largest=max(counts.items(),key=lambda x:(x[1],x[0]))
        out[grouping]={"counts":dict(sorted(counts.items())),"largest_group":largest[0],"largest_share":largest[1]/total,
                       "performance_dominated":largest[1]/total>.5}
    return out


def _interpret(target, metrics, comparisons, stability):
    l10=comparisons["L1_minus_L0"]; l21=comparisons["L2_minus_L1"]
    path_good=metrics["L1"]["log_loss"]<metrics["L0"]["log_loss"] and metrics["L1"]["brier"]<metrics["L0"]["brier"]
    path_interval=l10["log_loss"]["q975"]<0 and l10["brier"]["q975"]<0
    calibrated=(metrics["L1"]["calibration_slope"] is not None and 0.5<=metrics["L1"]["calibration_slope"]<=1.5 and abs(metrics["L1"]["calibration_intercept"])<=.5)
    dominated=any(v["performance_dominated"] for v in stability["dominance"].values())
    if path_good and path_interval and calibrated and not dominated: verdict="SUPPORTS CONTINUATION-STATE SIGNAL"
    elif not path_good and l10["log_loss"]["q025"]>=0 and l10["brier"]["q025"]>=0: verdict="COUNTS AGAINST"
    else: verdict="MIXED"
    return {"target":target,"verdict":verdict,"path_state_improves_both_proper_scores":path_good,
            "path_state_both_intervals_below_zero":path_interval,"L1_calibration_reasonable":calibrated,
            "dominance_flag":dominated,"cross_asset_both_intervals_below_zero":l21["log_loss"]["q975"]<0 and l21["brier"]["q975"]<0,
            "rule":"contract evidence panel; no single metric or AUC threshold determines verdict"}


def run_t3b(repo: Path, output: Path) -> dict:
    frozen=verify_freeze(repo); output.mkdir(parents=True,exist_ok=True)
    all_metrics={}; all_comparisons={}; calibration={}; stability={}; predictions=[]; selections={}
    for target in ("M1","M2"):
        spec=frozen["freeze"][target]; rows,_,counts=_read_locked_rows(repo,target)
        if not rows: raise ValueError(f"no eligible locked 2025 rows for {target}")
        train=_read_final_training_rows(repo,target,spec["final_2024_training"]["ordered_row_keys"])
        y=[r["label"] for r in rows]; b0=sum(r["label"] for r in train)/len(train)
        probabilities={"B0":[b0]*len(rows)}; edges={"B0":training_bin_edges([b0]*len(train))}
        for name in ("L0","L1","L2"):
            key=f"{target}_{name}"; probabilities[name]=score_frozen(rows,frozen["preprocessing"][key],frozen["models"][key])
            edges[name]=training_bin_edges(score_frozen(train,frozen["preprocessing"][key],frozen["models"][key]))
        target_metrics={name:evaluate(y,p,b0,edges[name]) for name,p in probabilities.items()}
        groups={name:_group_metrics(rows,y,p,b0) for name,p in probabilities.items()}
        comparisons={
            "L1_minus_L0":block_bootstrap(rows,target_metrics["L1"]["row_log_loss"],target_metrics["L0"]["row_log_loss"],target_metrics["L1"]["row_brier"],target_metrics["L0"]["row_brier"]),
            "L2_minus_L1":block_bootstrap(rows,target_metrics["L2"]["row_log_loss"],target_metrics["L1"]["row_log_loss"],target_metrics["L2"]["row_brier"],target_metrics["L1"]["row_brier"])}
        stab={"group_metrics":groups,"dominance":_dominance(rows,target_metrics),"selection_counts":counts,
              "coefficient_scoring_consistency":{"assessment":"observed scoring behavior reported without causal sign attribution or model alteration",
              "mean_probability_by_model":{k:statistics.fmean(v) for k,v in probabilities.items()}}}
        all_metrics[target]={k:_strip_rows(v) for k,v in target_metrics.items()}; all_comparisons[target]=comparisons
        calibration[target]={k:{"intercept":v["calibration_intercept"],"slope":v["calibration_slope"],"reliability":v["reliability"],"frozen_training_bin_edges":edges[k]} for k,v in target_metrics.items()}
        stability[target]=stab; selections[target]={"n":len(rows),"positive":sum(y),"negative":len(y)-sum(y),**counts}
        for i,row in enumerate(rows):
            predictions.append({"target":target,"trade_id":row["trade_id"],"milestone_id":row["milestone_id"],"symbol":row["symbol"],"milestone_ts":row["milestone_ts"],"label":row["label"],**{f"p_{k.lower()}":probabilities[k][i] for k in probabilities}})
    interpretations={t:_interpret(t,all_metrics[t],all_comparisons[t],stability[t]) for t in ("M1","M2")}
    interpretations["overall"]={"verdict":"; ".join(f"{t}: {interpretations[t]['verdict']}" for t in ("M1","M2")),"pooled_or_averaged":False}
    payloads={"metrics.json":all_metrics,"comparisons.json":all_comparisons,"calibration.json":calibration,"stability.json":stability,"interpretation.json":interpretations,"selection_summary.json":selections}
    with (output/"predictions.csv").open("w",newline="",encoding="utf-8") as h:
        writer=csv.DictWriter(h,fieldnames=list(predictions[0]),lineterminator="\n"); writer.writeheader(); writer.writerows(predictions)
    for name,value in payloads.items(): write_json(output/name,value)
    core={name:sha256_file(output/name) for name in OUTPUT_FILES}
    state={"branch":subprocess.run(["git","branch","--show-current"],cwd=repo,text=True,capture_output=True,check=True).stdout.strip(),
           "head":subprocess.run(["git","rev-parse","HEAD"],cwd=repo,text=True,capture_output=True,check=True).stdout.strip(),
           "remote":subprocess.run(["git","remote","get-url","origin"],cwd=repo,text=True,capture_output=True,check=True).stdout.strip(),
           "git_status_before_execution":"clean","conda_environment":os.environ.get("CONDA_DEFAULT_ENV",""),"python":platform.python_version(),"interpreter":sys.executable}
    manifest={"version":"C3_T3B_LOCKED_2025_V1","repository_environment":state,"verified_freeze_hashes":frozen["verified"],"core_hashes":core,
              "bootstrap":{"seed":SEED,"replications":BOOTSTRAP_REPLICATIONS,"block":"UTC calendar month; all symbols/events together","quantile_method":"linear type-7"},
              "seals":{"no_refitting":True,"no_model_selection":True,"no_threshold_optimization":True,"2026_paths_enumerated":False,"2026_data_accessed":False},
              "economic_analysis_run":False,"selection_summary":selections}
    write_json(output/"reproducibility_manifest.json",manifest)
    return manifest


def verify_rebuild(repo: Path, output: Path) -> dict:
    published=json.loads((output/"reproducibility_manifest.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="c3_t3b_rebuild_") as d:
        rebuilt=run_t3b(repo,Path(d))
    same=rebuilt["core_hashes"]==published["core_hashes"]
    result={"version":"C3_T3B_INDEPENDENT_REBUILD_V1","published_core_hashes":published["core_hashes"],"rebuilt_core_hashes":rebuilt["core_hashes"],"identical":same}
    result["evidence_sha256"]=canonical_hash(result); write_json(output/"independent_rebuild.json",result)
    if not same: raise AssertionError("independent T3-B rebuild differs")
    return result
