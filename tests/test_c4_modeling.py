from __future__ import annotations
import csv, hashlib, json, math
from pathlib import Path
import numpy as np
import pytest

from binance_data_foundation.c4_modeling import (
    CLASSES, FOLDS, G1_EXTRA, P1_EXTRA, _pre_value_2024, b0_probabilities,
    feature_manifest, fit_preprocessing, load_accepted_2024_rows, matrix,
    proper_scores, trade_weights, weighted_quantile,
)

REPO=Path(__file__).resolve().parents[1]
ART=REPO/'artifacts/c4_sequential_exit_state'

def rows():
    return [
        {'row_id':'b','trade_id':'a','symbol':'BTCUSDT','event_class':'continuation'},
        {'row_id':'a','trade_id':'a','symbol':'BTCUSDT','event_class':'adverse_reversal'},
        {'row_id':'c','trade_id':'b','symbol':'ETHUSDT','event_class':'no_event_60m'},
    ]

def test_exact_nested_manifests_and_family_roles():
    for target in ('T1','T2'):
        m=feature_manifest(target)
        assert m['strict_nesting'] and set(m['G0']) < set(m['G1']) < set(m['P1'])
        assert all(m['families'][x]=='genuine path history' for x in P1_EXTRA)
        assert all(m['families'][x]=='geometry/current state' for x in G1_EXTRA[target])
    assert 't1_upper_distance_assertion' not in feature_manifest('T1')['P1']
    assert 't1_lower_distance_assertion' not in feature_manifest('T1')['P1']
    assert {'t2_upper_distance','t2_lower_distance'} <= set(feature_manifest('T2')['G1'])
    assert 'running_mfe' not in feature_manifest('T1')['P1']

def test_equal_trade_weights_and_weighted_b0():
    r=rows(); w=trade_weights(r)
    assert np.allclose(w,[.5,.5,1])
    assert sum(w[:2])==pytest.approx(1) and w[2]==1
    assert np.allclose(b0_probabilities(r,'T1',w),[.25,.25,.5])

def test_weighted_ecdf_tie_break_and_preprocessing_zero_iqr():
    assert weighted_quantile([5,1,1],[1,1,1],['c','b','a'],.5)==1
    r=rows(); f={x['row_id']:{'v':1.,'z':float(i)} for i,x in enumerate(r)}; w=trade_weights(r)
    prep,kept=fit_preprocessing(r,f,['v','z'],w)
    assert prep['v']['excluded_zero_iqr'] and 'v' not in kept
    assert prep['z']['median']==1 and prep['z']['iqr']==2

def test_proper_scores_use_supplied_equal_trade_weights():
    r=rows(); w=trade_weights(r); p=np.array([[.8,.1,.1],[.2,.7,.1],[.1,.1,.8]])
    got=proper_scores(r,p,'T1',w)
    y=np.array([0,1,2]); wn=w/w.sum()
    assert got['trade_weighted_log_loss']==pytest.approx(np.sum(wn*-np.log(p[np.arange(3),y])))

def test_2024_seal_rejects_before_feature_use():
    with pytest.raises(ValueError): _pre_value_2024({'entry_execution_ms':'1735689600000','snapshot_ms':'not-a-number'})
    with pytest.raises(ValueError): _pre_value_2024({'entry_execution_ms':'1767225600000','snapshot_ms':'not-a-number'})

def test_fold_boundaries_and_no_trade_crossing_contract():
    assert FOLDS['fold_A']==(1704067200000,1719792000000,1727740800000)
    assert FOLDS['fold_B']==(1704067200000,1727740800000,1735689600000)
    entries={'x':1710000000000,'y':1720000000000,'z':1730000000000}
    for _,(_,v,e) in FOLDS.items():
        train={t for t,x in entries.items() if x<v}; valid={t for t,x in entries.items() if v<=x<e}
        assert not train&valid

def test_freeze_is_complete_and_has_no_later_scoring():
    freeze=json.loads((ART/'c4_2024_freeze.json').read_text())
    for key in ('contract_sha256','adequacy_decision_sha256','threshold_panel_sha256','bootstrap_structure_sha256','populations','row_trade_ids','feature_schema_sha256','preprocessing_sha256','models_sha256','solver','interpretation','seals'):
        assert key in freeze
    assert freeze['seals']=={'2025_predictive_scoring':'NOT PERFORMED','2026_access':False,'economic_or_stage_B_analysis':False}
    assert not (ART/'predictions_2025.csv').exists()
    assert not (ART/'development_metrics_2025.csv').exists()

def test_production_population_and_prediction_rows_are_2024_only():
    predictions=list(csv.DictReader((ART/'development_predictions_2024.csv').open()))
    assert predictions and {r['target'] for r in predictions}=={'T1','T2'}
    assert {r['fold'] for r in predictions}=={'fold_A','fold_B'}
    population=json.loads((ART/'modeling_population_2024.json').read_text())
    for target in ('T1','T2'):
        assert population[target]['complete_case_rows']>0
        assert len(population[target]['row_ids'])==population[target]['complete_case_rows']
        assert len(set(population[target]['row_ids']))==population[target]['complete_case_rows']

def test_accepted_bootstrap_configuration_and_output_determinism_fields():
    detail=json.loads((ART/'local/bootstrap_structure_details.json').read_text())
    assert detail['configuration_hash']=='0a679d60427561b662059f289249d7151aad9e53c97e1ceec669e2353233d923'
    comparisons=json.loads((ART/'bootstrap_comparisons_2024.json').read_text())
    for fold in ('T1_fold_A','T1_fold_B','T2_fold_A','T2_fold_B'):
        for comparison in ('G1-G0','P1-G1'):
            for metric in ('log_loss','brier'):
                x=comparisons[fold][comparison][metric]
                assert len(x['replicates'])==2000 and len(x['ci95'])==2
                assert x['sign_convention'].startswith('first_minus_second')

def test_calibration_support_gates_are_frozen():
    calibration=json.loads((ART/'calibration_2024.json').read_text())
    for fold in calibration.values():
        for cls in fold.values():
            assert cls['intercept_slope_supported']==(cls['unique_event_trades']>=50)
            for b in cls['bins']:
                assert b['supported']==(b['unique_resolved_trades']>=30)
                assert b['unstable']==(b['unique_event_trades']<10)

def test_source_has_no_random_row_split_or_alternative_model_family():
    source=(REPO/'src/binance_data_foundation/c4_modeling.py').read_text()
    assert 'train_test_split' not in source and 'RandomForest' not in source and 'GradientBoost' not in source
    assert '2025_predictive_scoring":"NOT PERFORMED"' in source
