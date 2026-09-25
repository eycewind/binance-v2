from __future__ import annotations

import hashlib
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

BOUNDARY_2025_MS = 1735689600000
BOUNDARY_2026_MS = 1767225600000


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class LockedCheckpoint:
    freeze_hash: str
    freeze: dict
    schema: dict
    preprocessing: dict
    models: dict


def load_locked_checkpoint(repo: Path, artifact: Path, lock_path: Path | None = None) -> LockedCheckpoint:
    """Validate the complete 2024 seal before any predictive row may be consumed."""
    freeze_path=artifact/"c4_2024_freeze.json"
    lock_path=lock_path or artifact/"c4_2024_freeze.sha256"
    if not freeze_path.is_file() or not lock_path.is_file():
        raise RuntimeError("missing frozen checkpoint or external freeze lock")
    expected=lock_path.read_text(encoding="utf-8").strip().split()[0]
    actual=_sha256(freeze_path)
    if actual != expected: raise RuntimeError("freeze hash mismatch")
    freeze=json.loads(freeze_path.read_text(encoding="utf-8"))
    if freeze.get("version") != "C4_2024_FREEZE_V2": raise RuntimeError("unsupported freeze version")
    if freeze.get("seals") != {"2025_predictive_scoring":"NOT PERFORMED","2026_access":False,"economic_or_stage_B_analysis":False}:
        raise RuntimeError("invalid checkpoint seals")
    for name,digest in freeze["material_artifact_hashes"].items():
        path=artifact/name
        if not path.is_file() or _sha256(path)!=digest: raise RuntimeError(f"material artifact mismatch: {name}")
    for name,digest in freeze["source_test_hashes"].items():
        path=repo/name
        if not path.is_file() or _sha256(path)!=digest: raise RuntimeError(f"source provenance mismatch: {name}")
    env=freeze["environment"]
    if os.environ.get("PYTHONPATH") is not None or os.environ.get("CONDA_DEFAULT_ENV")!=env["conda_env"]:
        raise RuntimeError("environment provenance mismatch")
    if sys.version.split()[0]!=env["python_version"] or np.__version__!=env["numpy_version"]:
        raise RuntimeError("runtime version mismatch")
    schema=json.loads((artifact/"feature_schema.json").read_text())
    preprocessing=json.loads((artifact/"final_preprocessing_2024.json").read_text())
    models=json.loads((artifact/"final_models_2024.json").read_text())
    snapshot_schema=json.loads((artifact/"snapshot_schema.json").read_text())
    if snapshot_schema["target_definition_versions"] != freeze["target_definitions"]:
        raise RuntimeError("target schema mismatch")
    for target in ("T1","T2"):
        for model in ("G0","G1","P1"):
            key=f"{target}_{model}"
            if preprocessing[key]["columns"] != models[target]["models"][model]["columns"]:
                raise RuntimeError(f"frozen column mismatch: {key}")
            expected=[c for c in schema["targets"][target][model] if c.startswith("symbol_") or not preprocessing[key]["parameters"][c]["excluded_zero_iqr"]]
            if expected != preprocessing[key]["columns"]:
                raise RuntimeError(f"feature schema order mismatch: {key}")
    return LockedCheckpoint(actual,freeze,schema,preprocessing,models)


def _validate_2025_metadata(row: dict) -> None:
    # This function is called before accessing row["features"].
    entry=int(row["entry_execution_ms"]); snapshot=int(row["snapshot_ms"])
    if not (BOUNDARY_2025_MS <= entry < BOUNDARY_2026_MS): raise ValueError("locked evaluator accepts 2025 entries only")
    if not (BOUNDARY_2025_MS <= snapshot < BOUNDARY_2026_MS): raise ValueError("locked evaluator rejects snapshot outside 2025")


def predict_feature_rows(checkpoint: LockedCheckpoint, target: str, model: str, rows: list[dict]) -> list[dict]:
    """Apply frozen preprocessing/parameters only; contains no fitting or selection path."""
    if target not in ("T1","T2") or model not in ("B0","G0","G1","P1"): raise ValueError("unknown frozen target/model")
    for row in rows: _validate_2025_metadata(row)
    classes=checkpoint.freeze["class_order"][target]
    frozen=checkpoint.models[target]["models"][model]
    if model=="B0": probs=np.tile(np.asarray(frozen["probabilities"],float),(len(rows),1))
    else:
        prep=checkpoint.preprocessing[f"{target}_{model}"]; columns=prep["columns"]
        if columns != frozen["columns"]: raise RuntimeError("column order changed after checkpoint load")
        x=np.empty((len(rows),len(columns)),float)
        for j,col in enumerate(columns):
            if col.startswith("symbol_"): x[:,j]=[r["symbol"]==col[7:] for r in rows]
            else:
                parameter=prep["parameters"][col]
                x[:,j]=[(r["features"][col]-parameter["median"])/parameter["iqr"] for r in rows]
        design=np.column_stack((np.ones(len(rows)),x)); coef=np.asarray(frozen["coefficients"],float)
        eta=np.column_stack((design@coef,np.zeros(len(rows)))); eta-=eta.max(axis=1,keepdims=True)
        exp=np.exp(eta); probs=exp/exp.sum(axis=1,keepdims=True)
    return [{"row_id":row["row_id"],"target":target,"model":model,**{f"p_{c}":float(v) for c,v in zip(classes,p)}} for row,p in zip(rows,probs)]
