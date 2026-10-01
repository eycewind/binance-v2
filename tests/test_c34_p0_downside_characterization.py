from pathlib import Path

import numpy as np
import pytest

from binance_data_foundation import c34_p0_downside_characterization as c34


def test_exact_crossdown_inclusive_sma_and_independent_of_e1():
    closes = [100.0] * 24 + [99.0]
    base = c34.START_MS - 25*c34.HOUR_MS
    hours = [{"open_time_ms": base+i*c34.HOUR_MS, "available_at_ms": base+(i+1)*c34.HOUR_MS, "close": str(x)} for i,x in enumerate(closes)]
    rows = c34.causal_hour_rows("BTCUSDT", hours)
    assert rows[-1]["is_p0"] is True
    assert "entry" not in rows[-1] and "trade" not in rows[-1]


def test_forward_endpoint_excursions_threshold_timing_and_no_membership_mutation():
    n=49*60+1; ts=np.arange(n,dtype=np.int64)*c34.MINUTE_MS; opens=np.ones(n)*100
    high=np.ones(n)*100; low=np.ones(n)*100; low[30]=98; high[90]=103; opens[60]=101
    m={"ts":ts,"open":opens,"high":high,"low":low}; state={"t_ms":0,"symbol":"BTCUSDT","year":"2024","month":"2024-01","is_p0":True}
    out=c34.evaluate_forward(state,m)
    assert out["return_1h"] == pytest.approx(.01); assert out["mae_1h"] == pytest.approx(-.02)
    assert out["time_to_mae_1h_minutes"] == 30; assert out["mfe_3h"] == pytest.approx(.03)
    assert out["down_10_3h"] and out["down_time_10_3h_minutes"] == 30
    assert out["up_20_3h"] and out["up_time_20_3h_minutes"] == 90
    high[-1]=1e9; assert c34.evaluate_forward(state,m)["return_1h"] == out["return_1h"]


def _row(t,is_p0,x,outcome):
    r={"symbol":"BTCUSDT","t_ms":t,"year":"2024","month":"2024-01","is_p0":is_p0,
       "current_1h_return":x,"trailing_24h_realized_volatility":x,"close_over_sma24_minus_1":x}
    for h in c34.HORIZONS:
        r.update({f"return_{h}h":outcome,f"mae_{h}h":outcome,f"mfe_{h}h":abs(outcome),f"down_05_{h}h":False,f"down_10_{h}h":False,f"down_20_{h}h":False,f"down_30_{h}h":False})
    return r


def test_non_p0_exclusion_causal_deterministic_matching_and_outcome_blindness():
    e=[_row(100,True,.1,-.5)]; c=[_row(1,False,.09,999),_row(2,False,.5,-999)]
    p1,a1=c34.match_state(e,c); c[0]["return_24h"]=-123456; p2,a2=c34.match_state(e,c)
    assert not p1[0]["control"]["is_p0"] and p1[0]["control"]["t_ms"]==p2[0]["control"]["t_ms"]==1
    assert a1["outcomes_used"] is a2["outcomes_used"] is False


def test_pcg64_bootstrap_deterministic_and_guards():
    pairs=[]
    for i in range(4):
        e=_row(100+i,True,.1,-.02); c=_row(i,False,.1,-.01); pairs.append({"event":e,"control":c})
    a=c34.bootstrap(pairs,"event"); b=c34.bootstrap(pairs,"event")
    assert a==b and a["iterations"]==2000 and a["generator"]=="PCG64" and a["paired"]
    with pytest.raises(PermissionError): c34.reject_2026(Path("data")/("20"+"26")/"x")


def test_frozen_scope_has_no_strategy_construction():
    source=Path(c34.__file__).read_text(encoding="utf-8")
    assert c34.P0_VERSION=="P0_H1_SMA24_CROSSDOWN_V1" and c34.HORIZONS==(1,3,6,12,24,48)
    assert c34.REPLICATES==2000 and c34.SEED==20261001
    for forbidden in ("short_entry", "stop_loss", "take_profit", "horizon_selection", "symbol_selection"):
        assert forbidden not in source


def test_total_population_is_distinct_from_fixed_horizon_eligibility():
    # A valid P0 event is defined causally; lack of a pre-2026 48h evaluation
    # path is reported separately and cannot erase the event from its count.
    assert "\"total_events\":total_detected" in Path(c34.__file__).read_text(encoding="utf-8")
