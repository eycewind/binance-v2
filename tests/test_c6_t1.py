from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import inspect
import copy
import hashlib
import multiprocessing
import numpy as np
import pytest

from binance_data_foundation.c6_t1 import *

UTC=timezone.utc

def _ledger_worker(path, payload, queue):
    try:
        append_attempt_event(Path(path),payload); queue.put("ok")
    except Exception as exc:
        queue.put(type(exc).__name__)

def test_provenance_fails_closed(tmp_path):
    (tmp_path/"contracts").mkdir(); (tmp_path/"contracts/C6_simple_t2_exit_controls_CONTRACT.md").write_text("changed")
    with pytest.raises(RuntimeError,match="contract hash"): provenance_gate(tmp_path,{})
    with pytest.raises(RuntimeError,match="missing accepted"): provenance_gate(Path("."),{"x":("missing","0"*64)})

def test_repository_provenance_passes_without_opening_economic_rows():
    got=provenance_gate(Path("."))
    assert got["status"]=="PASS" and got["population"]["pooled"]=={"snapshots":38745,"trades":439}
    assert not got["canonical_economic_rows_opened"] and not got["sealed_paths_enumerated"]

def test_exact_registry_hierarchy_and_no_variants():
    assert tuple(ALIASES.values()) == CONTROL_REGISTRY[3:]
    assert PRIMARY_HIERARCHY == (("S1_EXIT_FIRST_T2_V1","P0_HELD_V1"),("G1_Q75_EXIT_V1","S1_EXIT_FIRST_T2_V1"),("G1_Q75_EXIT_V1","S3_G1_TIMING_PERMUTATION_V1"))

def test_first_second_immediate_open_fallback_and_no_gap_skip():
    t=datetime(2024,1,1,1,5,tzinfo=UTC); path=[Snapshot("r1",t),Snapshot("r2",t+timedelta(minutes=5))]; p0=P0Exit(t+timedelta(hours=1),90)
    assert exit_first_t2(path,{t:[101]},p0).trigger_row_id=="r1"
    assert exit_second_t2(path,{path[1].completed_boundary:[102]},p0).trigger_row_id=="r2"
    assert exit_second_t2(path[:1],{},p0).label=="P0_FALLBACK"
    with pytest.raises(ValueError,match="zero-snapshot"): exit_second_t2([],{},p0)
    missing=exit_first_t2(path,{t+timedelta(minutes=1):[999]},p0)
    assert not missing.executable and missing.failure=="missing_immediate_next_1m_open"
    early=P0Exit(t,90); assert exit_first_t2(path,{t:[101]},early).label=="P0_FALLBACK"

def fixtures():
    return [TimingTrade("a",2024,"BTCUSDT",4,4),TimingTrade("b",2024,"BTCUSDT",2,2),TimingTrade("c",2024,"BTCUSDT",4,1),TimingTrade("d",2024,"BTCUSDT",1,"P0_FALLBACK"),
            TimingTrade("e",2025,"ETHUSDT",2,2),TimingTrade("f",2025,"ETHUSDT",1,"P0_FALLBACK")]

def test_g1_label_derivation_uses_timing_identity_only():
    assert derive_g1_timing_label(executed_before_p0=True,trigger_ordinal=2,path_length=3)==2
    assert derive_g1_timing_label(executed_before_p0=False,trigger_ordinal=None,path_length=1)=="P0_FALLBACK"
    with pytest.raises(ValueError,match="incompatible"): derive_g1_timing_label(executed_before_p0=True,trigger_ordinal=4,path_length=3)
    with pytest.raises(ValueError,match="cannot carry"): derive_g1_timing_label(executed_before_p0=False,trigger_ordinal=1,path_length=3)

def test_1000_constrained_permutations_deterministic_and_structural():
    a=timing_permutations(fixtures()); b=timing_permutations(fixtures())
    assert canonical_bytes(a)==canonical_bytes(b)
    v=validate_permutations(fixtures(),a)
    assert v["assignments"]==1000 and v["strata_preserved"] and v["timing_multisets_preserved"] and v["feasibility_rate"]==1
    assert all(r["label"]=="P0_FALLBACK" or r["label"]<=r["path_length"] for x in a for r in x["rows"])
    assert a[0]["strata_audit"][0]["priority_stream_start_inclusive"]==0
    assert a[-1]["strata_audit"][-1]["priority_stream_end_exclusive"]>0
    with pytest.raises(ValueError,match="frozen"): timing_permutations(fixtures(),99)

def test_s3_rejects_duplicate_ids_and_tampered_bijections_metadata_or_strata():
    with pytest.raises(ValueError,match="duplicate"): timing_permutations([fixtures()[0],fixtures()[0]])
    a=timing_permutations(fixtures())
    def cross_stratum(x):
        left,right=x[0]["rows"][0],x[0]["rows"][4]
        left["donor_trade_id"],right["donor_trade_id"]=right["donor_trade_id"],left["donor_trade_id"]
        left["label"],right["label"]=right["label"],left["label"]
    for mutate,match in [
        (lambda x:x[0].update(assignment=1),"indices"),
        (lambda x:x[0].update(master_seed=1),"RNG"),
        (lambda x:x[0]["rows"][0].update(trade_id=x[0]["rows"][1]["trade_id"]),"recipient"),
        (lambda x:x[0]["rows"][0].update(donor_trade_id=x[0]["rows"][1]["donor_trade_id"]),"donor"),
        (cross_stratum,"stratum"),
    ]:
        bad=copy.deepcopy(a); mutate(bad)
        with pytest.raises(RuntimeError,match=match): validate_permutations(fixtures(),bad)

def test_s3_authenticates_exact_rng_priorities_pairing_and_metadata():
    expected=timing_permutations(fixtures())
    mutations=[
        lambda x:x[0]["rows"][0].update(edge_priority_uint64=x[0]["rows"][0]["edge_priority_uint64"]+1),
        lambda x:x[0]["strata_audit"][0].update(priority_stream_start_inclusive=1),
        lambda x:x[0].update(unrecognized_score_instruction=True),
    ]
    # Swap two compatible donors while retaining a structurally valid bijection/multiset.
    def swap_pairing(x):
        rows=x[0]["rows"][:4]
        compatible=lambda label,length: label=="P0_FALLBACK" or label<=length
        pair=next((i,j) for i in range(len(rows)) for j in range(i+1,len(rows))
                  if compatible(rows[j]["label"],rows[i]["path_length"])
                  and compatible(rows[i]["label"],rows[j]["path_length"]))
        i,j=pair
        rows[i]["donor_trade_id"],rows[j]["donor_trade_id"]=rows[j]["donor_trade_id"],rows[i]["donor_trade_id"]
        rows[i]["label"],rows[j]["label"]=rows[j]["label"],rows[i]["label"]
    mutations.append(swap_pairing)
    for mutate in mutations:
        bad=copy.deepcopy(expected); mutate(bad)
        with pytest.raises(RuntimeError,match="deterministic reconstruction"):
            validate_permutations(fixtures(),bad)

def test_infeasible_randomization_fails_closed():
    bad=[TimingTrade("a",2024,"BTCUSDT",1,2),TimingTrade("b",2024,"BTCUSDT",1,"P0_FALLBACK")]
    with pytest.raises(ValueError,match="impossible"): timing_permutations(bad)

def test_controls_have_no_score_interface_and_coin_flip_once_deterministic():
    assert "score" not in TimingTrade.__dataclass_fields__
    rows=[{"trade_id":str(i),"entry_execution_ts":f"2024-01-{i+1:02d}","symbol":"BTCUSDT"} for i in range(20)]
    a=coin_flip_labels(rows); assert a==coin_flip_labels(rows) and all(x["decisions"]==1 for x in a)
    assert {x["label"] for x in a}<={1,"P0_FALLBACK"}
    assert "score" not in inspect.signature(exit_first_t2).parameters
    assert "score" not in inspect.signature(exit_second_t2).parameters
    assert "score" not in inspect.signature(timing_permutations).parameters
    assert "outcome" not in TimingTrade.__dataclass_fields__
    assert "score" not in inspect.signature(coin_flip_labels).parameters

def test_bootstrap_multiplicity_and_combined_randomization_reproducible():
    ids=[f"t{i}" for i in range(10)]; base=datetime(2024,1,1)
    weeks={t:(base+timedelta(days=7*i)).date().isoformat() for i,t in enumerate(ids)}
    samples=moving_block_samples(weeks); assert len(samples)==2000 and samples==moving_block_samples(weeks)
    assert any(len(s)!=len(set(s)) for s in samples)
    x=np.arange(10000,dtype=float).reshape(1000,10)/10000
    a=uncertainty_fixture(x,ids,samples); b=uncertainty_fixture(x,ids,samples)
    assert a==b and len(a["combined_assignment_indices"])==2000
    month_times={t:(base+timedelta(days=35*i)).isoformat() for i,t in enumerate(ids)}
    months=calendar_month_samples(month_times)
    assert len(months)==2000 and months==calendar_month_samples(month_times)
    assert any(len(s)!=len(set(s)) for s in months)
    with pytest.raises(ValueError,match="combined uncertainty seed"):
        uncertainty_fixture(x,ids,samples,seed=1)

@pytest.mark.parametrize("point,ci,label",[(1,(.1,2),"STRONG_POSITIVE"),(1,(0,2),"DIRECTIONAL_ONLY"),(0,(-1,1),"NULL_OR_OPPOSING"),(-1,(-2,-.1),"STRONG_NEGATIVE")])
def test_evidence_labels(point,ci,label): assert evidence_label(point,ci)==label

def test_hierarchy_stopping_and_all_interpretation_branches():
    assert reached_gates(["DIRECTIONAL_ONLY","STRONG_POSITIVE","STRONG_POSITIVE"])==(True,False,False)
    assert interpret("INSUFFICIENT")=="INSUFFICIENT_EVIDENCE"
    assert interpret("NULL_OR_OPPOSING")=="COUNTS_AGAINST_SIMPLE_T2_EXPLANATION"
    assert interpret("STRONG_POSITIVE","DIRECTIONAL_ONLY")=="SIMPLE_T2_EXIT_EXPLAINS_OBSERVED_VALUE"
    assert interpret("STRONG_POSITIVE","STRONG_POSITIVE","DIRECTIONAL_ONLY")=="MODEL_TIMING_ADDS_ECONOMIC_VALUE"
    assert interpret("STRONG_POSITIVE","STRONG_POSITIVE","STRONG_POSITIVE")=="MODEL_SELECTION_BEATS_RANDOM_TIMING"
    assert interpret("STRONG_POSITIVE","STRONG_POSITIVE","STRONG_POSITIVE",auxiliary_positive=False)=="MIXED"
    assert interpret("DIRECTIONAL_ONLY")=="MIXED"
    assert len(set(LABELS))==len(LABELS)

@pytest.mark.parametrize("g1,g2,g3,expected",[
    ("STRONG_POSITIVE","STRONG_POSITIVE","STRONG_POSITIVE","MIXED"),
    ("STRONG_POSITIVE","STRONG_POSITIVE","DIRECTIONAL_ONLY","MIXED"),
    ("STRONG_POSITIVE","STRONG_POSITIVE","NULL_OR_OPPOSING","MIXED"),
    ("STRONG_POSITIVE","DIRECTIONAL_ONLY",None,"SIMPLE_T2_EXIT_EXPLAINS_OBSERVED_VALUE"),
    ("DIRECTIONAL_ONLY",None,None,"MIXED"),
    ("NULL_OR_OPPOSING",None,None,"COUNTS_AGAINST_SIMPLE_T2_EXPLANATION"),
])
def test_safety_precedence_exact(g1,g2,g3,expected):
    assert interpret(g1,g2,g3,adverse_safety_breach=True)==expected

def test_secondary_context_cannot_rescue_or_reorder_primary_hierarchy():
    assert set(inspect.signature(interpret).parameters)=={"g1","g2","g3","auxiliary_positive","adverse_safety_breach"}
    assert reached_gates(["NULL_OR_OPPOSING","STRONG_POSITIVE","STRONG_POSITIVE"])==(True,False,False)
    g=reporting_governance()
    assert g["primary"]=="pooled" and not g["year_specific_tuning"] and not g["symbol_specific_tuning"]
    assert not any(x in inspect.signature(interpret).parameters for x in ("s2","s4","p1","year","symbol"))

def test_year_symbol_governance_costs_and_no_tuning():
    g=reporting_governance(); assert g["primary"]=="pooled" and g["mandatory_years"]==[2024,2025]
    assert not g["year_specific_tuning"] and not g["symbol_specific_tuning"] and len(g["mandatory_symbols"])==5
    assert set(COSTS)=={"C0","C_BASE","C_S5","C_S10"}

@pytest.mark.parametrize("case",["C0","C_BASE","C_S5","C_S10"])
def test_exact_c5_cost_arithmetic_on_synthetic_fixture(case):
    got=c5_cost_ledger(100,[(110,10)],C5_COST_CASES[case],10)
    assert got["fixed_replay_legs"]==2
    assert np.isclose(got["total_transaction_cost_quote"],got["entry_fee_quote"]+got["exit_fee_quote"]+got["slippage_cost_quote"])
    assert COSTS[case]["fee_per_leg"]==C5_COST_CASES[case].fee_rate
    assert COSTS[case]["adverse_slippage_per_leg"]==C5_COST_CASES[case].slippage_rate

def event(i,status="START"):
    x={"attempt_id":i,"event":status,"time":"2040-01-01T00:00:00Z","configuration_hash":"a","source_hash":"b","input_hashes":{},"random_seeds":{},"contract_sha256":CONTRACT_SHA256,"readiness_sha256":"c","status":status,"output_hashes":{"x":"h"} if status=="PASS" else {}}
    if status=="FAIL": x["failure_reason"]="synthetic failure"
    return x

def test_attempt_ledger_is_append_only_and_no_fake_attempt(tmp_path):
    p=tmp_path/"ledger.jsonl"; append_attempt_event(p,event("one")); first=p.read_bytes(); append_attempt_event(p,event("one","PASS"))
    assert p.read_bytes().startswith(first) and len(p.read_text().splitlines())==2
    with pytest.raises(ValueError): append_attempt_event(p,{"attempt_id":"bad"})

def test_attempt_lifecycle_rejects_invalid_order_and_duplicates(tmp_path):
    p=tmp_path/"ledger.jsonl"
    with pytest.raises(RuntimeError,match="START"): append_attempt_event(p,event("x","PASS"))
    append_attempt_event(p,event("x"))
    with pytest.raises(RuntimeError,match="exists"): append_attempt_event(p,event("x"))
    append_attempt_event(p,event("x","FAIL"))
    with pytest.raises(RuntimeError,match="START"): append_attempt_event(p,event("x","FAIL"))
    y=event("y","PASS"); y["output_hashes"]={}
    with pytest.raises(RuntimeError): append_attempt_event(p,y)
    append_attempt_event(p,event("z")); z=event("z","FAIL"); z["failure_reason"]=""
    with pytest.raises(ValueError,match="reason"): append_attempt_event(p,z)

def test_attempt_lifecycle_is_interprocess_atomic(tmp_path):
    ctx=multiprocessing.get_context("fork")
    p=tmp_path/"concurrent.jsonl"; q=ctx.Queue(); start=event("same")
    workers=[ctx.Process(target=_ledger_worker,args=(str(p),start,q)) for _ in range(2)]
    for w in workers:w.start()
    for w in workers:w.join(10)
    assert sorted(q.get(timeout=2) for _ in workers)==["RuntimeError","ok"]
    assert [json.loads(x)["event"] for x in p.read_text().splitlines()]==["START"]
    terminal=event("same","PASS"); q2=ctx.Queue()
    workers=[ctx.Process(target=_ledger_worker,args=(str(p),terminal,q2)) for _ in range(2)]
    for w in workers:w.start()
    for w in workers:w.join(10)
    assert sorted(q2.get(timeout=2) for _ in workers)==["RuntimeError","ok"]
    assert [json.loads(x)["event"] for x in p.read_text().splitlines()]==["START","PASS"]

@pytest.mark.parametrize("raw",["/data/2026/x.csv","data/predictions_2026.csv","data/2026Q1/x","SEALED/x","confirmation/x","data/confirmation_data.csv"])
def test_sealed_path_variants_rejected_without_probe(raw):
    with pytest.raises(PermissionError): reject_sealed_path(raw)

@pytest.mark.parametrize("raw",["data/2024/predictions.csv","data/2025/confirmed_schema.csv","artifacts/c6_design/readme.md","data/confirmatory_notes.txt"])
def test_ordinary_paths_allowed(raw): reject_sealed_path(raw)

def test_bad_lexical_path_precedes_every_filesystem_operation(monkeypatch):
    import binance_data_foundation.c6_t1 as m
    calls=[]
    monkeypatch.setattr(Path,"resolve",lambda self: calls.append("resolve"))
    monkeypatch.setattr(Path,"exists",lambda self: calls.append("exists"))
    monkeypatch.setattr(Path,"stat",lambda self: calls.append("stat"))
    monkeypatch.setattr(Path,"open",lambda self,*a,**k: calls.append("open"))
    with pytest.raises(PermissionError):
        m._internal_run_with_test_dependencies(repo=Path("synthetic/SEALED"),ledger_path=Path("ledger"),output_dir=Path("out"),
            economic_executor=lambda *_:None,execution_flag=T2_EXECUTION_FLAG)
    assert calls==[]

def test_provenance_rejects_supplied_sealed_path_before_filesystem(monkeypatch):
    calls=[]
    monkeypatch.setattr(Path,"is_file",lambda self:calls.append("is_file"))
    monkeypatch.setattr(Path,"open",lambda self,*a,**k:calls.append("open"))
    with pytest.raises(PermissionError): provenance_gate(Path("."),{"bad":("synthetic/Confirmation_Data.csv","0"*64)})
    assert calls==[]

def test_runner_provenance_failure_precedes_economic_executor(tmp_path):
    assert "readiness_sha256" not in inspect.signature(run_c6_t2_once).parameters
    assert "population_validator" not in inspect.signature(run_c6_t2_once).parameters
    assert "economic_executor" not in inspect.signature(run_c6_t2_once).parameters

def test_synthetic_runner_is_explicit_governed_and_terminal(monkeypatch,tmp_path):
    import binance_data_foundation.c6_t1 as m
    repo=tmp_path/"repo"; (repo/"contracts").mkdir(parents=True); (repo/"contracts/C6_simple_t2_exit_controls_CONTRACT.md").write_text("synthetic")
    ready=repo/"artifacts/c6_simple_t2_exit_controls/t1_readiness.json"; ready.parent.mkdir(parents=True)
    ready.write_text(json.dumps({"T2_ready":True,"blockers":[],"control_registry":list(CONTROL_REGISTRY),"seeds":{"coin_flip":20240926,"combined_uncertainty":20240925,"market_bootstrap":20240923,"random_timing":20240924}}))
    canonical=repo/UPSTREAM["canonical_c5_trade_results"][0]; canonical.parent.mkdir(parents=True); canonical.write_text("synthetic")
    for rel,_ in UPSTREAM.values():
        p=repo/rel; p.parent.mkdir(parents=True,exist_ok=True); p.touch(exist_ok=True)
    expected="a"*64
    freeze=repo/EXECUTION_FREEZE_REL; freeze.write_text(json.dumps({"version":"C6_T2_EXECUTION_FREEZE_V1",
        "readiness_path":"artifacts/c6_simple_t2_exit_controls/t1_readiness.json","readiness_sha256":expected,
        "contract_sha256":CONTRACT_SHA256,"runner_configuration_sha256":hashlib.sha256(canonical_bytes(m._runner_config())).hexdigest()}))
    def fake_sha(path):
        return CONTRACT_SHA256 if path.name.endswith("CONTRACT.md") else expected
    monkeypatch.setattr(m,"sha256",fake_sha)
    monkeypatch.setattr(m,"EXECUTION_FREEZE_SHA256",expected)
    prov=lambda _:{"artifacts":{k:{"sha256":v[1]} for k,v in UPSTREAM.items()},"population":{"pooled":{"snapshots":38745}}}
    calls=[]
    def engine(path,config):
        calls.append((path,config)); structural=fixtures(); assignments=timing_permutations(structural)
        return {"control_registry":list(CONTROL_REGISTRY),"hierarchy":[list(x) for x in PRIMARY_HIERARCHY],"interpretation":"MIXED","metrics":{},"statistics":{},
                "s3_assignments":assignments,"s3_structural_inputs":[x.__dict__ for x in structural],"seeds":config["seeds"]}
    ledger=tmp_path/"attempts.jsonl"
    with pytest.raises(PermissionError): m._internal_run_with_test_dependencies(repo=repo,ledger_path=ledger,output_dir=tmp_path/"denied",economic_executor=engine,execution_flag="",provenance_fn=prov)
    assert not calls and not ledger.exists()
    population={"trades":439,"by_year":{2024:155,2025:284},"by_symbol":{"BTCUSDT":74,"ETHUSDT":85,"SOLUSDT":106,"XRPUSDT":87,"BNBUSDT":87}}
    got=m._internal_run_with_test_dependencies(repo=repo,ledger_path=ledger,output_dir=tmp_path/"out",economic_executor=engine,
        execution_flag=T2_EXECUTION_FLAG,attempt_id="synthetic",provenance_fn=prov,population_fn=lambda _:population)
    assert got["status"]=="PASS" and len(calls)==1
    events=[json.loads(x) for x in ledger.read_text().splitlines()]
    assert [x["event"] for x in events]==["START","PASS"] and events[0]["source_hash"] and events[0]["configuration_hash"] and events[0]["input_hashes"]

@pytest.mark.parametrize("field,bad",[("by_year",{2024:156,2025:283}),
    ("by_symbol",{"BTCUSDT":75,"ETHUSDT":84,"SOLUSDT":106,"XRPUSDT":87,"BNBUSDT":87})])
def test_population_mismatch_fails_before_callback(field,bad):
    import binance_data_foundation.c6_t1 as m
    population={"trades":439,"by_year":{2024:155,2025:284},"by_symbol":{"BTCUSDT":74,"ETHUSDT":85,"SOLUSDT":106,"XRPUSDT":87,"BNBUSDT":87}}
    population[field]=bad; called=[]
    with pytest.raises(RuntimeError,match="complete frozen population"):
        m._assert_frozen_population(population,38745)
    assert not called

def test_readiness_cannot_invoke_economics_and_sealed_path_rejected(monkeypatch):
    import binance_data_foundation.c6_t1 as m
    monkeypatch.setattr(m,"execute_economic_replay",lambda:pytest.fail("economic replay called"))
    monkeypatch.setattr(m,"provenance_gate",lambda repo:{"artifacts":{k:{"sha256":v[1]} for k,v in UPSTREAM.items()}})
    out=m.build_readiness(Path("."),{"status":"PASS"}); assert out["T2_ready"] and not out["economic_replay_performed"]
    with pytest.raises(PermissionError): reject_sealed_path(Path("data")/"2026"/"x.csv")
    with pytest.raises(PermissionError): reject_sealed_path(Path("sealed_confirmation")/"x")
    with pytest.raises(PermissionError): execute_economic_replay()

def _freeze_payload(readiness_hash="a"*64):
    import binance_data_foundation.c6_t1 as m
    return {"version":"C6_T2_EXECUTION_FREEZE_V1","readiness_path":"artifacts/c6_simple_t2_exit_controls/t1_readiness.json",
            "readiness_sha256":readiness_hash,"contract_sha256":CONTRACT_SHA256,
            "runner_configuration_sha256":hashlib.sha256(canonical_bytes(m._runner_config())).hexdigest()}

def test_authoritative_freeze_hash_rejects_alteration_and_matching_readiness(monkeypatch,tmp_path):
    import binance_data_foundation.c6_t1 as m
    freeze=tmp_path/EXECUTION_FREEZE_REL;freeze.parent.mkdir(parents=True);freeze.write_bytes(canonical_bytes(_freeze_payload()))
    expected=hashlib.sha256(freeze.read_bytes()).hexdigest();monkeypatch.setattr(m,"EXECUTION_FREEZE_SHA256",expected)
    assert m._read_execution_freeze(tmp_path)["readiness_sha256"]=="a"*64
    freeze.write_bytes(canonical_bytes(_freeze_payload("b"*64)))
    readiness=tmp_path/"artifacts/c6_simple_t2_exit_controls/t1_readiness.json";readiness.write_text("altered matching readiness")
    with pytest.raises(RuntimeError,match="execution-freeze hash"):m._read_execution_freeze(tmp_path)

def test_approved_path_accepts_regular_and_allowed_symlink(tmp_path):
    regular=tmp_path/"ordinary_2024.txt";regular.write_text("ok")
    link=tmp_path/"ordinary_link";link.symlink_to(regular)
    assert approved_path(regular)==regular.resolve() and approved_path(link)==regular.resolve()

@pytest.mark.parametrize("target_name",["synthetic_2026.txt","synthetic_sealed.txt","synthetic_confirmation.txt"])
def test_approved_path_rejects_forbidden_symlink_before_content_read(monkeypatch,tmp_path,target_name):
    target=tmp_path/target_name;target.write_text("must not be read");link=tmp_path/"safe_link";link.symlink_to(target)
    opened=[];original=Path.open
    def watched(self,*a,**k):
        if self==target:opened.append(self)
        return original(self,*a,**k)
    monkeypatch.setattr(Path,"open",watched)
    with pytest.raises(PermissionError):approved_path(link)
    assert opened==[]

def _synthetic_economic_trades():
    import binance_data_foundation.c6_t1 as m
    out=[];start=datetime(2024,1,1,tzinfo=UTC)
    for i in range(10):
        entry=start+timedelta(weeks=i);entry_ms=int(entry.timestamp()*1000);tid=f"economic-{i:02d}"
        base={"trade_id":tid,"symbol":"BTCUSDT","year":2024,"entry_execution_ts":entry.isoformat(),
              "entry_execution_ms":entry_ms,"raw_entry_price":100.0,"trade_entry_week":entry.date().isoformat(),"t2_eligible":True}
        accepted=[]
        prices={"P0_HELD_V1":100.0,"G1_Q75_EXIT_V1":120.0,"P1_Q75_EXIT_V1":118.0}
        for policy,price in prices.items():
            for case in COSTS:accepted.append(m._cost_row(base,policy,price,entry_ms+3600000,policy!="P0_HELD_V1",case))
        ordinal=(i%3)+1 if i%3<2 else None
        out.append({**base,"p0_execution_ms":entry_ms+3600000,"p0_price":100.0,
                    "path":[{"row_id":f"{tid}-1","execution_ms":entry_ms+300000,"raw_open":110.0},
                            {"row_id":f"{tid}-2","execution_ms":entry_ms+600000,"raw_open":115.0}],
                    "g1_executed_before_p0":ordinal is not None,"g1_trigger_ordinal":ordinal,
                    "accepted_policy_rows":accepted,"adverse_safety_breach":False})
    return out

@pytest.fixture(scope="module")
def synthetic_economic_result():
    import binance_data_foundation.c6_t1 as m
    return m.execute_economic_fixture(_synthetic_economic_trades(),m._runner_config())

def test_executor_connects_all_controls_costs_seeds_and_s3(synthetic_economic_result):
    got=synthetic_economic_result
    assert got["control_registry"]==list(CONTROL_REGISTRY)
    assert got["seeds"]=={"market_bootstrap":20240923,"random_timing":20240924,"combined_uncertainty":20240925,"coin_flip":20240926}
    assert got["s3_authentication"]["assignments"]==1000
    summaries=got["metrics"]["policy_summaries"]["pooled"]
    for policy in ("S1_EXIT_FIRST_T2_V1","S2_EXIT_SECOND_T2_V1","S4_FIRST_T2_COIN_FLIP_V1"):
        assert set(summaries[policy])==set(COSTS)

def test_executor_exact_hierarchy_stopping_and_safety_precedence(synthetic_economic_result):
    import binance_data_foundation.c6_t1 as m
    got=synthetic_economic_result
    assert got["hierarchy"]==[list(x) for x in PRIMARY_HIERARCHY]
    assert got["statistics"]["reached"]==[True,True,True]
    adverse=_synthetic_economic_trades()
    for t in adverse:t["adverse_safety_breach"]=True
    assert m.execute_economic_fixture(adverse,m._runner_config())["interpretation"]=="MIXED"

def test_production_executor_requires_governed_capability():
    import binance_data_foundation.c6_t1 as m
    with pytest.raises(PermissionError,match="governed one-shot"):m.execute_economic_replay(Path("unused"),m._runner_config())

def _synthetic_runner_repo(tmp_path,monkeypatch):
    import binance_data_foundation.c6_t1 as m
    repo=tmp_path/"repo";(repo/"contracts").mkdir(parents=True);(repo/"contracts/C6_simple_t2_exit_controls_CONTRACT.md").write_text("synthetic")
    ready=repo/"artifacts/c6_simple_t2_exit_controls/t1_readiness.json";ready.parent.mkdir(parents=True)
    ready.write_text(json.dumps({"T2_ready":True,"blockers":[],"control_registry":list(CONTROL_REGISTRY),"seeds":{"coin_flip":20240926,"combined_uncertainty":20240925,"market_bootstrap":20240923,"random_timing":20240924}}))
    for rel,_ in UPSTREAM.values():p=repo/rel;p.parent.mkdir(parents=True,exist_ok=True);p.touch(exist_ok=True)
    freeze=repo/EXECUTION_FREEZE_REL;freeze.write_bytes(canonical_bytes(_freeze_payload()))
    expected="d"*64;monkeypatch.setattr(m,"EXECUTION_FREEZE_SHA256",expected)
    monkeypatch.setattr(m,"sha256",lambda p:CONTRACT_SHA256 if p.name.endswith("CONTRACT.md") else expected if p.name=="t2_execution_freeze.json" else "a"*64)
    prov=lambda _: {"artifacts":{k:{"sha256":v[1]} for k,v in UPSTREAM.items()},"population":{"pooled":{"snapshots":38745}}}
    pop=lambda _:{"trades":439,"by_year":{2024:155,2025:284},"by_symbol":{"BTCUSDT":74,"ETHUSDT":85,"SOLUSDT":106,"XRPUSDT":87,"BNBUSDT":87}}
    return m,repo,prov,pop

def test_runner_rejects_altered_s3_after_start_and_records_fail(monkeypatch,tmp_path):
    m,repo,prov,pop=_synthetic_runner_repo(tmp_path,monkeypatch);ledger=tmp_path/"ledger.jsonl"
    def engine(path,config):
        assert json.loads(ledger.read_text().splitlines()[0])["event"]=="START"
        structural=fixtures();assignments=timing_permutations(structural);rows=assignments[0]["rows"]
        i,j=0,1;rows[i]["donor_trade_id"],rows[j]["donor_trade_id"]=rows[j]["donor_trade_id"],rows[i]["donor_trade_id"]
        rows[i]["label"],rows[j]["label"]=rows[j]["label"],rows[i]["label"]
        return {"control_registry":list(CONTROL_REGISTRY),"hierarchy":[list(x) for x in PRIMARY_HIERARCHY],"interpretation":"MIXED","metrics":{},"statistics":{},
                "s3_assignments":assignments,"s3_structural_inputs":[x.__dict__ for x in structural],"seeds":config["seeds"]}
    with pytest.raises(RuntimeError,match="deterministic reconstruction"):
        m._internal_run_with_test_dependencies(repo=repo,ledger_path=ledger,output_dir=tmp_path/"out",economic_executor=engine,
            execution_flag=T2_EXECUTION_FLAG,attempt_id="altered",provenance_fn=prov,population_fn=pop)
    assert [json.loads(x)["event"] for x in ledger.read_text().splitlines()]==["START","FAIL"]

def test_synthetic_executor_failure_produces_one_fail_terminal(monkeypatch,tmp_path):
    m,repo,prov,pop=_synthetic_runner_repo(tmp_path,monkeypatch);ledger=tmp_path/"failure.jsonl"
    def engine(*_):raise RuntimeError("synthetic executor failure")
    with pytest.raises(RuntimeError,match="synthetic executor failure"):
        m._internal_run_with_test_dependencies(repo=repo,ledger_path=ledger,output_dir=tmp_path/"out",economic_executor=engine,
            execution_flag=T2_EXECUTION_FLAG,attempt_id="failed",provenance_fn=prov,population_fn=pop)
    events=[json.loads(x) for x in ledger.read_text().splitlines()]
    assert [x["event"] for x in events]==["START","FAIL"] and events[-1]["failure_reason"]
