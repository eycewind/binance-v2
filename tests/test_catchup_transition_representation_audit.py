from pathlib import Path
import inspect

import pytest

from binance_data_foundation import catchup_transition_representation_audit as audit


def _hours(t, returns):
    out = {s: {} for s in audit.SYMBOLS}
    for s in audit.SYMBOLS:
        price = 100.0
        for i, u in enumerate(range(t-15*audit.HOUR, t+2*audit.HOUR, audit.HOUR)):
            r = returns.get((s, u), returns.get(u, .0))
            out[s][u] = {"valid": True, "open": price, "close": price*(1+r), "count": 60,
                         "source_start_ms": u, "source_end_ms": u+59*audit.MINUTE}
            price *= 1+r
    return out


def test_frozen_hashes_population_and_universe():
    assert audit.verify_frozen_documents(Path.cwd())["all_match"]
    entries, rec = audit.reconcile_population(Path.cwd())
    assert len(entries) == 2199 and rec["semantic_sha256"] == audit.ENTRY_SHA256
    assert rec["year_counts"] == {"2024":1093,"2025":1106}
    assert rec["symbol_counts"] == audit.EXPECTED_SYMBOLS
    assert len(audit.SYMBOLS) == 5 and len(audit.PRIMARY) == 10


def test_return_arithmetic_formulae_loo_and_ddof_zero():
    t=1_735_776_000_000
    prev=dict(zip(audit.SYMBOLS,(.01,.02,.03,.04,.05)))
    recent=dict(zip(audit.SYMBOLS,(-.01,.04,.06,.08,.10)))
    returns={(s,t-2*audit.HOUR):prev[s] for s in audit.SYMBOLS}|{(s,t-audit.HOUR):recent[s] for s in audit.SYMBOLS}
    h=_hours(t,returns); x=audit.state_at(h,"BTCUSDT",t)
    peers=[s for s in audit.SYMBOLS if s!="BTCUSDT"]
    assert x["BASKET_PREV_RETURN"] == pytest.approx(sum(prev[s] for s in peers)/4)
    assert x["BREADTH_PREVIOUS"]==1 and x["BREADTH_RECENT"]==.8
    assert x["NEW_JOINER_FRACTION"]==0 and x["PERSISTENT_PARTICIPANT_FRACTION"]==.8
    assert x["BASKET_ACCELERATION"]==pytest.approx(x["BASKET_RECENT_RETURN"]-x["BASKET_PREV_RETURN"])
    assert x["PRIOR_RELATIVE_DEFICIT"]==pytest.approx(-x["SUBJECT_RELATIVE_PREVIOUS"])
    assert x["RELATIVE_IMPROVEMENT"]==pytest.approx(x["SUBJECT_RELATIVE_RECENT"]-x["SUBJECT_RELATIVE_PREVIOUS"])
    assert x["DISPERSION_PREVIOUS"]==pytest.approx(__import__('numpy').std(list(prev.values()),ddof=0))


def test_symbol_onset_boundaries_most_recent_null_and_missing():
    t=1_735_776_000_000; s="ETHUSDT"
    h=_hours(t,{})
    for u in h[s]: h[s][u]["valid"] = False
    h[s][t-audit.HOUR]["valid"] = h[s][t-2*audit.HOUR]["valid"] = True
    # Equality, positive-not-improving, and improving-nonpositive do not qualify.
    h[s][t-audit.HOUR]["close"]=h[s][t-audit.HOUR]["open"]*1.01
    h[s][t-2*audit.HOUR]["close"]=h[s][t-2*audit.HOUR]["open"]*1.01
    assert audit.most_recent_symbol_onset(h,s,t) is None
    h[s][t-2*audit.HOUR]["close"]=h[s][t-2*audit.HOUR]["open"]*.999
    assert audit.most_recent_symbol_onset(h,s,t)==t
    # Add qualifying t-1h; t remains most recent.
    h[s][t-3*audit.HOUR]["close"]=h[s][t-3*audit.HOUR]["open"]*.998
    h[s][t-3*audit.HOUR]["valid"] = True
    assert audit.most_recent_symbol_onset(h,s,t)==t
    h[s][t-audit.HOUR]["valid"]=False
    h[s][t-2*audit.HOUR]["close"]=h[s][t-2*audit.HOUR]["open"]*1.01
    assert audit.most_recent_symbol_onset(h,s,t)==t-audit.HOUR
    h[s][t-2*audit.HOUR]["valid"]=False; h[s][t-3*audit.HOUR]["valid"]=False
    assert audit.most_recent_symbol_onset(h,s,t) is None
    # Positive but deteriorating, and improving but non-positive, both fail.
    h[s][t-audit.HOUR]["valid"]=h[s][t-2*audit.HOUR]["valid"]=True
    h[s][t-2*audit.HOUR]["close"]=h[s][t-2*audit.HOUR]["open"]*1.02
    h[s][t-audit.HOUR]["close"]=h[s][t-audit.HOUR]["open"]*1.01
    assert audit.most_recent_symbol_onset(h,s,t) is None
    h[s][t-2*audit.HOUR]["close"]=h[s][t-2*audit.HOUR]["open"]*.98
    h[s][t-audit.HOUR]["close"]=h[s][t-audit.HOUR]["open"]*.99
    assert audit.most_recent_symbol_onset(h,s,t) is None
    # A qualifying event 13 hours before E1 is outside the exact window.
    for u in h[s]: h[s][u]["valid"]=False
    u=t-13*audit.HOUR
    h[s][u-2*audit.HOUR]["valid"]=h[s][u-audit.HOUR]["valid"]=True
    h[s][u-2*audit.HOUR]["close"]=h[s][u-2*audit.HOUR]["open"]*.99
    h[s][u-audit.HOUR]["close"]=h[s][u-audit.HOUR]["open"]*1.01
    assert audit.most_recent_symbol_onset(h,s,t) is None


def test_market_onset_threshold_change_and_most_recent():
    t=1_735_776_000_000
    def case(prev_pos,recent_pos):
        r={}
        for i,s in enumerate(audit.SYMBOLS):
            r[(s,t-2*audit.HOUR)]=.01 if i<prev_pos else -.01
            r[(s,t-audit.HOUR)]=.01 if i<recent_pos else -.01
        h=_hours(t,r)
        for s in audit.SYMBOLS:
            for u in h[s]: h[s][u]["valid"] = u in (t-2*audit.HOUR,t-audit.HOUR)
        return h
    assert audit.most_recent_market_onset(case(2,3),t)==t
    assert audit.most_recent_market_onset(case(1,2),t) is None
    assert audit.most_recent_market_onset(case(3,3),t) is None
    assert audit.most_recent_market_onset(case(4,4),t) is None
    h=case(2,3)
    for s in audit.SYMBOLS:
        h[s][t-3*audit.HOUR]["valid"]=True
        h[s][t-3*audit.HOUR]["close"]=h[s][t-3*audit.HOUR]["open"]*(-.01+1)
    assert audit.most_recent_market_onset(h,t)==t


def test_catchup_boundaries_extension_lead_and_causal_independence():
    future, fill=audit.synthetic_causality_tests()
    assert future["status"]==fill["status"]=="PASS"
    t=1_735_776_000_000; h=_hours(t,{})
    r=audit.representation_row(h,"ETHUSDT",t)
    assert r["CATCHUP_SEQUENCE_CANDIDATE"]==0
    assert r["source_end_ts"]<t and r["available_ts"]<=t
    assert audit._extension(h,"ETHUSDT",t,t) is None
    # Frozen candidate uses strict signs: either exact-zero boundary remains false.
    r["MARKET_ONSET_TS"]=t; r["PRIOR_RELATIVE_DEFICIT"]=0; r["RELATIVE_IMPROVEMENT"]=1
    candidate=int(r["MARKET_ONSET_TS"] is not None and r["PRIOR_RELATIVE_DEFICIT"]>0 and r["RELATIVE_IMPROVEMENT"]>0)
    assert candidate==0
    r["PRIOR_RELATIVE_DEFICIT"]=1; r["RELATIVE_IMPROVEMENT"]=0
    candidate=int(r["MARKET_ONSET_TS"] is not None and r["PRIOR_RELATIVE_DEFICIT"]>0 and r["RELATIVE_IMPROVEMENT"]>0)
    assert candidate==0
    r["MARKET_ONSET_TS"]=None; r["RELATIVE_IMPROVEMENT"]=1
    candidate=int(r["MARKET_ONSET_TS"] is not None and r["PRIOR_RELATIVE_DEFICIT"]>0 and r["RELATIVE_IMPROVEMENT"]>0)
    assert candidate==0


def test_correlations_duplicates_hashes_and_firewalls_are_deterministic():
    rows=[]
    for i in range(5):
        row={k:float(i+j) for j,k in enumerate(audit.PRIMARY)}; rows.append(row)
    assert audit.correlation(rows,False)==audit.correlation(rows,False)
    assert audit.correlation(rows,True)==audit.correlation(rows,True)
    assert audit.exact_duplicates(rows)==audit.exact_duplicates(rows)
    with pytest.raises(PermissionError): audit.reject_2026("data/year=2026/x")
    with pytest.raises(PermissionError): audit._firewall(["GROSS40_label"])
    source=inspect.getsource(audit)
    assert "sklearn" not in source and ".fit(" not in source
