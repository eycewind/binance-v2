from __future__ import annotations

import argparse
import json
from pathlib import Path

from .c4_locked_input import prepare_locked_2025_input


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare the all-target C4 locked 2025 input; never scores")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--artifact-dir", default="artifacts/c4_sequential_exit_state")
    parser.add_argument("--prepare-locked-2025-input", action="store_true", required=True)
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    artifact = Path(args.artifact_dir)
    if not artifact.is_absolute():
        artifact = repo / artifact
    result = prepare_locked_2025_input(repo, artifact)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
