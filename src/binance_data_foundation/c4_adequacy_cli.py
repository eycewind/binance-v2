from __future__ import annotations
import argparse, json
from pathlib import Path
from .c4_adequacy import run, verify_rebuild

def main():
    p=argparse.ArgumentParser(); p.add_argument('--repo',default='.'); p.add_argument('--artifact-dir',default='artifacts/c4_sequential_exit_state'); p.add_argument('--verify-rebuild',action='store_true'); a=p.parse_args()
    repo=Path(a.repo).resolve(); artifact=Path(a.artifact_dir); artifact=artifact if artifact.is_absolute() else repo/artifact
    print(json.dumps(verify_rebuild(repo,artifact) if a.verify_rebuild else run(repo,artifact),indent=2,sort_keys=True))
if __name__=='__main__': main()
