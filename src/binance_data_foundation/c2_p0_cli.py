from __future__ import annotations

import argparse
import json
from pathlib import Path

from .c2_p0 import build_p0_checkpoint


def main() -> None:
    parser = argparse.ArgumentParser(prog="binance-c2-p0")
    parser.add_argument("--normalized-dir", default="data/normalized/c2_history")
    parser.add_argument("--aggregate-dir", default="data/normalized/c2_frozen_inputs")
    parser.add_argument("--artifact-dir", default="artifacts/c2_asymmetric_exit_experiment")
    args = parser.parse_args()
    result = build_p0_checkpoint(Path(args.normalized_dir), Path(args.aggregate_dir), Path(args.artifact_dir))
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
