from __future__ import annotations
import argparse,json
from pathlib import Path
from .c2_candidate_run import _write_manifest, build_candidate_checkpoint
from .c2_common import write_json

def main()->None:
    p=argparse.ArgumentParser(prog="binance-c2-candidates")
    p.add_argument("--normalized-dir",default="data/normalized/c2_history")
    p.add_argument("--aggregate-dir",default="data/normalized/c2_frozen_inputs")
    p.add_argument("--artifact-dir",default="artifacts/c2_asymmetric_exit_experiment")
    p.add_argument("--verify-rebuild",action="store_true")
    a=p.parse_args(); normalized,aggregate,artifact=Path(a.normalized_dir),Path(a.aggregate_dir),Path(a.artifact_dir)
    result=build_candidate_checkpoint(normalized,aggregate,artifact)
    if a.verify_rebuild:
        second=build_candidate_checkpoint(normalized,aggregate,artifact)
        if result != second: raise RuntimeError("offline rebuild core hashes differ")
        import json as _json
        summary=_json.loads((artifact/"candidate_policy_summary.json").read_text(encoding="utf-8"))
        evidence={"mode":"--verify-rebuild","independent_rebuilds":2,"core_result_match":True,
                  "verified_core_hashes":second}
        write_json(artifact/"candidate_reproducibility.json",{
            "verification_mode":"--verify-rebuild","independent_offline_rebuilds":2,
            "frozen_entry_hash_unchanged":True,"common_horizon_hash_unchanged":True,
            "semantic_hashes_reproduced":True,"paired_trade_semantic_hash":second["paired_trade_semantic_hash"],
            "summary_hashes_reproduced":second["summary_hashes"],
            "manifest_byte_identity_expected":False,
            "manifest_note":"created_at_utc is regenerated; core trade-table and summary hashes must reproduce"})
        _write_manifest(artifact,second,summary,True,evidence,normalized,aggregate)
        result={**second,"deterministic_offline_rebuild_verified":True}
    print(json.dumps(result,indent=2,sort_keys=True))
if __name__=="__main__":main()
