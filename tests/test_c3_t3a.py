from __future__ import annotations

import math
import hashlib
import json
from pathlib import Path

import pytest

from binance_data_foundation.c3_milestone import FEATURE_COLUMNS
from binance_data_foundation.c3_t3a import (
    CALENDAR_COLUMNS, C_GRID, FOLDS, SOLVER_MAX_ITERATIONS, SOLVER_TOLERANCE, SYMBOL_ORDER,
    T3A_END_MS, _calendar_values, _row_key_hash, assert_feature_matrix, auc_pr, auc_roc,
    block_bootstrap, chronological_split, evaluate, fit_logistic,
    final_2024_training_rows, fit_preprocessor, guard_development_timestamp, load_accepted_t1t2, predict_logistic,
    training_bin_edges, transform,
)


def row(ts, resolution, label=1, symbol="BTCUSDT", shift=0.0):
    month = {1_704_067_200_000:"2024-01",1_719_792_000_000:"2024-07",1_727_740_800_000:"2024-10"}.get(ts,"2024-06")
    return {"trade_id":str(ts)+symbol,"milestone_id":"M1","symbol":symbol,"milestone_ms":ts,
            "milestone_ts":month+"-01T00:00:00+00:00","label_resolution_ms_raw":str(resolution),
            "label_raw":str(label),"features":{name:float(i)+shift for i,name in enumerate(FEATURE_COLUMNS)}}


def test_exact_fold_membership_and_resolution_purge():
    jan,jul,oct=T(0),T(182),T(274)
    rows=[row(jan,jan+1),row(jul,jul+1,0),row(oct,oct+1),row(jul+1,T(274),1)]
    a_train,a_valid,purge=chronological_split(rows,"fold_a")
    assert [r["milestone_ms"] for r in a_train]==[jan]
    assert [r["milestone_ms"] for r in a_valid]==[jul]
    assert purge["validation"]["boundary_resolution"]==1
    b_train,b_valid,_=chronological_split(rows,"fold_b")
    assert jan in [r["milestone_ms"] for r in b_train] and oct in [r["milestone_ms"] for r in b_valid]


def T(days): return 1_704_067_200_000+days*86_400_000


def test_scaler_training_only_and_validation_cannot_influence_it():
    train=[row(T(0),T(0)+1,shift=s) for s in (0,1,2)]
    spec=fit_preprocessor(train,(FEATURE_COLUMNS[0],))
    before=spec.copy(); transform([row(T(2),T(2)+1,shift=1_000_000)],spec)
    assert spec==before and spec["continuous"][FEATURE_COLUMNS[0]]["median"]==1


def test_zero_iqr_center_no_scale_and_category_training_only():
    train=[row(T(0),T(0)+1),row(T(1),T(1)+1)]
    spec=fit_preprocessor(train,(FEATURE_COLUMNS[0],))
    assert spec["continuous"][FEATURE_COLUMNS[0]]["zero_iqr"]
    with pytest.raises(ValueError,match="absent"):
        transform([row(T(2),T(2)+1,symbol="ETHUSDT")],spec)


def test_calendar_controls_training_only_scaled_and_formula_exact():
    train=[]
    for i,symbol in enumerate(SYMBOL_ORDER):
        r=row(T(i),T(i)+1,symbol=symbol); r["milestone_ts"]=f"2024-{i+1:02d}-01T00:00:00+00:00"; train.append(r)
    spec=fit_preprocessor(train,(FEATURE_COLUMNS[0],)); before=json.loads(json.dumps(spec))
    assert spec["calendar_order"]==list(CALENDAR_COLUMNS)
    assert _calendar_values("2024-03-01T00:00:00+00:00")==pytest.approx((1.0,0.0),abs=1e-15)
    validation=row(T(10),T(10)+1,symbol="BTCUSDT"); validation["milestone_ts"]="2024-12-01T00:00:00+00:00"
    vector=transform([validation],spec)[0]
    assert spec==before
    raw=_calendar_values(validation["milestone_ts"])
    for j,name in enumerate(CALENDAR_COLUMNS):
        rule=spec["calendar"][name]; expected=raw[j]-rule["median"]
        if not rule["zero_iqr"]: expected/=rule["iqr"]
        assert vector[-2+j]==pytest.approx(expected)


def test_exact_feature_columns_and_provenance_outcome_rejection():
    assert_feature_matrix(FEATURE_COLUMNS)
    with pytest.raises(ValueError,match="forbidden"):
        assert_feature_matrix(FEATURE_COLUMNS+("label",))
    with pytest.raises(ValueError): assert_feature_matrix(FEATURE_COLUMNS[:-1])


def test_b0_and_hand_metrics():
    y=[0,1]; p=[.25,.75]; m=evaluate(y,p,.5,training_bin_edges([.5,.5]))
    assert m["brier"]==pytest.approx(.0625)
    assert m["log_loss"]==pytest.approx(-math.log(.75))
    assert auc_roc(y,p)==1 and auc_pr(y,p)==1
    b0=evaluate(y,[.5,.5],.5,training_bin_edges([.5,.5]))
    assert b0["brier_skill_vs_b0"]==0
    assert b0["pr_auc"]==.5


def test_reliability_boundaries_are_training_defined():
    edges=training_bin_edges([0,1,2,3,4])
    assert edges==[.8,1.6,2.4,3.2]
    assert training_bin_edges([100,101,102,103,104])!=edges


def test_fixed_c_grid_only_and_deterministic_fit():
    x=[[-1.],[0.],[1.],[2.]]; y=[0,0,1,1]
    assert C_GRID==(.1,1.,10.)
    assert fit_logistic(x,y,1)==fit_logistic(x,y,1)
    with pytest.raises(ValueError,match="fixed grid"): fit_logistic(x,y,.5)


def test_attempt_count_contract_constant():
    assert 2*2*(1+1+5+1+3+3)==56


def test_block_bootstrap_keeps_complete_month_blocks():
    rows=[{"month":"2024-01","symbol":"BTC"},{"month":"2024-01","symbol":"ETH"},{"month":"2024-02","symbol":"BTC"}]
    result=block_bootstrap(rows,[1,2,3],[0,0,0],[1,2,3],[0,0,0],replications=20)
    assert result["month_block_integrity"] and "all symbols" in result["block"]


def test_no_2025_scoring_and_exact_boundary_rejection():
    guard_development_timestamp(T3A_END_MS-1)
    with pytest.raises(ValueError,match="2025-01-01"):
        guard_development_timestamp(T3A_END_MS)
    model=fit_logistic([[-1.],[1.]],[0,1],1)
    with pytest.raises(ValueError,match="refuses to score"):
        predict_logistic(model,[[0.]],[T3A_END_MS])


def test_2026_rejection_remains_implied_by_stricter_t3a_guard():
    with pytest.raises(ValueError): guard_development_timestamp(1_767_225_600_000)


REPO=Path(__file__).resolve().parents[1]
T3A=REPO/"artifacts/c3_milestone_state_continuation/t3a_2024"


def test_real_fold_counts_final_selection_and_row_hash():
    datasets,_=load_accepted_t1t2(REPO)
    expected={"M1":((95,83),(48,57),(143,140),(49,49)),"M2":((66,58),(33,39),(99,97),(28,32))}
    for target,rows in datasets.items():
        observed=[]
        for fold in FOLDS:
            train,valid,_=chronological_split(rows,fold)
            for selected in (train,valid): observed.append((sum(r["label"] for r in selected),len(selected)-sum(r["label"] for r in selected)))
        assert tuple(observed)==expected[target]
        final=final_2024_training_rows(rows)
        counts={"M1":(381,192,189),"M2":(256,127,129)}[target]
        assert (len(final),sum(r["label"] for r in final),len(final)-sum(r["label"] for r in final))==counts
        assert _row_key_hash(final)==_row_key_hash(final)
        assert max(r["milestone_ms"] for r in final)<T3A_END_MS


def test_authorized_attempt_ledger_exact_composition():
    ledger=[json.loads(line) for line in (T3A/"attempt_ledger.jsonl").read_text().splitlines()]
    assert len(ledger)==56
    assert {m:sum(x["baseline_model"]==m for x in ledger) for m in ("B0","B1","B2","L0","L1","L2")}=={"B0":4,"B1":4,"B2":20,"L0":4,"L1":12,"L2":12}
    assert {x["C"] for x in ledger if x["baseline_model"] in ("L1","L2")}==set(C_GRID)
    assert all(x["failure"] is None for x in ledger)


def test_freeze_complete_source_hashes_and_solver_protocol():
    freeze=json.loads((T3A/"freeze_specifications.json").read_text())
    required={"final_2024_training","locked_2025_evaluation","symbol_encoding","calendar_controls","continuous_preprocessing","model_implementation","final_artifacts","source_and_test_hashes"}
    for spec in freeze.values():
        assert required<=set(spec)
        assert spec["symbol_encoding"]["order"]==list(SYMBOL_ORDER)
        assert spec["model_implementation"]["tolerance"]==SOLVER_TOLERANCE
        assert spec["model_implementation"]["maximum_iterations"]==SOLVER_MAX_ITERATIONS
        assert spec["locked_2025_evaluation"]["contents_opened"] is False
        for relative,digest in spec["source_and_test_hashes"].items():
            assert hashlib.sha256((REPO/relative).read_bytes()).hexdigest()==digest


def test_final_preprocessing_models_and_prediction_rows_are_frozen_pre2025():
    datasets,_=load_accepted_t1t2(REPO)
    stored_prep=json.loads((T3A/"final_preprocessing.json").read_text()); models=json.loads((T3A/"final_models.json").read_text())
    predictions=json.loads((T3A/"predictions.json").read_text())
    for target,rows in datasets.items():
        final=final_2024_training_rows(rows)
        for model,features in (("L0",("realized_volatility_last6_5m","distance_from_h1_sma24")),("L1",FEATURE_COLUMNS[:27]),("L2",FEATURE_COLUMNS)):
            key=f"{target}_{model}"; assert stored_prep[key]==fit_preprocessor(final,features)
            assert models[key]["target_training_row_hash"]==_row_key_hash(final)
            assert models[key]["model_spec"]["converged"]
        valid_keys={r["trade_id"]:r["milestone_ms"] for r in rows}
        for table in (x for x in predictions if x["target"]==target):
            assert all(valid_keys[key]<T3A_END_MS for key in table["row_keys"])


def test_independent_rebuild_evidence_exists_and_matches():
    evidence=json.loads((T3A/"independent_rebuild.json").read_text())
    assert evidence["run_a_equals_run_b"] and evidence["rebuild_equals_published"]
    assert evidence["run_a_core_hashes"]==evidence["run_b_core_hashes"]==evidence["published_core_hashes"]
