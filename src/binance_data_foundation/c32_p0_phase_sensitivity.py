"""C32 canonical-P0 reconciliation and fail-closed phase gate.

The accepted P0 is inspected, not redefined.  C32 may only continue when that
implementation has one frozen daily evaluation phase.  The repository's
accepted P0 is hourly, so the production run intentionally terminates at the
contract's reconciliation gate with C32_INSUFFICIENT.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import platform
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from .c2_common import ENTRY_COLUMNS, hash_rows, iter_gzip_csv
from .c2_costs import COST_SCENARIOS, apply_round_trip_costs
from .c2_entries import hourly_sma24
from .c2_p0 import EXPECTED_FROZEN_ENTRY_HASH, P0_VERSION, decide_p0
from .ingest import sha256_file

CONTRACT_REL = "contracts/C32_P0_PHASE_SENSITIVITY_CONTRACT.md"
OUTPUT_REL = "artifacts/c32_p0_phase_sensitivity"
C2_REL = "artifacts/c2_asymmetric_exit_experiment"
HOURLY_REL = "data/normalized/c2_frozen_inputs"
EXPECTED_ENTRIES = 2199
EXPECTED_HORIZON_HASH = "81e57cfa46f8d39a0448ab6dee2f445c9212f6a29230fe7009c860a580666b7f"
EXPECTED_TRADE_HASH = "b3c44b5f609d6651cba51ceb743843b709b85bdcb593f1e967034016f7163848"
SEED = 20261001
REPLICATES = 2000
END_MS = 1767225600000

REQUIRED_OUTPUTS = (
    "run_manifest.json", "provenance.json", "canonical_p0_reconciliation.json",
    "phase_definition.json", "phase_bar_audit.json", "population_reconciliation.json",
    "common_support.json", "phase_trade_counts.json", "phase_net_return_profile.json",
    "phase_gross_return_profile.json", "phase_mfe_profile.json", "phase_surrender_profile.json",
    "phase_mfe_timing_profile.json", "phase_holding_time_profile.json",
    "canonical_phase_deltas.json", "robust_phase_statistics.json",
    "cross_year_phase_stability.json", "circular_smoothness.json",
    "trade_bootstrap_intervals.json", "month_bootstrap_intervals.json",
    "symbol_phase_profiles.json", "cost_robustness.json", "causality_tests.json",
    "interpretation_predicates.json", "final_summary.json", "reproducibility_hashes.json",
)


def reject_future_path(path: os.PathLike[str] | str) -> None:
    """Reject explicitly future-labelled market partitions without enumerating them."""
    if any(part == "2026" or part.startswith("2026-") for part in Path(path).parts):
        raise PermissionError("C32 prohibits 2026 market data and metadata access")


def _load_csv(path: Path) -> list[dict]:
    reject_future_path(path)
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _year(ts: str) -> str:
    return ts[:4]


def reconcile_canonical(repo: Path) -> tuple[dict, dict]:
    c2 = repo / C2_REL
    entries_path = c2 / "frozen_entries.csv"
    horizons_path = c2 / "common_horizons_p0.csv"
    trades_path = c2 / "p0_trade_records.csv"
    entries = _load_csv(entries_path)
    horizons = _load_csv(horizons_path)
    trades = _load_csv(trades_path)

    population = {
        "expected_count": EXPECTED_ENTRIES,
        "actual_count": len(entries),
        "expected_semantic_hash": EXPECTED_FROZEN_ENTRY_HASH,
        "actual_semantic_hash": hash_rows(entries, ENTRY_COLUMNS),
        "year_counts": dict(sorted(Counter(_year(r["entry_execution_ts"]) for r in entries).items())),
        "symbol_counts": dict(sorted(Counter(r["symbol"] for r in entries).items())),
    }
    population["status"] = "PASS" if (
        len(entries) == EXPECTED_ENTRIES
        and population["actual_semantic_hash"] == EXPECTED_FROZEN_ENTRY_HASH
        and population["year_counts"] == {"2024": 1093, "2025": 1106}
        and population["symbol_counts"] == {"BNBUSDT": 442, "BTCUSDT": 451, "ETHUSDT": 434,
                                                "SOLUSDT": 431, "XRPUSDT": 441}
    ) else "FAIL"

    accepted = {r["trade_id"]: r for r in horizons}
    by_symbol: dict[str, list[dict]] = defaultdict(list)
    for row in entries:
        by_symbol[row["symbol"]].append(row)
    reproduced = []
    source_hashes = {}
    observed_boundary_hours: set[int] = set()
    for symbol in sorted(by_symbol):
        source = repo / HOURLY_REL / f"{symbol}_1h.csv.gz"
        reject_future_path(source)
        source_hashes[str(source.relative_to(repo))] = sha256_file(source)
        hours = [r for r in iter_gzip_csv(source) if int(r["open_time_ms"]) < END_MS]
        if any(int(r["available_at_ms"]) - int(r["open_time_ms"]) != 3_600_000 for r in hours):
            raise RuntimeError("accepted P0 source contains a non-hourly bar")
        for bar in hours:
            observed_boundary_hours.add(datetime.fromtimestamp(int(bar["available_at_ms"]) / 1000, timezone.utc).hour)
        sma = hourly_sma24(hours)
        execution = {int(r["open_time_ms"]): r for r in hours}
        dataset_last = max(execution)
        for entry in by_symbol[symbol]:
            decision = decide_p0(int(entry["entry_execution_ms"]), hours, execution, dataset_last, hourly_sma=sma)
            ref = accepted[entry["trade_id"]]
            reproduced.append({
                "trade_id": entry["trade_id"],
                "timestamp_exact": decision.execution_ms == int(ref["p0_execution_ms"]),
                "price_exact": decision.exit_price == float(ref["p0_raw_exit_price"]),
                "reason_exact": decision.reason == ref["p0_exit_reason"],
            })

    trade_columns = tuple(trades[0])
    costs_exact = True
    for row in trades:
        scenario = next(x for x in COST_SCENARIOS if x.scenario_id == row["cost_scenario"])
        calc = apply_round_trip_costs(float(row["entry_price"]), float(row["exit_price"]),
                                      float(row["entry_notional_usdt"]), scenario)
        costs_exact &= all(float(row[key]) == calc[key] for key in ("gross_return", "net_return"))
    all_exact = len(reproduced) == EXPECTED_ENTRIES and all(
        r["timestamp_exact"] and r["price_exact"] and r["reason_exact"] for r in reproduced
    )
    reference_hashes = {
        str(horizons_path.relative_to(repo)): sha256_file(horizons_path),
        str(trades_path.relative_to(repo)): sha256_file(trades_path),
    }
    reconciliation = {
        "status": "PASS" if all_exact and costs_exact else "FAIL",
        "p0_version": P0_VERSION,
        "model": "hourly close below trailing SMA of 24 consecutive 1-hour closes",
        "features": ["1h_close", "SMA24_of_1h_close"],
        "feature_order": ["1h_close", "SMA24_of_1h_close"],
        "parameters": {"bar_duration_hours": 1, "sma_lookback_bars": 24, "time_cap_days": 7},
        "decision_semantics": "first completed 1h bar after entry with close < inclusive trailing SMA24",
        "execution_semantics": "same decision boundary exact 1-minute open; missing/invalid boundary censors; no gap skipping",
        "terminal_semantics": "seven-day exact-boundary open, or right-censor if dataset/cap minute unavailable",
        "cost_semantics": "frozen C2 round-trip adverse slippage and quote fees",
        "accepted_trade_count": len(horizons),
        "reproduced_trade_count": len(reproduced),
        "exit_timestamps_exact": all(r["timestamp_exact"] for r in reproduced),
        "exit_prices_exact": all(r["price_exact"] for r in reproduced),
        "exit_reasons_exact": all(r["reason_exact"] for r in reproduced),
        "gross_and_net_cost_rows_exact": costs_exact,
        "accepted_horizon_hash_expected": EXPECTED_HORIZON_HASH,
        "accepted_horizon_hash_actual": reference_hashes[str(horizons_path.relative_to(repo))],
        "accepted_trade_hash_expected": EXPECTED_TRADE_HASH,
        "accepted_trade_hash_actual": reference_hashes[str(trades_path.relative_to(repo))],
        "year_counts": population["year_counts"], "symbol_counts": population["symbol_counts"],
        "observed_utc_evaluation_boundary_hours": sorted(observed_boundary_hours),
        "evaluation_interval_hours": 1,
        "canonical_daily_phase": None,
        "daily_phase_discovery": "FAIL_NO_UNIQUE_DAILY_PHASE",
    }
    provenance = {"source_hashes": source_hashes, "reference_hashes": reference_hashes}
    return {"population": population, "reconciliation": reconciliation}, provenance


def unavailable(reason: str) -> dict:
    return {"status": "NOT_RUN_RECONCILIATION_GATE", "reason": reason}


def run(repo: Path) -> dict:
    repo = repo.resolve()
    output = repo / OUTPUT_REL
    gate, provenance = reconcile_canonical(repo)
    rec = gate["reconciliation"]
    mismatch = (
        "Accepted canonical P0 is hourly (1h bars, SMA24, evaluation every hour across UTC hours 00-23); "
        "it has no single frozen daily aggregation phase. Constructing once-daily 24h-OHLCV variants would "
        "change its bar duration, feature definition, lookback-in-bars and evaluation cadence."
    )
    classification = "C32_INSUFFICIENT"
    if gate["population"]["status"] != "PASS" or rec["status"] != "PASS":
        mismatch = "Canonical P0 or E1 outcome reconciliation failed."

    _write(output / "population_reconciliation.json", gate["population"])
    _write(output / "canonical_p0_reconciliation.json", rec)
    phase_definition = {
        "status": "FAIL_NO_FROZEN_DAILY_PHASE", "reason": mismatch,
        "requested_phase_hours": list(range(24)), "variants_constructed": 0,
        "canonical_daily_phase": None, "canonical_evaluation_interval_hours": 1,
        "counterfactual_daily_model_created": False,
    }
    _write(output / "phase_definition.json", phase_definition)
    skip_files = [x for x in REQUIRED_OUTPUTS if x not in {
        "run_manifest.json", "provenance.json", "canonical_p0_reconciliation.json",
        "phase_definition.json", "population_reconciliation.json", "interpretation_predicates.json",
        "final_summary.json", "reproducibility_hashes.json",
    }]
    for name in skip_files:
        _write(output / name, unavailable(mismatch))
    predicates = {
        "classification": classification,
        "canonical_reconciliation_failure": True,
        "failure_kind": "no canonical daily aggregation phase",
        "common_support_established": False,
        "stable_predicate_evaluated": False,
        "unstable_predicate_evaluated": False,
        "no_material_predicate_evaluated": False,
        "higher_cadence_p0_test_justified": False,
    }
    _write(output / "interpretation_predicates.json", predicates)
    final = {
        "classification": classification, "higher_cadence_p0_test_justified": False,
        "canonical_p0_reproduced": rec["status"] == "PASS",
        "e1_population_reconciled": gate["population"]["status"] == "PASS",
        "canonical_phase": None, "failure_reason": mismatch,
        "phase_experiment_executed": False, "phase_selected": False,
        "bootstrap_executed": False, "bootstrap_spec": {"iterations": REPLICATES, "generator": "PCG64", "seed": SEED},
        "higher_cadence_experiment_executed": False, "p0_retrained_or_modified": False,
        "new_exit_logic_introduced": False, "future_market_data_or_metadata_accessed": False,
    }
    _write(output / "final_summary.json", final)
    provenance.update({
        "contract_sha256": sha256_file(repo / CONTRACT_REL),
        "implementation_hashes": {
            "src/binance_data_foundation/c2_p0.py": sha256_file(repo / "src/binance_data_foundation/c2_p0.py"),
            "src/binance_data_foundation/c2_entries.py": sha256_file(repo / "src/binance_data_foundation/c2_entries.py"),
            "src/binance_data_foundation/c32_p0_phase_sensitivity.py": sha256_file(Path(__file__)),
        },
        "python": sys.version, "platform": platform.platform(),
        "git_head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True).stdout.strip(),
        "command": "conda run -n binance-v2-research python scripts/c32_p0_phase_sensitivity.py",
        "rng": {"generator": "PCG64", "seed": SEED, "iterations": REPLICATES, "used": False},
    })
    _write(output / "provenance.json", provenance)
    manifest = {
        "status": "COMPLETE_AT_RECONCILIATION_GATE", "classification": classification,
        "created_at_utc": datetime.now(timezone.utc).isoformat(), "contract_sha256": provenance["contract_sha256"],
        "required_artifacts": list(REQUIRED_OUTPUTS), "phase_artifacts_are_fail_closed_placeholders": True,
        "dirty_status_recorded_after_run": True,
    }
    _write(output / "run_manifest.json", manifest)
    hashes = {name: sha256_file(output / name) for name in REQUIRED_OUTPUTS if name != "reproducibility_hashes.json"}
    _write(output / "reproducibility_hashes.json", {"artifact_sha256": hashes})
    return final

