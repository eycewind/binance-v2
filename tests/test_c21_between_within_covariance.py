import json
from pathlib import Path
import numpy as np
import pytest

from binance_data_foundation.c21_between_within_covariance import (
    ADJUSTMENT_FIELDS, bootstrap, causal_adjustment, decomposition, reject_2026, trade_statistics,
)


def rows():
    out=[]
    specs={"a":(2024,"BTCUSDT",[(.1,1.,100.),(.3,0.,102.),(.5,-1.,104.)]),
           "b":(2025,"ETHUSDT",[(.7,4.,200.),(.9,2.,204.)])}
    for j,(tid,(year,symbol,values)) in enumerate(specs.items()):
        for k,(p,v,price) in enumerate(values):
            out.append({"trade_id":tid,"year":year,"symbol":symbol,"entry_ms":j*10**9,
                        "state_ms":j*10**9+(k+1)*300000,"p_t2":p,"DELTA_LIQ_5":v,
                        "elapsed_minutes":5.*(k+1),"current_return_from_entry":price/(100. if tid=="a" else 200.)-1})
    return out


def test_equal_total_trade_weight_and_covariance_identity():
    got=decomposition(rows(),"DELTA_LIQ_5")
    assert got["trades"]==2
    assert got["total_covariance"]==pytest.approx(got["between_trade_covariance"]+got["within_trade_covariance_component"],abs=1e-15)
    assert abs(got["reconstruction_residual"])<=1e-15


def test_covariance_and_correlation_are_distinct_summaries():
    got=decomposition(rows(),"DELTA_LIQ_5")
    assert "within_trade_covariance_component" in got
    assert got["within_trade_correlations"]["eligible_trades"]==1
    assert got["within_trade_covariance_component"]!=got["within_trade_correlations"]["mean"]


def test_year_symbol_grouping_and_trade_statistics():
    stats=trade_statistics(rows(),"DELTA_LIQ_5")
    assert {(x["year"],x["symbol"]) for x in stats}=={(2024,"BTCUSDT"),(2025,"ETHUSDT")}


def test_whole_trade_and_calendar_bootstrap_are_deterministic():
    a=bootstrap(rows(),"DELTA_LIQ_5"); b=bootstrap(rows(),"DELTA_LIQ_5")
    assert a==b and a["unit"]=="whole_trade"
    c=bootstrap(rows(),"DELTA_LIQ_5",True)
    assert c["unit"]=="calendar_month_cluster_of_whole_trades"


def test_causal_adjustment_fields_and_calculations():
    rr=rows(); got=causal_adjustment(rr,"DELTA_LIQ_5")
    assert ADJUSTMENT_FIELDS==("elapsed_minutes","current_return_from_entry")
    assert rr[0]["elapsed_minutes"]==(rr[0]["state_ms"]-rr[0]["entry_ms"])/60000
    assert rr[0]["current_return_from_entry"]==pytest.approx(0.)
    assert set(got).isdisjoint({"outcome","terminal_ms","p0_return","mfe","mae","mean_p","mean_v"})


def test_diagnostic_means_not_adjustment_features_and_no_2026():
    assert "mean_p" not in ADJUSTMENT_FIELDS and "mean_v" not in ADJUSTMENT_FIELDS
    with pytest.raises(PermissionError): reject_2026(Path("sealed/2026/data"))


def test_executed_c20_reproduction_and_live_feature_prohibition():
    root=Path(__file__).resolve().parents[1]; out=root/"artifacts/c21_between_within_covariance"
    reproduced=json.loads((out/"c20_reproduction.json").read_text())
    diagnostic=json.loads((out/"diagnostic_only_trade_means.json").read_text())
    assert reproduced["status"]=="PASS" and reproduced["population_match"]
    assert all(x==0 for x in reproduced["maximum_absolute_differences"].values())
    assert diagnostic["live_feature_schema"]==[]
    assert diagnostic["role"]=="DIAGNOSTIC_ONLY_NOT_A_LIVE_FEATURE"
