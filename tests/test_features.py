import math

import pytest

from binance_data_foundation.features import compute_symbol_features


def _row(symbol: str, minute: int, close: float) -> dict:
    open_ms = 1_735_689_600_000 + minute * 60_000
    return {
        "symbol": symbol,
        "open_time_ms": open_ms,
        "open_time_utc": f"t{minute}",
        "close_time_utc": f"t{minute}-close",
        "close": close,
    }


def test_log_return_warmup_and_hand_values() -> None:
    rows = [_row("BTCUSDT", i, float(i + 1)) for i in range(22)]
    out = compute_symbol_features(rows)
    assert out[0]["ret_1_log"] == ""
    assert float(out[1]["ret_1_log"]) == pytest.approx(math.log(2 / 1))
    assert out[4]["ret_5_log"] == ""
    assert float(out[5]["ret_5_log"]) == pytest.approx(math.log(6 / 1))
    assert out[20]["vol_20_ret_1_log"] != ""


def test_five_bar_returns_are_indexed_consecutive_windows() -> None:
    rows = [_row("BTCUSDT", i, float(i + 1)) for i in range(8)]
    out = compute_symbol_features(rows)
    assert float(out[5]["ret_5_log"]) == pytest.approx(math.log(6 / 1))
    assert float(out[6]["ret_5_log"]) == pytest.approx(math.log(7 / 2))
    assert float(out[7]["ret_5_log"]) == pytest.approx(math.log(8 / 3))


def test_gap_resets_windows() -> None:
    rows = [_row("ETHUSDT", i, 100 + i) for i in range(6)]
    rows.append(_row("ETHUSDT", 10, 200))
    rows.extend(_row("ETHUSDT", i, 200 + i) for i in range(11, 16))
    out = compute_symbol_features(rows)
    assert out[6]["ret_1_log"] == ""
    assert out[10]["ret_5_log"] == ""
    assert float(out[11]["ret_5_log"]) == pytest.approx(math.log(215 / 200))


def test_nonpositive_prices_make_features_unavailable() -> None:
    rows = [_row("SOLUSDT", i, close) for i, close in enumerate([1, 2, 0, 4, 5, 6])]
    out = compute_symbol_features(rows)
    assert out[2]["ret_1_log"] == ""
    assert out[5]["ret_5_log"] == ""
    recovery = [_row("SOLUSDT", i, close) for i, close in enumerate([1, 2, 0, 4, 5, 6, 7, 8, 9, 10, 11])]
    recovered = compute_symbol_features(recovery)
    assert float(recovered[10]["ret_5_log"]) == pytest.approx(math.log(11 / 6))


def test_append_or_later_change_does_not_rewrite_prior_features() -> None:
    base = [_row("XRPUSDT", i, 50 + i) for i in range(8)]
    first = compute_symbol_features(base)
    changed_later = base + [_row("XRPUSDT", 8, 1000)]
    second = compute_symbol_features(changed_later)
    assert second[: len(first)] == first


def test_future_modification_does_not_rewrite_prior_features() -> None:
    base = [_row("XRPUSDT", i, 50 + i) for i in range(12)]
    changed = list(base)
    changed[9] = _row("XRPUSDT", 9, 999)
    assert compute_symbol_features(base)[:9] == compute_symbol_features(changed)[:9]


def test_symbol_isolation_and_duplicate_rejection() -> None:
    with pytest.raises(ValueError, match="one symbol"):
        compute_symbol_features([_row("AAA", 0, 1), _row("BBB", 1, 2)])
    with pytest.raises(ValueError, match="duplicate"):
        compute_symbol_features([_row("AAA", 0, 1), _row("AAA", 0, 2)])


def test_sample_stddev_ddof_one_and_constant_sequence() -> None:
    constant = [_row("AAA", i, 2.0**i) for i in range(21)]
    out = compute_symbol_features(constant)
    assert float(out[20]["vol_20_ret_1_log"]) == pytest.approx(0.0)
    closes = [100.0]
    for i in range(1, 22):
        closes.append(closes[-1] * (1 + i / 1000))
    varied = [_row("AAA", i, close) for i, close in enumerate(closes)]
    varied_out = compute_symbol_features(varied)
    rets = [math.log(closes[i] / closes[i - 1]) for i in range(1, 21)]
    mean = sum(rets) / len(rets)
    expected = math.sqrt(sum((x - mean) ** 2 for x in rets) / 19)
    assert float(varied_out[20]["vol_20_ret_1_log"]) == pytest.approx(expected)


def test_availability_is_next_interval_boundary() -> None:
    out = compute_symbol_features([_row("AAA", 0, 1)])
    assert out[0]["available_after_utc"] == "2025-01-01T00:01:00+00:00"
