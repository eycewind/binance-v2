"""One-shot frozen-science C13 execution after the C7-seed coupling repair."""
from __future__ import annotations

import hashlib, json, os, platform, shutil, sys, tempfile, uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from . import c10_post_t2 as c10
from . import c12_post_t2_warning as c12
from . import c13_warning_economics as c13

AUTHORIZATION="AUTHORIZE_C13F_ONE_SHOT"
OUTPUT_REL="artifacts/c13f_frozen_science_implementation_repair"
CONTRACT_REL="contracts/C13F_frozen_science_implementation_repair_CONTRACT.md"
C13_READY_REL="artifacts/c13_post_t2_warning_economics/readiness_freeze.json"
C13_LEDGER_REL="artifacts/c13_post_t2_warning_economics/attempt_ledger.jsonl"
C13R_LEDGER_REL="artifacts/c13r_c13_infrastructure_recovery/attempt_ledger.jsonl"
C13_ATTEMPT="C13-bbfde36f-2da4-4d32-8dd5-0467a2482f6b"
C13R_ATTEMPT="C13R-d637b1d1-0092-40db-9cf8-3dab5257511a"
OLD_CODE_SHA256="aa97453dddbad5ed3f7246a3dabf0f9e4a72de4cd94f9fef2b9dd43910d8558e"
DOCUMENTS=("run_manifest","provenance","source_population_reconciliation","prediction_availability","policy_registry","execution_rules","cost_config","bootstrap_config","canonical_paired_trade_table","pooled_report","t2_non_t2_decomposition","prediction_availability_decomposition","w1_trigger_diagnostics","d2_control_report","year_reports","symbol_reports","equal_weight_symbol_report","breadth_report","cost_sensitivities","safety_report","winner_truncation_report","holding_exposure_report","classification_predicates","final_classification","final_summary")

def sha(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1<<20),b""):h.update(block)
    return h.hexdigest()

def rows(path:Path)->list[dict]:
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()] if path.exists() else []

def append(path:Path,value:dict)->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("a") as f:f.write(json.dumps(value,sort_keys=True)+"\n")

def history(repo:Path)->dict:
    expected=((C13_LEDGER_REL,C13_ATTEMPT,["START","ECONOMIC_READ"]),(C13R_LEDGER_REL,C13R_ATTEMPT,["START","ECONOMIC_READ","FAIL"]))
    out={}
    for rel,attempt,events in expected:
        own=[x for x in rows(repo/rel) if x.get("attempt_id")==attempt]
        if [x.get("event") for x in own]!=events or "ECONOMIC_EMISSION" in events:raise RuntimeError(f"preserved {attempt} lifecycle mismatch")
        out[attempt]={"lifecycle":events,"economic_result_emitted":False,"ledger_sha256":sha(repo/rel)}
    if "frozen bootstrap seed/replicates required" not in rows(repo/C13R_LEDGER_REL)[-1].get("failure",""):raise RuntimeError("C13R failure identity mismatch")
    return out

def documents(ready:dict,attempt:str,result:dict,data:dict,population:list[dict])->dict:
    docs={
      "run_manifest":{"version":"C13F_RUN_V1","attempt_id":attempt,"status":"PASS","label":"C13F frozen-science execution of the C13 experiment after implementation repair.","one_shot":True,"c13_contract_sha256":ready["original_c13_contract_sha256"],"c13f_contract_sha256":ready["c13f_contract_sha256"]},
      "provenance":ready,"source_population_reconciliation":{"total":len(population),"by_year":dict(Counter(str(x["entry_year"]) for x in population)),"t2":len(data["trades"]),"no_t2":len(population)-len(data["trades"]),"outcomes":dict(Counter(x["terminal"] for x in data["trades"]))},
      "prediction_availability":c12.population(data["trades"],data["binary_rows"],data["scored_rows"]),
      "policy_registry":{"P0":"canonical unchanged","W1":{"threshold":"strictly <0.20","persistence":3},"D2_CONTROL":"frozen midpoint boundary"},
      "execution_rules":{"completed_information_only":True,"execution":"immediate next 1m open","P0_wins_ties":True,"gaps":"fail closed"},"cost_config":c13.COSTS,"bootstrap_config":{"method":"whole-trade four-entry-week moving blocks","seed":c13.SEED,"replicates":c13.REPLICATES,"block_weeks":4},
      "canonical_paired_trade_table":{"rows":result["table"]},"pooled_report":{"bootstrap":result["bootstrap"],"C_BASE":result["sensitivities"]["C_BASE"]},"t2_non_t2_decomposition":result["decomposition"],"prediction_availability_decomposition":result["availability"],"w1_trigger_diagnostics":{"rows":result["diagnostics"]},"d2_control_report":{"trigger_count":result["trigger_counts"]["D2_CONTROL"],"contrast":result["bootstrap"]["contrasts"]["D2_CONTROL-P0"]},"year_reports":result["years"],"symbol_reports":result["symbols"],"equal_weight_symbol_report":{"W1-P0":result["breadth"]["equal_weight_symbol"]},"breadth_report":result["breadth"],"cost_sensitivities":result["sensitivities"],"safety_report":result["safety"],"winner_truncation_report":result["winners"],"holding_exposure_report":result["exposure"],"classification_predicates":result["classification"]["predicates"],"final_classification":{"label":result["classification"]["label"]}}
    docs["final_summary"]={"label":docs["run_manifest"]["label"],"attempt_id":attempt,"status":"PASS","population":docs["source_population_reconciliation"],"availability":docs["prediction_availability"],"trigger_counts":result["trigger_counts"],"economics":docs["pooled_report"],"decomposition":result["decomposition"],"safety":result["safety"],"winners":result["winners"],"years":result["years"],"symbols":result["symbols"],"breadth":result["breadth"],"classification":result["classification"],"cost_sensitivities":result["sensitivities"],"confirmations":{"c13f_economic_attempts":1,"retry":False,"threshold_model_timeframe_policy_search":False,"c7_c12_scientific_modification":False,"accessed_2026":False,"c14_started":False}}
    return docs

def validate_documents(docs:dict)->None:
    missing=set(DOCUMENTS)-set(docs)
    if missing:raise ValueError("missing output documents: "+", ".join(sorted(missing)))
    if docs["bootstrap_config"]!={"method":"whole-trade four-entry-week moving blocks","seed":20261013,"replicates":2000,"block_weeks":4}:raise ValueError("C13 bootstrap schema/config mismatch")
    for name in ("W1-P0","D2_CONTROL-P0","W1-D2_CONTROL"):
        item=docs["pooled_report"]["bootstrap"]["contrasts"][name]
        if set(item)!={"point","ci95"} or len(item["ci95"])!=2:raise ValueError("bootstrap contrast schema mismatch")

def preflight(repo:Path)->dict:
    c13.reject_2026(repo)
    if os.environ.get("CONDA_DEFAULT_ENV")!="binance-v2-research":raise RuntimeError("conda environment must be binance-v2-research")
    hist=history(repo); frozen=json.loads((repo/C13_READY_REL).read_text())
    if frozen["code_sha256"]!=OLD_CODE_SHA256 or frozen["seed"]!=20261013 or frozen["replicates"]!=2000:raise RuntimeError("original C13 frozen identity mismatch")
    for rel,expected in frozen["source_hashes"].items():
        if rel=="src/binance_data_foundation/c13_warning_economics.py":continue
        if sha(repo/rel)!=expected:raise RuntimeError("original C13 source/input identity mismatch: "+rel)
    pop=json.loads((repo/"artifacts/c7_full_population_t2_exit_overlay/population_manifest.json").read_text())["rows"]; t2=sum(bool(x["overlay_strictly_before_p0"]) for x in pop)
    if (len(pop),t2,len(pop)-t2)!=(2199,845,1354):raise RuntimeError("population mismatch")
    evidence=repo/OUTPUT_REL/"test_evidence.json"; dry=repo/OUTPUT_REL/"synthetic_pipeline_validation.json"
    if not evidence.exists() or not dry.exists():raise RuntimeError("C13F test and dry-run evidence required")
    ev=json.loads(evidence.read_text()); dr=json.loads(dry.read_text())
    if ev.get("focused",{}).get("status")!="PASS" or ev.get("full_suite",{}).get("status")!="PASS" or dr.get("status")!="PASS":raise RuntimeError("C13F validation evidence is not PASS")
    code=sha(repo/"src/binance_data_foundation/c13_warning_economics.py")
    return {"status":"READY","history":hist,"original_c13_contract_sha256":frozen["contract_sha256"],"c13f_contract_sha256":sha(repo/CONTRACT_REL),"source_hashes":{k:v for k,v in frozen["source_hashes"].items() if k!="src/binance_data_foundation/c13_warning_economics.py"},"population_sha256":frozen["population_sha256"],"probability_provenance_sha256":frozen["probability_provenance_sha256"],"old_implementation_sha256":OLD_CODE_SHA256,"repaired_c13_code_sha256":code,"c13f_runner_sha256":sha(Path(__file__)),"configuration_sha256":c13.semantic_hash({"policies":c13.POLICIES,"costs":c13.COSTS,"seed":c13.SEED,"replicates":c13.REPLICATES}),"environment_sha256":c13.semantic_hash({"python":sys.version,"numpy":np.__version__,"platform":platform.platform(),"conda":"binance-v2-research"}),"output_schema_sha256":c13.semantic_hash(DOCUMENTS),"seed":20261013,"replicates":2000,"cost_configuration":c13.COSTS,"synthetic_validation_sha256":sha(dry),"test_evidence_sha256":sha(evidence),"economic_read":False,"no_2026":"VERIFIED"}

def run_once(repo:Path,authorization:str)->dict:
    if authorization!=AUTHORIZATION:raise PermissionError("explicit C13F authorization required")
    out=repo/OUTPUT_REL; ledger=out/"attempt_ledger.jsonl"
    if any(x.get("economic_read") for x in rows(ledger)):raise RuntimeError("C13F one-shot already consumed")
    ready=preflight(repo); c13.write_json(out/"readiness_freeze.json",ready); attempt=f"C13F-{uuid.uuid4()}"; now=lambda:datetime.now(timezone.utc).isoformat()
    append(ledger,{"attempt_id":attempt,"event":"START","timestamp":now(),"economic_read":False})
    try:
        append(ledger,{"attempt_id":attempt,"event":"ECONOMIC_READ","timestamp":now(),"economic_read":True})
        data=c12.generate_frozen_panel(repo)
        if c12.reproduce_c11(repo,data)["status"]!="PASS":raise RuntimeError("C11 reproduction failed")
        population=json.loads((repo/"artifacts/c7_full_population_t2_exit_overlay/population_manifest.json").read_text())["rows"]
        markets={s:c10.load_market(repo/c13.c7.INPUTS[s+"_1m"][0]) for s in c13.SYMBOLS}; result=c13.execute(population,data,markets); docs=documents(ready,attempt,result,data,population); validate_documents(docs)
        temp=Path(tempfile.mkdtemp(prefix="c13f-",dir=out)); hashes={}
        try:
            for name,value in docs.items():c13.write_json(temp/f"{name}.json",value);hashes[f"{name}.json"]=sha(temp/f"{name}.json")
            c13.write_json(temp/"reproducibility_hashes.json",hashes)
            for path in temp.iterdir():shutil.move(str(path),out/path.name)
        finally:shutil.rmtree(temp)
        append(ledger,{"attempt_id":attempt,"event":"ECONOMIC_EMISSION","timestamp":now(),"economic_read":True,"output_hashes":hashes})
        append(ledger,{"attempt_id":attempt,"event":"PASS","timestamp":now(),"economic_read":True,"output_hashes":hashes})
        return docs["final_summary"]
    except Exception as exc:
        append(ledger,{"attempt_id":attempt,"event":"FAIL","timestamp":now(),"economic_read":True,"failure":f"{type(exc).__name__}: {exc}"});raise
