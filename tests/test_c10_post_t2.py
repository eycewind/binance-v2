from pathlib import Path

import numpy as np
import pytest

from binance_data_foundation.c10_post_t2 import (
    ARCHITECTURES, CLASSES, Bars, Market, aggregate, feature_row, first_event,
    fit_multinomial, fit_scaler, freeze_geometry, load_c7_population,
    paired_uncertainty, reject_2026, split_fold, trade_weights,
)


def market(n=3000, start=1704067200000, flat=False):
    ms=start+np.arange(n,dtype=np.int64)*60_000
    close=np.full(n,101.0) if flat else 100*np.exp(np.arange(n)*1e-5)
    op=np.r_[close[0],close[:-1]]
    return Market(ms,op.copy(),np.maximum(op,close)*1.0002,np.minimum(op,close)*.9998,
                  close.copy(),np.arange(n,dtype=float)+100,np.ones(n)*10)


def trade(m, t0=20, p0=100):
    return {"trade_id":"x","symbol":"BTCUSDT","year":2024,"entry_ms":int(m.ms[0]),
            "entry_price":100.0,"t0_ms":int(m.ms[t0]),"p0_ms":int(m.ms[p0])}


def test_exact_c7_population_reconciliation(repo_root=Path(__file__).parents[1]):
    rows=load_c7_population(repo_root)
    assert len(rows)==845
    assert sum(r["year"]==2024 for r in rows)==415
    assert sum(r["year"]==2025 for r in rows)==430


def test_frozen_peak_and_level_construction():
    m=market(200,flat=True); m.high[5]=103; tr=trade(m)
    g=freeze_geometry(tr,m)
    assert g["p0_t2"]==103
    assert g["continuation_level"]==pytest.approx(103*1.005)
    assert g["deterioration_level"]==pytest.approx(101.5)
    m.high[30]=120
    assert freeze_geometry(tr,m)==g


def test_first_event_order_ambiguity_and_p0_precedence():
    m=market(200,flat=True); tr=trade(m)
    g=freeze_geometry(tr,m); m.high[25]=g["continuation_level"]
    assert first_event(tr,m)["terminal"]=="CONTINUATION_FIRST"
    m.high[21]=g["continuation_level"]; m.low[21]=g["deterioration_level"]
    assert first_event(tr,m)["terminal"]=="AMBIGUOUS"
    m.high[21]=101; m.low[21]=101; tr["p0_ms"]=int(m.ms[22]); m.high[22]=999
    assert first_event(tr,m)["terminal"]=="P0_FIRST"


@pytest.mark.parametrize("minutes",[1,2,5,10,15])
def test_completed_state_and_context_bars(minutes):
    m=market(); b=aggregate(m,minutes); end=int(b.end_ms[20]); i=b.at(end)
    changed=market(); source=changed.index(end); changed.close[source:]+=1000; changed.high[source:]+=1000
    b2=aggregate(changed,minutes)
    assert b.close[i]==b2.close[b2.at(end)]


def test_feature_formulas_identical_no_future_and_terminal_cutoff():
    m=market(); tr=trade(m,t0=2000,p0=2900)|{"p0_t2":float(m.high[1999])}
    tr|={"continuation_level":tr["p0_t2"]*1.005,"deterioration_level":50+tr["p0_t2"]/2}
    for _,(cm,fm) in ARCHITECTURES.items():
        t=((tr["t0_ms"]//(fm*60_000))+15)*fm*60_000
        a=feature_row(tr,t,m,aggregate(m,cm),aggregate(m,fm)); assert a is not None
        assert set(a)==set(feature_row(tr,t,m,aggregate(m,cm),aggregate(m,fm)))
        m2=market(); ix=m2.index(t); m2.close[ix:]+=999; m2.high[ix:]+=999
        b=feature_row(tr,t,m2,aggregate(m2,cm),aggregate(m2,fm))
        assert a==b


def rows(n=12):
    out=[]
    for i in range(n):
        for j in range(i%4+1):
            out.append({"trade_id":str(i),"symbol":"BTCUSDT","entry_ms":1704067200000+i*20_000_000,
                "terminal_ms":1704067200000+i*20_000_000+1000,"label":i%3,"features":{"x":float(i+j)}})
    return out


def test_per_trade_weighting_and_training_only_preprocessing():
    r=rows(); w=trade_weights(r)
    for tid in {x["trade_id"] for x in r}:
        assert sum(v for v,x in zip(w,r) if x["trade_id"]==tid)==pytest.approx(1)
    scale=fit_scaler(r,("x",),w); valid=[{**r[0],"features":{"x":1e12}}]
    assert scale==fit_scaler(r,("x",),w)
    assert valid[0]["features"]["x"]>scale["x"]["mean"]


def test_chronological_folds_and_whole_trade_purge():
    r=rows(); r.append({**r[0],"trade_id":"cross","entry_ms":1704067200000,"terminal_ms":1719792000000})
    train,valid=split_fold(r,"fold_A")
    assert "cross" not in {x["trade_id"] for x in train}
    assert all(x["entry_ms"]<1719792000000 and x["terminal_ms"]<1719792000000 for x in train)
    assert all(1719792000000<=x["entry_ms"]<1727740800000 for x in valid)


def test_deterministic_multinomial_and_uncertainty():
    r=rows(30); w=trade_weights(r); x=np.column_stack((np.ones(len(r)),np.arange(len(r))))
    y=np.asarray([z["label"] for z in r]); a=fit_multinomial(x,y,w); b=fit_multinomial(x,y,w)
    np.testing.assert_array_equal(a["coef"],b["coef"])
    p=np.tile([.3,.4,.3],(len(r),1)); q=np.tile([.2,.5,.3],(len(r),1))
    assert paired_uncertainty(r,p,q)==paired_uncertainty(r,p,q)


def test_no_2026_access():
    with pytest.raises(PermissionError): reject_2026("metadata/2026/index.json")
