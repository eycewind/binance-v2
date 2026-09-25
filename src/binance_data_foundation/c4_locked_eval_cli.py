from __future__ import annotations
import argparse, json
from pathlib import Path
from .c4_locked_eval import evaluate_locked_2025, validate_readiness

def main():
    p=argparse.ArgumentParser(description="C4 all-or-nothing locked 2025 evaluator; never fits or selects")
    p.add_argument("--repo",default="."); p.add_argument("--artifact-dir",default="artifacts/c4_sequential_exit_state")
    mode=p.add_mutually_exclusive_group(required=True); mode.add_argument("--readiness",action="store_true"); mode.add_argument("--evaluate-locked-2025",action="store_true")
    p.add_argument("--input",help="authorized input; default ARTIFACT/locked_2025_input.json"); p.add_argument("--output-dir",help="default ARTIFACT/locked_2025")
    a=p.parse_args(); repo=Path(a.repo).resolve(); artifact=Path(a.artifact_dir)
    if not artifact.is_absolute():artifact=repo/artifact
    if a.readiness:
        if a.input or a.output_dir:p.error("readiness accepts no predictive input or output")
        result=validate_readiness(repo,artifact)
    else:
        result=evaluate_locked_2025(repo,artifact,Path(a.input) if a.input else artifact/"locked_2025_input.json",Path(a.output_dir) if a.output_dir else artifact/"locked_2025")
    print(json.dumps(result,indent=2,sort_keys=True))
if __name__=="__main__":main()
