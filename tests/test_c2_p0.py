from __future__ import annotations

from copy import deepcopy

import pytest

from binance_data_foundation.c2_common import hash_rows
from binance_data_foundation.c2_costs import COST_SCENARIOS, apply_round_trip_costs
from binance_data_foundation.c2_p0 import HORIZON_COLUMNS, SEVEN_DAYS_MS, _complete_path, decide_p0
from binance_data_foundation.c2_path_metrics import evaluate_path


START = 1_704_067_200_000
HOUR = 3_600_000
MINUTE = 60_000


def hour(i: int, close: float) -> dict:
    start = START + i * HOUR
    return {"symbol": "AAAUSDT", "open_time_ms": start, "available_at_ms": start + HOUR,
            "open": close, "high": close, "low": close, "close": close,
            "base_volume": 1, "quote_volume": 1, "trade_count": 1}


def minute(ts: int, *, open_: float = 100, high: float | None = None, low: float | None = None, close: float | None = None) -> dict:
    high = open_ if high is None else high
    low = open_ if low is None else low
    close = open_ if close is None else close
    return {"symbol": "AAAUSDT", "open_time_ms": ts, "open": open_, "high": high, "low": low,
            "close": close, "base_volume": 1, "quote_volume": 1, "trade_count": 1}


def crossdown_hours() -> list[dict]:
    return [hour(i, close) for i, close in enumerate([100.0] * 24 + [99.0])]


def test_p0_crossdown_strict_inequality_equality_and_causal_availability() -> None:
    hours = crossdown_hours()
    decision_ms = START + 25 * HOUR
    result = decide_p0(START + 24 * HOUR, hours, {decision_ms: minute(decision_ms, open_=99)}, decision_ms)
    assert result.signal_ms == decision_ms
    assert result.decision_ms == hours[-1]["available_at_ms"]
    assert result.execution_ms == decision_ms
    assert result.reason == "sma24_crossdown"

    equal_hours = [hour(i, 100.0) for i in range(25)]
    entry_ms = START + 24 * HOUR
    cap_ms = entry_ms + SEVEN_DAYS_MS
    equal = decide_p0(entry_ms, equal_hours, {cap_ms: minute(cap_ms)}, cap_ms)
    assert equal.signal_ms is None
    assert equal.reason == "time_cap"


def test_exact_boundary_missing_minute_censors_without_skipping() -> None:
    decision_ms = START + 25 * HOUR
    result = decide_p0(START + 24 * HOUR, crossdown_hours(), {decision_ms + MINUTE: minute(decision_ms + MINUTE)}, decision_ms + MINUTE)
    assert result.execution_ms is None
    assert result.censor_reason == "p0_execution_minute_missing_or_invalid"


def test_invalid_exact_boundary_minute_censors() -> None:
    decision_ms = START + 25 * HOUR
    invalid = minute(decision_ms)
    invalid["high"] = 0
    result = decide_p0(START + 24 * HOUR, crossdown_hours(), {decision_ms: invalid}, decision_ms)
    assert result.censor_reason == "p0_execution_minute_missing_or_invalid"


def test_future_data_mutation_does_not_change_earlier_p0_exit() -> None:
    hours = crossdown_hours() + [hour(25, 1000), hour(26, 1)]
    decision_ms = START + 25 * HOUR
    before = decide_p0(START + 24 * HOUR, hours, {decision_ms: minute(decision_ms, open_=99)}, START + 27 * HOUR)
    changed = deepcopy(hours)
    changed[-1]["close"] = 999999
    after = decide_p0(START + 24 * HOUR, changed, {decision_ms: minute(decision_ms, open_=99)}, START + 27 * HOUR)
    assert before == after


def test_seven_day_exact_cap_and_missing_cap_and_dataset_end() -> None:
    entry_ms = START
    cap_ms = entry_ms + SEVEN_DAYS_MS
    no_signal = [hour(i, 100) for i in range(24 * 8)]
    capped = decide_p0(entry_ms, no_signal, {cap_ms: minute(cap_ms, open_=101)}, cap_ms)
    assert capped.execution_ms == cap_ms and capped.reason == "time_cap"
    missing = decide_p0(entry_ms, no_signal, {}, cap_ms + MINUTE)
    assert missing.censor_reason == "seven_day_cap_minute_missing_or_invalid"
    ended = decide_p0(entry_ms, no_signal, {}, cap_ms - MINUTE)
    assert ended.censor_reason == "dataset_end_before_seven_day_cap"


def test_p0_exit_before_cap_defines_immutable_horizon() -> None:
    decision_ms = START + 25 * HOUR
    result = decide_p0(START + 24 * HOUR, crossdown_hours(), {decision_ms: minute(decision_ms, open_=99)}, decision_ms)
    assert result.execution_ms < START + 24 * HOUR + SEVEN_DAYS_MS
    assert result.execution_ms == result.decision_ms


def test_complete_path_excludes_entry_and_exit_minute_ranges_and_detects_gap() -> None:
    lookup = {
        START: minute(START, high=999, low=1),
        START + MINUTE: minute(START + MINUTE, high=103, low=100),
        START + 2 * MINUTE: minute(START + 2 * MINUTE, high=999, low=1),
    }
    rows, gap = _complete_path(START, START + 2 * MINUTE, lookup)
    assert gap is None
    assert [int(row["open_time_ms"]) for row in rows] == [START + MINUTE]
    assert max(float(row["high"]) for row in rows) == 103
    rows, gap = _complete_path(START, START + 2 * MINUTE, {START: lookup[START]})
    assert not rows and gap == START + MINUTE


def test_hand_path_mfe_mae_green_red_timing_drawdown_and_p0_invariants() -> None:
    rows = [
        minute(START + MINUTE, open_=101, high=103, low=101, close=102),
        minute(START + 2 * MINUTE, open_=102, high=103, low=99.5, close=100),
    ]
    metrics = evaluate_path(entry_ms=START, entry_price=100, exit_ms=START + 3 * MINUTE, exit_price=99, minute_rows=rows)
    assert metrics["held_mfe"] == pytest.approx(0.03)
    assert metrics["common_horizon_mfe"] == pytest.approx(0.03)
    assert metrics["held_mae"] == pytest.approx(-0.01)
    assert metrics["common_horizon_mae"] == pytest.approx(-0.01)
    assert metrics["time_to_held_mfe_seconds"] == 60
    assert metrics["time_to_common_horizon_mfe_seconds"] == 60
    assert metrics["max_drawdown_from_post_entry_peak"] == pytest.approx(1 - 99 / 103)
    assert metrics["held_green_then_red"] is True
    assert metrics["common_opportunity_positive_exit_red"] is True
    assert metrics["held_peak_gain_surrendered"] == pytest.approx(0.04)
    assert metrics["common_opportunity_capture_gap"] == pytest.approx(0.04)


def test_non_green_losing_path_and_zero_tiny_mfe_retention() -> None:
    rows = [minute(START + MINUTE, open_=99, high=100, low=98, close=99)]
    metrics = evaluate_path(entry_ms=START, entry_price=100, exit_ms=START + 2 * MINUTE, exit_price=99, minute_rows=rows)
    assert metrics["held_mfe"] == 0
    assert metrics["held_green_then_red"] is False
    assert metrics["held_peak_gain_retention"] is None
    assert metrics["held_retention_null_reason"] == "held_mfe_below_retention_threshold"
    tiny = evaluate_path(entry_ms=START, entry_price=100, exit_ms=START + 2 * MINUTE, exit_price=100,
                         minute_rows=[minute(START + MINUTE, high=100.49, low=100)])
    assert tiny["held_peak_gain_retention"] is None


def test_retention_is_valid_at_exact_half_percent_and_negative_is_not_clamped() -> None:
    metrics = evaluate_path(entry_ms=START, entry_price=100, exit_ms=START + 2 * MINUTE, exit_price=99,
                            minute_rows=[minute(START + MINUTE, high=100.5, low=99)])
    assert metrics["held_mfe"] == pytest.approx(0.005)
    assert metrics["held_peak_gain_retention"] == pytest.approx(-2.0)
    assert metrics["common_opportunity_capture_ratio"] == pytest.approx(-2.0)


def test_held_surrender_and_common_capture_gap_use_distinct_horizons() -> None:
    held_rows = [minute(START + MINUTE, high=101, low=100)]
    common_rows = held_rows + [minute(START + 2 * MINUTE, high=105, low=100)]
    metrics = evaluate_path(entry_ms=START, entry_price=100, exit_ms=START + 2 * MINUTE, exit_price=100,
                            minute_rows=held_rows, common_exit_ms=START + 3 * MINUTE,
                            common_exit_price=100, common_minute_rows=common_rows)
    assert metrics["held_peak_gain_surrendered"] == pytest.approx(0.01)
    assert metrics["common_opportunity_capture_gap"] == pytest.approx(0.05)


def test_costs_apply_adverse_slippage_and_quote_fees() -> None:
    base = next(s for s in COST_SCENARIOS if s.scenario_id == "C_BASE")
    result = apply_round_trip_costs(100, 99, 1000, base)
    assert result["entry_price_after_slippage"] == pytest.approx(100.02)
    assert result["exit_price_after_slippage"] == pytest.approx(98.9802)
    assert result["gross_return"] < result["raw_price_return"]
    assert result["net_return"] < result["gross_return"]
    assert result["entry_fee_usdt"] == pytest.approx(1.0)
    assert result["exit_fee_usdt"] == pytest.approx((1000 / 100.02) * 98.9802 * 0.001)
    assert result["fees_usdt"] == pytest.approx(result["entry_fee_usdt"] + result["exit_fee_usdt"])


def test_deterministic_common_horizon_semantic_hash() -> None:
    row = {column: "" for column in HORIZON_COLUMNS}
    row.update({"trade_id": "E1-x", "symbol": "AAAUSDT", "entry_execution_ms": START})
    assert hash_rows([row], HORIZON_COLUMNS) == hash_rows([deepcopy(row)], HORIZON_COLUMNS)
