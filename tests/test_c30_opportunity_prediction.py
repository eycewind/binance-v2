from pathlib import Path
import inspect

import numpy as np
import pytest

from binance_data_foundation import c30_opportunity_prediction as c30


def test_contract_population_tasks_schema_and_model_are_frozen():
    assert c30.sha256_file(Path(c30.CONTRACT_REL)) == c30.CONTRACT_SHA256
    assert c30.c29.EXPECTED_ENTRIES == 2199
    assert c30.c29.ENTRY_SHA256 == "6885678a43b0d2f40b34e65adf15247072cdec2bbc8437cafd8cb69d8fba5da3"
    assert c30.TASKS == ("H3_GROSS40", "H3_GROSS50", "H6_GROSS40", "H6_GROSS50",
                           "H12_GROSS40", "H12_GROSS50", "H24_GROSS40", "H24_GROSS50")
    assert len(c30.FEATURES) == 34 and len(set(c30.FEATURES)) == 34
    assert c30.MODEL_SPEC == {"estimator":"LogisticRegression","penalty":"l2","C":1.0,
        "solver":"lbfgs","max_iter":10000,"class_weight":None,"random_state":None,"tol":1e-6}


def test_exact_real_population_features_and_c29_endpoint_labels():
    repo=Path.cwd(); entries,rec,opens=c30.c29._load_and_reconcile(repo)
    assert rec["status"] == "PASS" and len(entries) == 2199
    horizon,coverage=c30.c29.build_rows(entries,opens)
    assert [coverage[f"H{h}"]["valid_executable_trade_count"] for h in c30.c29.HORIZONS] == [2199,2198,2197,2196]
    features,summary=c30.build_feature_rows(entries,c30._hour_states(c30._load_hourly(repo)))
    assert summary["complete_feature_rows"] + summary["excluded_rows"] == 2199
    rows,labels=c30.attach_outcomes(features,horizon)
    assert len(rows) == summary["complete_feature_rows"] and all(x["exact"] for x in labels.values())
    assert all(r["max_source_available_at_ms"] <= r["entry_ms"] and r["max_source_bar_open_ms"] < r["entry_ms"] for r in rows)
    for r in rows:
        if r["symbol"] == "BTCUSDT":
            assert all(r["features"][f"relative_to_btc_return_{h}h"] == 0 for h in (1,3,6,12,24))


def test_endpoint_boundary_is_not_touch_or_mfe_and_cost_accounting():
    assert c30.c29.opportunity_label(.004,.004) and not c30.c29.opportunity_label(.003999999,.004)
    assert c30.c29.opportunity_label(.005,.005) and not c30.c29.opportunity_label(.004999999,.005)
    entry=1_700_000_000_000
    entries=[{"trade_id":"x","symbol":"BTCUSDT","entry_execution_ms":str(entry),"entry_price":"100"}]
    opens={"BTCUSDT":{entry+h*3_600_000:100.4 for h in c30.c29.HORIZONS}}
    rows,_=c30.c29.build_rows(entries,opens)
    # A hypothetical path touch is absent by construction: only the exact endpoint open is supplied.
    assert all(rows[h][0]["labels"] == {"GROSS40":True,"GROSS50":False} for h in c30.c29.HORIZONS)
    assert rows[3][0]["returns"]["C0"] == pytest.approx(.004)
    assert rows[3][0]["returns"]["DESIGN_BNB"] == pytest.approx(c30.c29.cost_outcome(100,100.4,"DESIGN_BNB")["return"])
    assert rows[3][0]["returns"]["C_BASE"] == pytest.approx(c30.c29.cost_outcome(100,100.4,"C_BASE")["return"])


def test_chronology_resolution_baseline_metric_sign_and_groups():
    assert c30.VALIDATION_START_2024 == 1719792000000
    assert c30.VALIDATION_START_2025 == 1735689600000
    y=np.array([0,1,1,0]); p=np.array([.1,.9,.8,.2]); m=c30.metric_values(y,p,.5)
    assert m["delta_brier"] == pytest.approx(m["brier_baseline"]-m["brier_model"])
    assert m["delta_logloss"] == pytest.approx(m["log_loss_baseline"]-m["log_loss_model"])
    train=np.linspace(.01,.99,100); b=c30.probability_boundaries(train)
    assert len(b["cut_points_upper_inclusive_for_lower_group"]) == 4
    tied=np.array([.1]*20+[.2]*20+[.3]*20+[.4]*20+[.5]*20)
    bt=c30.probability_boundaries(tied); groups=c30.assign_groups(tied,bt)
    assert all(len(set(groups[i:i+20])) == 1 for i in range(0,100,20))


def test_feature_arithmetic_cross_asset_completed_only():
    states={s:{100:{"returns":{1:.01,3:.02,6:-.01,12:.03,24:.04},"volatility":{6:.1,12:.2,24:.3},
        "close_over_sma24":.01,"sma24_slope":.001,"previous_close_over_sma24":-.01,"geometry_change":.02,
        "source_open_ms":0,"available_at_ms":100}} for s in c30.SYMBOLS}
    states["BTCUSDT"][100]["returns"]={1:.005,3:.01,6:.02,12:.00,24:-.01}
    entry={"trade_id":"x","symbol":"ETHUSDT","entry_execution_ms":"100"}
    rows,summary=c30.build_feature_rows([entry],states); f=rows[0]["features"]
    assert summary["excluded_rows"] == 0
    assert f["relative_to_btc_return_1h"] == pytest.approx(.005)
    assert f["relative_to_btc_return_6h"] == pytest.approx(-.03)
    assert f["universe_positive_return_fraction_6h"] == pytest.approx(.2)
    assert f["universe_mean_return_1h"] == pytest.approx(.009)


def test_economic_groups_include_failures_and_bootstrap_is_frozen_deterministic(monkeypatch):
    rr=[]
    for i in range(25):
        rr.append({"trade_id":str(i),"symbol":c30.SYMBOLS[i%5],"entry_ms":i,"entry_month":f"2024-{1+i//5:02d}",
            "label":int(i%3==0),"probability":.02+i/30,"baseline":.3,"group":f"P{1+i//5}",
            "returns":{"C0":(i-12)/1000,"DESIGN_BNB":(i-14)/1000,"C_BASE":(i-15)/1000}})
    predictions={t:{2024:list(rr),2025:[dict(r,entry_month=r["entry_month"].replace("2024","2025")) for r in rr]} for t in c30.TASKS}
    e0,eb,ec,ordering=c30.economic_documents(predictions)
    assert sum(e0["H3_GROSS40"]["2024"][g]["trade_count"] for g in ("P1","P2","P3","P4","P5")) == 25
    assert sum(e0["H3_GROSS40"]["2024"][g]["opportunity_positive_count"] for g in ("P1","P2","P3","P4","P5")) < 25
    monkeypatch.setattr(c30,"REPLICATES",20)
    a,ea=c30.bootstrap_documents(predictions,"whole_trade"); b,eboot=c30.bootstrap_documents(predictions,"whole_trade")
    assert a == b and ea == eboot and not a["model_refit"]


def test_no_search_cutoff_strategy_mfe_or_post_2025_access():
    with pytest.raises(PermissionError): c30.reject_prohibited_path("data/2026-01/file.csv")
    source=inspect.getsource(c30)
    assert "GridSearch" not in source and "RandomizedSearch" not in source
    assert "take_profit" not in source and "stop_loss" not in source
    assert '"MFE_used":False' in source
    assert '"no_PnL_optimization":True' in source
    assert '"C31_started":False' in source
