from copy import deepcopy
import csv

import pytest

from binance_data_foundation.c2_common import hash_rows
from binance_data_foundation.c2_temporal import (
    _drawdown_summary, _load_validated_candidate_rows, analyze_path,
)
from binance_data_foundation.ingest import sha256_file


E=1_704_067_200_000; M=60_000


def bar(n:int,high:float,low:float,close:float=100)->dict:
    return {"open_time_ms":E+n*M,"open":100,"high":high,"low":low,"close":close}


def analyze(rows:list[dict],horizon_price:float=100,minutes:int=5)->dict:
    return analyze_path(E,100,E+minutes*M,horizon_price,rows)


def test_exact_first_passage_and_threshold_equality() -> None:
    result=analyze([bar(1,100.9,99.8),bar(2,101,99.9)])
    assert result["1pct_hit"] and result["1pct_first_passage_ms"]==E+2*M
    assert result["1pct_first_passage_seconds"]==120


def test_never_hit_is_explicitly_censored() -> None:
    result=analyze([bar(1,100.4,99.8)],horizon_price=100.2)
    assert result["0_5pct_hit"] is False and result["0_5pct_first_passage_ms"] is None


def test_drawdown_before_threshold_excludes_ambiguous_touch_minute_low() -> None:
    result=analyze([bar(1,100.5,99),bar(2,101,97)])
    assert result["1pct_pre_hit_mae"]==pytest.approx(-.01)
    assert result["1pct_touch_minute_low_ambiguous"] is True


def test_first_competing_event_order_and_elapsed_time() -> None:
    result=analyze([bar(1,101,100),bar(2,101.5,99.8),bar(3,102,100)])
    assert result["after_1pct_first_event"]=="returns_entry"
    assert result["after_1pct_elapsed_seconds"]==60
    assert result["after_1pct_total_seconds"]==120


def test_same_minute_competing_event_is_ambiguous() -> None:
    result=analyze([bar(1,101,100),bar(2,102.2,99.8)])
    assert result["after_1pct_first_event"]=="same_minute_ambiguous"


def test_post_two_percent_transition_and_return_to_one_percent() -> None:
    result=analyze([bar(1,102,100),bar(2,102.5,101)],horizon_price=101.5)
    assert result["after_2pct_first_event"]=="returns_1pct"
    assert result["after_2pct_elapsed_seconds"]==60
    assert result["after_2pct_to_1pct_seconds"]==60
    assert result["after_2pct_to_entry_seconds"] is None


def test_nested_milestone_clocks_and_explicit_censoring() -> None:
    result=analyze([bar(1,101,100),bar(2,103,101),bar(3,104,100.5)],horizon_price=101)
    assert result["after_1pct_to_2pct_seconds"]==60
    assert result["after_1pct_to_3pct_seconds"]==60
    assert result["after_1pct_to_5pct_seconds"] is None
    assert result["after_1pct_to_entry_seconds"] is None


def test_no_use_after_h() -> None:
    with pytest.raises(ValueError,match="strictly after entry and before H"):
        analyze_path(E,100,E+2*M,100,[bar(1,101,100),bar(3,999,1)])


def test_horizon_endpoint_can_hit_without_using_endpoint_range() -> None:
    result=analyze([bar(1,100.1,99.9)],horizon_price=101)
    assert result["1pct_first_passage_ms"]==E+5*M
    assert result["1pct_touch_minute_low_ambiguous"] is False


def test_deterministic_and_future_mutation_outside_h_rejected() -> None:
    rows=[bar(1,101,99.5),bar(2,102,100)]
    assert analyze(rows)==analyze(deepcopy(rows))
    with pytest.raises(ValueError): analyze_path(E,100,E+3*M,100,rows+[bar(4,200,1)])


def test_2026_timestamp_not_accepted_as_path() -> None:
    end_2026=1_767_225_600_000
    with pytest.raises(ValueError): analyze_path(end_2026-M,100,end_2026+M,100,[{"open_time_ms":end_2026,"high":101,"low":99}])


def test_frozen_entry_exactly_at_2026_boundary_is_rejected() -> None:
    boundary=1_767_225_600_000
    with pytest.raises(ValueError,match="2026 timestamps"):
        analyze_path(boundary,100,boundary+M,100,[])


def test_horizon_exactly_at_2026_boundary_is_rejected() -> None:
    boundary=1_767_225_600_000
    with pytest.raises(ValueError,match="2026 timestamps"):
        analyze_path(boundary-M,100,boundary,100,[])


def _candidate_fixture(tmp_path, **updates):
    columns=("entry_signal_ts","entry_decision_ts","entry_execution_ts","entry_execution_ms",
             "exit_signal_ts","exit_decision_ts","exit_execution_ts","common_horizon_end_ts",
             "common_horizon_end_ms","policy_activated_ms","rescued")
    row={column:"" for column in columns}
    row.update({"entry_execution_ts":"2025-01-01T00:00:00Z","entry_execution_ms":"1735689600000",
                "exit_execution_ts":"2025-01-01T00:01:00Z",
                "common_horizon_end_ts":"2025-01-01T00:02:00Z",
                "common_horizon_end_ms":"1735689720000","rescued":"not-consumed-during-validation", **updates})
    path=tmp_path/"candidate.csv"
    with path.open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=columns,lineterminator="\n"); writer.writeheader(); writer.writerow(row)
    return path,row,columns


@pytest.mark.parametrize("field", ["exit_execution_ts", "common_horizon_end_ts"])
def test_candidate_outcome_timestamp_exactly_at_boundary_is_rejected(tmp_path,field) -> None:
    path,row,columns=_candidate_fixture(tmp_path,**{field:"2026-01-01T00:00:00Z"})
    digest=sha256_file(path); semantic=hash_rows([row],columns)
    with pytest.raises(ValueError,match=f"2026 candidate timestamp rejected: {field}"):
        _load_validated_candidate_rows(path,expected_file_hash=digest,expected_semantic_hash=semantic)


def test_candidate_hash_mismatch_is_rejected_before_diagnostics(tmp_path) -> None:
    path=tmp_path/"candidate.csv"; path.write_text("this,is,not,the,accepted,input\n",encoding="utf-8")
    with pytest.raises(ValueError,match="file hash mismatch before diagnostics"):
        _load_validated_candidate_rows(path,expected_file_hash="0"*64,expected_semantic_hash="0"*64)


def test_pre_fill_entry_minute_touch_cannot_count() -> None:
    with pytest.raises(ValueError,match="strictly after entry"):
        analyze_path(E,100,E+2*M,100,[{"open_time_ms":E,"high":105,"low":99}])


def test_h_uses_only_execution_price_for_hits_and_transitions() -> None:
    result=analyze([bar(1,101,100)],horizon_price=101.5)
    assert result["2pct_hit"] is False
    assert result["after_1pct_first_event"] == "none_before_H"
    assert result["after_1pct_to_2pct_seconds"] is None


def test_h_execution_price_can_resolve_event() -> None:
    result=analyze([bar(1,101,100)],horizon_price=102)
    assert result["after_1pct_first_event"] == "reaches_2pct"
    assert result["after_1pct_event_ms"] == E+5*M


def test_return_barriers_include_exact_equality() -> None:
    one=analyze([bar(1,101,100),bar(2,101.2,100)])
    two=analyze([bar(1,102,100),bar(2,102.2,101)])
    assert one["after_1pct_first_event"] == "returns_entry"
    assert two["after_2pct_first_event"] == "returns_1pct"


def test_initial_milestone_same_minute_ambiguity() -> None:
    result=analyze([bar(1,102.1,99.9)])
    assert result["after_1pct_first_event"] == "same_minute_ambiguous"
    assert result["after_1pct_event_ms"] == E+M


def test_first_resolved_event_remains_first_when_opposite_occurs_later() -> None:
    result=analyze([bar(1,101,100),bar(2,102,100.5),bar(3,102.2,99.5)])
    assert result["after_1pct_first_event"] == "reaches_2pct"
    assert result["after_1pct_event_ms"] == E+2*M


def test_all_competing_clocks_can_be_censored() -> None:
    result=analyze([bar(1,101,100.1),bar(2,101.5,100.1)],horizon_price=101.5)
    assert result["after_1pct_first_event"] == "none_before_H"
    assert all(result[f"after_1pct_to_{target}_seconds"] is None for target in ("2pct","3pct","5pct","entry"))


def test_adverse_threshold_equality_is_reported_as_at_or_below() -> None:
    rows=[{"1pct_hit":True,"1pct_pre_hit_mae":-.01,"1pct_touch_minute_low_ambiguous":False}]
    for label in ("0_5pct","2pct","3pct","5pct"):
        rows[0].update({f"{label}_hit":False,f"{label}_pre_hit_mae":None,
                        f"{label}_touch_minute_low_ambiguous":False})
    summary=_drawdown_summary(rows)
    assert summary["1pct"]["went_at_or_below_before_success"]["-0.01"]["count"] == 1
