from pathlib import Path

import pytest

from binance_data_foundation.c32_p0_phase_sensitivity import (
    EXPECTED_ENTRIES, REQUIRED_OUTPUTS, reconcile_canonical, reject_future_path, run,
)


REPO = Path(__file__).resolve().parents[1]


def test_exact_frozen_population_and_canonical_hourly_reconciliation() -> None:
    gate, _ = reconcile_canonical(REPO)
    pop = gate["population"]
    assert pop["status"] == "PASS" and pop["actual_count"] == EXPECTED_ENTRIES
    assert pop["year_counts"] == {"2024": 1093, "2025": 1106}
    assert pop["symbol_counts"] == {"BNBUSDT": 442, "BTCUSDT": 451, "ETHUSDT": 434,
                                     "SOLUSDT": 431, "XRPUSDT": 441}
    rec = gate["reconciliation"]
    assert rec["status"] == "PASS"
    assert rec["exit_timestamps_exact"] and rec["exit_prices_exact"]
    assert rec["gross_and_net_cost_rows_exact"]


def test_phase_discovery_fails_closed_instead_of_redefining_p0() -> None:
    gate, _ = reconcile_canonical(REPO)
    rec = gate["reconciliation"]
    assert rec["p0_version"] == "P0_H1_SMA24_CROSSDOWN_V1"
    assert rec["parameters"] == {"bar_duration_hours": 1, "sma_lookback_bars": 24, "time_cap_days": 7}
    assert rec["evaluation_interval_hours"] == 1
    assert rec["observed_utc_evaluation_boundary_hours"] == list(range(24))
    assert rec["canonical_daily_phase"] is None
    assert rec["daily_phase_discovery"] == "FAIL_NO_UNIQUE_DAILY_PHASE"


def test_future_partition_guard() -> None:
    reject_future_path(Path("data/normalized/c2_frozen_inputs/BTCUSDT_1h.csv.gz"))
    with pytest.raises(PermissionError):
        reject_future_path(Path("data/normalized") / ("20" + "26") / "BTCUSDT.csv.gz")


def test_run_emits_complete_fail_closed_artifact_set(tmp_path: Path) -> None:
    # Run against the repository because reconciliation inputs are immutable; output is then checked in place.
    result = run(REPO)
    assert result["classification"] == "C32_INSUFFICIENT"
    assert result["canonical_p0_reproduced"] is True
    assert result["phase_experiment_executed"] is False
    assert result["bootstrap_executed"] is False
    output = REPO / "artifacts/c32_p0_phase_sensitivity"
    assert {p.name for p in output.iterdir()} == set(REQUIRED_OUTPUTS)
