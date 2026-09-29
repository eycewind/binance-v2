from pathlib import Path
import numpy as np

from binance_data_foundation import c25_q1_sequential_exit as c25


def test_contract_hash_and_frozen_scope():
    assert c25.sha(Path("contracts/C25_q1_sequential_exit_CONTRACT.md")) == c25.CONTRACT_SHA256
    assert c25.TARGET == "DELTA_LIQ_5"
    assert c25.COSTS == ("C0","C_BASE","C_S5","C_S10")


def test_q1_tie_is_included_and_no_persistence():
    assert c25.q1(.4,.4) and c25.q1(.39,.4) and not c25.q1(.4000001,.4)
    states=[{"state_ms":100}]
    got,failed,path,reassess=c25.choose_model_exit(states,[.4],.4,200,300,lambda t:(10.,None))
    assert path=="MODEL_EXIT_EXECUTED" and got["actual_ms"]==100 and reassess==0 and not failed


def test_first_q1_irrevocable_full_exit_and_non_q1_reassessment():
    states=[{"state_ms":100},{"state_ms":105},{"state_ms":110}]
    got,_,path,reassess=c25.choose_model_exit(states,[.6,.3,.9],.4,200,300,lambda t:(12.,None))
    assert path=="MODEL_EXIT_EXECUTED" and got["decision_ms"]==105 and got["price"]==12 and reassess==1


def test_terminal_tie_precedence_and_t2_disables_later_actions():
    got,_,path,_=c25.choose_model_exit([{"state_ms":100},{"state_ms":110}],[.3,.2],.4,100,300,lambda t:(9.,None))
    assert path=="REACHED_T2_BEFORE_MODEL_EXIT" and got is None
    got,_,path,_=c25.choose_model_exit([{"state_ms":100}],[.3],.4,100,100,lambda t:(9.,None))
    assert path=="ELIGIBLE_NEVER_Q1" and got is None


def test_missing_fill_fails_closed_and_allows_honest_reassessment():
    calls=[]
    def lookup(t):
        calls.append(t); return (None,"MISSING_NEXT_OPEN") if len(calls)==1 else (11.,None)
    got,failed,path,_=c25.choose_model_exit([{"state_ms":100},{"state_ms":105}],[.2,.2],.4,200,300,lookup)
    assert path=="MODEL_EXIT_EXECUTED" and got["actual_ms"]==105 and len(failed)==1


def test_p0_fallback_pairing_and_bootstraps_deterministic():
    rows=[]
    for i in range(6):
        d=(i-2)*.001
        rows.append({"trade_id":str(i),"entry_month":f"2025-0{1+i//3}","covered":i%2==0,"costs":{"C_BASE":{"delta_return":d,"delta_pnl":1000*d,"p0_return":.01,"c25_return":.01+d}}})
    a=c25.bootstrap(rows,"whole_trade",replicates=20); b=c25.bootstrap(rows,"whole_trade",replicates=20)
    m1=c25.bootstrap(rows,"calendar_month",replicates=20); m2=c25.bootstrap(rows,"calendar_month",replicates=20)
    assert a==b and m1==m2 and a["generator"]=="PCG64" and m1["pairing_preserved"]
    unchanged=dict(rows[0]); unchanged["costs"]={"C_BASE":{"delta_return":0.,"delta_pnl":0.,"p0_return":.02,"c25_return":.02}}
    assert c25.paired_summary([unchanged])["ties"]==1


def test_no_2026_access():
    import pytest
    with pytest.raises(PermissionError): c25.reject_2026("data/2026/x")
