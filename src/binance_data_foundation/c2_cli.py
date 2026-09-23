from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from .c2_inputs import build_frozen_inputs, ingest_history


def main() -> None:
    parser = argparse.ArgumentParser(prog="binance-c2-inputs")
    sub = parser.add_subparsers(dest="command", required=True)
    acquire = sub.add_parser("acquire")
    acquire.add_argument("--raw-dir", default="data/raw/c2_binance_vision_monthly")
    acquire.add_argument("--normalized-dir", default="data/normalized/c2_history")
    acquire.add_argument("--artifact-dir", default="artifacts/c2_asymmetric_exit_experiment")
    acquire.add_argument("--offline", action="store_true")
    build = sub.add_parser("build")
    build.add_argument("--normalized-dir", default="data/normalized/c2_history")
    build.add_argument("--output-dir", default="data/normalized/c2_frozen_inputs")
    build.add_argument("--artifact-dir", default="artifacts/c2_asymmetric_exit_experiment")
    args = parser.parse_args()
    if args.command == "acquire":
        result = ingest_history(Path(args.raw_dir), Path(args.normalized_dir), Path(args.artifact_dir), offline=args.offline)
    else:
        result = build_frozen_inputs(Path(args.normalized_dir), Path(args.output_dir), Path(args.artifact_dir))
        _write_run_manifest(Path(args.artifact_dir), result)
    print(json.dumps(result, indent=2, sort_keys=True))
    if not result.get("success", True):
        raise SystemExit(1)


def _write_run_manifest(artifact_dir: Path, build_summary: dict) -> None:
    contract = Path("contracts/C2_asymmetric_exit_experiment_CONTRACT.md")
    history = json.loads((artifact_dir / "history_summary.json").read_text(encoding="utf-8"))
    revision = subprocess.run(["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
    manifest = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "code_revision": revision,
        "implementation_hashes": {
            str(path): _hash(path) for path in sorted([
                Path("src/binance_data_foundation/c2_acquisition.py"),
                Path("src/binance_data_foundation/c2_aggregation.py"),
                Path("src/binance_data_foundation/c2_common.py"),
                Path("src/binance_data_foundation/c2_entries.py"),
                Path("src/binance_data_foundation/c2_inputs.py"),
                Path("src/binance_data_foundation/c2_cli.py"),
                Path("tests/test_c2_inputs.py"),
                Path("pyproject.toml"),
                Path("environment.yml"),
            ])
        },
        "contract_sha256": _hash(contract),
        "environment": {
            "name": "binance-v2-research", "python": platform.python_version(),
            "interpreter": {"implementation": sys.implementation.name, "executable_name": Path(sys.executable).name},
            "dependency_lock": "environment.yml",
        },
        "source_hashes": {row["zip_path"]: row["sha256"] for row in json.loads((artifact_dir / "source_manifest.json").read_text()) if row["status"] == "verified"},
        "normalized_data_hashes": history["normalized_hashes"],
        "aggregation_version": build_summary["aggregation_version"],
        "aggregate_hashes": build_summary["aggregate_hashes"],
        "entry_fixture_id": build_summary["entry_fixture_id"],
        "symbols": history["symbols"],
        "source_start_utc": history["source_start_utc"],
        "study_start_utc": history["study_start_utc"],
        "study_end_exclusive_utc": history["study_end_exclusive_utc"],
        "research_partitions": history["research_partitions"],
        "gap_rules": "no imputation; invalid/missing minute invalidates aggregate; gap breaks SMA24",
        "frozen_entry_hash": build_summary["frozen_entry_hash"],
        "row_counts": {"normalized": history["row_counts"], "aggregates": build_summary["aggregate_rows"]},
        "exclusion_counts": {"aggregates": build_summary["aggregate_exclusions"], "refractory": build_summary["suppressed_refractory_signals"], "unexecutable": build_summary["unexecutable_signals"]},
    }
    (artifact_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    main()
