from __future__ import annotations

import argparse
import json
from pathlib import Path

from .c3_milestone import verify_rebuild, write_checkpoint


def main() -> None:
    parser = argparse.ArgumentParser(prog="binance-c3-milestones")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--artifact-dir", default="artifacts/c3_milestone_state_continuation")
    parser.add_argument("--verify-rebuild", action="store_true")
    args = parser.parse_args()
    repo, artifact = Path(args.repo).resolve(), Path(args.artifact_dir)
    if not artifact.is_absolute():
        artifact = repo / artifact
    result = verify_rebuild(repo, artifact) if args.verify_rebuild else write_checkpoint(repo, artifact)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
