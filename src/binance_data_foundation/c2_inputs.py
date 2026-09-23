"""Compatibility façade and orchestration for the C2 T1/T2 input pipeline."""

from __future__ import annotations

import csv
from pathlib import Path

from .c2_acquisition import (
    MINUTE_COLUMNS, MONTHLY_BASE_URL, approved_months, ingest_history,
    theoretical_row_counts, validate_month, _obtain_month, _read_month,
)
from .c2_aggregation import AggregationResult, aggregate_minutes, stream_aggregates
from .c2_common import (
    AGGREGATE_COLUMNS, AGGREGATION_VERSION, ENTRY_COLUMNS, ENTRY_FIXTURE_ID,
    ENTRY_NOTIONAL_USDT, HISTORY_SCHEMA_VERSION, MAX_COMPRESSED_BYTES,
    MAX_LOCAL_BYTES, SOURCE_START_MS, STUDY_END_MS, STUDY_START_MS, SYMBOLS,
    hash_rows, iter_gzip_csv, research_partitions, write_gzip_csv, write_json,
)
from .c2_entries import FrozenEntryResult, freeze_entries, hourly_sma24
from .ingest import sha256_file


def build_frozen_inputs(normalized_dir: Path, output_dir: Path, artifact_dir: Path) -> dict:
    """Build validated aggregates and E1 entries; contains no exit-policy behavior."""
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    aggregate_hashes: dict[str, str] = {}
    aggregate_rows: dict[str, dict[str, int]] = {}
    aggregate_exclusions: dict[str, dict[str, int]] = {}
    all_entries: list[dict] = []
    all_signals: list[dict] = []
    suppressed = 0
    unexecutable = 0
    for symbol in SYMBOLS:
        minute_path = normalized_dir / f"{symbol}_1m.csv.gz"
        if not minute_path.exists():
            raise FileNotFoundError(minute_path)
        minute_execution_rows = [row for row in iter_gzip_csv(minute_path) if int(row["open_time_ms"]) % 3_600_000 == 0]
        aggregate_rows[symbol] = {}
        aggregate_exclusions[symbol] = {}
        hour_bars: list[dict] = []
        for timeframe in (5, 60):
            valid: list[dict] = []
            exclusions: list[dict] = []
            for kind, record in stream_aggregates(iter_gzip_csv(minute_path), timeframe):
                (valid if kind == "bar" else exclusions).append(record)
            label = "5m" if timeframe == 5 else "1h"
            aggregate_rows[symbol][label] = len(valid)
            aggregate_exclusions[symbol][label] = len(exclusions)
            path = output_dir / f"{symbol}_{label}.csv.gz"
            aggregate_hashes[path.name] = write_gzip_csv(path, valid, AGGREGATE_COLUMNS)
            if timeframe == 60:
                hour_bars = valid
        frozen = freeze_entries(hour_bars, minute_execution_rows)
        all_entries.extend(frozen.entries)
        all_signals.extend(frozen.signals)
        suppressed += frozen.suppressed_refractory
        unexecutable += frozen.unexecutable
    all_entries.sort(key=lambda r: (int(r["entry_execution_ms"]), r["symbol"], r["trade_id"]))
    frozen_hash = hash_rows(all_entries, ENTRY_COLUMNS)
    entries_path = artifact_dir / "frozen_entries.csv"
    with entries_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ENTRY_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(all_entries)
    entries_by_symbol = {symbol: sum(row["symbol"] == symbol and row["status"] == "executable" for row in all_signals) for symbol in SYMBOLS}
    entries_by_month: dict[str, int] = {}
    entries_per_timestamp: dict[int, int] = {}
    for row in all_entries:
        month = row["entry_execution_ts"][:7]
        entries_by_month[month] = entries_by_month.get(month, 0) + 1
        ts = int(row["entry_execution_ms"])
        entries_per_timestamp[ts] = entries_per_timestamp.get(ts, 0) + 1
    summary = {
        "aggregation_version": AGGREGATION_VERSION, "entry_fixture_id": ENTRY_FIXTURE_ID,
        "entry_notional_usdt": ENTRY_NOTIONAL_USDT, "research_partitions": research_partitions(),
        "theoretical_row_counts": theoretical_row_counts(), "aggregate_hashes": aggregate_hashes,
        "aggregate_rows": aggregate_rows, "aggregate_exclusions": aggregate_exclusions,
        "total_executable_entries": len(all_entries), "entries_by_symbol": entries_by_symbol,
        "entries_by_month": dict(sorted(entries_by_month.items())),
        "suppressed_refractory_signals": suppressed, "unexecutable_signals": unexecutable,
        "simultaneous_entry_timestamps": sum(count > 1 for count in entries_per_timestamp.values()),
        "entries_at_simultaneous_timestamps": sum(count for count in entries_per_timestamp.values() if count > 1),
        "max_entries_same_timestamp": max(entries_per_timestamp.values(), default=0),
        "overlap_note": "Position overlap is not defined before exits/common horizons; only equal entry timestamps are counted.",
        "frozen_entry_hash": frozen_hash, "frozen_entry_file_hash": sha256_file(entries_path),
    }
    write_json(artifact_dir / "frozen_input_summary.json", summary)
    return summary


__all__ = [
    "AGGREGATE_COLUMNS", "AggregationResult", "ENTRY_FIXTURE_ID", "FrozenEntryResult",
    "aggregate_minutes", "approved_months", "build_frozen_inputs", "freeze_entries",
    "hash_rows", "hourly_sma24", "ingest_history", "research_partitions",
    "stream_aggregates", "theoretical_row_counts", "validate_month", "_obtain_month", "_read_month",
]
