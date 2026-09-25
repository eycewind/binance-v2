from __future__ import annotations

import hashlib
import json
import math
import os
import sys
import tempfile
from collections import Counter
from contextlib import contextmanager
from pathlib import Path

import numpy as np

from . import c4_modeling
from .c4_adequacy import build_tables, load_inputs
from .c4_locked_eval import CLASS_ORDER, load_locked_checkpoint
from .ingest import sha256_file


EXPECTED_FREEZE_SHA256 = "011c35e91297468e2015442ec2c95079cfdb8cf28bf11a113e2ad6e1ee093fb2"
EXPECTED_CONFIG_SHA256 = "750ecd9b3c02b401dd1298e29d39174bf38a26f6f0ac3950b7180a3f261a2064"
START_2025_MS = 1735689600000
END_2025_MS = 1767225600000
INPUT_NAME = "locked_2025_input.json"
MANIFEST_NAME = "locked_2025_input_manifest.json"
SUPERSEDED_INPUT_SHA256 = "230106486e24624da73dc60fb2346973f0bbf9039be428d0960e50999b631757"
TARGETS = ("T1", "T2")


def _sha256(path: Path) -> str:
    return sha256_file(path)


def _validate_2025_metadata(row: dict) -> None:
    """Validate timestamps before any predictive value is requested."""
    entry = int(row["entry_execution_ms"])
    snapshot = int(row["snapshot_ms"])
    if not START_2025_MS <= entry < END_2025_MS:
        raise ValueError("locked input preparation accepts 2025 entries only")
    if not START_2025_MS <= snapshot < END_2025_MS:
        raise ValueError("locked input preparation accepts 2025 snapshots only")


@contextmanager
def _accepted_feature_builder_for_2025():
    """Run the hash-locked feature builder with only its year gate adapted."""
    original = c4_modeling._pre_value_2024
    c4_modeling._pre_value_2024 = _validate_2025_metadata
    try:
        yield c4_modeling.build_feature_table
    finally:
        c4_modeling._pre_value_2024 = original


def _checkpoint(repo: Path, artifact: Path):
    checkpoint = load_locked_checkpoint(repo, artifact)
    if checkpoint.freeze_hash != EXPECTED_FREEZE_SHA256:
        raise RuntimeError("unexpected external C4 freeze hash")
    if checkpoint.freeze.get("locked_2025_evaluation_sha256") != EXPECTED_CONFIG_SHA256:
        raise RuntimeError("unexpected locked evaluation configuration hash")
    return checkpoint


def _source_provenance(repo: Path, artifact: Path) -> list[dict]:
    accepted = json.loads((artifact / "input_manifest.json").read_text())
    records = []
    for item in accepted["explicit_allowlist"]:
        path = repo / item["path"]
        actual = _sha256(path)
        if actual != item["sha256"]:
            raise RuntimeError(f"2025 source provenance mismatch: {item['path']}")
        records.append({"path": item["path"], "role": item["role"], "sha256": actual})
    for relative, role in (
        ("src/binance_data_foundation/c4_locked_input.py", "locked_input_preparation"),
        ("src/binance_data_foundation/c4_locked_input_cli.py", "locked_input_cli"),
    ):
        records.append({"path": relative, "role": role, "sha256": _sha256(repo / relative)})
    return records


def _exclusion_counts(rows: list[dict]) -> dict[str, int]:
    counts = Counter()
    for row in rows:
        if not row["target_eligible"]:
            counts["target_ineligible"] += 1
        elif row["ambiguous"]:
            counts["ambiguous"] += 1
        elif row["censored"]:
            counts["censored"] += 1
        elif not row["resolved"]:
            counts["unresolved_other"] += 1
    return dict(sorted(counts.items()))


def _has_complete_raw_feature_inputs(row: dict) -> bool:
    names = ("entry_price", "elapsed_minutes", "current_return", "drawdown_from_running_peak",
             "peak_gain_retained_fraction", "upper_barrier", "lower_barrier", "snapshot_close")
    return all(row.get(name) is not None and math.isfinite(float(row[name])) for name in names)


def _input_row(row: dict, target: str, features: dict, feature_columns: list[str]) -> dict:
    _validate_2025_metadata(row)
    if row["event_class"] not in CLASS_ORDER[target]:
        raise ValueError(f"class order/outcome mismatch for {target}")
    continuous = [name for name in feature_columns if not name.startswith("symbol_")]
    if any(name not in features for name in continuous):
        raise RuntimeError(f"feature column mismatch for {target}")
    if not all(math.isfinite(float(features[name])) for name in continuous):
        raise RuntimeError(f"non-finite complete-case feature for {target}")
    return {
        "row_id": row["row_id"],
        "trade_id": row["trade_id"],
        "target": target,
        "entry_execution_ms": row["entry_execution_ms"],
        "snapshot_ms": row["snapshot_ms"],
        "symbol": row["symbol"],
        "trade_entry_week": row["trade_entry_week"],
        "snapshot_month": row["snapshot_month"],
        "snapshot_quarter": row["snapshot_quarter"],
        "target_eligible": True,
        "resolved": True,
        "censored": False,
        "ambiguous": False,
        "event_class": row["event_class"],
        "features": {name: float(features[name]) for name in continuous},
    }


def validate_prepared_row_schema(checkpoint, row: dict) -> None:
    """Apply the locked evaluator's pre-scoring completeness/schema contract."""
    target = row["target"]
    if target not in TARGETS:
        raise ValueError("unknown locked target")
    _validate_2025_metadata(row)
    if row["event_class"] not in CLASS_ORDER[target]:
        raise ValueError(f"class order/outcome mismatch for {target}")
    required = checkpoint.schema["targets"][target]["P1"]
    numeric = [name for name in required if not name.startswith("symbol_")]
    features = row["features"]
    if list(features) != numeric:
        raise RuntimeError(f"incomplete frozen P1 feature schema for {target}")
    if not all(math.isfinite(float(features[name])) for name in numeric):
        raise RuntimeError(f"non-finite frozen P1 feature for {target}")


def _atomic_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=False, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.rename(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def prepare_locked_2025_input(repo: Path, artifact: Path | None = None) -> dict:
    repo = Path(repo).resolve()
    artifact = Path(artifact) if artifact is not None else repo / "artifacts/c4_sequential_exit_state"
    if not artifact.is_absolute():
        artifact = repo / artifact
    input_path = artifact / INPUT_NAME
    manifest_path = artifact / MANIFEST_NAME
    if input_path.exists() or manifest_path.exists():
        raise FileExistsError("locked 2025 input or manifest already exists; overwrite is prohibited")

    # This must remain the first operation capable of opening any predictive source.
    checkpoint = _checkpoint(repo, artifact)
    provenance = _source_provenance(repo, artifact)

    entries, horizons, minutes, _ = load_inputs(repo)
    tables = build_tables(entries, horizons, minutes)
    output_rows = []
    summaries = {}
    for target in TARGETS:
        partition = [row for row in tables[target] if row["temporal_partition"] == "2025_locked"]
        for row in partition:
            _validate_2025_metadata(row)
        candidates = [row for row in partition if row["target_eligible"] and row["resolved"]
                      and not row["censored"] and not row["ambiguous"]]
        exclusions = _exclusion_counts(partition)
        feature_candidates = [row for row in candidates if _has_complete_raw_feature_inputs(row)]
        with _accepted_feature_builder_for_2025() as feature_builder:
            retained, feature_values = feature_builder(repo, feature_candidates)
        retained.sort(key=lambda row: (row["snapshot_ms"], row["symbol"], row["trade_id"], row["row_id"]))
        schema_columns = checkpoint.schema["targets"][target]["P1"]
        model_columns = checkpoint.models[target]["models"]["P1"]["columns"]
        if model_columns != checkpoint.preprocessing[f"{target}_P1"]["columns"]:
            raise RuntimeError(f"frozen P1 schema mismatch for {target}")
        expected = [name for name in checkpoint.schema["targets"][target]["P1"]
                    if name.startswith("symbol_") or not checkpoint.preprocessing[f"{target}_P1"]["parameters"][name]["excluded_zero_iqr"]]
        if model_columns != expected:
            raise RuntimeError(f"frozen feature schema/order mismatch for {target}")
        rows = [_input_row(row, target, feature_values[row["row_id"]], schema_columns) for row in retained]
        for row in rows:
            validate_prepared_row_schema(checkpoint, row)
        output_rows.extend(rows)
        exclusions["feature_incomplete"] = len(candidates) - len(retained)
        summaries[target] = {
            "resolved_candidate_rows": len(candidates),
            "complete_case_rows": len(rows),
            "excluded_rows_by_reason": dict(sorted(exclusions.items())),
            "unique_trades": len({row["trade_id"] for row in rows}),
            "class_counts": dict(sorted(Counter(row["event_class"] for row in rows).items())),
            "feature_columns": schema_columns,
            "input_feature_columns": [name for name in schema_columns if not name.startswith("symbol_")],
            "frozen_model_columns": model_columns,
            "class_order": CLASS_ORDER[target],
        }
    output_rows.sort(key=lambda row: (row["snapshot_ms"], row["symbol"], row["trade_id"], row["target"], row["row_id"]))
    if {row["target"] for row in output_rows} != set(TARGETS):
        raise RuntimeError("locked input must contain both T1 and T2")

    _atomic_json(input_path, output_rows)
    input_sha256 = _sha256(input_path)
    manifest = {
        "version": "C4_LOCKED_2025_INPUT_MANIFEST_V1",
        "freeze_sha256": checkpoint.freeze_hash,
        "locked_evaluation_config_sha256": checkpoint.freeze["locked_2025_evaluation_sha256"],
        "input_path": str(input_path.relative_to(repo)),
        "input_sha256": input_sha256,
        "superseded_invalid_input": {
            "sha256": SUPERSEDED_INPUT_SHA256,
            "reason": "INVALIDATED_BY_SCHEMA_OMISSION: missing zero_5m_count_6",
            "authorized_for_scoring": False,
        },
        "row_count": len(output_rows),
        "trade_count": len({row["trade_id"] for row in output_rows}),
        "targets": summaries,
        "feature_schema_sha256": checkpoint.freeze["feature_schema_sha256"],
        "source_input_provenance": provenance,
        "environment_provenance": {
            "conda_env": os.environ.get("CONDA_DEFAULT_ENV"),
            "python_version": sys.version.split()[0],
            "numpy_version": np.__version__,
            "environment_yml_sha256": _sha256(repo / "environment.yml"),
            "requirements_dev_sha256": _sha256(repo / "requirements-dev.txt"),
        },
        "authorized_period": {
            "start_inclusive_utc": "2025-01-01T00:00:00Z",
            "end_exclusive_utc": "2026-01-01T00:00:00Z",
        },
        "2026_access": False,
        "predictive_scoring_performed": False,
        "predictive_rows_scored": 0,
        "model_fit_performed": False,
        "preprocessing_fit_performed": False,
        "stage_B_or_economic_analysis": False,
    }
    try:
        _atomic_json(manifest_path, manifest)
    except BaseException:
        input_path.unlink(missing_ok=True)
        raise
    return {"input_path": str(input_path), "manifest_path": str(manifest_path),
            "input_sha256": input_sha256, "manifest_sha256": _sha256(manifest_path),
            "row_count": len(output_rows), "trade_count": manifest["trade_count"],
            "targets": summaries, "freeze_sha256": checkpoint.freeze_hash,
            "config_sha256": checkpoint.freeze["locked_2025_evaluation_sha256"]}
