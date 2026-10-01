from pathlib import Path

import numpy as np
import pytest

from binance_data_foundation import c33_p0_hourly_phase_sensitivity as c33


def minute_fixture(n=180):
    ts = np.arange(n, dtype=np.int64) * 60_000
    x = np.arange(n, dtype=float) + 100
    return {"ts": ts, "open": x, "high": x + 2, "low": x - 2, "close": x + 1,
            "volume": np.ones(n), "quote": np.ones(n) * 10, "trades": np.ones(n, dtype=np.int64)}


@pytest.mark.parametrize("phase", range(60))
def test_all_phase_lattices_exact_duration_cadence_and_ohlcv(phase):
    m = minute_fixture(240)
    b = c33.construct_phase_bars(m, phase)
    assert np.all(b["boundary_ms"] - b["open_ms"] == 3_600_000)
    assert np.all(np.diff(b["boundary_ms"]) == 3_600_000)
    assert np.all(b["source_rows"] == 60)
    j = 0; lo = np.searchsorted(m["ts"], b["open_ms"][j]); hi = lo + 60
    assert b["open"][j] == m["open"][lo]
    assert b["high"][j] == max(m["high"][lo:hi])
    assert b["low"][j] == min(m["low"][lo:hi])
    assert b["close"][j] == m["close"][hi - 1]
    assert b["volume"][j] == sum(m["volume"][lo:hi])


def test_exact_24_completed_bar_sma_and_causality():
    b = c33.construct_phase_bars(minute_fixture(1800), 17)
    assert np.isnan(b["sma24"][:23]).all()
    assert b["sma24"][23] == pytest.approx(np.mean(b["close"][:24]))
    altered = minute_fixture(1800); altered["close"][-1] = 1e9
    b2 = c33.construct_phase_bars(altered, 17)
    assert np.array_equal(b["close"][:-1], b2["close"][:-1])


def test_phase_offsets_and_guards():
    m = minute_fixture(240)
    assert c33.construct_phase_bars(m, 1)["boundary_ms"][0] % 3_600_000 == 60_000
    assert c33.construct_phase_bars(m, 59)["boundary_ms"][0] % 3_600_000 == 59 * 60_000
    with pytest.raises(PermissionError):
        c33.reject_2026(Path("data") / ("20" + "26") / "x.csv")


def test_paired_stats_smoothness_neighborhood_and_pcg64_bootstrap():
    x = np.arange(120, dtype=float).reshape(2, 60) / 10000
    years = np.asarray(["2024", "2025"]); months = np.asarray(["2024-01", "2025-01"])
    s = c33._smoothness(x.mean(axis=0)); assert s["adjacent_smoothness_ratio"] > 0
    one = c33._bootstrap(x, years, months, "trade")
    two = c33._bootstrap(x, years, months, "trade")
    assert one["iterations"] == 2000 and one["generator"] == "PCG64"
    assert one["replicate_hashes"] == two["replicate_hashes"]


def test_frozen_configuration_has_no_adaptation_or_cadence_change():
    assert c33.PHASES == tuple(range(60))
    assert c33.HOUR_MS == 60 * c33.MINUTE_MS
    assert c33.REPLICATES == 2000
    assert c33.EXPECTED_FROZEN_ENTRY_HASH == "6885678a43b0d2f40b34e65adf15247072cdec2bbc8437cafd8cb69d8fba5da3"
