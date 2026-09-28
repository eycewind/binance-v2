from pathlib import Path
import hashlib
import numpy as np
import pytest

from binance_data_foundation.c8_timescale import Market
from binance_data_foundation import c10_post_t2 as c10
from binance_data_foundation import c11_dynamic_post_t2 as c11
from binance_data_foundation.c16_cross_asset_economic_state import (
    ALL_FEATURES, CONTRACT_SHA256, CROSS_FEATURES, cross_asset_features,
    evaluate_2024, fit, predict, reject_2026,
)

def markets(n=130, future_bump=False):
    ms=np.arange(n,dtype=np.int64)*60000
    out={}
    for j,s in enumerate(c10.SYMBOLS):
        p=100+j+np.arange(n)*(j+1)*.01
        if future_bump:p[-1]=1e8
        out[s]=Market(ms,p.copy(),p+1,p-1,p.copy(),np.ones(n),np.ones(n))
    return out

def test_contract_frozen(repo_root=Path(__file__).parents[1]):
    assert hashlib.sha256((repo_root/"contracts/C16_cross_asset_economic_state_CONTRACT.md").read_bytes()).hexdigest()==CONTRACT_SHA256

def test_alignment_completed_bars_and_no_future_bars():
    t=120*60000;a=cross_asset_features("SOLUSDT",t,markets())
    b=cross_asset_features("SOLUSDT",t,markets(future_bump=True))
    assert a==b and set(a)==set(CROSS_FEATURES)
    broken=markets();broken["ETHUSDT"].ms[119]+=1
    assert cross_asset_features("SOLUSDT",t,broken) is None

def test_frozen_feature_formulas():
    mm=markets();t=120*60000;x=cross_asset_features("SOLUSDT",t,mm)
    r={s:mm[s].close[119]/mm[s].close[114]-1 for s in c10.SYMBOLS}
    a=np.asarray(list(r.values()))
    assert x["btc_return_5m"]==pytest.approx(r["BTCUSDT"])
    assert x["eth_return_5m"]==pytest.approx(r["ETHUSDT"])
    assert x["market_return_5m"]==pytest.approx(a.mean())
    assert x["market_breadth_5m"]==pytest.approx(np.mean(a>0))
    assert x["relative_btc_5m"]==pytest.approx(r["SOLUSDT"]-r["BTCUSDT"])
    assert x["relative_market_5m"]==pytest.approx(r["SOLUSDT"]-a.mean())
    assert x["dispersion_5m"]==pytest.approx(np.std(a,ddof=0))
    assert x["market_abs_vol_30m"]>=0 and -1<=x["btc_corr_60m"]<=1

def test_btc_neutral_self_value_and_indicator():
    x=cross_asset_features("BTCUSDT",120*60000,markets())
    assert x["btc_corr_60m"]==0 and x["btc_self_indicator"]==1

def rows():
    out=[]
    for i in range(24):
        entry=1704067200000 + i*14*86400000
        for k in range(1+i%3):
            feat={n:float(i*.1+k*.01+j*.001) for j,n in enumerate(ALL_FEATURES)}
            out.append({"trade_id":str(i),"symbol":c10.SYMBOLS[i%5],"entry_ms":entry,"terminal_ms":entry+60000,"state_ms":entry+60000,"label":i%2,"event_label":"DETERIORATION_FIRST" if i%3==0 else "CONTINUATION_FIRST","features":feat})
    return out

def test_whole_trade_weighting_training_only_and_determinism():
    rr=rows();m=fit(rr,c11.NAMES);before=dict(m["scaler"])
    altered=[rr[0]|{"features":rr[0]["features"]|{c11.NAMES[0]:1e30}}]
    predict(m,altered);assert m["scaler"]==before
    np.testing.assert_array_equal(m["model"]["coef"],fit(rr,c11.NAMES)["model"]["coef"])
    w=c10.trade_weights(rr)
    assert all(sum(v for v,r in zip(w,rr) if r["trade_id"]==tid)==pytest.approx(1) for tid in {r["trade_id"] for r in rr})

def test_chronological_folds_are_whole_trade():
    rr=rows()
    for fold in c10.FOLDS:
        train,valid=c10.split_fold(rr,fold)
        assert not ({r["trade_id"] for r in train}&{r["trade_id"] for r in valid})
        if train and valid:assert max(r["entry_ms"] for r in train)<min(r["entry_ms"] for r in valid)

def test_no_target_features():
    assert not any(any(b in n for b in ("delta_v","future","p0","exit_now","hold_to")) for n in ALL_FEATURES)

@pytest.mark.parametrize("path",["data/2026/x","metadata_2026.json",Path("sealed/2026Q1")])
def test_no_2026_access(path):
    with pytest.raises(PermissionError):reject_2026(path)
