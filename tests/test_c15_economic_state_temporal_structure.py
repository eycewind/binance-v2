import hashlib, json
from pathlib import Path

import pytest

from binance_data_foundation import c14_post_t2_economic_state as c14
from binance_data_foundation.c15_economic_state_temporal_structure import (
    CONTRACT_SHA256, category_distribution, magnitude_band, persistence,
    positive_concentration, reject_2026, state, trade_summary, transition_events,
)

def rows(states, tid="t", year=2024, symbol="BTCUSDT"):
    values={"HOLD_BETTER":.01,"EXIT_BETTER":-.01,"EXACT_ZERO":0.}
    return [{"trade_id":tid,"state_ms":(i+1)*60000,"economic_state":s,"delta_v":values[s],
             "year":year,"symbol":symbol,"event_label":"CONTINUATION_FIRST"} for i,s in enumerate(states)]

def test_contract_frozen(repo=Path(__file__).parents[1]):
    assert hashlib.sha256((repo/"contracts/C15_economic_state_temporal_structure_CONTRACT.md").read_bytes()).hexdigest()==CONTRACT_SHA256

def test_reuses_frozen_c14_delta_v_builder():
    assert c14.target_for_snapshot.__module__.endswith("c14_post_t2_economic_state")
    assert state(.1)=="HOLD_BETTER" and state(-.1)=="EXIT_BETTER" and state(0)=="EXACT_ZERO"

def test_transition_counting_and_runs():
    ts=trade_summary(rows(["HOLD_BETTER","HOLD_BETTER","EXIT_BETTER","EXIT_BETTER","HOLD_BETTER"]))[0]
    assert (ts["hold_to_exit"],ts["exit_to_hold"],ts["total_transitions"])==(1,1,2)
    assert ts["longest_hold_run"]==2 and ts["longest_exit_run"]==2
    assert ts["median_hold_dwell"]==1.5 and ts["median_exit_dwell"]==2

def test_persistence_horizon_and_whole_trade_weighting():
    rr=rows(["HOLD_BETTER"]*101,"long")+rows(["HOLD_BETTER","EXIT_BETTER"],"short")
    got=persistence(rr,(1,))["horizons_minutes"]["1"]["HOLD_BETTER"]
    assert got["eligible_trades"]==2 and got["whole_trade_weighted_same_state_probability"]==pytest.approx(.5)

@pytest.mark.parametrize(("x","expected"),[(.0009,"<0.10%"),(.001,"0.10% to <0.25%"),(.0025,"0.25% to <0.50%"),(.005,"0.50% to <1.00%"),(.01,">=1.00%")])
def test_near_zero_bins(x,expected): assert magnitude_band(x)==expected

def test_concentration_and_group_fields():
    rr=rows(["HOLD_BETTER"],"a",2024,"BTCUSDT")+rows(["HOLD_BETTER"],"b",2025,"ETHUSDT")
    rr[1]["delta_v"]=.03
    got=positive_concentration(rr)
    assert got["top_contribution"]["top_1_percent"]==pytest.approx(.75)
    ts=trade_summary(rr);assert {t["year"] for t in ts}=={2024,2025} and {t["symbol"] for t in ts}=={"BTCUSDT","ETHUSDT"}

def test_deterministic_outputs():
    rr=rows(["HOLD_BETTER","EXIT_BETTER","HOLD_BETTER"])
    assert json.dumps(category_distribution(trade_summary(rr),rr),sort_keys=True)==json.dumps(category_distribution(trade_summary(rr),rr),sort_keys=True)
    assert len(transition_events(rr))==2

@pytest.mark.parametrize("path",["data/2026/x","metadata/2026","2026.json"])
def test_no_2026_access(path):
    with pytest.raises(PermissionError): reject_2026(path)
