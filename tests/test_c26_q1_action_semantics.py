from pathlib import Path
import inspect
import numpy as np
import pytest

from binance_data_foundation import c26_q1_action_semantics as c26


def test_contract_hash_and_frozen_scope():
    assert c26.sha(Path(c26.CONTRACT_REL)) == c26.CONTRACT_SHA256
    assert c26.TARGET == "DELTA_LIQ_5"
    source=inspect.getsource(c26)
    for forbidden in ("DELTA_LIQ_15", "DELTA_LIQ_30", "DELTA_LIQ_60", "DELTA_LIQ_EVENT"):
        assert forbidden not in source


def test_weighting_and_all_q1_summary():
    rows=[{"trade_id":"a","DELTA_LIQ_5":-1.,"probability":.1,"elapsed_minutes":5,"current_return_from_entry":0},
          {"trade_id":"a","DELTA_LIQ_5":1.,"probability":.2,"elapsed_minutes":10,"current_return_from_entry":.1},
          {"trade_id":"b","DELTA_LIQ_5":2.,"probability":.3,"elapsed_minutes":5,"current_return_from_entry":.2}]
    got=c26.weighted_summary(rows,[.5,.5,1.])
    assert got["snapshot_count"]==3 and got["trade_count"]==2
    assert got["weighted_mean_DELTA_LIQ_5"]==1.0
    assert got["weighted_positive_rate"]==.75


def test_quadrants_zero_rule_exclusive_and_exhaustive():
    assert c26.quadrant(-1,-1)=="SHORT_BAD_LIFECYCLE_BAD"
    assert c26.quadrant(-1,0)=="SHORT_BAD_LIFECYCLE_RECOVERS"
    assert c26.quadrant(0,-1)=="SHORT_OK_LIFECYCLE_BAD"
    assert c26.quadrant(0,0)=="SHORT_OK_LIFECYCLE_GOOD"
    assert len({c26.quadrant(v,p) for v in (-1,0) for p in (-1,0)})==4


def test_v5_vp0_same_trigger_and_label_cross_tab_logic():
    causal={"DELTA_LIQ_5":.002,"exit_now_net":.01}
    ledger={"canonical_p0_net_return":.03,"paired_return_difference":-.02}
    assert causal[c26.TARGET]==.002
    assert np.isclose(ledger["canonical_p0_net_return"]-causal["exit_now_net"],.02)
    assert c26.impact(ledger)=="SURRENDERED_UPSIDE"


def _bootstrap_rows():
    rows=[]; first=[]
    for tid,month,ys in (("a","2024-01",[-1.,2.]),("b","2024-02",[-2.,4.]),("c","2024-02",[1.])):
        for j,y in enumerate(ys):
            r={"trade_id":tid,"entry_month":month,"DELTA_LIQ_5":y,"base_weight":1/len(ys)}; rows.append(r)
            if j==0:first.append(r)
    return rows,first


def test_all_q1_and_first_vs_all_bootstrap_deterministic():
    rows,first=_bootstrap_rows()
    for unit in ("whole_trade","calendar_month"):
        a=c26.bootstrap(rows,first,unit,replicates=40); b=c26.bootstrap(rows,first,unit,replicates=40)
        assert a==b and a["generator"]=="PCG64"
        assert "Delta_first_all_mean" in a["intervals"]


def test_trade_concentration_accounting_and_month_loo_primitives():
    ledger=[{"paired_pnl_difference":x} for x in (4.,2.,-3.,-1.,0.)]
    got=c26.concentration(ledger)
    assert got["positive"]["total_contribution"]==6
    assert got["negative_absolute"]["total_contribution"]==4
    assert got["positive"]["trades_to_explain_50pct"]==1
    assert got["accounting_reconciles"]


def test_no_2024_training_leakage_and_one_first_trigger_per_trade_construction():
    rows=[{"trade_id":"a","state_ms":2},{"trade_id":"a","state_ms":1},{"trade_id":"b","state_ms":3}]
    first=[min((r for r in rows if r["trade_id"]==tid),key=lambda r:r["state_ms"]) for tid in sorted({r["trade_id"] for r in rows})]
    assert len(first)==len({r["trade_id"] for r in first})==2
    source=inspect.getsource(c26.run)
    assert 'datasets={2024:(train24,valid24)' in source


def test_no_new_model_policy_threshold_horizon_or_2026_access():
    with pytest.raises(PermissionError): c26.reject_2026("data/2026/x")
    source=inspect.getsource(c26.run)
    assert "fit_candidates" in source  # exact frozen score reproduction only
    assert "C_BASE" in source and "REPLICATES" in source
    assert '"new_model":False' in source and '"threshold_search":False' in source
    assert '"persistence_search":False' in source and '"alternate_policy":False' in source
