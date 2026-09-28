from pathlib import Path
import hashlib
import numpy as np
import pytest

from binance_data_foundation import c7_t1 as c7
from binance_data_foundation import c10_post_t2 as c10
from binance_data_foundation import c11_dynamic_post_t2 as c11
from binance_data_foundation.c8_timescale import Market
from binance_data_foundation.c14_post_t2_economic_state import (
    CONTRACT_SHA256, assert_feature_firewall, fit_logistic, predict_logistic,
    reject_2026, target_for_snapshot, weights,
)

def market(times=(0,60000,120000),opens=(100,105,110)):
    a=np.asarray(times,dtype=np.int64);p=np.asarray(opens,dtype=float);v=np.ones(len(a))
    return Market(a,p,p+1,p-1,p,v,np.ones(len(a),dtype=np.int64))

def trade(p0=120000):return {"entry_price":100.,"p0_ms":p0}
def row(t=60000):return {"state_ms":t}

def test_contract_frozen(repo_root=Path(__file__).parents[1]):
    assert hashlib.sha256((repo_root/"contracts/C14_post_t2_economic_state_CONTRACT.md").read_bytes()).hexdigest()==CONTRACT_SHA256

def test_delta_v_next_open_p0_and_identical_costs():
    got=target_for_snapshot(row(),trade(),market(),120.,"C_BASE")
    now=c7.cost_ledger(100,105,"C_BASE")["net_return"];hold=c7.cost_ledger(100,120,"C_BASE")["net_return"]
    assert got["exit_now_price"]==105 and got["exit_now_net"]==pytest.approx(now)
    assert got["hold_to_p0_net"]==pytest.approx(hold)
    assert got["delta_v"]==pytest.approx(hold-now) and got["economic_state"]=="HOLD_BETTER"

def test_exact_zero_and_exit_better():
    assert target_for_snapshot(row(),trade(),market(),105.)["economic_state"]=="EXACT_ZERO"
    assert target_for_snapshot(row(),trade(),market(),90.)["economic_state"]=="EXIT_BETTER"

def test_p0_tie_precedence_and_gap_handling():
    assert target_for_snapshot(row(120000),trade(),market(),120.)["reason"]=="P0_TIE_OR_PRECEDENCE"
    assert target_for_snapshot(row(),trade(),market((0,60000,180000)),120.)["eligible"]
    assert target_for_snapshot(row(120000),trade(180000),market((0,120000,180000)),120.)["reason"]=="MISSING_NEXT_OPEN"

def test_strict_causal_feature_target_firewall():
    assert_feature_firewall(c11.NAMES+c10.SYMBOL_FEATURES)
    for bad in ("future_mfe","future_MAE_5m","eventual_p0_return","delta_v","future_recovery"):
        with pytest.raises(ValueError):assert_feature_firewall([bad])

def synthetic_rows():
    out=[]
    for i in range(8):
        for j in range(1+(i%3)):
            feat={n:float(i+j/10+k/100) for k,n in enumerate(c11.NAMES)}
            out.append({"trade_id":str(i),"symbol":c10.SYMBOLS[i%5],"label":i%2,"features":feat})
    return out

def test_per_trade_weighting_and_training_only_preprocessing():
    rr=synthetic_rows();w=weights(rr)
    assert all(sum(x for x,r in zip(w,rr) if r["trade_id"]==tid)==pytest.approx(1) for tid in {r["trade_id"] for r in rr})
    model=fit_logistic(rr,c10.CONTEXT_FEATURES);before=dict(model["scaler"])
    altered=[rr[0]|{"features":rr[0]["features"]|{c10.CONTEXT_FEATURES[0]:1e20}}]
    predict_logistic(model,altered);assert model["scaler"]==before

def test_chronological_whole_trade_folds():
    for start,cut,end in c10.FOLDS.values():
        assert start<cut<end
    rr=[]
    for i,(entry,terminal) in enumerate(((1705000000000,1706000000000),(1719000000000,1719500000000),(1728000000000,1729000000000))):
        rr += [{"trade_id":str(i),"entry_ms":entry,"terminal_ms":terminal} for _ in range(2)]
    for fold in c10.FOLDS:
        train,valid=c10.split_fold(rr,fold)
        assert not ({r["trade_id"] for r in train}&{r["trade_id"] for r in valid})

def test_deterministic_model():
    rr=synthetic_rows();a=fit_logistic(rr,c10.CONTEXT_FEATURES);b=fit_logistic(rr,c10.CONTEXT_FEATURES)
    np.testing.assert_array_equal(a["model"]["coef"],b["model"]["coef"])

@pytest.mark.parametrize("path",["data/2026/x","metadata_2026.json",Path("sealed/2026Q1")])
def test_no_2026_access(path):
    with pytest.raises(PermissionError):reject_2026(path)
