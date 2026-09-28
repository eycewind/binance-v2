from pathlib import Path

import numpy as np
import pytest

from binance_data_foundation.c8_timescale import (
    ARCHITECTURES, Bars, Market, aggregate, design, feature_row, fit_logistic,
    fit_scaler, moving_block_samples, paired_uncertainty, reject_2026,
    split_fold, terminal_for_trade, trade_weights,
)


def market(n=3000, start=1703980800000):
    ms=start+np.arange(n,dtype=np.int64)*60_000
    close=100*np.exp(np.arange(n)*1e-5); op=np.r_[close[0],close[:-1]]
    return Market(ms,op,np.maximum(op,close)*1.0002,np.minimum(op,close)*.9998,
                  close,np.arange(n,dtype=float)+100,np.ones(n)*10)


@pytest.mark.parametrize("minutes",[5,10,15,30,60,120])
def test_causal_aggregation_all_frozen_resolutions(minutes):
    m=market(); b=aggregate(m,minutes)
    i=4; end=int(b.end_ms[i]); start=m.index(end-minutes*60_000)
    assert b.close[i] == m.close[start+minutes-1]
    assert b.high[i] == max(m.high[start:start+minutes])
    assert end % (minutes*60_000) == 0


def test_completed_bar_availability_and_no_same_bar_future():
    m=market(); b=aggregate(m,5); end=int(b.end_ms[20]); i=b.at(end)
    changed=market(); source=changed.index(end)
    changed.close[source:]+=1000; changed.high[source:]+=1000
    b2=aggregate(changed,5)
    assert b.close[i] == b2.close[b2.at(end)]


def test_first_t2_terminal_cutoff_and_strict_p0():
    m=market(100); entry=int(m.ms[0]); p0=entry+60*60_000
    m.high[4]=102; m.close[4]=101.5
    tr={"entry_ms":entry,"p0_ms":p0,"entry_price":100}
    out=terminal_for_trade(tr,m)
    assert out=={"terminal_ms":entry+5*60_000,"label":1,"terminal":"T2_FIRST"}
    tr["p0_ms"]=entry+5*60_000
    assert terminal_for_trade(tr,m)["terminal"]=="P0_FIRST"


def test_feature_formulas_identical_and_no_future_leakage():
    m=market(); tr={"entry_ms":int(m.ms[2000]),"entry_price":float(m.close[2000]),"symbol":"BTCUSDT"}
    for _,(slow,fast) in ARCHITECTURES.items():
        sb,fb=aggregate(m,slow),aggregate(m,fast); t=((tr["entry_ms"]//(fast*60_000))+5)*fast*60_000
        a=feature_row(tr,t,m,sb,fb); assert a is not None
        assert set(k.split("_",1)[0] for k in a if k.startswith(("slow_","fast_")))=={"slow","fast"}
        m2=market(); ix=m2.index(t); m2.high[ix:]+=10000; m2.close[ix:]+=10000
        a2=feature_row(tr,t,m2,aggregate(m2,slow),aggregate(m2,fast))
        assert a==a2


def rows(ntrades=4):
    out=[]
    for t in range(ntrades):
        for j in range(t+1):
            out.append({"trade_id":str(t),"symbol":"BTCUSDT","entry_ms":1704067200000+t*604800000,
                "terminal_ms":1704067200000+t*604800000+1000,"state_ms":j,"label":t%2,
                "features":{"x":float(t+j)}})
    return out


def test_equal_trade_weighting():
    r=rows(); w=trade_weights(r)
    assert all(abs(sum(x for x,rr in zip(w,r) if rr["trade_id"]==t)-1)<1e-12 for t in {x["trade_id"] for x in r})


def test_chronological_fold_purge():
    r=rows(); r.append({**r[0],"trade_id":"cross","entry_ms":1704067200000,"terminal_ms":1719792000000})
    train,valid=split_fold(r,"fold_A")
    assert "cross" not in {x["trade_id"] for x in train}
    assert all(x["entry_ms"]<1719792000000 and x["terminal_ms"]<1719792000000 for x in train)


def test_training_only_scaling_and_deterministic_fit():
    r=rows(20); w=trade_weights(r); scale=fit_scaler(r,("x",),w)
    valid=[{**r[0],"features":{"x":1e9}}]
    assert scale==fit_scaler(r,("x",),w)
    x=design(r,("x",),scale); y=np.asarray([z["label"] for z in r],float)
    a=fit_logistic(x,y,w); b=fit_logistic(x,y,w)
    np.testing.assert_array_equal(a["coef"],b["coef"])
    assert design(valid,("x",),scale)[0,1] > 1e6


def test_whole_trade_bootstrap_and_seed():
    r=rows(30); samples=moving_block_samples(r,replicates=10)
    assert samples==moving_block_samples(r,replicates=10)
    assert all(isinstance(t,str) for sample in samples for t in sample)
    p=np.linspace(.1,.9,len(r)); out=paired_uncertainty(r,p,np.full(len(r),.5),samples)
    assert out["brier"]["ci95"]==paired_uncertainty(r,p,np.full(len(r),.5),samples)["brier"]["ci95"]


def test_no_2026_path_access():
    with pytest.raises(PermissionError): reject_2026(Path("data/2026/file.csv"))
