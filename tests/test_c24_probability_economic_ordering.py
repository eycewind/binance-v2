from pathlib import Path
import numpy as np
import pytest

from binance_data_foundation.c24_probability_economic_ordering import (
    CONTRACT_SHA256, assign_bins, associations, bin_boundaries, bin_summaries,
    bootstrap, ordering, reject_2026, sha, weighted_quantile, weights,
)


def rows():
    out=[]
    for j,(tid,entry) in enumerate((("a",0),("b",2_000_000_000),("c",4_000_000_000),("d",6_000_000_000),("e",8_000_000_000))):
        for k in range(j+1): out.append({"trade_id":tid,"entry_ms":entry,"symbol":"BTCUSDT","DELTA_LIQ_5":float(j-2+k/10)})
    return out


def test_contract_hash_and_exact_zero_label_source():
    assert sha(Path("contracts/C24_probability_economic_ordering_CONTRACT.md")) == CONTRACT_SHA256
    source=Path("src/binance_data_foundation/c24_probability_economic_ordering.py").read_text()
    assert '"exact_zero":0' in source and 'pv=valid_pred["S+C9"]["binary"]' in source


def test_whole_trade_weights_and_weighted_quantiles():
    rr=rows(); w=weights(rr)
    assert np.isclose(w.sum(),5) and all(np.isclose(w[[r["trade_id"]==t for r in rr]].sum(),1) for t in "abcde")
    assert weighted_quantile([1,2,3],[1,1,2],.5)==2


def test_training_only_boundaries_duplicates_and_frozen_application():
    rr=rows(); p=np.array([.1]*1+[.2]*2+[.5]*3+[.8]*4+[.9]*5)
    definition=bin_boundaries(p,rr); assert definition["training_only"] and definition["duplicate_values_never_split"]
    bins=assign_bins(p,definition["cut_values"])
    assert all(len(set(bins[p==v]))==1 for v in set(p))
    assert np.array_equal(assign_bins([0,.3,1],definition["cut_values"]),assign_bins([0,.3,1],definition["cut_values"]))


def test_summaries_spreads_tail_accounting_and_rank():
    rr=rows(); p=np.linspace(.01,.99,len(rr)); cuts=[.15,.35,.55,.75]
    sm=bin_summaries(rr,"DELTA_LIQ_5",p,cuts); eco=ordering(rr,"DELTA_LIQ_5",p,sm)
    assert np.isclose(sm["Q1"]["positive_contribution"]+sm["Q1"]["negative_contribution"],sm["Q1"]["net_contribution"])
    assert np.isclose(eco["Delta_mean_Q5_Q1"],sm["Q5"]["weighted_mean_delta_liq"]-sm["Q1"]["weighted_mean_delta_liq"])
    assert associations(p,[r["DELTA_LIQ_5"] for r in rr],weights(rr))["weighted_spearman"] > 0


def test_paired_bootstraps_pcg64_deterministic_and_no_refit():
    rr=rows(); p=np.linspace(.01,.99,len(rr)); cuts=[.15,.35,.55,.75]
    for unit in ("calendar_month","whole_trade"):
        a=bootstrap(rr,"DELTA_LIQ_5",p,cuts,unit,replicates=20); b=bootstrap(rr,"DELTA_LIQ_5",p,cuts,unit,replicates=20)
        assert a==b and a["generator"]=="PCG64" and not a["models_refit_inside_replicates"]


def test_governance_no_search_horizon_future_or_2026():
    source=Path("src/binance_data_foundation/c24_probability_economic_ordering.py").read_text()
    assert 'threshold_or_bin_search":False' in source and 'horizon_selection":False' in source
    assert "c20.TARGETS" in source and "FEATURES" not in source
    with pytest.raises(PermissionError): reject_2026("sealed/2026/data")
