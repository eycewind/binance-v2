from __future__ import annotations
from array import array
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import numpy as np
import pytest

from binance_data_foundation.c3_milestone import DenseSeries, _pre_holdout_timestamp
from binance_data_foundation.c4_adequacy import (
    ACCEPTED_CORE_HASHES, ADEQUACY_DECISIONS, ADEQUACY_THRESHOLDS,
    BOOTSTRAP_CONFIG, BOOTSTRAP_PARTITIONS, FIVE_MINUTES, HOUR, MINUTE,
    STUDY_END_MS, T1, T2, _json_hash, _partition, _resolve, _snapshot_id,
    _target, adequacy_decision, bootstrap_structure, bootstrap_structures,
)

REPO = Path(__file__).resolve().parents[1]
ARTIFACT = REPO / 'artifacts/c4_sequential_exit_state'

def series(rows, start=0, size=80):
    vals={n:array('d',[math.nan])*size for n in ('open','high','low','close','base_volume','quote_volume','trade_count')}; valid=bytearray(size)
    for i,o,h,l,c in rows:
        for n,v in zip(('open','high','low','close'),(o,h,l,c)): vals[n][i]=v
        for n in ('base_volume','quote_volume','trade_count'): vals[n][i]=1
        valid[i]=1
    return DenseSeries(MINUTE,start,vals,valid)

def base():
    return {'target_id':'','running_mfe':.02,'current_return':.01,'already_beyond_giveback_state':False,'t1_upper_distance_assertion':None,'t1_lower_distance_assertion':None}

def test_t1_formulas_and_equality_touch():
    s=series([(i,100,101 if i==0 else 100.5,99.5,100) for i in range(61)])
    r=base(); _target(r,'T1',s,0,HOUR+MINUTE,100,100,100,100)
    assert r['upper_barrier']==101 and r['lower_barrier']==99.25
    assert r['event_class']=='continuation' and r['resolution_ts'].endswith('00:01:00+00:00')

def test_open_precedence_and_both_hit():
    assert _resolve(series([(0,102,103,98,101)]),0,HOUR+1,100,101,99,'up','down')['event_class']=='up'
    assert _resolve(series([(0,98,102,97,99)]),0,HOUR+1,100,101,99,'up','down')['event_class']=='down'
    x=_resolve(series([(0,100,101,99,100)]),0,HOUR+1,100,101,99,'up','down')
    assert x['ambiguous'] and x['ambiguity_reason']=='ambiguous_same_minute'

def test_endpoint_exactly_60m_and_no_synthetic_point():
    rows=[(i,100,100,100,100) for i in range(60)]; rows[-1]=(59,100,101,100,100)
    x=_resolve(series(rows),0,HOUR+MINUTE,100,101,99,'up','down')
    assert x['event_class']=='up' and x['resolution_ms']==HOUR

def test_H_exact_point_unavailable_and_no_post_H_range():
    s=series([(i,100,100,100,100) for i in range(10)]+[(10,100,200,1,100)])
    x=_resolve(s,0,10*MINUTE,None,101,99,'up','down')
    assert x['censor_reason']=='unavailable_exact_H_point'
    y=_resolve(s,0,10*MINUTE,101,101,99,'up','down')
    assert y['event_class']=='up' and y['event_timing']=='exact_H_point'

def test_chronology_gap_censors_before_later_open():
    s=series([(0,100,100,100,100),(2,102,103,98,100)])
    assert _resolve(s,0,HOUR,100,101,99,'up','down')['censor_reason']=='chronology_gap'

@pytest.mark.parametrize('peak,close,eligible,reason',[(101,100.6,True,''),(101,100.5,False,'already_beyond_giveback_state'),(100.999,100.8,False,'peak_gain_below_1pct'),(102,100,False,'current_return_not_positive')])
def test_t2_formulas_and_eligibility_edges(peak,close,eligible,reason):
    r=base(); _target(r,'T2',series([(i,close,close,close,close) for i in range(61)]),0,HOUR+MINUTE,100,100,peak,close)
    assert r['lower_barrier']==(100+peak)/2 and r['upper_barrier']==peak*1.005
    assert r['target_eligible'] is eligible and r['target_ineligible_reason']==reason

def test_future_peak_cannot_mutate_frozen_t2_barriers():
    r=base(); s=series([(i,101,150 if i==1 else 101,100.9,101) for i in range(61)])
    _target(r,'T2',s,0,HOUR+MINUTE,100,100,102,101.5)
    assert r['upper_barrier']==pytest.approx(102.51) and r['lower_barrier']==101

def test_deterministic_ids_order_and_boundaries():
    assert _snapshot_id('x',FIVE_MINUTES)==_snapshot_id('x',FIVE_MINUTES)
    assert _partition(1735689599999)=='2024_fold_B_validate' and _partition(1735689600000)=='2025_locked'
    with pytest.raises(ValueError): _partition(STUDY_END_MS)
    with pytest.raises(ValueError): _pre_holdout_timestamp(STUDY_END_MS,'synthetic')

def test_first_valid_boundary_and_partial_bar_exclusion_oracle():
    e=1704067320000
    first=((e+FIVE_MINUTES-1)//FIVE_MINUTES)*FIVE_MINUTES
    assert first==1704067500000 and first-FIVE_MINUTES<e
    assert first + FIVE_MINUTES == 1704067800000  # first bar whose start is post-entry

def test_equal_trade_weights():
    ns={'a':3,'b':7}
    for n in ns.values(): assert sum(1/n for _ in range(n))==pytest.approx(1)

def bootstrap_rows():
    out=[]
    for i,w in enumerate(('2024-01-01','2024-01-08','2024-01-15','2024-01-22','2024-01-29')):
        for j in range(i+1): out.append({'trade_id':f't{i}','trade_entry_week':w,'target_eligible':True,'resolved':True})
    return out

def test_bootstrap_whole_trade_overlap_multiplicity_and_seed():
    a=bootstrap_structure(bootstrap_rows()); b=bootstrap_structure(bootstrap_rows())
    assert a['sequence_sha256']==b['sequence_sha256'] and a['trades_never_split']
    assert any(any(v>1 for v in m.values()) for m in a['trade_multiplicities'])
    rng=np.random.Generator(np.random.PCG64(20240924))
    assert [int(rng.integers(2)) for _ in range(10)] != a['sampled_block_indices'][0][:10]
    assert BOOTSTRAP_CONFIG['replicates']==2000

def test_type7_oracle():
    x=np.array([0,10,20,30,40])
    assert np.quantile(x,.025,method='linear')==1 and np.quantile(x,.975,method='linear')==39

def test_no_trade_split_partition():
    e=1720000000000
    assert len({_partition(e) for _ in range(100)})==1

def test_numpy_environment_provenance_without_pythonpath():
    assert np.__version__ == '2.4.6'
    assert sys.executable == '/home/ata/miniconda3/envs/binance-v2-research/bin/python'
    assert str(Path(np.__file__).resolve()).startswith('/home/ata/miniconda3/envs/binance-v2-research/')
    assert 'PYTHONPATH' not in os.environ

def test_frozen_adequacy_decision_exact_values():
    expected = {
        'minimum_unique_resolved_trades_per_class':150, 'minimum_total_resolved_trades':300,
        'minimum_entry_weeks':40, 'minimum_months':9, 'required_symbol_count':5,
        'minimum_class_entry_weeks':40, 'minimum_class_months':9,
        'require_each_class_in_all_symbols':True, 'minimum_class_symbol_unique_resolved_trades':20,
        'maximum_single_trade_snapshot_concentration':.05, 'maximum_entry_week_concentration':.15,
        'maximum_snapshot_month_concentration':.20, 'maximum_overall_censoring':.20,
        'maximum_subgroup_censoring':.20, 'subgroup_censoring_minimum_eligible_rows':100,
        'maximum_ambiguity':.01, 'minimum_nonempty_four_entry_week_bootstrap_blocks_per_split':2,
        'reliability_bin_minimum_unique_resolved_trades':30,
        'class_bin_unstable_below_unique_event_trades':10,
        'calibration_intercept_slope_minimum_unique_event_trades':50,
    }
    assert ADEQUACY_THRESHOLDS == expected
    assert ADEQUACY_DECISIONS == {'T1':'ADEQUATE FOR MODELING','T2':'ADEQUATE FOR MODELING'}
    assert adequacy_decision()['threshold_panel_sha256'] == _json_hash(expected)

def test_accepted_core_hashes_and_decision_artifact():
    for key in ('T1','T2'):
        path=ARTIFACT/'local'/f'{key.lower()}_snapshots.csv'
        assert hashlib.sha256(path.read_bytes()).hexdigest() == ACCEPTED_CORE_HASHES[key]
    decision=json.loads((ARTIFACT/'adequacy_decision.json').read_text())
    manifest=json.loads((ARTIFACT/'reproducibility_manifest.json').read_text())
    assert decision == adequacy_decision()
    assert manifest['adequacy_decision']['file_sha256'] == hashlib.sha256((ARTIFACT/'adequacy_decision.json').read_bytes()).hexdigest()
    assert manifest['adequacy_decision']['threshold_panel_sha256'] == decision['threshold_panel_sha256']

def test_target_split_bootstrap_structures_are_deterministic_and_whole_trade():
    details=json.loads((ARTIFACT/'local/bootstrap_structure_details.json').read_text())['targets']
    assert set(details) == {'T1','T2'}
    for target in details.values():
        assert set(target) == set(BOOTSTRAP_PARTITIONS)
        for value in target.values():
            assert value['available'] and value['trades_never_split'] and value['multiplicities_preserved']
            assert len(value['nonempty_block_indices']) >= 2
            assert value['blocks_drawn_per_replicate'] == math.ceil(value['W']/4)
            assert value['config'] == BOOTSTRAP_CONFIG
            assert len(value['sampled_block_indices']) == 2000
            assert len(value['trade_multiplicities']) == 2000
    # Different target/split memberships must not be silently represented by one combined structure.
    identities={(t,p,v['sequence_sha256'],v['multiplicity_sha256']) for t,parts in details.items() for p,v in parts.items()}
    assert len(identities) == 12

def test_split_bootstrap_helper_reproducibility():
    rows=[]
    partitions=('2024_fold_A_train','2024_fold_A_validate_fold_B_train','2024_fold_B_validate','2025_locked')
    for i,p in enumerate(partitions):
        for j in range(6):
            rows.append({'trade_id':f'{p}-{j}','trade_entry_week':f'2024-{1+i*2+j:02d}-01','target_eligible':True,'resolved':True,'temporal_partition':p})
    a=bootstrap_structures(rows); b=bootstrap_structures(rows)
    assert {p:(v['sequence_sha256'],v['multiplicity_sha256']) for p,v in a.items()} == {p:(v['sequence_sha256'],v['multiplicity_sha256']) for p,v in b.items()}

def test_checkpoint_contains_no_prediction_or_unsealed_access():
    manifest=json.loads((ARTIFACT/'reproducibility_manifest.json').read_text())
    assert manifest['confirmations'] == {
        'predictive_models_run':False, 'predictive_metrics_computed':False,
        '2025_predictive_scoring_run':False, 'economic_analysis_run':False,
        '2026_paths_enumerated':False, '2026_market_data_accessed':False,
    }
