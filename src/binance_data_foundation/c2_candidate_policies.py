from __future__ import annotations

from dataclasses import dataclass

from .c2_common import valid_minute


P1_VERSION = "P1_BRACKET_TP2_SL1_V1"
P2_VERSION = "P2_M5_TRAIL1_AFTER_GAIN1_V1"
P3_VERSION = "P3_M5_MOMENTUM_DETERIORATION_V1"
MINUTE_MS = 60_000
FIVE_MINUTES_MS = 300_000


@dataclass(frozen=True)
class CandidateDecision:
    policy_version: str
    signal_ms: int | None
    decision_ms: int | None
    execution_ms: int | None
    exit_price: float | None
    exit_reason: str | None
    censored: bool = False
    censor_reason: str | None = None
    ambiguity_flag: str = "none"
    gap_through: bool = False
    activated_ms: int | None = None
    negative_sequence_count: int = 0


def decide_p1(
    entry_ms: int, entry_price: float, horizon_ms: int, horizon_price: float,
    minute_lookup: dict[int, dict],
) -> CandidateDecision:
    """Standing bracket chronology only; no opportunity metrics are accepted."""
    take_profit, stop_loss = entry_price * 1.02, entry_price * 0.99
    for ts in range(entry_ms + MINUTE_MS, horizon_ms, MINUTE_MS):
        row = minute_lookup.get(ts)
        if row is None or not valid_minute(row):
            return CandidateDecision(P1_VERSION, None, None, None, None, None, True, f"data_gap_at_{ts}")
        open_price = float(row["open"])
        if open_price >= take_profit:
            return CandidateDecision(P1_VERSION, ts, ts, ts, open_price, "take_profit_gap_through", gap_through=True)
        if open_price <= stop_loss:
            return CandidateDecision(P1_VERSION, ts, ts, ts, open_price, "stop_loss_gap_through", gap_through=True)
        touched_tp = float(row["high"]) >= take_profit
        touched_sl = float(row["low"]) <= stop_loss
        if touched_tp and touched_sl:
            return CandidateDecision(P1_VERSION, ts, ts, ts, stop_loss, "stop_loss",
                                     ambiguity_flag="ambiguous_both_hit_conservative")
        if touched_tp:
            return CandidateDecision(P1_VERSION, ts, ts, ts, take_profit, "take_profit")
        if touched_sl:
            return CandidateDecision(P1_VERSION, ts, ts, ts, stop_loss, "stop_loss")
    horizon = minute_lookup.get(horizon_ms)
    if horizon is None or not valid_minute(horizon):
        return CandidateDecision(P1_VERSION, None, horizon_ms, None, None, None, True, "common_horizon_minute_missing")
    return CandidateDecision(P1_VERSION, None, horizon_ms, horizon_ms, horizon_price, "common_horizon_cap")


def decide_p2(
    entry_ms: int, entry_price: float, horizon_ms: int, horizon_price: float,
    five_minute_bars: dict[int, dict], minute_lookup: dict[int, dict],
) -> CandidateDecision:
    """Causal completed-5m trailing decision; final/common metrics are not inputs."""
    running_peak = entry_price
    activated_ms = None
    first_open = entry_ms + FIVE_MINUTES_MS
    for open_ms in range(first_open, horizon_ms, FIVE_MINUTES_MS):
        available_ms = open_ms + FIVE_MINUTES_MS
        if available_ms >= horizon_ms:
            break
        bar = five_minute_bars.get(open_ms)
        if bar is None:
            return CandidateDecision(P2_VERSION, None, None, None, None, None, True,
                                     f"missing_complete_5m_bar_at_{open_ms}", activated_ms=activated_ms)
        running_peak = max(running_peak, float(bar["high"]))
        if activated_ms is None and running_peak >= entry_price * 1.01:
            activated_ms = available_ms
        if activated_ms is not None and float(bar["close"]) <= running_peak * 0.99:
            minute = minute_lookup.get(available_ms)
            if minute is None or not valid_minute(minute):
                return CandidateDecision(P2_VERSION, available_ms, available_ms, None, None, None, True,
                                         "execution_minute_missing_or_invalid", activated_ms=activated_ms)
            return CandidateDecision(P2_VERSION, available_ms, available_ms, available_ms,
                                     float(minute["open"]), "trail_trigger", activated_ms=activated_ms)
    horizon = minute_lookup.get(horizon_ms)
    if horizon is None or not valid_minute(horizon):
        return CandidateDecision(P2_VERSION, None, horizon_ms, None, None, None, True,
                                 "common_horizon_minute_missing", activated_ms=activated_ms)
    return CandidateDecision(P2_VERSION, None, horizon_ms, horizon_ms, horizon_price,
                             "common_horizon_cap", activated_ms=activated_ms)


def decide_p3(
    entry_ms: int, horizon_ms: int, horizon_price: float,
    five_minute_bars: dict[int, dict], minute_lookup: dict[int, dict],
) -> CandidateDecision:
    """Causal two-negative-return decision; final/common metrics are not inputs."""
    previous_bar = five_minute_bars.get(entry_ms - FIVE_MINUTES_MS)
    if previous_bar is None:
        return CandidateDecision(P3_VERSION, None, None, None, None, None, True, "missing_pre_entry_5m_close")
    previous_close = float(previous_bar["close"])
    previous_negative = False
    negative_sequences = 0
    for open_ms in range(entry_ms, horizon_ms, FIVE_MINUTES_MS):
        available_ms = open_ms + FIVE_MINUTES_MS
        if available_ms >= horizon_ms:
            break
        bar = five_minute_bars.get(open_ms)
        if bar is None:
            return CandidateDecision(P3_VERSION, None, None, None, None, None, True,
                                     f"missing_complete_5m_bar_at_{open_ms}", negative_sequence_count=negative_sequences)
        current_close = float(bar["close"])
        negative = current_close < previous_close
        if previous_negative and negative:
            negative_sequences += 1
            if available_ms < horizon_ms:
                minute = minute_lookup.get(available_ms)
                if minute is None or not valid_minute(minute):
                    return CandidateDecision(P3_VERSION, available_ms, available_ms, None, None, None, True,
                                             "execution_minute_missing_or_invalid", negative_sequence_count=negative_sequences)
                return CandidateDecision(P3_VERSION, available_ms, available_ms, available_ms,
                                         float(minute["open"]), "momentum_deterioration",
                                         negative_sequence_count=negative_sequences)
        previous_negative, previous_close = negative, current_close
    horizon = minute_lookup.get(horizon_ms)
    if horizon is None or not valid_minute(horizon):
        return CandidateDecision(P3_VERSION, None, horizon_ms, None, None, None, True,
                                 "common_horizon_minute_missing", negative_sequence_count=negative_sequences)
    return CandidateDecision(P3_VERSION, None, horizon_ms, horizon_ms, horizon_price,
                             "common_horizon_cap", negative_sequence_count=negative_sequences)
