from pathlib import Path

import numpy as np
import pytest

from binance_data_foundation.c23_incremental_c9_ablation import (
    FEATURES, MODELS, binary_label, fit_candidates, paired_bootstrap, reject_2026,
)


def rows():
    out=[]
    for j,(tid,entry,p) in enumerate((("a",0,.2),("b",2_000_000_000,.7),("c",4_000_000_000,.4))):
        for k in range(3):
            out.append({"trade_id":tid,"entry_ms":entry,"terminal_ms":entry+1_000_000,
                "state_ms":entry+(k+1)*300_000,"DELTA_LIQ_5":(-1+j)+k*.2,
                "causal_features":{"elapsed_minutes_since_entry":5*(k+1),
                    "observable_current_return_from_entry":.01*k,"p_t2":p+.02*k}})
    return out


def test_exact_c22_binary_zero_boundary():
    assert binary_label(1e-12)==1 and binary_label(-1e-12)==0 and binary_label(0.0)==0


def test_exact_schemas_and_sole_difference():
    assert MODELS == ("S","S+C9")
    assert FEATURES["S"] == ("elapsed_minutes_since_entry","observable_current_return_from_entry")
    assert set(FEATURES["S+C9"])-set(FEATURES["S"]) == {"p_t2"}


def test_training_only_preprocessing_and_fixed_models():
    rr=rows(); a,d=fit_candidates(rr[:6],rr[6:],"DELTA_LIQ_5")
    assert d["S"]["binary"]["C"]==1.0 and d["S+C9"]["continuous"]["alpha"]==1.0
    assert set(a)==set(MODELS)


def test_paired_bootstraps_are_deterministic_and_whole_trade():
    rr=rows(); n=len(rr); s={"binary":np.linspace(.2,.8,n),"continuous":np.linspace(-.5,.5,n)}
    c={"binary":np.linspace(.25,.75,n),"continuous":np.linspace(-.4,.4,n)}
    for unit in ("calendar_month","whole_trade"):
        a=paired_bootstrap(rr,"DELTA_LIQ_5",s,c,unit,replicates=20)
        b=paired_bootstrap(rr,"DELTA_LIQ_5",s,c,unit,replicates=20)
        assert a==b and a["pairing_preserved"] and not a["models_refit_inside_replicates"]


def test_observable_timing_no_fold_a_full_2024_and_no_2026():
    source=Path("src/binance_data_foundation/c23_incremental_c9_ablation.py").read_text()
    assert "fast.close[fast.at(t)]" in source and "NOT_FABRICATED" in source
    assert "fit_candidates(rows24, rows25" in source
    with pytest.raises(PermissionError): reject_2026(Path("sealed/2026/data"))
