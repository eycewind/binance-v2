from pathlib import Path
import inspect

import pytest

from binance_data_foundation import c28_strategy_economic_review as c28


def test_contract_entry_population_and_frozen_scope():
    assert c28.sha256_file(Path(c28.CONTRACT_REL)) == c28.CONTRACT_SHA256
    assert c28.EXPECTED_ENTRIES == 2199
    assert c28.ENTRY_SHA256 == "6885678a43b0d2f40b34e65adf15247072cdec2bbc8437cafd8cb69d8fba5da3"
    assert c28.HORIZONS == (6, 24, 72, 168) and c28.PRIMARY_HORIZON == 24
    assert c28.COST_IDS == ("C0", "C_BASE", "C_S5", "C_S10")


def _entry(ms=1_706_745_600_000):
    return {"trade_id": "e", "symbol": "BTCUSDT", "entry_execution_ms": str(ms), "entry_price": "100"}


def test_reference_pool_all_frozen_matching_and_exclusions():
    e = _entry()  # 2024-02-01 00:00 UTC
    day = 24 * 3_600_000
    candidates = [
        {"symbol": "BTCUSDT", "decision_ms": int(e["entry_execution_ms"]) + 7 * day, "e1_fired": False, "entry_valid": True},
        {"symbol": "ETHUSDT", "decision_ms": int(e["entry_execution_ms"]) + 7 * day, "e1_fired": False, "entry_valid": True},
        {"symbol": "BTCUSDT", "decision_ms": int(e["entry_execution_ms"]) + 7 * day + 3_600_000, "e1_fired": False, "entry_valid": True},
        {"symbol": "BTCUSDT", "decision_ms": int(e["entry_execution_ms"]) + 8 * day, "e1_fired": True, "entry_valid": True},
        {"symbol": "BTCUSDT", "decision_ms": int(e["entry_execution_ms"]) + 9 * day, "e1_fired": False, "entry_valid": False},
        {"symbol": "BTCUSDT", "decision_ms": int(e["entry_execution_ms"]) + day, "e1_fired": False, "entry_valid": True},
    ]
    got = c28.reference_pool(e, candidates, [int(e["entry_execution_ms"])], 24)
    assert got == candidates[:1]


def test_reference_pool_zero_handling_and_no_2026():
    assert c28.reference_pool(_entry(), [], [int(_entry()["entry_execution_ms"])], 24) == []
    with pytest.raises(PermissionError):
        c28.reject_2026("data/partition=2026/metadata.json")


def test_fixed_horizon_exact_timing_and_identical_cost_accounting():
    start = 1_700_000_000_000
    opens = {start + h * 3_600_000: 100 + h for h in c28.HORIZONS}
    for h in c28.HORIZONS:
        actual = c28.fixed_horizon_outcome(start, 100, h, opens, "C_BASE")
        reference = c28.fixed_horizon_outcome(start, 100, h, opens, "C_BASE")
        assert actual == reference and actual["exit_ms"] == start + h * 3_600_000
    assert c28.fixed_horizon_outcome(start, 100, 24, {}, "C0") is None


def test_equal_weight_reference_averaging_and_retention_arithmetic():
    rows = [{"trade_id": "a", "entry_month": "2024-01", "actual": {"C0": {"return": .03}}, "reference": {"C0": {"return": .01}}},
            {"trade_id": "b", "entry_month": "2024-01", "actual": {"C0": {"return": .01}}, "reference": {"C0": {"return": .02}}}]
    got = c28.paired_summary(rows, "C0")
    assert got["mean_entry_advantage"] == pytest.approx(.005)
    assert got["total_normalized_contribution_usdt"] == pytest.approx(10)


def test_bootstraps_are_pcg64_deterministic_and_preserve_attached_outcomes():
    rows = []
    for i, month in enumerate(("2024-01", "2024-02", "2024-02")):
        rows.append({"trade_id": str(i), "entry_month": month,
                     "actual": {c: {"return": .01 * (i + 1)} for c in ("C0", "C_BASE")},
                     "reference": {c: {"return": .005 * i} for c in ("C0", "C_BASE")}})
    for unit in ("calendar_month", "whole_entry"):
        a = c28.bootstrap(rows, unit, replicates=50); b = c28.bootstrap(rows, unit, replicates=50)
        assert a == b and a["generator"] == "PCG64" and not a["shared_reference_pool_dependence_eliminated"]


@pytest.mark.parametrize("supported,survives,p0,expected", [
    (False, False, -1, "INVESTIGATE_ENTRY_MODEL"),
    (True, False, -1, "RECONSIDER_STRATEGY_ECONOMICS"),
    (True, True, 0, "INVESTIGATE_PERMANENT_EXIT_TARGET"),
    (True, True, .001, "REVIEW_COMPLETE_P0_NOT_ECONOMICALLY_BROKEN"),
])
def test_frozen_strategy_decision_predicates(supported, survives, p0, expected):
    assert c28.strategy_decision(supported, survives, p0) == expected


def test_no_model_policy_mfe_exit_or_best_horizon_construction():
    source = inspect.getsource(c28)
    assert "sklearn" not in source and ".fit(" not in source
    assert '"mfe_exit": False' in source and '"no_best_horizon": True' in source
    assert "take_profit" not in source and "stop_loss" not in source
    assert "max(r[\"actual\"]" not in source
    assert "actual_rows = _actual_rows(entries, opens_by)" in source
    assert "_actual_economics(actual_rows)" in source


def test_p0_cost_accounting_and_summary_sign_counts():
    c0 = c28._cost_outcome(100, 101, "C0")
    base = c28._cost_outcome(100, 101, "C_BASE")
    assert c0["return"] == pytest.approx(.01) and base["return"] < c0["return"]
    got = c28.return_summary([{"return": 1., "pnl_usdt": 2.}, {"return": -1., "pnl_usdt": -2.}, {"return": 0., "pnl_usdt": 0.}])
    assert got["win_loss_tie_count"] == {"win": 1, "loss": 1, "tie": 1}
