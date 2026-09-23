from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator


SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT")
SOURCE_START_MS = 1_703_980_800_000  # 2023-12-31T00:00:00Z
STUDY_START_MS = 1_704_067_200_000  # 2024-01-01T00:00:00Z
SANITY_END_MS = 1_711_929_600_000  # 2024-04-01T00:00:00Z
STUDY_END_MS = 1_767_225_600_000  # 2026-01-01T00:00:00Z
HISTORY_SCHEMA_VERSION = "c2-history-1m-gzip-v1"
AGGREGATION_VERSION = "c2-causal-aggregate-v1"
ENTRY_FIXTURE_ID = "E1_H1_SMA24_CROSS_V1"
ENTRY_NOTIONAL_USDT = 1000.0
MAX_COMPRESSED_BYTES = 400 * 1024 * 1024
MAX_LOCAL_BYTES = 2 * 1024 * 1024 * 1024

AGGREGATE_COLUMNS = (
    "symbol", "timeframe", "open_time_ms", "open_time_utc", "available_at_ms",
    "available_at_utc", "open", "high", "low", "close", "base_volume",
    "quote_volume", "trade_count", "source_rows",
)
ENTRY_COLUMNS = (
    "trade_id", "symbol", "entry_fixture_id", "entry_signal_ts",
    "entry_decision_ts", "entry_execution_ts", "entry_execution_ms",
    "entry_price", "entry_notional_usdt", "entry_timeframe",
)


def research_partitions() -> dict:
    return {
        "warmup": {"start_utc": iso(SOURCE_START_MS), "end_exclusive_utc": iso(STUDY_START_MS)},
        "sanity_calibration": {"start_utc": iso(STUDY_START_MS), "end_exclusive_utc": iso(SANITY_END_MS)},
        "headline_evaluation": {"start_utc": iso(SANITY_END_MS), "end_exclusive_utc": iso(STUDY_END_MS)},
    }


def hash_rows(rows: Iterable[dict], columns: Iterable[str]) -> str:
    payload = io.StringIO(newline="")
    writer = csv.DictWriter(payload, fieldnames=tuple(columns), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: row[key] for key in writer.fieldnames})
    return hashlib.sha256(payload.getvalue().encode()).hexdigest()


def iter_gzip_csv(path: Path) -> Iterator[dict]:
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        yield from csv.DictReader(handle)


def write_gzip_csv(path: Path, rows: Iterable[dict], columns: Iterable[str]) -> str:
    from .ingest import sha256_file

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("wb") as binary:
        with gzip.GzipFile(filename="", mode="wb", fileobj=binary, mtime=0) as gz:
            with io.TextIOWrapper(gz, encoding="utf-8", newline="") as text:
                writer = csv.DictWriter(text, fieldnames=tuple(columns), lineterminator="\n")
                writer.writeheader()
                writer.writerows(rows)
    os.replace(tmp, path)
    return sha256_file(path)


def valid_minute(row: dict) -> bool:
    try:
        ts = int(row["open_time_ms"])
        o, h, low, close = (float(row[key]) for key in ("open", "high", "low", "close"))
        base, quote = float(row["base_volume"]), float(row["quote_volume"])
        trades = int(row["trade_count"])
    except (KeyError, TypeError, ValueError, OverflowError):
        return False
    return (ts % 60_000 == 0 and all(math.isfinite(x) and x > 0 for x in (o, h, low, close))
            and h >= max(o, close) and low <= min(o, close) and low <= h
            and math.isfinite(base) and base >= 0 and math.isfinite(quote) and quote >= 0 and trades >= 0)


def canonical_number(value: float) -> str:
    return f"{value:.17g}"


def iso(value_ms: int) -> str:
    return datetime.fromtimestamp(value_ms / 1000, timezone.utc).isoformat()


def tree_size(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file()) if path.is_dir() else path.stat().st_size


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
