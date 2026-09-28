from pathlib import Path
import numpy as np
import pytest
from binance_data_foundation import c7_t1 as c7
from binance_data_foundation.c8_timescale import Market, MINUTE
from binance_data_foundation.c18_pre_t2_economic_value import (assert_feature_firewall, band_name, persistence,
    reject_2026, right_tail, summary, target_for_snapshot, trajectory_alignment)

def market(times=(0,MINUTE,2*MINUTE), opens=(100,101,102)):
    a=np.asarray(times,dtype=np.int64);p=np.asarray(opens,dtype=float);z=np.ones(len(a))
    return Market(a,p,p,p,p,z,z)

def test_target_next_open_cost_parity_and_delta():
    tr={"entry_price":100.,"p0_ms":3*MINUTE};r={"state_ms":MINUTE}
    got=target_for_snapshot(r,tr,market(),110.,"C_BASE")
    assert got["execution_ms"]==MINUTE and got["exit_now_price"]==101
    assert got["exit_now_net"]==pytest.approx(c7.cost_ledger(100,101,"C_BASE")["net_return"])
    assert got["delta_v"]==pytest.approx(c7.cost_ledger(100,110,"C_BASE")["net_return"]-got["exit_now_net"])

def test_p0_tie_precedence_and_gap_fail_closed():
    assert target_for_snapshot({"state_ms":MINUTE},{"entry_price":100.,"p0_ms":MINUTE},market(),100.)["reason"]=="P0_TIE_OR_PRECEDENCE"
    class Gap:
        ms=np.asarray([0,2*MINUTE]);open=np.asarray([100.,102.])
        def index(self,t): return 1 if t==2*MINUTE else None
    assert target_for_snapshot({"state_ms":2*MINUTE},{"entry_price":100.,"p0_ms":4*MINUTE},Gap(),103.)["reason"]=="GAP_FAIL_CLOSED"

@pytest.mark.parametrize("p,name",[(0.0,"<0.20"),(.2,"0.20 to <0.40"),(.4,"0.40 to <0.60"),(.6,"0.60 to <0.80"),(.8,">=0.80")])
def test_probability_band_assignment(p,name): assert band_name(p)==name

def rows():
    return [{"trade_id":"a","state_ms":i*5*MINUTE,"p_t2":p,"delta_v":d,"economic_state":"HOLD_BETTER" if d>0 else "EXIT_BETTER"} for i,(p,d) in enumerate(((.1,-.2),(.2,.1),(.3,.2)),1)] + [
        {"trade_id":"b","state_ms":5*MINUTE,"p_t2":.8,"delta_v":.4,"economic_state":"HOLD_BETTER"}]

def test_whole_trade_weighting_and_deterministic_trajectory_persistence():
    rr=rows();assert summary(rr)["mean_delta_v_pre"]==pytest.approx((np.mean([-.2,.1,.2])+.4)/2)
    assert trajectory_alignment(rr)==trajectory_alignment(rr)
    assert persistence(rr)["horizons_minutes"]["5"]["same_state_persistence"]==pytest.approx(.5)

def test_strict_target_feature_separation_and_no_2026():
    assert_feature_firewall(["current_return","running_mfe"])
    with pytest.raises(ValueError):assert_feature_firewall(["future_p0_return"])
    with pytest.raises(PermissionError):reject_2026(Path("sealed/2026/data"))

def test_snapshot_boundary_is_strictly_before_terminal():
    # Frozen C8 snapshot loop uses t < terminal; this guards the contract boundary directly.
    source=Path("src/binance_data_foundation/c8_timescale.py").read_text()
    assert "while t < terminal:" in source

def test_right_tail_positive_maximum_is_clamped_at_zero():
    rr=[{"trade_id":"x","state_ms":0,"delta_v":-.1},{"trade_id":"x","state_ms":1,"delta_v":-.2}]
    assert right_tail(rr)["maximum_positive_delta_v_per_trade"]["min"]==0
