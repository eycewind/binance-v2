from __future__ import annotations
import argparse, json
from pathlib import Path
from .c4_modeling import portable_rebuild, run, verify_two_rebuilds

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--repo',default='.')
    parser.add_argument('--artifact-dir',default='artifacts/c4_sequential_exit_state')
    parser.add_argument('--verify-rebuild',action='store_true')
    parser.add_argument('--portable-rebuild',action='store_true',help='regenerate and hash-verify ignored modeling inputs before rebuilding')
    args=parser.parse_args(); repo=Path(args.repo).resolve(); out=Path(args.artifact_dir)
    if not out.is_absolute(): out=repo/out
    if args.verify_rebuild and args.portable_rebuild: parser.error('choose only one rebuild mode')
    result=verify_two_rebuilds(repo,out) if args.verify_rebuild else portable_rebuild(repo,out) if args.portable_rebuild else run(repo,out)
    print(json.dumps(result,indent=2,sort_keys=True))
if __name__=='__main__': main()
