from __future__ import annotations
import argparse,json
from pathlib import Path
from .c2_candidate_run import build_candidate_checkpoint

def main()->None:
    p=argparse.ArgumentParser(prog="binance-c2-candidates")
    p.add_argument("--normalized-dir",default="data/normalized/c2_history")
    p.add_argument("--aggregate-dir",default="data/normalized/c2_frozen_inputs")
    p.add_argument("--artifact-dir",default="artifacts/c2_asymmetric_exit_experiment")
    a=p.parse_args(); result=build_candidate_checkpoint(Path(a.normalized_dir),Path(a.aggregate_dir),Path(a.artifact_dir))
    print(json.dumps(result,indent=2,sort_keys=True))
if __name__=="__main__":main()
