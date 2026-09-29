from pathlib import Path
import inspect

import pytest

from binance_data_foundation import c29_opportunity_prevalence as c29


def test_frozen_contract_population_horizons_and_costs():
    assert c29.sha256_file(Path(c29.CONTRACT_REL)) == c29.CONTRACT_SHA256
    assert c29.EXPECTED_ENTRIES == 2199
    assert c29.ENTRY_SHA256 == "6885678a43b0d2f40b34e65adf15247072cdec2bbc8437cafd8cb69d8fba5da3"
    assert c29.EXPECTED_YEARS == {2024: 1093, 2025: 1106}
    assert c29.EXPECTED_SYMBOLS == {"BNBUSDT": 442, "BTCUSDT": 451, "ETHUSDT": 434, "SOLUSDT": 431, "XRPUSDT": 441}
    assert c29.HORIZONS == (3, 6, 12, 24)
    assert c29.COST_IDS == ("C0", "C_BASE", "C_S5", "C_S10")
    assert (c29.DESIGN_BNB.fee_rate, c29.DESIGN_BNB.slippage_rate) == (.00075, .0002)


def test_exact_real_entry_reconciliation():
    entries, rec, _ = c29._load_and_reconcile(Path.cwd())
    assert len(entries) == 2199 and rec["status"] == "PASS"
    assert rec["year_counts"] == {"2024": 1093, "2025": 1106}
    assert rec["symbol_counts"] == c29.EXPECTED_SYMBOLS
    assert rec["timestamps_prices_and_24h_refractory_exact"]


def test_exact_boundaries_and_c0_only_labels():
    assert c29.opportunity_label(.004, .004) and not c29.opportunity_label(.003999, .004)
    assert c29.opportunity_label(.005, .005) and not c29.opportunity_label(.004999, .005)
    entry = 1_700_000_000_000
    entries = [{"trade_id": "x", "symbol": "BTCUSDT", "entry_execution_ms": str(entry), "entry_price": "100"}]
    opens = {"BTCUSDT": {entry + h*3_600_000: 100.5 for h in c29.HORIZONS}}
    rows, coverage = c29.build_rows(entries, opens)
    assert all(rows[h][0]["exit_fill_ms"] == entry + h*3_600_000 for h in c29.HORIZONS)
    assert all(rows[h][0]["labels"] == {"GROSS40": True, "GROSS50": True} for h in c29.HORIZONS)
    assert all(coverage[f"H{h}"]["unavailable_trade_count"] == 0 for h in c29.HORIZONS)
    missing, _ = c29.build_rows(entries, {"BTCUSDT": {}})
    assert all(not missing[h] for h in c29.HORIZONS)  # unavailable, never synthetic


def _rows():
    values = [.004, .005, -.004, -.005]
    return [{"trade_id": str(i), "symbol": "BTCUSDT" if i < 2 else "ETHUSDT", "year": 2024 if i < 2 else 2025,
             "entry_month": f"202{4 if i < 2 else 5}-0{1+i%2}",
             "returns": {c: v-(0 if c == "C0" else .001) for c in c29.ALL_COST_IDS},
             "pnls": {c: (v-(0 if c == "C0" else .001))*1000 for c in c29.ALL_COST_IDS},
             "labels": {"GROSS40": v >= .004, "GROSS50": v >= .005}} for i, v in enumerate(values)]


def test_ladders_decomposition_concentration_and_bootstrap_determinism():
    rows = _rows()
    assert c29.threshold_ladder(rows, c29.POSITIVE_LADDER, True)[">=+0.0040"]["full_population"]["count"] == 2
    assert c29.threshold_ladder(rows, c29.NEGATIVE_LADDER, False)["<=-0.0040"]["by_year"]["2025"]["count"] == 2
    p = c29.prevalence(rows, "GROSS40")
    assert set(p["by_year"]) == {"2024", "2025"} and set(p["by_symbol"]) == set(c29.EXPECTED_SYMBOLS)
    assert c29.concentration(rows, "GROSS40")["opportunity_count"] == 2
    for unit in ("whole_trade", "UTC_entry_calendar_month"):
        assert c29.bootstrap(rows, unit, replicates=50) == c29.bootstrap(rows, unit, replicates=50)


def test_no_2026_model_mfe_label_policy_or_horizon_selection():
    with pytest.raises(PermissionError): c29.reject_2026("data/year=2026/file.csv")
    source = inspect.getsource(c29)
    assert "sklearn" not in source and ".fit(" not in source
    assert 'HORIZONS = (3, 6, 12, 24)' in source
    assert '"mfe_exit": False' in source
    assert "take_profit" not in source and "stop_loss" not in source
    assert '"No preferred holding horizon was selected."' in source
