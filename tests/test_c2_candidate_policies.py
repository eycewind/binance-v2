from __future__ import annotations

from copy import deepcopy
import inspect

import pytest

from binance_data_foundation.c2_candidate_policies import decide_p1, decide_p2, decide_p3
from binance_data_foundation.c2_path_metrics import evaluate_path


START = 1_704_067_200_000
M = 60_000
M5 = 300_000


def minute(ts: int, open_: float = 100, high: float | None = None, low: float | None = None, close: float | None = None) -> dict:
    return {"symbol": "AAA", "open_time_ms": ts, "open": open_, "high": open_ if high is None else high,
            "low": open_ if low is None else low, "close": open_ if close is None else close,
            "base_volume": 1, "quote_volume": 1, "trade_count": 1}


def bar5(ts: int, close: float, *, high: float | None = None) -> dict:
    return {"symbol": "AAA", "open_time_ms": ts, "available_at_ms": ts + M5,
            "open": close, "high": close if high is None else high, "low": close, "close": close}


def test_p1_tp_sl_and_entry_minute_exclusion() -> None:
    h = START + 3 * M
    entry_extreme = minute(START, high=999, low=1)
    tp = decide_p1(START, 100, h, 100, {START: entry_extreme, START + M: minute(START + M, high=102), h: minute(h)})
    assert tp.exit_reason == "take_profit" and tp.exit_price == 102 and tp.execution_ms == START + M
    sl = decide_p1(START, 100, h, 100, {START: entry_extreme, START + M: minute(START + M, low=99), h: minute(h)})
    assert sl.exit_reason == "stop_loss" and sl.exit_price == 99


@pytest.mark.parametrize("open_,reason", [(103, "take_profit_gap_through"), (98, "stop_loss_gap_through")])
def test_p1_gap_through_executes_at_open(open_: float, reason: str) -> None:
    h = START + 2 * M
    result = decide_p1(START, 100, h, 100, {START + M: minute(START + M, open_), h: minute(h)})
    assert result.exit_reason == reason and result.exit_price == open_ and result.gap_through


def test_p1_both_hit_is_conservative_and_explicit() -> None:
    h = START + 2 * M
    result = decide_p1(START, 100, h, 100, {START + M: minute(START + M, high=103, low=98), h: minute(h)})
    assert result.exit_price == 99 and result.exit_reason == "stop_loss"
    assert result.ambiguity_flag == "ambiguous_both_hit_conservative"


def test_p1_gap_stops_chronology_and_h_forces_close() -> None:
    h = START + 3 * M
    assert decide_p1(START, 100, h, 101, {START + 2 * M: minute(START + 2 * M), h: minute(h, 101)}).censored
    complete = {START + M: minute(START + M), START + 2 * M: minute(START + 2 * M), h: minute(h, 101)}
    forced = decide_p1(START, 100, h, 101, complete)
    assert forced.exit_reason == "common_horizon_cap" and forced.exit_price == 101


def test_p2_no_activation_below_one_percent_and_exact_activation() -> None:
    h = START + 15 * M
    below = {START + M5: bar5(START + M5, 100, high=100.999), START + 2 * M5: bar5(START + 2 * M5, 100)}
    forced = decide_p2(START, 100, h, 100, below, {h: minute(h)})
    assert forced.activated_ms is None and forced.exit_reason == "common_horizon_cap"
    exact = {START + M5: bar5(START + M5, 100.5, high=101), START + 2 * M5: bar5(START + 2 * M5, 99.99)}
    execution = START + 3 * M5
    triggered = decide_p2(START, 100, START + 20 * M, 100, exact, {execution: minute(execution, 99.8), START + 20 * M: minute(START + 20 * M)})
    assert triggered.activated_ms == START + 2 * M5
    assert triggered.exit_reason == "trail_trigger" and triggered.execution_ms == execution


def test_p2_once_active_peak_is_causal_equality_triggers_next_minute() -> None:
    h = START + 25 * M
    bars = {
        START + M5: bar5(START + M5, 101, high=101),
        START + 2 * M5: bar5(START + 2 * M5, 102, high=102),
        START + 3 * M5: bar5(START + 3 * M5, 100.98, high=101),
    }
    execution = START + 4 * M5
    result = decide_p2(START, 100, h, 100, bars, {execution: minute(execution, 100.9), h: minute(h)})
    assert result.execution_ms == execution and result.exit_reason == "trail_trigger"
    changed = deepcopy(bars); changed[START + 4 * M5] = bar5(START + 4 * M5, 1, high=10000)
    assert decide_p2(START, 100, h, 100, changed, {execution: minute(execution, 100.9), h: minute(h)}) == result


def test_p2_missing_execution_and_missing_bar_censor() -> None:
    h = START + 20 * M
    bars = {START + M5: bar5(START + M5, 99, high=101)}
    result = decide_p2(START, 100, h, 100, bars, {h: minute(h)})
    assert result.censor_reason == "execution_minute_missing_or_invalid"
    assert decide_p2(START, 100, h, 100, {}, {h: minute(h)}).censor_reason.startswith("missing_complete_5m_bar")


def test_p2_future_mutation_cannot_change_earlier_exit() -> None:
    h = START + 30 * M
    bars = {START + M5: bar5(START + M5, 99, high=101), START + 2 * M5: bar5(START + 2 * M5, 999, high=999)}
    execution = START + 2 * M5
    minutes = {execution: minute(execution, 99), h: minute(h)}
    before = decide_p2(START, 100, h, 100, bars, minutes)
    changed = deepcopy(bars); changed[START + 2 * M5]["close"] = 1
    assert decide_p2(START, 100, h, 100, changed, minutes) == before


def test_p3_one_negative_no_exit_two_negatives_exit_exactly() -> None:
    h = START + 20 * M
    bars = {START - M5: bar5(START - M5, 103), START: bar5(START, 102), START + M5: bar5(START + M5, 101)}
    execution = START + 2 * M5
    result = decide_p3(START, h, 100, bars, {execution: minute(execution, 100.5), h: minute(h)})
    assert result.exit_reason == "momentum_deterioration" and result.execution_ms == execution
    one = decide_p3(START, START + M5, 100, {START - M5: bar5(START - M5, 103), START: bar5(START, 102)}, {START + M5: minute(START + M5)})
    assert one.exit_reason == "common_horizon_cap"


def test_p3_equality_breaks_sequence_and_preentry_does_not_count_itself() -> None:
    h = START + 20 * M
    bars = {START - M5: bar5(START - M5, 100), START: bar5(START, 100), START + M5: bar5(START + M5, 99), START + 2 * M5: bar5(START + 2 * M5, 98)}
    execution = START + 3 * M5
    result = decide_p3(START, h, 100, bars, {execution: minute(execution), h: minute(h)})
    assert result.execution_ms == execution


def test_p3_gap_execution_h_force_and_future_invariance() -> None:
    h = START + 20 * M
    base = {START - M5: bar5(START - M5, 103), START: bar5(START, 102), START + M5: bar5(START + M5, 101)}
    execution = START + 2 * M5
    assert decide_p3(START, h, 100, base, {h: minute(h)}).censored
    forced_bars = {START - M5: bar5(START - M5, 100), START: bar5(START, 101), START + M5: bar5(START + M5, 102), START + 2 * M5: bar5(START + 2 * M5, 103)}
    forced = decide_p3(START, h, 99, forced_bars, {h: minute(h, 99)})
    assert forced.exit_reason == "common_horizon_cap"
    minutes = {execution: minute(execution), h: minute(h)}
    before = decide_p3(START, h, 100, base, minutes)
    changed = deepcopy(base); changed[START + M5 * 2] = bar5(START + M5 * 2, 999)
    assert decide_p3(START, h, 100, changed, minutes) == before
    missing_bar = {START - M5: bar5(START - M5, 100), START: bar5(START, 99)}
    assert decide_p3(START, h, 100, missing_bar, {h: minute(h)}).censor_reason.startswith("missing_complete_5m_bar")


def test_candidate_held_metrics_can_differ_while_common_horizon_stays_immutable() -> None:
    common = [minute(START + M, high=101, low=100), minute(START + 2 * M, high=105, low=99)]
    candidate = evaluate_path(entry_ms=START, entry_price=100, exit_ms=START + 2 * M, exit_price=101,
                              minute_rows=common[:1], common_exit_ms=START + 3 * M,
                              common_exit_price=99, common_minute_rows=common)
    p0 = evaluate_path(entry_ms=START, entry_price=100, exit_ms=START + 3 * M, exit_price=99,
                       minute_rows=common)
    assert candidate["held_mfe"] != p0["held_mfe"]
    assert candidate["common_horizon_mfe"] == p0["common_horizon_mfe"]
    assert candidate["common_horizon_mae"] == p0["common_horizon_mae"]


def test_hand_paths_cover_rescue_damage_and_identical_outcomes() -> None:
    h = START + 3 * M
    rescue = decide_p1(START, 100, h, 99, {START + M: minute(START + M, high=102), h: minute(h, 99)})
    damage = decide_p1(START, 100, h, 105, {START + M: minute(START + M, low=99), h: minute(h, 105)})
    identical = decide_p1(START, 100, h, 100, {START + M: minute(START + M), START + 2*M: minute(START + 2*M), h: minute(h)})
    assert rescue.exit_price / 100 - 1 > 0 and 99 / 100 - 1 < 0
    assert damage.exit_price / 100 - 1 < 0 and 105 / 100 - 1 > 0
    assert identical.execution_ms == h and identical.exit_price == 100


def test_policy_decision_interfaces_cannot_receive_final_opportunity_metrics() -> None:
    forbidden = {"mfe", "mae", "common_horizon_mfe", "final_mfe", "held_mfe"}
    for function in (decide_p1, decide_p2, decide_p3):
        assert forbidden.isdisjoint(inspect.signature(function).parameters)
