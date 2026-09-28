from pathlib import Path

import numpy as np
import pytest

from binance_data_foundation import c10_post_t2 as c10
from binance_data_foundation.c11_dynamic_post_t2 import (
    CONTRACT_SHA256, binary_rows, fit_model, inner_predictions, predict_model,
    reconciliation, reject_2026,
)


def rows(labels, states=(1, 2, 3)):
    out = []
    for i, label in enumerate(labels):
        for j in range(states[i % len(states)]):
            features = {x: float(i + j / 10 + k / 100) for k, x in enumerate(c10.CONTEXT_FEATURES + c10.FAST_FEATURES)}
            out.append({"trade_id": f"t{i}", "symbol": c10.SYMBOLS[i % len(c10.SYMBOLS)], "year": 2024,
                "entry_ms": 1704067200000 + i * 100000, "t0_ms": 1704067200000 + i * 100000 + 60000,
                "state_ms": 1704067200000 + i * 100000 + 120000, "terminal_ms": 1704067200000 + i * 100000 + 300000,
                "label": label, "features": features})
    return out


def test_contract_is_frozen(repo_root=Path(__file__).parents[1]):
    import hashlib
    assert hashlib.sha256((repo_root / "contracts/C11_dynamic_post_t2_state_CONTRACT.md").read_bytes()).hexdigest() == CONTRACT_SHA256


def test_exact_source_and_terminal_reconciliation(repo_root=Path(__file__).parents[1]):
    trades = c10.load_c7_population(repo_root)
    assert len(trades) == 845
    assert sum(t["year"] == 2024 for t in trades) == 415
    assert sum(t["year"] == 2025 for t in trades) == 430
    summary = __import__("json").loads((repo_root / "artifacts/c10_post_t2_timescale_adequacy/final_summary.json").read_text())
    assert summary["events"]["counts"] == {"CONTINUATION_FIRST":335,"DETERIORATION_FIRST":508,"P0_FIRST":2}


def test_binary_population_preserves_and_excludes_p0():
    rr = rows([0, 1, 2]); got = binary_rows(rr)
    assert {r["trade_id"] for r in got} == {"t0", "t1"}
    assert [r["label"] for r in got if r["trade_id"] == "t0"] == [1]
    assert set(r["label"] for r in got if r["trade_id"] == "t1") == {0}
    trades = ([{"trade_id":f"c{i}","terminal":"CONTINUATION_FIRST","year":2024} for i in range(335)] +
              [{"trade_id":f"d{i}","terminal":"DETERIORATION_FIRST","year":2025} for i in range(508)] +
              [{"trade_id":f"p{i}","terminal":"P0_FIRST","year":2025} for i in range(2)])
    model_rows = [{"trade_id":t["trade_id"]} for t in trades[:843]]
    rec = reconciliation(trades, model_rows)
    assert rec["source_trades"] == 845 and rec["binary_target_trades"] == 843
    assert rec["terminal_outcomes"]["P0_FIRST"] == 2


def test_per_trade_weighting_and_training_only_scaling():
    rr = binary_rows(rows([0, 1, 0, 1, 0, 1], states=(1,2,4)))
    w = c10.trade_weights(rr)
    assert all(sum(x for x,r in zip(w,rr) if r["trade_id"] == tid) == pytest.approx(1) for tid in {r["trade_id"] for r in rr})
    model = fit_model(rr)
    before = model["scaler"].copy(); valid = [{**rr[0], "features": rr[0]["features"] | {c10.FAST_FEATURES[0]:1e12}}]
    predict_model(model, valid)
    assert model["scaler"] == before


def test_binary_logistic_and_calibration_are_deterministic():
    rr = binary_rows(rows([0,1] * 12))
    a, b = fit_model(rr), fit_model(rr)
    np.testing.assert_array_equal(a["fit"]["coef"], b["fit"]["coef"])
    np.testing.assert_array_equal(predict_model(a,rr), predict_model(b,rr))


@pytest.mark.parametrize("path", ["data/2026/x", "metadata_2026.json", Path("sealed/2026Q1")])
def test_no_2026_access(path):
    with pytest.raises(PermissionError): reject_2026(path)


def test_c10_geometry_completed_bars_leakage_terminal_and_folds_are_reused():
    assert c10.ARCHITECTURES["A"] == (5,1)
    assert c10.freeze_geometry.__module__.endswith("c10_post_t2")
    assert c10.feature_row.__module__.endswith("c10_post_t2")
    assert c10.snapshots.__module__.endswith("c10_post_t2")
    assert c10.split_fold.__module__.endswith("c10_post_t2")


def test_inner_calibration_is_strictly_training_only(monkeypatch):
    seen = []
    def fake_fit(train, names=None):
        seen.append(max(r["entry_ms"] for r in train)); return object()
    def fake_predict(model, valid): return np.full(len(valid), .5)
    monkeypatch.setattr("binance_data_foundation.c11_dynamic_post_t2.fit_model", fake_fit)
    monkeypatch.setattr("binance_data_foundation.c11_dynamic_post_t2.predict_model", fake_predict)
    rr=[]
    for i,(entry,terminal) in enumerate(((1705000000000,1706000000000),(1713000000000,1714000000000),(1721000000000,1722000000000))):
        rr.append({"trade_id":str(i),"label":i%2,"entry_ms":entry,"terminal_ms":terminal})
    _,_,definitions=inner_predictions(rr, c10.FOLDS["fold_B"][2])
    assert definitions
    assert all(d["train_bounds_ms"][1] <= d["score_bounds_ms"][0] for d in definitions)
