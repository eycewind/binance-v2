from pathlib import Path
import inspect
import pytest

from binance_data_foundation import c27_temp5_feasibility_policy as c27


def test_contract_hash_and_frozen_scope():
    assert c27.sha(Path(c27.CONTRACT_REL))==c27.CONTRACT_SHA256
    assert c27.TARGET=="DELTA_LIQ_5" and c27.COSTS==("C0","C_BASE","C_S5","C_S10")
    source=inspect.getsource(c27)
    for forbidden in ("DELTA_LIQ_15","DELTA_LIQ_30","DELTA_LIQ_60","DELTA_LIQ_EVENT"):
        assert forbidden not in source


def test_actual_roundtrip_friction_and_full_reentry():
    zero=c27.incremental_roundtrip_friction(100,110,105,"C0")
    assert zero["incremental_friction_return"]==0 and zero["reentry_quantity"]==zero["cash_after_sell"]/105
    base=c27.incremental_roundtrip_friction(100,110,105,"C_BASE")
    assert base["incremental_friction_return"]>0
    assert base["buy_executed_notional"]+base["buy_fee_quote"]==pytest.approx(base["cash_after_sell"])
    assert base["incremental_friction_quote"]==pytest.approx(base["sell_slippage_quote"]+base["sell_fee_quote"]+base["buy_slippage_quote"]+base["buy_fee_quote"])


def _rows():
    out=[]
    for tid,month,value,friction in (("a","2024-01",-.01,.002),("b","2024-02",.004,.002),("c","2024-02",-.003,.002)):
        out.append({"trade_id":tid,"entry_month":month,"DELTA_LIQ_5":value,"friction":{"C_BASE":{"incremental_friction_return":friction}}})
    return out


def test_margin_summary_and_bootstraps_are_paired_deterministic():
    rows=_rows(); got=c27.feasibility_summary(rows,"C_BASE")
    assert got["mean_feasibility_margin_5"]==pytest.approx((.008-.006+.001)/3)
    for unit in ("whole_trade","calendar_month"):
        a=c27.bootstrap(rows,unit,replicates=40); b=c27.bootstrap(rows,unit,replicates=40)
        assert a==b and a["generator"]=="PCG64" and a["paired_quantities_preserved"]


def test_gate_is_deterministic_and_blocks_stage_b():
    yearly={str(y):{"C_BASE":{"mean_feasibility_margin_5":.001 if y==2024 else -.001}} for y in c27.YEARS}
    interval={"intervals":{"mean_feasibility_margin_5":{"ci95":[-.01,.01]}}}
    uncertainty={str(y):interval for y in c27.YEARS}
    got=c27.gate(yearly,uncertainty,uncertainty)
    assert got["FEASIBILITY_GATE"]=="FAIL" and not got["stage_b_authorized"]
    assert got["classification"]=="STOP_TEMPORARY_EXIT_CANDIDATE"


def test_no_2026_access_and_no_alternate_policy_search():
    with pytest.raises(PermissionError): c27.reject_2026("data/2026/x")
    source=inspect.getsource(c27.run)
    assert 'datasets={2024:(train24,valid24),2025:(rows24,rows25)}' in source
    assert 'if gate_result["stage_b_authorized"]' in source
    assert '"stage_b_executed":False' in source and '"no_tuning_or_search":True' in source
