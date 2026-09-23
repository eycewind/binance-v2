from argparse import ArgumentParser
from pathlib import Path

from .c2_temporal import _manifest, build_temporal_analysis


def main() -> None:
    parser=ArgumentParser(description="Build descriptive C2-A temporal path-kinetics artifacts")
    parser.add_argument("--normalized-dir",default="data/normalized/c2_history")
    parser.add_argument("--artifact-dir",default="artifacts/c2_asymmetric_exit_experiment")
    parser.add_argument("--verify-rebuild", action="store_true",
                        help="independently rebuild twice and record verification only if core hashes match")
    args=parser.parse_args()
    normalized_dir, artifact_dir = Path(args.normalized_dir), Path(args.artifact_dir)
    first = build_temporal_analysis(normalized_dir, artifact_dir)
    if not args.verify_rebuild:
        print(first)
        return
    second = build_temporal_analysis(normalized_dir, artifact_dir)
    if first != second:
        raise RuntimeError("deterministic offline rebuild verification failed: core outputs or hashes differ")
    evidence = {"mode":"--verify-rebuild", "independent_rebuilds":2,
                "core_result_match":True, "verified_hashes":second}
    _manifest(artifact_dir, second, True, evidence)
    print({**second, "deterministic_offline_rebuild_verified": True})


if __name__ == "__main__": main()
