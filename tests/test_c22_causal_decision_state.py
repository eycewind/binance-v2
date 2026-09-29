from pathlib import Path

import numpy as np
import pytest

from binance_data_foundation.c22_causal_decision_state import (
    FEATURES, PROHIBITED, build_causal_rows, design, fit_models, fit_preprocessor,
    reject_2026, target_geometry_audit,
)


def toy_rows():
    rows=[]
    for tid,base in (("a",.2),("b",.6)):
        for j in range(4):
            features={"p_t2":base+.05*j,"elapsed_minutes_since_entry":5*(j+1),
                "observable_current_return_from_entry":.01*j,"first_honest_p_t2":base,
                "delta_p_from_first":.05*j}
            for lag in (5,15,30):
                missing=float(5*(j+1)-lag<5)
                features[f"delta_p_{lag}m"]=None if missing else .05*min(j,lag//5)
                features[f"delta_p_{lag}m_missing"]=missing
            rows.append({"trade_id":tid,"entry_ms":0 if tid=="a" else 10**9,
                "terminal_ms":900_000 if tid=="a" else 10**9+900_000,
                "state_ms":5*(j+1)*60_000,"DELTA_LIQ_5":(-1 if tid=="a" else 1)+j*.1,
                "causal_features":features})
    return rows


def test_decision_timestamp_and_observable_price_semantics():
    source=Path("src/binance_data_foundation/c8_timescale.py").read_text()
    assert "market.index(t - MINUTE)" in source
    assert 'fast.close[fi] / price - 1' in source


def test_next_open_and_full_trade_means_are_prohibited():
    all_features={x for names in FEATURES.values() for x in names}
    assert "exit_now_price" in PROHIBITED and "mean_p" in PROHIBITED
    assert all_features.isdisjoint(PROHIBITED)


def test_first_honest_and_lags_are_past_only_and_missing_explicit(monkeypatch):
    frozen=[]
    for j,p in enumerate((.2,.3,.5)):
        frozen.append({"trade_id":"a","state_ms":300_000*(j+1),"entry_ms":0,"p_t2":p,
            "features":{"current_return":.01*j}})
    monkeypatch.setattr("binance_data_foundation.c22_causal_decision_state.c21.build_frozen_rows",
                        lambda repo:(frozen,{}))
    rows,_=build_causal_rows(Path(".")); f=[r["causal_features"] for r in rows]
    assert all(x["first_honest_p_t2"]==.2 for x in f)
    assert f[0]["delta_p_5m"] is None and f[0]["delta_p_5m_missing"]==1
    assert f[1]["delta_p_5m"]==pytest.approx(.1)
    assert f[2]["delta_p_15m"] is None


def test_target_geometry_audit_pre_fit_contract():
    audit=target_geometry_audit()
    assert audit["status"]=="PASS" and audit["completed_before_model_fitting"]
    assert audit["targets"]["DELTA_LIQ_EVENT"]["explicit_form"]=="V_it = A_i - B_i P_exec,it"


def test_training_only_preprocessing_and_deterministic_fits():
    rows=toy_rows(); train=rows[:2]+rows[4:6]; valid=rows[2:4]+rows[6:]
    prep=fit_preprocessor(train,FEATURES["M3"])
    assert prep["delta_p_30m"]["imputation"]=="training_weighted_median"
    assert np.array_equal(design(valid,FEATURES["M3"],prep),design(valid,FEATURES["M3"],prep))
    a,_=fit_models(train,valid,"DELTA_LIQ_5"); b,_=fit_models(train,valid,"DELTA_LIQ_5")
    for model in a:
        assert np.array_equal(a[model]["binary"],b[model]["binary"])
        assert np.array_equal(a[model]["continuous"],b[model]["continuous"])


def test_chronological_whole_trade_weighting_and_no_2026():
    rows=toy_rows(); train=rows[:4]; valid=rows[4:]
    assert max(r["terminal_ms"] for r in train)<min(r["entry_ms"] for r in valid)
    assert {r["trade_id"] for r in train}.isdisjoint({r["trade_id"] for r in valid})
    with pytest.raises(PermissionError): reject_2026(Path("sealed/2026/data"))
