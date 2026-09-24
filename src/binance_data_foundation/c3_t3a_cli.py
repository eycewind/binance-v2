from __future__ import annotations

import argparse
import json
from pathlib import Path

from .c3_t3a import run_t3a, verify_rebuild


def main() -> None:
    parser = argparse.ArgumentParser(prog="binance-c3-t3a")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--output", default="artifacts/c3_milestone_state_continuation/t3a_2024")
    parser.add_argument("--verify-rebuild", action="store_true")
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    output = Path(args.output)
    if not output.is_absolute(): output = repo / output
    result = verify_rebuild(repo, output) if args.verify_rebuild else run_t3a(repo, output)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__": main()
