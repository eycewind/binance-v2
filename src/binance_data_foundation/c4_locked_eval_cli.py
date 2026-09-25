from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from .c4_locked_eval import load_locked_checkpoint, predict_feature_rows


def main():
    parser=argparse.ArgumentParser(description="C4 locked prediction-only evaluator; never fits or selects")
    parser.add_argument("--repo",default=".")
    parser.add_argument("--artifact-dir",default="artifacts/c4_sequential_exit_state")
    parser.add_argument("--features-json",required=True,help="authorized 2025 causal feature rows")
    parser.add_argument("--target",required=True,choices=("T1","T2"))
    parser.add_argument("--model",required=True,choices=("B0","G0","G1","P1"))
    args=parser.parse_args(); repo=Path(args.repo).resolve(); artifact=Path(args.artifact_dir)
    if not artifact.is_absolute(): artifact=repo/artifact
    checkpoint=load_locked_checkpoint(repo,artifact)
    rows=json.loads(Path(args.features_json).read_text(encoding="utf-8"))
    print(json.dumps(predict_feature_rows(checkpoint,args.target,args.model,rows),indent=2,sort_keys=True))


if __name__=="__main__": main()
