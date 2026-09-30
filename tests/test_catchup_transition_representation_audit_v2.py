from pathlib import Path

import pytest

from binance_data_foundation import catchup_transition_representation_audit as v1
from binance_data_foundation import catchup_transition_representation_audit_v2 as audit


def _hours(t, returns=None):
    returns = returns or {}
    out = {s:{} for s in v1.SYMBOLS}
    for s in v1.SYMBOLS:
        price=100.0
        for u in range(t-15*v1.HOUR,t+2*v1.HOUR,v1.HOUR):
            r=returns.get((s,u),returns.get(u,0.0))
            out[s][u]={"valid":True,"open":price,"close":price*(1+r),"count":60,"source_start_ms":u,"source_end_ms":u+59*v1.MINUTE}
            price*=1+r
    return out


def test_hashes_population_schema_and_peers():
    assert audit.verify_frozen_documents(Path.cwd())["all_match"]
    entries, rec=v1.reconcile_population(Path.cwd())
    assert len(entries)==2199 and rec["semantic_sha256"]==v1.ENTRY_SHA256
    assert audit.PRIMARY == ("NEW_JOINER_FRACTION","BASKET_ACCELERATION","PRIOR_RELATIVE_DEFICIT","RELATIVE_IMPROVEMENT","DISPERSION_CHANGE","MINUTES_SINCE_MARKET_ONSET_DETECTION","MINUTES_SINCE_SUBJECT_ONSET_DETECTION","SUBJECT_ONSET_INTERVAL_RETURN","BTC_ONSET_LEAD_MINUTES")
    assert "BREADTH_CHANGE" not in audit.PRIMARY and "SUBJECT_EXTENSION_SINCE_ONSET" not in audit.PRIMARY
    assert all(len([x for x in v1.SYMBOLS if x!=s])==4 for s in v1.SYMBOLS)


def test_same_boundary_interval_detection_and_formulae():
    t=1_735_776_000_000; h=_hours(t)
    h["ETHUSDT"][t-2*v1.HOUR]["close"]=h["ETHUSDT"][t-2*v1.HOUR]["open"]*.99
    h["ETHUSDT"][t-v1.HOUR]["close"]=h["ETHUSDT"][t-v1.HOUR]["open"]*1.02
    row=audit.representation_row(h,"ETHUSDT",t)
    assert row["SUBJECT_ONSET_DETECTED_TS"]==t
    assert row["SUBJECT_ONSET_INTERVAL_START_TS"]==t-v1.HOUR
    assert row["SUBJECT_ONSET_INTERVAL_END_TS"]==t
    assert row["MINUTES_SINCE_SUBJECT_ONSET_DETECTION"]==0
    assert row["SUBJECT_ONSET_INTERVAL_RETURN"]==pytest.approx(.02)
    assert row["BASKET_ACCELERATION"]==pytest.approx(row["BASKET_RECENT_RETURN"]-row["BASKET_PREV_RETURN"])
    assert row["PRIOR_RELATIVE_DEFICIT"]==pytest.approx(-(row["SUBJECT_PREV_RETURN"]-row["BASKET_PREV_RETURN"]))
    assert row["RELATIVE_IMPROVEMENT"]==pytest.approx((row["SUBJECT_RECENT_RETURN"]-row["BASKET_RECENT_RETURN"])-(row["SUBJECT_PREV_RETURN"]-row["BASKET_PREV_RETURN"]))


def test_onset_window_count_most_recent_and_fail_cases():
    t=1_735_776_000_000; h=_hours(t); s="ETHUSDT"
    for u in h[s]: h[s][u]["valid"]=False
    for u, ret in ((t-3*v1.HOUR,.005),(t-2*v1.HOUR,.01),(t-v1.HOUR,.02),
                   (t-14*v1.HOUR,.005),(t-13*v1.HOUR,.01)):
        h[s][u]["valid"]=True
        h[s][u]["close"]=h[s][u]["open"]*(1+ret)
    found=audit.symbol_onsets(h,s,t)
    assert found[0]==t and t-12*v1.HOUR in found and len(found)>=2
    assert all(u>=t-12*v1.HOUR for u in found)
    # equality, positive non-improving, improving non-positive and missing do not qualify
    h2=_hours(t); 
    for u in h2[s]: h2[s][u]["valid"]=False
    h2[s][t-2*v1.HOUR]["valid"]=h2[s][t-v1.HOUR]["valid"]=True
    h2[s][t-2*v1.HOUR]["close"]=h2[s][t-2*v1.HOUR]["open"]*1.01
    h2[s][t-v1.HOUR]["close"]=h2[s][t-v1.HOUR]["open"]*1.01
    assert audit.symbol_onsets(h2,s,t)==[]


def test_market_thresholds_counts_and_causality():
    t=1_735_776_000_000
    def case(prev,recent):
        returns={}
        for i,s in enumerate(v1.SYMBOLS):
            returns[(s,t-2*v1.HOUR)]=.01 if i<prev else -.01
            returns[(s,t-v1.HOUR)]=.01 if i<recent else -.01
        h=_hours(t,returns)
        for s in v1.SYMBOLS:
            for u in h[s]: h[s][u]["valid"]=u in (t-2*v1.HOUR,t-v1.HOUR)
        return h
    assert audit.market_onsets(case(2,3),t)==[t]
    assert audit.market_onsets(case(1,2),t)==[]
    assert audit.market_onsets(case(3,3),t)==[]
    future,fill,same=audit.synthetic_causality_tests()
    assert future["status"]==fill["status"]==same["status"]=="PASS"


def test_deterministic_correlations_duplicates_and_guards():
    rows=[{k:float(i+j) for j,k in enumerate(audit.PRIMARY)} for i in range(5)]
    assert audit._corr(rows,False)==audit._corr(rows,False)
    assert audit._duplicates(rows)==audit._duplicates(rows)
    with pytest.raises(PermissionError): v1.reject_2026("forbidden/year=2026/x")
    with pytest.raises(PermissionError): v1._firewall(["C30_probability"])
