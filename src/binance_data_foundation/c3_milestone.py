from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import statistics
import subprocess
import sys
import tempfile
from array import array
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .c2_common import ENTRY_COLUMNS, STUDY_END_MS, SYMBOLS, hash_rows, iso, valid_minute, write_json
from .c2_p0 import HORIZON_COLUMNS
from .ingest import sha256_file


DATASET_VERSION = "C3_MILESTONE_STATE_DATASET_V1"
FEATURE_SCHEMA_VERSION = "C3_CAUSAL_MILESTONE_FEATURES_V1"
PREDECESSOR_REVISION = "ab08b62"
MINUTE = 60_000
FIVE_MINUTES = 300_000
HOUR = 3_600_000

EXPECTED_FROZEN_ENTRY_HASH = "6885678a43b0d2f40b34e65adf15247072cdec2bbc8437cafd8cb69d8fba5da3"
EXPECTED_COMMON_HORIZON_HASH = "81e57cfa46f8d39a0448ab6dee2f445c9212f6a29230fe7009c860a580666b7f"
EXPECTED_PAIRED_HASH = "43de8894095963bda5aee47d8d24f6dec34a3b9cc7def1eec80256156baff5f1"
EXPECTED_NORMALIZED_HASHES = {
    "BNBUSDT": "6e79f58348cdcfd4e15b26b6f4c14728d8ccafd174072d6d174afbd05df8c84f",
    "BTCUSDT": "fa08f546140f3d6a7fad25ecb264c30d6f37e2986dcdf0ab21028ca3d5ba2cb7",
    "ETHUSDT": "fba74415cb41188235b287cc2a47f9935568f613bc5ea1bb1f1d5a9405fc5ef9",
    "SOLUSDT": "f0fef1a1f2f5ebdeac981d448860f94950c80e054dd78396c65cb91f858e4cef",
    "XRPUSDT": "71f9d40b1aa9c7fb03a42b181bb203e61c27a9e5a07ecc0a4438bc6581187cfb",
}
EXPECTED_AGGREGATE_HASHES = {
    ("BNBUSDT", "5m"): "240f995297f699dbe4447e1b8c75b79fe399486051aacb015e41d9854450df59",
    ("BTCUSDT", "5m"): "d03158a81dbacd97c149e68b77b467cebe46ba35a4571e8a3c486417372f32d5",
    ("ETHUSDT", "5m"): "50e57bce10b6dd4a3b4221adae739f7de406991f4fdb60add9233d4becbcd93e",
    ("SOLUSDT", "5m"): "6c71ba711fabd286c16de08cf296eb077a88d2d59f743bb0c56e3c3af7afe85d",
    ("XRPUSDT", "5m"): "c55e59696915fd499272e2c82e788ecefeb8935df273dac48e038fee39c0ec4e",
    ("BNBUSDT", "1h"): "175e102d2893771392dc54df22f33fe3d37a66a0b681fdd33a2d5e5a89899f3a",
    ("BTCUSDT", "1h"): "f9f9453665b89a8bb7c10c84c4257f606856f6f31996a6b34b30fa2649c97971",
    ("ETHUSDT", "1h"): "ed03a4bafbebdc7c0b3936abc12a7597ff467659d566bf954bc17c41f2b43e67",
    ("SOLUSDT", "1h"): "936a588a20660ef80ff5f3b2c45590bff4cfafde4232100db8eca14e81716a20",
    ("XRPUSDT", "1h"): "49da571c398801b2b45450aa2d8f7efb0d05720e551815f8f632aa07248943c8",
}
EXPECTED_KEYED_FEATURE_HASHES = {
    "M1": "18e22f50982ce2449f50dae05d084c55be8727d8f6db3db4a841595471e44caf",
    "M2": "03e7c7503bc458031e326e89b155c600069a5f6dcef871c399551cc2530ade7a",
}

FEATURE_COLUMNS = (
    "time_from_entry_seconds", "pre_milestone_mae", "complete_5m_bars_since_entry",
    "path_efficiency_5m", "positive_5m_fraction_last6", "negative_5m_fraction_last6",
    "recent_drawdown_last6_5m", "local_return_5m", "local_return_15m",
    "local_return_30m", "local_return_60m", "local_momentum_acceleration",
    "consecutive_positive_5m", "consecutive_negative_5m", "absolute_return_5m",
    "realized_volatility_last6_5m", "volatility_expansion_ratio", "latest_5m_range_ratio",
    "distance_from_h1_sma24", "h1_sma24_slope", "distance_from_6h_high",
    "distance_from_6h_low", "trend_persistence_last12_5m", "base_volume_ratio",
    "quote_volume_ratio", "trade_count_ratio", "quote_volume_acceleration",
    "btc_minus_subject_return_5m", "btc_minus_subject_return_15m",
    "btc_minus_subject_return_60m", "eth_minus_subject_return_5m",
    "eth_minus_subject_return_15m", "eth_minus_subject_return_60m",
    "other_four_breadth_15m", "btc_eth_agreement_15m",
)

PROVENANCE_COLUMNS = (
    "dataset_version", "feature_schema_version", "trade_id", "symbol", "entry_fixture_id",
    "entry_execution_ts", "entry_execution_ms", "entry_price", "milestone_id", "milestone_ts",
    "milestone_interval_start_ts", "milestone_interval_start_ms", "milestone_available_ts",
    "milestone_available_ms", "feature_cutoff_ts", "feature_cutoff_ms", "milestone_timing",
    "milestone_price", "common_horizon_end_ts", "common_horizon_end_ms", "source_resolution",
    "rolling_1m_available_ts", "aligned_5m_available_ts", "h1_available_ts", "cross_asset_available_ts",
    "data_quality_flag", "feature_eligible", "feature_ineligible_reason", "split_eligibility",
    "split_exclusion_reason", "applicable_label_resolution_boundary_ts",
)

OUTCOME_COLUMNS = (
    "trade_id", "milestone_id", "label", "label_name", "label_resolution_ts",
    "label_resolution_ms", "label_resolution_timing", "censored", "censor_reason",
    "ambiguous", "ambiguity_reason", "upper_barrier_price", "fallback_barrier_price",
    "time_to_resolution_seconds",
)

AUDIT_COLUMNS = PROVENANCE_COLUMNS + FEATURE_COLUMNS + tuple(x for x in OUTCOME_COLUMNS if x not in ("trade_id", "milestone_id"))
KEYED_FEATURE_COLUMNS = ("trade_id", "milestone_id") + FEATURE_COLUMNS
FEATURE_MATRIX_COLUMNS = FEATURE_COLUMNS
ROW_KEY_COLUMNS = ("model_row_index", "trade_id", "milestone_id")

MILESTONES = {
    "M1": {"id": "M1_FIRST_PLUS_1PCT_V1", "milestone": 1.01, "upper": 1.02, "fallback": 1.00},
    "M2": {"id": "M2_FIRST_PLUS_2PCT_V1", "milestone": 1.02, "upper": 1.03, "fallback": 1.01},
}


@dataclass
class DenseSeries:
    step_ms: int
    start_ms: int
    values: dict[str, array]
    valid: bytearray

    @classmethod
    def from_rows(cls, rows: Iterable[dict], step_ms: int) -> "DenseSeries":
        materialized = sorted((dict(r) for r in rows), key=lambda r: int(r["open_time_ms"]))
        if not materialized:
            return cls(step_ms, 0, {}, bytearray())
        start, end = int(materialized[0]["open_time_ms"]), int(materialized[-1]["open_time_ms"])
        size = (end - start) // step_ms + 1
        names = ("open", "high", "low", "close", "base_volume", "quote_volume", "trade_count")
        values = {name: array("d", [math.nan]) * size for name in names}
        valid = bytearray(size)
        for row in materialized:
            ts = _pre_holdout_timestamp(row["open_time_ms"], "synthetic source")
            if ts % step_ms:
                raise ValueError("off-grid source timestamp")
            index = (ts - start) // step_ms
            if valid[index]:
                raise ValueError("duplicate source timestamp")
            if row.get("_invalid", False):
                valid[index] = 2
                continue
            for name in names:
                values[name][index] = float(row.get(name, 0))
            valid[index] = 1
        return cls(step_ms, start, values, valid)

    def get(self, timestamp_ms: int) -> dict | None:
        delta = timestamp_ms - self.start_ms
        if delta < 0 or delta % self.step_ms:
            return None
        index = delta // self.step_ms
        if index >= len(self.valid) or self.valid[index] != 1:
            return None
        return {name: values[index] for name, values in self.values.items()}


@dataclass(frozen=True)
class C3Inputs:
    entries: tuple[dict, ...]
    horizons: dict[str, dict]
    minutes: dict[str, DenseSeries]
    bars5: dict[str, DenseSeries]
    hours: dict[str, DenseSeries]
    manifest: dict


def _pre_holdout_timestamp(value: object, label: str) -> int:
    try:
        timestamp = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"invalid {label} timestamp") from exc
    if timestamp >= STUDY_END_MS:
        raise ValueError(f"{label} timestamp at or after sealed 2026 boundary")
    return timestamp


def _read_csv_verified(path: Path, expected_hash: str, columns: tuple[str, ...], timestamp_field: str) -> list[dict]:
    if sha256_file(path) != expected_hash:
        raise ValueError(f"accepted input hash mismatch: {path}")
    with path.open(encoding="utf-8", newline="") as handle:
        rows = []
        for row in csv.DictReader(handle):
            _pre_holdout_timestamp(row[timestamp_field], str(path))
            rows.append(row)
    if hash_rows(rows, columns) != expected_hash:
        raise ValueError(f"accepted semantic hash mismatch: {path}")
    return rows


def _load_gzip_series(path: Path, expected_hash: str, step_ms: int) -> DenseSeries:
    import gzip
    if sha256_file(path) != expected_hash:
        raise ValueError(f"accepted market input hash mismatch: {path}")
    names = ("open", "high", "low", "close", "base_volume", "quote_volume", "trade_count")
    values = {name: array("d") for name in names}
    valid = bytearray()
    start = previous = None
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            # Boundary validation deliberately precedes every other field access.
            timestamp = _pre_holdout_timestamp(row["open_time_ms"], str(path))
            if timestamp % step_ms or (previous is not None and timestamp != previous + step_ms):
                raise ValueError(f"missing, duplicate, or off-grid source timestamp: {path}")
            if step_ms == MINUTE and not valid_minute(row):
                raise ValueError(f"invalid accepted minute: {path} at {timestamp}")
            parsed = {name: float(row[name]) for name in names}
            if not all(math.isfinite(value) for value in parsed.values()):
                raise ValueError(f"non-finite accepted source value: {path} at {timestamp}")
            if start is None:
                start = timestamp
            for name in names:
                values[name].append(parsed[name])
            valid.append(1)
            previous = timestamp
    if start is None:
        raise ValueError(f"empty accepted market input: {path}")
    return DenseSeries(step_ms, start, values, valid)


def load_accepted_inputs(repo: Path) -> C3Inputs:
    artifact = repo / "artifacts/c2_asymmetric_exit_experiment"
    normalized = repo / "data/normalized/c2_history"
    aggregates = repo / "data/normalized/c2_frozen_inputs"
    entries_path = artifact / "frozen_entries.csv"
    horizons_path = artifact / "common_horizons_p0.csv"
    paired_path = artifact / "c2a_paired_trade_records.csv"
    entries = _read_csv_verified(entries_path, EXPECTED_FROZEN_ENTRY_HASH, ENTRY_COLUMNS, "entry_execution_ms")
    horizons = _read_csv_verified(horizons_path, EXPECTED_COMMON_HORIZON_HASH, HORIZON_COLUMNS, "common_horizon_end_ms")
    if sha256_file(paired_path) != EXPECTED_PAIRED_HASH:
        raise ValueError("accepted paired-table hash mismatch")
    horizon_by_id = {row["trade_id"]: row for row in horizons}
    if {row["trade_id"] for row in entries} != set(horizon_by_id):
        raise ValueError("frozen-entry/common-horizon pairing mismatch")
    minutes, bars5, hours = {}, {}, {}
    paths: list[dict] = [
        _input_record(repo, entries_path, EXPECTED_FROZEN_ENTRY_HASH, "frozen_entries"),
        _input_record(repo, horizons_path, EXPECTED_COMMON_HORIZON_HASH, "common_horizons"),
        _input_record(repo, paired_path, EXPECTED_PAIRED_HASH, "accepted_paired_table_hash_only"),
    ]
    for symbol in SYMBOLS:
        minute_path = normalized / f"{symbol}_1m.csv.gz"
        minutes[symbol] = _load_gzip_series(minute_path, EXPECTED_NORMALIZED_HASHES[symbol], MINUTE)
        paths.append(_input_record(repo, minute_path, EXPECTED_NORMALIZED_HASHES[symbol], "normalized_1m"))
        for timeframe, step, target in (("5m", FIVE_MINUTES, bars5), ("1h", HOUR, hours)):
            aggregate_path = aggregates / f"{symbol}_{timeframe}.csv.gz"
            expected = EXPECTED_AGGREGATE_HASHES[(symbol, timeframe)]
            target[symbol] = _load_gzip_series(aggregate_path, expected, step)
            paths.append(_input_record(repo, aggregate_path, expected, f"aggregate_{timeframe}"))
    contract_path = repo / "contracts/C3_milestone_state_continuation_CONTRACT.md"
    manifest = {
        "manifest_version": "C3_T1_INPUT_MANIFEST_V1", "predecessor_revision": PREDECESSOR_REVISION,
        "execution_revision": _git_revision(repo), "contract_path": str(contract_path.relative_to(repo)),
        "contract_sha256": sha256_file(contract_path), "boundary_end_exclusive_utc": "2026-01-01T00:00:00Z",
        "explicit_allowlist": paths, "schemas": {"history": "c2-history-1m-gzip-v1", "aggregates": "c2-causal-aggregate-v1",
        "entries": "E1_H1_SMA24_CROSS_V1", "horizons": "P0_H1_SMA24_CROSSDOWN_V1"},
        "date_bounds": {"source_start_utc": "2023-12-31T00:00:00Z", "end_exclusive_utc": "2026-01-01T00:00:00Z"},
        "environment": {"conda_env": os.environ.get("CONDA_DEFAULT_ENV", ""), "python": sys.version.split()[0], "interpreter": sys.executable},
        "verification": {"all_hashes_verified": True, "timestamps_checked_before_values": True,
        "paired_table_outcomes_consumed": False, "2026_paths_enumerated": False, "2026_market_data_accessed": False},
    }
    return C3Inputs(tuple(entries), horizon_by_id, minutes, bars5, hours, manifest)


def _input_record(repo: Path, path: Path, digest: str, role: str) -> dict:
    return {"path": str(path.relative_to(repo)), "sha256": digest, "role": role}


def _git_revision(repo: Path) -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


def _rolling_return(series: DenseSeries, cutoff: int, minutes: int) -> float | None:
    width = minutes * MINUTE
    for ts in range(cutoff - width - MINUTE, cutoff, MINUTE):
        if series.get(ts) is None:
            return None
    end, start = series.get(cutoff - MINUTE), series.get(cutoff - width - MINUTE)
    return None if end is None or start is None else end["close"] / start["close"] - 1


def _last_aligned(series: DenseSeries, cutoff: int, count: int) -> list[dict] | None:
    last_start = cutoff // series.step_ms * series.step_ms - series.step_ms
    rows = [series.get(last_start - (count - 1 - i) * series.step_ms) for i in range(count)]
    return None if any(row is None for row in rows) else rows  # type: ignore[return-value]


def _returns(rows: list[dict]) -> list[float]:
    return [rows[i]["close"] / rows[i - 1]["close"] - 1 for i in range(1, len(rows))]


def _ratio(value: float, denominator: float) -> float | None:
    return None if denominator == 0 else value / denominator


def compute_features(symbol: str, entry_ms: int, entry_price: float, cutoff: int,
                     minutes: dict[str, DenseSeries], bars5: dict[str, DenseSeries],
                     hours: dict[str, DenseSeries], milestone_return: float) -> tuple[dict, list[str]]:
    result: dict[str, float | int | None] = {name: None for name in FEATURE_COLUMNS}
    result["time_from_entry_seconds"] = (cutoff - entry_ms) // 1000
    subject_minutes, subject5, subject_hours = minutes[symbol], bars5[symbol], hours[symbol]
    pre_rows = [subject_minutes.get(ts) for ts in range(entry_ms + MINUTE, cutoff, MINUTE)]
    if pre_rows and all(row is not None for row in pre_rows):
        result["pre_milestone_mae"] = min([0.0] + [row["low"] / entry_price - 1 for row in pre_rows if row is not None])

    last5_start = cutoff // FIVE_MINUTES * FIVE_MINUTES - FIVE_MINUTES
    post5 = []
    ts = entry_ms if entry_ms % FIVE_MINUTES == 0 else (entry_ms // FIVE_MINUTES + 1) * FIVE_MINUTES
    while ts <= last5_start:
        row = subject5.get(ts)
        if row is None:
            post5 = []
            break
        post5.append(row); ts += FIVE_MINUTES
    result["complete_5m_bars_since_entry"] = len(post5)
    if len(post5) >= 2:
        movement = sum(abs(x) for x in _returns(post5))
        result["path_efficiency_5m"] = _ratio(milestone_return, movement)

    bars13 = _last_aligned(subject5, cutoff, 13)
    bars25 = _last_aligned(subject5, cutoff, 25)
    if bars13:
        recent6 = _returns(bars13[-7:]); prior6 = _returns(bars13[:7])
        result["positive_5m_fraction_last6"] = sum(x > 0 for x in recent6) / 6
        result["negative_5m_fraction_last6"] = sum(x < 0 for x in recent6) / 6
        result["recent_drawdown_last6_5m"] = bars13[-1]["close"] / max(x["high"] for x in bars13[-6:]) - 1
        pos = neg = 0
        for value in reversed(recent6):
            if value > 0 and neg == 0: pos += 1
            elif value < 0 and pos == 0: neg += 1
            else: break
        result["consecutive_positive_5m"] = min(pos, 6)
        result["consecutive_negative_5m"] = min(neg, 6)
        result["realized_volatility_last6_5m"] = statistics.stdev(recent6)
        prior_vol = statistics.stdev(prior6)
        result["volatility_expansion_ratio"] = _ratio(statistics.stdev(recent6), prior_vol)
        latest_range = (bars13[-1]["high"] - bars13[-1]["low"]) / bars13[-1]["close"]
        prior_ranges = [(x["high"] - x["low"]) / x["close"] for x in bars13[:-1]]
        result["latest_5m_range_ratio"] = _ratio(latest_range, statistics.median(prior_ranges))
        result["trend_persistence_last12_5m"] = sum(x > 0 for x in _returns(bars13)) / 12
        for field, output in (("base_volume", "base_volume_ratio"), ("quote_volume", "quote_volume_ratio"), ("trade_count", "trade_count_ratio")):
            result[output] = _ratio(bars13[-1][field], statistics.median(x[field] for x in bars13[:-1]))
        result["quote_volume_acceleration"] = _ratio(statistics.fmean(x["quote_volume"] for x in bars13[-3:]), statistics.fmean(x["quote_volume"] for x in bars13[-6:-3]))
    if bars25:
        recent_returns = _returns(bars25[-13:])
        # Audit-only uncapped streak values are represented by the capped schema values above.

    local = {}
    for width in (5, 15, 30, 60):
        local[width] = _rolling_return(subject_minutes, cutoff, width)
        result[f"local_return_{width}m"] = local[width]
    result["absolute_return_5m"] = None if local[5] is None else abs(local[5])
    recent15 = local[15]
    prior15 = _window_return(subject_minutes, cutoff - 15 * MINUTE, 15)
    if recent15 is not None and prior15 is not None:
        result["local_momentum_acceleration"] = recent15 - prior15

    h25 = _last_aligned(subject_hours, cutoff, 25)
    if h25:
        current_sma = statistics.fmean(x["close"] for x in h25[-24:])
        previous_sma = statistics.fmean(x["close"] for x in h25[-25:-1])
        latest_close = h25[-1]["close"]
        result["distance_from_h1_sma24"] = latest_close / current_sma - 1
        result["h1_sma24_slope"] = current_sma / previous_sma - 1
        recent6h = h25[-6:]
        result["distance_from_6h_high"] = latest_close / max(x["high"] for x in recent6h) - 1
        result["distance_from_6h_low"] = latest_close / min(x["low"] for x in recent6h) - 1

    context_returns: dict[str, dict[int, float | None]] = {}
    for context_symbol in SYMBOLS:
        context_returns[context_symbol] = {width: _rolling_return(minutes[context_symbol], cutoff, width) for width in (5, 15, 60)}
    for leader, prefix in (("BTCUSDT", "btc"), ("ETHUSDT", "eth")):
        for width in (5, 15, 60):
            leader_value = context_returns[leader][width]
            result[f"{prefix}_minus_subject_return_{width}m"] = None if leader_value is None or local[width] is None else leader_value - local[width]
    others = [context_returns[s][15] for s in SYMBOLS if s != symbol]
    if all(x is not None for x in others):
        result["other_four_breadth_15m"] = sum(float(x) > 0 for x in others) / 4
    btc15, eth15 = context_returns["BTCUSDT"][15], context_returns["ETHUSDT"][15]
    if btc15 is not None and eth15 is not None:
        result["btc_eth_agreement_15m"] = int(_sign(btc15) == _sign(eth15))
    missing = [name for name in FEATURE_COLUMNS if result[name] is None or not math.isfinite(float(result[name]))]
    return result, missing


def _window_return(series: DenseSeries, cutoff: int, width_minutes: int) -> float | None:
    return _rolling_return(series, cutoff, width_minutes)


def _sign(value: float) -> int:
    return 1 if value > 0 else -1 if value < 0 else 0


def build_milestone_row(entry: dict, horizon: dict, spec: dict, inputs: C3Inputs) -> dict | None:
    symbol = entry["symbol"]
    series = inputs.minutes[symbol]
    entry_ms = _pre_holdout_timestamp(entry["entry_execution_ms"], "entry")
    horizon_ms = _pre_holdout_timestamp(horizon["common_horizon_end_ms"], "horizon")
    entry_price, horizon_price = float(entry["entry_price"]), float(horizon["p0_raw_exit_price"])
    milestone_price = entry_price * spec["milestone"]
    milestone_ms = None
    timing = "localized_to_1m_interval"
    touch = None
    for ts in range(entry_ms + MINUTE, horizon_ms, MINUTE):
        row = series.get(ts)
        if row is None:
            return _pre_milestone_gap_row(entry, horizon, spec, ts)
        if row["high"] >= milestone_price:
            milestone_ms, touch = ts, row
            break
    if milestone_ms is None and horizon_price >= milestone_price:
        milestone_ms, timing = horizon_ms, "exact_H_execution_point"
    if milestone_ms is None:
        return None
    upper, fallback = entry_price * spec["upper"], entry_price * spec["fallback"]
    outcome = _resolve_label(series, milestone_ms, horizon_ms, horizon_price, upper, fallback, touch)
    features, missing = compute_features(symbol, entry_ms, entry_price, milestone_ms, inputs.minutes, inputs.bars5, inputs.hours, spec["milestone"] - 1)
    availability_ms = milestone_ms if timing == "exact_H_execution_point" else milestone_ms + MINUTE
    split = _split_metadata(milestone_ms, outcome)
    provenance = {
        "dataset_version": DATASET_VERSION, "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "trade_id": entry["trade_id"], "symbol": symbol, "entry_fixture_id": entry["entry_fixture_id"],
        "entry_execution_ts": entry["entry_execution_ts"], "entry_execution_ms": entry_ms, "entry_price": entry["entry_price"],
        "milestone_id": spec["id"], "milestone_ts": iso(milestone_ms), "milestone_interval_start_ts": iso(milestone_ms),
        "milestone_interval_start_ms": milestone_ms, "milestone_available_ts": iso(availability_ms), "milestone_available_ms": availability_ms,
        "feature_cutoff_ts": iso(milestone_ms), "feature_cutoff_ms": milestone_ms, "milestone_timing": timing,
        "milestone_price": _number(milestone_price), "common_horizon_end_ts": horizon["common_horizon_end_ts"],
        "common_horizon_end_ms": horizon_ms, "source_resolution": "1m_or_exact_H_point",
        "rolling_1m_available_ts": iso(milestone_ms),
        "aligned_5m_available_ts": iso(milestone_ms // FIVE_MINUTES * FIVE_MINUTES),
        "h1_available_ts": iso(milestone_ms // HOUR * HOUR), "cross_asset_available_ts": iso(milestone_ms),
        "data_quality_flag": "complete",
        "feature_eligible": not missing, "feature_ineligible_reason": ";".join(missing), **split,
    }
    return {**provenance, **features, **outcome, "upper_barrier_price": _number(upper), "fallback_barrier_price": _number(fallback)}


def _pre_milestone_gap_row(entry: dict, horizon: dict, spec: dict, gap_ms: int) -> dict:
    """Represent broken pre-milestone chronology without inventing a milestone or label."""
    entry_ms = _pre_holdout_timestamp(entry["entry_execution_ms"], "entry")
    horizon_ms = _pre_holdout_timestamp(horizon["common_horizon_end_ms"], "horizon")
    blank_features = {name: None for name in FEATURE_COLUMNS}
    provenance = {
        "dataset_version": DATASET_VERSION, "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "trade_id": entry["trade_id"], "symbol": entry["symbol"], "entry_fixture_id": entry["entry_fixture_id"],
        "entry_execution_ts": entry["entry_execution_ts"], "entry_execution_ms": entry_ms,
        "entry_price": entry["entry_price"], "milestone_id": spec["id"], "milestone_ts": "",
        "milestone_interval_start_ts": "", "milestone_interval_start_ms": "",
        "milestone_available_ts": "", "milestone_available_ms": "", "feature_cutoff_ts": "",
        "feature_cutoff_ms": "", "milestone_timing": "unresolved_pre_milestone_gap",
        "milestone_price": _number(float(entry["entry_price"]) * spec["milestone"]),
        "common_horizon_end_ts": horizon["common_horizon_end_ts"], "common_horizon_end_ms": horizon_ms,
        "source_resolution": "1m", "rolling_1m_available_ts": "", "aligned_5m_available_ts": "",
        "h1_available_ts": "", "cross_asset_available_ts": "", "data_quality_flag": "pre_milestone_gap",
        "feature_eligible": False, "feature_ineligible_reason": "pre_milestone_gap",
        "split_eligibility": "", "split_exclusion_reason": "pre_milestone_gap",
        "applicable_label_resolution_boundary_ts": "",
    }
    outcome = {
        "label": "", "label_name": "", "label_resolution_ts": iso(gap_ms),
        "label_resolution_ms": gap_ms, "label_resolution_timing": "gap_detected_before_milestone",
        "censored": True, "censor_reason": "pre_milestone_gap", "ambiguous": False,
        "ambiguity_reason": "", "upper_barrier_price": "", "fallback_barrier_price": "",
        "time_to_resolution_seconds": "",
    }
    return {**provenance, **blank_features, **outcome}


def _resolve_label(series: DenseSeries, milestone_ms: int, horizon_ms: int, horizon_price: float,
                   upper: float, fallback: float, touch: dict | None) -> dict:
    def resolved(label, name, ts, timing, ambiguous=False, ambiguity_reason=""):
        return {"label": label, "label_name": name, "label_resolution_ts": iso(ts), "label_resolution_ms": ts,
                "label_resolution_timing": timing, "censored": False, "censor_reason": "",
                "ambiguous": ambiguous, "ambiguity_reason": ambiguity_reason,
                "time_to_resolution_seconds": (ts - milestone_ms) // 1000}
    if touch is not None:
        up, down = touch["high"] >= upper, touch["low"] <= fallback
        if up and down:
            return resolved("", "", milestone_ms, "localized_to_1m_interval", True, "ambiguous_same_minute")
        if up:
            return resolved(1, "continuation", milestone_ms, "localized_to_1m_interval")
    for ts in range(milestone_ms + MINUTE, horizon_ms, MINUTE):
        row = series.get(ts)
        if row is None:
            return {"label": "", "label_name": "", "label_resolution_ts": iso(ts), "label_resolution_ms": ts,
                    "label_resolution_timing": "gap_detected", "censored": True, "censor_reason": f"gap_at_{ts}",
                    "ambiguous": False, "ambiguity_reason": "", "time_to_resolution_seconds": ""}
        up, down = row["high"] >= upper, row["low"] <= fallback
        if up and down:
            return resolved("", "", ts, "localized_to_1m_interval", True, "ambiguous_same_minute")
        if up: return resolved(1, "continuation", ts, "localized_to_1m_interval")
        if down: return resolved(0, "fallback", ts, "localized_to_1m_interval")
    if horizon_price >= upper:
        return resolved(1, "continuation", horizon_ms, "exact_H_execution_point")
    if horizon_price <= fallback:
        return resolved(0, "fallback", horizon_ms, "exact_H_execution_point")
    return {"label": "", "label_name": "", "label_resolution_ts": iso(horizon_ms), "label_resolution_ms": horizon_ms,
            "label_resolution_timing": "exact_H_execution_point", "censored": True, "censor_reason": "right_censored_at_H",
            "ambiguous": False, "ambiguity_reason": "", "time_to_resolution_seconds": ""}


def _split_metadata(milestone_ms: int, outcome: dict) -> dict:
    boundaries = {
        "fold_a_train": (1704067200000, 1719792000000), "fold_a_validation": (1719792000000, 1727740800000),
        "fold_b_train": (1704067200000, 1727740800000), "fold_b_validation": (1727740800000, 1735689600000),
        "final_2024_fit": (1704067200000, 1735689600000), "locked_2025_evaluation": (1735689600000, STUDY_END_MS),
    }
    eligibility, exclusions, applicable = [], [], []
    event_ms = int(outcome["label_resolution_ms"])
    for name, (start, end) in boundaries.items():
        if not start <= milestone_ms < end:
            continue
        applicable.append(iso(end))
        if event_ms >= end:
            reason = "unresolved_at_2025_evaluation_boundary" if name == "locked_2025_evaluation" else (
                "unresolved_at_validation_boundary" if "validation" in name else "unresolved_at_training_boundary")
            exclusions.append(f"{name}:{reason}")
        elif outcome["ambiguous"]:
            exclusions.append(f"{name}:ambiguous")
        elif outcome["censored"]:
            exclusions.append(f"{name}:censored")
        else:
            eligibility.append(name)
    return {"split_eligibility": ";".join(eligibility), "split_exclusion_reason": ";".join(exclusions),
            "applicable_label_resolution_boundary_ts": ";".join(applicable)}


def build_datasets(inputs: C3Inputs) -> dict[str, list[dict]]:
    result = {key: [] for key in MILESTONES}
    for entry in inputs.entries:
        horizon = inputs.horizons[entry["trade_id"]]
        for key, spec in MILESTONES.items():
            row = build_milestone_row(entry, horizon, spec, inputs)
            if row is not None: result[key].append(row)
    for rows in result.values():
        rows.sort(key=lambda r: (_audit_order_ms(r), r["symbol"], r["trade_id"], r["milestone_id"]))
    return result


def _audit_order_ms(row: dict) -> int:
    value = row.get("milestone_interval_start_ms")
    return int(value) if value not in (None, "") else int(row["label_resolution_ms"])


def schema_document() -> dict:
    document = {"version": FEATURE_SCHEMA_VERSION, "provenance_columns": list(PROVENANCE_COLUMNS),
                "feature_columns": list(FEATURE_COLUMNS), "outcome_columns": list(OUTCOME_COLUMNS),
                "keyed_feature_columns": list(KEYED_FEATURE_COLUMNS),
                "model_matrix_columns": list(FEATURE_MATRIX_COLUMNS),
                "model_matrix_row_key_columns": list(ROW_KEY_COLUMNS),
                "model_matrix_policy": "complete-case feature-eligible milestone rows only; exact ordered feature_columns; row correspondence is stored separately",
                "m2_conditioning": "M2 rows are conditional on the trade already reaching +2%; M1 and M2 populations are not directly comparable."}
    document["schema_sha256"] = hashlib.sha256(json.dumps(document, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return document


def write_checkpoint(repo: Path, artifact_dir: Path) -> dict:
    inputs = load_accepted_inputs(repo)
    datasets = build_datasets(inputs)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    schema = schema_document()
    write_json(artifact_dir / "input_manifest.json", inputs.manifest)
    write_json(artifact_dir / "feature_schema.json", schema)
    core_hashes, summaries, ledger = {}, {}, []
    for key, rows in datasets.items():
        prefix = key.lower()
        milestone_rows = [row for row in rows if row["milestone_interval_start_ms"] not in (None, "")]
        model_rows = [row for row in milestone_rows if row["feature_eligible"]]
        audit_path = artifact_dir / f"{prefix}_audit.csv"
        keyed_path = artifact_dir / f"{prefix}_keyed_features.csv"
        feature_path = artifact_dir / f"{prefix}_features.csv"
        row_key_path = artifact_dir / f"{prefix}_feature_row_keys.csv"
        outcome_path = artifact_dir / f"{prefix}_outcomes.csv"
        _write_csv(audit_path, rows, AUDIT_COLUMNS)
        _write_csv(keyed_path, milestone_rows, KEYED_FEATURE_COLUMNS)
        _write_csv(feature_path, model_rows, FEATURE_MATRIX_COLUMNS)
        row_keys = [{"model_row_index": index, "trade_id": row["trade_id"], "milestone_id": row["milestone_id"]}
                    for index, row in enumerate(model_rows)]
        _write_csv(row_key_path, row_keys, ROW_KEY_COLUMNS)
        _write_csv(outcome_path, milestone_rows, OUTCOME_COLUMNS)
        hashes = {
            "audit_table_file_hash": sha256_file(audit_path),
            "audit_table_semantic_hash": _semantic_hash(rows, AUDIT_COLUMNS),
            "keyed_feature_table_file_hash": sha256_file(keyed_path),
            "keyed_feature_table_semantic_hash": _semantic_hash(milestone_rows, KEYED_FEATURE_COLUMNS),
            "feature_matrix_file_hash": sha256_file(feature_path),
            "feature_matrix_semantic_hash": _semantic_hash(model_rows, FEATURE_MATRIX_COLUMNS),
            "feature_row_keys_file_hash": sha256_file(row_key_path),
            "feature_row_keys_semantic_hash": _semantic_hash(row_keys, ROW_KEY_COLUMNS),
            "outcome_table_file_hash": sha256_file(outcome_path),
            "outcome_table_semantic_hash": _semantic_hash(milestone_rows, OUTCOME_COLUMNS),
        }
        core_hashes[key] = hashes
        summaries[key] = _summary(rows, hashes)
        ledger.extend(_exclusion_rows(rows))
        write_json(artifact_dir / f"{prefix}_summary.json", summaries[key])
    ledger.sort(key=lambda r: (r["milestone_id"], r["symbol"], r["month"], r["reason"]))
    write_json(artifact_dir / "exclusion_ledger.json", ledger)
    manifest = {"manifest_version": "C3_T1_T2_REPRODUCIBILITY_V1", "predecessor_revision": PREDECESSOR_REVISION,
                "execution_revision": _git_revision(repo), "feature_schema_hash": schema["schema_sha256"],
                "feature_schema_file_hash": sha256_file(artifact_dir / "feature_schema.json"),
                "input_manifest_sha256": sha256_file(artifact_dir / "input_manifest.json"), "core_hashes": core_hashes,
                "milestone_counts_reconciled": _reconcile(summaries),
                "cross_asset_duplicate_safety": _cross_asset_duplicate_safety(datasets), "predictive_models_run": False,
                "predictive_metrics_computed": False, "2026_market_data_accessed": False,
                "independent_rebuild_verified": False}
    write_json(artifact_dir / "reproducibility_manifest.json", manifest)
    return {"feature_schema_hash": schema["schema_sha256"], "core_hashes": core_hashes, "summaries": summaries}


def verify_rebuild(repo: Path, artifact_dir: Path) -> dict:
    with tempfile.TemporaryDirectory(prefix="c3_rebuild_a_") as first_dir, tempfile.TemporaryDirectory(prefix="c3_rebuild_b_") as second_dir:
        first = write_checkpoint(repo, Path(first_dir))
        second = write_checkpoint(repo, Path(second_dir))
    if first != second:
        raise RuntimeError("independent offline rebuild core hashes differ")
    final = write_checkpoint(repo, artifact_dir)
    if final != first:
        raise RuntimeError("published checkpoint differs from independent offline rebuilds")
    manifest_path = artifact_dir / "reproducibility_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["independent_rebuild_verified"] = True
    manifest["independent_rebuilds"] = 2
    manifest["verified_core_hashes"] = second["core_hashes"]
    write_json(manifest_path, manifest)
    return {**second, "independent_rebuild_verified": True}


def _summary(rows: list[dict], hashes: dict) -> dict:
    milestone_rows = [r for r in rows if r["milestone_interval_start_ms"] not in (None, "")]
    gap_rows = [r for r in rows if r["censor_reason"] == "pre_milestone_gap"]
    labels = Counter(str(r["label"]) for r in milestone_rows)
    boundary = Counter({"unresolved_at_training_boundary": 0, "unresolved_at_validation_boundary": 0,
                        "unresolved_at_2025_evaluation_boundary": 0})
    by_symbol = Counter(r["symbol"] for r in milestone_rows)
    by_month = Counter(r["milestone_ts"][:7] for r in milestone_rows)
    for row in milestone_rows:
        for item in str(row["split_exclusion_reason"]).split(";"):
            if ":unresolved_at_" in item: boundary[item.split(":", 1)[1]] += 1
    ineligible = [r for r in milestone_rows if not r["feature_eligible"]]
    return {"milestone_id": rows[0]["milestone_id"] if rows else "", "m2_conditioned_on_reaching_plus_2pct": bool(rows and rows[0]["milestone_id"].startswith("M2")),
            "total_milestone_rows": len(milestone_rows), "pre_milestone_gap_audit_rows": len(gap_rows),
            "continuation": labels["1"], "fallback": labels["0"],
            "censored": sum(bool(r["censored"]) for r in milestone_rows), "ambiguous": sum(bool(r["ambiguous"]) for r in milestone_rows),
            "feature_eligible": sum(bool(r["feature_eligible"]) for r in milestone_rows), "feature_ineligible": len(ineligible),
            "model_matrix_rows": sum(bool(r["feature_eligible"]) for r in milestone_rows),
            "model_matrix_column_count": len(FEATURE_MATRIX_COLUMNS),
            "model_matrix_identifiers_absent": True,
            "complete_case_scope_warning": {
                "missingness_concentration": "structurally concentrated in the fastest milestone arrivals",
                "maximum_ineligible_time_from_entry_seconds": max((int(r["time_from_entry_seconds"]) for r in ineligible), default=None),
                "observed_fast_arrival_fact": ("all excluded M1 rows reached the milestone in under 10 minutes"
                                               if rows and rows[0]["milestone_id"].startswith("M1") else
                                               "all excluded M2 rows reached the milestone within 5 minutes"),
                "inference_scope": "T3 inference applies only to feature-eligible milestone states and must not claim coverage of the fastest arrivals",
            },
            "fold_boundary_exclusions": dict(sorted(boundary.items())), "by_symbol": dict(sorted(by_symbol.items())),
            "by_month": dict(sorted(by_month.items())), "hashes": hashes}


def _exclusion_rows(rows: list[dict]) -> list[dict]:
    counts = Counter()
    for row in rows:
        if row["censor_reason"] == "pre_milestone_gap":
            month = row["label_resolution_ts"][:7]
            counts[(row["milestone_id"], row["symbol"], month, "pre_milestone_gap")] += 1
            continue
        month = row["milestone_ts"][:7]
        for reason in str(row["feature_ineligible_reason"]).split(";"):
            if reason: counts[(row["milestone_id"], row["symbol"], month, reason)] += 1
    return [{"milestone_id": k[0], "symbol": k[1], "month": k[2], "feature_family": _feature_family(k[3]),
             "reason": k[3], "count": v} for k, v in counts.items()]


def _feature_family(feature: str) -> str:
    if feature == "pre_milestone_gap":
        return "chronology"
    index = FEATURE_COLUMNS.index(feature)
    return "A" if index < 7 else "B" if index < 14 else "C" if index < 18 else "D" if index < 23 else "E" if index < 27 else "F"


def _cross_asset_duplicate_safety(datasets: dict[str, list[dict]]) -> dict:
    result = {}
    for subject, prefix in (("BTCUSDT", "btc"), ("ETHUSDT", "eth")):
        subject_rows = [row for rows in datasets.values() for row in rows if row["symbol"] == subject]
        for width in (5, 15, 60):
            context = f"{prefix}_minus_subject_return_{width}m"
            local = f"local_return_{width}m"
            pairs = [(row[context], row[local]) for row in subject_rows if row[context] is not None and row[local] is not None]
            duplicate = bool(pairs) and all(float(a) == float(b) for a, b in pairs)
            if duplicate:
                raise RuntimeError(f"cross-asset context duplicates local predictor: {subject} {width}m")
            result[f"{subject}_{width}m"] = {"rows_checked": len(pairs), "exact_duplicate": False}
    return result


def _reconcile(summaries: dict) -> bool:
    expected = {"M1": (852, 432, 385, 34, 1, 806, 46), "M2": (552, 279, 264, 8, 1, 546, 6)}
    for key, values in expected.items():
        summary = summaries[key]
        actual = (summary["total_milestone_rows"], summary["continuation"], summary["fallback"], summary["censored"],
                  summary["ambiguous"], summary["feature_eligible"], summary["feature_ineligible"])
        if actual != values:
            raise RuntimeError(f"{key} milestone/label reconciliation failed: expected {values}, got {actual}")
        if summary["hashes"]["keyed_feature_table_semantic_hash"] != EXPECTED_KEYED_FEATURE_HASHES[key]:
            raise RuntimeError(f"{key} accepted feature values changed unexpectedly")
    return True


def _write_csv(path: Path, rows: list[dict], columns: tuple[str, ...]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: _number(row.get(column, "")) for column in columns})


def _semantic_hash(rows: list[dict], columns: tuple[str, ...]) -> str:
    return hash_rows(({column: _number(row.get(column, "")) for column in columns} for row in rows), columns)


def _number(value: object) -> object:
    if isinstance(value, float):
        return format(value, ".17g")
    return value
