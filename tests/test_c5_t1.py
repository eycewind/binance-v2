from datetime import datetime, timedelta, timezone
import copy, math
import numpy as np, pytest
from binance_data_foundation.c5_t1 import *

UTC=timezone.utc
def prob(row="r",model="G1",give=.6,peak=.2): return {"row_id":row,"trade_id":"t","symbol":"BTCUSDT","snapshot_ms":"1704067200000","target":"T2","model":model,"p_renewed_peak":peak,"p_substantial_giveback":give,"p_no_event_60m":1-give-peak}

def test_governance_and_upstream_fail_closed(tmp_path):
    repo=tmp_path; (repo/"contracts").mkdir();
    (repo/"contracts/C5_economic_exit_policy_CONTRACT.md").write_text("bad"); (repo/"contracts/C5_economic_exit_policy_ADDENDUM.md").write_text("bad")
    with pytest.raises(RuntimeError,match="governance hash mismatch"): verify_governance(repo)
    with pytest.raises(RuntimeError,match="missing authoritative"): provenance_gate(Path("."),{"x":("missing", "0"*64)})

def test_prediction_exact_coverage_and_rejections():
    exp=[{"row_id":"r","trade_id":"t","symbol":"BTCUSDT","snapshot_ms":"1704067200000"}]
    rows=[prob(model="G1"),prob(model="P1")]
    assert prediction_coverage(exp,rows)["status"]=="PASS"
    assert prediction_coverage(exp,rows[:-1])["missing_predictions"]==1
    assert prediction_coverage(exp,rows+[rows[0]])["duplicate_predictions"]==1
    bad=copy.deepcopy(rows);bad[0]["trade_id"]="wrong";assert prediction_coverage(exp,bad)["mismatches"]["trade_id"]==1
    bad=copy.deepcopy(rows);bad[0]["symbol"]="ETHUSDT";assert prediction_coverage(exp,bad)["mismatches"]["symbol"]==1
    bad=copy.deepcopy(rows);bad[0]["snapshot_ms"]="1";assert prediction_coverage(exp,bad)["mismatches"]["snapshot_ms"]==1
    bad=copy.deepcopy(rows);bad[0]["target"]="T1";assert prediction_coverage(exp,bad)["mismatches"]["target"]==1
    extra=rows+[prob("extra","G1")];assert prediction_coverage(exp,extra)["extra_predictions"]==1

def test_whole_path_exclusion_rules_and_identity():
    raw=["a","b","c","d"]
    assert whole_path_authorization(raw,set(raw),set(raw))["authorized"]
    assert whole_path_authorization(raw,{"b","c","d"},{"b","c","d"})["path_pattern"]=="left_truncated"
    assert whole_path_authorization(raw,{"a","c","d"},{"a","c","d"})["path_pattern"]=="internally_gapped"
    assert whole_path_authorization(raw,{"a","b","c"},{"a","b","c"})["path_pattern"]=="right_truncated"
    assert whole_path_authorization(raw,set(),set())["path_pattern"]=="wholly_unpredicted"
    with pytest.raises(RuntimeError,match="G1/P1"):whole_path_authorization(raw,{"a"},{"b"})

def test_score_thresholds_global_and_governance():
    rows=[prob(str(i),m,give=.2+i*.05,peak=.1) for m in ("G1","P1") for i in range(8)]
    got=freeze_thresholds(rows)
    assert got["G1"]["Q75"]==got["P1"]["Q75"] and got["G1"]["global_not_symbol_specific"]
    assert got["G1"]["Q75"]==np.quantile([state_score(r) for r in rows[:8]],.75,method="linear")
    assert not q90_can_advance("MIXED","SUPPORTS BROAD ECONOMIC EXIT VALUE")
    assert len(POLICIES)==5 and POLICIES[1::2]==("G1_Q75_EXIT_V1","G1_Q90_EXIT_V1")

def test_activation_boundaries():
    assert t2_active(100,101,100.50001,True)
    assert not t2_active(100,100.99999,101,True)
    assert not t2_active(100,101,100.5,True)
    assert not t2_active(100,101,0,True)
    assert not t2_active(100,101,101,False)

def test_execution_first_trigger_fallback_and_no_skip():
    t=datetime(2024,1,1,1,5,tzinfo=UTC); h=t+timedelta(hours=1); p0=h
    snaps=[Snapshot("a",t,.9),Snapshot("b",t+timedelta(minutes=5),1)]
    x=replay_synthetic(snaps,.8,{t:[102],t+timedelta(minutes=5):[999]},h,p0,90)
    assert x.trigger_row_id=="a" and x.execution_ts==t and x.raw_exit_price==102
    x=replay_synthetic(snaps,.8,{t+timedelta(minutes=1):[102]},h,p0,90);assert not x.executable and "missing" in x.censor_reason
    assert replay_synthetic(snaps,2,{},h,p0,90).reason=="P0_FALLBACK"
    assert replay_synthetic([Snapshot("x",p0,.9)],.8,{p0:[100]},h,p0,90).reason=="P0_FALLBACK"

@pytest.mark.parametrize("name,bp",[("C0",0),("C_BASE",24),("C_S5",30),("C_S10",40)])
def test_cost_cases_and_per_leg_charging(name,bp):
    case=COSTS[name]; got=cost_ledger(100,[(100,5),(100,5)],case,10)
    assert case.approximate_round_trip_bp==bp and got["fixed_replay_legs"]==3
    assert len(got["exit_transactions"])==2
    assert math.isclose(got["total_transaction_cost_quote"],got["entry_fee_quote"]+got["exit_fee_quote"]+got["slippage_cost_quote"])
    if name=="C_BASE": assert all(x["fee_quote"]>0 for x in got["exit_transactions"])

def test_reporting_support_and_concentration():
    schema=metric_row_schema();assert set(SYMBOLS)<set(schema) and "pooled_trade_weighted" in schema
    assert support_classification(49)=="INSUFFICIENT SUPPORT" and support_classification(50)=="SUFFICIENT"
    p={s:10 for s in SYMBOLS};g={s:1 for s in SYMBOLS};eligible={s:50 for s in SYMBOLS};ci={s:(0,2) for s in SYMBOLS}
    assert concentration(p,g,eligible,ci,True)["classification"].startswith("BROAD")
    p["BTCUSDT"]=41; p["ETHUSDT"]=-1
    got=concentration(p,g,eligible,ci,True);assert got["classification"].startswith("CONCENTRATED") and got["signed_p1_minus_p0"]["ETHUSDT"]==-1 and got["total_negative_contribution_magnitude"]==1
    row={k:0 for k in REPORT_FIELDS};row.update({"trade_id":"t","gross_return":.02,"net_return":.01,"t2_eligible":True,"triggered":True})
    summary=compute_metric_summary([row]);assert summary["net_expectancy"]==.01 and summary["fixed_notional_net_pnl"]==10 and summary["t2_eligible_trades"]==1

def test_population_gate_layers_support_and_governance(monkeypatch):
    got=replay_population_gate(Path("."));assert got["status"]=="PASS" and not got["no_action_substitution"] and not got["in_sample_2024_backfill"]
    assert set(got["layers"])=={"raw_T2_eligible","complete_case_model_eligible","authorized_frozen_prediction","replay_authorized_complete_path"}
    for layer in got["layers"].values():assert set(layer)>= {"pooled","by_year","by_symbol","by_year_symbol"}
    assert got["year_role"]["split_role"]=="DIAGNOSTIC_ONLY_NO_POLICY_SELECTION_OR_TUNING"
    assert all(x["replay_authorized_complete_path_trades"]>=50 for x in got["support"].values())

def test_readiness_does_not_call_economic_functions(monkeypatch):
    monkeypatch.setattr("binance_data_foundation.c5_t1.compute_metric_summary",lambda *a,**k:pytest.fail("economic metric called"))
    monkeypatch.setattr("binance_data_foundation.c5_t1.replay_synthetic",lambda *a,**k:pytest.fail("replay called"))
    got=build_readiness(Path("."),{"status":"PASS"});assert got["T2_ready"] and not got["economic_replay_performed"] and not got["real_PnL_calculated"]

def test_classification_rules_and_q90_no_rescue():
    assert symbol_strength(50,.1,(.01,.2),.1)=="STRONG SUPPORT"
    assert symbol_strength(50,.1,(-.1,.2),.1)=="DIRECTIONAL SUPPORT"
    assert symbol_strength(49,.1,(.01,.2),.1)=="INSUFFICIENT SUPPORT"
    assert deployment_label(50,.1,.1,(0,.2),(0,.2),False,True)=="SUITABLE FOR FURTHER VALIDATION"
    assert overall_classification(True,.1,.1,(.01,.2),(0,.2),False,True,True,"BROAD / MULTI-SYMBOL ECONOMIC VALUE").startswith("SUPPORTS BROAD")
    assert not q90_can_advance("COUNTS AGAINST","SUPPORTS BROAD ECONOMIC EXIT VALUE")

def test_bootstrap_blocks_whole_trades_deterministic():
    values={f"t{i}":float(i) for i in range(8)}; weeks={f"t{i}":f"2024-01-{1+7*i:02d}" for i in range(4)}
    # Continue in February with valid ISO dates.
    base=datetime(2024,1,1)
    weeks={f"t{i}":(base+timedelta(days=7*i)).date().isoformat() for i in range(8)}
    a=moving_block_bootstrap(values,weeks);b=moving_block_bootstrap(values,weeks)
    assert a["available"] and len(a["replicates"])==2000 and a["replicates"]==b["replicates"] and a["ci95"]==b["ci95"] and a["multiplicity_preserved"]

def test_t1_has_no_real_replay_or_sealed_access():
    source=Path(__file__).parents[1]/"src/binance_data_foundation/c5_t1.py"; text=source.read_text()
    assert "sealed" not in text.lower() or "sealed_paths_enumerated" in text
    assert "economic_replay_performed\":False" in text.replace(" ","")
    assert not hasattr(__import__("binance_data_foundation.c5_t1",fromlist=["x"]),"run_historical_replay")
