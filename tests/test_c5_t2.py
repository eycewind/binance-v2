from __future__ import annotations

from pathlib import Path

from binance_data_foundation.c5_t1 import POLICIES
from binance_data_foundation.c5_t2 import CUTOFFS, EXPECTED, T1_SHA, _evaluation


def test_frozen_t2_registry_cutoffs_and_population() -> None:
    assert POLICIES == ("P0_HELD_V1", "G1_Q75_EXIT_V1", "P1_Q75_EXIT_V1", "G1_Q90_EXIT_V1", "P1_Q90_EXIT_V1")
    assert CUTOFFS == {
        "G1_Q75_EXIT_V1": 0.38599566214835807,
        "G1_Q90_EXIT_V1": 0.5437961868373885,
        "P1_Q75_EXIT_V1": 0.3962652238189601,
        "P1_Q90_EXIT_V1": 0.5665730461166496,
    }
    assert EXPECTED["pooled"] == {"trades": 439, "snapshots": 38745}
    assert EXPECTED["by_symbol"] == {"BTCUSDT":74,"ETHUSDT":85,"SOLUSDT":106,"XRPUSDT":87,"BNBUSDT":87}


def test_accepted_readiness_hash_is_frozen() -> None:
    assert T1_SHA == "8c63b9e39b0b5365014c05c74bc1c57907ad9072109d3dbc8c2c430c385f6b4a"


def test_future_opportunity_starts_strictly_after_exit() -> None:
    entry={"entry_price":"100","entry_execution_ms":"0"}
    horizon={"p0_execution_ms":"240000","p0_raw_exit_price":"101","common_horizon_mfe":"0.06"}
    row={"raw_exit_price":102.0,"exit_execution_ms":60000}
    minutes={60000:{"high":"999"},120000:{"high":"105"},180000:{"high":"106"}}
    got=_evaluation(row,entry,horizon,minutes)
    assert got["future_max_price_after_exit_to_H"] == 106
    assert got["subsequent_plus_5"] is True
    assert got["preserved_at_least_half_peak"] is False


def test_no_sealed_path_literal_in_t2_implementation() -> None:
    source=Path("src/binance_data_foundation/c5_t2.py").read_text()
    assert "sealed_confirmation_access\":False" in source
    assert "data/sealed" not in source
