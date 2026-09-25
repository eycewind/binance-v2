from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

import numpy as np
import pytest

from binance_data_foundation import c4_modeling
from binance_data_foundation.c4_locked_eval import load_locked_checkpoint, predict_feature_rows


def _write(path, value):
    path.write_text(json.dumps(value,sort_keys=True),encoding='utf-8')


def _checkpoint(tmp_path, source_hash=None):
    repo=tmp_path/'repo'; art=tmp_path/'art'; repo.mkdir(parents=True); art.mkdir(parents=True)
    source=repo/'source.py'; source.write_text('accepted\n')
    columns={'G0':['x'],'G1':['x'],'P1':['x']}
    schema={'targets':{'T1':columns,'T2':columns}}
    prep={f'{t}_{m}':{'columns':['x'],'parameters':{'x':{'median':0.,'iqr':2.,'excluded_zero_iqr':False}}} for t in ('T1','T2') for m in ('G0','G1','P1')}
    fit={'C':1.,'columns':['x'],'coefficients':[[0.,0.],[1.,-1.]],'converged':True}
    models={t:{'models':{'B0':{'probabilities':[.2,.3,.5]},'G0':fit,'G1':fit,'P1':fit}} for t in ('T1','T2')}
    snapshot={'target_definition_versions':{'T1':'C4_T1_CONT_PLUS1_VS_REV_MINUS075_H60_V1','T2':'C4_T2_GIVEBACK50_VS_NEWPEAK050_H60_V1'}}
    for name,obj in [('feature_schema.json',schema),('final_preprocessing_2024.json',prep),('final_models_2024.json',models),('snapshot_schema.json',snapshot)]: _write(art/name,obj)
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    material={n:sha(art/n) for n in ('feature_schema.json','final_preprocessing_2024.json','final_models_2024.json','snapshot_schema.json')}
    freeze={'version':'C4_2024_FREEZE_V2','seals':{'2025_predictive_scoring':'NOT PERFORMED','2026_access':False,'economic_or_stage_B_analysis':False},
        'material_artifact_hashes':material,'source_test_hashes':{'source.py':source_hash or sha(source)},
        'environment':{'conda_env':os.environ.get('CONDA_DEFAULT_ENV'),'python_version':sys.version.split()[0],'numpy_version':np.__version__},
        'target_definitions':snapshot['target_definition_versions'],'class_order':{'T1':['a','b','c'],'T2':['d','e','f']}}
    _write(art/'c4_2024_freeze.json',freeze); (art/'c4_2024_freeze.sha256').write_text(sha(art/'c4_2024_freeze.json')+'  c4_2024_freeze.json\n')
    return repo,art


def test_locked_prediction_has_no_fit_selection_or_calibration_path(tmp_path,monkeypatch):
    repo,art=_checkpoint(tmp_path); checkpoint=load_locked_checkpoint(repo,art)
    for name in ('fit_multinomial','fit_preprocessing','run'):
        monkeypatch.setattr(c4_modeling,name,lambda *a,**k:pytest.fail('development path invoked'))
    row={'entry_execution_ms':1735689600000,'snapshot_ms':1735689900000,'row_id':'r','symbol':'BTCUSDT','features':{'x':2.}}
    got=predict_feature_rows(checkpoint,'T1','P1',[row])
    assert got[0]['row_id']=='r' and sum(got[0][f'p_{c}'] for c in ('a','b','c'))==pytest.approx(1)


def test_locked_checkpoint_refuses_missing_and_hash_mismatch(tmp_path):
    with pytest.raises(RuntimeError,match='missing'): load_locked_checkpoint(tmp_path,tmp_path)
    repo,art=_checkpoint(tmp_path/'x'); (art/'feature_schema.json').write_text('{}')
    with pytest.raises(RuntimeError,match='material artifact mismatch'): load_locked_checkpoint(repo,art)


def test_locked_checkpoint_refuses_source_mismatch(tmp_path):
    repo,art=_checkpoint(tmp_path,source_hash='0'*64)
    with pytest.raises(RuntimeError,match='source provenance mismatch'): load_locked_checkpoint(repo,art)


def test_2026_is_rejected_before_feature_values_are_consumed(tmp_path):
    repo,art=_checkpoint(tmp_path); checkpoint=load_locked_checkpoint(repo,art)
    class Bomb(dict):
        def __getitem__(self,key): raise AssertionError('feature consumed before boundary rejection')
    row={'entry_execution_ms':1767225600000,'snapshot_ms':1767225600000,'row_id':'x','symbol':'BTCUSDT','features':Bomb()}
    with pytest.raises(ValueError,match='2025 entries only'): predict_feature_rows(checkpoint,'T1','P1',[row])


def test_exact_frozen_column_and_class_order(tmp_path):
    repo,art=_checkpoint(tmp_path); checkpoint=load_locked_checkpoint(repo,art)
    assert checkpoint.preprocessing['T2_P1']['columns']==['x']
    assert checkpoint.freeze['class_order']['T2']==['d','e','f']
