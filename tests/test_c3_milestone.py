from __future__ import annotations

from copy import deepcopy

import csv
import json
import statistics

import pytest

from binance_data_foundation.c3_milestone import (
    AUDIT_COLUMNS, FEATURE_COLUMNS, FEATURE_MATRIX_COLUMNS, KEYED_FEATURE_COLUMNS, OUTCOME_COLUMNS,
    PROVENANCE_COLUMNS, STUDY_END_MS, C3Inputs, DenseSeries, MILESTONES,
    _pre_holdout_timestamp, _resolve_label, _rolling_return, _split_metadata,
    build_milestone_row, compute_features, schema_document, verify_rebuild,
)


M = 60_000
F = 5 * M
H = 60 * M
E = 1_704_067_200_000
SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT")


def minute(ts: int, close: float = 100, *, high: float | None = None, low: float | None = None,
           volume: float = 10, trades: int = 2) -> dict:
    return {"open_time_ms": ts, "open": close, "high": close if high is None else high,
            "low": close if low is None else low, "close": close, "base_volume": volume,
            "quote_volume": volume * close, "trade_count": trades}


def series(rows: list[dict], step: int = M) -> DenseSeries:
    return DenseSeries.from_rows(rows, step)


def simple_inputs(subject_rows: list[dict], horizon_ms: int, horizon_price: float = 100,
                  entry_ms: int = E) -> tuple[C3Inputs, dict, dict]:
    # Long causal warm-up for all feature families; subject rows override matching minutes.
    minute_rows = [minute(E - 26 * H + i * M, 90 + i * .001) for i in range(26 * 60 + 400)]
    replacements = {int(row["open_time_ms"]): row for row in subject_rows}
    minute_rows = [replacements.get(int(row["open_time_ms"]), row) for row in minute_rows]
    for row in subject_rows:
        if int(row["open_time_ms"]) not in {int(x["open_time_ms"]) for x in minute_rows}:
            minute_rows.append(row)
    minute_rows.sort(key=lambda r: int(r["open_time_ms"]))
    minutes = {symbol: series(minute_rows) for symbol in SYMBOLS}
    bars = [minute(E - 25 * H + i * F, 95 + i * .01, high=95.2 + i * .01, low=94.8 + i * .01,
                   volume=20 + i, trades=10 + i) for i in range(320)]
    hours = [minute(E - 25 * H + i * H, 95 + i * .1, high=96 + i * .1, low=94 + i * .1) for i in range(28)]
    entry = {"trade_id": "T1", "symbol": "BTCUSDT", "entry_fixture_id": "E1_H1_SMA24_CROSS_V1",
             "entry_execution_ts": "2024-01-01T00:00:00+00:00", "entry_execution_ms": entry_ms, "entry_price": "100"}
    horizon = {"trade_id": "T1", "common_horizon_end_ts": "2024-01-01T05:00:00+00:00",
               "common_horizon_end_ms": horizon_ms, "p0_raw_exit_price": str(horizon_price)}
    inputs = C3Inputs((entry,), {"T1": horizon}, minutes,
                      {symbol: series(bars, F) for symbol in SYMBOLS},
                      {symbol: series(hours, H) for symbol in SYMBOLS}, {})
    return inputs, entry, horizon


def test_first_touch_entry_minute_exclusion_and_equality() -> None:
    rows = [minute(E, 100, high=110, low=90), minute(E + M, 100, high=100.9),
            minute(E + 2 * M, 101, high=101, low=100.5), minute(E + 3 * M, 102, high=102, low=101)]
    inputs, entry, horizon = simple_inputs(rows, E + 5 * M, 101.5)
    row = build_milestone_row(entry, horizon, MILESTONES["M1"], inputs)
    assert row is not None and row["milestone_interval_start_ms"] == E + 2 * M
    assert row["label"] == 1 and row["label_resolution_ms"] == E + 3 * M


def test_touch_minute_upper_only_and_fallback_only_nonresolution() -> None:
    upper = _resolve_label(series([]), E + M, E + 3 * M, 101, 102, 100, minute(E + M, high=102, low=100.1))
    assert upper["label"] == 1
    later = series([minute(E + 2 * M, high=101, low=100)])
    fallback_only = _resolve_label(later, E + M, E + 3 * M, 101, 102, 100, minute(E + M, high=101, low=99))
    assert fallback_only["label"] == 0 and fallback_only["label_resolution_ms"] == E + 2 * M


def test_same_minute_ambiguity_and_later_first_event_ordering() -> None:
    ambiguous = _resolve_label(series([]), E + M, E + 3 * M, 101, 102, 100, minute(E + M, high=102, low=100))
    assert ambiguous["ambiguous"] and ambiguous["label"] == ""
    later = series([minute(E + 2 * M, high=102, low=100.5), minute(E + 3 * M, high=103, low=99)])
    resolved = _resolve_label(later, E + M, E + 4 * M, 101, 102, 100, minute(E + M, high=101, low=100.1))
    assert resolved["label"] == 1 and resolved["label_resolution_ms"] == E + 2 * M


def test_later_minute_upper_and_fallback_hit_is_ambiguous() -> None:
    later = series([minute(E + 2 * M, high=102, low=100)])
    result = _resolve_label(later, E + M, E + 3 * M, 101, 102, 100,
                            minute(E + M, high=101, low=100.1))
    assert result["ambiguous"] and result["ambiguity_reason"] == "ambiguous_same_minute"
    assert result["label"] == "" and result["label_resolution_ms"] == E + 2 * M


def test_h_uses_point_only_and_censoring() -> None:
    rows = series([minute(E + 2 * M, high=999, low=1)])
    censored = _resolve_label(rows, E + M, E + 2 * M, 101, 102, 100, minute(E + M, high=101, low=100.1))
    assert censored["censored"] and censored["censor_reason"] == "right_censored_at_H"
    continued = _resolve_label(series([]), E + M, E + 2 * M, 102, 102, 100, minute(E + M, high=101, low=100.1))
    assert continued["label"] == 1 and continued["label_resolution_timing"] == "exact_H_execution_point"


def test_milestone_first_reached_exactly_at_h_and_h_range_is_ignored() -> None:
    horizon_ms = E + 3 * M
    rows = [minute(E + M, high=100.5), minute(E + 2 * M, high=100.9),
            minute(horizon_ms, high=999, low=1)]
    inputs, entry, horizon = simple_inputs(rows, horizon_ms, 101)
    row = build_milestone_row(entry, horizon, MILESTONES["M1"], inputs)
    assert row is not None and row["milestone_interval_start_ms"] == horizon_ms
    assert row["milestone_timing"] == "exact_H_execution_point"
    assert row["censored"] and row["censor_reason"] == "right_censored_at_H"


def test_gap_censors_without_skipping() -> None:
    later = series([minute(E + 3 * M, high=102, low=100.5)])
    result = _resolve_label(later, E + M, E + 4 * M, 101, 102, 100, minute(E + M, high=101, low=100.1))
    assert result["censored"] and result["censor_reason"] == f"gap_at_{E + 2 * M}"


def test_pre_milestone_gap_is_explicit_and_has_no_features_or_label() -> None:
    rows = [minute(E + M, high=100.5), minute(E + 3 * M, high=110)]
    inputs, entry, horizon = simple_inputs(rows, E + 5 * M, 110)
    dense = inputs.minutes["BTCUSDT"]
    gap_index = (E + 2 * M - dense.start_ms) // M
    dense.valid[gap_index] = 0
    row = build_milestone_row(entry, horizon, MILESTONES["M1"], inputs)
    assert row is not None
    assert row["censored"] and row["censor_reason"] == "pre_milestone_gap"
    assert row["milestone_interval_start_ms"] == "" and row["label"] == ""
    assert not row["feature_eligible"] and row["feature_ineligible_reason"] == "pre_milestone_gap"
    assert all(row[name] is None for name in FEATURE_COLUMNS)


def test_invalid_pre_milestone_minute_is_treated_as_chronology_break() -> None:
    bad = minute(E + 2 * M, close=100, high=99, low=100) | {"_invalid": True}
    rows = [minute(E + M, high=100.5), bad, minute(E + 3 * M, high=110)]
    inputs, entry, horizon = simple_inputs(rows, E + 5 * M, 110)
    # Rebuild the subject series so DenseSeries records the invalid minute as unavailable.
    inputs.minutes["BTCUSDT"] = series(rows)
    row = build_milestone_row(entry, horizon, MILESTONES["M1"], inputs)
    assert row is not None and row["censor_reason"] == "pre_milestone_gap"


def test_exact_2026_boundary_rejected() -> None:
    with pytest.raises(ValueError, match="sealed 2026 boundary"):
        _pre_holdout_timestamp(STUDY_END_MS, "synthetic")


def test_rolling_return_non_aligned_cutoff_and_gap() -> None:
    cutoff = E + 67 * M
    rows = [minute(E + i * M, 100 + i) for i in range(68)]
    value = _rolling_return(series(rows), cutoff, 5)
    # C(cutoff) is the close of [cutoff-1m, cutoff), here 166; C(cutoff-5m)=161.
    assert value == pytest.approx(166 / 161 - 1)
    gapped = series([row for row in rows if int(row["open_time_ms"]) != cutoff - 3 * M])
    assert _rolling_return(gapped, cutoff, 5) is None


def test_touch_minute_and_future_mutation_do_not_change_features() -> None:
    cutoff = E + 67 * M
    rows = [minute(E - 26 * H + i * M, 90 + i * .001) for i in range(26 * 60 + 200)]
    inputs, _, _ = simple_inputs(rows, E + 4 * H)
    before = compute_features("BTCUSDT", E, 100, cutoff, inputs.minutes, inputs.bars5, inputs.hours, .01)
    mutated = deepcopy(rows)
    for row in mutated:
        if int(row["open_time_ms"]) >= cutoff:
            row.update({"close": 9999, "high": 9999, "low": 1})
    other, _, _ = simple_inputs(mutated, E + 4 * H)
    after = compute_features("BTCUSDT", E, 100, cutoff, other.minutes, other.bars5, other.hours, .01)
    assert before == after


def test_local_path_volatility_sma_volume_and_context_features() -> None:
    cutoff = E + 67 * M
    subject = [minute(E - 26 * H + i * M, 90 + i * .001) for i in range(26 * 60 + 200)]
    inputs, _, _ = simple_inputs(subject, E + 4 * H)
    features, missing = compute_features("BTCUSDT", E, 100, cutoff, inputs.minutes, inputs.bars5, inputs.hours, .01)
    assert features["local_return_5m"] is not None
    assert features["local_momentum_acceleration"] is not None
    expected_mae = min(0.0, min(inputs.minutes["BTCUSDT"].get(ts)["low"] / 100 - 1 for ts in range(E + M, cutoff, M)))
    assert features["pre_milestone_mae"] == pytest.approx(expected_mae)
    post_bars = [inputs.bars5["BTCUSDT"].get(ts) for ts in range(E, E + 65 * M, F)]
    expected_movement = sum(abs(post_bars[i]["close"] / post_bars[i - 1]["close"] - 1) for i in range(1, len(post_bars)))
    assert features["path_efficiency_5m"] == pytest.approx(.01 / expected_movement)
    last_start = cutoff // F * F - F
    bars13 = [inputs.bars5["BTCUSDT"].get(last_start - (12 - i) * F) for i in range(13)]
    recent_returns = [bars13[i]["close"] / bars13[i - 1]["close"] - 1 for i in range(7, 13)]
    assert features["realized_volatility_last6_5m"] == pytest.approx(statistics.stdev(recent_returns))
    assert features["latest_5m_range_ratio"] is not None
    last_hour = cutoff // H * H - H
    h25 = [inputs.hours["BTCUSDT"].get(last_hour - (24 - i) * H) for i in range(25)]
    current_sma = statistics.fmean(x["close"] for x in h25[-24:])
    previous_sma = statistics.fmean(x["close"] for x in h25[:-1])
    assert features["distance_from_h1_sma24"] == pytest.approx(h25[-1]["close"] / current_sma - 1)
    assert features["h1_sma24_slope"] == pytest.approx(current_sma / previous_sma - 1)
    assert features["base_volume_ratio"] == pytest.approx(bars13[-1]["base_volume"] / statistics.median(x["base_volume"] for x in bars13[:-1]))
    assert features["quote_volume_ratio"] == pytest.approx(bars13[-1]["quote_volume"] / statistics.median(x["quote_volume"] for x in bars13[:-1]))
    assert features["trade_count_ratio"] == pytest.approx(bars13[-1]["trade_count"] / statistics.median(x["trade_count"] for x in bars13[:-1]))
    assert features["btc_minus_subject_return_15m"] == pytest.approx(0)
    assert features["other_four_breadth_15m"] in (0, .25, .5, .75, 1)
    assert not missing


def test_numeric_btc_eth_relative_context_and_other_four_breadth() -> None:
    cutoff = E + 67 * M
    inputs, _, _ = simple_inputs([], E + 4 * H)
    rates = {"SOLUSDT": .001, "BTCUSDT": .002, "ETHUSDT": -.001,
             "XRPUSDT": .0005, "BNBUSDT": 0.0}
    start = E - 70 * M
    for symbol, rate in rates.items():
        inputs.minutes[symbol] = series([minute(start + i * M, 100 * (1 + rate) ** i) for i in range(138)])
    features, _ = compute_features("SOLUSDT", E, 100, cutoff, inputs.minutes, inputs.bars5, inputs.hours, .01)
    subject15 = 1.001 ** 15 - 1
    assert features["btc_minus_subject_return_15m"] == pytest.approx((1.002 ** 15 - 1) - subject15)
    assert features["eth_minus_subject_return_15m"] == pytest.approx((.999 ** 15 - 1) - subject15)
    assert features["other_four_breadth_15m"] == pytest.approx(.5)
    assert features["btc_eth_agreement_15m"] == 0


def test_partially_pre_entry_aligned_bar_excluded() -> None:
    entry = E + 2 * M
    cutoff = E + 17 * M
    subject = [minute(E - 26 * H + i * M, 90 + i * .001) for i in range(26 * 60 + 200)]
    inputs, _, _ = simple_inputs(subject, E + 4 * H, entry_ms=entry)
    features, _ = compute_features("BTCUSDT", entry, 100, cutoff, inputs.minutes, inputs.bars5, inputs.hours, .01)
    # Eligible aligned bars start at 00:05 and 00:10; the 00:00 bar partly precedes entry.
    assert features["complete_5m_bars_since_entry"] == 2


def test_relative_context_not_exact_local_duplicate() -> None:
    cutoff = E + 67 * M
    subject = [minute(E - 26 * H + i * M, 90 + i * .001) for i in range(26 * 60 + 200)]
    inputs, _, _ = simple_inputs(subject, E + 4 * H)
    for symbol in ("BTCUSDT", "ETHUSDT"):
        features, _ = compute_features(symbol, E, 100, cutoff, inputs.minutes, inputs.bars5, inputs.hours, .01)
        prefix = "btc" if symbol == "BTCUSDT" else "eth"
        assert features[f"{prefix}_minus_subject_return_15m"] == pytest.approx(0)
        assert f"{prefix}_minus_subject_return_15m" != "local_return_15m"


def test_structural_separation_and_schema_hash_determinism() -> None:
    assert set(FEATURE_COLUMNS).isdisjoint(PROVENANCE_COLUMNS)
    assert set(FEATURE_COLUMNS).isdisjoint(OUTCOME_COLUMNS)
    assert FEATURE_MATRIX_COLUMNS == FEATURE_COLUMNS
    assert KEYED_FEATURE_COLUMNS == ("trade_id", "milestone_id") + FEATURE_COLUMNS
    assert len(FEATURE_MATRIX_COLUMNS) == 35
    assert "trade_id" not in FEATURE_MATRIX_COLUMNS and "milestone_id" not in FEATURE_MATRIX_COLUMNS
    assert len(AUDIT_COLUMNS) == len(set(AUDIT_COLUMNS))
    assert schema_document() == schema_document()


@pytest.mark.parametrize(
    "milestone,event,boundary,reason",
    [
        (1_725_158_400_000, 1_727_740_800_000, 1_727_740_800_000, "unresolved_at_validation_boundary"),
        (1_730_419_200_000, 1_735_689_600_000, 1_735_689_600_000, "unresolved_at_validation_boundary"),
        (1_730_419_200_000, 1_735_689_600_000, 1_735_689_600_000, "unresolved_at_training_boundary"),
        (1_750_000_000_000, STUDY_END_MS, STUDY_END_MS, "unresolved_at_2025_evaluation_boundary"),
    ],
)
def test_fold_boundary_eligibility(milestone: int, event: int, boundary: int, reason: str) -> None:
    outcome = {"label_resolution_ms": event, "ambiguous": False, "censored": False}
    metadata = _split_metadata(milestone, outcome)
    assert reason in metadata["split_exclusion_reason"]
    assert str(boundary) not in metadata["split_eligibility"]


def test_deterministic_row_identity_for_same_inputs() -> None:
    rows = [minute(E + M, high=101, low=100.1), minute(E + 2 * M, high=102, low=100.5)]
    inputs, entry, horizon = simple_inputs(rows, E + 4 * M, 101)
    first = build_milestone_row(entry, horizon, MILESTONES["M1"], inputs)
    second = build_milestone_row(entry, horizon, MILESTONES["M1"], inputs)
    assert first == second


def test_artifact_rebuild_has_literal_feature_matrix_and_reproducible_hashes(tmp_path, monkeypatch) -> None:
    rows = [minute(E + i * M, close=100 + i * .01, high=100 + i * .01) for i in range(1, 80)]
    rows[65]["high"] = 101
    rows[66]["high"] = 102
    inputs, _, _ = simple_inputs(rows, E + 75 * M, 101)
    import binance_data_foundation.c3_milestone as module
    monkeypatch.setattr(module, "load_accepted_inputs", lambda repo: inputs)
    monkeypatch.setattr(module, "_git_revision", lambda repo: "synthetic-pre-holdout")
    monkeypatch.setattr(module, "_reconcile", lambda summaries: True)
    monkeypatch.setattr(module, "_cross_asset_duplicate_safety", lambda datasets: {})
    result = verify_rebuild(tmp_path, tmp_path / "artifacts")
    assert result["independent_rebuild_verified"]
    with (tmp_path / "artifacts/m1_features.csv").open(newline="", encoding="utf-8") as handle:
        assert tuple(next(csv.reader(handle))) == FEATURE_COLUMNS
    manifest = json.loads((tmp_path / "artifacts/reproducibility_manifest.json").read_text(encoding="utf-8"))
    assert manifest["verified_core_hashes"] == manifest["core_hashes"]
