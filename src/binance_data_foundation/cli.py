from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from .features import compute_features_csv
from .ingest import SampleSpec, ingest_sample, sha256_file

EXPECTED_NORMALIZED_SYMBOLS = frozenset(SampleSpec.fixed().symbols)


def main() -> None:
    parser = argparse.ArgumentParser(prog="binance-data-foundation")
    sub = parser.add_subparsers(dest="command", required=True)

    ingest = sub.add_parser("ingest")
    ingest.add_argument("--raw-dir", default="data/raw/binance_vision")
    ingest.add_argument("--normalized-dir", default="data/normalized/binance_vision")
    ingest.add_argument("--artifact-dir", default="artifacts/c1_binance_data_foundation")
    ingest.add_argument("--offline", action="store_true")

    features = sub.add_parser("features")
    features.add_argument("--normalized-dir", default="data/normalized/binance_vision")
    features.add_argument("--output", default="artifacts/c1_binance_data_foundation/features.csv")
    features.add_argument("--artifact-dir", default="artifacts/c1_binance_data_foundation")

    args = parser.parse_args()
    if args.command == "ingest":
        report = ingest_sample(
            SampleSpec.fixed(),
            Path(args.raw_dir),
            Path(args.normalized_dir),
            Path(args.artifact_dir),
            offline=args.offline,
        )
        print(json.dumps(report, indent=2, sort_keys=True))
        if not report["success"]:
            sys.exit(1)
    elif args.command == "features":
        input_paths = _verify_validated_inputs(Path(args.normalized_dir), Path(args.artifact_dir))
        out = compute_features_csv(Path(args.normalized_dir), Path(args.output), input_paths=input_paths)
        print(json.dumps({"output": str(out)}, indent=2, sort_keys=True))


def _verify_validated_inputs(normalized_dir: Path, artifact_dir: Path) -> list[Path]:
    normalized_dir = normalized_dir.resolve()
    quality_path = artifact_dir / "data_quality.json"
    hashes_path = artifact_dir / "normalized_hashes.json"
    if not quality_path.exists() or not hashes_path.exists():
        raise SystemExit("missing validation manifest; run successful ingest first")
    quality = json.loads(quality_path.read_text(encoding="utf-8"))
    failures = [q for q in quality if q.get("status") != "pass"]
    if failures:
        raise SystemExit(f"validation manifest contains failures: {failures[:3]}")
    expected = json.loads(hashes_path.read_text(encoding="utf-8"))
    if not expected:
        raise SystemExit("empty normalized hash manifest")
    manifest_paths = {Path(path_text).resolve() for path_text in expected}
    requested_paths = set(normalized_dir.glob("*_1m_normalized.csv"))
    requested_paths = {path.resolve() for path in requested_paths}
    expected_paths = {
        normalized_dir / f"{symbol}_1m_normalized.csv"
        for symbol in EXPECTED_NORMALIZED_SYMBOLS
    }
    expected_paths = {path.resolve() for path in expected_paths}
    missing = sorted(path.name for path in expected_paths - requested_paths)
    unexpected = sorted(path.name for path in requested_paths - expected_paths)
    if missing:
        raise SystemExit(f"missing expected normalized inputs: {missing}")
    if unexpected:
        raise SystemExit(f"unexpected normalized inputs: {unexpected}")
    if manifest_paths != expected_paths:
        raise SystemExit("validation manifest does not match requested normalized directory")
    for path_text, expected_hash in expected.items():
        path = Path(path_text).resolve()
        if not path.exists():
            raise SystemExit(f"missing normalized input: {path_text}")
        actual = sha256_file(path)
        if actual != expected_hash:
            raise SystemExit(f"stale or mutated normalized input: {path}")
        with path.open(newline="") as f:
            row_count = sum(1 for _ in csv.DictReader(f))
        if row_count != 5760:
            raise SystemExit(f"incomplete normalized input: {path} rows={row_count}")
    return sorted(expected_paths)


if __name__ == "__main__":
    main()
