import json
import csv
import tempfile
from pathlib import Path
import pytest
from binance_data_foundation.c3_t3b import (END_2025_MS, START_2025_MS, T3A_DIR,
    _read_locked_rows, apply_frozen_preprocessor, run_t3b, score_frozen, verify_freeze)

REPO=Path(__file__).resolve().parents[1]

def test_exact_locked_temporal_selection_and_strict_resolution_boundary():
    for target in ("M1","M2"):
        rows,_,_= _read_locked_rows(REPO,target)
        assert rows and all(START_2025_MS <= r["milestone_ms"] < END_2025_MS for r in rows)

def test_frozen_artifacts_hashes_choices_and_feature_order():
    f=verify_freeze(REPO)
    for target in ("M1","M2"):
        assert f["freeze"][target]["selected_L1_C"] == f["freeze"][target]["selected_L2_C"] == .1
        assert f["freeze"][target]["L0"]["C"] == 1.

def test_frozen_symbol_calendar_encoding_and_2026_rejection():
    f=verify_freeze(REPO); prep=f["preprocessing"]["M1_L0"]
    row={"milestone_ms":END_2025_MS,"milestone_ts":"2026-01-01T00:00:00Z","symbol":"BTCUSDT","features":{"realized_volatility_last6_5m":0.,"distance_from_h1_sma24":0.}}
    with pytest.raises(ValueError,match="2026"): apply_frozen_preprocessor([row],prep)

def test_deterministic_frozen_predictions_and_no_fit_path(monkeypatch):
    f=verify_freeze(REPO); rows,_,_=_read_locked_rows(REPO,"M1"); rows=rows[:3]
    import binance_data_foundation.c3_t3a as t3a
    monkeypatch.setattr(t3a,"fit_logistic",lambda *a,**k: (_ for _ in ()).throw(AssertionError("refit")))
    a=score_frozen(rows,f["preprocessing"]["M1_L1"],f["models"]["M1_L1"])
    b=score_frozen(rows,f["preprocessing"]["M1_L1"],f["models"]["M1_L1"])
    assert a==b

def test_t3b_has_no_model_selection_or_threshold_optimizer():
    source=(REPO/"src/binance_data_foundation/c3_t3b.py").read_text()
    assert "fit_logistic(" not in source and "fit_preprocessor(" not in source
    assert "threshold_optimization" in source and "C_GRID" not in source

def test_generated_predictions_are_lf_only_and_semantically_identical():
    published=REPO/"artifacts/c3_milestone_state_continuation/t3b_2025/predictions.csv"
    with tempfile.TemporaryDirectory(prefix="c3_t3b_lf_test_") as name:
        generated=Path(name); run_t3b(REPO,generated)
        raw=(generated/"predictions.csv").read_bytes()
        assert b"\r" not in raw
        assert raw == published.read_bytes()
        with published.open(newline="",encoding="utf-8") as a, (generated/"predictions.csv").open(newline="",encoding="utf-8") as b:
            assert list(csv.DictReader(a)) == list(csv.DictReader(b))
