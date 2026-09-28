from pathlib import Path
import hashlib
import numpy as np
import pytest

from binance_data_foundation.c8_timescale import Market
from binance_data_foundation import c10_post_t2 as c10
from binance_data_foundation import c11_dynamic_post_t2 as c11
from binance_data_foundation.c17_entry_to_t2_path_class import (
    ALL_FEATURES, CONTRACT_SHA256, PATH_FEATURES, assert_feature_firewall,
    c16_classify, evaluate_2024, fit, path_features, predict, reject_2026,
)


def market(closes):
    c=np.asarray(closes,float);ms=np.arange(len(c),dtype=np.int64)*c10.MINUTE
    return Market(ms,c.copy(),c+1,c-1,c.copy(),np.ones(len(c)),np.ones(len(c)))


def trade(n, entry=100.):
    return {"trade_id":"x","entry_ms":0,"t0_ms":n*c10.MINUTE,"entry_price":entry}


def test_contract_frozen(repo_root=Path(__file__).parents[1]):
    assert hashlib.sha256((repo_root/"contracts/C17_entry_to_t2_path_class_CONTRACT.md").read_bytes()).hexdigest()==CONTRACT_SHA256


def test_entry_t2_boundaries_and_no_future_access():
    a=market([100,101,102,103,104,999]);b=market([100,101,102,103,104,-999])
    assert path_features(trade(5),a)==path_features(trade(5),b)
    assert path_features(trade(5),a)["entry_to_t2_minutes"]==5


def test_milestones_excursion_efficiency_peak_drawdown_and_fractions():
    m=market([100,101,99,102,101]);x=path_features(trade(5),m)
    assert x["entry_to_first_0p5pct_minutes"]==1
    assert x["entry_to_first_1pct_minutes"]==1
    assert x["pre_t2_mfe"]==pytest.approx(.03)
    assert x["pre_t2_mae"]==pytest.approx(-.02)
    assert x["pre_t2_range"]==pytest.approx(.05)
    movement=sum(abs(v/u-1) for u,v in zip([100,100,101,99,102],[100,101,99,102,101]))
    assert x["entry_to_t2_path_efficiency"]==pytest.approx(.01/movement)
    assert x["pre_t2_new_running_highs"]==3
    assert x["pre_t2_max_drawdown"]<0
    assert x["pre_t2_fraction_close_above_entry"]==pytest.approx(3/5)
    assert 0<=x["pre_t2_fraction_close_within_0p5pct_peak"]<=1


def test_volatility_late_momentum_acceleration_and_missing():
    c=np.arange(100.,140.);x=path_features(trade(40),market(c))
    expected=np.std(np.asarray(c)/np.r_[100.,c[:-1]]-1,ddof=0)
    assert x["pre_t2_return_std"]==pytest.approx(expected)
    assert x["final_5m_return"]==pytest.approx(c[-1]/c[-6]-1)
    assert x["final_15m_return"]==pytest.approx(c[-1]/c[-16]-1)
    assert x["final_30m_return"]==pytest.approx(c[-1]/c[-31]-1)
    assert x["final_5m_minus_preceding_5m"]==pytest.approx(c[-1]/c[-6]-1-(c[-6]/c[-11]-1))
    short=path_features(trade(6),market(c[:6]))
    assert short["final_5m_return_missing"]==0
    assert short["final_15m_return"] is None and short["final_15m_return_missing"]==1
    assert short["final_5m_minus_preceding_5m"] is None and short["acceleration_5m_missing"]==1


def test_one_row_class_definition():
    rows=[]
    for tid,states in (("h",["HOLD_BETTER"]*9+["EXIT_BETTER"]),("e",["EXIT_BETTER"]*9+["HOLD_BETTER"]),("m",["HOLD_BETTER"]*8+["EXIT_BETTER"]*2),("z",["EXIT_BETTER"]*8+["EXACT_ZERO"]*2)):
        for state in states: rows.append({"trade_id":tid,"economic_state":state,"year":2024,"symbol":"BTCUSDT","event_label":"DETERIORATION_FIRST"})
    classes,summary,by=c16_classify(rows)
    assert classes=={"h":"PREDOMINANTLY_HOLD","e":"PREDOMINANTLY_EXIT","m":"MIXED","z":"MIXED"}
    assert len(by)==4 and sum(v["count"] for v in summary.values())==4


def synthetic_rows():
    out=[]
    for i in range(32):
        entry=1704067200000+i*11*86400000
        features={n:float(i*.01+j*.001) for j,n in enumerate(ALL_FEATURES)}
        features["entry_to_first_1pct_minutes"]=None if i%3==0 else float(i)
        out.append({"trade_id":str(i),"symbol":c10.SYMBOLS[i%5],"year":2024,"entry_ms":entry,"t0_ms":entry+60000,"state_ms":entry+120000,
                    "terminal_ms":entry+180000,"event_label":"DETERIORATION_FIRST" if i%2 else "CONTINUATION_FIRST","label":i%2,"features":features})
    return out


def test_training_only_preprocessing_chronological_folds_and_determinism():
    rr=synthetic_rows();m=fit(rr,c11.NAMES);before=(dict(m["imputation"]),dict(m["scaler"]))
    predict(m,[rr[0]|{"features":rr[0]["features"]|{c11.NAMES[0]:1e30}}])
    assert (m["imputation"],m["scaler"])==before
    np.testing.assert_array_equal(m["model"]["coef"],fit(rr,c11.NAMES)["model"]["coef"])
    for fold in c10.FOLDS:
        tr,va=c10.split_fold(rr,fold)
        assert not ({r["trade_id"] for r in tr}&{r["trade_id"] for r in va})
        if tr and va: assert max(r["entry_ms"] for r in tr)<min(r["entry_ms"] for r in va)


def test_leakage_firewall_and_exact_schema():
    assert len(PATH_FEATURES)==len(set(PATH_FEATURES)) and set(PATH_FEATURES).issubset(ALL_FEATURES)
    assert_feature_firewall(ALL_FEATURES)
    with pytest.raises(ValueError): assert_feature_firewall(ALL_FEATURES+("delta_v",))


@pytest.mark.parametrize("path",["data/2026/x","metadata_2026.json",Path("sealed/2026Q1")])
def test_no_2026_access(path):
    with pytest.raises(PermissionError): reject_2026(path)
