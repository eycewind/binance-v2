from pathlib import Path

import pytest

from binance_data_foundation import c7_t1 as c7
from binance_data_foundation.c19_target_definition_review import build_artifacts, reject_2026


def test_incremental_cost_decomposition_matches_frozen_ledger():
    entry, now, p0, notional = 100.0, 107.0, 103.0, 1000.0
    fee = c7.COSTS["C_BASE"]["fee_rate"]
    slip = c7.COSTS["C_BASE"]["slippage_rate"]
    quantity = notional / (entry * (1 + slip))
    direct = c7.cost_ledger(entry, p0, "C_BASE")["net_return"] - c7.cost_ledger(entry, now, "C_BASE")["net_return"]
    reduced = quantity * (1 - slip) * (1 - fee) * (p0 - now) / notional
    assert direct == pytest.approx(reduced)


def test_review_is_methodology_only_and_recommends_no_selection(monkeypatch):
    monkeypatch.setenv("CONDA_DEFAULT_ENV", "binance-v2-research")
    files = build_artifacts(Path.cwd())
    assert files["c18_reinterpretation"]["accounting_valid"] is True
    assert files["c20_recommendation"]["executed"] is False
    assert files["final_summary"]["confirmations"]["candidate_horizons_evaluated"] is False


def test_no_2026_path_access():
    with pytest.raises(PermissionError):
        reject_2026(Path("data/2026/metadata.json"))
