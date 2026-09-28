from datetime import datetime, timezone
import numpy as np
from binance_data_foundation import c13_warning_economics as c13

class Market:
    def __init__(self,ms,opens,lows=None):
        self.ms=np.asarray(ms);self.open=np.asarray(opens,float);self.low=np.asarray(lows or opens,float)
    def index(self,t):
        x=np.flatnonzero(self.ms==t);return int(x[0]) if len(x)==1 else None

def test_w1_strict_p3_and_next_open():
    m=Market([60_000,120_000,180_000,240_000],[10,11,12,13])
    rows=[{"state_ms":x} for x in (60_000,120_000,180_000)]
    assert c13.w1_choice({"rows":rows,"p":np.array([.19,.20,.19])},300_000,m)["triggered"] is False
    got=c13.w1_choice({"rows":rows,"p":np.array([.19,.10,.05])},300_000,m)
    assert got["triggered"] and got["execution_ms"]==180_000 and got["exit_price"]==12

def test_w1_tie_and_gap_fail_closed():
    m=Market([60_000,180_000],[10,12]);rows=[{"state_ms":x} for x in (60_000,120_000,180_000)]
    assert c13.w1_choice({"rows":rows,"p":np.array([.1,.1,.1])},180_000,m)["reason"]=="P0_TIE_OR_PRECEDENCE"
    rows=[{"state_ms":x} for x in (60_000,180_000,240_000)]
    assert c13.w1_choice({"rows":rows,"p":np.array([.1,.1,.1])},300_000,m)["reason"]=="DISCONTINUOUS_P3"

def test_d2_frozen_touch_next_open_and_tie():
    m=Market([60_000,120_000,180_000],[10,11,12],[10,8,7])
    tr={"t0_ms":60_000,"deterioration_level":9}
    got=c13.d2_choice(tr,240_000,m);assert got["triggered"] and got["execution_ms"]==180_000 and got["exit_price"]==12
    assert c13.d2_choice(tr,180_000,m)["triggered"] is False

def test_unavailable_exact_fallback_and_seed():
    m=Market([60_000],[10]);got=c13.w1_choice(None,60_000,m)
    assert got=={"triggered":False,"execution_ms":60_000,"reason":"UNAVAILABLE_PROBABILITY"}
    assert c13.SEED==20261013 and c13.REPLICATES==2000

def test_costs_actual_legs_and_no_2026():
    from binance_data_foundation.c7_t1 import cost_ledger
    x=cost_ledger(100,110,"C_BASE");assert x["executed_legs"]==2 and x["exit_executed_notional"]!=1000
    try:c13.reject_2026("data/2026/file.csv")
    except PermissionError:pass
    else:assert False

def test_frozen_population_constants():
    assert c13.POLICIES==("P0","W1","D2_CONTROL") and len(c13.SYMBOLS)==5
