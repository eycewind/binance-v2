from pathlib import Path

import numpy as np
import pytest

from binance_data_foundation.c12_post_t2_warning import (
    CONTRACT_SHA256, all_condition_metrics, condition_mask, direction_consistency,
    event_metrics, first_persistent, generate_frozen_panel, lead_time,
    probability_band, reject_2026, reproduce_c11, trade_panels,
)


def _panel(probabilities, outcome="DETERIORATION_FIRST", terminal=600000):
    label=int(outcome=="CONTINUATION_FIRST")
    rows=[{"trade_id":"t","label":label,"symbol":"BTCUSDT","year":2024,"t0_ms":0,
           "state_ms":i*60000,"terminal_ms":terminal} for i in range(1,len(probabilities)+1)]
    return trade_panels(rows,np.asarray(probabilities))


def test_contract_is_frozen(repo_root=Path(__file__).parents[1]):
    import hashlib
    assert hashlib.sha256((repo_root/"contracts/C12_post_t2_warning_leadtime_CONTRACT.md").read_bytes()).hexdigest()==CONTRACT_SHA256


@pytest.mark.parametrize("p,expected",[(0,"VERY_DETERIORATION_LIKE"),(.199999,"VERY_DETERIORATION_LIKE"),
    (.2,"DETERIORATION_LEANING"),(.399999,"DETERIORATION_LEANING"),(.4,"UNCERTAIN"),
    (.599999,"UNCERTAIN"),(.6,"CONTINUATION_LEANING"),(.799999,"CONTINUATION_LEANING"),
    (.8,"VERY_CONTINUATION_LIKE"),(1,"VERY_CONTINUATION_LIKE")])
def test_frozen_probability_bands_and_boundaries(p,expected):
    assert probability_band(p)==expected


def test_persistence_p1_p2_p3_detection():
    mask=np.asarray([False,True,True,False,True,True,True])
    assert first_persistent(mask,1)==1
    assert first_persistent(mask,2)==2
    assert first_persistent(mask,3)==6


def test_lead_time_and_no_post_terminal():
    assert lead_time(600000,300000)==5
    with pytest.raises(ValueError):lead_time(600000,600000)
    rows=[{"trade_id":"t","label":0,"state_ms":600000,"terminal_ms":600000}]
    with pytest.raises(RuntimeError):trade_panels(rows,[.2])


def test_false_warning_recovery_cycles_and_duration():
    panels=_panel([.5,.3,.2,.7,.3,.2,.1,.8],"CONTINUATION_FIRST",600000)
    got=event_metrics(panels,"CONTINUATION_FIRST","lt_0.40",2)
    assert got["coverage"]==1
    assert got["among_detected"]["recovered_ge_0.60"]==1
    assert got["among_detected"]["condition_entry_cycles"]["median"]==2
    assert got["among_detected"]["warning_recovery_cycles"]["median"]==2
    assert got["among_detected"]["maximum_contiguous_condition_minutes"]["median"]==3


def test_p0_exclusion_is_structural():
    # Binary panels accept only binary labels; P0 never has an outcome key or denominator.
    panels=_panel([.1,.2])
    got=all_condition_metrics(panels)
    assert got["DETERIORATION_FIRST"]["lt_0.40"]["P1"]["eligible_outcome_trades"]==1
    assert got["CONTINUATION_FIRST"]["lt_0.40"]["P1"]["eligible_outcome_trades"]==0


def test_deterministic_strata_helpers_and_results():
    a=np.asarray([.1,.2,.3,.25,.4])
    assert direction_consistency(a)==direction_consistency(a.copy())
    panels=_panel(a)
    assert all_condition_metrics(panels)==all_condition_metrics(panels)


@pytest.mark.parametrize("path",["data/2026/x","metadata_2026.json",Path("sealed/2026Q1")])
def test_no_2026_access(path):
    with pytest.raises(PermissionError):reject_2026(path)


def test_exact_c11_probability_reproduction(repo_root=Path(__file__).parents[1]):
    data=generate_frozen_panel(repo_root)
    got=reproduce_c11(repo_root,data)
    assert got["status"]=="PASS"
    assert all(got["checks"].values())
    assert got["probability_rows"]>0
