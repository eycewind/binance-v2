from __future__ import annotations
import argparse, json
from pathlib import Path
from .c3_t3b import run_t3b, verify_rebuild

def main():
    p=argparse.ArgumentParser(prog="binance-c3-t3b"); p.add_argument("--repo",default="."); p.add_argument("--output",default="artifacts/c3_milestone_state_continuation/t3b_2025"); p.add_argument("--verify-rebuild",action="store_true")
    a=p.parse_args(); repo=Path(a.repo).resolve(); out=Path(a.output); out=out if out.is_absolute() else repo/out
    print(json.dumps(verify_rebuild(repo,out) if a.verify_rebuild else run_t3b(repo,out),indent=2,sort_keys=True))
if __name__=="__main__": main()
