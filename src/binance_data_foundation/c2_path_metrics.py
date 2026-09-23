from __future__ import annotations

import math


RETENTION_THRESHOLD = 0.005
THRESHOLDS = (("0_5pct", 0.005), ("1pct", 0.01), ("2pct", 0.02), ("3pct", 0.03))


def evaluate_path(
    *, entry_ms: int, entry_price: float, exit_ms: int, exit_price: float,
    minute_rows: list[dict], common_exit_ms: int | None = None,
    common_exit_price: float | None = None, common_minute_rows: list[dict] | None = None,
) -> dict:
    """Evaluate raw held/common paths; decision logic must never call this function."""
    common_exit_ms = exit_ms if common_exit_ms is None else common_exit_ms
    common_exit_price = exit_price if common_exit_price is None else common_exit_price
    common_minute_rows = minute_rows if common_minute_rows is None else common_minute_rows
    held = _path(entry_ms, entry_price, exit_ms, exit_price, minute_rows)
    common = _path(entry_ms, entry_price, common_exit_ms, common_exit_price, common_minute_rows)
    raw_return = exit_price / entry_price - 1
    result = {
        "held_mfe": held["mfe"], "held_mae": held["mae"],
        "common_horizon_mfe": common["mfe"], "common_horizon_mae": common["mae"],
        "time_to_held_mfe_seconds": held["time_to_mfe_seconds"],
        "time_to_common_horizon_mfe_seconds": common["time_to_mfe_seconds"],
        "holding_duration_seconds": (exit_ms - entry_ms) // 1000,
        "common_horizon_duration_seconds": (common_exit_ms - entry_ms) // 1000,
        "max_drawdown_from_post_entry_peak": held["max_drawdown"],
        "held_peak_gain_surrendered": held["mfe"] - raw_return,
        "common_opportunity_capture_gap": common["mfe"] - raw_return,
        "held_peak_gain_retention": raw_return / held["mfe"] if _retention_permitted(held["mfe"]) else None,
        "held_retention_null_reason": None if _retention_permitted(held["mfe"]) else "held_mfe_below_retention_threshold",
        "common_opportunity_capture_ratio": raw_return / common["mfe"] if _retention_permitted(common["mfe"]) else None,
        "common_retention_null_reason": None if _retention_permitted(common["mfe"]) else "common_mfe_below_retention_threshold",
        "held_ever_green": held["mfe"] > 0,
        "common_opportunity_ever_green": common["mfe"] > 0,
        "held_green_then_red": held["mfe"] > 0 and raw_return < 0,
        "common_opportunity_positive_exit_red": common["mfe"] > 0 and raw_return < 0,
        "held_mfe_timing": held["mfe_timing"],
        "common_mfe_timing": common["mfe_timing"],
        "ambiguity_flag": "ohlc_extremes_localized_to_minute_no_intraminute_order" if minute_rows or common_minute_rows else "none",
    }
    for label, threshold in THRESHOLDS:
        result[f"held_ever_above_{label}"] = held["mfe"] >= threshold
        result[f"common_opportunity_above_{label}"] = common["mfe"] >= threshold
    return result


def _retention_permitted(mfe: float) -> bool:
    return mfe >= RETENTION_THRESHOLD or math.isclose(mfe, RETENTION_THRESHOLD, rel_tol=0.0, abs_tol=1e-15)


def _path(entry_ms: int, entry_price: float, exit_ms: int, exit_price: float, rows: list[dict]) -> dict:
    if exit_ms < entry_ms:
        raise ValueError("exit cannot precede entry")
    peak = entry_price
    trough = entry_price
    max_drawdown = 0.0
    mfe_price = entry_price
    mfe_ms = entry_ms
    mfe_timing = "exact_entry_anchor"
    for row in rows:
        ts = int(row["open_time_ms"])
        if not entry_ms < ts < exit_ms:
            raise ValueError("path rows must be complete minutes strictly after entry and before exit")
        high, low = float(row["high"]), float(row["low"])
        # Compare the current low only with peaks known before this OHLC minute;
        # this avoids inventing high-before-low ordering within the minute.
        max_drawdown = max(max_drawdown, 1 - low / peak)
        if high > mfe_price:
            mfe_price, mfe_ms, mfe_timing = high, ts, "localized_to_1m_interval"
        peak = max(peak, high)
        trough = min(trough, low)
    max_drawdown = max(max_drawdown, 1 - exit_price / peak)
    if exit_price > mfe_price:
        mfe_price, mfe_ms, mfe_timing = exit_price, exit_ms, "exact_execution_boundary"
    trough = min(trough, exit_price)
    return {
        "mfe": max(mfe_price / entry_price - 1, 0.0),
        "mae": min(trough / entry_price - 1, 0.0),
        "time_to_mfe_seconds": (mfe_ms - entry_ms) // 1000,
        "mfe_timing": mfe_timing,
        "max_drawdown": max_drawdown,
    }
