from __future__ import annotations

import csv
import hashlib
import json
import math
import statistics
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .c2_common import (ENTRY_COLUMNS, hash_rows, iso, iter_gzip_csv, research_partitions,
                        require_pre_holdout_ms, valid_minute, write_json)
from .c2_costs import COST_SCENARIOS, apply_round_trip_costs
from .c2_entries import hourly_sma24
from .c2_path_metrics import evaluate_path
from .ingest import sha256_file


P0_VERSION = "P0_H1_SMA24_CROSSDOWN_V1"
RUN_ID = "C2A_P0_COMMON_HORIZON_V1"
SEVEN_DAYS_MS = 7 * 24 * 3_600_000
EXPECTED_FROZEN_ENTRY_HASH = "6885678a43b0d2f40b34e65adf15247072cdec2bbc8437cafd8cb69d8fba5da3"

HORIZON_COLUMNS = (
    "trade_id", "symbol", "entry_fixture_id", "entry_execution_ts", "entry_execution_ms", "entry_price",
    "p0_version", "p0_signal_ts", "p0_decision_ts", "p0_execution_ts", "p0_execution_ms",
    "p0_raw_exit_price", "p0_exit_reason", "common_horizon_end_ts", "common_horizon_end_ms",
    "common_horizon_duration_seconds", "censored", "censor_reason", "data_quality_flag",
    "held_mfe", "held_mae", "common_horizon_mfe", "common_horizon_mae",
    "time_to_held_mfe_seconds", "time_to_common_horizon_mfe_seconds", "max_drawdown_from_post_entry_peak",
    "held_peak_gain_surrendered", "common_opportunity_capture_gap", "held_peak_gain_retention",
    "held_retention_null_reason", "common_opportunity_capture_ratio", "common_retention_null_reason",
    "held_ever_green", "held_ever_above_0_5pct", "held_ever_above_1pct", "held_ever_above_2pct",
    "held_ever_above_3pct", "common_opportunity_ever_green", "common_opportunity_above_0_5pct",
    "common_opportunity_above_1pct", "common_opportunity_above_2pct", "common_opportunity_above_3pct",
    "held_green_then_red", "common_opportunity_positive_exit_red", "held_mfe_timing", "common_mfe_timing",
    "ambiguity_flag",
)


@dataclass(frozen=True)
class P0Decision:
    signal_ms: int | None
    decision_ms: int
    execution_ms: int | None
    exit_price: float | None
    reason: str | None
    censor_reason: str | None


def decide_p0(
    entry_ms: int, hour_bars: list[dict], execution_minutes: dict[int, dict], dataset_last_ms: int,
    *, hourly_sma: tuple[float | None, ...] | None = None,
) -> P0Decision:
    """Causal P0 decision code. It receives no path metrics or future summaries."""
    cap_ms = entry_ms + SEVEN_DAYS_MS
    sma = hourly_sma24(hour_bars) if hourly_sma is None else hourly_sma
    if len(sma) != len(hour_bars):
        raise ValueError("hourly_sma length must match hour_bars")
    for i, bar in enumerate(hour_bars):
        decision_ms = int(bar["available_at_ms"])
        if decision_ms <= entry_ms or decision_ms > cap_ms or sma[i] is None:
            continue
        if float(bar["close"]) < sma[i]:
            minute = execution_minutes.get(decision_ms)
            if minute is None or not valid_minute(minute):
                return P0Decision(decision_ms, decision_ms, None, None, None, "p0_execution_minute_missing_or_invalid")
            return P0Decision(decision_ms, decision_ms, decision_ms, float(minute["open"]), "sma24_crossdown", None)
    if cap_ms > dataset_last_ms:
        return P0Decision(None, cap_ms, None, None, None, "dataset_end_before_seven_day_cap")
    minute = execution_minutes.get(cap_ms)
    if minute is None or not valid_minute(minute):
        return P0Decision(None, cap_ms, None, None, None, "seven_day_cap_minute_missing_or_invalid")
    return P0Decision(None, cap_ms, cap_ms, float(minute["open"]), "time_cap", None)


def build_p0_checkpoint(
    normalized_dir: Path, aggregate_dir: Path, artifact_dir: Path,
) -> dict:
    entries_path = artifact_dir / "frozen_entries.csv"
    if sha256_file(entries_path) != EXPECTED_FROZEN_ENTRY_HASH:
        raise ValueError("frozen-entry hash mismatch; refusing P0 build")
    entries = list(csv.DictReader(entries_path.open(encoding="utf-8", newline="")))
    by_symbol: dict[str, list[dict]] = defaultdict(list)
    for entry in entries:
        require_pre_holdout_ms(entry["entry_execution_ms"], "frozen entry")
        by_symbol[entry["symbol"]].append(entry)
    horizons: list[dict] = []
    trades: list[dict] = []
    for symbol in sorted(by_symbol):
        hours = list(iter_gzip_csv(aggregate_dir / f"{symbol}_1h.csv.gz"))
        symbol_sma = hourly_sma24(hours)
        minute_lookup = {}
        dataset_last_ms = -1
        for row in iter_gzip_csv(normalized_dir / f"{symbol}_1m.csv.gz"):
            ts = require_pre_holdout_ms(row["open_time_ms"], "normalized minute")
            dataset_last_ms = max(dataset_last_ms, ts)
            if valid_minute(row):
                minute_lookup[ts] = row
        execution_minutes = {ts: row for ts, row in minute_lookup.items() if ts % 3_600_000 == 0}
        for entry in by_symbol[symbol]:
            entry_ms, entry_price = int(entry["entry_execution_ms"]), float(entry["entry_price"])
            decision = decide_p0(entry_ms, hours, execution_minutes, dataset_last_ms, hourly_sma=symbol_sma)
            if decision.censor_reason:
                horizon = _censored_row(entry, decision, decision.censor_reason)
                horizons.append(horizon)
                trades.extend(_censored_trade_row(entry, horizon, scenario.scenario_id) for scenario in COST_SCENARIOS)
                continue
            assert decision.execution_ms is not None and decision.exit_price is not None and decision.reason is not None
            path_rows, missing = _complete_path(entry_ms, decision.execution_ms, minute_lookup)
            if missing is not None:
                horizon = _censored_row(entry, decision, f"path_gap_at_{iso(missing)}")
                horizons.append(horizon)
                trades.extend(_censored_trade_row(entry, horizon, scenario.scenario_id) for scenario in COST_SCENARIOS)
                continue
            metrics = evaluate_path(
                entry_ms=entry_ms, entry_price=entry_price, exit_ms=decision.execution_ms,
                exit_price=decision.exit_price, minute_rows=path_rows,
            )
            horizon = _horizon_row(entry, decision, metrics)
            horizons.append(horizon)
            for scenario in COST_SCENARIOS:
                costs = apply_round_trip_costs(entry_price, decision.exit_price, float(entry["entry_notional_usdt"]), scenario)
                trades.append(_trade_row(entry, horizon, costs))
    horizons.sort(key=lambda row: (int(row["entry_execution_ms"]), row["symbol"], row["trade_id"]))
    trades.sort(key=lambda row: (int(row["entry_execution_ms"]), row["symbol"], row["trade_id"], row["cost_scenario"]))
    horizon_path = artifact_dir / "common_horizons_p0.csv"
    trade_path = artifact_dir / "p0_trade_records.csv"
    _write_csv(horizon_path, horizons, HORIZON_COLUMNS)
    trade_columns = tuple(trades[0]) if trades else ()
    _write_csv(trade_path, trades, trade_columns)
    summary = summarize(entries, horizons, trades)
    summary.update({
        "run_id": RUN_ID, "p0_version": P0_VERSION,
        "frozen_entry_hash": EXPECTED_FROZEN_ENTRY_HASH,
        "common_horizon_semantic_hash": hash_rows(horizons, HORIZON_COLUMNS),
        "common_horizon_file_hash": sha256_file(horizon_path),
        "p0_trade_records_semantic_hash": hash_rows(trades, trade_columns),
        "p0_trade_records_file_hash": sha256_file(trade_path),
    })
    write_json(artifact_dir / "p0_summary.json", summary)
    _write_manifest(artifact_dir, summary)
    return summary


def _complete_path(entry_ms: int, exit_ms: int, lookup: dict[int, dict]) -> tuple[list[dict], int | None]:
    rows = []
    for ts in range(entry_ms + 60_000, exit_ms, 60_000):
        row = lookup.get(ts)
        if row is None:
            return [], ts
        rows.append(row)
    return rows, None


def _censored_row(entry: dict, decision: P0Decision, reason: str) -> dict:
    row = {column: "" for column in HORIZON_COLUMNS}
    row.update({
        "trade_id": entry["trade_id"], "symbol": entry["symbol"], "entry_fixture_id": entry["entry_fixture_id"],
        "entry_execution_ts": entry["entry_execution_ts"], "entry_execution_ms": entry["entry_execution_ms"],
        "entry_price": entry["entry_price"], "p0_version": P0_VERSION,
        "p0_signal_ts": iso(decision.signal_ms) if decision.signal_ms is not None else "",
        "p0_decision_ts": iso(decision.decision_ms), "censored": True, "censor_reason": reason,
        "data_quality_flag": "right_censored",
    })
    return row


def _horizon_row(entry: dict, decision: P0Decision, metrics: dict) -> dict:
    assert decision.execution_ms is not None and decision.exit_price is not None
    row = {
        "trade_id": entry["trade_id"], "symbol": entry["symbol"], "entry_fixture_id": entry["entry_fixture_id"],
        "entry_execution_ts": entry["entry_execution_ts"], "entry_execution_ms": entry["entry_execution_ms"],
        "entry_price": entry["entry_price"], "p0_version": P0_VERSION,
        "p0_signal_ts": iso(decision.signal_ms) if decision.signal_ms is not None else "",
        "p0_decision_ts": iso(decision.decision_ms), "p0_execution_ts": iso(decision.execution_ms),
        "p0_execution_ms": decision.execution_ms, "p0_raw_exit_price": format(decision.exit_price, ".17g"),
        "p0_exit_reason": decision.reason, "common_horizon_end_ts": iso(decision.execution_ms),
        "common_horizon_end_ms": decision.execution_ms,
        "common_horizon_duration_seconds": (decision.execution_ms - int(entry["entry_execution_ms"])) // 1000,
        "censored": False, "censor_reason": "", "data_quality_flag": "complete",
    }
    row.update(metrics)
    return {column: row.get(column, "") for column in HORIZON_COLUMNS}


def _trade_row(entry: dict, horizon: dict, costs: dict) -> dict:
    return {
        "run_id": RUN_ID, "trade_id": entry["trade_id"], "symbol": entry["symbol"],
        "entry_fixture_id": entry["entry_fixture_id"], "entry_signal_ts": entry["entry_signal_ts"],
        "entry_decision_ts": entry["entry_decision_ts"], "entry_execution_ts": entry["entry_execution_ts"],
        "entry_execution_ms": entry["entry_execution_ms"], "entry_price": entry["entry_price"],
        "entry_notional_usdt": entry["entry_notional_usdt"], "exit_policy": "P0", "exit_policy_version": P0_VERSION,
        "exit_signal_ts": horizon["p0_signal_ts"], "exit_decision_ts": horizon["p0_decision_ts"],
        "exit_execution_ts": horizon["p0_execution_ts"], "exit_price": horizon["p0_raw_exit_price"],
        "exit_reason": horizon["p0_exit_reason"], "entry_timeframe": "1h", "signal_timeframe": "1h",
        "exit_observation_timeframe": "1h", "source_timeframe": "1m",
        "execution_price_assumption": "exact_boundary_1m_open", "common_horizon_end_ts": horizon["common_horizon_end_ts"],
        "censored": False, "censor_reason": "", "data_quality_flag": horizon["data_quality_flag"],
        **costs,
        **{key: horizon[key] for key in HORIZON_COLUMNS if key.startswith(("held_", "common_", "time_to_", "max_drawdown", "ambiguity"))},
    }


def _censored_trade_row(entry: dict, horizon: dict, scenario_id: str) -> dict:
    row = _trade_row(entry, horizon, {
        "cost_scenario": scenario_id, "fee_rate": "", "slippage_rate": "", "quantity": "",
        "entry_price_after_slippage": "", "exit_price_after_slippage": "", "raw_price_return": "",
        "gross_return": "", "net_return": "", "entry_fee_usdt": "", "exit_fee_usdt": "",
        "fees_usdt": "", "slippage_usdt": "", "quantity_convention": "",
    })
    row.update({"censored": True, "censor_reason": horizon["censor_reason"], "data_quality_flag": "right_censored"})
    return row


def summarize(entries: list[dict], horizons: list[dict], trades: list[dict]) -> dict:
    complete = [row for row in horizons if str(row["censored"]).lower() == "false"]
    censored = [row for row in horizons if str(row["censored"]).lower() == "true"]
    return {
        "total_frozen_entries": len(entries), "p0_resolved_exits": len(complete),
        "p0_crossdown_exits": sum(row["p0_exit_reason"] == "sma24_crossdown" for row in complete),
        "seven_day_caps": sum(row["p0_exit_reason"] == "time_cap" for row in complete),
        "right_censored": len(censored),
        "exit_reason_counts": dict(sorted(Counter(row["p0_exit_reason"] for row in complete).items())),
        "censor_reason_counts": dict(sorted(Counter(row["censor_reason"] for row in censored).items())),
        "overall": _group_summary(horizons, trades),
        "by_symbol": {symbol: _group_summary([h for h in horizons if h["symbol"] == symbol], [t for t in trades if t["symbol"] == symbol]) for symbol in sorted({e["symbol"] for e in entries})},
        "by_partition": {name: _group_summary(
            [h for h in horizons if _partition(h["entry_execution_ts"]) == name],
            [t for t in trades if _partition(t["entry_execution_ts"]) == name],
        ) for name in ("sanity_calibration", "headline_evaluation")},
    }


def _group_summary(horizons: list[dict], trades: list[dict]) -> dict:
    complete = [row for row in horizons if str(row["censored"]).lower() == "false"]
    censored = [row for row in horizons if str(row["censored"]).lower() == "true"]
    result = {
        "frozen_entries": len(horizons), "resolved_entries": len(complete), "right_censored": len(censored),
        "p0_crossdown_exits": sum(h["p0_exit_reason"] == "sma24_crossdown" for h in complete),
        "seven_day_caps": sum(h["p0_exit_reason"] == "time_cap" for h in complete),
        "exit_reason_counts": dict(sorted(Counter(h["p0_exit_reason"] for h in complete).items())),
        "censor_reason_counts": dict(sorted(Counter(h["censor_reason"] for h in censored).items())),
        "common_horizon_duration_seconds": _distribution([float(h["common_horizon_duration_seconds"]) for h in complete]),
        "common_horizon_mfe": _distribution([float(h["common_horizon_mfe"]) for h in complete]),
        "common_horizon_mae": _distribution([float(h["common_horizon_mae"]) for h in complete]),
        "held_green_then_red": _count_rate(complete, "held_green_then_red"),
        "common_opportunity_positive_exit_red": _count_rate(complete, "common_opportunity_positive_exit_red"),
        "opportunity_thresholds": {label: _count_rate(complete, f"common_opportunity_above_{label}") for label in ("0_5pct", "1pct", "2pct", "3pct")},
        "returns_by_cost": {},
    }
    for scenario in (x.scenario_id for x in COST_SCENARIOS):
        rows = [row for row in trades if row["cost_scenario"] == scenario and str(row["censored"]).lower() == "false"]
        result["returns_by_cost"][scenario] = {
            "raw": _distribution([float(row["raw_price_return"]) for row in rows]),
            "gross": _distribution([float(row["gross_return"]) for row in rows]),
            "net": _distribution([float(row["net_return"]) for row in rows]),
        }
    return result


def _distribution(values: list[float]) -> dict:
    if not values: return {"count": 0, "min": None, "p05": None, "p25": None, "median": None, "mean": None, "p75": None, "p95": None, "max": None}
    ordered = sorted(values)
    def q(p: float) -> float:
        index = (len(ordered) - 1) * p
        lo, hi = math.floor(index), math.ceil(index)
        return ordered[lo] if lo == hi else ordered[lo] + (ordered[hi] - ordered[lo]) * (index - lo)
    return {"count": len(values), "min": ordered[0], "p05": q(.05), "p25": q(.25), "median": q(.5),
            "mean": statistics.fmean(values), "p75": q(.75), "p95": q(.95), "max": ordered[-1]}


def _count_rate(rows: list[dict], key: str) -> dict:
    count = sum(str(row[key]).lower() == "true" for row in rows)
    return {"count": count, "rate": count / len(rows) if rows else None}


def _partition(timestamp: str) -> str:
    return "sanity_calibration" if timestamp < "2024-04-01" else "headline_evaluation"


def _write_csv(path: Path, rows: list[dict], columns: tuple[str, ...]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_manifest(artifact_dir: Path, summary: dict) -> None:
    prior = json.loads((artifact_dir / "run_manifest.json").read_text(encoding="utf-8"))
    contract = Path("contracts/C2_asymmetric_exit_experiment_CONTRACT.md")
    paths = [Path(__file__), Path(__file__).with_name("c2_p0_cli.py"), Path(__file__).with_name("c2_costs.py"),
             Path(__file__).with_name("c2_path_metrics.py"), Path("tests/test_c2_p0.py")]
    manifest = {
        "run_id": RUN_ID, "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "code_revision": subprocess.run(["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip(),
        "contract_sha256": sha256_file(contract), "frozen_entry_hash": EXPECTED_FROZEN_ENTRY_HASH,
        "aggregate_hashes": prior["aggregate_hashes"], "p0_version": P0_VERSION,
        "cost_scenarios": [{"id": x.scenario_id, "fee_rate": x.fee_rate, "slippage_rate": x.slippage_rate} for x in COST_SCENARIOS],
        "research_partitions": research_partitions(), "censor_counts": summary["censor_reason_counts"],
        "common_horizon_semantic_hash": summary["common_horizon_semantic_hash"],
        "implementation_hashes": {
            str(path.relative_to(Path.cwd())) if path.is_absolute() else str(path): sha256_file(path)
            for path in paths
        },
        "output_hashes": {name: sha256_file(artifact_dir / name) for name in ("common_horizons_p0.csv", "p0_trade_records.csv", "p0_summary.json", "p0_reproducibility.json") if (artifact_dir / name).exists()},
        "implemented_policies": [P0_VERSION], "explicitly_not_implemented": ["P1", "P2", "P3", "C2-B"],
    }
    write_json(artifact_dir / "p0_manifest.json", manifest)
