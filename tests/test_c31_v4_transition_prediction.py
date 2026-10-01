from pathlib import Path
import inspect
import numpy as np
import pytest
from binance_data_foundation import c31_v4_transition_prediction as c31

def test_frozen_contract_schema_model_and_hashes():
    assert c31.sha256_file(Path(c31.CONTRACT_REL)) == c31.CONTRACT_SHA256
    assert c31.FEATURES == ("NEW_JOINER_FRACTION","BASKET_ACCELERATION","PRIOR_RELATIVE_DEFICIT","RELATIVE_IMPROVEMENT","DISPERSION_CHANGE","MARKET_EXPANSION_STATE_AT_E1","MARKET_EXPANSION_CURRENT_RUN_LENGTH","CATCHUP_STATE_AT_E1","CATCHUP_CURRENT_RUN_LENGTH")
    assert c31.MODEL_SPEC == {"estimator":"LogisticRegression","penalty":"l2","C":1.0,"solver":"lbfgs","max_iter":10000,"class_weight":None,"random_state":None,"tol":1e-6}
    assert c31.REPLICATES == 2000

def test_population_labels_coverage_v4_and_folds_exact():
    repo=Path.cwd(); entries,pop,opens=c31.c29._load_and_reconcile(repo)
    assert pop["original_trade_count"] == 2199 and pop["year_counts"] == {"2024":1093,"2025":1106}
    assert pop["symbol_counts"] == {"BNBUSDT":442,"BTCUSDT":451,"ETHUSDT":434,"SOLUSDT":431,"XRPUSDT":441}
    horizon,cov=c31.c29.build_rows(entries,opens)
    assert [cov[f"H{h}"]["valid_executable_trade_count"] for h in c31.c29.HORIZONS] == [2199,2198,2197,2196]
    hours,_=c31.vbase.load_hourly_market(repo); rows=c31.build_v4_rows(entries,hours)
    assert len(rows)==2199 and tuple(rows[0]["features"])==c31.FEATURES
    rows,labels=c31.c30.attach_outcomes(rows,horizon); assert all(x["exact"] for x in labels.values())
    folds,reports=c31.c30.make_folds(rows)
    assert all(max(r["tasks"][t]["resolution_ms"] for r in folds[t][y][0]) < (c31.c30.VALIDATION_START_2024 if y==2024 else c31.c30.VALIDATION_START_2025) for t in c31.TASKS for y in (2024,2025))

def test_scores_calibration_scaling_and_pcg64_are_deterministic():
    assert c31._loss([0,1],[.2,.8]) == pytest.approx((.04,-np.log(.8)))
    s=c31.c30.StandardScaler().fit([[1,2],[3,4]]); assert np.allclose(s.mean_,[2,3])
    cal=c31.c30._calibration(np.array([0,0,1,1]),np.array([.1,.2,.8,.9])); assert "calibration_slope" in cal and "ece_10_equal_width_bins" in cal
    a=np.random.Generator(np.random.PCG64(c31.SEED)).integers(10,size=20); b=np.random.Generator(np.random.PCG64(c31.SEED)).integers(10,size=20); assert np.array_equal(a,b)

def test_no_policy_search_pnl_or_2026_access_paths():
    with pytest.raises(PermissionError): c31.c30.reject_prohibited_path("market/2026/file")
    source=inspect.getsource(c31)
    assert "GridSearch" not in source and "RandomizedSearch" not in source
    assert "prediction_driven_PnL\":True" in source
