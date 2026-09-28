from pathlib import Path
import numpy as np
import pytest

from binance_data_foundation import c7_t1 as c7
from binance_data_foundation.c8_timescale import Market, MINUTE
from binance_data_foundation.c20_forward_liquidation_value import (
    TARGETS, band_name, liquidation_targets, reject_2026, summary,
)


def market(n=80, missing=(), opens=None):
    times=np.asarray([i*MINUTE for i in range(n) if i not in missing],dtype=np.int64)
    prices=np.asarray(opens if opens is not None else [100+i for i in range(n) if i not in missing],dtype=float)
    z=np.ones(len(times));return Market(times,prices,prices,prices,prices,z,z)


def trade(terminal=40, outcome="T2_FIRST"):
    return {"entry_price":100.,"terminal_ms":terminal*MINUTE,"terminal":outcome}


def test_immediate_and_exact_reassessment_next_open_timing():
    got=liquidation_targets({"state_ms":10*MINUTE},trade(),market(),140.)
    assert got["exit_now_execution_ms"]==10*MINUTE
    for h in (5,15,30):
        assert got[f"reassessment_ms_{h}"]==(10+h)*MINUTE
        assert got[f"endpoint_ms_{h}"]==(10+h)*MINUTE
        assert got[f"forward_price_{h}"]==100+10+h


def test_t2_before_horizon_truncates_and_never_reads_post_terminal():
    class Guard:
        ms=np.arange(0,21*MINUTE,MINUTE,dtype=np.int64);open=np.arange(100,121,dtype=float)
        def index(self,t):
            if t>20*MINUTE: raise AssertionError("post-terminal access")
            return int(t//MINUTE) if t>=0 and t%MINUTE==0 else None
    got=liquidation_targets({"state_ms":10*MINUTE},trade(20),Guard(),999.)
    assert got["endpoint_source_15"]=="T2_FIRST" and got["endpoint_ms_60"]==20*MINUTE
    assert got["DELTA_LIQ_EVENT"]==got["DELTA_LIQ_60"]


def test_p0_before_horizon_uses_frozen_p0_execution():
    got=liquidation_targets({"state_ms":10*MINUTE},trade(20,"P0_FIRST"),market(21),123.)
    assert got["endpoint_source_15"]=="P0_FIRST" and got["forward_price_60"]==123.


def test_gap_missing_evidence_fails_closed():
    got=liquidation_targets({"state_ms":10*MINUTE},trade(),market(missing=(14,)),140.)
    assert not got["eligible"] and got["reason"] in {"MISSING_NEXT_OPEN","GAP_OR_DUPLICATE_FAIL_CLOSED"}


def test_event_target_and_paired_cost_cancellation():
    tr=trade(20);got=liquidation_targets({"state_ms":10*MINUTE},tr,market(),120.,"C_BASE")
    cfg=c7.COSTS["C_BASE"];s,f=cfg["slippage_rate"],cfg["fee_rate"]
    q=1000/(100*(1+s)); expected=q*(1-s)*(1-f)*(120-110)/1000
    assert got["DELTA_LIQ_EVENT"]==pytest.approx(expected)
    assert got["DELTA_LIQ_EVENT"]==pytest.approx(c7.cost_ledger(100,120,"C_BASE")["net_return"]-c7.cost_ledger(100,110,"C_BASE")["net_return"])


@pytest.mark.parametrize("p,name",[(0,"<0.20"),(.2,"0.20 to <0.40"),(.4,"0.40 to <0.60"),(.6,"0.60 to <0.80"),(.8,">=0.80")])
def test_probability_bands(p,name): assert band_name(p)==name


def test_whole_trade_weighting_year_symbol_fields_and_determinism():
    rows=[{"trade_id":"a","p_t2":.1,"year":2024,"symbol":"BTCUSDT","DELTA_LIQ_5":x} for x in (0.,2.)]+[{"trade_id":"b","p_t2":.9,"year":2025,"symbol":"ETHUSDT","DELTA_LIQ_5":4.}]
    assert summary(rows,"DELTA_LIQ_5")["mean"]==pytest.approx(2.5)
    assert summary(rows,"DELTA_LIQ_5")==summary(rows,"DELTA_LIQ_5")


def test_no_future_max_target_and_no_2026_access():
    assert all("MAX" not in x and "BEST" not in x for x in TARGETS)
    with pytest.raises(PermissionError):reject_2026(Path("sealed/2026/metadata"))
